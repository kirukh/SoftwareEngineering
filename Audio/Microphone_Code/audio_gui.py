"""
Tkinter-Oberflaeche des Microphone-Clients.

Aufbau (von oben nach unten):
- Anleitungstext
- Start/Stop-Buttons fuer die Spracherkennung
- Textfeld mit dem erkannten Rohtext
- Rahmen "Erkannter Befehl" mit Befehl/Objekt und Fehlerzeile
- Rahmen "Roboter-Status" mit der Live-Rueckmeldung des Controllers

Datenfluss beim Druecken von "Stop":
1. SpeechRecognizer liefert den erkannten Text
2. Der Text wird lokal mit parse_command(...) zerlegt → sofortige Anzeige
3. Zusaetzlich wird der Rohtext per POST an den Roboter-Server geschickt
   (rein informativ, Anzeige haengt nicht davon ab)
"""

import os
import sys
import io
import threading
import httpx
from PIL import Image, ImageTk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Shared_Code"))

import requests
import tkinter as tk
from audio_speech_recognizer import SpeechRecognizer
from command_parser import parse_command

STREAM_URL = "http://192.168.137.82:7995/stream" # Raspberry-IP anpassen

class MjpegStreamView:
    def __init__(self, parent, stream_url):
        self.parent = parent
        self.root = parent.winfo_toplevel()
        self.stream_url = stream_url

        self.label = tk.Label(parent, text="Warte auf Kamera...", bg="black", fg="white")
        self.label.pack(fill=tk.BOTH, expand=True)

        self._running = True
        self._latest_jpeg = None
        self._latest_photo = None
        self._jpeg_lock = threading.Lock()

        threading.Thread(target=self._read_stream, daemon=True).start()
        self._refresh_ui()

    def _read_stream(self):
        buffer = b""

        while self._running:
            try:
                with httpx.stream("GET", self.stream_url, timeout=10.0) as resp:
                    resp.raise_for_status()

                    for chunk in resp.iter_bytes():
                        if not self._running:
                            return

                        buffer += chunk

                        while True:
                            start = buffer.find(b"\xff\xd8")
                            end = buffer.find(b"\xff\xd9")

                            if start == -1 or end == -1 or end < start:
                                break

                            jpeg = buffer[start:end + 2]
                            buffer = buffer[end + 2:]

                            with self._jpeg_lock:
                                self._latest_jpeg = jpeg

            except Exception as e:
                print(f"[kamera] Verbindungsfehler: {e}")
                if not self._running:
                    return
                threading.Event().wait(1.0)

    def _refresh_ui(self):
        if not self._running:
            return

        with self._jpeg_lock:
            jpeg = self._latest_jpeg

        if jpeg is not None:
            try:
                img = Image.open(io.BytesIO(jpeg))
                img.thumbnail((640, 360))

                photo = ImageTk.PhotoImage(img)
                self.label.config(image=photo, text="")
                self._latest_photo = photo

            except Exception as e:
                print(f"[kamera] Frame konnte nicht angezeigt werden: {e}")

        self.root.after(33, self._refresh_ui)

    def stop(self):
        self._running = False

class App:
    def __init__(self, root, api_url, state=None):
        """
        root     : Tk-Hauptfenster
        api_url  : URL des Roboter-Servers fuer POST /speech
        state    : gemeinsamer StatusState (optional, fuer Live-Status-Anzeige)
        """
        self.robot_url = api_url
        self.root = root
        self.state = state
        self.root.title("Speech Recorder")
        self.root.geometry("500x700")

        # --- obere Anleitung + Buttons ---
        self.label = tk.Label(root, text="Press Start and speak...\nResult appears after Stop")
        self.label.pack(pady=10)

        button_frame = tk.Frame(root)
        button_frame.pack(pady=5)

        self.start_button = tk.Button(
            button_frame,
            text="Start",
            command=self.start
        )
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = tk.Button(
            button_frame,
            text="Stop",
            command=self.stop
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)

        # Rohtext der Spracherkennung
        self.result_box = tk.Text(root, height=5, width=50)
        self.result_box.pack(padx=10, pady=10)

        # --- Befehlsanzeige (lokal geparst) ---
        tk.Label(root, text="Erkannter Befehl", font=("Helvetica", 11, "bold")).pack(pady=(6, 2))

        self.command_frame = tk.Frame(root, relief="groove", borderwidth=2)
        self.command_frame.pack(padx=10, pady=(0, 10), fill="x")

        tk.Label(self.command_frame, text="Befehl:", anchor="w", width=10).grid(row=0, column=0, sticky="w", padx=8, pady=4)
        self.command_label = tk.Label(self.command_frame, text="-", font=("Helvetica", 11, "bold"), fg="green", anchor="w")
        self.command_label.grid(row=0, column=1, sticky="w")

        tk.Label(self.command_frame, text="Objekt:", anchor="w", width=10).grid(row=1, column=0, sticky="w", padx=8, pady=4)
        self.item_label = tk.Label(self.command_frame, text="-", font=("Helvetica", 11, "bold"), fg="blue", anchor="w")
        self.item_label.grid(row=1, column=1, sticky="w")

        # rote Fehler-/Hinweiszeile (z.B. "Server nicht erreichbar", "Kein Befehl erkannt")
        self.status_label = tk.Label(self.command_frame, text="", fg="red")
        self.status_label.grid(row=2, column=0, columnspan=2, pady=(0, 4))

        # --- Roboter-Status (Live-Updates vom Controller per POST /status) ---
        self.robot_status_frame = tk.LabelFrame(root, text="Roboter-Status", padx=10, pady=5)
        self.robot_status_frame.pack(padx=10, pady=(0, 10), fill="x")
        self.robot_status_label = tk.Label(
            self.robot_status_frame, text="Bereit", font=("Helvetica", 12, "bold")
        )
        self.robot_status_label.pack()

        self.recognizer = SpeechRecognizer()

        # Falls ein StatusState uebergeben wurde: alle 500 ms aus dem State lesen.
        if self.state is not None:
            self._poll_robot_status()

        # --- Kamera-Stream vom Raspberry / Visual-Server ---
        camera_frame = tk.LabelFrame(root, text="Kamera", padx=5, pady=5)
        camera_frame.pack(padx=10, pady=10, fill="both", expand=True)

        self.camera_view = MjpegStreamView(
            camera_frame,
            STREAM_URL
        )

    def start(self):
        """Aufnahme starten — leert das Textfeld und aktiviert das Mikrofon."""
        self.result_box.delete("1.0", tk.END)
        self.recognizer.start_listening()

    def stop(self):
        """
        Aufnahme stoppen, Ergebnis anzeigen und an Roboter-Server senden.

        Reihenfolge ist bewusst so gewaehlt, dass die GUI auch dann sinnvoll
        bleibt, wenn der Server nicht erreichbar ist:
        Rohtext -> lokales Parsing -> Befehl/Objekt -> erst danach POST.
        """
        text = self.recognizer.stop_listening()
        self.result_box.insert(tk.END, text)

        # Lokal parsen, damit Befehl/Objekt unabhaengig vom Server angezeigt werden.
        command_data = parse_command(text)
        self._update_command_box(command_data)

        # POST an den Roboter-Server — Fehler werden erkannt und in der GUI gemeldet.
        try:
            response = requests.post(self.robot_url, json={"raw_string": text}, timeout=3)
            print(response.status_code, "\n", response.json())
        except requests.RequestException as e:
            print("POST an Roboter fehlgeschlagen:", e)
            self.status_label.config(text="Server nicht erreichbar")

    def _update_command_box(self, command_data):
        """Schreibt das Parser-Ergebnis in die Befehlsanzeige."""
        if command_data.get("command_build"):
            self.command_label.config(text=command_data.get("command", "-"))
            self.item_label.config(text=command_data.get("item", "-"))
            self.status_label.config(text="")
        else:
            self.command_label.config(text="-")
            self.item_label.config(text="-")
            self.status_label.config(text="Kein Befehl erkannt")

    def _poll_robot_status(self):
        """
        Liest den aktuellen Roboter-Status aus dem StatusState und aktualisiert
        das Label. Plant sich selbst alle 500 ms erneut ein — root.after() laeuft
        im Tkinter-Hauptthread, daher ist der Zugriff threadsicher.
        """
        s = self.state.get()
        self.robot_status_label.config(text=self._format_robot_status(s))
        self.root.after(500, self._poll_robot_status)

    def _format_robot_status(self, s):
        """Wandelt den State-Dict in einen lesbaren Anzeigetext um."""
        status = s.get("status", "idle")
        item = s.get("item")
        details = s.get("details")
        if status == "idle":
            return "Bereit"
        if status == "searching":
            return f"Suche nach: {item or '?'}"
        if status == "found":
            return f"Ziel gefunden: {item or '?'}"
        if status == "lost":
            return "Ziel verloren"
        if status == "error":
            return f"Fehler: {details or 'unbekannt'}"
        return status
