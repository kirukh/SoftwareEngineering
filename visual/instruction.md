# Anleitung: Visual-Server starten & einbinden

Wie der Visual-Server auf dem Pi gestartet wird und wie ihr (Controller-Team)
ihn aus eurem Code ansprecht. Sprint-Ziel: Roboter findet ein vom Audio-Team
gemeldetes Objekt und liefert die Koordinaten zurück.

Für die **Bildübertragung** (MJPEG-Stream ans Audio-Team) siehe Abschnitt 10.
Für das **lokale Testen ohne Pi** siehe [`TESTING.md`](TESTING.md).

## TL;DR für das Controller-Team

```python
from visual_client import VisualClient

with VisualClient(base_url="http://127.0.0.1:7995") as visual:
    visual.start("cell phone")          # COCO-Label vom Audio-Team
    while suche_läuft:
        r = visual.latest()
        if r["status"] == "running" and r["found"]:
            controller.handle_found(r)  # r["x"], r["y"], r["w"], r["h"] sind 0.0–1.0
            break
        time.sleep(0.1)
    # stop() wird beim Verlassen automatisch aufgerufen
```

## 1. Vorbereitung auf dem Pi

```bash
git clone <unser-repo>
cd SoftwareEngineering/
```

Der Hailo-Stack wird über das hailo-apps-Setup installiert (`sudo ./install.sh`
im hailo-apps-Repo). Fragt Christian, wenn das auf einem frischen Pi gemacht
werden muss.

## 2. Server starten

### Auf dem Pi (Hailo)

Hailo braucht die aktivierte hailo-apps-Umgebung — die setzt neben dem venv auch
die nötigen GStreamer-/TAPPAS-Variablen:

```bash
cd ~/hailo-apps && source setup_env.sh
cd ~/SoftwareEngineering && python server.py
```

Der Server nimmt automatisch den besten Detector: Hailo, wenn das AI-Kit
funktioniert, sonst YOLO als Fallback. Beim Start steht in der Konsole, welcher
Detector aktiv ist.

### Netzwerk-Zugriff

`host` bindet per Default auf `0.0.0.0`, der Server ist also unter
`http://<pi-ip>:7995` aus dem lokalen Netz erreichbar (Pi-IP: `hostname -I`).
Das ist für `/stream` nötig, wenn das Audio-Team auf einem anderen Rechner
läuft. Nur lokal binden: `VISUAL_HOST=127.0.0.1 python server.py`.

### Detector erzwingen

| Effekt | Linux / macOS | Windows (PowerShell) |
|---|---|---|
| Auto: Hailo, sonst YOLO | `python server.py` | `python server.py` |
| Nur Hailo (fail wenn weg) | `VISUAL_DETECTOR=hailo python server.py` | `$env:VISUAL_DETECTOR="hailo"; python server.py` |
| Nur YOLO (Webcam) | `VISUAL_DETECTOR=yolo python server.py` | `$env:VISUAL_DETECTOR="yolo"; python server.py` |

## 3. HTTP-API

Base URL: `http://127.0.0.1:7995` (oder `http://<pi-ip>:7995`).

### `POST /track/start`
```http
POST /track/start
Content-Type: application/json

{"name": "cell phone"}
```
→ `{"status": "running", "name": "cell phone"}`

`name` muss ein **gültiges COCO-Label** sein. Das Audio-Team mappt natürliche
Sprache → COCO; wir nehmen den Wert 1:1. Idempotent: gleicher Name = no-op,
anderer Name stoppt das alte Tracking und startet neu.

### `GET /track/latest`
Aggregiertes Ergebnis aus dem Sliding Window. Drei Formen:
```json
{"status": "idle"}

{"status": "running", "name": "cell phone", "found": false,
 "confidence": 0.0, "x": null, "y": null, "w": null, "h": null}

{"status": "running", "name": "cell phone", "found": true,
 "confidence": 0.87, "x": 0.51, "y": 0.48, "w": 0.18, "h": 0.32}
```
Alle Koordinaten normiert auf 0.0–1.0 (Bruchteile des Bildes, keine Pixel).

### `POST /track/stop`
→ `{"status": "stopped", "was_running": true}` (idempotent)

### `GET /health`
→ `{"status": "ok", "detector": "hailo", "ready": true}`

`detector` ist `"hailo"`, `"yolo"` oder `"none"`. `ready=true`, sobald ein
Detector geladen ist — `ready=false` heißt, ein `/track/start` würde noch
fehlschlagen (Server fährt noch hoch).

### `GET /stream`
MJPEG-Live-Stream mit Boxen. Details: Abschnitt 10.

### `GET /`
Browser-Dashboard zum Selbsttesten (Live-Bild + Start/Stop).

## 4. Integration in den Controller

### Option A: `visual_client.py` direkt nutzen (empfohlen)

```python
from visual_client import VisualClient
import time

with VisualClient(base_url="http://127.0.0.1:7995") as visual:
    if not visual.ready():
        raise RuntimeError("Visual-Server nicht bereit")
    visual.start("cell phone")
    while controller_state == "searching":
        r = visual.latest()
        if r["status"] == "running" and r["found"]:
            handle_found(r["x"], r["y"], r["w"], r["h"], r["confidence"])
            break
        time.sleep(0.1)
```

### Option B: Roh-HTTP via `curl`

```bash
curl -X POST http://127.0.0.1:7995/track/start \
     -H "Content-Type: application/json" -d '{"name": "cell phone"}'
curl http://127.0.0.1:7995/track/latest
curl -X POST http://127.0.0.1:7995/track/stop
```

> Tipp: `http://127.0.0.1:7995/docs` im Browser öffnen — die FastAPI-Oberfläche
> lässt alle Endpoints per Klick ausführen.

## 5. Polling-Verhalten

- **Empfohlene Rate: 100 ms.** Schneller bringt nichts, weil das Window erst
  alle paar hundert ms ein neues aggregiertes Ergebnis liefert.
- **`found=true` ist stabil:** mind. 5 von 8 Frames im Fenster müssen das Objekt
  erkannt haben. Das filtert Jitter raus.
- **Stale-Guard:** kommt seit `stale_after_seconds` (Default 1.5s) kein neuer
  Frame, meldet `/track/latest` `found=false` — kein eingefrorener alter Treffer.

## 6. Typische Probleme

| Symptom | Vermutliche Ursache |
|---|---|
| `httpx.ConnectError` | Server nicht gestartet, falscher Host/Port |
| Connection refused von außen | mit `VISUAL_HOST=0.0.0.0` starten (ist Default) |
| `found` wird nie `true` | falsches Label (`"smartphone"` statt `"cell phone"`), Objekt nicht im Bild, oder `confidence_min` zu hoch |
| `/health` zeigt `detector: yolo` obwohl Hailo erwartet | Hailo-Init schlug fehl, Fallback griff. Logs checken |
| `address already in use` beim Start | alter Prozess hält den Port: `fuser -k 7995/tcp`, dann neu starten |
| `No module named 'hailo_apps...'` | Server ohne aktivierte hailo-apps-Umgebung gestartet → erst `source setup_env.sh` |

## 7. Konfiguration

Alle Parameter in `config.py`. Drei Ebenen: Defaults < `config.yaml` < Env.
Aktive Werte: `python config.py`.

| Feld | Default | Env |
|---|---|---|
| `host` | `0.0.0.0` | `VISUAL_HOST` |
| `port` | `7995` | `VISUAL_PORT` |
| `detector_mode` | `""` | `VISUAL_DETECTOR` |
| `confidence_min` | `0.5` | `VISION_CONFIDENCE_MIN` |
| `window_size` | `8` | `VISION_WINDOW_SIZE` |
| `min_hits_in_window` | `5` | `VISION_MIN_HITS_IN_WINDOW` |
| `camera_index` | `0` | `VISION_CAMERA_INDEX` |
| `model_path` | `yolov8n.pt` | `VISION_MODEL_PATH` |
| `hailo_input` | `rpi` | `VISION_HAILO_INPUT` |
| `hailo_hef_path` | `""` | `VISION_HAILO_HEF_PATH` |
| `stop_timeout_seconds` | `5.0` | `VISION_STOP_TIMEOUT_SECONDS` |
| `stale_after_seconds` | `1.5` | `VISION_STALE_AFTER_SECONDS` |
| `stream_jpeg_quality` | `80` | `VISION_STREAM_JPEG_QUALITY` |
| `stream_fps` | `15` | `VISION_STREAM_FPS` |
| `stream_max_width` | `640` | `VISION_STREAM_MAX_WIDTH` |

## 10. Bildübertragung: `GET /stream`

MJPEG-Live-Stream des Kamerabilds mit eingezeichneten Bounding-Boxen, Labels und
Confidence. Für das Audio-Team.

### Verhalten
- Boxen/Bewegung nur bei aktivem Tracking (`POST /track/start`). Ohne Tracking
  ein graues Platzhalterbild — die Verbindung bleibt offen.
- Der Stream öffnet **keine eigene Kamera**: er liefert die Frames aus, die der
  laufende Detector ohnehin produziert (eine Kamera, ein Detector, zwei Ausgänge).
- Frames werden serverseitig auf `stream_max_width` verkleinert und auf
  `stream_fps` gedrosselt — für einen flüssigen, latenzarmen Live-View.

### Einbindung im Browser
```html
<img src="http://<pi-ip>:7995/stream">
```

### Einbindung in Tkinter (Audio-Team)
Tkinter rendert MJPEG nicht nativ — der Multipart-Stream muss in einem
Hintergrund-Thread geparst werden. Fertige Vorlage: `tkinter_stream_example.py`
(braucht dort `pillow` und `httpx`):
```bash
python tkinter_stream_example.py http://<pi-ip>:7995
```

Der Stream funktioniert mit Hailo **und** YOLO.

## 11. Bekannte offene Punkte

- **Team-übergreifende Config-Datei** (alle Modul-Ports an einer Stelle): in
  Diskussion. Aktuell nur Visual.

Bei Fragen: Slack `#team-visual` oder direkt Christian.