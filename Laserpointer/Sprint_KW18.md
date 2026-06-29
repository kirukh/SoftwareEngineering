# Sprint-Log - Team Laserpointer

## Punktesystem: Estimation (EST)

| Punkte | Definition | Beispiel |
| --- | --- | --- |
| 1 | Trivial | Kleine Code-Fixes, Tippfehler |
| 2 | Standard | Einfache Logik, neue API-Felder |
| 3 | Komplex | Validierung, neue Endpunkte |
| 5 | Herausfordernd | Hardware-Treiber, mathematische Transformation |
| 8 | Kritisch | Teamübergreifende Integration |

## Sprint 4: Systemintegration und Verifikation

**Zeitraum:** KW 18

**Ziel:** Der Controller kann den Laserpointer-Service über die vereinbarte
HTTP-Schnittstelle steuern.

### User Stories

| ID | User Story | EST | Status |
| --- | --- | --- | --- |
| LP-US-07 | Als Controller möchte ich den Laser über eine stabile API steuern. | 8 | Done |
| LP-US-08 | Als Teammitglied möchte ich klare Statusinformationen für Integrationstests erhalten. | 3 | Done |
| LP-US-09 | Als Teammitglied möchte ich auch ohne Arduino testen können. | 3 | Done |

### Backlog und Status

| ID | Task | Fokus | EST | Status |
| --- | --- | --- | --- | --- |
| T-401 | Integrationstest mit Team Controller | Schnittstellen-Check | 5 | Done |
| T-402 | Datentypen und Wertebereiche festlegen | API-Logik | 2 | Done |
| T-403 | Simulationsmodus ohne Arduino bereitstellen | Entwicklung | 3 | Done |
| T-404 | API-Dokumentation über `/docs` prüfen | Dokumentation | 1 | Done |

### Highlights

1. `POST /laser` akzeptiert normalisierte Koordinaten von `0.0` bis `1.0`.
2. `x = -1` und `y = -1` deaktivieren den Laser und zentrieren die Servos.
3. `GET /laser/health` liefert Status, Modus, Zielwerte und Servo-Winkel.
4. Wenn kein Arduino gefunden wird, läuft der Service im Simulationsmodus weiter.
5. Der Controller kennt Endpunkte, Datentypen und Wertebereiche.

### Zusammenfassung

Die Zusammenarbeit mit dem Controller-Team war erfolgreich. Der Controller ruft
die `/laser`-API korrekt auf, die Koordinatenübergabe funktioniert und der
Laserstatus kann über `/laser/health` geprüft werden. Damit ist der
Laserpointer-Service für die Präsentation und weitere Integration vorbereitet.
