# Team Audio

## Übersicht

Die Aufgabe des Audioteams ist es eine Spracheingabe zu ermöglichen und aus dieser Keywords rauszufiltern. Diese werden als Steuerungsbefehle für den Roboter im Controller interpretiert.

## 1. Teamaufgabe

* Spracheingabe:      Aufnahme einer Spracheingabe
* Spracherkennung:    Erkennung der gesprochenen Worte
* Textinterpretation: Umwandlung der gesprochenen Worte zu Text
* Befehlserkennung:   Erkennung von Keywords und an Controller weitergeben

## 2. User Stories

* Als User möchte ich einen Button haben, mit welchen ich die Spracheingabe starten und stoppen kann.
* Als User möchte ich eine visuelle Rückmeldung erhalten, wie meine Sprache interpretiert wurde.
* Als User möchte ich das der Roboter anschließend meinen Befehl ausführt.

## 3. Funktionale Anforderungen

* Um die Teamaufgabe zu erfüllen, muss ein Mikrofonzugriff gewährleistet sein. 
* Die Spracheingabe von Speach-to-Text umwandelt und daraus die Command words rausgefiltert werden.


## 4. Technische Details

* Sprache zu Text über vosk Model - Gewünschtes Modell bei # https://alphacephei.com/vosk/models herunterladen und in audio_speech_recognizer die Variable Model Path abändern

* Commands Objects aktuell statisch eingebaut aufgrund der Liste Unterstützer Objekte von https://github.com/ultralytics/ultralytics/blob/main/ultralytics/cfg/datasets/coco.yaml 26.04.2026 

* Inteface von Microphone an Controlle über FastAPI /speech route
Übergabedata data = {"raw_string": "text"}

* Übergabe an Interface Team durch aufruf der Funktion start_robot(command_data) mit command_data = {'command_build': True, 'command': 'search', 'item': 'cell phone'} falls command_build oder abbruch bei False



