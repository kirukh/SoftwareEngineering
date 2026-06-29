# Für Interfaces 🧠

Hey, bei euch sind's auch nur Kleinigkeiten. Eine Pflicht-Sache, eine optionale.

## 1) Pflicht: `main.py` (der Starter im Hauptordner)
Damit der Gateway mitstartet und alle Unterprozesse wissen, dass sie an ihn posten
sollen, kommt **ganz oben** die Env rein und der Gateway als **erster** Service.

**Oben dazu:**
```python
import os
# Navi2 + Laser teilen sich EINEN Arduino über den Gateway. Diese Variable wird
# an alle Unterprozesse vererbt -> sie posten an den Gateway statt direkt auf Serial.
os.environ.setdefault("ARDUINO_GATEWAY_URL", "http://127.0.0.1:8005")
```

**Und in der `services`-Liste als erster Eintrag (Gateway zuerst, ohne --reload):**
```python
(ROOT / "ArduinoGateway", [sys.executable, "-m", "uvicorn", "gateway:app",
                           "--host", "0.0.0.0", "--port", "8005"]),
```
Wichtig: Gateway **zuerst**, weil er der einzige Besitzer des Serial-Ports ist.
Kein `--reload` für den Gateway (sonst geht der Port doppelt auf).

> Auf dem Pi starten wir alles eh über `ArduinoGateway/start_integrated.sh` –
> da ist das schon drin. Diese main.py-Änderung ist für den normalen Start/lokal.

## 2) Optional: `controller.py` – 3 Sek Wartezeit vor dem Start
Nur fürs Testen/Video praktisch: nach dem `/start` wartet der Roboter kurz, damit
man noch in Position kommt, bevor er losdreht. Könnt ihr auch weglassen.

**Oben:**
```python
import os, time
STARTUP_DELAY_SECONDS = float(os.environ.get("STARTUP_DELAY_SECONDS", "3"))
```
**In `ablauf(command_dict)` direkt vor `state = "IDLE"`:**
```python
    if STARTUP_DELAY_SECONDS > 0:
        print(f"Warte {STARTUP_DELAY_SECONDS}s vor dem Start...")
        time.sleep(STARTUP_DELAY_SECONDS)
```
Per Env `STARTUP_DELAY_SECONDS=0` schaltet ihr's komplett aus.

Fragen? -> Laser-Gruppe (Yusuf). 🙌
