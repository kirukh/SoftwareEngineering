"""HTTP-Server des Visual-Moduls (Pi 5 / Laptop-Fallback).

Endpoints:
    POST /track/start    {"name": "cell phone"}      Controller-Team
    GET  /track/latest   aggregiertes Window-Ergebnis Controller-Team
    POST /track/stop     Tracking beenden             Controller-Team
    GET  /health         Status + aktiver Detector + ready
    GET  /stream         MJPEG-Live-Stream mit Boxen  Audio-Team
    GET  /               Browser-Dashboard zum Testen

Konfiguration: siehe config.py. Aktive Werte: ``python config.py``.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
log = logging.getLogger("visual.server")

import cv2
import numpy as np
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, field_validator

import visual
from config import CONFIG
from frame_buffer import FRAME_BUFFER


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Detector wird vorgeladen...")
    try:
        visual.prewarm()
        log.info("Bereit. Aktiver Detector: %s", visual.active_detector())
    except Exception as e:
        log.error("Prewarm fehlgeschlagen: %s", e, exc_info=True)
    yield
    visual.stop_tracking()


app = FastAPI(title="Visual API (Pi 5 / Laptop-Fallback)", version="1.0.0", lifespan=lifespan)


class TrackStartReq(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name darf nicht leer sein")
        return v.strip()


@app.post("/track/start", summary="Tracking starten")
def track_start(req: TrackStartReq) -> dict:
    try:
        return visual.start_tracking(req.name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/track/latest", summary="Aktuelles Tracking-Ergebnis")
def track_latest() -> dict:
    return visual.get_latest()


@app.post("/track/stop", summary="Tracking beenden")
def track_stop() -> dict:
    return visual.stop_tracking()


@app.get("/health", summary="Server-Health-Check")
def health() -> dict:
    detector, ready = visual.get_health_status()
    return {"status": "ok", "detector": detector, "ready": ready}


_BOUNDARY = "visualframe"
_PLACEHOLDER_JPEG = cv2.imencode(".jpg", np.full((480, 640, 3), 64, dtype=np.uint8))[1].tobytes()


def _encode_jpeg(frame: np.ndarray) -> bytes | None:
    max_w = CONFIG.stream_max_width
    if max_w and frame.shape[1] > max_w:
        scale = max_w / frame.shape[1]
        frame = cv2.resize(frame, (max_w, int(frame.shape[0] * scale)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), CONFIG.stream_jpeg_quality])
    return buf.tobytes() if ok else None


async def _mjpeg_generator():
    """Liefert fortlaufend JPEG-Frames aus dem FRAME_BUFFER (keine eigene Kamera),
    gedrosselt auf stream_fps. Ohne Tracking geht der Platzhalter raus."""
    last_seq = -1
    min_interval = 1.0 / CONFIG.stream_fps
    while True:
        frame, seq = await asyncio.to_thread(FRAME_BUFFER.wait_for_frame, last_seq, 1.0)
        last_seq = seq
        payload = await asyncio.to_thread(_encode_jpeg, frame) if frame is not None else None
        if payload is None:
            payload = _PLACEHOLDER_JPEG
        yield (
            b"--" + _BOUNDARY.encode() + b"\r\n"
            b"Content-Type: image/jpeg\r\n"
            b"Content-Length: " + str(len(payload)).encode() + b"\r\n\r\n"
            + payload + b"\r\n"
        )
        await asyncio.sleep(min_interval)


@app.get("/stream", summary="MJPEG-Live-Stream mit eingezeichneten Boxen")
def stream() -> StreamingResponse:
    return StreamingResponse(
        _mjpeg_generator(),
        media_type=f"multipart/x-mixed-replace; boundary={_BOUNDARY}",
    )


@app.get("/", response_class=HTMLResponse, summary="Browser-Dashboard")
def dashboard() -> str:
    return """
    <!DOCTYPE html>
    <html lang="de">
    <head>
        <meta charset="utf-8">
        <title>Visual-Modul — Steuerung</title>
        <style>
            body { font-family: system-ui, Arial, sans-serif; text-align: center;
                   background: #1e1e22; color: #eee; margin: 0; padding: 24px; }
            .wrap { max-width: 760px; margin: auto; }
            img { width: 640px; max-width: 100%; border: 3px solid #444;
                  border-radius: 8px; background: #000; }
            input { padding: 10px; font-size: 16px; width: 220px; border-radius: 6px; border: 1px solid #666; }
            button { padding: 10px 20px; font-size: 16px; margin: 8px; cursor: pointer;
                     border: none; border-radius: 6px; color: #fff; }
            .start { background: #28a745; } .stop { background: #dc3545; }
            #status { margin-top: 14px; font-weight: 600; color: #ffc107; }
        </style>
    </head>
    <body>
        <div class="wrap">
            <h1>Visual-Modul — Live-Test</h1>
            <img src="/stream" alt="Live-Stream">
            <div>
                <input id="obj" value="person" placeholder="COCO-Label, z.B. cell phone">
                <button class="start" onclick="start()">Start</button>
                <button class="stop" onclick="stop()">Stop</button>
            </div>
            <div id="status">Status: bereit</div>
        </div>
        <script>
            const s = (t) => document.getElementById('status').innerText = "Status: " + t;
            async function start() {
                const name = document.getElementById('obj').value;
                s("starte '" + name + "'...");
                const res = await fetch('/track/start', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({name})
                });
                if (!res.ok) { s("Fehler beim Start (" + res.status + ")"); return; }
                s("tracke '" + (await res.json()).name + "'");
            }
            async function stop() {
                s("stoppe...");
                await fetch('/track/stop', {method: 'POST'});
                s("gestoppt (idle)");
            }
        </script>
    </body>
    </html>
    """


if __name__ == "__main__":
    log.info("Starte auf %s:%s", CONFIG.host, CONFIG.port)
    uvicorn.run("server:app", host=CONFIG.host, port=CONFIG.port, reload=False)
