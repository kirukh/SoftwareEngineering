"""
Thread-sicherer Container fuer den aktuellen Roboter-Status.

Bruecke zwischen FastAPI-Thread (status_server) und Tkinter-Thread (audio_gui):
- status_server schreibt per state.set(...) bei eingehendem POST /status
- audio_gui liest per state.get() im 500ms-Polling und aktualisiert das Label

Das Lock schuetzt vor Race-Conditions zwischen Schreiber und Leser. Ohne Lock
koennte der GUI-Thread ein halb-aktualisiertes Dictionary lesen.
"""
import threading


class StatusState:
    def __init__(self):
        self._lock = threading.Lock()
        # Default: Roboter ist im Leerlauf. item/details sind optional.
        self._current = {"status": "idle", "item": None, "details": None}

    def set(self, status, item=None, details=None):
        """Aktualisiert den Status atomar."""
        with self._lock:
            self._current = {"status": status, "item": item, "details": details}

    def get(self):
        """Gibt eine Kopie des aktuellen Status zurueck — Aufrufer kann sie gefahrlos veraendern."""
        with self._lock:
            return dict(self._current)
