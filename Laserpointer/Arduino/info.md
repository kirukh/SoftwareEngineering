# Arduino-Hinweise

Die Datei `arduino_code.txt` enthält den Sketch für die Arduino IDE. Der Sketch
muss auf den Arduino geladen werden, bevor der Laserpointer-Service echte
Hardware ansteuern kann.

## Verbindung

- Baudrate: `115200`
- Pan-/X-Servo: Pin `9`
- Tilt-/Y-Servo: Pin `10`
- Kommandoformat: `X<pan>Y<tilt>`, zum Beispiel `X90Y45`

Der Python-Service erkennt den Arduino automatisch über bekannte USB-IDs. Eine
manuelle Portanpassung in `main.py` ist im Normalfall nicht mehr nötig.

Beim Start von Uvicorn beziehungsweise beim ersten `POST /laser` sollte in den
Logs sichtbar sein, ob der Arduino verbunden wurde oder ob der Service im
Simulationsmodus läuft.
