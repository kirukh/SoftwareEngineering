# TESTING.md — Visual-Modul lokal testen (ohne Pi)

Wie ihr das Visual-Modul auf einem normalen Rechner (Windows oder Linux/macOS)
testet — den kompletten **YOLO-Pfad**: Server, Tracking, MJPEG-Stream, Dashboard.

Der **Hailo-Pfad** läuft nur auf dem Pi (siehe `Anleitung.md`).

## 0. Voraussetzungen

- Funktionierende Webcam (YOLO nutzt sie als Bildquelle).
- Python 3 mit `pip`.
- Abhängigkeiten:
```bash
pip install -r requirements.txt
pip install pillow          # nur fürs Tkinter-Stream-Beispiel
```
Falls `tkinter` fehlt (Python aus dem Microsoft Store): die python.org-Installation nutzen.

## 1. Config prüfen

```bash
python config.py
```
Unten sollten die Stream-Felder auftauchen (`stream_jpeg_quality`, `stream_fps`,
`stream_max_width`) — dann ist die aktuelle `config.py` aktiv.

## 2. Server starten (YOLO erzwingen)

**Linux / macOS:**
```bash
VISUAL_DETECTOR=yolo python server.py
```
**Windows (PowerShell):**
```powershell
$env:VISUAL_DETECTOR="yolo"; python server.py
```

`VISUAL_DETECTOR=yolo` ist auf dem Laptop wichtig, sonst probiert der Auto-Modus
zuerst Hailo. Beim allerersten Start lädt `ultralytics` einmalig `yolov8n.pt`
herunter. Wenn `Bereit. Aktiver Detector: yolo` erscheint, läuft der Server.

## 3. Dashboard im Browser (schnellster Check)

Öffne `http://127.0.0.1:7995/` im Browser. Du siehst den Live-Stream (zunächst
grau, weil kein Tracking läuft) und ein Eingabefeld mit Start/Stop-Buttons. Tippe
`person` ein und klick **Start** — sobald du im Bild bist, erscheint eine Box,
die dir folgt, und der Status zeigt `tracke 'person'`.

Alternativ nur den reinen Stream: `http://127.0.0.1:7995/stream`.

## 4. Tracking per curl (optional)

```bash
curl -X POST http://127.0.0.1:7995/track/start \
     -H "Content-Type: application/json" -d '{"name": "person"}'
curl http://127.0.0.1:7995/track/latest
curl -X POST http://127.0.0.1:7995/track/stop
```
`"person"` ist das zuverlässigste COCO-Label zum Ausprobieren. Erwartung bei
`/track/latest`: `found: true` mit `x`/`y`/`w`/`h`, sobald du erkannt wirst.

## 5. Tkinter-Test (der echte Audio-Team-Weg)

Bei laufendem Server, neues Terminal:
```bash
python tkinter_stream_example.py
```
Es öffnet sich ein Fenster mit demselben Live-Video wie im Browser. Startest du
das Fenster vor dem Tracking, zeigt es erst den Platzhalter und schaltet
automatisch auf Video um, sobald `track/start` aufgerufen wird. Genau dieses
Skript ist die Vorlage für die Audio-Seite.

## 6. Automatische Tests

```bash
python test_visual.py            # Fake-Tests, ohne Hardware/Kamera
python test_visual.py --server   # zusätzlich HTTP-Endpoints (Fake-Detector)
```

## 7. Wenn etwas klemmt

| Symptom | Ursache / Lösung |
|---|---|
| Dashboard bleibt grau, obwohl Tracking läuft | Kamera sieht dich nicht (Licht, Index). `/track/latest` auch nie `found:true`? → `VISION_CAMERA_INDEX` ändern |
| `found` wird nie `true` | falscher Kamera-Index oder Objekt nicht erkannt |
| `connection refused` | Server läuft nicht oder falscher Port |
| `address already in use` | alter Prozess hält den Port: `fuser -k 7995/tcp` (Linux) bzw. Prozess im Task-Manager beenden |
| Stream ruckelt | YOLOv8n auf CPU ist nicht flüssig — normal, kein Code-Fehler. Auf dem Pi mit Hailo ist es flüssig |

**Kamera-Index ändern:**
```bash
VISION_CAMERA_INDEX=1 VISUAL_DETECTOR=yolo python server.py
```