"""FastAPI service for the Laserpointer pan/tilt controller."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator, Final

from fastapi import FastAPI, HTTPException
import serial
from serial.tools import list_ports

try:
    from .schemas import LaserRequest
except ImportError:  # Allows `uvicorn main:app` from inside this folder.
    from schemas import LaserRequest

logger = logging.getLogger(__name__)

BAUD_RATE: Final = 57_600  # 115200 corrupts Serial RX on this board once Servo is attached.
SERIAL_TIMEOUT_SECONDS: Final = 0.1
ARDUINO_RESET_DELAY_SECONDS: Final = 2.0
RECONNECT_INTERVAL_SECONDS: Final = 5.0

ARDUINO_USB_IDS: Final = (
    (0x1A86, 0x7523),  # Arduino Uno/Nano clones using the CH340 USB chip.
)

SERVO_X_MIN: Final = 0
SERVO_X_MAX: Final = 180
SERVO_Y_MIN: Final = 0
SERVO_Y_MAX: Final = 90
SERVO_CENTER_X: Final = 90
SERVO_CENTER_Y: Final = 90
DISABLE_COORDINATE: Final = -1.0

# Wenn gesetzt (z.B. "http://127.0.0.1:8005"), gehen Laser-Befehle als HTTP-POST
# an den Arduino-Gateway statt direkt auf den seriellen Port. So teilen sich
# Laserpointer (Servo) und Navi2 (Antrieb) denselben Arduino. Nicht gesetzt =
# unverändertes Direkt-Serial-Verhalten (Abwärtskompatibel).
GATEWAY_URL: Final = os.environ.get("ARDUINO_GATEWAY_URL")

arduino: serial.Serial | None = None

current_laser_status: dict[str, object] = {
    "status": "idle",
    "mode": "simulation",
    "connected_port": None,
    "current_x": 0.0,
    "current_y": 0.0,
    "target_x": 0.0,
    "target_y": 0.0,
    "target_confidence": 0.0,
    "servo_x": SERVO_CENTER_X,
    "servo_y": SERVO_CENTER_Y,
}


def is_hardware_connected() -> bool:
    """Return whether the serial connection is currently usable."""
    return arduino is not None and arduino.is_open


def find_arduino_port() -> str | None:
    """Find a connected Arduino on Windows or Linux."""
    for port in list_ports.comports():
        if (port.vid, port.pid) in ARDUINO_USB_IDS:
            return port.device
    return None


def connect_arduino_if_available() -> str | None:
    """Open the serial connection once hardware is detected."""
    global arduino

    if is_hardware_connected():
        return None

    arduino_port = find_arduino_port()
    if arduino_port is None:
        current_laser_status.update({"mode": "simulation", "connected_port": None})
        return "No Arduino found on USB ports. Operating in simulation mode."

    try:
        arduino = serial.Serial(
            port=arduino_port,
            baudrate=BAUD_RATE,
            timeout=SERIAL_TIMEOUT_SECONDS,
        )
        time.sleep(ARDUINO_RESET_DELAY_SECONDS)
    except (OSError, serial.SerialException) as exc:
        arduino = None
        current_laser_status.update({"mode": "simulation", "connected_port": None})
        return f"Found Arduino on {arduino_port}, but the serial connection failed: {exc}"

    current_laser_status.update({"mode": "hardware", "connected_port": arduino_port})
    logger.info("Connected to Arduino on %s", arduino_port)
    return None


last_connection_warning: str | None = None


async def _reconnect_loop() -> None:
    """Retry the Arduino connection in the background so requests never block on it."""
    global last_connection_warning
    while True:
        if is_hardware_connected():
            last_connection_warning = None
        else:
            last_connection_warning = await asyncio.to_thread(connect_arduino_if_available)
        await asyncio.sleep(RECONNECT_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    global last_connection_warning
    last_connection_warning = await asyncio.to_thread(connect_arduino_if_available)
    task = asyncio.create_task(_reconnect_loop())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="Laserpointer", lifespan=lifespan)


def send_command(command: str) -> bool:
    """Send a command to the Arduino, the gateway, or record that it was simulated."""
    global arduino

    # Gateway-Modus: Laser-Befehl per HTTP an den Arduino-Gateway senden.
    if GATEWAY_URL:
        try:
            import requests
            requests.post(f"{GATEWAY_URL}/laser", json={"command": command}, timeout=5)
            return True
        except Exception:
            logger.exception("Failed to send laser command to gateway")
            return False

    if is_hardware_connected() and arduino is not None:
        try:
            arduino.write(command.encode("ascii"))
            return True
        except (OSError, serial.SerialException):
            logger.exception("Failed to write command to Arduino")
            try:
                arduino.close()
            except (OSError, serial.SerialException):
                logger.debug("Failed to close broken Arduino connection", exc_info=True)
            arduino = None
            current_laser_status.update({"mode": "simulation", "connected_port": None})

    logger.info("Simulated laser command: %s", command.strip())
    return False


# Lazer-Nische: normierte Bildkoordinaten (0..1, Mitte=0.5) werden RELATIV ZUR
# MITTE auf Servo-Winkel abgebildet, skaliert mit dem Sichtfeld (FOV) der Kamera
# – NICHT linear über die vollen 0..180°. Sonst übersteuert der Servo massiv,
# weil das Kamera-FOV (~70°) viel schmaler als der Servo-Hub (180°) ist.
# Alle Werte per Env tunebar, damit man Richtung/Verstärkung live kalibrieren kann:
#   LASER_PAN_CENTER / LASER_TILT_CENTER : Servo-Winkel, wenn Ziel mittig ist
#   LASER_PAN_FOV_DEG / LASER_TILT_FOV_DEG: wie viele Grad die volle Bildbreite/-höhe abdeckt
#   LASER_PAN_DIR / LASER_TILT_DIR       : +1 oder -1, falls Servo spiegelverkehrt sitzt
PAN_CENTER_DEG: Final = float(os.environ.get("LASER_PAN_CENTER", "90"))
TILT_CENTER_DEG: Final = float(os.environ.get("LASER_TILT_CENTER", "45"))
PAN_FOV_DEG: Final = float(os.environ.get("LASER_PAN_FOV_DEG", "70"))
TILT_FOV_DEG: Final = float(os.environ.get("LASER_TILT_FOV_DEG", "50"))
PAN_DIR: Final = float(os.environ.get("LASER_PAN_DIR", "1"))
TILT_DIR: Final = float(os.environ.get("LASER_TILT_DIR", "1"))


def map_to_servo_angles(x: float, y: float) -> tuple[int, int]:
    """Map normalized coordinates (0..1, center 0.5) to servo angles, relative to
    the configured center and scaled by the camera FOV."""
    angle_x = PAN_CENTER_DEG + PAN_DIR * (x - 0.5) * PAN_FOV_DEG
    angle_y = TILT_CENTER_DEG + TILT_DIR * (y - 0.5) * TILT_FOV_DEG
    angle_x = int(round(min(max(angle_x, SERVO_X_MIN), SERVO_X_MAX)))
    angle_y = int(round(min(max(angle_y, SERVO_Y_MIN), SERVO_Y_MAX)))
    return angle_x, angle_y


def build_servo_command(angle_x: int, angle_y: int) -> str:
    """Build the compact command format parsed by the Arduino sketch."""
    return f"X{angle_x}Y{angle_y}\n"


def is_disable_request(req: LaserRequest) -> bool:
    """Return whether the request asks the laser to switch off."""
    return req.x == DISABLE_COORDINATE and req.y == DISABLE_COORDINATE


def validate_coordinates(req: LaserRequest) -> None:
    """Reject partial disable commands and out-of-range target coordinates."""
    if is_disable_request(req):
        return

    if req.x == DISABLE_COORDINATE or req.y == DISABLE_COORDINATE:
        raise HTTPException(
            status_code=400,
            detail="Use x=-1 and y=-1 together to disable the laser.",
        )

    if not 0.0 <= req.x <= 1.0 or not 0.0 <= req.y <= 1.0:
        raise HTTPException(
            status_code=400,
            detail=(
                "Coordinates must be normalized values from 0 to 1, "
                "or x=-1 and y=-1 to disable the laser."
            ),
        )


@app.get("/")
def root() -> dict[str, object]:
    """Return a small service banner for liveness checks."""
    return {
        "success": True,
        "service": "laserpointer",
        "connected": is_hardware_connected(),
    }


@app.post("/laser")
def laser(req: LaserRequest) -> dict[str, object]:
    """Aim the laser at normalized coordinates or disable it."""
    validate_coordinates(req)
    warning = None if is_hardware_connected() else last_connection_warning

    if is_disable_request(req):
        command = build_servo_command(SERVO_CENTER_X, SERVO_CENTER_Y)
        is_hardware = send_command(command)
        current_laser_status.update(
            {
                "status": "idle",
                "current_x": 0.0,
                "current_y": 0.0,
                "target_x": 0.0,
                "target_y": 0.0,
                "target_confidence": 0.0,
                "servo_x": SERVO_CENTER_X,
                "servo_y": SERVO_CENTER_Y,
            }
        )

        message = "Laser disabled"
        if not is_hardware:
            message += " (simulated)"

        return {
            "success": True,
            "message": message,
            "warning": warning,
            "servo": {"x": SERVO_CENTER_X, "y": SERVO_CENTER_Y},
        }

    angle_x, angle_y = map_to_servo_angles(req.x, req.y)
    command = build_servo_command(angle_x, angle_y)
    # Diagnose: Ziel-Koordinate (0..1, Mitte 0.5) -> berechneter Servo-Winkel.
    # So lässt sich aus dem Log die Kalibrierung (FOV/Richtung/Mitte) prüfen.
    logger.info(
        "LASER AIM: x=%.3f y=%.3f conf=%.2f -> servo X=%d Y=%d (cmd=%s)",
        req.x, req.y, req.confidence, angle_x, angle_y, command.strip(),
    )
    is_hardware = send_command(command)

    current_laser_status.update(
        {
            "status": "targeting",
            "target_x": req.x,
            "target_y": req.y,
            "target_confidence": req.confidence,
            "current_x": req.x,
            "current_y": req.y,
            "servo_x": angle_x,
            "servo_y": angle_y,
        }
    )

    message = f"Laser pointing to X:{angle_x}deg Y:{angle_y}deg"
    if not is_hardware:
        message += " (simulated)"

    return {
        "success": True,
        "message": message,
        "warning": warning,
        "coordinates": {"x": req.x, "y": req.y},
        "servo": {"x": angle_x, "y": angle_y},
    }


@app.get("/laser/health")
def get_laser_health() -> dict[str, object]:
    """Return the latest laser state and hardware connection status."""
    return {
        "status": current_laser_status,
        "arduino_running": is_hardware_connected(),
    }
