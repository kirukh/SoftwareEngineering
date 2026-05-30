"""HTTP-Server für die Kommunikation mit dem Controller.

FastAPI auf 127.0.0.1:7995 (Default). Endpoints:
    POST   /track/start    Body: {"name": "cell phone"}
    GET    /track/latest   aggregiertes Window-Ergebnis
    POST   /track/stop     Tracking beenden
    GET    /health         Server-Check (inkl. aktiver Detector + ready-Flag)
    GET    /stream         MJPEG-Live-Stream mit eingezeichneten Boxen

Konfiguration: siehe config.py (Defaults < config.yaml < Env-Variablen).
Aktive Werte anzeigen: `python config.py`.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

# Logging einmalig konfigurieren, BEVOR die Module unten importiert werden,
# damit ihre Log-Ausgaben (config-Warnungen, Detector-Wahl, prewarm) sichtbar
# sind. basicConfig ist idempotent — ein evtl. später folgendes uvicorn-Setup
# überschreibt es nicht.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("visual.server")

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

import visual
from config import CONFIG
from frame_buffer import FRAME_BUFFER


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Detector beim Server-Start vorladen, damit /health erst antwortet wenn
    # alles bereit ist und der erste /track/start nicht in einen Timeout läuft.
    log.info("Detector wird vorgeladen...")
    try:
        visual.prewarm()
        log.info("Bereit. Aktiver Detector: %s", visual.active_detector())
    except Exception as e:
        # Prewarm-Fehler nicht den Server-Start abbrechen lassen — das wäre
        # schlecht im Rollout. Stattdessen loggen, /health meldet dann
        # status='degraded' / ready=false, und der erste /track/start liefert
        # den eigentlichen Fehler.
        log.error("Prewarm fehlgeschlagen: %s", e, exc_info=True)
    yield
    visual.stop_tracking()


app = FastAPI(
    title="visual_api",
    description="Tracking-API für das Visual-Modul",
    version="0.5.0",
    lifespan=lifespan,
)


# ------------------------------------------------------------------ Schemas

class TrackStartReq(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name darf nicht leer sein")
        return v.strip()


class TrackStartRes(BaseModel):
    status: str
    name: str


class TrackLatestRes(BaseModel):
    status: str  # 'idle' | 'running'
    name: str | None = None
    found: bool | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    x: float | None = Field(default=None, ge=0.0, le=1.0)
    y: float | None = Field(default=None, ge=0.0, le=1.0)
    w: float | None = Field(default=None, ge=0.0, le=1.0)
    h: float | None = Field(default=None, ge=0.0, le=1.0)


class TrackStopRes(BaseModel):
    status: str
    was_running: bool


class HealthRes(BaseModel):
    status: str           # 'ok' wenn ein Detector geladen ist, sonst 'degraded'
    detector: str         # 'hailo' | 'yolo' | 'none' | ...
    ready: bool           # True wenn Detection tatsächlich bereit ist


# ------------------------------------------------------------------ Endpoints

@app.post("/track/start", response_model=TrackStartRes, summary="Tracking starten")
def track_start(request: TrackStartReq) -> TrackStartRes:
    try:
        return TrackStartRes(**visual.start_tracking(request.name))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/track/latest", response_model=TrackLatestRes, summary="Aktuelles Tracking-Ergebnis")
def track_latest() -> TrackLatestRes:
    return TrackLatestRes(**visual.get_latest())


@app.post("/track/stop", response_model=TrackStopRes, summary="Tracking beenden")
def track_stop() -> TrackStopRes:
    return TrackStopRes(**visual.stop_tracking())


@app.get("/health", response_model=HealthRes, summary="Server-Health-Check")
def health() -> HealthRes:
    """Health- und Readiness-Check.

    Wichtig für das Controller-Team: HTTP 200 heißt nur "Server läuft". Ob
    Detection wirklich bereit ist (prewarm erfolgreich, ein Detector geladen),
    steht im `ready`-Flag bzw. an `status`:
      - ready=true,  status="ok"        → losgehen
      - ready=false, status="degraded"  → Server up, aber kein Detector
        (z.B. prewarm fehlgeschlagen). Ein /track/start würde 500 liefern.
    """
    detector = visual.active_detector()
    ready = detector not in ("", "none")
    return HealthRes(
        status="ok" if ready else "degraded",
        detector=detector,
        ready=ready,
    )


# ------------------------------------------------------------------ MJPEG-Stream

# Multipart-Boundary für den MJPEG-Stream. Beliebiger Marker-String, muss
# nur zwischen Header und Frames konsistent sein.
_BOUNDARY = "visualframe"

# Ein simples 1x1-Platzhalter-JPEG (grau), das ausgeliefert wird, solange
# noch kein echter Frame da ist (z.B. /stream geöffnet, aber kein Tracking
# aktiv). So sieht der Client sofort etwas und nicht einen Verbindungsfehler.
_PLACEHOLDER_JPEG = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000ffdb00430008060607060508"
    "0707070909080a0c140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20242e2720"
    "222c231c1c2837292c30313434341f27393d38323c2e333432ffc00011080001"
    "000103012200021101031101ffc4001f0000010501010101010100000000000000"
    "000102030405060708090a0bffc400b5100002010303020403050504040000017d"
    "01020300041105122131410613516107227114328191a1082342b1c11552d1f024"
    "33627282090a161718191a25262728292a3435363738393a434445464748494a53"
    "5455565758595a636465666768696a737475767778797a838485868788898a9293"
    "9495969798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6b7b8b9bac2c3c4c5c6c7c8c9"
    "cad2d3d4d5d6d7d8d9dae1e2e3e4e5e6e7e8e9eaf1f2f3f4f5f6f7f8f9faffda00"
    "0c03010002110311003f00fbfeffd9"
)


async def _mjpeg_generator():
    """Async-Generator: liefert fortlaufend JPEG-Frames im Multipart-Format.

    Liest nur aus dem FRAME_BUFFER — öffnet KEINE Kamera. Die Frames werden
    vom laufenden Detector-Stream dort abgelegt. Läuft kein Tracking, wird
    der Platzhalter-Frame gesendet, damit die Verbindung nicht abreißt.
    """
    last_seq = -1
    # Mindestabstand zwischen zwei Frames, begrenzt die Bandbreite.
    min_interval = 1.0 / CONFIG.stream_fps

    while True:
        # Auf einen neuen Frame warten (max. 1s), damit der Stream auch
        # ohne aktives Tracking am Leben bleibt.
        jpeg, seq = await asyncio.to_thread(
            FRAME_BUFFER.wait_for_frame, last_seq, 1.0
        )
        last_seq = seq

        payload = jpeg if jpeg is not None else _PLACEHOLDER_JPEG
        yield (
            b"--" + _BOUNDARY.encode() + b"\r\n"
            b"Content-Type: image/jpeg\r\n"
            b"Content-Length: " + str(len(payload)).encode() + b"\r\n\r\n"
            + payload + b"\r\n"
        )
        await asyncio.sleep(min_interval)


@app.get("/stream", summary="MJPEG-Live-Stream mit eingezeichneten Boxen")
def stream() -> StreamingResponse:
    """MJPEG-Stream der annotierten Kamerabilder.

    Im Browser direkt einbettbar:  <img src="http://<pi-ip>:7995/stream">

    Für Tkinter (Audio-Team): kein natives Rendering — der Stream muss in
    einem Hintergrund-Thread selbst geparst werden. Siehe tkinter_stream_example.py.

    Hinweis: Der Stream zeigt nur dann Boxen/Bewegung, wenn Tracking aktiv
    ist (POST /track/start). Ohne Tracking kommt ein Platzhalter-Bild.
    """
    return StreamingResponse(
        _mjpeg_generator(),
        media_type=f"multipart/x-mixed-replace; boundary={_BOUNDARY}",
    )


# ------------------------------------------------------------------ Main

if __name__ == "__main__":
    log.info("Starte auf %s:%s", CONFIG.host, CONFIG.port)
    uvicorn.run("server:app", host=CONFIG.host, port=CONFIG.port, reload=False)