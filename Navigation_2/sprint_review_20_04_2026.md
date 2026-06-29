# Sprint Review — 20.04.2026

## Sprint-Ziel

Entwicklung eines ersten Konzepts zur Steuerung eines autonomen Roboters, einschließlich Hardware-Recherche, Grundlagen der Motorbewegung und einer ersten technischen Evaluierung auf der Zielplattform.

---

## Zusammenfassung

Dieser Sprint lag der Schwerpunkt auf **Konzeption und Evaluierung**. Das Team legte die grundlegende Systemarchitektur des Roboters fest, wählte Hardware-Komponenten aus und evaluierte diese, und definierte eine erste Version des JSON-Interfaces zwischen Controller und Navigation.

---

## Abgeschlossene Arbeiten

### 1. Systemübersicht

Der Hardware-Stack des Roboters wurde festgelegt:

| Komponente | Details |
|---|---|
| Steuereinheit | Raspberry Pi 5 |
| Motortreiber | L298N (oder gleichwertig) |
| Schnittstelle | GPIO |
| Antriebstyp | Differential Drive (2x DC-Motor) |

Die Bewegung entsteht durch das Verhältnis der linken und rechten Radgeschwindigkeiten:

| left_steps | right_steps | Bewegung |
|---|---|---|
| + | + | Gerade vorwärts |
| - | - | Gerade rückwärts |
| + | - | Drehung rechts (auf der Stelle) |
| - | + | Drehung links (auf der Stelle) |
| + | 0 | Kurve rechts |
| 0 | + | Kurve links |
| - | 0 | Rückwärtskurve (rechts) |
| 0 | - | Rückwärtskurve (links) |
| 0 | 0 | Stop |

### 2. Systemarchitektur

```
Controller → Navigation → GPIO → Motortreiber → Motoren → Bewegung
```

### 3. JSON-Interface (Controller ↔ Navigation) — v1

**Eingabe (Controller → Navigation):**
```json
{
  "left_steps": -95,
  "right_steps": 95
}
```

**Ausgabe (Navigation → Controller):**
```json
{
  "done": true,
  "left_steps": -95,
  "right_steps": 95
}
```

---

## Wichtige Entscheidungen

- Raspberry Pi 5 als zentrale Steuereinheit bestätigt.
- Motortreiber-Schicht zwischen Pi und Motoren ist zwingend erforderlich.
- Erstes JSON-Interface verwendet rohe `left_steps` / `right_steps`-Werte.
- Differential Drive als Antriebsmodell bestätigt.

---

## Offene Punkte / Risiken

- Definition von Steps noch nicht finalisiert (Einheit, Auflösung, Skalierung).
- Fehlerfälle im JSON-Interface noch nicht spezifiziert.
- PWM-Geschwindigkeitswerte noch nicht kalibriert.

---

## Ziele für den nächsten Sprint

1. Finalisierung des JSON-Interfaces (inkl. Fehlerfälle und Step-Definition).
2. Implementierung eines Navigation-Prototyps (Befehl empfangen → ausführen → Antwort senden).
3. Implementierung grundlegender GPIO-Funktionen: `GPIO.setmode`, `GPIO.setup`, `forward()`, `stop()` und einfache PWM-Geschwindigkeitsregelung.
