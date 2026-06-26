"""HailoDetector — DetectorProtocol-Implementierung für Pi 5 + Hailo.

Erkennung läuft über die Hailo-Detection-Pipeline auf ALLE Objekte; gefiltert
(für /track/latest) und gezeichnet (für /stream) wird im Callback. Das gesuchte
Ziel bekommt im Stream eine eigene Highlight-Farbe, alle anderen Erkennungen
eine neutrale Farbe.

Das Suchziel kommt als TargetHolder und wird pro Frame im Callback neu gelesen
(target.get()). Ein Ziel-Wechsel zur Laufzeit ändert nur diese Variable — die
GStreamer-Pipeline läuft unverändert weiter, KEIN Rebuild nötig. Geteardownt
wird nur bei echtem stop_tracking(), Server-Shutdown oder Stream-Fehler.

  ⚠️  Teardown-Hinweis (war ein realer Bug): Die GStreamer-MainLoop (app.run())
      muss zuverlässig zum Zurückkehren gebracht werden, sonst leakt der
      Runner-Thread und hält Kamera + Hailo-Device — mehrere konkurrierende
      "Hailo Detection App"-Pipelines sind die Folge. _shutdown_pipeline() ist
      darauf ausgelegt (EOS + shutdown-Guard + loop.quit + NULL); zusätzlich
      verhindert eine Single-Pipeline-Invariante, dass je zwei nebeneinander
      laufen. Schlägt ein Teardown doch fehl, failt der nächste Start LAUT
      statt still eine zweite Pipeline danebenzustellen.

  ⚠️  Der Frame-Abgriff für /stream ist am echten Pi weiterhin ungetestet
      (T-20/T-30). Die mit  # TODO(T-30)  markierten Stellen am Gerät prüfen.
"""
from __future__ import annotations

import threading
import time

from config import CONFIG
from frame_buffer import FRAME_BUFFER
from visual_interface import FrameCallback, TargetHolder, VisionResult

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

# numpy/cv2 für die Frame-Konvertierung. Auf dem Pi via Hailo-Stack vorhanden,
# auf dem Laptop via ultralytics/opencv. Import defensiv halten.
try:
    import numpy as np
    import cv2
    _frame_libs_available = True
except ImportError:
    _frame_libs_available = False

# Box-Farben für /stream (BGR). Ziel auffällig, Rest neutral.
_TARGET_COLOR = (255, 0, 255)  # Magenta — gesuchtes Objekt
_OTHER_COLOR = (0, 255, 0)     # Grün — alle anderen Erkennungen

# Drosselung der /stream-Frame-Erzeugung. Der Callback läuft pro Pipeline-Frame;
# JPEG-Encoding bei jedem Frame würde die Pipeline unnötig belasten.
_last_publish = 0.0

# --- Single-Pipeline-Invariante --------------------------------------------
# Es darf NIE mehr als eine Hailo-Pipeline gleichzeitig auf der Kamera laufen.
# Wird ein vorheriger Teardown nicht abgeschlossen (Runner-Thread lebt noch),
# bleibt _pipeline_alive True und der nächste Start failt LAUT, statt still
# eine zweite, konkurrierende Pipeline zu starten (genau das Pile-up, das das
# Team beobachtet hat).
_pipeline_lock = threading.Lock()
_pipeline_alive = False

# Hinweis: Der Controller liefert immer bereits korrekte COCO-Labels
# (Mapping passiert im Audio-Team). Daher kein Aliasing hier nötig.


class HailoDetector:
    def prewarm(self) -> None:
        """Hailo lädt erst beim Pipeline-Start — nichts vorzuladen."""
        pass

    def stream(
        self,
        target: TargetHolder,
        on_frame: FrameCallback,
        stop_event: threading.Event,
    ) -> None:
        global _pipeline_alive

        if not _hailo_available:
            raise RuntimeError("Hailo-Bibliotheken nicht verfügbar. Auf dem Pi ausführen.")

        # Single-Pipeline-Invariante prüfen, BEVOR eine neue Pipeline gebaut wird.
        with _pipeline_lock:
            if _pipeline_alive:
                raise RuntimeError(
                    "Es läuft bereits eine Hailo-Pipeline (vorheriger Teardown nicht "
                    "abgeschlossen). Kamera/Hailo-Device evtl. noch belegt. Server-Logs "
                    "prüfen und den hängenden Prozess beenden — siehe "
                    "'fuser -v /dev/video0 /dev/hailo0'. Kein zweiter Start, um ein "
                    "Pile-up konkurrierender Pipelines zu vermeiden."
                )
            _pipeline_alive = True

        app = None
        runner = None
        try:
            class _UserData(app_callback_class):
                pass

            app = GStreamerDetectionApp(
                _make_callback(target, on_frame, stop_event),
                _UserData(),
            )

            # GStreamer-Mainloop blockiert — in eigenen Thread auslagern,
            # damit wir hier auf stop_event reagieren können.
            runner = threading.Thread(target=app.run, daemon=True, name="hailo-gst-mainloop")
            runner.start()

            stop_event.wait()
        finally:
            # Pipeline runterfahren — robust gegen API-Unterschiede zwischen Versionen.
            if app is not None:
                _shutdown_pipeline(app)

            # Auf das saubere Ende warten und VERIFIZIEREN, dass der Mainloop wirklich
            # zurückgekehrt ist. Tut er das nicht, leakt der Thread und hält die
            # Kamera — dann _pipeline_alive bewusst auf True lassen, damit der
            # nächste Start laut failt statt still eine Konkurrenz-Pipeline zu starten.
            leaked = False
            if runner is not None:
                runner.join(timeout=CONFIG.stop_timeout_seconds)
                leaked = runner.is_alive()

            if leaked:
                print(
                    "[hailo] KRITISCH: GStreamer-Mainloop nach Teardown noch aktiv. "
                    "Kamera/Hailo-Device bleibt belegt. Prozess prüfen und beenden: "
                    "'fuser -v /dev/video0 /dev/hailo0'. Nächster Hailo-Start wird "
                    "abgelehnt, bis das aufgeräumt ist."
                )
            else:
                with _pipeline_lock:
                    _pipeline_alive = False

            FRAME_BUFFER.clear()


def _make_callback(
    target: TargetHolder,
    on_frame: FrameCallback,
    stop_event: threading.Event,
):
    """Wird pro Frame aus der GStreamer-Pipeline aufgerufen.

    Zwei Aufgaben in einem Durchlauf über die Detections:
      1) Tracking: bestes Ziel-Match → VisionResult an on_frame().
      2) /stream: alle Detections auf das Frame zeichnen, Ziel hervorgehoben.
    """
    def _callback(pad, info, user_data):
        if stop_event.is_set():
            return Gst.PadProbeReturn.OK

        buffer = info.get_buffer()
        if buffer is None:
            return Gst.PadProbeReturn.OK

        # Ziel pro Frame frisch lesen → Live-Switch ohne Pipeline-Rebuild.
        current = (target.get() or "").strip().lower()

        roi = hailo.get_roi_from_buffer(buffer)
        detections = roi.get_objects_typed(hailo.HAILO_DETECTION)

        # --- 1) Tracking: bestes Ziel-Match ---
        best_conf, best_x, best_y, best_w, best_h = 0.0, 0.0, 0.0, 0.0, 0.0
        for det in detections:
            label = (det.get_label() or "").strip().lower()
            if label != current:
                continue
            conf = float(det.get_confidence())
            if conf >= CONFIG.confidence_min and conf > best_conf:
                bbox = det.get_bbox()
                best_conf = conf
                best_x, best_y = bbox.x_center(), bbox.y_center()
                best_w, best_h = bbox.width(), bbox.height()

        if best_conf > 0:
            on_frame(VisionResult(
                current, True,
                round(best_conf, 4),
                round(best_x, 4), round(best_y, 4),
                round(best_w, 4), round(best_h, 4),
            ))
        else:
            on_frame(VisionResult(current, False, 0.0))

        # --- 2) /stream: annotierten Frame ablegen (gedrosselt) ---
        _publish_annotated_frame(pad, buffer, detections, current)

        return Gst.PadProbeReturn.OK

    return _callback


def _publish_annotated_frame(pad, buffer, detections, target: str) -> None:
    """Zieht den Frame aus dem Buffer, zeichnet alle Detections selbst (Ziel in
    Highlight-Farbe) und legt den rohen BGR-Frame (ndarray) in den FRAME_BUFFER.
    Kodiert/skaliert wird im Server (_encode_jpeg), nicht hier.

    ⚠️  TODO(T-30): Komplett ungetestet am Pi. Zu verifizieren:
      - Führt der Callback-Pad überhaupt das Video-Frame? (sonst Tap auf einen
        Pad VOR dem Overlay legen.)
      - Pixelformat: hier RGB angenommen. Bei NV12/YUV cv2.cvtColor mit
        passendem Code; Format aus structure.get_string("format") lesen.
      - Sitzt der Pad VOR dem hailo_overlay? Sonst sind die Overlay-Boxen schon
        eingebrannt → Doppel-Zeichnen.
    """
    global _last_publish
    if not _frame_libs_available:
        return

    # Drosseln auf stream_fps.
    now = time.monotonic()
    if now - _last_publish < 1.0 / CONFIG.stream_fps:
        return
    _last_publish = now

    try:
        caps = pad.get_current_caps()
        if caps is None:
            return
        structure = caps.get_structure(0)
        ok_w, width = structure.get_int("width")
        ok_h, height = structure.get_int("height")
        if not (ok_w and ok_h):
            return

        success, map_info = buffer.map(Gst.MapFlags.READ)
        if not success:
            return
        try:
            # TODO(T-30): Annahme RGB (3 Kanäle). .copy(), weil der gemappte
            # Buffer read-only ist und wir gleich darauf zeichnen.
            frame = np.frombuffer(map_info.data, dtype=np.uint8)
            frame = frame.reshape((height, width, 3)).copy()
        finally:
            buffer.unmap(map_info)

        # Erst nach BGR, dann zeichnen — so stimmen die BGR-Farbkonstanten im
        # finalen JPEG. (TODO(T-30): Falls Quelle nicht RGB, Code anpassen.)
        bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        for det in detections:
            label = (det.get_label() or "")
            conf = float(det.get_confidence())
            bbox = det.get_bbox()
            cx, cy, bw, bh = bbox.x_center(), bbox.y_center(), bbox.width(), bbox.height()
            x1 = int((cx - bw / 2) * width)
            y1 = int((cy - bh / 2) * height)
            x2 = int((cx + bw / 2) * width)
            y2 = int((cy + bh / 2) * height)

            is_target = label.strip().lower() == target
            color = _TARGET_COLOR if is_target else _OTHER_COLOR
            thickness = 3 if is_target else 1
            cv2.rectangle(bgr, (x1, y1), (x2, y2), color, thickness)
            cv2.putText(
                bgr, f"{label} {conf:.2f}", (x1, max(0, y1 - 5)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA,
            )

        # Contract: server.py kodiert/skaliert selbst (_encode_jpeg) — hier den
        # ROHEN BGR-Frame (ndarray) ablegen, nicht JPEG-Bytes.
        FRAME_BUFFER.set_frame(bgr)
    except Exception as e:
        # Ein kaputter Frame darf die Pipeline nicht stören.
        print(f"[hailo] Frame-Annotation fehlgeschlagen (ignoriert): {e}")


def _shutdown_pipeline(app) -> None:
    """Pipeline runterfahren — so, dass app.run() (GLib-MainLoop) zuverlässig
    zurückkehrt. Reihenfolge bewusst:

      0) Guard: genau EINMAL ausführen. Ein doppeltes app.shutdown() kann je
         nach Hailo-Version segfaulten.
      1) EOS in die Pipeline schicken — der Bus-Watch der App quittet daraufhin
         i.d.R. die MainLoop sauber, sodass app.run() zurückkehrt.
      2) app.shutdown() — Hailo-eigener, dokumentierter Pfad.
      3) GLib-MainLoop explizit quitten (mehrere mögliche Attributnamen) — als
         Backstop, falls 1)+2) die Loop nicht beenden.
      4) pipeline.set_state(NULL) — gibt Kamera + Hailo-Device frei.

    ⚠️  TODO(T-30): Loop-Attributname und app.shutdown()-Existenz am echten Pi
        verifizieren. Wenn der Runner-Thread nach dem Join noch lebt (siehe
        stream()), greift Schritt 3 nicht — dann Attributnamen hier anpassen.
    """
    # 0) Doppel-Teardown verhindern.
    if getattr(app, "_visual_shutdown_done", False):
        return
    try:
        setattr(app, "_visual_shutdown_done", True)
    except Exception:
        pass

    pipeline = getattr(app, "pipeline", None)

    # 1) EOS — sauberster Weg, die MainLoop zum Quitten zu bringen.
    try:
        if pipeline is not None:
            pipeline.send_event(Gst.Event.new_eos())
    except Exception as e:
        print(f"[hailo] EOS senden warf Fehler: {e}")

    # 2) Hailo-eigene shutdown()-Methode.
    if hasattr(app, "shutdown"):
        try:
            app.shutdown()
        except Exception as e:
            print(f"[hailo] app.shutdown() warf Fehler: {e}")

    # 3) GLib-MainLoop explizit quitten — Backstop. Attributname ist je nach
    #    Hailo-Version unterschiedlich, daher mehrere durchprobieren.
    for attr in ("loop", "main_loop", "mainloop", "_loop"):
        loop = getattr(app, attr, None)
        if loop is not None and hasattr(loop, "quit"):
            try:
                loop.quit()
            except Exception as e:
                print(f"[hailo] {attr}.quit() warf Fehler: {e}")
            break

    # 4) Pipeline auf NULL — gibt Kamera/Hailo-Device frei.
    try:
        if pipeline is not None:
            pipeline.set_state(Gst.State.NULL)
    except Exception as e:
        print(f"[hailo] pipeline.set_state(NULL) warf Fehler: {e}")