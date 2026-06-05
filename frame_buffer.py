"""Thread-sicherer Puffer für genau einen rohen Video-Frame.

Kamera und Detector greifen exklusiv auf die Hardware zu, deshalb öffnet der
/stream-Endpoint keine eigene Kamera: der laufende Detector legt hier seinen
letzten Frame ab, der HTTP-Endpoint liest ihn nur. Es wird immer nur der
neueste Frame gehalten.
"""
from __future__ import annotations

import threading

import numpy as np


class FrameBuffer:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._frame: np.ndarray | None = None
        self._seq = 0
        self._new_frame = threading.Condition(self._lock)

    def set_frame(self, frame: np.ndarray) -> None:
        with self._lock:
            self._frame = frame
            self._seq += 1
            self._new_frame.notify_all()

    def wait_for_frame(self, last_seq: int, timeout: float) -> tuple[np.ndarray | None, int]:
        """Blockiert bis zu ``timeout`` Sekunden auf einen Frame neuer als last_seq."""
        with self._lock:
            if self._seq == last_seq:
                self._new_frame.wait(timeout=timeout)
            return self._frame, self._seq

    def clear(self) -> None:
        with self._lock:
            self._frame = None
            # _seq absichtlich nicht zurücksetzen (monoton steigend halten).


FRAME_BUFFER = FrameBuffer()
