# Visual Team — README

Objekterkennung über Kamera + KI auf dem Raspberry Pi 5 + Hailo-8.
Stellt dem Controller eine HTTP-API bereit, die kontinuierlich Tracking-Ergebnisse
liefert ("Dauerfeuer"); der Controller pollt das aktuelle aggregierte Ergebnis.
Zusätzlich gibt es einen MJPEG-Live-Stream (`GET /stream`) mit eingezeichneten
Bounding-Boxen, den das Audio-Team in seine Oberfläche einbetten kann, sowie ein
einfaches Browser-Dashboard (`GET /`) zum Selbsttest.

**Quick Start für das Controller-Team:** siehe [`Anleitung.md`](Anleitung.md).
**Lokal testen (ohne Pi):** siehe [`TESTING.md`](TESTING.md).

## Architektur

```
                        ┌──────────────────────────────────┐
  Controller            │  Visual-Server (FastAPI :7995)   │
  ─────────             │  ────────────────────            │
  POST /track/start ───▶│  visual.start_tracking()         │
  GET  /track/latest ──▶│  visual.get_latest()             │
  POST /track/stop  ───▶│  visual.stop_tracking()          │
  GET  /health      ───▶│  status + Detector + ready       │
                        │                                  │
  Audio-Team            │  Hintergrund-Thread:             │
  GET  /stream      ───▶│  Detector.stream() → on_frame ───┼──▶ Sliding Window
                        │         │                        │    (8 Frames)
  Browser (du)          │         └─ annotierter Frame ────┼──▶ FrameBuffer
  GET  /            ───▶│                                  │    (letztes Bild)
                        └──────────────────────────────────┘
                                       │
                                       ▼
                          ┌─────────────────────────┐
                          │ Auto-Wahl:              │
                          │  1) HailoDetector       │
                          │  2) YoloDetector (Fall.)│
                          └─────────────────────────┘
```

Der Detector liefert pro Frame ein Roh-Ergebnis. `visual.py` hält ein **Sliding
Window** der letzten N Frames (Default 8) und aggregiert beim Polling: bei
mind. M Treffern (Default 5) → `found=True` mit Mittelwerten von
`confidence`, `x`, `y`, `w`, `h`, sonst `found=False`. Liefert der Detector
seit `stale_after_seconds` keinen Frame mehr (Pipeline hängt), wird das Window
als veraltet behandelt und `found=False` gemeldet — kein eingefrorener Treffer.

Derselbe Detector legt zusätzlich pro Frame das **annotierte Kamerabild** in
einen thread-sicheren `FrameBuffer`. `/stream` liest nur aus diesem Puffer und
öffnet keine eigene Kamera. Ein Detector, eine Kamera, zwei Ausgänge.

## Konfiguration

Alle Parameter liegen in `config.py` als `VisualConfig`-Dataclass.
Drei Ebenen, später hat Vorrang: Defaults im Code < `config.yaml` < Env-Variablen.

Aktive Werte anzeigen:
```bash
python config.py
```

| Feld | Default | Env-Variable | Bedeutung |
|---|---|---|---|
| `host` | `0.0.0.0` | `VISUAL_HOST` | Server-Bind (`0.0.0.0` = im Netz erreichbar) |
| `port` | `7995` | `VISUAL_PORT` | Server-Port (Range 7991–8000) |
| `detector_mode` | `""` (auto) | `VISUAL_DETECTOR` | `"hailo"`, `"yolo"` oder leer für Auto |
| `confidence_min` | `0.5` | `VISION_CONFIDENCE_MIN` | Mindest-Konfidenz pro Frame |
| `window_size` | `8` | `VISION_WINDOW_SIZE` | Sliding-Window-Größe |
| `min_hits_in_window` | `5` | `VISION_MIN_HITS_IN_WINDOW` | Mindesttreffer für `found=true` |
| `camera_index` | `0` | `VISION_CAMERA_INDEX` | Webcam-Index (nur YOLO) |
| `model_path` | `yolov8n.pt` | `VISION_MODEL_PATH` | YOLO-Modell-Pfad |
| `hailo_input` | `rpi` | `VISION_HAILO_INPUT` | Hailo-Eingabequelle: `rpi`, `usb`, `/dev/videoX` |
| `hailo_hef_path` | `""` | `VISION_HAILO_HEF_PATH` | HEF-Pfad (leer = Default-HEF der Pipeline) |
| `stop_timeout_seconds` | `5.0` | `VISION_STOP_TIMEOUT_SECONDS` | Wait beim Tracking-Stop |
| `stale_after_seconds` | `1.5` | `VISION_STALE_AFTER_SECONDS` | Window gilt ohne neuen Frame als veraltet |
| `stream_jpeg_quality` | `80` | `VISION_STREAM_JPEG_QUALITY` | JPEG-Qualität für `/stream` (1–100) |
| `stream_fps` | `15` | `VISION_STREAM_FPS` | Max. Frames/s, die `/stream` ausliefert |
| `stream_max_width` | `640` | `VISION_STREAM_MAX_WIDTH` | Stream-Frames vor dem Encoding verkleinern (0 = aus) |

## HTTP-API

### `POST /track/start`
```json
Request:  {"name": "cell phone"}
Response: {"status": "running", "name": "cell phone"}
```
`name` muss ein gültiges COCO-Label sein (das Audio-Team mappt Sprache → COCO).

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
Alle Koordinaten normiert auf 0.0–1.0.

### `POST /track/stop`
```json
Response: {"status": "stopped", "was_running": true}
```

### `GET /health`
```json
Response: {"status": "ok", "detector": "hailo", "ready": true}
```
`detector` ist `"hailo"`, `"yolo"` oder `"none"`. `ready` ist `true`, sobald ein
Detector geladen ist — der Check, den der Controller beim Hochfahren nutzen sollte.

### `GET /stream`
MJPEG-Live-Stream der annotierten Kamerabilder, Content-Type
`multipart/x-mixed-replace`. Im Browser direkt einbettbar:
```
<img src="http://<pi-ip>:7995/stream">
```
Zeigt nur dann Boxen, wenn Tracking aktiv ist; sonst ein graues Platzhalterbild.
Für Tkinter (Audio-Team) siehe [`tkinter_stream_example.py`](tkinter_stream_example.py).

### `GET /`
Browser-Dashboard zum Selbsttest: Live-Stream plus Start/Stop-Buttons, ohne
Kommandozeile. Praktisch auf dem Pi über `http://<pi-ip>:7995/`.

## Server starten

```bash
# Auto-Detector (Hailo wenn verfügbar, sonst YOLO)
python server.py

# YOLO-Webcam erzwingen (Laptop ohne Hailo)
VISUAL_DETECTOR=yolo python server.py

# Hailo erzwingen (kein Fallback, fail wenn nicht da)
VISUAL_DETECTOR=hailo python server.py
```
Windows (PowerShell): `$env:VISUAL_DETECTOR="yolo"; python server.py`.

> Auf dem Pi den Server aus der aktivierten hailo-apps-Umgebung starten
> (`source setup_env.sh`), sonst werden die Hailo-/GStreamer-Bindings nicht
> gefunden.

## Fallback-Verhalten

| Konfiguration | Hailo OK | Hailo kaputt |
|---|---|---|
| `detector_mode` leer (Auto) | nutzt Hailo | fällt auf YOLO, Server läuft |
| `detector_mode=hailo` | nutzt Hailo | Server-Start failed (hart) |
| `detector_mode=yolo` | nutzt YOLO | nutzt YOLO |

## Polling-Beispiel (Controller-Seite)

```python
from visual_client import VisualClient
import time

with VisualClient() as visual:                 # default: http://127.0.0.1:7995
    visual.start("cell phone")                  # COCO-Label vom Audio-Team
    while controller_running:
        r = visual.latest()
        if r["status"] == "running" and r["found"]:
            laser.point_to(r["x"], r["y"])      # auch r["w"], r["h"]
        else:
            laser.idle()
        time.sleep(0.1)
    # stop() wird vom Context-Manager automatisch gerufen
```

## Tests

```bash
python config.py                 # aktive Config anzeigen
python test_visual.py            # Fake-Tests, ohne Hardware
python test_visual.py --server   # zusätzlich HTTP-Endpoints (mit Fake)
python live_e2e_test.py          # interaktiver Webcam-Test (YOLO)
```

## Anforderungen

| ID | Anforderung |
|---|---|
| FR-01 | Suchanfragen (Objektname) per HTTP vom Controller akzeptieren |
| FR-02 | Bilder von der Kamera kontinuierlich erfassen |
| FR-03 | KI-gestützte Bildanalyse pro Frame |
| FR-04 | Ergebnis mit `name`, `found`, `confidence`, `x`, `y`, `w`, `h` |
| FR-05 | Sliding-Window-Aggregation für stabile Ausgabe |
| FR-06 | Auto-Fallback Hailo → YOLO |
| FR-07 | Zentrale Konfiguration (`config.py`) mit Env-Override und optional YAML |
| FR-08 | MJPEG-Live-Stream (`/stream`) mit Boxen — Hailo und YOLO |
| ITF-01 | HTTP-API: `POST /track/start`, `GET /track/latest`, `POST /track/stop` |
| ITF-02 | JSON-Antworten, Pydantic-validiert |
| ITF-03 | `GET /health` liefert aktiven Detector und `ready` |
| ITF-04 | `GET /stream` liefert MJPEG-Multipart-Stream |