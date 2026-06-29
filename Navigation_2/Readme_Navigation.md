# Navigation Team - README

## Übersicht

Das Navigation-Team ist verantwortlich für die Ausführung von Bewegungsbefehlen des Roboters.  
Es übernimmt keine Entscheidungslogik, sondern führt ausschließlich die vom Controller gesendeten Anweisungen aus und bestätigt deren Abschluss.

---

## Team-Aufgaben

- *Eingabe*: Bewegungsbefehle vom Controller empfangen  
- *Bewegungsausführung*: Rotation um einen gegebenen Winkel durchführen  
- *Fortbewegung*: Vorwärtsbewegung in definierten Schritten ausführen  
- *Stoppen*: Bewegung bei STOP-Befehl sofort beenden  
- *Ausgabe*: Bestätigung nach jeder ausgeführten Aktion an den Controller senden  

---

## Workflow

Methode: execute_command(command: dict) in navigation.py

Prozess:
1. Controller sendet einen Bewegungsbefehl  
2. Navigation empfängt den Befehl  
3. Navigation führt die entsprechende Bewegung aus (TURN, MOVE_FORWARD oder STOP)  
4. Navigation wartet, bis die Bewegung abgeschlossen ist  
5. Navigation sendet { "done": true } an den Controller zurück  
6. Navigation wartet auf den nächsten Befehl  

---

## Funktionale Anforderungen

FR-01: Bewegungsbefehle vom Controller akzeptieren  
FR-02: Rotation um einen gegebenen Winkel ausführen  
FR-03: Vorwärtsbewegung in definierten Schritten ausführen  
FR-04: Einen empfangenen Befehl vollständig ausführen und danach eine Bestätigung senden  
FR-05: Bewegung bei einem STOP-Befehl sofort beenden  

---

## Cross-Team-Integration

ITF-01: Bewegungsbefehle vom Controller empfangen  
ITF-02: Abschlussbestätigung { "done": true } an den Controller zurückgeben  

---

## Schnittstelle zum Controller

Eingabe (vom Controller):

{ "action": "TURN", "value": 15 }  
{ "action": "MOVE_FORWARD", "steps": 3 }  
{ "action": "STOP" }  

Ausgabe (an Controller):

{ "done": true }

---

## Verhaltenslogik

Navigation trifft keine eigenen Entscheidungen.  
Alle Aktionen basieren ausschließlich auf Befehlen des Controllers.

TURN → Rotation um den angegebenen Winkel  
MOVE_FORWARD → Vorwärtsbewegung in diskreten Schritten  
STOP → sofortiges Anhalten  

Nach jeder ausgeführten Aktion wird eine Bestätigung gesendet.

---

## Technische Anmerkung

Navigation übersetzt die vom Controller erhaltenen Befehle in konkrete Motoraktionen zur physischen Bewegung des Roboters.