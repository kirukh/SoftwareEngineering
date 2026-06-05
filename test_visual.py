"""
test_visual.py — Tests für die Tracking-API.

    python test_visual.py            # Fake-Tests, ohne Hardware
    python test_visual.py --server   # zusätzlich: HTTP-Endpoints via VisualClient

Echter Webcam-Test: siehe live_e2e_test.py
"""
from __future__ import annotations

import sys
import threading
import time

import visual
from visual_interface import VisionResult


# ------------------------------------------------------------------ Fake-Detektoren

class _AlwaysFoundDetector:
    def stream(self, name, on_frame, stop_event):
        while not stop_event.is_set():
            on_frame(VisionResult(name, True, 0.9, 0.5, 0.5, 0.2, 0.3))
            time.sleep(0.01)


class _NeverFoundDetector:
    def stream(self, name, on_frame, stop_event):
        while not stop_event.is_set():
            on_frame(VisionResult(name, False, 0.0))
            time.sleep(0.01)


def trennlinie(titel: str) -> None:
    print(f"\n{'='*55}\n  {titel}\n{'='*55}")


def _wait_until(predicate, timeout: float = 2.0, interval: float = 0.05) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


# ------------------------------------------------------------------ Fake-Tests

def run_fake_tests() -> None:
    trennlinie("Test 1: idle vor start_tracking()")
    visual.stop_tracking()
    result = visual.get_latest()
    print(f"  {result}")
    assert result == {"status": "idle"}
    print("  ✓ idle wenn nichts läuft")

    trennlinie("Test 2: start_tracking() + get_latest() — immer gefunden")
    visual.set_detector(_AlwaysFoundDetector())
    visual.start_tracking("smartphone")

    assert _wait_until(lambda: visual.get_latest().get("found") is True), \
        "Window wurde nicht rechtzeitig mit Treffern gefüllt"
    result = visual.get_latest()
    print(f"  {result}")
    assert result["status"] == "running"
    assert result["found"] is True
    assert result["name"] == "smartphone"
    assert 0.0 <= result["confidence"] <= 1.0
    assert result["x"] is not None and result["y"] is not None
    assert result["w"] is not None and result["h"] is not None
    print("  ✓ Tracking liefert aggregiertes Treffer-Dict mit w/h")

    trennlinie("Test 3: stop_tracking()")
    stop_result = visual.stop_tracking()
    print(f"  stop: {stop_result}")
    assert stop_result["status"] == "stopped"
    assert stop_result["was_running"] is True

    latest = visual.get_latest()
    print(f"  latest nach stop: {latest}")
    assert latest == {"status": "idle"}
    print("  ✓ Stop funktioniert, status zurück auf idle")

    trennlinie("Test 4: Nie-Gefunden → found=False")
    visual.set_detector(_NeverFoundDetector())
    visual.start_tracking("laptop")

    time.sleep(0.3)  # Window auffüllen lassen
    result = visual.get_latest()
    print(f"  {result}")
    assert result["status"] == "running"
    assert result["found"] is False
    assert result["name"] == "laptop"
    assert result["x"] is None and result["y"] is None
    assert result["w"] is None and result["h"] is None
    visual.stop_tracking()
    print("  ✓ Not-Found-Aggregat korrekt")

    trennlinie("Test 5: Idempotentes start_tracking()")
    visual.set_detector(_AlwaysFoundDetector())
    r1 = visual.start_tracking("cup")
    r2 = visual.start_tracking("cup")
    assert r1["status"] == "running" and r2["status"] == "running"
    visual.stop_tracking()
    print("  ✓ Doppelter start ist no-op")

    trennlinie("Test 6: stop_tracking() ohne laufendes Tracking")
    result = visual.stop_tracking()
    print(f"  {result}")
    assert result["status"] == "stopped"
    assert result["was_running"] is False
    print("  ✓ Stop ist idempotent")


# ------------------------------------------------------------------ Server-Test

def run_server_tests() -> None:
    """Startet Server, ruft Endpoints via VisualClient — wie der Controller."""
    try:
        import uvicorn
        from visual_client import VisualClient
    except ImportError:
        print("  Skip: httpx / uvicorn nicht installiert.")
        return

    visual.set_detector(_AlwaysFoundDetector())

    import server
    config = uvicorn.Config(server.app, host="127.0.0.1", port=8765, log_level="warning")
    srv = uvicorn.Server(config)
    threading.Thread(target=srv.run, daemon=True).start()

    client = VisualClient(base_url="http://127.0.0.1:8765")
    if not _wait_until(client.health, timeout=10.0):
        raise RuntimeError("Server ist nicht hochgekommen")

    try:
        trennlinie("Server-Test 1: /health via client.health()")
        assert client.health() is True
        print("  ✓ Server antwortet")

        trennlinie("Server-Test 2: latest() vor start → idle")
        r = client.latest()
        print(f"  {r}")
        assert r["status"] == "idle"

        trennlinie("Server-Test 3: start() + latest() polling")
        print(f"  start: {client.start('smartphone')}")
        for _ in range(20):
            r = client.latest()
            if r.get("found"):
                break
            time.sleep(0.1)
        print(f"  latest: {r}")
        assert r["status"] == "running"
        assert r["found"] is True
        assert r["w"] is not None and r["h"] is not None

        trennlinie("Server-Test 4: stop()")
        r = client.stop()
        print(f"  {r}")
        assert r["status"] == "stopped"

        trennlinie("Server-Test 5: validation error (leerer name)")
        # Direkter Test über interne Schicht — Pydantic-422 hat client.start nicht durchgelassen.
        import httpx
        r = httpx.post("http://127.0.0.1:8765/track/start", json={"name": "  "})
        print(f"  {r.status_code}")
        assert r.status_code == 422
        print("  ✓ Pydantic-Validation greift")
    finally:
        srv.should_exit = True
        client.close()
        visual.stop_tracking()
        visual.set_detector(None)


# ------------------------------------------------------------------ Main

if __name__ == "__main__":
    run_fake_tests()
    trennlinie("Alle Fake-Tests bestanden ✓")

    if "--server" in sys.argv:
        run_server_tests()
        trennlinie("Server-Tests bestanden ✓")
    else:
        print("\n  Tipp: --server für HTTP-Endpoint-Tests | live_e2e_test.py für Webcam")
