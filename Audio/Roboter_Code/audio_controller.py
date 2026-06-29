"""
FastAPI-Server auf der Roboter-Seite.

Nimmt vom Microphone-Client den erkannten Sprachtext entgegen (POST /speech),
laesst ihn vom gemeinsamen command_parser zerlegen und leitet das Ergebnis an
das eigentliche Roboter-Interface weiter.

Start (aus dem Roboter_Code-Verzeichnis heraus):
    uvicorn audio_controller:app --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI
from command_parser import parse_command
import requests

app = FastAPI()

# URL der eigentlichen Roboter-Steuerung. Wird vom anderen Team bereitgestellt.
interface_api = "http://127.0.0.1:7980/audio_command"


@app.get("/")
def read_root():
    """Schneller Health-Check — sollte im Browser ein {"Hello": "World"} zeigen."""
    return {"Hello": "World"}


@app.post("/speech")
def get_speech(posted_data: dict):
    """
    Endpunkt fuer den Microphone-Client.

    Erwartet: {"raw_string": "<gesprochener Text>"}
    Antwortet mit dem geparsten Befehl, damit der Client das Ergebnis anzeigen kann.
    """
    print("Got dict", posted_data)
    command_data = build_command(posted_data["raw_string"])
    return command_data


def build_command(s):
    """
    Parst den Text und leitet ihn — falls erkennbar — an das Roboter-Interface weiter.
    Fehler beim Weiterleiten brechen die Antwort an den Client nicht ab; der Client
    bekommt in jedem Fall die geparsten Felder zurueck.
    """
    command_data = parse_command(s)
    if command_data["command_build"]:
        try:
            response = requests.post(interface_api, json=command_data)
            print("robot started:", command_data, response)
        except Exception:
            print("Roboter-Interface nicht erreichbar!")
    return command_data
