# Für Visual 👀

Hey, bei euch gibt's **keinen Code von uns zum Einbauen** – nur zwei Sachen, die uns
beim Testen aufgefallen sind. Bitte mal anschauen, das würde echt helfen.

## 1) Bug: Hailo-Pipelines stapeln sich (wichtig!)
Bei **jedem** `track/start` (also jedem Zielwechsel) startet eine neue GStreamer-
Pipeline – aber die **alte stirbt nicht**. Die Prozesse heißen `Hailo Detection App`
(nicht `server.py`!), deshalb fällt's erst auf, wenn man genau hinschaut.

Was passiert: nach ein paar Zielwechseln laufen 5–10+ solche Prozesse gleichzeitig,
die kämpfen alle um die **eine** Kamera/NPU – und dann erkennt der Detector **gar
nichts mehr** (`found:false`, `confidence:0.0`), obwohl das Kamerabild im `/stream`
noch normal kommt. Mega verwirrend beim Debuggen.

Symptom im Log: `Detector-Thread nach 5.0s Timeout noch aktiv — Kamera/Pipeline evtl.
noch belegt.`

**Bitte:** beim `stop_tracking` (bzw. bevor eine neue Pipeline startet) den alten
GStreamer-Prozess wirklich beenden. Aktuell killt das `app.shutdown()` den
`Hailo Detection App`-Prozess scheinbar nicht zuverlässig.

Workaround bei uns bis dahin: immer nur **ein** Ziel pro Visual-Lauf, und vor jedem
sauberen Test alles hart killen (`pkill -9 -f "Hailo Detection App"`).

## 2) Tipp: Empfindlichkeit
Mit den Defaults (`confidence_min = 0.5`, `min_hits_in_window = 5`) hat's beim Suchen
**selten** ausgelöst – Personen kamen teils nur mit ~0.34 an. Mit
```
VISION_CONFIDENCE_MIN=0.35
VISION_MIN_HITS_IN_WINDOW=2
```
(beide per Env, gehen schon über eure config.py) lief's deutlich zuverlässiger.
Vielleicht wäre das ein besserer Default fürs Roboter-Setup.

Ansonsten: Detector an sich läuft top – wenn's sauber ist, kam die Person mit 0.88. 👌

Fragen? -> Laser-Gruppe (Yusuf).
