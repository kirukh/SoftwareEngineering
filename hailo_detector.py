"""HailoDetector — DetectorProtocol-Implementierung für Pi 5 + Hailo-8.

Zusätzlich zum VisionResult pro Frame versucht der Detector, den jeweils
letzten ANNOTIERTEN Frame in den gemeinsamen FRAME_BUFFER zu schreiben,
damit der /stream-Endpoint ein Live-Bild mit Boxen liefern kann.

  ⚠️  ACHTUNG — UNGETESTET AM ECHTEN PI (Sprint-Task T-20 noch offen).
      Der Frame-Abgriff aus der GStreamer-Pipeline unten ist ein fundierter
      Entwurf, KEIN verifiziertes Feature. Die mit  # TODO(T-20)  markierten
      Stellen müssen am Gerät geprüft werden. Solange das nicht passiert
      ist: für die Demo den YOLO-Fallback nutzen, der läuft sicher.
"""
from __future__ import annotations

import threading

from config import CONFIG
from frame_buffer import FRAME_BUFFER
from visual_interface import FrameCallback, VisionResult

# Hailo-Stack ist nur auf dem Pi installiert — Imports dürfen auf dem Laptop fehlschlagen.
_hailo_available = False
try:
    import gi
    gi.require_version("Gst", "1.0")
    from gi.repository import Gst
    import hailo
    from hailo_apps.hailo_app_python.apps.detection_simple.detection_pipeline_simple import (
        GStreamerDetectionApp,
    )
    from hailo_apps.hailo_app_python.core.gstreamer.gstreamer_app import app_callback_class
    _hailo_available = True
except ImportError:
    pass

# numpy für die Frame-Konvertierung. Auf dem Pi via Hailo-Stack vorhanden,
# auf dem Laptop via ultralytics/opencv. Import defensiv halten.
try:
    import numpy as np
    import cv2
    _frame_libs_available = True
except ImportError:
    _frame_libs_available = False

# Hinweis: Der Controller liefert immer bereits korrekte COCO-Labels
# (Mapping passiert im Audio-Team). Daher kein Aliasing hier nötig.


class HailoDetector:
    def prewarm(self) -> None:
        """Hailo lädt erst beim Pipeline-Start — nichts vorzuladen."""
        pass

    def stream(
        self,
        object_name: str,
        on_frame: FrameCallback,
        stop_event: threading.Event,
    ) -> None:
        if not _hailo_available:
            raise RuntimeError("Hailo-Bibliotheken nicht verfügbar. Auf dem Pi ausführen.")

        target = object_name.strip().lower()

        class _UserData(app_callback_class):
            pass

        app = GStreamerDetectionApp(
            _make_callback(target, object_name, on_frame, stop_event),
            _UserData(),
        )

        # GStreamer-Mainloop blockiert — in eigenen Thread auslagern,
        # damit wir hier auf stop_event reagieren können.
        runner = threading.Thread(target=app.run, daemon=True)
        runner.start()

        # Frame-Abgriff für /stream einhängen, sobald die Pipeline steht.
        # Bewusst NACH app.run()-Start, weil app.pipeline erst dann existiert.
        _attach_frame_tap(app, stop_event)

        stop_event.wait()

        # Pipeline-Shutdown — mehrere Pfade versuchen, je nach Hailo-Version.
        _shutdown_pipeline(app)

        # Auf das saubere Ende warten, damit die Kamera/Pipeline frei wird.
        runner.join(timeout=3.0)

        # Puffer leeren, damit der Stream kein eingefrorenes Bild zeigt.
        FRAME_BUFFER.clear()


def _attach_frame_tap(app, stop_event: threading.Event) -> None:
    """Hängt eine Pad-Probe hinter dem Overlay-Element ein, um den
    annotierten Frame (mit eingezeichneten Boxen) abzugreifen.

    ⚠️  TODO(T-20): Dieser ganze Block ist ungetestet. Beim Pi-Live-Test
    zu verifizieren:
      - Heißt das Overlay-Element wirklich 'hailo_overlay'?  Pipeline mit
        `GST_DEBUG_DUMP_DOT_DIR` dumpen und die Element-Namen prüfen.
      - Liefert der Buffer RGB oder NV12/YUV?  Davon hängt die
        cv2-Konvertierung unten ab.
      - Caps (Breite/Höhe) sauslesen statt zu raten.
    Wenn der Tap nicht klappt, läuft das TRACKING trotzdem weiter —
    nur der /stream bleibt dann leer. Das ist Absicht: der Stream ist
    ein Zusatzfeature, kein Grund das Kern-Tracking zu riskieren.
    """
    if not _frame_libs_available:
        print("[hailo] numpy/cv2 fehlen — Frame-Tap für /stream deaktiviert.")
        return

    # Kurz warten, bis die Pipeline aufgebaut ist.
    pipeline = getattr(app, "pipeline", None)
    if pipeline is None:
        print("[hailo] app.pipeline nicht vorhanden — Frame-Tap übersprungen.")
        return

    # TODO(T-20): Element-Name am echten Pi verifizieren.
    overlay = pipeline.get_by_name("hailo_overlay")
    if overlay is None:
        print("[hailo] Overlay-Element nicht gefunden — /stream bleibt leer. "
              "Element-Namen am Pi prüfen (siehe TODO im Code).")
        return

    src_pad = overlay.get_static_pad("src")
    if src_pad is None:
        print("[hailo] Overlay-src-Pad nicht gefunden — /stream bleibt leer.")
        return

    src_pad.add_probe(Gst.PadProbeType.BUFFER, _frame_probe, None)
    print("[hailo] Frame-Tap für /stream eingehängt (hinter hailo_overlay).")


def _frame_probe(pad, info, user_data):
    """Pad-Probe: zieht den annotierten Videoframe aus dem GStreamer-Buffer.

    ⚠️  TODO(T-20): Konvertierung ungetestet — Format am Pi prüfen.
    """
    try:
        buffer = info.get_buffer()
        if buffer is None:
            return Gst.PadProbeReturn.OK

        caps = pad.get_current_caps()
        if caps is None:
            return Gst.PadProbeReturn.OK

        structure = caps.get_structure(0)
        ok_w, width = structure.get_int("width")
        ok_h, height = structure.get_int("height")
        if not (ok_w and ok_h):
            return Gst.PadProbeReturn.OK

        success, map_info = buffer.map(Gst.MapFlags.READ)
        if not success:
            return Gst.PadProbeReturn.OK
        try:
            # TODO(T-20): Annahme RGB (3 Kanäle). Falls die Pipeline
            # NV12/YUV liefert, hier cv2.cvtColor mit passendem Code
            # einsetzen. Format aus structure.get_string("format") lesen.
            frame = np.frombuffer(map_info.data, dtype=np.uint8)
            frame = frame.reshape((height, width, 3))
            bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            ok, jpeg = cv2.imencode(
                ".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), CONFIG.stream_jpeg_quality]
            )
            if ok:
                FRAME_BUFFER.set_frame(jpeg.tobytes())
        finally:
            buffer.unmap(map_info)
    except Exception as e:
        # Ein kaputter Frame darf die Pipeline nicht stören.
        print(f"[hailo] Frame-Probe-Fehler (ignoriert): {e}")

    return Gst.PadProbeReturn.OK


def _shutdown_pipeline(app) -> None:
    """Pipeline runterfahren — robust gegen API-Unterschiede zwischen Hailo-Versionen.

    Wir kennen die exakte API nicht (Pi-Live-Test steht noch aus), daher
    werden ALLE bekannten Pfade durchlaufen, nicht nur der erste der greift.
    Das ist redundant, aber ein doppeltes set_state(NULL) ist gefahrlos —
    ein hängender GLib.MainLoop nicht.

      1) app.shutdown()                          — Hailo-eigene Methode
      2) app.pipeline.set_state(Gst.State.NULL)  — Standard-GStreamer
      3) app.loop.quit()                         — GLib-MainLoop killen
    """
    # 1) Hailo-eigene Methode
    if hasattr(app, "shutdown"):
        try:
            app.shutdown()
        except Exception as e:
            print(f"[hailo] app.shutdown() warf Fehler: {e}")

    # 2) GStreamer-Pipeline auf NULL setzen
    try:
        pipeline = getattr(app, "pipeline", None)
        if pipeline is not None:
            pipeline.set_state(Gst.State.NULL)
    except Exception as e:
        print(f"[hailo] pipeline.set_state(NULL) warf Fehler: {e}")

    # 3) GLib.MainLoop quitten (nötig, sonst hängt der Runner-Thread)
    try:
        loop = getattr(app, "loop", None)
        if loop is not None and hasattr(loop, "quit"):
            loop.quit()
    except Exception as e:
        print(f"[hailo] loop.quit() warf Fehler: {e}")


def _make_callback(
    target: str,
    original_name: str,
    on_frame: FrameCallback,
    stop_event: threading.Event,
):
    """Wird pro Frame aus der GStreamer-Pipeline aufgerufen."""
    def _callback(pad, info, user_data):
        if stop_event.is_set():
            return Gst.PadProbeReturn.OK

        buffer = info.get_buffer()
        if buffer is None:
            return Gst.PadProbeReturn.OK

        roi = hailo.get_roi_from_buffer(buffer)
        best_conf, best_x, best_y, best_w, best_h = 0.0, 0.0, 0.0, 0.0, 0.0

        for det in roi.get_objects_typed(hailo.HAILO_DETECTION):
            label = (det.get_label() or "").strip().lower()
            if label != target:
                continue
            conf = float(det.get_confidence())
            if conf >= CONFIG.confidence_min and conf > best_conf:
                bbox = det.get_bbox()
                best_conf = conf
                best_x, best_y = bbox.x_center(), bbox.y_center()
                best_w, best_h = bbox.width(), bbox.height()

        if best_conf > 0:
            on_frame(VisionResult(
                original_name, True,
                round(best_conf, 4),
                round(best_x, 4), round(best_y, 4),
                round(best_w, 4), round(best_h, 4),
            ))
        else:
            on_frame(VisionResult(original_name, False, 0.0))

        return Gst.PadProbeReturn.OK

    return _callback