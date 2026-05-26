"""YoloDetector — DetectorProtocol-Implementierung mit YOLOv8 + Webcam.

Zusätzlich zum VisionResult pro Frame schreibt der Detector den jeweils
letzten ANNOTIERTEN Frame (Boxen eingezeichnet, JPEG-kodiert) in den
gemeinsamen FRAME_BUFFER. Der /stream-Endpoint liest von dort.
"""
from __future__ import annotations

import threading
import time

import cv2
from ultralytics import YOLO

from config import CONFIG
from frame_buffer import FRAME_BUFFER
from visual_interface import FrameCallback, VisionResult

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
        object_name: str,
        on_frame: FrameCallback,
        stop_event: threading.Event,
    ) -> None:
        model = self._model_lazy()
        target = object_name.lower()
        names: dict[int, str] = model.names

        cap = cv2.VideoCapture(CONFIG.camera_index)
        if not cap.isOpened():
            raise RuntimeError(f"Kamera {CONFIG.camera_index} konnte nicht geöffnet werden.")

        try:
            while not stop_event.is_set():
                ok, frame = cap.read()
                if not ok:
                    time.sleep(0.02)
                    continue

                results = model.predict(
                    frame, conf=CONFIG.confidence_min, verbose=False, imgsz=640
                )
                result = results[0]
                match = _best_match(result, names, target)

                if match is None:
                    on_frame(VisionResult(object_name, False, 0.0))
                else:
                    conf, x, y, w, h = match
                    on_frame(VisionResult(
                        object_name, True,
                        round(conf, 4),
                        round(x, 4), round(y, 4),
                        round(w, 4), round(h, 4),
                    ))

                # --- Annotierten Frame für den /stream-Endpoint ablegen ---
                # result.plot() rendert ALLE erkannten Objekte mit Box,
                # Label und Confidence in ein BGR-Array. Das zeigt auch
                # andere COCO-Objekte, nicht nur das gesuchte — fürs
                # Debuggen/Demo gewollt. Wenn nur das Zielobjekt gezeigt
                # werden soll, müsste man hier manuell filtern und zeichnen.
                _publish_frame(result)
        finally:
            cap.release()
            # Beim Stop den Puffer leeren, damit der Stream nicht ein
            # eingefrorenes altes Bild weiterzeigt.
            FRAME_BUFFER.clear()


def _publish_frame(result) -> None:
    """Annotierten Frame zu JPEG kodieren und in den FRAME_BUFFER legen."""
    try:
        annotated = result.plot()  # BGR-ndarray mit Boxen/Labels/Confidence
        ok, buf = cv2.imencode(
            ".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), CONFIG.stream_jpeg_quality]
        )
        if ok:
            FRAME_BUFFER.set_frame(buf.tobytes())
    except Exception as e:
        # Ein fehlgeschlagener Frame darf das Tracking nicht abbrechen.
        print(f"[yolo] Frame-Encoding fehlgeschlagen: {e}")


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