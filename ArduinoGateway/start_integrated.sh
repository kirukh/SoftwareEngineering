#!/usr/bin/env bash
# Startet die integrierte Roboter-Pipeline auf dem Pi (robopi1):
#   Gateway (einziger Serial-Besitzer) + Visual (Hailo) + Laser + Controller.
# Navi2 (Antrieb) und Laserpointer (Servo) teilen sich denselben Arduino über
# den Gateway (ARDUINO_GATEWAY_URL). Voraussetzung: combined_firmware.ino ist
# auf den Arduino geflasht.
#
# Benutzung:  bash ArduinoGateway/start_integrated.sh
# Stoppen:    pkill -f uvicorn ; pkill -f "server.py"
set -u

ROOT="$HOME/ss2026_se_groupa"
GW_PORT=8005
export ARDUINO_GATEWAY_URL="http://127.0.0.1:${GW_PORT}"

# Visual empfindlicher machen, damit der Roboter beim Suchen zuverlässiger stoppt:
# niedrigere Confidence-Schwelle und weniger nötige Treffer im Fenster, bis ein
# Ziel als "gefunden" gilt. (Default war 0.5 / 5 Treffer -> löste selten aus.)
export VISION_CONFIDENCE_MIN="${VISION_CONFIDENCE_MIN:-0.35}"
export VISION_MIN_HITS_IN_WINDOW="${VISION_MIN_HITS_IN_WINDOW:-2}"

echo "== venv aktivieren =="
source "$HOME/hailo-apps/venv_hailo_apps/bin/activate"

echo "== alte Prozesse stoppen =="
pkill -9 -f "uvicorn" 2>/dev/null
pkill -9 -f "server.py" 2>/dev/null
sleep 2

echo "== 1) Gateway (Serial-Besitzer, Port ${GW_PORT}) =="
( cd "$ROOT/ArduinoGateway" && python -m uvicorn gateway:app --host 0.0.0.0 --port ${GW_PORT} > /tmp/gw.log 2>&1 & )
sleep 4
echo "   status: $(curl -s --max-time 3 http://127.0.0.1:${GW_PORT}/status)"

echo "== 2) Visual (Hailo + Kamera, Port 7995) =="
( cd "$ROOT/visual" && python server.py > /tmp/visual.log 2>&1 & )
sleep 10
echo "   health: $(curl -s --max-time 3 http://127.0.0.1:7995/health)"

# Kamera direkt live schalten: Tracking mit Default-Ziel starten, damit /stream
# schon nach dem Boot ein Bild liefert (sonst erst nach dem ersten /track/start).
# Per Env AUTO_TRACK_TARGET="" abschaltbar oder anderes Ziel setzen.
AUTO_TRACK_TARGET="${AUTO_TRACK_TARGET:-person}"
if [ -n "$AUTO_TRACK_TARGET" ]; then
  curl -s --max-time 4 -X POST http://127.0.0.1:7995/track/start \
    -H "Content-Type: application/json" -d "{\"name\":\"$AUTO_TRACK_TARGET\"}" >/dev/null \
    && echo "   auto-track gestartet: $AUTO_TRACK_TARGET (Kamera live)"
fi

echo "== 3) Laserpointer (Port 8004, Gateway-Modus) =="
( cd "$ROOT/Laserpointer" && python -m uvicorn main:app --host 0.0.0.0 --port 8004 > /tmp/laser.log 2>&1 & )
sleep 3
echo "   health: $(curl -s --max-time 3 http://127.0.0.1:8004/)"

echo "== 4) Controller (Port 7979, Gateway-Modus) =="
( cd "$ROOT/Interfaces" && python -m uvicorn controller:app --host 0.0.0.0 --port 7979 > /tmp/ctrl.log 2>&1 & )
sleep 3

echo ""
echo "== FERTIG =="
echo "Test (Audio simulieren):"
echo "  curl -X POST http://127.0.0.1:7979/start -H 'Content-Type: application/json' \\"
echo "       -d '{\"command\":\"search\",\"item\":\"person\",\"command_build\":true}'"
echo "Logs: /tmp/gw.log  /tmp/visual.log  /tmp/laser.log  /tmp/ctrl.log"
