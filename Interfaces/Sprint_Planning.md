# Sprint Planning 

## Zeitraum
27.04. – 04.05.

---

# 1. Sprintziel

Ziel des Sprints ist die Festlegung der Controller Architektur und der datenbezogenen Vereinbarung mit jeder Schnittstelle.

---

# 2. Geplante User Stories

### US1
Als Controller möchten wir einheitliche Datentypen definieren, damit alle Module standardisiert miteinander kommunizieren können.

### US2
Als Controller möchten wir eine einfache Zustandslogik entwerfen, damit der Ablauf des Roboters strukturiert gesteuert werden kann.

### US3
Als Controller möchten wir einen ersten Prototypen vom Zustandsautomaten implementieren, in dem alle Module integriert werden.

### US4
Als Controller möchten wir Testdaten und Simulationen verwenden, damit Tests ohne echten Roboter möglich sind.

---

# 3. Geplante Aufgaben

## Definition gemeinsamer Datentypen
Festlegung gemeinsamer Dictionary-Strukturen zwischen den Schnittstellen:

- Audio  Controller
- Visual  Controller
- Controller  Laser 

## Zentrale Controller Architektur
Entwerfen eines Zustandsautomaten
Geplante Zustände:

IDLE  SCANNING  MOVING  LASER  FINISH  DONE

## Controller Grundgerüst implementieren
Implementieren der Zustandsautomaten-Schleife
Anlegen von Stubs

## Datenprotokollierung
Implementieren der Klasse `core_log`zur Debugging-Verfolgung von Audio und Visual-Dicts

## Navigationsintegration
Integrieren von `Navigation_2.execute_command()`
Implementieren der Drehzahllogik 

## Testumgebung 
Testdaten und Simulationen implementieren für isolierte Tests ohne Hardware

