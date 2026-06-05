"""YoloDetector — DetectorProtocol-Implementierung mit YOLOv8 + Webcam.

Fallback bzw. lokales Testen ohne Pi. Pro Frame: VisionResult fürs Tracking
und der annotierte Frame (rohes BGR-Array) in den FRAME_BUFFER für /stream.
"""
from __future__ import annotations

import logging
import threading
import time

import cv2
from ultralytics import YOLO

from config import CONFIG
from frame_buffer import FRAME_BUFFER
from visual_interface import FrameCallback, VisionResult

log = logging.getLogger("visual.yolo")


class YoloDetector:
    def __init__(self) -> None:
        self._model: YOLO | None = None

    def _model_lazy(self) -> YOLO:
        if self._model is None:
            self._model = YOLO(CONFIG.model_path)
        return self._model

    def prewarm(self) -> None:
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
            raise RuntimeError(f"Kamera (Index {CONFIG.camera_index}) konnte nicht geöffnet werden.")

        log.info("YOLO-Webcam-Stream gestartet. Target='%s'", target)
        try:
            while not stop_event.is_set():
                ret, frame = cap.read()
                if not ret:
                    log.warning("Kein Frame von der Webcam.")
                    time.sleep(0.01)
                    continue

                results = model.predict(frame, verbose=False)
                if not results:
                    continue
                result = results[0]

                match = _best_match(result, names, target)
                if match is not None:
                    conf, x, y, w, h = match
                    on_frame(VisionResult(object_name, True, conf, x, y, w, h))
                else:
                    on_frame(VisionResult(object_name, False, 0.0))

                _publish_frame(result)
        finally:
            cap.release()
            FRAME_BUFFER.clear()


def _publish_frame(result) -> None:
    try:
        annotated = result.plot()  # BGR mit Boxen/Labels/Confidence
        if annotated is not None:
            FRAME_BUFFER.set_frame(annotated.copy())
    except Exception as e:
        log.warning("Frame-Übergabe an den Puffer fehlgeschlagen: %s", e)


def _best_match(result, names: dict, target: str):
    """Beste passende Box als (conf, x, y, w, h) normiert auf 0..1, oder None."""
    if result.boxes is None or len(result.boxes) == 0:
        return None

    best = None
    for box in result.boxes:
        if names.get(int(box.cls[0]), "").lower() != target:
            continue
        conf = float(box.conf[0])
        if best is None or conf > best[0]:
            x_c, y_c, w, h = box.xywhn[0].tolist()  # bereits normiert 0..1
            best = (round(conf, 4), round(x_c, 4), round(y_c, 4), round(w, 4), round(h, 4))
    return best
