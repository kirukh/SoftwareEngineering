# Sprint Review - Laserpointer

**Teammitglieder:**

- Yusuf Simsekoglu
- Leonhard Loschuetz
- Serkan Sueray

## Sprint Goal

Im aktuellen Sprint wollten wir die Laserpointer-Verantwortung im Gesamtsystem
klären, eine nutzbare HTTP-Schnittstelle bereitstellen und die Ansteuerung der
Pan-/Tilt-Servos für die Controller-Integration vorbereiten.

## Teamaufgabe

Wir sind für die Ausrichtung des Laserpointers auf ein vom Controller
vorgegebenes Ziel verantwortlich.

- Empfang von normalisierten Zielkoordinaten und Konfidenz
- Umrechnung der Koordinaten in Servo-Winkel
- Serielle Übergabe der Servo-Winkel an den Arduino
- Rückmeldung des aktuellen Laserstatus an den Controller
- Simulationsmodus, falls keine Hardware angeschlossen ist

## User Stories

| ID | User Story | Akzeptanzkriterium |
| --- | --- | --- |
| US-01 | Als Controller möchte ich Zielkoordinaten senden, damit der Laser auf ein erkanntes Objekt zeigt. | `POST /laser` nimmt gültige Koordinaten an und gibt berechnete Servo-Winkel zurück. |
| US-02 | Als Teammitglied möchte ich ohne Arduino testen können, damit Integrationstests jederzeit möglich sind. | Ohne Hardware antwortet der Service erfolgreich im Simulationsmodus. |
| US-03 | Als Controller möchte ich den Laser deaktivieren können, wenn kein Ziel aktiv ist. | `x = -1` und `y = -1` setzen den Status auf `idle` und zentrieren die Servos. |
| US-04 | Als Integrator möchte ich den aktuellen Zustand abfragen können. | `GET /laser/health` liefert Status, Modus, Port und letzte Servo-Werte. |

## Funktionale Anforderungen

| ID | Anforderung | Status |
| --- | --- | --- |
| FR-01 | Verarbeitung von eingehenden Zielkoordinaten | Erfüllt |
| FR-02 | Validierung von Wertebereichen und Konfidenz | Erfüllt |
| FR-03 | Mapping von Bildkoordinaten auf Servo-Winkel | Erfüllt |
| FR-04 | Rückmeldung des aktuellen Laserstatus | Erfüllt |
| FR-05 | Fallback auf Simulationsmodus ohne Arduino | Erfüllt |

## Sprint Review

### Erreicht

- Die Rolle des Laserpointer-Teams ist klar von Navigation, Audio und Visual
  abgegrenzt.
- Die aktuelle Schnittstelle besteht aus `GET /`, `POST /laser` und
  `GET /laser/health`.
- Die automatische Arduino-Erkennung und der Simulationsmodus sind umgesetzt.
- Controller-Integration ist möglich, auch wenn die Hardware gerade nicht
  angeschlossen ist.
- Veraltete Rotations- und Navigationsbeschreibungen wurden aus der aktiven
  Dokumentation entfernt.

### Noch offen

- Es gibt noch keine eigene automatisierte Testsuite für den Laserpointer-Ordner.
- Der endgültige mechanische Servo-Bereich kann nach Hardware-Kalibrierung noch
  angepasst werden.
- Ein optionaler Konfidenz-Schwellwert kann später ergänzt werden, falls der
  Controller diese Entscheidung nicht selbst treffen soll.

## Abhängigkeiten zu anderen Teams

- **Controller:** sendet Zielkoordinaten und wertet die Laserpointer-Antwort aus
- **Visual:** liefert erkannte Objektpositionen an den Controller
- **Interface:** kann den Gesamtstatus sichtbar machen
- **Hardware:** stellt Arduino, Servos und Laserhalterung bereit

## Fazit

Das Sprintziel wurde erreicht. Der Laserpointer-Service ist als eigenständiges
FastAPI-Modul lauffähig, besitzt eine klare Controller-Schnittstelle und kann
mit oder ohne Arduino in den Gesamtprozess integriert werden.
