#versuch 
from Navigation_2.ImplementationCode.Navigation import execute_command
from Navigation_2.ImplementationCode.HardwareConfig import init
from Navigation_2.ImplementationCode.model import RobotCommand

# Initialisieren
init()
default = RobotCommand(action= "TURN")
print(execute_command(default))

"""
1. Objekt links erkannt 
{
  "action": "SEARCH",
  "x": 0.2,
  "distance": 1.0
}

2. Objekt rechts erkannt 
{
  "action": "SEARCH",
  "x": 0.8,
  "distance": 1.0
}

3. Objekt perfekt zentriert 
{
  "action": "SEARCH",
  "x": 0.5,
  "distance": 1.0
}

4. Kein Objekt sichtbar → Suchmodus (Rotation)
{
  "action": "SEARCH",
  
}

5. Objekt erkannt, aber keine Distanz (nur Alignment)
{
  "action": "SEARCH",
  "x": 0.4
}

6. Explizite Drehung 
{
  "action": "TURN"
}

7. Stop
{
  "action": "STOP"
}

8. Grenzfall nahe Zentrum ( kleine Korrektur )
{
  "action": "SEARCH",
  "x": 0.52,
  "distance": 0.5
}
"""