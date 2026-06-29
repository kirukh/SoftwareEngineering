from Navigation_2.ImplementationCode.HardwareConfig import *
from Navigation_2.ImplementationCode.model import *
import math
import time 
import logging
from datetime import datetime

# Logging 
log_filename = f"navigation_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)s | %(message)s',
    
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
    ]
)
logger = logging.getLogger(__name__)

def compute_error(x):
    error = x - x_center
    logger.debug(f"compute_error({x}) = {error}")
    return error

def is_centered(error):
    result = abs(error) <= threshold
    logger.debug(f"is_centered({error}) = {result} (threshold={threshold})")
    return result

def compute_angle_sooner(error): 
    #diese Funktion stimmt die physiche und mathematische Berechnungslogik aber in der praxis ist es noch ungenau 
    #Voraussetzung ist : error ∈ [-0.5, 0.5]
    angle= error*FOV  
    result = max(-FOV/2, min(FOV/2, angle)) #schutz wenn error ∈ [-0.5, 0.5] nicht gilt
    logger.debug(f"compute_angle({error}) = {result}° (FOV={FOV})")
    return result

""" k (Gain-Faktor):
 k bestimmt, wie stark der Roboter auf den Positionsfehler reagiert.
 Der Fehler ist die Abweichung vom Bildzentrum (x - x_center).
 Ein kleiner k-Wert bedeutet sanfte, langsame Korrekturen.
 Ein großer k-Wert bedeutet schnelle, aber möglicherweise instabile Reaktionen.
 k dient also als Verstärkungsfaktor zwischen Wahrnehmung (Vision) und Bewegung (Motor).
 Verhalten: 
    kleines k → langsame, stabile Bewegung
    großes k → schnelle, aber evtl. instabile Bewegung
 k ist ein Verstärkungsfaktor, der in der Praxis durch Tests und Kalibrierung (trial-and-error tuning) bestimmt wird. 
 """

def compute_angle(error): 
    result = k * error
    logger.debug(f"compute_angle_later({error}) = {result}")
    return result

def angle_to_steps(angle):
    logger.debug(f"angle_to_steps({angle}°) gestartet")

    angle_rad = math.radians(angle)
    arc = angle_rad * (wheel_base /2)
    
    wheel_circ = 2 * math.pi * wheel_radius
    revs = arc / wheel_circ
    steps = revs * steps_per_rev
    
    sign = 1 if angle >= 0 else -1
    abs_steps = max(1, int(abs(steps)))  
    
    result = sign * abs_steps
    logger.debug(f"angle_to_steps({angle}°) = {result} steps")
    return result
    """logikerklärung :
       angle_to_steps()     → gibt immer positiven Betrag zurück (abs)
        ↓
       rotate()             → entscheidet wer + und wer - bekommt
        ↓
       left_motor(-steps)   → rückwärts
       right_motor(+steps)  → vorwärts
       """

def distance_to_steps(distance):
    wheel_circumference = 2 * math.pi * wheel_radius
    physical_steps= distance / wheel_circumference
    #hinweis: steps_per_rev = wie viele elektrische Schritte ein Stepper-Motor braucht, um eine komplette Umdrehung (360°) zu machen
    motor_steps = (distance / wheel_circumference) * steps_per_rev
    #step hier ist so gemeint: die kleinste elektrische Bewegungseinheit des Stepper-Motors und nicht die physische steps
    result = max(1, round(motor_steps))
    logger.debug(f"distance_to_steps({distance}m) = {result} steps (wheel_circ={wheel_circumference:.4f}m, motor_steps_raw={motor_steps:.2f})")
    return result
def _to_dict(input_data):
    # diese Funktion konvertiere den Objekt "Robotcommand" zu DICT
    if isinstance(input_data, RobotCommand):
        logger.debug("Konvertiere RobotCommand Objekt zu Dictionary")
        if hasattr(input_data, 'model_dump'):
            return input_data.model_dump()
    return input_data
#Haupfunktion

def execute_command(input_data):
    input_data = _to_dict(input_data)
    logger.info(f"=== execute_command aufgerufen mit: {input_data} ===")
    
    # Pydantic validierung
    try:
        cmd = RobotCommand(**input_data) #input_data dict wird entgepackt mit kwargs
        logger.debug(f"Validierung erfolgreich: action={cmd.action}, x={cmd.x}, distance={cmd.distance}")
    except Exception as e:
        logger.error(f"Validierung fehlgeschlagen: {e}")
        stop_motors()
        return {"action": "stop", "done": False, "error": "invalid_input"}

    action = cmd.action
    logger.info(f"Action: {action}")

    # ACTION = STOP
    if action == "STOP":
        logger.info("STOP - Motoren anhalten")
        stop_motors()
        return {"action": "stop", "done": True, "error": None}

    # ACTION = TURN
    if action == "TURN":
        logger.info("TURN - Drehung ausführen")
        angle = cmd.angle
        if angle is None:
            angle=30 #30 ist eine default drehungswinkel
            logger.info(f"TURN - Kein Winkel angegeben. Verwende Standardwinkel {angle}°")
        else:
            logger.info(f"TURN - Drehe um {angle}°")
        rotate_with_angle(angle) 
        return {"action": "turn", "done": True, "error": None}

    # ACTION = SEARCH
    if action == "SEARCH":
        logger.debug("SEARCH Modus")

        x = cmd.x
        distance = cmd.distance
        # validation: wenn search ohne x 

        if x is None:
            logger.warning("SEARCH ohne x-Parameter -> Führe TURN aus")
            rotate_with_angle(30)
            return {"action": "turn", "done": True, "error": None}
        # search ohne x = turn 

        error = compute_error(x)
        logger.info(f"x={x}, error={error}, centered? {is_centered(error)}")

        # nicht zentriertes Objekt -> rotate
        if not is_centered(error):
            angle = compute_angle(error)
            logger.info(f"Nicht zentriert -> Drehe um {angle}° ({angle} grad)")
            rotate_with_angle(angle)

        # zentriert -> sich vorwärts bewegen
        if distance is None:
            logger.warning("Zentriert aber keine Distanz -> STOP")
            stop_motors()
            return {"action": "search", "done": False, "error": "missing_distance"}
        if distance is not None and distance <= 0:
            logger.error(f"Ungültige distance: {distance}")
            stop_motors()
            return {"action": "search", "done": False, "error": "invalid_distance"}

        steps = distance_to_steps(distance)
        logger.info(f"Zentriert! Bewege vorwärts {distance}m ({steps} steps)")
        move_forward(steps)
        return {"action": "search", "done": True, "error": None}

    # fallback
    logger.error(f"Unbekannte Action: {action}")
    stop_motors()
    return {"action": "stop", "done": False, "error": "unknown_error"}
#rotate logik wird geändert : rotate wird mit winkel arbeiten (anhand von sensor ) also wenn die command ist rotate:30 dann wird der roboter sich drehen bis circa diesen Winkel erreicht ist 

