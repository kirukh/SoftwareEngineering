"""
visual.py — Tracking-API des Visual-Moduls.

Logik-Schicht zwischen HTTP (server.py) und Detector:
    start_tracking(name)   # Detector im Hintergrund starten ODER Ziel live wechseln
    get_latest()           # aktuelles aggregiertes Window-Ergebnis
    stop_tracking()        # Detector sauber beenden
    prewarm()              # Modell vorladen (vom Server beim Start)

Aggregation: Sliding Window über die letzten N Roh-Frames vom Detector.
Größe und Mindesttreffer kommen aus CONFIG (siehe config.py).

Suchziel-Wechsel ist ein LIVE-SWITCH: solange Tracking läuft, tauscht ein
erneuter start_tracking() mit anderem Namen nur das Ziel im TargetHolder aus.
Der Detector-Thread und die Kamera laufen weiter — kein cap.release()/reopen,
kein GStreamer-Pipeline-Rebuild. Erst stop_tracking() fährt alles herunter.

Detector-Wahl per CONFIG.detector_mode (auch via VISUAL_DETECTOR Env-Var).
Auto-Modus: Hailo wird probiert, bei jedem Fehler fällt der Code auf YOLO
zurück (Sprint-Ziel: Rollout muss laufen, auch wenn das Hailo-Kit hakt).
"""
from __future__ import annotations

import threading
from collections import deque

from config import CONFIG
from frame_buffer import FRAME_BUFFER
from visual_interface import DetectorProtocol, TargetHolder, VisionResult


# ------------------------------------------------------------------ State

_detector: DetectorProtocol | None = None
_active_detector_name: str = "none"  # für /health-Antwort, hilft dem Controller-Team
_ready: bool = False  # True, sobald prewarm() durch ist → /health kann 'degraded' melden

_tracking_lock = threading.Lock()
_tracking_thread: threading.Thread | None = None
_stop_event: threading.Event | None = None
# Aktuelles Suchziel. Lebt über die gesamte Tracking-Session und wird beim
# Live-Switch nur umgesetzt (statt Thread neu zu starten). None = kein Tracking.
_target: TargetHolder | None = None

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
        print(f"[visual] Hailo-Module nicht importierbar: {e}")
        return None

    if not _hailo_available:
        return None

    try:
        return HailoDetector()
    except Exception as e:
        print(f"[visual] Hailo-Initialisierung fehlgeschlagen: {e}")
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
            print("[visual] Auto-Modus: Hailo nicht verfügbar, fallback auf YOLO.")
            _detector = _try_yolo()
            _active_detector_name = "yolo"

    print(f"[visual] {type(_detector).__name__} aktiv")
    return _detector


def set_detector(detector: DetectorProtocol | None) -> None:
    """Erlaubt Tests, einen eigenen Detector zu injizieren (oder zurückzusetzen)."""
    global _detector, _active_detector_name, _ready
    _detector = detector
    _active_detector_name = type(detector).__name__.lower() if detector else "none"
    _ready = detector is not None


def active_detector() -> str:
    """Gibt den Namen des aktiven Detectors zurück ('hailo' | 'yolo' | 'none' | ...)."""
    return _active_detector_name


def get_health_status() -> tuple[str, bool]:
    """Für /health: (aktiver Detector, ready).

    ready=True, sobald prewarm() durchgelaufen ist bzw. ein Detector aktiv
    gesetzt wurde. Solange False kann der Server /health als 'degraded' melden
    (Prewarm noch nicht durch oder fehlgeschlagen).
    """
    return _active_detector_name, _ready


def prewarm() -> None:
    """Detector initialisieren und Modell vorladen. Vom Server beim Start aufgerufen."""
    global _ready
    detector = _get_detector()
    if hasattr(detector, "prewarm"):
        detector.prewarm()
    _ready = True


# ------------------------------------------------------------------ Aggregation

def _on_frame(frame: VisionResult) -> None:
    with _window_lock:
        _window.append(frame)


def _aggregate() -> dict:
    """Window → Dict. Mittelwerte über Treffer-Frames, sonst found=False."""
    # _target lokal greifen: stop_tracking() könnte es nebenläufig auf None
    # setzen. Der Name kommt aus dem aktuellen Ziel, nicht aus den Frames —
    # so stimmt er auch direkt nach einem Live-Switch.
    target = _target
    name = target.get() if target is not None else ""

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
    """Startet den Detector im Hintergrund — oder wechselt das Ziel live.

    - Kein Tracking aktiv      → Detector-Thread + Kamera hochfahren.
    - Tracking läuft, gleicher Name → no-op.
    - Tracking läuft, anderer Name  → LIVE-SWITCH: nur das Ziel im TargetHolder
      tauschen. Kamera und Detector laufen weiter, KEIN Neustart.

    Validation passiert im Server (Pydantic). Hier nur defensives strip().
    """
    global _tracking_thread, _stop_event, _target
    name = name.strip()

    with _tracking_lock:
        running = _tracking_thread is not None and _tracking_thread.is_alive()
        if running and _target is not None:
            if _target.get() == name:
                # Gleiches Ziel → Tracking läuft unverändert weiter.
                return {"status": "running", "name": name}

            # Live-Switch: Ziel umsetzen, Window leeren. Kein cap.release()/
            # reopen, kein Pipeline-Rebuild — der Detector liest das neue Ziel
            # ab dem nächsten Frame. Window leeren, damit /track/latest nicht
            # kurz noch das alte Objekt als found meldet (~min_hits Frames bis
            # found wieder true sein kann, Kamera ist ja schon warm).
            _target.set(name)
            with _window_lock:
                _window.clear()
            return {"status": "running", "name": name}

        # Erststart: Detector-Thread + Kamera hochfahren.
        with _window_lock:
            _window.clear()

        _target = TargetHolder(name)
        _stop_event = threading.Event()
        detector = _get_detector()
        _tracking_thread = threading.Thread(
            target=_run_stream,
            args=(detector, _target, _stop_event),
            daemon=True,
        )
        _tracking_thread.start()

    return {"status": "running", "name": name}


def _run_stream(detector: DetectorProtocol, target: TargetHolder, stop_event: threading.Event) -> None:
    """Worker: ruft detector.stream() bis stop_event gesetzt wird.

    Hinweis: Wenn der Stream *zur Laufzeit* crasht (z.B. Hailo-Pipeline failed
    erst beim Start), gibt es hier KEIN Auto-Fallback auf YOLO. Das ist
    bewusst — ein Wechsel des aktiven Detectors mitten im Tracking wäre
    fehleranfällig. Stattdessen sieht der Controller den nächsten /track/latest
    mit found=False, und kann ggf. /track/stop + /track/start neu auslösen.
    """
    try:
        detector.stream(target, _on_frame, stop_event)
    except Exception as e:
        print(f"[visual] Stream-Fehler: {e}")
        with _window_lock:
            _window.clear()
        # Stream-Frames für /stream ebenfalls verwerfen — sonst zeigt der
        # MJPEG-Stream nach einem Crash ein eingefrorenes altes Bild.
        FRAME_BUFFER.clear()


def get_latest() -> dict:
    """Aktuelles aggregiertes Window-Ergebnis. status='idle' wenn nichts läuft."""
    with _tracking_lock:
        running = _tracking_thread is not None and _tracking_thread.is_alive()

    if not running:
        return {"status": "idle"}

    return {"status": "running", **_aggregate()}


def stop_tracking() -> dict:
    """Stoppt den laufenden Detector. Idempotent."""
    with _tracking_lock:
        was_running = _tracking_thread is not None and _tracking_thread.is_alive()
        _stop_locked()
    return {"status": "stopped", "was_running": was_running}


def _stop_locked() -> None:
    """Muss unter _tracking_lock aufgerufen werden."""
    global _tracking_thread, _stop_event, _target
    if _stop_event is not None:
        _stop_event.set()
    if _tracking_thread is not None:
        # Timeout aus Config: GStreamer-Pipeline braucht u.U. etwas zum Aufräumen.
        _tracking_thread.join(timeout=CONFIG.stop_timeout_seconds)
    _tracking_thread = None
    _stop_event = None
    _target = None
    with _window_lock:
        _window.clear()
    # Frame-Puffer leeren, damit /stream nach dem Stop nicht ein
    # eingefrorenes Bild weiterzeigt. Der Detector macht das in seinem
    # finally-Block auch selbst — hier doppelt, falls join() in den
    # Timeout läuft und der Detector-Thread noch nicht durch ist.
    FRAME_BUFFER.clear()