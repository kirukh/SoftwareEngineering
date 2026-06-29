"""
Offline-Spracherkennung in Deutsch via Vosk.

Funktionsweise:
- sounddevice oeffnet einen Raw-Input-Stream vom Mikrofon (16 kHz, Mono)
- Jeder Audio-Block wird im Callback in eine Queue gelegt
- Ein eigener Hintergrund-Thread holt die Bloecke aus der Queue und gibt sie
  an den KaldiRecognizer (Vosk) weiter
- Der Recognizer liefert Teilergebnisse beim Sprechen und ein finales Ergebnis
  beim Stoppen — beides wird gesammelt und am Ende als ein String zurueckgegeben

Das Modell muss lokal liegen — Pfad siehe MODEL_PATH unten. Weitere Modelle:
https://alphacephei.com/vosk/models
"""
from vosk import Model, KaldiRecognizer
import queue
import sounddevice as sd
import json
import threading
import os

# Pfad zum Vosk-Modell, relativ zu dieser Datei. Liegt im venv-Verzeichnis,
# damit es nicht versehentlich ins Git eincheckt wird (Modell ist gross).
MODEL_PATH = os.path.join(os.path.dirname(__file__), "vosk-model-small-de-0.15")
samplerate = 16000


class SpeechRecognizer:
    def __init__(self):
        # Queue puffert Audio-Bloecke zwischen Mikrofon-Callback und Verarbeitungs-Thread.
        self.q = queue.Queue()
        self.model = Model(MODEL_PATH)
        self.recognizer = KaldiRecognizer(self.model, samplerate)

        self.stream = None
        self.running = False
        self.thread = None

        # Sammelt alle erkannten Teil-Saetze. Wird beim Start zurueckgesetzt.
        self.full_text = []

    def callback(self, indata, frames, time, status):
        """Wird von sounddevice fuer jeden Audio-Block aufgerufen (eigener Thread!)."""
        if status:
            print(status)
        self.q.put(bytes(indata))

    def _process_audio(self):
        """Laeuft im Hintergrund-Thread: holt Audio aus der Queue und gibt sie an Vosk."""
        while self.running:
            try:
                data = self.q.get(timeout=0.1)
            except queue.Empty:
                continue

            # AcceptWaveform liefert True, wenn ein vollstaendiges Teil-Ergebnis vorliegt.
            if self.recognizer.AcceptWaveform(data):
                result = json.loads(self.recognizer.Result())
                text = result.get("text", "")
                if text:
                    print("You said:", text)
                    self.full_text.append(text)

    def start_listening(self):
        """Mikrofon aktivieren und Verarbeitungs-Thread starten. Idempotent."""
        if self.running:
            return

        self.full_text = []
        self.running = True

        self.stream = sd.RawInputStream(
            samplerate=samplerate,
            blocksize=8000,
            dtype='int16',
            channels=1,
            callback=self.callback
        )
        self.stream.start()

        # daemon=True: Thread stirbt automatisch beim Programmende.
        self.thread = threading.Thread(target=self._process_audio, daemon=True)
        self.thread.start()

        print("Listening started")

    def stop_listening(self):
        """
        Mikrofon stoppen, restliche Audio-Daten finalisieren und das gesamte
        bisher Erkannte als zusammenhaengenden String zurueckgeben.
        """
        if not self.running:
            return ""

        # Signalisiert dem Verarbeitungs-Thread, dass er die Schleife verlassen soll.
        self.running = False

        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        if self.thread:
            self.thread.join()
            self.thread = None

        # FinalResult() liefert den noch nicht abgeschlossenen Resttext.
        final_result = json.loads(self.recognizer.FinalResult())
        final_text = final_result.get("text", "")
        if final_text:
            self.full_text.append(final_text)

        full_sentence = " ".join(self.full_text)

        print("Listening stopped")
        print("Final text:", full_sentence)

        return full_sentence
