# Anleitung: Visual-Server starten & einbinden

Diese Anleitung erklärt, wie der Visual-Server auf dem Pi gestartet wird und wie ihr (Controller-Team) ihn aus eurem Code anspricht. Sprint-Ziel: Roboter findet ein vom Audio-Team gemeldetes Objekt und liefert die Koordinaten zurück.

Für die **Bildübertragung** (MJPEG-Stream ans Audio-Team) siehe Abschnitt 10.
Für das **lokale Testen ohne Pi** siehe die separate [`testing.md`](testing.md).

## TL;DR für das Controller-Team

```python
from visual_client import VisualClient

with VisualClient(base_url="http://127.0.0.1:7995") as visual:
    visual.start("cell phone")          # COCO-Label vom Audio-Team
    while suche_läuft:
        r = visual.latest()
        if r["status"] == "running" and r["found"]:
            # Treffer! r["x"], r["y"], r["w"], r["h"] sind 0.0–1.0
            controller.handle_found(r)
            break
        time.sleep(0.1)
    # stop() wird automatisch beim Verlassen aufgerufen
```

Das ist alles. Details unten.

---

## 1. Vorbereitung auf dem Pi

### 1.1 Repo + Dependencies

```bash
git clone <unser-repo>
cd visual/
pip install -r requirements.txt
```

Auf dem Pi ist zusätzlich der Hailo-Stack installiert (das macht der Pi-Setup-Script vom Team — fragt Christian, wenn das auf einem frischen Pi gemacht werden muss).

### 1.2 YOLO-Modell laden (Fallback)

Beim ersten YOLO-Start zieht `ultralytics` das `yolov8n.pt`-Modell von sich aus runter. Das dauert kurz, ist aber einmalig. Wenn das Pi später offline laufen soll, einmal vorab online starten.

### 1.3 Config prüfen

```bash
python config.py
```

Zeigt die aktiven Werte. Falls etwas nicht stimmt: über Env-Variablen anpassen oder über eine `config.yaml` (siehe Abschnitt 7).

Linux / macOS — einzelner Lauf auf anderem Port:
```bash
VISUAL_PORT=7996 python server.py
```
Windows (PowerShell):
```powershell
$env:VISUAL_PORT="7996"; python server.py
```

## 2. Server starten

### Standardfall (alles auf dem Pi)

```bash
python server.py
```

Der Server lauscht auf `127.0.0.1:7995` und nimmt automatisch den besten Detector: Hailo, wenn das AI-Kit funktioniert, sonst YOLO als Fallback. Beim Start steht in der Konsole, welcher Detector aktiv ist.

### Andere Geräte sollen zugreifen können

Wenn der Controller (oder das Audio-Team) auf einem anderen Gerät läuft und über Netzwerk auf den Pi zugreift:

Linux / macOS:
```bash
VISUAL_HOST=0.0.0.0 python server.py
```
Windows (PowerShell):
```powershell
$env:VISUAL_HOST="0.0.0.0"; python server.py
```

Damit ist der Server unter `http://<pi-ip>:7995` aus dem lokalen Netzwerk erreichbar. Das ist insbesondere für den `/stream`-Endpoint nötig, wenn das Audio-Team auf einem anderen Rechner läuft (siehe Abschnitt 10).

### Detector erzwingen

| Effekt | Linux / macOS | Windows (PowerShell) |
|---|---|---|
| Auto: Hailo, sonst YOLO | `python server.py` | `python server.py` |
| Nur Hailo (fail wenn weg) | `VISUAL_DETECTOR=hailo python server.py` | `$env:VISUAL_DETECTOR="hailo"; python server.py` |
| Nur YOLO (Webcam) | `VISUAL_DETECTOR=yolo python server.py` | `$env:VISUAL_DETECTOR="yolo"; python server.py` |

> Windows-Hinweis: In PowerShell setzt `$env:NAME="wert"` die Variable für die
> Sitzung. In der klassischen Eingabeaufforderung (cmd) stattdessen
> `set NAME=wert`. Die beiden Syntaxen nicht vermischen.

## 3. HTTP-API

Base URL: `http://127.0.0.1:7995` (oder `http://<pi-ip>:7995` bei `VISUAL_HOST=0.0.0.0`).

### `POST /track/start`

```http
POST /track/start
Content-Type: application/json

{"name": "cell phone"}
```

→ `{"status": "running", "name": "cell phone"}`

**Wichtig:** `name` muss ein **gültiges COCO-Label** sein. Das Audio-Team mappt natürliche Sprache → COCO. Wir nehmen den Wert hier 1:1, ohne weiteres Mapping. Liste der COCO-Klassen: siehe `coco.yaml` (Single Source of Truth zwischen Audio- und Visual-Team).

Idempotent:
- Aufruf mit demselben Namen während Tracking läuft → no-op
- Aufruf mit anderem Namen → altes Tracking wird gestoppt, neues gestartet

### `GET /track/latest`

Aktuelles aggregiertes Ergebnis aus dem Sliding Window der letzten 8 Frames. Status-abhängig drei Formen:

**Kein Tracking aktiv:**
```json
{"status": "idle"}
```

**Tracking läuft, aktuell nichts erkannt:**
```json
{
  "status": "running", "name": "cell phone", "found": false,
  "confidence": 0.0, "x": null, "y": null, "w": null, "h": null
}
```

**Tracking läuft, Treffer:**
```json
{
  "status": "running", "name": "cell phone", "found": true,
  "confidence": 0.87,
  "x": 0.51, "y": 0.48,
  "w": 0.18, "h": 0.32
}
```

Alle Koordinaten sind auf 0.0–1.0 normiert (Bruchteile des Bildes, nicht Pixel).

### `POST /track/stop`

```http
POST /track/stop
```

→ `{"status": "stopped", "was_running": true}`

Idempotent — Aufruf ohne laufendes Tracking gibt `was_running: false`.

### `GET /health`

```http
GET /health
```

→ `{"status": "ok", "detector": "hailo"}`

`detector` ist `"hailo"`, `"yolo"`, oder `"none"` (Server noch nicht geprewarmt). Praktisch, um schnell zu prüfen, ob der Pi gerade Hailo oder Fallback fährt.

### `GET /stream`

MJPEG-Live-Stream mit eingezeichneten Bounding-Boxen. Details und Einbindung: Abschnitt 10.

## 4. Integration in den Controller

### Option A: `visual_client.py` direkt nutzen (empfohlen)

`visual_client.py` ist eine fertige Python-Bibliothek, die alle Endpoints kapselt. Einfach in eurem Repo importieren:

```python
from visual_client import VisualClient
import time

with VisualClient(base_url="http://127.0.0.1:7995") as visual:
    # Healthcheck beim Verbinden:
    if not visual.health():
        raise RuntimeError("Visual-Server nicht erreichbar")

    # Tracking starten (Label vom Audio-Team):
    visual.start("cell phone")

    # Polling-Loop:
    while controller_state == "searching":
        r = visual.latest()
        if r["status"] == "running" and r["found"]:
            handle_found(r["x"], r["y"], r["w"], r["h"], r["confidence"])
            break
        time.sleep(0.1)

    # stop() wird vom Context-Manager automatisch gerufen
```

### Option B: Roh-HTTP via `httpx`/`requests`

Wenn ihr keinen Python-Import wollt, geht alles auch direkt per HTTP. Beispiel mit `curl`:

Linux / macOS:
```bash
curl -X POST http://127.0.0.1:7995/track/start \
     -H "Content-Type: application/json" \
     -d '{"name": "cell phone"}'
curl http://127.0.0.1:7995/track/latest
curl -X POST http://127.0.0.1:7995/track/stop
```

Windows (PowerShell) — `curl` ist in Windows 10/11 enthalten, aber das
JSON-Quoting ist anders (doppelte Anführungszeichen, innere escaped):
```powershell
curl -X POST http://127.0.0.1:7995/track/start -H "Content-Type: application/json" -d "{\"name\": \"cell phone\"}"
curl http://127.0.0.1:7995/track/latest
curl -X POST http://127.0.0.1:7995/track/stop
```

> Tipp: Wenn das Quoting nervt, einfach `http://127.0.0.1:7995/docs` im
> Browser öffnen — die FastAPI-Oberfläche lässt alle Endpoints per Klick
> ausführen, ganz ohne Kommandozeile.

## 5. Polling-Verhalten

- **Empfohlene Polling-Rate: 100 ms.** Schneller bringt nichts, weil das Sliding Window erst alle ~250 ms (Hailo) bzw. ~500 ms (YOLO) ein neues aggregiertes Ergebnis liefert.
- **Polling ist günstig** — nur ein HTTP GET, keine Berechnung serverseitig.
- **`found=True` ist stabil**: Mindestens 5 von 8 Frames im Fenster müssen das Objekt erkannt haben. Das filtert YOLO-/Hailo-Jitter raus.

## 6. Typische Probleme

| Symptom | Vermutliche Ursache |
|---|---|
| `httpx.ConnectError` | Server nicht gestartet, oder falscher Host/Port |
| Connection refused von anderem Gerät | `VISUAL_HOST=127.0.0.1` (Default) blockt von außen. Mit `VISUAL_HOST=0.0.0.0` starten |
| `found` wird nie `true` | (1) Falsches Label — `"smartphone"` statt `"cell phone"`. (2) Objekt nicht im Sichtfeld. (3) Konfidenz zu niedrig — `confidence_min` runtersetzen |
| `/health` zeigt `detector: yolo` obwohl Hailo erwartet | Hailo-Init schlug fehl, Fallback griff. Server-Logs checken |
| Erster `/track/start` braucht 10–30s | Normal: YOLO lädt das Modell. Mit Prewarm beim Server-Start abgedeckt |
| `/stream` zeigt nur ein graues Bild | Kein Tracking aktiv — erst `POST /track/start`. Oder: Server läuft unter Hailo, dort ist der Stream noch nicht verifiziert (T-20, siehe Abschnitt 10) |
| `ModuleNotFoundError: vision_interface` | Datei wurde in `visual_interface.py` umbenannt — Import anpassen |
| Windows: Env-Variable wirkt nicht | In PowerShell `$env:NAME="wert"`, in cmd `set NAME=wert`. Gilt nur für die aktuelle Sitzung |

## 7. Konfiguration

Alle Tuning-Parameter liegen in `config.py`. Drei Ebenen (späteres überschreibt früheres):

1. **Defaults** im Code
2. **`config.yaml`** im Repo-Root (optional)
3. **Env-Variablen**

### Alle Felder

| Feld | Default | Env | Erlaubte Werte |
|---|---|---|---|
| `host` | `127.0.0.1` | `VISUAL_HOST` | IP oder Hostname |
| `port` | `7995` | `VISUAL_PORT` | 7991–8000 |
| `detector_mode` | `""` | `VISUAL_DETECTOR` | `""`, `"hailo"`, `"yolo"` |
| `confidence_min` | `0.5` | `VISION_CONFIDENCE_MIN` | 0.0–1.0 |
| `window_size` | `8` | `VISION_WINDOW_SIZE` | ≥ 1 |
| `min_hits_in_window` | `5` | `VISION_MIN_HITS_IN_WINDOW` | 1–window_size |
| `camera_index` | `0` | `VISION_CAMERA_INDEX` | ≥ 0 |
| `model_path` | `yolov8n.pt` | `VISION_MODEL_PATH` | Pfad |
| `stop_timeout_seconds` | `5.0` | `VISION_STOP_TIMEOUT_SECONDS` | > 0 |
| `stream_jpeg_quality` | `80` | `VISION_STREAM_JPEG_QUALITY` | 1–100 |
| `stream_fps` | `15` | `VISION_STREAM_FPS` | ≥ 1 |

### `config.yaml` verwenden

```bash
cp config.yaml.example config.yaml
pip install pyyaml
nano config.yaml         # eigene Werte eintragen
python config.py         # checken dass die Werte angenommen wurden
python server.py
```

Env-Variablen überschreiben `config.yaml`.

## 8. Lokal testen (ohne Pi)

Kurzfassung: Server mit YOLO + Webcam laufen lassen.

Linux / macOS:
```bash
VISUAL_DETECTOR=yolo python server.py
```
Windows (PowerShell):
```powershell
$env:VISUAL_DETECTOR="yolo"; python server.py
```

Dann gegen `http://127.0.0.1:7995` arbeiten. COCO-Label `"person"` ist am zuverlässigsten zum Probieren. **Ausführliche Schritt-für-Schritt-Anleitung inklusive Stream-Test: siehe [`testing.md`](testing.md).**

## 9. Konfiguration für externen Zugriff

Wenn das Audio-Team auf einem anderen Rechner läuft als der Visual-Server, muss der Server mit `VISUAL_HOST=0.0.0.0` gestartet werden (siehe Abschnitt 2), sonst sind weder API noch `/stream` von außen erreichbar.

## 10. Bildübertragung: `GET /stream`

Der `/stream`-Endpoint liefert einen **MJPEG-Live-Stream** des Kamerabilds mit eingezeichneten Bounding-Boxen, Labels und Confidence-Werten. Gedacht für das Audio-Team, das das Bild in seiner Oberfläche anzeigen will.

### Verhalten

- Der Stream zeigt **nur dann Boxen/Bewegung, wenn Tracking aktiv ist** (`POST /track/start` wurde aufgerufen). Ohne aktives Tracking kommt ein graues Platzhalterbild — die Verbindung bleibt offen.
- Der Stream öffnet **keine eigene Kamera**. Er liefert die Frames aus, die der laufende Detector ohnehin produziert. Tracking und Stream teilen sich denselben Detector und dieselbe Kamera.

### Einbindung im Browser

Trivial — der Browser rendert MJPEG nativ:

```html
<img src="http://<pi-ip>:7995/stream">
```

### Einbindung in Tkinter (Audio-Team)

Tkinter kann MJPEG **nicht** von selbst rendern. Der Multipart-Stream muss in einem Hintergrund-Thread geparst und Frame für Frame in ein `Label` gepusht werden. Eine **fertige, kopierbare Vorlage** liegt im Repo:

```bash
python tkinter_stream_example.py                       # Server auf localhost
python tkinter_stream_example.py http://<pi-ip>:7995   # Server auf dem Pi
```

Das Skript ist kein Teil des Servers, sondern Beispielcode für die Audio-Seite. Es braucht dort zusätzlich `pillow` (`pip install pillow`).

### ⚠️ Aktueller Stand — bitte beachten

Der `/stream`-Endpoint ist mit dem **YOLO-Detector vollständig getestet** (Laptop + Webcam: Stream liefert annotierte Frames, Box folgt dem Objekt).

Der **Hailo-Pfad ist ein Entwurf und noch nicht am echten Pi verifiziert.** Der Abgriff des annotierten Frames aus der Hailo-GStreamer-Pipeline hängt am offenen Sprint-Task **T-20** (Hailo-Live-Test auf dem Pi). Solange T-20 nicht abgeschlossen ist:

- Läuft der Server unter **YOLO** → `/stream` funktioniert.
- Läuft der Server unter **Hailo** → `/stream` *kann* leer bleiben (graues Platzhalterbild). Das **Tracking** (`/track/*`) ist davon **nicht** betroffen und läuft mit Hailo normal.

Ob der Stream für die Demo zwingend über Hailo laufen muss, ist eine offene Abstimmungsfrage (Team + Prof. Jehle). Bis dahin: für eine sichere Stream-Demo den Server mit `VISUAL_DETECTOR=yolo` starten.

## 11. Bekannte offene Punkte

- **Hailo-Stream-Verifikation** (`/stream` unter Hailo) — hängt an T-20, Pi-Live-Test.
- **Team-übergreifende Config-Datei** (alle Modul-Ports an einer Stelle): in Diskussion. Aktuell nur Visual.

Bei Fragen oder Problemen: Slack-Channel `#team-visual` oder direkt Christian.