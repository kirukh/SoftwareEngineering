"""
tkinter_stream_example.py — Beispiel für das AUDIO-TEAM.

Zeigt, wie der MJPEG-Stream von /stream in einem Tkinter-GUI angezeigt
wird. Anders als ein Browser kann Tkinter MJPEG NICHT von selbst rendern —
der Multipart-Stream muss in einem Hintergrund-Thread geparst und Frame
für Frame in ein Label gepusht werden.

Das ist eine fertige, kopierbare Vorlage — kein Teil des Visual-Servers,
sondern Beispielcode für eure Seite.

Benötigt auf eurer Seite:
    pip install pillow httpx

Start (Visual-Server muss laufen):
    python tkinter_stream_example.py
    python tkinter_stream_example.py http://192.168.0.42:7995   # Pi im Netz
"""
from __future__ import annotations

import io
import sys
import threading
import tkinter as tk

import httpx
from PIL import Image, ImageTk


class MjpegStreamView:
    """Liest einen MJPEG-Stream im Hintergrund und zeigt ihn in einem Label."""

    def __init__(self, root: tk.Tk, stream_url: str) -> None:
        self.root = root
        self.stream_url = stream_url
        self.label = tk.Label(root, text="Verbinde mit Stream...", bg="black", fg="white")
        self.label.pack(fill=tk.BOTH, expand=True)

        self._running = True
        self._latest_photo: ImageTk.PhotoImage | None = None

        # Stream-Lesen läuft im Hintergrund-Thread. Tkinter selbst ist
        # NICHT thread-safe — der Thread legt nur die rohen JPEG-Bytes ab,
        # das eigentliche Anzeigen passiert im Tkinter-Mainloop via after().
        self._latest_jpeg: bytes | None = None
        self._jpeg_lock = threading.Lock()

        threading.Thread(target=self._read_stream, daemon=True).start()
        self._refresh_ui()

    def _read_stream(self) -> None:
        """Hintergrund-Thread: MJPEG-Multipart-Stream parsen.

        Ein MJPEG-Stream ist eine Folge von Teilen, jeweils:
            --boundary\r\n
            Content-Type: image/jpeg\r\n
            Content-Length: <n>\r\n
            \r\n
            <n Bytes JPEG>
        Wir suchen die JPEG-Start-/End-Marker (FFD8 / FFD9) im Bytestrom.
        Das ist robuster als das Boundary-Parsing, weil es egal ist, wie
        der Server die Boundary genau formatiert.
        """
        buffer = b""
        while self._running:
            try:
                with httpx.stream("GET", self.stream_url, timeout=10.0) as resp:
                    resp.raise_for_status()
                    for chunk in resp.iter_bytes():
                        if not self._running:
                            return
                        buffer += chunk
                        # Vollständige JPEGs aus dem Puffer herausziehen.
                        while True:
                            start = buffer.find(b"\xff\xd8")  # JPEG SOI
                            end = buffer.find(b"\xff\xd9")     # JPEG EOI
                            if start == -1 or end == -1 or end < start:
                                break
                            jpeg = buffer[start:end + 2]
                            buffer = buffer[end + 2:]
                            with self._jpeg_lock:
                                self._latest_jpeg = jpeg
            except Exception as e:
                # Verbindung abgerissen (Server neu gestartet o.ä.) —
                # kurz warten und neu verbinden.
                print(f"[stream] Verbindungsfehler: {e} — reconnect in 1s")
                if not self._running:
                    return
                threading.Event().wait(1.0)

    def _refresh_ui(self) -> None:
        """Läuft im Tkinter-Mainloop: neuesten Frame ins Label rendern."""
        if not self._running:
            return
        with self._jpeg_lock:
            jpeg = self._latest_jpeg

        if jpeg is not None:
            try:
                img = Image.open(io.BytesIO(jpeg))
                photo = ImageTk.PhotoImage(img)
                self.label.config(image=photo, text="")
                # Referenz halten, sonst wird das Bild vom GC entfernt.
                self._latest_photo = photo
            except Exception as e:
                print(f"[stream] Frame konnte nicht dekodiert werden: {e}")

        # ~30 fps UI-Refresh. Der Stream selbst ist serverseitig auf
        # stream_fps begrenzt; öfter aktualisieren schadet nicht.
        self.root.after(33, self._refresh_ui)

    def stop(self) -> None:
        self._running = False


def main() -> None:
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:7995"
    stream_url = base_url.rstrip("/") + "/stream"

    root = tk.Tk()
    root.title("Visual-Stream (Audio-Team-Demo)")
    root.geometry("680x520")

    view = MjpegStreamView(root, stream_url)

    def on_close() -> None:
        view.stop()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    print(f"[stream] Zeige Stream von {stream_url}")
    print("[stream] Hinweis: Boxen erscheinen nur, wenn Tracking aktiv ist")
    print("[stream]          (POST /track/start am Visual-Server).")
    root.mainloop()


if __name__ == "__main__":
    main()
