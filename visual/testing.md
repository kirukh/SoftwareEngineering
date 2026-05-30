# testing.md — Visual-Modul lokal testen (ohne Pi)

Diese Anleitung beschreibt, wie ihr das Visual-Modul auf einem normalen
Rechner (Laptop/Desktop, Windows oder Linux/macOS) testet — also den
kompletten **YOLO-Pfad**: Server, Tracking, MJPEG-Stream.

Der **Hailo-Pfad** lässt sich nur auf dem Pi testen und ist hier nicht
abgedeckt (siehe `testing.md`, Abschnitt 10, Task T-20).

Befehle sind in zwei Varianten angegeben:
**Linux / macOS** und **Windows (PowerShell)**.

---

## 0. Voraussetzungen

- Eine funktionierende Webcam (YOLO nutzt sie als Bildquelle).
- Python 3 mit `pip`.
- Abhängigkeiten installiert:

```bash
pip install -r requirements.txt
pip install pillow          # nur für das Tkinter-Stream-Beispiel
```

`tkinter` selbst ist im offiziellen Installer von python.org enthalten.
Falls Python aus dem Microsoft Store stammt und `tkinter` fehlt
(`ModuleNotFoundError: tkinter`), die python.org-Installation nutzen.

---

## 1. Config prüfen

```bash
python config.py
```

In der Ausgabe sollten unten die beiden Stream-Felder auftauchen:
`stream_jpeg_quality` und `stream_fps`. Wenn sie da sind, ist die
aktuelle `config.py` korrekt eingespielt.

---

## 2. Server starten (YOLO erzwingen)

**Linux / macOS:**
```bash
VISUAL_DETECTOR=yolo python server.py
```

**Windows (PowerShell):**
```powershell
$env:VISUAL_DETECTOR="yolo"
python server.py
```

**Windows (cmd):**
```cmd
set VISUAL_DETECTOR=yolo
python server.py
```

`VISUAL_DETECTOR=yolo` ist auf dem Laptop wichtig — ohne das würde der
Auto-Modus zuerst Hailo probieren. Beim allerersten Start lädt
`ultralytics` einmalig das Modell `yolov8n.pt` herunter (kurz warten).

Wenn in der Konsole sinngemäß `Bereit. Aktiver Detector: yolo` steht,
läuft der Server auf `127.0.0.1:7995`. Dieses Terminal offen lassen.

---

## 3. Stream im Browser ansehen (schneller Check)

Auch wenn das Audio-Team Tkinter benutzt — für den Test ist der Browser
am schnellsten, weil er MJPEG nativ rendert. Im Browser öffnen:

```
http://127.0.0.1:7995/stream
```

Erwartung: zuerst ein **graues Platzhalterbild**. Das ist korrekt — es
läuft noch kein Tracking. Tab offen lassen.

---

## 4. Tracking starten

In einem **zweiten Terminal**:

**Linux / macOS:**
```bash
curl -X POST http://127.0.0.1:7995/track/start \
     -H "Content-Type: application/json" \
     -d '{"name": "person"}'
```

**Windows (PowerShell):**
```powershell
curl -X POST http://127.0.0.1:7995/track/start -H "Content-Type: application/json" -d "{\"name\": \"person\"}"
```

`"person"` ist das zuverlässigste COCO-Label zum Ausprobieren — einfach
in die Webcam schauen.

> Alternative ohne Kommandozeile: `http://127.0.0.1:7995/docs` im Browser
> öffnen und `track/start` per "Try it out" anklicken. Praktisch unter
> Windows, wenn das curl-Quoting zickt.

Jetzt sollte der Browser-Tab aus Schritt 3 von grau auf Live-Video
umschalten, und sobald du im Bild bist, erscheint eine Box mit `person`
und einem Confidence-Wert, die dir folgt.

Parallel das Tracking-Ergebnis pollen (drittes Terminal oder `/docs`):

```bash
curl http://127.0.0.1:7995/track/latest
```

Erwartung: `found: true` mit `x`/`y`/`w`/`h`, sobald du erkannt wirst.

---

## 5. Tracking stoppen

**Linux / macOS:**
```bash
curl -X POST http://127.0.0.1:7995/track/stop
```

**Windows (PowerShell):**
```powershell
curl -X POST http://127.0.0.1:7995/track/stop
```

Der Browser-Tab fällt zurück auf das graue Platzhalterbild — der Puffer
wird beim Stop geleert, damit kein altes Bild einfriert. Auch das ist
korrektes Verhalten.

---

## 6. Tkinter-Test (der echte Audio-Team-Weg)

Der Browser-Test zeigt, dass der Server läuft. Das Audio-Team hat aber
Tkinter, das MJPEG nicht nativ rendert. Bei laufendem Server, neues
Terminal:

```bash
python tkinter_stream_example.py
```

Es öffnet sich ein Fenster. Läuft Tracking (Schritt 4), erscheint dort
dasselbe Live-Video mit Boxen wie im Browser. Öffnest du das Fenster
vor dem Tracking-Start, zeigt es erst den Platzhalter und schaltet
automatisch auf Video um, sobald `track/start` aufgerufen wird — kein
Neustart von Tkinter nötig.

Genau dieses Skript ist die Vorlage für die Audio-Seite. Läuft es bei
dir, läuft es bei kiru und Schlief auch.

---

## 7. Automatische Tests

```bash
python test_visual.py            # Fake-Tests, ohne Hardware/Kamera
python test_visual.py --server   # zusätzlich HTTP-Endpoints (mit Fake-Detector)
```

Diese Tests brauchen keine Webcam — sie nutzen Fake-Detektoren.

---

## 8. Wenn etwas klemmt

| Symptom | Ursache / Lösung |
|---|---|
| `/stream` bleibt grau, obwohl Tracking läuft | Server-Log prüfen. `Frame-Encoding fehlgeschlagen` → Encoding-Problem. `found` auch in `/track/latest` nie `true` → Kamera sieht dich nicht (Licht, Index) |
| `found` wird nie `true` | Falscher Kamera-Index oder Objekt nicht erkannt. Index ändern (s.u.) |
| `httpx.ConnectError` / `curl: connection refused` | Server läuft nicht oder falscher Port |
| `ModuleNotFoundError: tkinter` | Python aus Microsoft Store ohne tkinter — python.org-Installation nutzen |
| Stream ruckelt / niedrige Bildrate | Normal: YOLOv8n auf CPU ist nicht flüssig. Kein Code-Fehler |

**Kamera-Index ändern**, falls die falsche Kamera genommen wird:

Linux / macOS:
```bash
VISION_CAMERA_INDEX=1 VISUAL_DETECTOR=yolo python server.py
```
Windows (PowerShell):
```powershell
$env:VISION_CAMERA_INDEX="1"; $env:VISUAL_DETECTOR="yolo"; python server.py
```

---

## Erwartungs-Check

- YOLOv8n auf einer Laptop-CPU läuft mit **spürbarer, nicht flüssiger**
  Bildrate. Das ist normal und kein Fehler. Auf dem Pi mit Hailo wäre es
  flüssiger.
- Der **Hailo-Stream** ist mit diesem Setup **nicht** testbar — dafür
  braucht es den Pi und den noch offenen Task T-20.