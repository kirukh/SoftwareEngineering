import serial
import time
import math
import os
import logging
from serial.tools import list_ports

#Logging für bessere Debugging
logger = logging.getLogger(__name__)

# Wenn gesetzt (z.B. "http://127.0.0.1:8005"), gehen Antriebsbefehle NICHT mehr
# direkt auf den seriellen Port, sondern als HTTP-POST an den Arduino-Gateway.
# So teilen sich Navi2 (Antrieb) und Laserpointer (Servo) denselben Arduino,
# ohne den seriellen Port gleichzeitig öffnen zu müssen. Nicht gesetzt =
# unverändertes Direkt-Serial-Verhalten (Abwärtskompatibel).
GATEWAY_URL = os.environ.get("ARDUINO_GATEWAY_URL")
# Hardware Konstanten
x_center = 0.5
threshold = 0.05
k = 60
FOV = 60.0
search_step_angle = FOV * 0.5
wheel_base = 0.17
wheel_radius = 0.06
steps_per_rev = 200
arduino = None


def init():
    global arduino
    try:
        ports = list_ports.comports()
        logger.info("Suche nach Arduino...")
        arduino_port = None
        for port in ports:
            logger.info(f"Gefunden: {port.device} - {port.description}")
            desc = port.description.lower()
            if (
                "arduino" in desc
                or "ch340" in desc
                or "usb serial" in desc
            ):
                arduino_port = port.device
                break
        if arduino_port is None:
            logger.error("Kein Arduino gefunden")
            logger.info("Arbeite im SIMULATIONS Modus")
            arduino = None
            return True
        logger.info(f"Verbinde mit {arduino_port}")
        arduino = serial.Serial(
            arduino_port,
            9600,
            timeout=2,
            
        )
        dtr=False,   # ← verhindert automatischen Reset
        rts=False    # ← verhindert automatischen Reset
        time.sleep(0.5)
        arduino.reset_input_buffer()
        arduino.dtr = True   # ← jetzt manuell resetten
        time.sleep(2)        # ← warten bis Arduino bootet und READY schickt
        start = time.time()
        while time.time() - start < 5:
            if arduino.in_waiting:
                line = arduino.readline().decode(errors="ignore").strip()
                logger.info(f"Arduino: {line}")
                if line == "READY":
                    logger.info("ARDUINO READY - Verbindung hergestellt")
                    return True
        logger.warning("Keine READY Antwort vom Arduino")
        return False

    except Exception as e:
        logger.error(f"Verbindungsfehler: {e}")
        logger.info("Arbeite im SIMULATIONS Modus")
        arduino = None
        return True
def send_command(cmd):
    logger.info(f"SENDE BEFEHL: {cmd}")

    # Gateway-Modus: Antriebsbefehl per HTTP an den Arduino-Gateway senden.
    if GATEWAY_URL:
        try:
            import requests
            r = requests.post(f"{GATEWAY_URL}/drive", json={"command": cmd}, timeout=20)
            ok = r.status_code == 200
            logger.info(f"[GATEWAY] {cmd} -> HTTP {r.status_code}")
            return ok
        except Exception as e:
            logger.error(f"[GATEWAY] Fehler beim Senden von '{cmd}': {e}")
            return False

    if arduino is None:
        logger.info(f"[SIMULATION] Befehl ausgeführt: {cmd}")
        logger.info("[SIMULATION] DONE")
        return True
    
    try:
        arduino.write((cmd + "\n").encode())
        logger.debug(f"Gesendet: {cmd}")
        
        start = time.time()
        while time.time() - start < 5:
            if arduino.in_waiting:
                response = arduino.readline().decode(errors='ignore').strip()
                logger.debug(f"Empfangen: {response}")
                
                if response == "DONE":
                    logger.info(f"BEFEHL ERFOLGREICH: {cmd}")  # ← WICHTIG
                    return True
                elif response:
                    logger.debug(f"Arduino Debug: {response}")
        
        logger.error(f"TIMEOUT - Keine DONE Antwort für: {cmd}")
        return False
        
    except Exception as e:
        logger.error(f"Fehler beim Senden: {e}")
        return False
def stop_motors():
    logger.info("STOP Motoren")
    return send_command("STOP")
"""def rotate_with_steps(steps):
    logger.info(f"ROTIERE um {steps} steps")
    return send_command(f"ROTATE:{steps}")"""
def move_forward(steps):
    logger.info(f"FAHRE VORWÄRTS {steps} steps")
    return send_command(f"FORWARD:{steps}")
def move_backward(steps):
    logger.info(f"FAHRE RÜCKWÄRTS {steps} steps")
    return send_command(f"BACKWARD:{steps}")
def rotate_with_angle(winkel):
    logger.info(f"ROTIERE um {winkel} grad")
    return send_command(f"ROTATE:{winkel}")
def motor_1 (steps):
    logger.info(f"MOTOR 1 macht {steps} steps")
    return send_command(f"M1:{steps}")
def motor_2 (steps):
    logger.info(f"MOTOR 2 macht {steps} steps")
    return send_command(f"M2:{steps}")