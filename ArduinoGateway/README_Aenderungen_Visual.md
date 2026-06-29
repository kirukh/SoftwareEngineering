# Änderungen nach dem Visual-Update (neuer Detector)

Kurz: Nach dem Merge des neuen Visual-Codes lief der Detector auf dem **Pi
(hailo-apps 26.3.0)** nicht – er ist für eine **neuere hailo-apps-API** gebaut.
Wir haben ihn auf dem Pi lauffähig gemacht und zwei kleine Komfort-Sachen ergänzt.
Der Code liegt schon auf **mygit (main)**.

## Probleme & Fixes – `visual/hailo_detector.py` (Commit `b054297`)
Der Pi hat das ältere hailo-apps-Layout. Angepasst:

| Problem | Fix |
|---|---|
| Import schlug fehl (`hailo_app_python` fehlt) → Detector = "none" | Fallback-Import aufs alte Layout (`detection_simple_pipeline` / `GStreamerDetectionSimpleApp`) |
| `signal only works in main thread` (Pipeline setzt SIGINT im Worker-Thread) | SIGINT-Registrierung im Thread abgefangen |
| Callback kam im **Handoff-Stil** `(element, buffer)` statt Pad-Probe → `get_buffer`-Fehler | Callback-Signatur angepasst, Buffer direkt genutzt |
| `HailoBBox` hat kein `x_center()/y_center()` | Mitte aus `xmin/ymin + width/height` berechnet |
| Es lief das **Demo-Video** statt der Kamera | Kameraquelle gesetzt: `--input rpi --use-frame` |
| `/stream` **fror ein** (Queues stauten) | Queues auf `leaky=downstream` gestellt |

## Komfort
- **`Interfaces/controller.py`** (`a94f9b9`): Kamera bleibt nach dem Fund **live**
  (`KEEP_CAMERA_LIVE`), es wird kein `/track/stop` mehr aufgerufen.
- **`ArduinoGateway/start_integrated.sh`** (`ee40ddb`): Kamera startet beim Boot
  **automatisch** (Auto-Tracking), `/stream` liefert sofort ein Bild.

## Ergebnis
Roboter läuft Ende-zu-Ende: suchen → Person erkennen (Hailo) → stoppen → Laser,
mit Live-Kamera. Die 6 Detector-Fixes sind zugleich die Antwort auf das
`TODO(T-30): am echten Pi verifizieren` im neuen Visual-Code.
