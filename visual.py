"""Tracking-API des Visual-Moduls — Logik-Schicht zwischen HTTP und Detector.

    start_tracking(name)   Detector im Hintergrund starten
    get_latest()           aktuelles aggregiertes Window-Ergebnis
    stop_tracking()        Detector beenden
    prewarm()              Modell vorladen (vom Server beim Start)
    get_health_status()    (detector_name, ready) für /health

Aggregation über ein Sliding Window der letzten N Frames. Detector-Wahl per
CONFIG.detector_mode; im Auto-Modus wird Hailo probiert und bei Fehler auf
YOLO zurückgefallen.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque

from config import CONFIG
from frame_buffer import FRAME_BUFFER
from visual_interface import DetectorProtocol, VisionResult

log = logging.getLogger("visual.core")

_detector: DetectorProtocol | None = None
_active_detector_name: str = "none"

_tracking_lock = threading.Lock()
_tracking_thread: threading.Thread | None = None
_stop_event: threading.Event | None = None
_current_name: str | None = None

_window_lock = threading.Lock()
_window: deque[VisionResult] = deque(maxlen=CONFIG.window_size)
_last_frame_ts: float = 0.0


def _try_hailo() -> DetectorProtocol | None:
    try:
        from hailo_detector import HailoDetector, _hailo_available
    except Exception as e:
        log.warning("Hailo-Module nicht importierbar: %s", e)
        return None
    if not _hailo_available:
        return None
    try:
        return HailoDetector()
    except Exception as e:
        log.warning("Hailo-Initialisierung fehlgeschlagen: %s", e)
        return None


def _try_yolo() -> DetectorProtocol:
    from yolo_detector import YoloDetector
    return YoloDetector()


def _get_detector() -> DetectorProtocol:
    global _detector, _active_detector_name
    if _detector is not None:
        return _detector

    mode = CONFIG.detector_mode
    if mode == "yolo":
        _detector, _active_detector_name = _try_yolo(), "yolo"
    elif mode == "hailo":
        d = _try_hailo()
        if d is None:
            raise RuntimeError(
                "detector_mode='hailo' gesetzt, aber Hailo nicht verfügbar. "
                "Config/Env entfernen (Auto-Fallback) oder Hailo-Stack reparieren."
            )
        _detector, _active_detector_name = d, "hailo"
    else:
        d = _try_hailo()
        if d is not None:
            _detector, _active_detector_name = d, "hailo"
        else:
            log.info("Auto-Modus: Hailo nicht verfügbar, Fallback auf YOLO.")
            _detector, _active_detector_name = _try_yolo(), "yolo"

    log.info("%s aktiv", type(_detector).__name__)
    return _detector


def set_detector(detector: DetectorProtocol | None) -> None:
    """Für Tests: eigenen Detector injizieren (oder zurücksetzen)."""
    global _detector, _active_detector_name
    _detector = detector
    _active_detector_name = type(detector).__name__.lower() if detector else "none"


def active_detector() -> str:
    return _active_detector_name


def get_health_status() -> tuple[str, bool]:
    """(detector_name, ready) für /health. ready=True, sobald ein Detector geladen ist."""
    return _active_detector_name, _detector is not None


def prewarm() -> None:
    detector = _get_detector()
    if hasattr(detector, "prewarm"):
        detector.prewarm()


def _on_frame(frame: VisionResult) -> None:
    global _last_frame_ts
    with _window_lock:
        _window.append(frame)
        _last_frame_ts = time.monotonic()


def _aggregate(name: str) -> dict:
    with _window_lock:
        snapshot = list(_window)
        last_ts = _last_frame_ts

    # Keine alten Treffer "einfrieren", wenn der Detector nichts mehr liefert.
    if last_ts == 0.0 or (time.monotonic() - last_ts) > CONFIG.stale_after_seconds:
        return _empty_result(name)

    hits = [f for f in snapshot if f.found]
    if len(hits) < CONFIG.min_hits_in_window:
        return _empty_result(name)

    n = len(hits)
    return {
        "name": name,
        "found": True,
        "confidence": round(sum(f.confidence for f in hits) / n, 4),
        "x": round(sum(f.x for f in hits) / n, 4),
        "y": round(sum(f.y for f in hits) / n, 4),
        "w": round(sum(f.w for f in hits) / n, 4),
        "h": round(sum(f.h for f in hits) / n, 4),
    }


def _empty_result(name: str) -> dict:
    return {"name": name, "found": False, "confidence": 0.0,
            "x": None, "y": None, "w": None, "h": None}


def start_tracking(name: str) -> dict:
    """Startet den Detector im Hintergrund. Idempotent: gleicher Name = no-op,
    anderer Name stoppt das alte Tracking und startet neu."""
    global _tracking_thread, _stop_event, _current_name, _last_frame_ts
    name = name.strip()

    with _tracking_lock:
        if _tracking_thread is not None and _tracking_thread.is_alive():
            if _current_name == name:
                return {"status": "running", "name": name}
            _stop_locked()

        with _window_lock:
            _window.clear()
            _last_frame_ts = time.monotonic()  # Grace-Period bis zum ersten Frame

        _current_name = name
        _stop_event = threading.Event()
        # _get_detector() bewusst unter dem Lock: verhindert doppelte Init bei
        # parallelen start-Aufrufen. Im Normalbetrieb hat prewarm() schon gebaut.
        detector = _get_detector()
        _tracking_thread = threading.Thread(
            target=_run_stream, args=(detector, name, _stop_event), daemon=True
        )
        _tracking_thread.start()

    return {"status": "running", "name": name}


def _run_stream(detector: DetectorProtocol, name: str, stop_event: threading.Event) -> None:
    # Kein Auto-Fallback bei Laufzeit-Crash: der Controller sieht dann found=False
    # und kann stop + start neu auslösen.
    try:
        detector.stream(name, _on_frame, stop_event)
    except Exception as e:
        log.error("Stream-Fehler: %s", e, exc_info=True)
        with _window_lock:
            _window.clear()
        FRAME_BUFFER.clear()


def get_latest() -> dict:
    with _tracking_lock:
        running = _tracking_thread is not None and _tracking_thread.is_alive()
        name = _current_name or ""
    if not running:
        return {"status": "idle"}
    return {"status": "running", **_aggregate(name)}


def stop_tracking() -> dict:
    with _tracking_lock:
        was_running = _tracking_thread is not None and _tracking_thread.is_alive()
        _stop_locked()
    return {"status": "stopped", "was_running": was_running}


def _stop_locked() -> None:
    """Muss unter _tracking_lock aufgerufen werden."""
    global _tracking_thread, _stop_event, _current_name
    if _stop_event is not None:
        _stop_event.set()
    if _tracking_thread is not None:
        _tracking_thread.join(timeout=CONFIG.stop_timeout_seconds)
        if _tracking_thread.is_alive():
            log.warning(
                "Detector-Thread nach %.1fs Timeout noch aktiv — Kamera/Pipeline "
                "evtl. noch belegt.", CONFIG.stop_timeout_seconds,
            )
    _tracking_thread = None
    _stop_event = None
    _current_name = None
    with _window_lock:
        _window.clear()
    FRAME_BUFFER.clear()
