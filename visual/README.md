# Visual Team — README

Objekterkennung über Kamera + KI auf dem Raspberry Pi 5 + Hailo-8.
Stellt dem Controller eine HTTP-API bereit, die kontinuierlich Tracking-Ergebnisse
liefert ("Dauerfeuer"). Controller pollt das aktuelle aggregierte Ergebnis.
Zusätzlich gibt es einen MJPEG-Live-Stream (`GET /stream`) mit eingezeichneten
Bounding-Boxen, den das Audio-Team in seine Oberfläche einbetten kann.

**Quick Start für Controller-Team:** siehe [`instruction.md`](instruction.md).
**Lokal testen (ohne Pi):** siehe [`testing.md`](testing.md).

## Architektur

```
                        ┌──────────────────────────────────┐
  Controller            │  Visual-Server (FastAPI :7995)   │
  ─────────             │  ────────────────────            │
  POST /track/start ───▶│  visual.start_tracking()         │
  GET  /track/latest ──▶│  visual.get_latest()             │
  POST /track/stop  ───▶│  visual.stop_tracking()          │
  GET  /health      ───▶│  status + aktiver Detector       │
                        │                                  │
  Audio-Team            │  Hintergrund-Thread:             │
  ─────────             │  Detector.stream() → on_frame ───┼──▶ Sliding Window
  GET  /stream      ───▶│         │                        │    (8 Frames)
                        │         └─ annotierter Frame ────┼──▶ FrameBuffer
                        └──────────────────────────────────┘    (letztes JPEG)
                                       │
                                       ▼
                          ┌─────────────────────────┐
                          │ Auto-Wahl:              │
                          │  1) HailoDetector       │
                          │  2) YoloDetector (Fall.)│
                          └─────────────────────────┘
```

Detector liefert pro Frame ein Roh-Ergebnis. `visual.py` hält ein **Sliding
Window** der letzten N Frames (Default 8) und aggregiert beim Polling: bei
mind. M Treffern (Default 5) → `found=True` mit Mittelwerten von
`confidence`, `x`, `y`, `w`, `h`. Sonst `found=False` mit allen Koordinaten
auf `null`.

Derselbe Detector legt zusätzlich pro Frame das **annotierte Kamerabild**
(Boxen eingezeichnet, JPEG-kodiert) in einen thread-sicheren `FrameBuffer`.
Der `/stream`-Endpoint liest nur aus diesem Puffer — er öffnet keine eigene
Kamera. Ein Detector, eine Kamera, zwei Ausgänge (`/track/latest` + `/stream`).

## Konfiguration

Alle Parameter liegen in `config.py` als `VisualConfig`-Dataclass.

**Drei Ebenen, später hat Vorrang:**
1. Defaults im Code
2. `config.yaml` im Repo-Root (optional, braucht PyYAML)
3. Umgebungsvariablen

Aktive Werte anzeigen:
```bash
python config.py
```

| Feld | Default | Env-Variable | Bedeutung |
|---|---|---|---|
| `host` | `127.0.0.1` | `VISUAL_HOST` | Server-Bind. `0.0.0.0` für externen Zugriff |
| `port` | `7995` | `VISUAL_PORT` | Server-Port (Range 7991–8000) |
| `detector_mode` | `""` (auto) | `VISUAL_DETECTOR` | `"hailo"`, `"yolo"`, oder leer für Auto |
| `confidence_min` | `0.5` | `VISION_CONFIDENCE_MIN` | Mindest-Konfidenz pro Frame |
| `window_size` | `8` | `VISION_WINDOW_SIZE` | Sliding-Window-Größe |
| `min_hits_in_window` | `5` | `VISION_MIN_HITS_IN_WINDOW` | Mindesttreffer für `found=true` |
| `camera_index` | `0` | `VISION_CAMERA_INDEX` | Webcam-Index (nur YOLO) |
| `model_path` | `yolov8n.pt` | `VISION_MODEL_PATH` | YOLO-Modell-Pfad |
| `stop_timeout_seconds` | `5.0` | `VISION_STOP_TIMEOUT_SECONDS` | Wait beim Tracking-Stop |
| `stream_jpeg_quality` | `80` | `VISION_STREAM_JPEG_QUALITY` | JPEG-Qualität für `/stream` (1–100) |
| `stream_fps` | `15` | `VISION_STREAM_FPS` | Max. Frames/s, die `/stream` ausliefert |

**`config.yaml` nutzen:**
```bash
cp config.yaml.example config.yaml
pip install pyyaml          # falls noch nicht da
# edit config.yaml as desired
python server.py
```

## HTTP-API

### `POST /track/start`
```json
Request:  {"name": "cell phone"}
Response: {"status": "running", "name": "cell phone"}
```

### `GET /track/latest`
```json
// Tracking läuft, Objekt erkannt
{"status": "running", "name": "cell phone", "found": true,
 "confidence": 0.87, "x": 0.51, "y": 0.48, "w": 0.18, "h": 0.32}

// Tracking läuft, Objekt nicht (mehr) erkannt
{"status": "running", "name": "cell phone", "found": false,
 "confidence": 0.0, "x": null, "y": null, "w": null, "h": null}

// Kein Tracking aktiv
{"status": "idle"}
```

### `POST /track/stop`
```json
Response: {"status": "stopped", "was_running": true}
```

### `GET /health`
```json
Response: {"status": "ok", "detector": "hailo"}
```
`detector` kann `"hailo"`, `"yolo"` oder `"none"` (vor Prewarm) sein —
hilfreich um zu sehen, ob im Auto-Modus der Fallback gegriffen hat.

### `GET /stream`

MJPEG-Live-Stream der annotierten Kamerabilder (Bounding-Boxen, Labels und
Confidence eingezeichnet). Content-Type `multipart/x-mixed-replace`.

```
http://<pi-ip>:7995/stream
```

Verhalten:
- **Boxen/Bewegung erscheinen nur, wenn Tracking aktiv ist** (`POST /track/start`).
  Ohne aktives Tracking sendet der Stream ein graues Platzhalterbild — die
  Verbindung bleibt offen, reißt also nicht ab.
- Im **Browser** direkt einbettbar: `<img src="http://<pi-ip>:7995/stream">`.
- In **Tkinter** (Audio-Team) ist *kein* natives Rendering möglich — der
  Multipart-Stream muss in einem Hintergrund-Thread selbst geparst werden.
  Fertige Vorlage: [`tkinter_stream_example.py`](tkinter_stream_example.py).

> ⚠️ **Stand des Stream-Features (wichtig):**
> Der `/stream`-Endpoint ist mit dem **YOLO-Detector vollständig getestet**
> (Laptop + Webcam). Der **Hailo-Pfad ist ein Entwurf und noch nicht am Pi
> verifiziert** — der Abgriff des annotierten Frames aus der GStreamer-Pipeline
> hängt am offenen Sprint-Task **T-20**. Läuft der Server unter Hailo, *kann*
> der Stream leer bleiben (graues Platzhalterbild), bis T-20 abgeschlossen ist.
> Das **Tracking** (`/track/*`) ist davon nicht betroffen und läuft mit Hailo
> wie gewohnt.

## Server starten

Linux / macOS:
```bash
# Auto-Detector (Hailo wenn verfügbar, sonst YOLO)
python server.py

# YOLO-Webcam erzwingen (Laptop ohne Hailo)
VISUAL_DETECTOR=yolo python server.py

# Hailo erzwingen (kein Fallback, fail wenn nicht da)
VISUAL_DETECTOR=hailo python server.py

# Netzwerk-Zugriff von anderen Geräten erlauben
VISUAL_HOST=0.0.0.0 python server.py
```

Windows (PowerShell):
```powershell
# Auto-Detector
python server.py

# YOLO-Webcam erzwingen
$env:VISUAL_DETECTOR="yolo"
python server.py

# Hailo erzwingen
$env:VISUAL_DETECTOR="hailo"
python server.py

# Netzwerk-Zugriff von anderen Geräten erlauben
$env:VISUAL_HOST="0.0.0.0"
python server.py
```

Windows (cmd):
```cmd
set VISUAL_DETECTOR=yolo
python server.py
```

> Hinweis Windows: Env-Variablen gelten nur für die aktuelle Terminal-Sitzung.
> In PowerShell `$env:NAME="wert"`, in cmd `set NAME=wert` — nicht verwechseln.

## Fallback-Verhalten

| Konfiguration | Hailo OK | Hailo kaputt |
|---|---|---|
| `detector_mode` leer (Auto) | nutzt Hailo | fällt auf YOLO, Server läuft |
| `detector_mode=hailo` | nutzt Hailo | Server-Start failed |
| `detector_mode=yolo` | nutzt YOLO | nutzt YOLO |

Sprint-Ziel ist "Rollout muss laufen" — der Auto-Modus stellt das sicher.
Wenn ihr explizit Hailo *messen* wollt (z.B. Inferenz-Performance), nutzt den
expliziten Modus, damit ein Fallback nicht stillschweigend passiert.

## Polling-Beispiel (Controller-Seite)

```python
from visual_client import VisualClient
import time

with VisualClient() as visual:
    visual.start("cell phone")  # COCO-Label, vom Audio-Team geliefert
    while controller_running:
        r = visual.latest()
        if r["status"] == "running" and r["found"]:
            laser.point_to(r["x"], r["y"])
        else:
            laser.idle()
        time.sleep(0.1)
```

> **Wichtig:** `name` muss ein gültiges COCO-Label sein (z.B. `"cell phone"`,
> `"person"`, `"bottle"`), nicht ein Umgangs-Begriff wie `"smartphone"` oder
> `"handy"`. Das Audio-Team mappt Sprache auf COCO-Labels, bevor es zum
> Controller geht. `coco.yaml` ist die geteilte Source-of-Truth.

## Tests

Linux / macOS:
```bash
python config.py                 # aktive Config anzeigen
python test_visual.py            # Fake-Tests, ohne Hardware
python test_visual.py --server   # zusätzlich HTTP-Endpoints (mit Fake)
python live_e2e_test.py          # interaktiver Webcam-Test (YOLO), Default cell phone 30s
```

Windows (PowerShell): identische Befehle, nur `python` ggf. als `py`.
Ausführliche Schritt-für-Schritt-Anleitung zum lokalen Testen (inkl.
`/stream`): siehe [`testing.md`](testing.md).

## Architektur-Entscheidung: HTTP-Server (Sprint 2)

In Sprint 1 hatten wir uns gegen REST entschieden (einmaliger Aufruf, kein
Netzwerk-Layer nötig). In Sprint 2 wurde die Anforderung geändert:
**kontinuierliches Tracking** ("Dauerfeuer") für den Laserpointer.
Optionen waren:

- Eigener OS-Prozess + IPC (Pipe/Socket) — komplex, schwer zu debuggen
- Server-Sent-Events — eine Sonderlocke ggü. den anderen Teams
- **HTTP-Polling — gewählt:** einheitlich mit den anderen Teams, mit `curl`
  trivial zu debuggen, FastAPI + Pydantic passt direkt zu unserem Code

## Anforderungen

| ID | Anforderung |
|---|---|
| FR-01 | Suchanfragen (Objektname) per HTTP vom Controller akzeptieren |
| FR-02 | Bilder von der Kamera-Hardware kontinuierlich erfassen |
| FR-03 | KI-gestützte Bildanalyse pro Frame durchführen |
| FR-04 | Ergebnis mit `name`, `found`, `confidence`, `x`, `y`, `w`, `h` zurückgeben |
| FR-05 | Sliding-Window-Aggregation über N Frames für stabile Ausgabe |
| FR-06 | Auto-Fallback Hailo → YOLO, damit Rollout auch ohne funktionierendes AI Kit läuft |
| FR-07 | Zentrale Konfiguration (`config.py`) mit Env-Override und optional YAML |
| FR-08 | MJPEG-Live-Stream (`/stream`) mit eingezeichneten Boxen — *YOLO getestet, Hailo offen (T-20)* |
| ITF-01 | HTTP-API: `POST /track/start`, `GET /track/latest`, `POST /track/stop` |
| ITF-02 | JSON-Antworten, Pydantic-validiert |
| ITF-03 | `GET /health` liefert aktiven Detector zurück (zum Debuggen) |
| ITF-04 | `GET /stream` liefert MJPEG-Multipart-Stream für die Bildanzeige |