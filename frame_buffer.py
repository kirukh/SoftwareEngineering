"""
frame_buffer.py — Thread-sicherer Puffer für den jeweils letzten annotierten Frame.

Hintergrund: Kamera und Hailo/YOLO greifen exklusiv auf die Hardware zu.
Der /stream-Endpoint darf deshalb KEINE zweite Kamera öffnen. Stattdessen
legt der laufende Detector-Stream hier seinen letzten annotierten Frame
(JPEG-kodiert) ab, und der HTTP-Endpoint liest ihn nur aus.

Ablauf:
    Detector.stream()  ──set_frame(jpeg_bytes)──▶  [ FrameBuffer ]
    GET /stream        ◀──get_frame()────────────  [ FrameBuffer ]

Der Puffer hält immer nur EINEN Frame (den neuesten). Wer pollt, bekommt
den aktuellsten Stand; verpasste Frames sind für einen Live-View egal.
"""
from __future__ import annotations

import threading


class FrameBuffer:
    """Hält genau einen JPEG-Frame, thread-sicher les-/schreibbar."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jpeg: bytes | None = None
        # Wird gesetzt, sobald ein neuer Frame da ist — erlaubt dem
        # Stream-Generator, blockierend auf den nächsten Frame zu warten,
        # statt in einer Busy-Loop zu pollen.
        self._new_frame = threading.Condition(self._lock)
        self._seq = 0  # Frame-Zähler, damit Consumer "schon gesehen" erkennen

    def set_frame(self, jpeg: bytes) -> None:
        """Vom Detector aufgerufen: neuen annotierten Frame ablegen."""
        with self._lock:
            self._jpeg = jpeg
            self._seq += 1
            self._new_frame.notify_all()

    def get_frame(self) -> bytes | None:
        """Aktuellen Frame holen (oder None, wenn noch keiner da ist)."""
        with self._lock:
            return self._jpeg

    def wait_for_frame(self, last_seq: int, timeout: float) -> tuple[bytes | None, int]:
        """Blockiert, bis ein Frame NEUER als last_seq da ist.

        Gibt (jpeg, seq) zurück. Bei Timeout wird der aktuelle Frame
        zurückgegeben (auch wenn unverändert), damit der Stream nicht
        einfriert, wenn der Detector gerade nichts liefert.
        """
        with self._lock:
            if self._seq == last_seq:
                self._new_frame.wait(timeout=timeout)
            return self._jpeg, self._seq

    def clear(self) -> None:
        """Puffer leeren — beim Stop des Trackings aufgerufen."""
        with self._lock:
            self._jpeg = None
            # _seq NICHT zurücksetzen: monoton steigend halten, sonst
            # denkt ein Consumer mit altem last_seq, es gäbe nichts Neues.


# Modulweite Instanz — von allen Detektoren und vom Server geteilt.
FRAME_BUFFER = FrameBuffer()