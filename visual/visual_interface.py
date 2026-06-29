"""Gemeinsame Typen und Detector-Protokoll für Team Visual."""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable, Protocol


@dataclass
class VisionResult:
    """Ergebnis eines einzelnen Frames."""
    name: str
    found: bool
    confidence: float
    x: float | None = None
    y: float | None = None
    w: float | None = None
    h: float | None = None


class TargetHolder:
    """Thread-sicheres, zur Laufzeit änderbares Suchziel.

    Erlaubt das Umschalten des gesuchten Objekts, OHNE den laufenden Detector
    oder die Kamera neu zu starten. Der laufende Stream liest pro Frame get();
    start_tracking() ruft set() für den Live-Switch.

    Eigener Lock — bewusst NICHT der _tracking_lock aus visual.py. Sonst würde
    ein Lesen im Detector-Thread (get() pro Frame) mit stop_tracking() →
    _tracking_thread.join() deadlocken: der Detector hängt am Lock, während der
    Main-Thread ihn unter genau diesem Lock hält und auf den Detector joint.
    """

    def __init__(self, name: str = "") -> None:
        self._lock = threading.Lock()
        self._name = name.strip()

    def get(self) -> str:
        with self._lock:
            return self._name

    def set(self, name: str) -> None:
        with self._lock:
            self._name = name.strip()


# Detector-Callback pro Frame. visual.py registriert hier seinen Window-Append.
FrameCallback = Callable[[VisionResult], None]


class DetectorProtocol(Protocol):
    """Detector im Streaming-Modus. Läuft bis stop_event gesetzt wird.

    Das Suchziel kommt als TargetHolder, nicht als fixer String: der Detector
    liest pro Frame target.get() und filtert darauf. So lässt sich das Ziel zur
    Laufzeit wechseln, ohne stream() (und damit Kamera/Pipeline) neu zu starten.
    """

    def stream(
        self,
        target: TargetHolder,
        on_frame: FrameCallback,
        stop_event: threading.Event,
    ) -> None: ...