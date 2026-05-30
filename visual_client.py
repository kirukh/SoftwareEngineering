"""visual_client.py — kleiner HTTP-Client für die Visual-API.

Vom Controller-Team zu nutzen, damit nicht jeder rohe httpx-Aufrufe schreibt.

Beispiel:
    from visual_client import VisualClient

    with VisualClient() as visual:
        visual.start("cell phone")
        while controller_running:
            r = visual.latest()
            if r["status"] == "running" and r["found"]:
                laser.point_to(r["x"], r["y"])
            else:
                laser.idle()
            time.sleep(0.1)
"""
from __future__ import annotations

import httpx


class VisualClient:
    def __init__(self, base_url: str = "http://127.0.0.1:7995", timeout: float = 5.0):
        # Eigene HTTP-Session: hält Verbindung offen, schneller als jedes Mal neu.
        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout)

    def start(self, name: str) -> dict:
        """Tracking starten. Idempotent — gleicher Name = no-op, anderer Name wechselt."""
        r = self._client.post("/track/start", json={"name": name})
        r.raise_for_status()
        return r.json()

    def latest(self) -> dict:
        """Aktuelles Tracking-Ergebnis pollen.

        Rückgabe immer ein Dict mit 'status':
        - {"status": "idle"}                          → kein Tracking aktiv
        - {"status": "running", "found": False, ...}  → Tracking läuft, nichts erkannt
        - {"status": "running", "found": True, "x": 0.5, "y": 0.5,
           "w": 0.2, "h": 0.3, "confidence": 0.87, "name": "cell phone"}
        """
        r = self._client.get("/track/latest")
        r.raise_for_status()
        return r.json()

    def stop(self) -> dict:
        """Tracking beenden. Idempotent."""
        r = self._client.post("/track/stop")
        r.raise_for_status()
        return r.json()

    def health(self) -> bool:
        """True wenn der Server antwortet — fürs Hochfahren / Reconnect-Logik.

        ACHTUNG: prüft nur, ob der HTTP-Server erreichbar ist, NICHT ob ein
        Detector geladen ist. Für "Detection wirklich bereit?" → ready().
        """
        try:
            return self._client.get("/health").status_code == 200
        except httpx.HTTPError:
            return False

    def ready(self) -> bool:
        """True wenn der Server läuft UND ein Detector geladen ist.

        Das ist der Check, den ihr beim Hochfahren wollt: health() ist True,
        sobald der Server antwortet — auch wenn der prewarm fehlgeschlagen ist
        und ein /track/start sofort einen 500er liefern würde. ready() schließt
        das aus.

        Rückwärtskompatibel: wertet das neue 'ready'-Feld aus, fällt sonst auf
        das 'detector'-Feld zurück (für ältere Server ohne 'ready').
        """
        info = self.health_info()
        if not info:
            return False
        if "ready" in info:
            return bool(info["ready"])
        return info.get("detector") not in (None, "", "none")

    def health_info(self) -> dict | None:
        """Detaillierter Health-Check inkl. aktivem Detector.

        Gibt z.B. {"status": "ok", "detector": "yolo", "ready": true} zurück,
        oder None bei Fehler. Praktisch zum Debuggen ('läuft auf dem Pi
        tatsächlich Hailo?').
        """
        try:
            r = self._client.get("/health")
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError:
            return None

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "VisualClient":
        return self

    def __exit__(self, *_exc) -> None:
        # stop() / close() dürfen niemals den ursprünglichen Fehler überdecken.
        try:
            self.stop()
        except Exception as e:
            print(f"[visual_client] stop() im __exit__ fehlgeschlagen: {e}")
        try:
            self.close()
        except Exception:
            pass