#include <Arduino.h>
#include <AccelStepper.h>
#include <Wire.h>
#include <L3G.h>
#include <Servo.h>

// ---- Navi2: Stepper + Gyro (main.cpp'den birebir) ----
#define STEP1 3
#define DIR1 2
#define STEP2 5
#define DIR2 4
#define ENABLE 12
AccelStepper motor1(AccelStepper::DRIVER, STEP1, DIR1);
AccelStepper motor2(AccelStepper::DRIVER, STEP2, DIR2);
L3G gyro;
#define SENSITIVITAET 0.00875
#define DEADBAND 20
// Suchdrehzahl (Steps/Sek). Niedriger = langsamer drehen, damit die Kamera pro
// Position Zeit zum Erkennen hat. 250 ist die Hälfte der ursprünglichen 500
// (deutlich langsamer), bleibt aber klar über der Gyro-DEADBAND-Schwelle.
#define ROTATE_SPEED 250
// SICHERHEIT: Maximale Dauer einer einzelnen Drehung. Erreicht der Gyro das
// Zielwinkel nicht (z.B. Sensor liefert nichts), bricht die Schleife nach dieser
// Zeit ab, damit der Roboter NICHT endlos weiterdreht.
#define MAX_ROTATE_MS 6000

// ---- Navi1: Laser servos (arduino_code.txt'den) ----
#define PAN_PIN 9
#define TILT_PIN 10
#define CENTER_ANGLE 90
#define SMOOTH_STEP_DELAY_MS 4
Servo pan;
Servo tilt;

String command = "";

void setup() {
  Serial.begin(9600);
  pinMode(ENABLE, OUTPUT);
  digitalWrite(ENABLE, LOW);
  motor1.setMaxSpeed(1000);
  motor1.setAcceleration(500);
  motor2.setMaxSpeed(1000);
  motor2.setAcceleration(500);

  Wire.begin();
  if (gyro.init(L3G::device_4200D, L3G::sa0_high)) {
    gyro.enableDefault();
    Serial.println("SENSOR READY");
  } else {
    Serial.println("SENSOR FEHLER");
  }

  pan.attach(PAN_PIN);
  tilt.attach(TILT_PIN);
  pan.write(CENTER_ANGLE);
  tilt.write(CENTER_ANGLE);
}

float readGyroZ() {
  gyro.read();
  int16_t z_raw = gyro.g.z;
  if (abs(z_raw) > DEADBAND) {
    return z_raw * SENSITIVITAET;
  }
  return 0.0;
}

void rotateWithAngle(float zielWinkel) {
  float winkel = 0.0;
  unsigned long letzteZeit = micros();
  long richtung = (zielWinkel > 0) ? 1 : -1;
  motor1.setSpeed(-ROTATE_SPEED * richtung);
  motor2.setSpeed(ROTATE_SPEED * richtung);
  unsigned long startMs = millis();
  while (abs(winkel) < abs(zielWinkel)) {
    motor1.runSpeed();
    motor2.runSpeed();
    unsigned long jetzt = micros();
    float dt = (jetzt - letzteZeit) / 1000000.0;
    letzteZeit = jetzt;
    winkel += readGyroZ() * dt;
    // SICHERHEIT: nie endlos drehen, falls der Gyro das Ziel nie meldet.
    if (millis() - startMs > MAX_ROTATE_MS) {
      Serial.println("ROTATE TIMEOUT");
      break;
    }
  }
  motor1.move(0);
  motor2.move(0);
  Serial.print("DONE winkel=");
  Serial.println(winkel);
}

void runMotors(long steps1, long steps2) {
  motor1.move(steps1);
  motor2.move(steps2);
  while (motor1.distanceToGo() != 0 || motor2.distanceToGo() != 0) {
    motor1.run();
    motor2.run();
  }
}

void moveServoSmooth(Servo &servo, int targetAngle) {
  int currentAngle = servo.read();
  int step = (targetAngle >= currentAngle) ? 1 : -1;
  for (int angle = currentAngle; angle != targetAngle; angle += step) {
    servo.write(angle);
    delay(SMOOTH_STEP_DELAY_MS);
  }
  servo.write(targetAngle);
}

void handleServo(char axis, int angle) {
  int safeAngle = constrain(angle, 0, 180);
  if (axis == 'X') {
    moveServoSmooth(pan, safeAngle);
  } else if (axis == 'Y') {
    moveServoSmooth(tilt, safeAngle);
  }
}

void loop() {
  if (!Serial.available()) return;
  char first = Serial.peek();

  // --- Laser (X/Y) ---
  if (first == 'X' || first == 'Y') {
    char axis = Serial.read();
    int angle = Serial.parseInt();
    handleServo(axis, angle);
    return;
  }

  // --- Navi2 satir komutu ---
  command = Serial.readStringUntil('\n');
  command.trim();
  if (command.length() == 0) return;

  if (command.startsWith("STOP")) {
    motor1.stop();
    motor2.stop();
    Serial.println("STOP: DONE");
  } else if (command.startsWith("FORWARD")) {
    long steps = strtol(command.substring(command.indexOf(':') + 1).c_str(), NULL, 10);
    runMotors(steps, steps);
    Serial.println("moveForward: DONE");
  } else if (command.startsWith("BACKWARD")) {
    long steps = strtol(command.substring(command.indexOf(':') + 1).c_str(), NULL, 10);
    runMotors(-steps, -steps);
    Serial.println("moveBackward: DONE");
  } else if (command.startsWith("ROTATE")) {
    float angle = strtol(command.substring(command.indexOf(':') + 1).c_str(), NULL, 10);
    rotateWithAngle(angle);
  } else if (command.startsWith("M1:")) {
    long steps = strtol(command.substring(command.indexOf(':') + 1).c_str(), NULL, 10);
    motor1.move(steps);
    while (motor1.distanceToGo() != 0) motor1.run();
    Serial.println("motor1Move: DONE");
  } else if (command.startsWith("M2:")) {
    long steps = strtol(command.substring(command.indexOf(':') + 1).c_str(), NULL, 10);
    motor2.move(steps);
    while (motor2.distanceToGo() != 0) motor2.run();
    Serial.println("motor2Move: DONE");
  }
}
