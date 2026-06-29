## Sprint-Ziel

Implementierung und Validierung der vollständigen Hardware-Integrationsschicht: serielle Kommunikation zwischen Python und Arduino, Motorsteuerung über Schrittmotortreiber und End-to-End-Ausführung von Navigationsbefehlen auf dem physischen Roboter.

---

## Zusammenfassung

Dieser Sprint lag der Schwerpunkt auf **Hardware-Inbetriebnahme und Systemintegration**. Die im vorherigen Sprint implementierte Navigationslogik wurde erstmals mit echter Hardware verbunden. Das Team hat serielle Kommunikation, Motortreiber-Konfiguration und Arduino-Sketch-Entwicklung erarbeitet, um eine verifizierte physische Bewegung des Roboters zu erreichen.

Am Ende des Sprints führt der Roboter erfolgreich `SEARCH`-, `TURN`- und `STOP`-Befehle aus, die vom Python-Navigations-Stack empfangen werden — mit korrekter Reaktion beider Schrittmotoren auf berechnete Schrittwerte.

---

## Abgeschlossene Arbeiten

### 1. Serielle Kommunikation (Python ↔ Arduino)

Implementierung eines zuverlässigen seriellen Handshakes in `HardwareConfig.py`:

- Arduino sendet `READY` beim Start
- Alle Befehle sind newline-terminierte Strings (`FORWARD:N`, `ROTATE:N`, `STOP`)
- Port konfiguriert auf 9600 Baud auf `COM3` mit 3 Sekunden Timeout
- `arduino.flushInput()` leert veraltete Pufferdaten nach dem Handshake

```python
arduino = serial.Serial("COM7", 9600, timeout=3)
time.sleep(2) 
ready = arduino.readline().decode().strip()
print(f"Arduino says: {ready}")
arduino.flushInput()
```

---

### 2. Arduino Sketch (`main.cpp`)

Entwicklung und Validierung der Arduino-Firmware mit folgender Struktur:

| Funktion | Beschreibung |
|---|---|
| `moveMotors(dir1, dir2, steps, delay)` | Low-Level-Pulserzeugung für beide Schrittmotortreiber gleichzeitig |
| `moveForward(steps)` | Setzt entgegengesetzte Richtungen für Geradeausfahrt |
| `moveBackward(steps)` | Umkehrung der Vorwärtsfahrt |
| `rotateRobot(steps)` | Gleiche Richtung auf beiden Motoren für Drehung auf der Stelle; Vorzeichen bestimmt links/rechts |
| `enableMotors()` | Setzt EN-Pins auf LOW (aktiv) |
| `stopMotors()` | Setzt EN-Pins auf HIGH (deaktiviert) |

**Pin-Belegung:**

| Signal | Motor 1 | Motor 2 |
|---|---|---|
| STEP | 7 | 3 |
| DIR | 6 | 2 |
| EN | 8 | 4 |
| SLEEP | 9 | gemeinsam |
| RESET | 10 | gemeinsam |

```cpp
void loop() {
  if (!Serial.available()) return;
  command = Serial.readStringUntil('\n');
  command.trim();
  if (command.length() == 0) return;

  enableMotors();

  if (command.startsWith("FORWARD")) {
    int steps = command.substring(command.indexOf(':') + 1).toInt();
    moveForward(steps);
  }
  else if (command.startsWith("ROTATE")) {
    int steps = command.substring(command.indexOf(':') + 1).toInt();
    rotateRobot(steps);
  }
  else if (command == "STOP") {
    stopMotors();
    return;
  }

  stopMotors();
}
```

---

### 3. Migration von Arduino IDE zu PlatformIO

Das Projekt wurde zu PlatformIO (VS Code) migriert für bessere Versionskontroll-Integration und reproduzierbare Builds.

**Konfiguration (`platformio.ini`):**

```ini
[env:nanoatmega328new]
platform = atmelavr
board = nanoatmega328new
framework = arduino
monitor_speed = 115200
upload_port = COM7
```

---

### 4. Navigationsintegration

Die vollständige Befehlspipeline wurde End-to-End validiert:

```
Controller.py
    ↓ {action, x, distance}
Navigation_2.py → execute_command()
    ↓ berechnet Winkel/Schritte
HardwareConfig.py → send_command()
    ↓ serieller Schreibvorgang
Arduino (main.cpp)
    ↓ Pulserzeugung
Schrittmotoren → physische Bewegung
```

**Beispielablauf für `x=0, distance=1.0`:**

1. `compute_error(0)` → Fehler = `-0.5`
2. `is_centered(-0.5)` → False → drehen
3. `compute_angle(-0.5)` → `-30°`
4. `angle_to_steps(-30)` → `-230 Schritte`
5. `rotate(-230)` → `ROTATE:-230` wird an Arduino gesendet
6. Nach `time.sleep(1)`: `distance_to_steps(1.0)` → `531 Schritte`
7. `move_forward(531)` → `FORWARD:531` wird an Arduino gesendet

---

### 5. Hardware-Konstanten (aktuelle Werte)

| Parameter | Wert | Status |
|---|---|---|
| `wheel_base` | `0.17 m` | Gemessen |
| `wheel_radius` | `0.06 m` | Gemessen |
| `steps_per_rev` | `200` | Datenblatt |
| `FOV` | `60.0°` | Platzhalter — Visual Team |
| `threshold` | `0.05` | Platzhalter |
| `k` | `60` | Nicht kalibriert |
| `speedDelay` | `2000 µs` | Funktionierender Wert — muss optimiert werden |

---

## Offene Punkte

- **Treiber-Überhitzung:** Ein Schrittmotortreiber wird deutlich heißer als der andere.
- **`k`-Faktor nicht kalibriert:** Der Proportionalverstärkungsfaktor für die Winkelkorrektur ist auf einen willkürlichen Wert gesetzt. Systematische Hardware-Tests erforderlich.
- **FOV-Wert:** Platzhalter — muss vom Visual Team geliefert und integriert werden.

---

## Ziele für den nächsten Sprint

- `FOV`-Wert vom Visual Team einholen und integrieren
- Kalibrierung von `k` durch Hardware-Tests beginnen
- Logging in `execute_command()` zur Fehlersuche bei Bewegungsgenauigkeit hinzufügen
