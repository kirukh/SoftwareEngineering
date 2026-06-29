# Warum der Gateway? (Wie die Teams am Roboter zusammenhängen)

Kurze Erklärung für alle, warum wir die Anbindung **so** gemacht haben – und warum
das für diesen Roboter die sinnvollste Art ist.

## Das Problem
Wir haben **einen** Arduino, aber **zwei** Teams reden mit ihm:
- **Navi2** steuert die Antriebs-Motoren (Stepper)
- **Laser** steuert die Servos (Pan/Tilt)

Und hier der Haken: ein serieller Port (USB zum Arduino) kann immer nur von **EINEM**
Programm gleichzeitig geöffnet werden. Wenn Navi2 und Laser beide direkt `serial.Serial(...)`
machen, knallt's – einer kriegt den Port, der andere fliegt raus.

## Die Lösung: ein Gateway
Ein kleiner Service (`ArduinoGateway`) ist der **einzige**, der den Serial-Port hält.
Alle anderen reden nicht mehr direkt mit dem Arduino, sondern schicken ihren Befehl
per HTTP an den Gateway:
- `POST /drive`  -> für Navi2 (Motor), wartet auf `DONE`
- `POST /laser`  -> für Laser (Servo)

```
 Navi2  ─┐
         ├─►  Gateway (hält als Einziger den Serial-Port)  ─►  Arduino
 Laser  ─┘
```

Auf dem Arduino läuft eine **gemeinsame Firmware** (`combined_firmware.ino`), die
Motor-Befehle UND Servo-Befehle versteht.

## Warum das die beste Art für uns ist
1. **Kein Port-Konflikt mehr** – das eigentliche Problem ist sauber gelöst.
2. **Abwärtskompatibel** – ist `ARDUINO_GATEWAY_URL` nicht gesetzt, läuft jedes Modul
   wie vorher (direkt Serial / Simulation). Niemand muss Angst haben, dass was kaputtgeht.
3. **Jeder kann allein testen** – ohne Arduino läuft alles in Simulation weiter.
4. **Eine einzige Stelle redet mit der Hardware** – wenn was klemmt, schaut man nur an
   einer Stelle (Gateway-Log), nicht in 3 verschiedenen Modulen.
5. **Erweiterbar** – kommt noch ein Aktor dazu, gibt's einfach einen neuen Endpoint.

## Was das für jedes Team heißt (eine Zeile)
> Statt direkt auf den Serial-Port zu schreiben: einfach an den Gateway posten,
> gesteuert über die Env-Variable `ARDUINO_GATEWAY_URL`.

Details pro Team stehen in `fuer_Navi2.md`, `fuer_Interfaces.md`, `fuer_Visual.md`.
Starten lässt sich die ganze Kette auf dem Pi mit `start_integrated.sh`,
stoppen mit `stop_all.sh`.

Bei Fragen: Laser-Gruppe (Yusuf). ✌️
