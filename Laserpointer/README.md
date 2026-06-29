# Laserpointer Team - README

## Übersicht

Das Laserpointer-Team ist für das präzise Ausrichten eines Laserpointers auf
ein vom Controller vorgegebenes Ziel zuständig. Der Service empfängt
normalisierte Bildkoordinaten `(x, y)` und eine Konfidenz, übersetzt die
Koordinaten in Servo-Winkel und sendet ein kompaktes serielles Kommando an
einen Arduino.

Der Service steuert keine Fahrmotoren, verarbeitet keine Kamera- oder
Audiodaten und trifft keine eigene Zielentscheidung. Diese Verantwortung liegt
bei Controller, Visual und den übrigen Teams.

## Aktueller Stand

- FastAPI-Service mit den Endpunkten `GET /`, `POST /laser` und
  `GET /laser/health`
- Automatische Arduino-Erkennung über bekannte USB-IDs
- Simulationsmodus, wenn keine Hardware gefunden wird
- Normalisierte Eingabekoordinaten im Bereich `0.0` bis `1.0`
- Deaktivierung über `x = -1` und `y = -1`
- Statusausgabe inklusive letztem Ziel, Servo-Winkeln und Hardwaremodus

## Start

Vom Repository-Root:

```bash
pip install -r Laserpointer/requirements.txt
uvicorn Laserpointer.main:app --reload --port 8004
```

Alternativ direkt im `Laserpointer`-Ordner:

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8004
```

Interaktive API-Dokumentation: `http://127.0.0.1:8004/docs`

## HTTP-Schnittstelle

### `GET /`

Liveness-Endpunkt ohne Request-Body.

Beispielantwort:

```json
{
  "success": true,
  "service": "laserpointer",
  "connected": false
}
```

### `POST /laser`

Richtet den Laser auf normalisierte Zielkoordinaten aus.

Request:

```json
{
  "x": 0.5,
  "y": 0.8,
  "confidence": 1.0
}
```

Erfolgreiche Antwort im Simulationsmodus:

```json
{
  "success": true,
  "message": "Laser pointing to X:90deg Y:17deg (simulated)",
  "warning": "No Arduino found on USB ports. Operating in simulation mode.",
  "coordinates": {
    "x": 0.5,
    "y": 0.8
  },
  "servo": {
    "x": 90,
    "y": 17
  }
}
```

Deaktivierung:

```json
{
  "x": -1,
  "y": -1,
  "confidence": 1.0
}
```

Der Service sendet dabei `X90Y90` an den Arduino und setzt den Status wieder
auf `idle`.

Beispielantwort:

```json
{
  "success": true,
  "message": "Laser disabled (simulated)",
  "warning": "No Arduino found on USB ports. Operating in simulation mode.",
  "servo": {
    "x": 90,
    "y": 90
  }
}
```

### `GET /laser/health`

Gibt den aktuellen internen Status zurück.

Beispielantwort:

```json
{
  "status": {
    "status": "targeting",
    "mode": "simulation",
    "connected_port": null,
    "current_x": 0.5,
    "current_y": 0.8,
    "target_x": 0.5,
    "target_y": 0.8,
    "target_confidence": 1.0,
    "servo_x": 90,
    "servo_y": 17
  },
  "arduino_running": false
}
```

## Validierung

| Feld | Regel |
| --- | --- |
| `x` | `0.0` bis `1.0`, oder `-1` gemeinsam mit `y = -1` zum Deaktivieren |
| `y` | `0.0` bis `1.0`, oder `-1` gemeinsam mit `x = -1` zum Deaktivieren |
| `confidence` | `0.0` bis `1.0` |

Teilweise Deaktivierungsbefehle wie `x = -1` und `y = 0.4` werden mit HTTP
400 abgelehnt. Der Controller ist aktuell für mögliche Konfidenz-Schwellwerte
zuständig; Laserpointer validiert und speichert die Konfidenz nur für Diagnose
und Integration.

## Servo-Mapping

| Achse | Eingabe | Servo-Bereich |
| --- | --- | --- |
| X / Pan | `0.0` bis `1.0` | `0` bis `180` Grad |
| Y / Tilt | `0.0` bis `1.0` | invertiert auf `90` bis `0` Grad |

Serielle Kommandos haben das Format `X<pan>Y<tilt>`, zum Beispiel `X90Y17`.
Die Baudrate beträgt `57600` (bei `115200` stört die Servo-Bibliothek den
seriellen Empfang auf manchen Uno-Klonen).

## Arduino

Der Arduino-Sketch liegt in `Arduino/arduino_code.txt` und muss mit der
Arduino IDE auf den Arduino geladen werden. Standard-Pins:

| Servo | Pin |
| --- | --- |
| Pan / X | 9 |
| Tilt / Y | 10 |

Beim Start sollte in den Uvicorn-Logs sichtbar sein, ob ein Arduino gefunden
wurde. Ohne Arduino läuft der Service weiter im Simulationsmodus.

## Funktionale Anforderungen

| ID | Anforderung | Status |
| --- | --- | --- |
| FR-01 | Normalisierte Zielkoordinaten vom Controller über `POST /laser` empfangen | Erfüllt |
| FR-02 | Eingaben validieren und ungültige Koordinaten ablehnen | Erfüllt |
| FR-03 | Koordinaten in Servo-Winkel für Pan und Tilt übersetzen | Erfüllt |
| FR-04 | Arduino automatisch erkennen und seriell ansteuern | Erfüllt |
| FR-05 | Simulationsmodus bereitstellen, wenn keine Hardware verfügbar ist | Erfüllt |
| FR-06 | Diagnose über `GET /laser/health` bereitstellen | Erfüllt |

## Qualitätscheck

```bash
python -m compileall Laserpointer
```

Aktuell gibt es im Laserpointer-Ordner keine eigene Testsuite. Für
Integrationstests kann der Controller `POST /laser` und `GET /laser/health`
gegen eine laufende Uvicorn-Instanz aufrufen.
