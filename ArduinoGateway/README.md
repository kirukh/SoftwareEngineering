# Arduino-Gateway (Entwurf)

## Problem

Laut Vorgabe sollen **Navi1 (Laserpointer)** und **Navi2 (Antrieb/Tekerlek)**
denselben **Arduino Nano** verwenden. Das bringt zwei Konflikte mit dem
aktuellen Aufbau:

1. **Zwei Sketches, ein Arduino.** Es gibt aktuell zwei getrennte `.ino`-Dateien
   (`Navigation_2/ArduinoIDE/Fahr_Befehle.ino` für die Stepper-Motoren,
   `Laserpointer/Arduino/arduino_code.txt` für die Servos). Ein Arduino kann
   nur ein Programm gleichzeitig ausführen.
2. **Zwei Python-Services, ein serieller Port.** Aktuell öffnet sowohl der
   Laserpointer-Service (`Laserpointer/main.py`) als auch potenziell der
   Navigation-Service ihre eigene `serial.Serial(...)`-Verbindung. Ein
   serieller Port kann aber nur von einem Prozess gleichzeitig geöffnet
   werden.

Zusätzliche Anforderung aus dem Use-Case: Sobald das Zielobjekt erkannt
wurde, soll der Roboter sich ihm **nähern (Navi2 fährt)**, während der
**Laser gleichzeitig auf das Objekt gerichtet bleibt (Navi1)**. Antrieb und
Laser müssen also **parallel** Befehle an denselben Arduino senden können,
nicht nur abwechselnd.

## Lösungsidee

```
Navigation-Service ──HTTP──┐
                            ├─→  Arduino-Gateway (einziger Besitzer des seriellen Ports) ──USB──→  Arduino Nano
Laserpointer-Service ─HTTP─┘                                                                         ├─ Stepper ×2 (Antrieb)
                                                                                                       └─ Servo ×2 (Laser)
```

- **Ein gemeinsamer Sketch** (`arduino/combined_arduino.ino`) steuert Stepper
  und Servos im selben Programm. Die `loop()`-Funktion blockiert dabei
  **nicht** während einer Antriebsbewegung (anders als die bisherigen
  Einzel-Sketches), damit Laser-Befehle auch während der Fahrt verarbeitet
  werden können.
- **Ein gemeinsamer Gateway-Service** (`gateway.py`) ist die einzige Instanz,
  die den seriellen Port öffnet. Navigation- und Laserpointer-Service senden
  ihre Befehle stattdessen per HTTP an den Gateway.

## Serielles Protokoll (Arduino ↔ Gateway)

Eine gemeinsame Baudrate: **57600**.

| Bereich | Befehl | Antwort |
| --- | --- | --- |
| Antrieb (Navi2) | `F:<steps>`, `B:<steps>`, `L:<steps>`, `R:<steps>`, `M1:<steps>`, `M2:<steps>`, `STOP` | `DONE` nach Abschluss |
| Laser (Navi1) | `X<angle>`, `Y<angle>` (0–180) | keine Antwort |

Die Befehlspräfixe überschneiden sich nicht (`F/B/L/R/M` vs. `X/Y`), daher
können beide Befehlsarten über dieselbe Leitung gemischt eintreffen, ohne
sich zu verwechseln.

## HTTP-Schnittstelle (Service ↔ Gateway)

| Endpunkt | Zweck | Verhalten |
| --- | --- | --- |
| `POST /drive` `{"command": "F:200"}` | Antriebsbefehl | wartet auf `DONE` (Timeout 15s) |
| `POST /laser` `{"command": "X90Y45"}` | Laserbefehl | sendet sofort, keine Wartezeit |
| `GET /status` | Diagnose | `{"connected", "port", "mode"}` |

`/laser` wartet bewusst nicht auf eine Antwort, damit das Nachführen des
Lasers nicht hinter einem laufenden Antriebsbefehl blockiert.

## Integrationsstand (verdrahtet)

Die Integration ist inzwischen umgesetzt — angepasst an die **tatsächlich
geflashte** Firmware `arduino/combined_firmware.ino` (9600 Baud, gyrogestütztes
`ROTATE`, Befehle `ROTATE:`/`FORWARD:`/`BACKWARD:`/`M1:`/`M2:`/`STOP` + Laser
`X<angle>`/`Y<angle>`). Hinweis: `arduino/combined_arduino.ino` ist der **ältere
Entwurf** (57600, `F:`/`R:`); maßgeblich ist `combined_firmware.ino`.

Umgesetzte Verdrahtung:

1. `Laserpointer/main.py`: `send_command()` postet an `<gateway>/laser`, sobald
   die Umgebungsvariable `ARDUINO_GATEWAY_URL` gesetzt ist (sonst altes
   Direkt-Serial-Verhalten — abwärtskompatibel).
2. `Navigation_2/ImplementationCode/HardwareConfig.py`: `send_command()` postet
   an `<gateway>/drive`, wenn `ARDUINO_GATEWAY_URL` gesetzt ist (sonst unverändert).
3. `gateway.py` nutzt 9600 Baud und erkennt den Abschluss am Teilwort `DONE`
   (Firmware meldet z.B. `motor1Move: DONE`, `DONE winkel=...`).
4. `start_integrated.sh` startet Gateway + Visual + Laser + Controller mit
   gesetztem `ARDUINO_GATEWAY_URL` in der richtigen Reihenfolge.

## Start

Integrierte Pipeline auf dem Pi (Arduino mit `combined_firmware.ino` geflasht):

```bash
bash ArduinoGateway/start_integrated.sh
```

Nur den Gateway (Simulationsmodus ohne Hardware, zum Testen):

```bash
pip install -r ArduinoGateway/requirements.txt
cd ArduinoGateway
python -m uvicorn gateway:app --host 0.0.0.0 --port 8005
```
