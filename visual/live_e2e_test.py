"""
live_e2e_test.py — Interaktiver Live-Test über die echte HTTP-Schnittstelle.

Was der Test macht:
  1. Startet den FastAPI-Server in einem Hintergrund-Thread
  2. Erzwingt YOLO-Detector mit Webcam (VISUAL_DETECTOR=yolo)
  3. Nutzt VisualClient genau so, wie es der Controller später machen wird
  4. Pollt N Sekunden lang und zeigt dir live, was rauskommt

Aufruf:
    python live_e2e_test.py                      # Default: cell phone, 30s
    python live_e2e_test.py cup 60               # cup, 60 Sekunden
"""
from __future__ import annotations

import os
import sys
import threading
import time

# YOLO erzwingen, BEVOR irgendwas aus visual importiert wird.
os.environ.setdefault("VISUAL_DETECTOR", "yolo")

import uvicorn

import server
from config import CONFIG
from visual_client import VisualClient


BASE_URL = f"http://127.0.0.1:{CONFIG.port}"


def wait_for_server(client: VisualClient, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if client.health():
            return
        time.sleep(0.2)
    raise RuntimeError(f"Server ist nach {timeout}s nicht hochgekommen")


def format_result(r: dict) -> str:
    if r["status"] == "idle":
        return "IDLE"
    if not r.get("found"):
        return "running, kein Treffer"
    return (
        f"FOUND  conf={r['confidence']:.2f}  "
        f"x={r['x']:.2f} y={r['y']:.2f}  "
        f"w={r['w']:.2f} h={r['h']:.2f}"
    )


def run_live_e2e(target: str, duration: float) -> None:
    print(f"\n{'='*60}")
    print(f"  Live-E2E-Test: Tracking auf '{target}', {duration:.0f}s")
    print(f"{'='*60}\n")

    print(f"[1/4] Server wird gestartet auf {BASE_URL}...")
    config = uvicorn.Config(
        server.app, host="127.0.0.1", port=CONFIG.port, log_level="warning",
    )
    threading.Thread(target=uvicorn.Server(config).run, daemon=True).start()

    print("[2/4] Auf Server-Health warten (lädt YOLO-Modell, kann 10-30s dauern)...")
    client = VisualClient(base_url=BASE_URL, timeout=10.0)
    wait_for_server(client, timeout=60.0)
    info = client.health_info() or {}
    print(f"      ✓ Server antwortet, Detector: {info.get('detector', '?')}")

    input(f"\n[3/4] Halte ein '{target}' bereit. ⏎ Enter zum Tracking-Start...")

    with client:
        client.start(target)
        print(f"\n[4/4] Polling für {duration:.0f}s, Strg+C bricht früher ab.\n")

        start = time.monotonic()
        try:
            while time.monotonic() - start < duration:
                r = client.latest()
                t = time.monotonic() - start
                print(f"  [{t:5.1f}s]  {format_result(r)}")
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\n  (abgebrochen)")


if __name__ == "__main__":
    # Default ist das COCO-Label "cell phone" (nicht "smartphone" — siehe
    # https://github.com/ultralytics/ultralytics → COCO-Klassen).
    target = sys.argv[1] if len(sys.argv) > 1 else "cell phone"
    duration = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
    run_live_e2e(target, duration)