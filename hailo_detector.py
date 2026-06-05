"""HailoDetector — DetectorProtocol-Implementierung für Pi 5 + Hailo-8.

Nutzt die hailo-apps-API (GStreamerDetectionApp). Pro Frame:
  1. VisionResult fürs Tracking-Window (on_frame)
  2. annotierter Frame in den FRAME_BUFFER für /stream

Der Frame wird über die hailo-apps-Helper aus dem GStreamer-Buffer gezogen
(get_caps_from_pad + get_numpy_from_buffer) statt über eine zweite Kamera.
"""
from __future__ import annotations

import contextlib
import logging
import signal
import sys
import threading
import time

import cv2

from config import CONFIG
from frame_buffer import FRAME_BUFFER
from visual_interface import FrameCallback, VisionResult

log = logging.getLogger("visual.hailo")

# Modul-Layout unterscheidet sich je nach installiertem Paket — beide probieren:
#   hailo-apps:           hailo_apps.python.*
#   hailo-rpi5-examples:  hailo_apps.hailo_app_python.*
_hailo_available = False
_import_error: Exception | None = None
_active_layout = ""

_CANDIDATE_LAYOUTS = [
    (
        "hailo_apps.python.pipeline_apps.detection.detection_pipeline",
        "hailo_apps.python.core.gstreamer.gstreamer_app",
        "hailo_apps.python.core.common.buffer_utils",
    ),
    (
        "hailo_apps.hailo_app_python.apps.detection.detection_pipeline",
        "hailo_apps.hailo_app_python.core.gstreamer.gstreamer_app",
        "hailo_apps.hailo_app_python.core.common.buffer_utils",
    ),
]

try:
    import importlib

    import gi
    gi.require_version("Gst", "1.0")
    from gi.repository import GLib, Gst
    import hailo

    for _det_mod, _gst_mod, _buf_mod in _CANDIDATE_LAYOUTS:
        try:
            GStreamerDetectionApp = importlib.import_module(_det_mod).GStreamerDetectionApp
            app_callback_class = importlib.import_module(_gst_mod).app_callback_class
            _buf = importlib.import_module(_buf_mod)
            get_caps_from_pad = _buf.get_caps_from_pad
            get_numpy_from_buffer = _buf.get_numpy_from_buffer
            _hailo_available = True
            _active_layout = _det_mod
            break
        except Exception as e:
            _import_error = e
except (ImportError, ValueError) as e:
    _import_error = e

if _hailo_available:
    log.info("Hailo-API geladen (Layout: %s)", _active_layout)
else:
    log.warning("Hailo/GStreamer nicht verfügbar (Fallback auf YOLO): %s", _import_error)


class HailoDetector:
    def __init__(self) -> None:
        if not _hailo_available:
            raise RuntimeError("Hailo-Bibliotheken fehlen. Läuft nur auf dem Pi.")
        self._app = None

    def prewarm(self) -> None:
        pass

    def stream(
        self,
        object_name: str,
        on_frame: FrameCallback,
        stop_event: threading.Event,
    ) -> None:
        target = object_name.strip().lower()

        user_data = app_callback_class()
        user_data.use_frame = True  # ohne use_frame liefert die Pipeline kein CPU-Bild
        callback = _make_callback(target, object_name, on_frame)

        # GStreamerDetectionApp.__init__ registriert einen SIGINT-Handler via
        # signal.signal() — das geht nur im Main-Thread, wir laufen aber im
        # Worker-Thread. _allow_signal_in_thread() neutralisiert das hier.
        # Eingabequelle/HEF kommen über die Kommandozeile (argparse).
        argv_backup = sys.argv[:]
        try:
            with _allow_signal_in_thread():
                sys.argv = _build_argv()
                app = GStreamerDetectionApp(callback, user_data)
        finally:
            sys.argv = argv_backup

        self._app = app
        _make_queues_leaky(app)  # verhindert das Volllaufen der Queues über die Laufzeit
        GLib.timeout_add(200, _make_stop_poller(app, stop_event))

        log.info("Hailo-Pipeline startet. Target='%s', input='%s'", target, CONFIG.hailo_input)
        try:
            app.run()  # blockiert bis loop.quit() (durch den Stop-Poller)
        finally:
            _shutdown(app)
            FRAME_BUFFER.clear()
            log.info("Hailo-Pipeline beendet.")


@contextlib.contextmanager
def _allow_signal_in_thread():
    """signal.signal() im Worker-Thread tolerieren (ValueError schlucken)."""
    orig = signal.signal

    def _safe(signalnum, handler):
        try:
            return orig(signalnum, handler)
        except ValueError:
            return None

    signal.signal = _safe
    try:
        yield
    finally:
        signal.signal = orig


def _build_argv() -> list[str]:
    # --use-frame ist nötig, damit das CPU-Bild bis zum Callback durchgereicht
    # wird (sonst bleibt /stream leer). Flag-Namen ggf. mit `hailo-detect --help`
    # gegenprüfen.
    argv = ["detection.py", "--input", CONFIG.hailo_input, "--use-frame"]
    if CONFIG.hailo_hef_path:
        argv += ["--hef-path", CONFIG.hailo_hef_path]
    return argv


def _make_queues_leaky(app) -> None:
    """Alle queue-Elemente auf leaky=downstream stellen: bei voller Queue den
    ältesten Frame verwerfen statt zu puffern. Hält die Latenz über die
    Laufzeit konstant (Aktualität vor Vollständigkeit)."""
    pipeline = getattr(app, "pipeline", None)
    if pipeline is None:
        return
    try:
        it = pipeline.iterate_recurse()
        count = 0
        while True:
            res, elem = it.next()
            if res != Gst.IteratorResult.OK:
                break
            factory = elem.get_factory()
            if factory and factory.get_name() == "queue":
                try:
                    elem.set_property("leaky", 2)
                    elem.set_property("max-size-buffers", 5)
                    elem.set_property("max-size-time", 0)
                    elem.set_property("max-size-bytes", 0)
                    count += 1
                except Exception as e:
                    log.debug("queue-Property setzen warf: %s", e)
        log.info("%d queue-Elemente auf leaky=downstream gesetzt.", count)
    except Exception as e:
        log.warning("Konnte Queues nicht auf leaky setzen: %s", e)


def _make_stop_poller(app, stop_event: threading.Event):
    def _poll() -> bool:
        if not stop_event.is_set():
            return True
        _shutdown(app)
        return False
    return _poll


def _shutdown(app) -> None:
    """Genau einmal über die framework-eigene shutdown()-Methode runterfahren.
    Ein zusätzliches manuelles set_state(NULL)/loop.quit() würde doppelt
    teardownen und kann segfaulten."""
    if getattr(app, "_visual_shutdown_done", False):
        return
    app._visual_shutdown_done = True

    if hasattr(app, "shutdown"):
        for args in ((), (None, None)):
            try:
                app.shutdown(*args)
                return
            except TypeError:
                continue
            except Exception as e:
                log.debug("app.shutdown%s warf: %s", args, e)
                return
    try:
        pipeline = getattr(app, "pipeline", None)
        if pipeline is not None:
            pipeline.set_state(Gst.State.NULL)
        loop = getattr(app, "loop", None)
        if loop is not None and hasattr(loop, "quit"):
            loop.quit()
    except Exception as e:
        log.debug("Fallback-Shutdown warf: %s", e)


def _make_callback(target: str, original_name: str, on_frame: FrameCallback):
    """hailo-apps ruft den Callback über das identity_callback-Element per
    handoff-Signal auf: Signatur (element, buffer, user_data), buffer ist
    direkt der Gst.Buffer."""

    diag = {"caps_logged": False, "pub_logged": False, "caps_warned": False}
    stream_interval = 1.0 / max(1, CONFIG.stream_fps)
    last_stream = {"ts": 0.0}

    def _callback(element, buffer, user_data):
        if buffer is None:
            return

        try:
            roi = hailo.get_roi_from_buffer(buffer)
            best = None  # (conf, x_center, y_center, w, h), normiert 0..1
            for det in roi.get_objects_typed(hailo.HAILO_DETECTION):
                if (det.get_label() or "").strip().lower() != target:
                    continue
                conf = float(det.get_confidence())
                if conf < CONFIG.confidence_min:
                    continue
                if best is None or conf > best[0]:
                    bbox = det.get_bbox()
                    w, h = bbox.width(), bbox.height()
                    best = (conf, bbox.xmin() + w / 2.0, bbox.ymin() + h / 2.0, w, h)

            if best is not None:
                conf, x_c, y_c, w, h = best
                on_frame(VisionResult(
                    original_name, True,
                    round(conf, 4), round(x_c, 4), round(y_c, 4), round(w, 4), round(h, 4),
                ))
            else:
                on_frame(VisionResult(original_name, False, 0.0))
        except Exception as e:
            best = None
            log.warning("Detektion fehlgeschlagen (ignoriert): %s", e)

        # Teures Frame-Abgreifen auf stream_fps drosseln (Detektion oben läuft
        # bei jedem Frame). Verhindert Pipeline-Rückstau.
        if getattr(user_data, "use_frame", False) and (
            time.monotonic() - last_stream["ts"] >= stream_interval
        ):
            last_stream["ts"] = time.monotonic()
            try:
                pad = element.get_static_pad("sink") or element.get_static_pad("src")
                fmt, width, height = get_caps_from_pad(pad)

                if not diag["caps_logged"]:
                    log.info("Stream-Caps: format=%r %sx%s", fmt, width, height)
                    diag["caps_logged"] = True

                if fmt is not None and width and height:
                    frame = cv2.cvtColor(
                        get_numpy_from_buffer(buffer, fmt, width, height), cv2.COLOR_RGB2BGR
                    )
                    if best is not None:
                        conf, x_c, y_c, w, h = best
                        x1, y1 = int((x_c - w / 2) * width), int((y_c - h / 2) * height)
                        x2, y2 = int((x_c + w / 2) * width), int((y_c + h / 2) * height)
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.putText(frame, f"{original_name} {conf:.2f}", (x1, max(0, y1 - 10)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    FRAME_BUFFER.set_frame(frame)
                    if not diag["pub_logged"]:
                        log.info("Erster Stream-Frame veröffentlicht (%dx%d).", width, height)
                        diag["pub_logged"] = True
                elif not diag["caps_warned"]:
                    log.warning("Keine Video-Caps am identity-Pad (format=%r) — /stream bleibt leer.", fmt)
                    diag["caps_warned"] = True
            except Exception as e:
                if not diag["caps_warned"]:
                    log.warning("Frame-Abgriff fehlgeschlagen (einmalig geloggt): %s", e)
                    diag["caps_warned"] = True

        return  # handoff-Rückgabewert wird ignoriert

    return _callback
