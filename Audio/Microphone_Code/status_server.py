"""
Kleiner FastAPI-Server, der auf dem Laptop laeuft und Status-Updates des
Roboter-Controllers entgegennimmt.

Aufgerufen wird er aus audio_main.py heraus in einem Hintergrund-Thread.
Der Controller schickt bei Statuswechseln:

    POST http://<laptop>:8002/status
    Content-Type: application/json
    {
        "status":  "idle" | "searching" | "found" | "lost" | "error",
        "item":    "<optional, z.B. person>",
        "details": "<optional, Freitext>"
    }

Ungueltige Status-Werte werden von Pydantic mit HTTP 422 abgelehnt — der
State bleibt in diesem Fall unveraendert.
"""
from enum import Enum

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel


class RobotStatus(str, Enum):
    """Erlaubte Statuswerte — mit dem Roboter-Team abgestimmt."""
    IDLE = "idle"
    SEARCHING = "searching"
    FOUND = "found"
    LOST = "lost"
    ERROR = "error"


class StatusUpdate(BaseModel):
    """Datenmodell des erwarteten Payloads. Pydantic validiert automatisch."""
    status: RobotStatus
    item: str | None = None
    details: str | None = None


def make_app(state):
    """
    Erzeugt eine FastAPI-Instanz, deren /status-Handler in den uebergebenen
    StatusState schreibt. Die Closure auf 'state' macht das Modul wiederverwendbar.
    """
    app = FastAPI()

    @app.post("/status")
    def receive_status(update: StatusUpdate):
        state.set(update.status.value, update.item, update.details)
        return {"ok": True}

    return app


def run(state, host="0.0.0.0", port=8012):
    """
    Startet uvicorn synchron — gedacht fuer den Aufruf in einem daemon-Thread.
    log_level="warning" unterdrueckt die Standard-Zugriffslogs, damit das
    Terminal des Microphone-Clients ruhig bleibt.
    """
    uvicorn.run(make_app(state), host=host, port=port, log_level="warning")
