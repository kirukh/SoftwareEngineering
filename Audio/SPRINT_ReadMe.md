
# AUDIO TEAM – SPRINT PLAN

---
## Legende: Story Points (SP)

Story Points schätzen den **relativen Aufwand** einer Aufgabe – nicht die Zeit in Stunden.

| SP  | Bedeutung                                                  | Beispiel                                         |
| --- | ---------------------------------------------------------- | ------------------------------------------------ |
| 1   | Sehr geringer Aufwand – schnell erledigt                   | Kurze Recherche, einfache Dokumentation          |
| 2   | Geringer Aufwand – überschaubare Aufgabe                   | Konzept skizzieren, Bibliothek evaluieren        |
| 3   | Mittlerer Aufwand – erfordert mehr Planung oder Abstimmung | Technologie-Entscheidung treffen, API definieren |
| 5   | Hoher Aufwand – komplex oder viele Abhängigkeiten          | Vollständige Feature-Implementierung             |
| 8+  | Sehr hoher Aufwand – sollte aufgeteilt werden              | Zu groß für einen Sprint, Task zerlegen          |

___
## Sprint 1: Erstellung Konzept & Festlegung geplanter Funktionsumfang

**Zeitraum:** KW 15  

### Sprint Goal
Grundlagen klären: Technologien evaluieren, Anforderungen formulieren und gewünschten Funktionsumfang definieren

---

### User Stories

| ID    | Story                                                                                | Akzeptanzkriterium                                 | SP  |
| :---- | ------------------------------------------------------------------------------------ | -------------------------------------------------- | --- |
| US-01 | Als User möchte ich einen Button haben, um die Spracheingabe zu starten und stoppen. | Planung und Konzeption der GUI                     | 2   |
| US-02 | Als System möchte ich gesprochene Sprache in Text umwandeln.                         | Recherche nach geeigneten Bibliotheken und Auswahl | 3   |
| US-03 | Als User möchte ich sehen, wie meine Sprache interpretiert wurde.                    | Konzept für Textanzeige festlegen                  | 1   |

---

### Sprint Backlog

| ID   | Task                                                            | Story        | SP  | Status  |
| ---- | --------------------------------------------------------------- | ------------ | --- | ------- |
| T-01 | Anforderung an Mikrofon Zugriff recherchieren und dokumentieren | US-01        | 2   | ⬜ To Do |
| T-02 | Speech-to-Text Bibliotheken vergleichen und auswählen           | US-02        | 1   | ⬜ To Do |
| T-03 | UI-Konzept für Aufnahme-Button und Textanzeige skizzieren       | US-01, US-03 | 3   | ⬜ To Do |
| T-04 | Textausgabe implementieren                                      | US-03        | 1   | ⬜ To Do |
| T-05 | Testplan für Audio-to-Text erstellen                            | alle         | 1   | ⬜ To Do |

---

### Team-Aufteilung

- Person 1: Recherche Mikrofon-Zugriff & Plattformanforderungen
- Person 2: Evaluation Speech-to-Text Bibliotheken
- Person 3: UI-Konzept & Testplan

---

## Sprint 2: Interface- und API-Planung

**Zeitraum:** KW 16  

### Sprint Goal
Definition einer klaren Schnittstelle zwischen Audio-Team und Controller-Team.

---

### User Stories

| ID | Story | Akzeptanzkriterium | SP |
|----|-------|--------------------|----|
| US-04 | Als Entwickler möchte ich eine klare Schnittstelle definieren. | API ist eindeutig spezifiziert. | 2 |
| US-05 | Als Controller möchte ich Befehle vom Audio-Team erhalten. | Übergabeformat ist definiert. | 2 |

---

### Sprint Backlog

| ID | Task | Story | SP | Status |
|----|------|-------|----|--------|
| T-06 | Schnittstelle definieren  | US-04 | 2 | ⬜ To Do |
| T-07 | Datenformat festlegen (String / Dict) | US-05 | 1 | ⬜ To Do |
| T-08 | Abstimmung mit Controller-Team | US-05 | 1 | ⬜ To Do |

---

### Team-Aufteilung

- Person 1: API Design  
- Person 2: Abstimmung Controller  
- Person 3: Dokumentation  

---

## Sprint 3: Umsetzung & Integration

**Zeitraum:** KW 17  

### Sprint Goal
Eine stabile Pipeline von Spracheingabe zu Textausgabe, die für die Weiterverarbeitung vorbereitet ist.

---

### User Stories

| ID | Story | Akzeptanzkriterium | SP |
|----|-------|--------------------|----|
| US-06 | Als User möchte ich, dass meine Sprache zuverlässig in Text umgewandelt wird. | Sprache wird stabil und korrekt erkannt. | 3 |
| US-07 | Als Audio-Team möchten wir die erzeugten Texte für weitere Verarbeitung bereitstellen. | Text wird in einem klar definierten Format ausgegeben. | 2 |

---

### Sprint Backlog

| ID   | Task                                                | Story | SP  | Status  |
| ---- | --------------------------------------------------- | ----- | --- | ------- |
| T-09 | Mikrofon-Zugriff implementieren                     | US-06 | 2   | ⬜ To Do |
| T-10 | Speech-to-Text integrieren (ausgewählte Bibliothek) | US-06 | 2   | ⬜ To Do |
| T-11 | Ausgabeformat festlegen (z. B. String / JSON)       | US-07 | 1   | ⬜ To Do |
| T-12 | API-Funktion implementieren                         | US-07 | 2   | ⬜ To Do |
| T-13 | Integrationstest intern (Audio -> Text)             | alle  | 1   | ⬜ To Do |

---

### Team-Aufteilung

- Person 1: Mikrofon + Aufnahme 
- Person 2: Speech-to-Text Integration
- Person 3: Ausgabeformat & Testing

---

## Sprint 4: Keyword-Erkennung & Übergabe an Controller

**Zeitraum:** KW 18  

### Sprint Goal
Gesprochener Text wird analysiert, Keywords erkannt und als Befehle an den Controller übergeben.

---

### User Stories

| ID | Story | Akzeptanzkriterium | SP |
|----|-------|--------------------|----|
| US-08 | Als System möchte ich Keywords aus Text erkennen. | Keywords werden korrekt extrahiert. | 3 |
| US-09 | Als User möchte ich sehen, welcher Befehl erkannt wurde. | Erkannter Command wird angezeigt. | 2 |
| US-10 | Als System möchte ich den Befehl an den Controller senden. | Controller erhält Command korrekt. | 3 |

---

### Sprint Backlog

| ID | Task | Story | SP | Status |
|----|------|-------|----|--------|
| T-12 | Keyword-Liste definieren | US-08 | 1 | ⬜ To Do |
| T-13 | Keyword-Erkennung implementieren | US-08 | 2 | ⬜ To Do |
| T-14 | Mapping zu Commands (z. B. "links" → MOVE_LEFT) | US-10 | 2 | ⬜ To Do |
| T-15 | Anzeige des Befehls | US-09 | 1 | ⬜ To Do |
| T-16 | Integrationstest mit Controller-Team | US-10 | 2 | ⬜ To Do |

---

### Team-Aufteilung

- Person 1: Textanalyse  & Keyword Erkennung
- Person 2: Mapping / Commands  
- Person 3: Testing + Integration mit Controller

---