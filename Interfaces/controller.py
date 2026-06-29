from fastapi import FastAPI
from pydantic import BaseModel
from fastapi import BackgroundTasks
import requests
import os
import time

# Verzögerung (Sekunden), bevor der Roboter nach dem /start-Befehl loslegt.
# Gibt der Person Zeit, das Handy wegzulegen / aus dem Bild zu gehen, bevor die
# Suche startet (z.B. fürs Video). Per Env STARTUP_DELAY_SECONDS anpassbar.
STARTUP_DELAY_SECONDS = float(os.environ.get("STARTUP_DELAY_SECONDS", "3"))

# Wenn True (Default): das Tracking beim Fund NICHT stoppen, damit das Kamerabild
# (/stream) live weiterläuft — praktisch fürs Beobachten/Live-Test. Auf "0" setzen,
# um wie früher beim Fund zu stoppen. Die Kamera unterstützt Live-Switch, ein
# Weiterlaufen ist also kein Leak.
KEEP_CAMERA_LIVE = os.environ.get("KEEP_CAMERA_LIVE", "1") != "0"

""" AUDIO """

""" VISUAL """
VISUAL_SERVER_URL = "http://127.0.0.1:7995"

""" NAVIGATION """

import sys
from pathlib import Path
# sys.path.append(r'C:\Users\GSchlief\Downloads\ss2026_se_groupa') # static route
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from Navigation_2.ImplementationCode import model
from Navigation_2.ImplementationCode import Navigation
from Navigation_2.ImplementationCode import HardwareConfig

""" LASER """
LASERURL = "http://localhost:8004/laser"

""" UTILITY / TESTING """
import random
import httpx

app = FastAPI()

class CommandDaten(BaseModel):
    command: str
    item: str
    command_build: bool

""" Lists to keep record of the dicts that the bot bases its actions on.
    audio -> data_init, visual -> data_visual """
class core_log():
    def __init__(self):
        self.data_init = []
        self.data_visual = []
        self.full_circle_counter = 0    #alternative end-condition of work loop

    def read_data_init(self):
        #print(f"log_read_int: ", self.data_init)       #DEBUG
        return self.data_init

    def write_data_init(self, data):
        self.data_init.append(data)       #DEBUG

    def read_data_visual(self):
        #print(f"log_read_vis: ", self.data_visual)     #DEBUG
        return self.data_visual

    def write_data_visual(self, data):
        self.data_visual.append(data)     #DEBUG


def idle(core_log, command_dict):
    """ waiting for command via audio input """
    # command_dict = kommt_von_irgendwoher
    """ saving the parsed data from audio """
    core_log.write_data_init(command_dict)

    """ start visual server """
    """ wait for bootup, give item to visual server """

    if command_dict["command"] == "search":
        return "SCANNING"
    elif command_dict["command"] == "drehen":
        return "MOVING"
    else:
        """ currently only search is a valid command, otherwise append 'elif:' as needed """
        return "FINISH"

def scanning(log, command_dict):
    """ waiting for results from visual, saves them, return depends on found/ not found """
    """ ask visual: what happens when target only seen whilst moving"""
    """ anaylse 1 'package', then decide """
    #findings_dict = (call to visualserver, give me the 1 latest dict)

    """ Item not yet sent to visual server """

    try:
        with httpx.Client() as client:
            # 1. Status prüfen, ob der Visual Server bereit ist oder schon sucht
            try:
                status_response = client.get(f"{VISUAL_SERVER_URL}/track/latest", timeout=2.0)
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    current_status = status_data.get("status")

                    if current_status == "idle":
                        item_name = command_dict.get("item", "unknown")
                        print(f"Visual Server ist idle. Starte Suche nach: {item_name}")
                        client.post(f"{VISUAL_SERVER_URL}/track/start", json={"name": item_name}, timeout=2.0)

                        return "SCANNING"
                    
                    elif current_status == "starting":
                        print("Visual Server ist am starten... Warten...")
                        return "SCANNING"
                    
                    elif current_status == "ready":
                        print("Visual Server ist ready. Lese Daten aus...")
                        pass
                else:
                    print(f"Konnte Status nicht prüfen, Server antwortete mit: {status_response.status_code}")
                    return "MOVING"
            except Exception as status_err:
                print(f"Fehler bei der Statusabfrage/Start des Visual Servers: {status_err}")
                return "MOVING"


            # Scannign starten
            response = client.get(f"{VISUAL_SERVER_URL}/track/latest")
            
            if response.status_code == 200:
                data = response.json()
                
                findings_dict = {
                    "item": data.get("name"),
                    "found": data.get("found", False),
                    "confidence": data.get("confidence", 0.0),
                    "coord_mid": [data.get("x"), data.get("y")],
                    "height": data.get("h"),
                    "width": data.get("w")
                }
                
                log.write_data_visual(findings_dict)
                print(f"Scanning log: {log.read_data_visual()[-1]}") 
                
                if findings_dict["found"] is True:
                    # Tracking nur stoppen, wenn die Kamera NICHT live bleiben soll.
                    # Default: live lassen (KEEP_CAMERA_LIVE), damit /stream nach dem
                    # Fund weiterläuft.
                    if not KEEP_CAMERA_LIVE:
                        try:
                            client.post(f"{VISUAL_SERVER_URL}/track/stop")
                        except Exception as stop_err:
                            print(f"Failed to stop tracking on visual server: {stop_err}")
                    return "LASER"
                else:
                    return "MOVING"
                    
            else:
                print(f"Visual server error: {response.status_code}")
                return "MOVING"  

    except Exception as e:
        print(f"Failed to connect to Visual Server: {e}")
        return "MOVING" 

def moving(log, command_dict):
    """ if target not found, initialize movement,
    keeps track of turned degrees to end loop when >360° return "search" """
    increment = HardwareConfig.search_step_angle    #search_step_angle if FOV * 0.5 hardcoded by Navigation
    if command_dict["command"] == "search":
        if log.full_circle_counter * increment >= 360:
            print(f"exit via full_circle_counter")                                                              #DEBUG
            return "FINISH"
        else:
            """ execute_command returns confirmation of execution.
            TODO: add wait for confirm and catch if error """
            default = model.RobotCommand(action = "TURN")
            re = Navigation.execute_command(default)
            print(f"nav_exe_return: ", re)                                                                      #DEBUG
            if re["done"] == True:
                log.full_circle_counter += 1
                return "SCANNING"
            else:
                """ no-brain error catcher """
                return "FINISH" #Branch for error handling

    elif command_dict["command"] == "drehen":
        com = command_dict["item"].split(" ")
        angle = int(com[0])
        if com[1] == "links":
            angle = angle * -1  # Vorzeichen negativ für links-kurve

        turn_def = model.RobotCommand(action= "TURN", angle= angle)
        re = Navigation.execute_command(turn_def)
        print(f"nav_exe_return: ", re)                                                                          #DEBUG
        if re["done"] == True:
            return "FINISH"
        else:
            return "FINISH" #Branch for error handling
    else:
        print("moving aborted, finishing")                                                                      #DEBUG
        return "FINISH" #Branch for error handling



def laser(log):
    datalog = log.read_data_visual()
    if not datalog:
        return "LASER"
    target = datalog[-1].get("coord_mid")
    if not target or len(target) < 2:
        return "LASER"
    payload = {
        "x": float(target[0]),
        "y": float(target[1]),
        "confidence": 1.0
    }
    try:
        response = httpx.post(LASERURL, json=payload, timeout=5.0)
        data = response.json()
    except (httpx.HTTPError, ValueError) as e:
        print(f"laser request failed: {e}")
        return "LASER"
    print(response.status_code, data)
    if response.status_code == 200 and data.get("success") is True:
        return "FINISH"
    return "LASER"

def finish():
    """ stop and cleanup (kill visual), return "DONE" """

    return "DONE"

@app.post("/start")
def start_robot(command: CommandDaten, background_tasks: BackgroundTasks):

    command_dict = command.dict()
    print("Angekommende Audio:")
    print(command_dict) 

    background_tasks.add_task(ablauf, command_dict)

    return {"status": "erhalten"}





def ablauf(command_dict):

    log = core_log()

    # Kurze Verzögerung, damit man nach dem /start-Befehl noch in Position kommt
    # (Handy weglegen / aus dem Bild gehen), bevor der Roboter zu drehen beginnt.
    if STARTUP_DELAY_SECONDS > 0:
        print(f"Warte {STARTUP_DELAY_SECONDS}s vor dem Start...")
        time.sleep(STARTUP_DELAY_SECONDS)

    state = "IDLE"

    while True:
        if state == "IDLE":
            print("Mode: IDLE")
            state = idle(log, command_dict)

        elif state == "SCANNING":
            print("Mode: SCANNING")
            state = scanning(log, command_dict)

        elif state == "MOVING":
            print("Mode: MOVING")
            state = moving(log, command_dict)

        elif state == "LASER":
            print("Mode: LASER")
            state = laser(log)

        elif state == "FINISH":
            print("Mode: FINISH")
            state = finish()

        elif state == "DONE":
            print("Mode: DONE")
            #init = log.read_data_init()
            vis = log.read_data_visual()
            print(f"done_recap ", len(vis))


            #print("done")
            try:
                 requests.post("http://127.0.0.1:7980/audio_antwort", json={"status": "done", "visual_data": vis})
                 print("Audio notified: done")
            except Exception as e:
                 print("Failed to notify audio:", e)

            break




if __name__ == "__main__":

    """ test data """


    command_dict = {"command_build" : True,
                 "command" : "search",
                 "item" : "mobile phone"
                 }
    findings_dict_1 = {"item" : "mobile phone",
                    "found" : True,
                    "confidence" : 0.9,
                    "coord_mid" : [0.45, 0.5],
                    "height" : 0.2,
                    "width" : 0.3
                    }
    findings_dict_2 = {"item" : "mobile phone",
                    "found" : False,
                    "confidence" : 0.0,
                    "coord_mid" : [None, None],
                    "height" : None,
                    "width" : None
                    }


    """ test data """

    ablauf(command_dict)
    print("hi")