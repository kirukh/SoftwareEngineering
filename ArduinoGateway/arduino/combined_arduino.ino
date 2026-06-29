// Kombinierter Sketch für EINEN Arduino Nano, der sowohl
// die Antriebsmotoren (Navi2 / Stepper) als auch den
// Laserpointer-Servo (Navi1 / Pan-Tilt) steuert.
//
// Pin-Belegung (kollisionsfrei mit den bisherigen Einzel-Sketches):
//   Stepper 1 (links):  STEP=3 DIR=2
//   Stepper 2 (rechts): STEP=6 DIR=5
//   Servo Pan  (X):     Pin 9
//   Servo Tilt (Y):     Pin 10
//
// Serielles Protokoll (eine gemeinsame Baudrate: 57600):
//   Antrieb (blockierend bis fertig, meldet "DONE"):
//     F:<steps>   vorwärts
//     B:<steps>   rückwärts
//     L:<steps>   links drehen
//     R:<steps>   rechts drehen
//     M1:<steps>  nur Motor 1
//     M2:<steps>  nur Motor 2
//     STOP        sofort anhalten
//   Laser (nicht blockierend, KEINE Antwort):
//     X<angle>    Pan-Winkel 0-180
//     Y<angle>    Tilt-Winkel 0-180
//
// Wichtig: Anders als die bisherigen Einzel-Sketches blockiert
// loop() NICHT mehr während einer Antriebsbewegung. So kann der
// Laser weiterhin nachgeführt werden, während sich der Roboter
// dem Ziel nähert (Navi2 fährt, Navi1/Laser hält gleichzeitig
// auf das Objekt).

#include <Arduino.h>
#include <AccelStepper.h>
#include <Servo.h>

// ---- Antrieb (Navi2) ----
#define STEP1 3
#define DIR1 2
#define STEP2 6
#define DIR2 5

AccelStepper motor1(AccelStepper::DRIVER, STEP1, DIR1);
AccelStepper motor2(AccelStepper::DRIVER, STEP2, DIR2);
bool driveBusy = false;

// ---- Laser (Navi1) ----
const int PAN_PIN = 9;
const int TILT_PIN = 10;
const int CENTER_ANGLE = 90;
const unsigned long SERVO_STEP_INTERVAL_MS = 4;

Servo pan;
Servo tilt;
int panCurrent = CENTER_ANGLE;
int panTarget = CENTER_ANGLE;
int tiltCurrent = CENTER_ANGLE;
int tiltTarget = CENTER_ANGLE;
unsigned long lastServoStepMs = 0;

String command = "";

void setup() {
  Serial.begin(57600);
  Serial.println("READY");

  motor1.setMaxSpeed(1000);
  motor1.setAcceleration(500);
  motor2.setMaxSpeed(1000);
  motor2.setAcceleration(500);

  pan.attach(PAN_PIN);
  tilt.attach(TILT_PIN);
  pan.write(CENTER_ANGLE);
  tilt.write(CENTER_ANGLE);
}

void startDrive(long steps1, long steps2) {
  motor1.move(steps1);
  motor2.move(steps2);
  driveBusy = true;
}

void handleDriveCommand(const String &cmd) {
  if (cmd.startsWith("F:")) {
    long steps = cmd.substring(2).toInt();
    startDrive(-steps, steps);
  } else if (cmd.startsWith("B:")) {
    long steps = cmd.substring(2).toInt();
    startDrive(steps, -steps);
  } else if (cmd.startsWith("R:")) {
    long steps = cmd.substring(2).toInt();
    startDrive(steps, steps);
  } else if (cmd.startsWith("L:")) {
    long steps = cmd.substring(2).toInt();
    startDrive(-steps, -steps);
  } else if (cmd.startsWith("M1:")) {
    motor1.move(cmd.substring(3).toInt());
    driveBusy = true;
  } else if (cmd.startsWith("M2:")) {
    motor2.move(cmd.substring(3).toInt());
    driveBusy = true;
  } else if (cmd == "STOP") {
    motor1.stop();
    motor2.stop();
    driveBusy = false;
    Serial.println("DONE");
  }
}

void handleServoCommand(char axis, int angle) {
  int safeAngle = constrain(angle, 0, 180);
  if (axis == 'X') {
    panTarget = safeAngle;
  } else if (axis == 'Y') {
    tiltTarget = safeAngle;
  }
}

void processSerial() {
  if (!Serial.available()) return;

  char first = Serial.peek();

  // Laser-Befehle: einzelnes Zeichen + Zahl, keine Zeilenumbrüche nötig.
  if (first == 'X' || first == 'Y') {
    char axis = Serial.read();
    int angle = Serial.parseInt();
    handleServoCommand(axis, angle);
    return;
  }

  // Antriebsbefehle: ganze Zeile bis '\n'.
  command = Serial.readStringUntil('\n');
  command.trim();
  if (command.length() == 0) return;
  handleDriveCommand(command);
}

void stepDrive() {
  motor1.run();
  motor2.run();
  if (driveBusy && motor1.distanceToGo() == 0 && motor2.distanceToGo() == 0) {
    driveBusy = false;
    Serial.println("DONE");
  }
}

void stepServos() {
  unsigned long now = millis();
  if (now - lastServoStepMs < SERVO_STEP_INTERVAL_MS) return;
  lastServoStepMs = now;

  if (panCurrent != panTarget) {
    panCurrent += (panTarget > panCurrent) ? 1 : -1;
    pan.write(panCurrent);
  }
  if (tiltCurrent != tiltTarget) {
    tiltCurrent += (tiltTarget > tiltCurrent) ? 1 : -1;
    tilt.write(tiltCurrent);
  }
}

void loop() {
  processSerial();
  stepDrive();
  stepServos();
}
