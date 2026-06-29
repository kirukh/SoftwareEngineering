# alte main der FastAPI -> Hauptort controller.py

from fastapi import FastAPI
from pydantic import BaseModel

from audio_interface import app as audio_command
from controller_visual_interface import app as visual_command

# Anwendung wird ersellt
app = FastAPI()

# prüft Datenmodelle
class Item(BaseModel):
    name: str
    price: float
    is_offer: bool | None = None
    

# Hauptseite
@app.get("/")

def root():
    return {"status": "Läuft"}

@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q" : q}

# PUT-Request
@app.put("/items/{item_id}")
def update_item(item_id: int, item: Item):
    return {"item_name": item.name, "item_id": item_id}

app.mount("/audio", audio_command)

app.mount("/visual", visual_command)

