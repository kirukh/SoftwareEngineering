from fastapi import FastAPI
from pydantic import BaseModel
import requests



app = FastAPI()

NAVIGATION_URL = "http://127.0.0.1:7979/start"

class CommandDaten(BaseModel):
    command: str
    item: str
    command_build: bool | None = None

def start_roboter(command_daten: dict):
    try:
        antwort = requests.post(NAVIGATION_URL, json=command_daten)
        return {
            "status": "weitergeleitet",
            "navigation_antwort": antwort.json()
        }
    except Exception as e:
        return {
            "status": "fehler",
            "message": str(e)
        }

@app.post("/audio_command")
def audio_uebergabe(command_daten: CommandDaten):
    print("Antwort von Audio", command_daten)
    if command_daten.command_build:
        return start_roboter(command_daten.dict())
    else:
        return {"status": "Befehl nicht erkannt"}
    
@app.post("/audio_antwort")
def audio_antwort(data: dict):
    print("Feedback: ", data)
    return {"erhalten": True}