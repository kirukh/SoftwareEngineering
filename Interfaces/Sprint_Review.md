# Sprint Review 

## Sprint Goal
Aufbau der grundlegenden Kommunikation zwischen Audio-Modul und dem Controller

Dabei sollte Controller: 
- Sprachbefehle vom Audio-Modul empfangen
- eingehende Daten validieren
- erste Datentypen definieren
- einen Befehl weiterverarbeiten

- - - 

## Geplante User Stories 

### US1
Als Controller möchte ich Sprachbefehle vom Audio-Modul empfangen können, damit Benutzer Befehle an den Roboter senden können. 

### US2 
Als Controller möchte ich standardisierte Datentypen definieren, damit alle Module einheitlich kommunizieren können. 

### US3 
Als Controller möchte ich gültige Suchbefehle erkennen und weiterverarbeiten können.

- - - 

## Umgesetzte Aufgaben 

### 1. Datentypen definiert
Erstellung eines einheitlichen Datenmodells mit Pydantic:
```python
class CommandDaten(BaseModel):
	command: str
	item: str
	command_build: bool | None = None

### 2. FastAPI-Schnittstelle für Audio erstellt
Audio-Modul kann Befehle über POST-Request an Controller senden:
@app.post("/audio_command")
def audio_uebergabe(command_daten: CommandDaten):

### 3. Hauptanwendung erstellt
Einbinden der API in die Hauptanwendung
app.mount("/audio", audio_command) 

## Ergebnis des Sprints
Audio -> Controller -> Validierung -> Roboterstart 
=> Aktueller Ablauf

## Probleme 
- noch kein Zugriff auf echten Roboter
- Visual-Modul nocht nicht integriert
- Navigation-Modul noch nicht integriert
- Parser noch einfach 

## Was wurde nicht geschafft? 
- Integration Visual
- Integration Navigation
- Unterstützung weiterer Befehle
- Erweiterung der Entscheidungslogik

## Nächster Sprint
- Audio refinen
- Visual Schnittstelle einbinden
- Entscheidungslogik erweitern
- weitere Befehle unterstützen 

