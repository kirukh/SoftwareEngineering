# **Team Interfaces/ Controller**

**Allgemein**

Die Aufgabe des Interfaces/ Controller Teams besteht darin, eine einheitliche Schnittstelle bereitzustellen. Damit die Kommunikation zwischen den einzelnen Systemkomponenten sichergestellt werden kann. Wir sind dafür verantwortlich Befehle zu empfangen und diese an die richtigen Komponenten weiterzuleiten.


**1. Teamaufgabe**

- Schnittstellenentwicklung: Sicherstellung der Kommunikation mit den anderen Systemen (Visuell, Audio, Navigation)
- Befehlsweiterleitung: Weitergabe der Befehle an entsprechende Komponenten
- Steuerung: Controller gibt Team Navigation Drehbewegung

**2. User Stories**

- Als User möchte ich, dass korrekt auf Befehle von Audio und Kamera reagiert wird
- Als User möchte ich, dass eine Rückmeldung zurückgegeben wird bei korrekter Ausführung
- Als User möchte ich, dass alle ankommende Informationen an die richtigen Komponenten weitergeleitet werden

**3. Funktionale Anforderungen**

- zuverlässige Kommunikation zwischen den Komponenten
- Befehle müssen richtig weitergeleitet werden

![](Interfaces/image.png)


**4. Sprintziele**

- Sprint1: Grundlagen Kommunikation (erste einfache Befehle weiterleiten, Datentypen)
- Sprint2: Befehlslogik (Mapping definieren)
- Sprint3: Entwurf in Python umsetzen
- Sprint4: Stabilität (fehlerarm, zuverlässig)