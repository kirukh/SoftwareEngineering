"""Gemeinsame Typen und Detector-Protokoll für Team Visual."""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable, Protocol


@dataclass
class VisionResult:
    """Ergebnis eines einzelnen Frames. Koordinaten normiert auf 0.0–1.0."""
    name: str
    found: bool
    confidence: float
    x: float | None = None
    y: float | None = None
    w: float | None = None
    h: float | None = None


FrameCallback = Callable[[VisionResult], None]


class DetectorProtocol(Protocol):
    """Detector im Streaming-Modus. Läuft, bis stop_event gesetzt wird."""

    def stream(
        self,
        object_name: str,
        on_frame: FrameCallback,
        stop_event: threading.Event,
    ) -> None: ...
