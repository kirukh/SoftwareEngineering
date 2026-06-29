"""Arduino-Gateway: einziger Besitzer der seriellen Verbindung.

Problem: Navi1 (Laserpointer-Servos) und Navi2 (Antriebs-Stepper) sollen
denselben Arduino Nano teilen. Zwei Python-Prozesse dürfen denselben
seriellen Port aber nicht gleichzeitig öffnen. Dieser Gateway-Service löst
das, indem er als einzige Instanz die serielle Verbindung hält und sie über
HTTP für beide Teams freigibt.

Laserpointer- und Navigation-Service müssen dafür ihren direkten
`serial.Serial(...)`-Zugriff durch einen HTTP-Call an diesen Gateway
ersetzen (siehe README.md in diesem Ordner). Das ist in diesem Entwurf noch
NICHT verdrahtet.

Endpunkte:
    POST /drive   {"command": "F:200"}   Antriebsbefehl, wartet auf "DONE"
    POST /laser   {"command": "X90Y45"}  Laserbefehl, keine Antwort nötig
    GET  /status                         Verbindungsstatus
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator, Final

import serial
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from serial.tools import list_ports

logger = logging.getLogger(__name__)

# 9600: passt zum geflashten combined_firmware.ino (Navi2-Stepper/Gyro + Laser-Servo
# in einem Sketch). Antrieb meldet Zeilen wie "motor1Move: DONE" / "DONE winkel=..."
# / "moveForward: DONE"; der Reader erkennt das Teilwort "DONE" (siehe _reader_loop).
BAUD_RATE: Final = 9_600
SERIAL_TIMEOUT_SECONDS: Final = 0.1
ARDUINO_RESET_DELAY_SECONDS: Final = 2.0
RECONNECT_INTERVAL_SECONDS: Final = 5.0
DRIVE_DONE_TIMEOUT_SECONDS: Final = 15.0

# CH340-USB-IDs der bisher verwendeten Arduino Nano/Uno-Klone.
ARDUINO_USB_IDS: Final = ((0x1A86, 0x7523),)
# Fallback, falls der Klon keine eindeutige USB-ID meldet (kam auf diesem Pi vor).
ARDUINO_FALLBACK_PORTS: Final = ("/dev/ttyUSB0",)

arduino: serial.Serial | None = None
connected_port: str | None = None

write_lock = asyncio.Lock()
pending_drive_done: asyncio.Event = asyncio.Event()


def is_hardware_connected() -> bool:
    return arduino is not None and arduino.is_open


def find_arduino_port() -> str | None:
    for port in list_ports.comports():
        if (port.vid, port.pid) in ARDUINO_USB_IDS:
            return port.device
    # Manche CH340-Klone melden keine passende USB-ID; dann den bekannten
    # Linux-Port nehmen, sofern er existiert.
    import os
    for candidate in ARDUINO_FALLBACK_PORTS:
        if os.path.exists(candidate):
            return candidate
    return None


def connect_if_available() -> None:
    """Einmaliger Verbindungsversuch; lässt den Service sonst in Simulation laufen."""
    global arduino, connected_port

    if is_hardware_connected():
        return

    port = find_arduino_port()
    if port is None:
        connected_port = None
        return

    try:
        arduino = serial.Serial(port=port, baudrate=BAUD_RATE, timeout=SERIAL_TIMEOUT_SECONDS)
        time.sleep(ARDUINO_RESET_DELAY_SECONDS)
    except (OSError, serial.SerialException) as exc:
        logger.warning("Arduino auf %s gefunden, Verbindung fehlgeschlagen: %s", port, exc)
        arduino = None
        connected_port = None
        return

    connected_port = port
    logger.info("Gateway verbunden mit Arduino auf %s", port)


async def _reader_loop() -> None:
    """Liest fortlaufend Zeilen vom Arduino; setzt pending_drive_done bei 'DONE'."""
    while True:
        if not is_hardware_connected():
            await asyncio.sleep(RECONNECT_INTERVAL_SECONDS)
            await asyncio.to_thread(connect_if_available)
            continue

        line = await asyncio.to_thread(arduino.readline)
        text = line.decode(errors="ignore").strip()
        # Die combined_firmware meldet den Abschluss als "motor1Move: DONE",
        # "moveForward: DONE" oder "DONE winkel=..."; daher Teilwort statt Gleichheit.
        if "DONE" in text:
            pending_drive_done.set()
        elif text:
            logger.debug("Arduino: %s", text)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await asyncio.to_thread(connect_if_available)
    task = asyncio.create_task(_reader_loop())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="Arduino Gateway", lifespan=lifespan)


class SerialCommand(BaseModel):
    command: str


@app.get("/status")
def status() -> dict[str, object]:
    return {
        "connected": is_hardware_connected(),
        "port": connected_port,
        "mode": "hardware" if is_hardware_connected() else "simulation",
    }


@app.post("/drive")
async def drive(req: SerialCommand) -> dict[str, object]:
    """Antriebsbefehl für Navi2. Blockiert bis 'DONE' oder Timeout."""
    if not is_hardware_connected():
        logger.info("Simuliert (kein Arduino): %s", req.command)
        return {"ok": True, "simulated": True}

    pending_drive_done.clear()
    async with write_lock:
        arduino.write((req.command + "\n").encode("ascii"))

    try:
        await asyncio.wait_for(pending_drive_done.wait(), timeout=DRIVE_DONE_TIMEOUT_SECONDS)
        return {"ok": True, "simulated": False}
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Kein 'DONE' vom Arduino erhalten.")


@app.post("/laser")
async def laser(req: SerialCommand) -> dict[str, object]:
    """Laserbefehl für Navi1. Keine Antwort, damit Tracking nicht blockiert."""
    if not is_hardware_connected():
        logger.info("Simuliert (kein Arduino): %s", req.command)
        return {"ok": True, "simulated": True}

    async with write_lock:
        arduino.write(req.command.encode("ascii"))
    return {"ok": True, "simulated": False}
