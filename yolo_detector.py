"""YoloDetector — DetectorProtocol-Implementierung mit YOLOv8 + Webcam.

Zusätzlich zum VisionResult pro Frame schreibt der Detector den jeweils
letzten ANNOTIERTEN Frame (Boxen eingezeichnet, roher BGR-ndarray) in den
gemeinsamen FRAME_BUFFER. Der /stream-Endpoint (server.py) kodiert/skaliert
selbst und liest nur von dort.

Erkennung läuft auf ALLE COCO-Objekte; im Stream bekommen alle erkannten
Objekte eine Box, das gesuchte Ziel zusätzlich eine eigene Highlight-Farbe.
Zurückgegeben (an /track/latest) wird weiterhin nur das gesuchte Ziel.

Das Suchziel kommt als TargetHolder und wird pro Frame neu gelesen — so kann
das Audio-/Controller-Team das Ziel zur Laufzeit wechseln (erneuter
/track/start mit anderem Label), ohne dass die Kamera neu geöffnet wird.
"""
from __future__ import annotations

import threading
import time

import cv2
from ultralytics import YOLO
from ultralytics.utils.plotting import Annotator, colors

from config import CONFIG
from frame_buffer import FRAME_BUFFER
from visual_interface import FrameCallback, TargetHolder, VisionResult

# Highlight-Farbe (BGR) für das gesuchte Objekt im Stream. Magenta, weil es in
# der ultralytics-Klassenpalette praktisch nicht vorkommt und damit eindeutig
# als "das ist das gesuchte Objekt" lesbar bleibt.
_TARGET_COLOR = (255, 0, 255)

# Hinweis: Der Controller liefert immer bereits korrekte COCO-Labels
# (Mapping passiert im Audio-Team). Daher kein Aliasing hier nötig.


class YoloDetector:
    def __init__(self) -> None:
        self._model: YOLO | None = None

    def _model_lazy(self) -> YOLO:
        if self._model is None:
            self._model = YOLO(CONFIG.model_path)
        return self._model

    def prewarm(self) -> None:
        """Modell vorladen — vom Server beim Start aufgerufen."""
        self._model_lazy()

    def stream(
        self,
        target: TargetHolder,
        on_frame: FrameCallback,
        stop_event: threading.Event,
    ) -> None:
        model = self._model_lazy()
        names: dict[int, str] = model.names

        cap = cv2.VideoCapture(CONFIG.camera_index)
        if not cap.isOpened():
            raise RuntimeError(f"Kamera {CONFIG.camera_index} konnte nicht geöffnet werden.")

        try:
            while not stop_event.is_set():
                # Ziel pro Frame frisch lesen — erlaubt Live-Switch ohne Neustart.
                current = target.get().lower()

                ok, frame = cap.read()
                if not ok:
                    time.sleep(0.02)
                    continue

                results = model.predict(
                    frame, conf=CONFIG.confidence_min, verbose=False, imgsz=640
                )
                result = results[0]
                match = _best_match(result, names, current)

                if match is None:
                    on_frame(VisionResult(current, False, 0.0))
                else:
                    conf, x, y, w, h = match
                    on_frame(VisionResult(
                        current, True,
                        round(conf, 4),
                        round(x, 4), round(y, 4),
                        round(w, 4), round(h, 4),
                    ))

                # Annotierten Frame für /stream ablegen: alle erkannten Objekte
                # mit Box, das gesuchte Ziel in Highlight-Farbe.
                _publish_frame(result, names, current)
        finally:
            cap.release()
            # Beim Stop den Puffer leeren, damit der Stream nicht ein
            # eingefrorenes altes Bild weiterzeigt.
            FRAME_BUFFER.clear()


def _publish_frame(result, names: dict, target: str) -> None:
    """Annotierten BGR-Frame (ndarray) in den FRAME_BUFFER legen.

    Contract: server.py erwartet im Puffer ROHE Frames (numpy-ndarray) und
    kodiert/skaliert selbst beim Ausliefern (_encode_jpeg). Hier daher NICHT
    mehr zu JPEG kodieren — sonst kommt im Stream-Generator 'bytes' statt
    ndarray an ('bytes' object has no attribute 'shape').
    """
    try:
        annotated = _draw_boxes(result, names, target)  # BGR ndarray
        FRAME_BUFFER.set_frame(annotated)
    except Exception as e:
        # Ein fehlgeschlagener Frame darf das Tracking nicht abbrechen.
        print(f"[yolo] Frame-Annotation fehlgeschlagen: {e}")


def _draw_boxes(result, names: dict, target: str):
    """Zeichnet ALLE Detections auf eine Kopie des Originalbilds.

    Gesuchtes Ziel → Highlight-Farbe (_TARGET_COLOR), alle anderen → ihre
    Klassenfarbe aus der ultralytics-Palette. Gibt ein BGR-ndarray zurück.
    """
    annotator = Annotator(result.orig_img.copy(), line_width=2)

    if result.boxes is not None:
        for box in result.boxes:
            cls_idx = int(box.cls[0])
            label_name = names.get(cls_idx, str(cls_idx))
            conf = float(box.conf[0])
            xyxy = box.xyxy[0].tolist()

            is_target = label_name.lower() == target
            color = _TARGET_COLOR if is_target else colors(cls_idx, bgr=True)
            label = f"{label_name} {conf:.2f}"
            annotator.box_label(xyxy, label, color=color)

    return annotator.result()


def _best_match(result, names: dict, target: str):
    """Beste passende Box als (conf, x, y, w, h) normiert auf 0..1, oder None."""
    if result.boxes is None or len(result.boxes) == 0:
        return None

    img_h, img_w = result.orig_shape
    best = None

    for box in result.boxes:
        label = names.get(int(box.cls[0]), "").lower()
        if label != target:
            continue
        conf = float(box.conf[0])
        if best is None or conf > best[0]:
            x_px, y_px, w_px, h_px = box.xywh[0].tolist()
            best = (conf, x_px / img_w, y_px / img_h, w_px / img_w, h_px / img_h)

    return best