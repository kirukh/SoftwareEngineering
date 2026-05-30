"""
visual.py — Tracking-API des Visual-Moduls.

Logik-Schicht zwischen HTTP (server.py) und Detector:
    start_tracking(name)   # Detector im Hintergrund starten
    get_latest()           # aktuelles aggregiertes Window-Ergebnis
    stop_tracking()        # Detector sauber beenden
    prewarm()              # Modell vorladen (vom Server beim Start)

Aggregation: Sliding Window über die letzten N Roh-Frames vom Detector.
Größe und Mindesttreffer kommen aus CONFIG (siehe config.py).

Detector-Wahl per CONFIG.detector_mode (auch via VISUAL_DETECTOR Env-Var).
Auto-Modus: Hailo wird probiert, bei jedem Fehler fällt der Code auf YOLO
zurück (Sprint-Ziel: Rollout muss laufen, auch wenn das Hailo-Kit hakt).
"""
from __future__ import annotations

import logging
import threading
from collections import deque

from config import CONFIG
from frame_buffer import FRAME_BUFFER
from visual_interface import DetectorProtocol, VisionResult

log = logging.getLogger("visual.core")


# ------------------------------------------------------------------ State

_detector: DetectorProtocol | None = None
_active_detector_name: str = "none"  # für /health-Antwort, hilft dem Controller-Team

_tracking_lock = threading.Lock()
_tracking_thread: threading.Thread | None = None
_stop_event: threading.Event | None = None
_current_name: str | None = None

_window_lock = threading.Lock()
_window: deque[VisionResult] = deque(maxlen=CONFIG.window_size)


# ------------------------------------------------------------------ Detector-Wahl

def _try_hailo() -> DetectorProtocol | None:
    """Versucht Hailo zu instanziieren. Gibt None zurück, wenn nicht verfügbar.

    Fängt JEDES Problem ab (Import, fehlende GStreamer-Bindings, kaputte
    Hailo-Treiber, defekte Module). Sprint-Ziel: Auto-Modus muss am Ende
    immer einen Detector liefern, notfalls YOLO.
    """
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
    """Lädt YOLO. Soll funktionieren, wenn ultralytics installiert ist."""
    from yolo_detector import YoloDetector
    return YoloDetector()


def _get_detector() -> DetectorProtocol:
    global _detector, _active_detector_name
    if _detector is not None:
        return _detector

    mode = CONFIG.detector_mode

    if mode == "yolo":
        _detector = _try_yolo()
        _active_detector_name = "yolo"
    elif mode == "hailo":
        # Explizit gewollt: kein Fallback, hart failen.
        d = _try_hailo()
        if d is None:
            raise RuntimeError(
                "detector_mode='hailo' gesetzt, aber Hailo nicht verfügbar. "
                "Entweder Config/Env entfernen (Auto-Fallback) oder Hailo-Stack reparieren."
            )
        _detector = d
        _active_detector_name = "hailo"
    else:
        # Auto-Modus: Hailo probieren, bei jedem Fehler auf YOLO zurückfallen.
        d = _try_hailo()
        if d is not None:
            _detector = d
            _active_detector_name = "hailo"
        else:
            log.info("Auto-Modus: Hailo nicht verfügbar, fallback auf YOLO.")
            _detector = _try_yolo()
            _active_detector_name = "yolo"

    log.info("%s aktiv", type(_detector).__name__)
    return _detector


def set_detector(detector: DetectorProtocol | None) -> None:
    """Erlaubt Tests, einen eigenen Detector zu injizieren (oder zurückzusetzen)."""
    global _detector, _active_detector_name
    _detector = detector
    _active_detector_name = type(detector).__name__.lower() if detector else "none"


def active_detector() -> str:
    """Gibt den Namen des aktiven Detectors zurück ('hailo' | 'yolo' | 'none' | ...)."""
    return _active_detector_name


def prewarm() -> None:
    """Detector initialisieren und Modell vorladen. Vom Server beim Start aufgerufen."""
    detector = _get_detector()
    if hasattr(detector, "prewarm"):
        detector.prewarm()


# ------------------------------------------------------------------ Aggregation

def _on_frame(frame: VisionResult) -> None:
    with _window_lock:
        _window.append(frame)


def _aggregate(name: str) -> dict:
    """Window → Dict. Mittelwerte über Treffer-Frames, sonst found=False.

    `name` wird vom Aufrufer unter _tracking_lock gelesen und hier nur noch
    durchgereicht — so wird _current_name nicht aus zwei verschiedenen Locks
    heraus gelesen.
    """
    with _window_lock:
        snapshot = list(_window)

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
    return {
        "name": name,
        "found": False,
        "confidence": 0.0,
        "x": None, "y": None, "w": None, "h": None,
    }


# ------------------------------------------------------------------ Tracking-API

def start_tracking(name: str) -> dict:
    """Startet den Detector im Hintergrund. Idempotent: laufendes Tracking
    wird vorher gestoppt, falls der Name sich ändert.

    Validation passiert im Server (Pydantic). Hier nur defensives strip().
    """
    global _tracking_thread, _stop_event, _current_name
    name = name.strip()

    with _tracking_lock:
        if _tracking_thread is not None and _tracking_thread.is_alive():
            if _current_name == name:
                return {"status": "running", "name": name}
            _stop_locked()

        with _window_lock:
            _window.clear()

        _current_name = name
        _stop_event = threading.Event()
        # Hinweis: _get_detector() läuft hier unter _tracking_lock. Im
        # Normalbetrieb hat prewarm() den Detector beim Server-Start bereits
        # gebaut, daher ist das billig. Nur falls prewarm fehlschlug, kann die
        # (langsame) Detector-Init hier kurz auch /track/latest und
        # /track/stop blockieren. Die Init bewusst NICHT außerhalb des Locks,
        # sonst könnten zwei parallele start-Aufrufe doppelt initialisieren.
        detector = _get_detector()
        _tracking_thread = threading.Thread(
            target=_run_stream,
            args=(detector, name, _stop_event),
            daemon=True,
        )
        _tracking_thread.start()

    return {"status": "running", "name": name}


def _run_stream(detector: DetectorProtocol, name: str, stop_event: threading.Event) -> None:
    """Worker: ruft detector.stream() bis stop_event gesetzt wird.

    Hinweis: Wenn der Stream *zur Laufzeit* crasht (z.B. Hailo-Pipeline failed
    erst beim Start), gibt es hier KEIN Auto-Fallback auf YOLO. Das ist
    bewusst — ein Wechsel des aktiven Detectors mitten im Tracking wäre
    fehleranfällig. Stattdessen sieht der Controller den nächsten /track/latest
    mit found=False, und kann ggf. /track/stop + /track/start neu auslösen.
    """
    try:
        detector.stream(name, _on_frame, stop_event)
    except Exception as e:
        log.error("Stream-Fehler: %s", e, exc_info=True)
        with _window_lock:
            _window.clear()
        # Stream-Frames für /stream ebenfalls verwerfen — sonst zeigt der
        # MJPEG-Stream nach einem Crash ein eingefrorenes altes Bild.
        FRAME_BUFFER.clear()


def get_latest() -> dict:
    """Aktuelles aggregiertes Window-Ergebnis. status='idle' wenn nichts läuft."""
    with _tracking_lock:
        running = _tracking_thread is not None and _tracking_thread.is_alive()
        name = _current_name or ""

    if not running:
        return {"status": "idle"}

    return {"status": "running", **_aggregate(name)}


def stop_tracking() -> dict:
    """Stoppt den laufenden Detector. Idempotent."""
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
        # Timeout aus Config: GStreamer-Pipeline braucht u.U. etwas zum Aufräumen.
        _tracking_thread.join(timeout=CONFIG.stop_timeout_seconds)
        if _tracking_thread.is_alive():
            # Thread ist nach dem Timeout NICHT durch. Python kann ihn nicht
            # hart killen — wir geben die Referenz trotzdem frei, aber der
            # alte Thread hält evtl. noch Kamera/GStreamer-Pipeline. Ein
            # unmittelbar folgender start_tracking() kann dann auf eine noch
            # belegte Kamera laufen (v.a. Hailo auf dem Pi). Sichtbar machen,
            # statt still zu verschlucken.
            log.warning(
                "Detector-Thread nach %.1fs Timeout noch aktiv — Kamera/Pipeline "
                "evtl. noch belegt. Falls der nächste Start hängt, hier prüfen.",
                CONFIG.stop_timeout_seconds,
            )
    _tracking_thread = None
    _stop_event = None
    _current_name = None
    with _window_lock:
        _window.clear()
    # Frame-Puffer leeren, damit /stream nach dem Stop nicht ein
    # eingefrorenes Bild weiterzeigt. Der Detector macht das in seinem
    # finally-Block auch selbst — hier doppelt, falls join() in den
    # Timeout läuft und der Detector-Thread noch nicht durch ist.
    FRAME_BUFFER.clear()