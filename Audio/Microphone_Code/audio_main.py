"""
Einstiegspunkt fuer den Microphone-Client (laeuft auf dem Laptop).

Startet zwei Dinge:
1. einen kleinen FastAPI-Server im Hintergrund-Thread, der Status-Updates
   vom Roboter-Controller per POST /status entgegennimmt
2. die Tkinter-GUI im Hauptthread (mainloop blockiert hier)

Der Server-Thread und die GUI teilen sich denselben StatusState — der GUI-Thread
liest periodisch, der Server-Thread schreibt bei eingehenden Updates.
"""
import threading
import tkinter as tk

import status_server
from audio_gui import App
from status_state import StatusState


if __name__ == "__main__":
    # URL des Roboter-Servers, an den gesprochene Befehle geschickt werden.
    robot_url = "http://192.168.137.82:8011/speech"

    # Gemeinsamer, thread-sicherer Status-Container.
    state = StatusState()

    # FastAPI-Server in einem daemon-Thread starten:
    # daemon=True sorgt dafuer, dass der Server-Thread beim Schliessen der GUI
    # automatisch mitstirbt — kein manuelles Aufraeumen noetig.
    threading.Thread(
        target=status_server.run, args=(state,), daemon=True
    ).start()

    root = tk.Tk()
    app = App(root, robot_url, state)
    root.mainloop()
