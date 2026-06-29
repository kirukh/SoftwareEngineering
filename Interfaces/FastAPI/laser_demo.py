import requests
import time
import json

# python3 -m venv .venv
# .\.venv\Scripts\activate
# pip install requests
# python3 .\laser_demo.py

LINUX_IP = "172.24.13.28" 
BASE_URL = f"http://{LINUX_IP}:8000"

def test_laser_control():
    # 1. Laser bewegen (Zielen)
    print("--- Schritt 1: Laser bewegen ---")
    aim_data = {
        "x": 0.5,
        "y": 0.75,
        "confidence": 0.98
    }
    try:
        response = requests.post(f"{BASE_URL}/laser", json=aim_data)
        print(f"Status Code: {response.status_code}")
        print(f"Antwort: {response.json()}\n")
    except Exception as e:
        print(f"Fehler: {e}")
        return

    # Kurz warten, damit man den Status-Unterschied sieht
    time.sleep(1)

    # 2. Status abfragen (GET)
    print("--- Schritt 2: Status abfragen ---")
    response = requests.get(f"{BASE_URL}/laser/status")
    if response.status_code == 200:
        print(f"Aktueller Server-Status: {json.dumps(response.json(), indent=2)}\n")

    time.sleep(1)

    # 3. Laser deaktivieren
    print("--- Schritt 3: Laser ausschalten ---")
    off_data = {
        "x": -1,
        "y": -1,
        "confidence": 0.0
    }
    response = requests.post(f"{BASE_URL}/laser", json=off_data)
    print(f"Status Code: {response.status_code}")
    print(f"Antwort: {response.json()}\n")

    # 4. Finalen Status prüfen
    print("--- Schritt 4: Finaler Status ---")
    response = requests.get(f"{BASE_URL}/laser/status")
    print(response.json())

if __name__ == "__main__":
    test_laser_control()