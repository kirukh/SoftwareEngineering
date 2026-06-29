#include <Arduino.h>
#include <AccelStepper.h>

// Motor 1
#define STEP1 3
#define DIR1 2

// Motor 2
#define STEP2 6
#define DIR2 5

AccelStepper motor1(AccelStepper::DRIVER, STEP1, DIR1);
AccelStepper motor2(AccelStepper::DRIVER, STEP2, DIR2);

String command = "";

void setup() {

  Serial.begin(9600);
  Serial.println("READY");

  motor1.setMaxSpeed(1000);
  motor1.setAcceleration(500);

  motor2.setMaxSpeed(1000);
  motor2.setAcceleration(500);
}

void loop() {

  if (!Serial.available()) return;

  command = Serial.readStringUntil('\n');
  command.trim();

  Serial.println("GOT: " + command);

  if (command.startsWith("F:")) {

    long steps = command.substring(2).toInt();

    motor1.move(-steps);
    motor2.move(steps);

    while (motor1.distanceToGo() != 0 ||
           motor2.distanceToGo() != 0) {

      motor1.run();
      motor2.run();
    }

    Serial.println("DONE");
  }

  else if (command.startsWith("B:")) {

    long steps = command.substring(2).toInt();

    motor1.move(steps);
    motor2.move(-steps);

    while (motor1.distanceToGo() != 0 ||
           motor2.distanceToGo() != 0) {

      motor1.run();
      motor2.run();
    }

    Serial.println("DONE");
  }
  else if (command.startsWith("R:")) {

    long steps = command.substring(2).toInt();

    motor1.move(steps);
    motor2.move(steps);

    while (motor1.distanceToGo() != 0 ||
           motor2.distanceToGo() != 0) {

      motor1.run();
      motor2.run();
    }

    Serial.println("DONE");
}

  else if (command.startsWith("L:")) {

    long steps = command.substring(2).toInt();

    motor1.move(-steps);
    motor2.move(-steps);

    while (motor1.distanceToGo() != 0 ||
           motor2.distanceToGo() != 0) {

      motor1.run();
      motor2.run();
    }

    Serial.println("DONE");
}
  else if (command.startsWith("M1:")) {

    long steps = command.substring(3).toInt();

    motor1.move(steps);

    while (motor1.distanceToGo() != 0) {
      motor1.run();
    }

    Serial.println("DONE");
}

  else if (command.startsWith("M2:")) {

    long steps = command.substring(3).toInt();

    motor2.move(steps);

    while (motor2.distanceToGo() != 0) {
      motor2.run();
    }

    Serial.println("DONE");
}
}
//M1:steps => kurve
//M2:steps => kurve
//F:steps  => vorwärts gehen
//B:steps => ruckwärts gehen
//L:steps => links drehung
//R:steps => rechts drehung