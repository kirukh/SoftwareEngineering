# Für Navi2 (Antrieb) 🚗

Hey Leute, kurz und schmerzlos – ihr müsst nur **eine Datei minimal anpassen**:
`Navigation_2/ImplementationCode/HardwareConfig.py`

## Warum überhaupt?
Motor (ihr) und Laser teilen sich **EINEN** Arduino. Zwei Programme dürfen denselben
seriellen Port aber nicht gleichzeitig aufmachen. Deshalb gibt's jetzt einen kleinen
**Gateway-Service**, der als Einziger den Port hält und ihn per HTTP für alle freigibt.

Heißt für euch: statt direkt auf `serial` zu schreiben, schickt ihr euren Befehl
per HTTP an den Gateway. **Eure Befehle bleiben exakt gleich** (`ROTATE:30`,
`FORWARD:...`, `M1:...` usw.) – nur der Weg dahin ändert sich.

## Das Beste: ihr müsst nichts kaputt machen
Wenn die Umgebungsvariable `ARDUINO_GATEWAY_URL` **nicht** gesetzt ist, läuft alles
**wie bisher** (direkt auf Serial). Also komplett abwärtskompatibel. 👍

## Was ihr ändert (2 kleine Stellen)

**1) Ganz oben dazu:**
```python
import os
GATEWAY_URL = os.environ.get("ARDUINO_GATEWAY_URL")
```

**2) In `send_command(cmd)` ganz am Anfang diesen Block rein:**
```python
def send_command(cmd):
    logger.info(f"SENDE BEFEHL: {cmd}")

    # Gateway-Modus: Antriebsbefehl per HTTP an den Arduino-Gateway senden.
    if GATEWAY_URL:
        try:
            import requests
            r = requests.post(f"{GATEWAY_URL}/drive", json={"command": cmd}, timeout=20)
            logger.info(f"[GATEWAY] {cmd} -> HTTP {r.status_code}")
            return r.status_code == 200
        except Exception as e:
            logger.error(f"[GATEWAY] Fehler beim Senden von '{cmd}': {e}")
            return False

    # ... ab hier euer alter Code (Direkt-Serial / Simulation) unverändert ...
```

Fertig. Der Gateway wartet beim `/drive` brav auf das `DONE` vom Arduino, blockt
also genau wie euer Serial-Code vorher.

Fragen? Meldet euch bei der Laser-Gruppe (Yusuf). 🙌
