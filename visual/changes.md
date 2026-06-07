# Visual module — change summary

Was sich im Visual-Modul geändert hat, an einer Stelle. Für die Migration auf
Controller- und Audio-Seite.

## TL;DR

Das Visual-Modul ist ein eigenständiger **HTTP-Server** (FastAPI auf
`127.0.0.1:7995` bzw. `0.0.0.0:7995`). Statt einmaliger `search()`-Aufrufe läuft
**kontinuierliches Tracking** im Hintergrund; ihr pollt das aktuelle aggregierte
Ergebnis. Es gibt einen Python-Client (`visual_client.py`).

Zusätzlich: ein **MJPEG-Live-Stream** (`GET /stream`) fürs Audio-Team und ein
**Browser-Dashboard** (`GET /`) zum Selbsttesten.

> **Port:** 7995 (Range 7991–8000, Festlegung Prof. Jehle).
> **Detector:** Auto-Fallback Hailo → YOLO. `GET /health` zeigt den aktiven an.

## Neuester Stand (Sprint 4)

- **Hailo-Stream funktioniert** auf dem Pi (T-20/T-30 erledigt). `/stream`
  liefert annotierte Frames mit Hailo **und** YOLO. Der Frame-Abgriff läuft über
  die hailo-apps-Helper aus der GStreamer-Pipeline (keine zweite Kamera).
- **Flüssiger, latenzarmer Stream:** Pipeline-Queues auf „alte Frames verwerfen",
  Frame-Abgriff auf `stream_fps` gedrosselt, Frames vor dem Encoding auf
  `stream_max_width` verkleinert.
- **`/health` liefert zusätzlich `ready`** — `true`, sobald ein Detector geladen
  ist. `VisualClient.ready()` wertet das aus. Nutzt das beim Hochfahren statt nur
  `health()` (das ist schon `true`, wenn der Server antwortet, der Detector aber
  evtl. noch nicht bereit ist).
- **Stale-Guard:** kommt seit `stale_after_seconds` (Default 1.5s) kein neuer
  Frame mehr, meldet `/track/latest` `found=false` statt einen alten Treffer
  einzufrieren.
- **Neue Config-Felder:** `hailo_input`, `hailo_hef_path`, `stale_after_seconds`,
  `stream_max_width`. `host`-Default ist jetzt `0.0.0.0` (von außen erreichbar).

## HTTP-API (für den Controller)

```python
# Tracking aus:
{"status": "idle"}

# läuft, nichts erkannt:
{"status": "running", "name": "cell phone", "found": false,
 "confidence": 0.0, "x": null, "y": null, "w": null, "h": null}

# läuft, Treffer:
{"status": "running", "name": "cell phone", "found": true,
 "confidence": 0.87, "x": 0.51, "y": 0.48, "w": 0.18, "h": 0.32}

# Health:
{"status": "ok", "detector": "hailo", "ready": true}   # detector: hailo|yolo|none
```
Alle Koordinaten normiert auf 0.0–1.0.

## Migration (altes → neues)

```python
# ALT (entfällt):
from visual import search
result = search({"name": "smartphone"})

# NEU:
from visual_client import VisualClient
import time

with VisualClient() as visual:              # default http://127.0.0.1:7995
    visual.start("cell phone")              # COCO-Label vom Audio-Team
    while controller_running:
        r = visual.latest()
        if r["status"] == "running" and r["found"]:
            laser.point_to(r["x"], r["y"])  # auch r["w"], r["h"]
        else:
            laser.idle()
        time.sleep(0.1)
    # stop() ruft der Context-Manager automatisch
```

Wichtige Verhaltensänderungen gegenüber Sprint 1:
1. **Kein One-Shot-`search()`** mehr — `start()`, dann `latest()` pollen, dann `stop()`.
2. **Ergebnis** enthält zusätzlich `w`, `h` und ein `status`-Feld.
3. **`name` muss ein gültiges COCO-Label sein** (`"cell phone"`, nicht
   `"smartphone"`). Das Audio-Team mappt; `coco.yaml` ist die Source-of-Truth.
4. **Der Server muss laufen** (`python server.py`) — keine In-Process-API mehr.
5. **Port 7995** (vorher 8000).

## Polling-Rate

100 ms ist ein guter Default. Schneller schadet nicht (idempotent, billig),
liefert aber keine frischeren Daten.

## Der `/stream`-Endpoint — fürs Audio-Team, nicht den Controller

`GET /stream` ist ein MJPEG-Video-Feed mit eingezeichneten Boxen, gedacht für die
Audio-Team-Oberfläche. **Nicht Teil der Tracking-Integration** — als Controller
müsst ihr ihn nicht aufrufen, und er ändert nichts an `/track/*`.

- Zeigt nur bei aktivem Tracking Boxen; sonst grauer Platzhalter.
- Öffnet keine zweite Kamera (teilt sich Detector + Kamera mit dem Tracking).
- Funktioniert mit Hailo **und** YOLO.

Audio-Team: `tkinter_stream_example.py` und Abschnitt 10 in `Anleitung.md`.

## Was auf unserer Seite noch offen ist

- **Team-übergreifende Config-Datei** (alle Modul-Ports zentral): in Diskussion.
  Die modulinterne Config (`config.py`) ist fertig.

## Repo + Docs

- `Anleitung.md` — Quick Start fürs Controller-Team
- `README.md` — volle API-Referenz und Config
- `TESTING.md` — lokaler Test ohne Pi
- `visual_client.py` — fertiger Python-Client
- `live_e2e_test.py` — lauffähiges End-to-End-Beispiel