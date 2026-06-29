#include <Arduino.h>
#include <AccelStepper.h>
#include <Wire.h>
#include <L3G.h>

//verbindungen motortreiber 1
#define STEP1 3// step : heisst jede High-Puls auf diesem Pin =1 Schritt bewegung
#define DIR1 2 //direction (richtung) : High=Vorwärt , Low=Rückwärts
//verbindungen motortrebier 2
#define STEP2 5
#define DIR2 4
//enabel für beide motoren
#define ENABLE 12
// AccelStepper ersetzt die manuelle digitalWrite Logik
AccelStepper motor1(AccelStepper::DRIVER, STEP1, DIR1);
AccelStepper motor2(AccelStepper::DRIVER, STEP2, DIR2);
//sensor
#define LEFT_FACTOR  1.00
#define RIGHT_FACTOR 1.03
L3G gyro;

// Sensor Kalibrierung
#define SENSITIVITAET 0.00875  // °/Sekunde pro Rohwert (250dps default)
#define DEADBAND 20            // Rauschen unter diesem Wert ignorieren


String command = ""; //hier werden die Serial befehle abgespeichert wie zb FORWORD:200 

//diese void Setup läuft EINMAL beim Start des Arduino
void setup() {

  Serial.begin(9600); //aktiviert die serielle Kommunikation auf dem Arduino (python - Arduino Connection)
  //Arduino kann Daten über USB senden und empfangen
  //Python kann diese Daten lesen und schreiben
  //9600 ist Übertragungsgeschwindigkei => wie schnell Daten übertragen werden
  //9600 (sehr stabil, langsam) 
  //115200 (schneller)
  pinMode(ENABLE, OUTPUT);
  digitalWrite(ENABLE, LOW);   // Treiber aktiv
  // Geschwindigkeit und Beschleunigung einstellen
  // setMaxSpeed: maximale Steps pro Sekunde
  // setAcceleration: Steps pro Sekunde² 
  motor1.setMaxSpeed(1000);
  motor1.setAcceleration(500);
  motor2.setMaxSpeed(1000);
  motor2.setAcceleration(500);

  // Sensor initialisieren (Adresse 0x69, SDO high)
  Wire.begin();
  if (gyro.init(L3G::device_4200D, L3G::sa0_high)) {
    gyro.enableDefault();
    Serial.println("SENSOR READY");
  } else {
    Serial.println("SENSOR FEHLER");
  }

}
// liest Sensor und gibt aktuelle Winkelgeschwindigkeit zurück (gefiltert)
float readGyroZ() {
  gyro.read();
  int16_t z_raw = gyro.g.z;
  if (abs(z_raw) > DEADBAND) {
    return z_raw * SENSITIVITAET;  // °/Sekunde
  }
  return 0.0;
}

// Rotation mit Sensor-Feedback bis Zielwinkel erreicht
// zielWinkel > 0 → rechts, zielWinkel < 0 → links
void rotateWithAngle(float zielWinkel) {

  float winkel = 0.0;
  unsigned long letzteZeit = micros();

  long richtung = (zielWinkel > 0) ? 1 : -1;

  motor1.setSpeed(-500 * richtung);
  motor2.setSpeed(500 * richtung);  // Motor 2 spiegelverkehrt wie bei rotate()

  while (abs(winkel) < abs(zielWinkel)) {
    motor1.runSpeed();
    motor2.runSpeed();

    unsigned long jetzt = micros();
    float dt = (jetzt - letzteZeit) / 1000000.0;
    letzteZeit = jetzt;

    float z_dps = readGyroZ();
    winkel += z_dps * dt;
  }

  // Motoren komplett anhalten
  motor1.move(0);
  motor2.move(0);

  Serial.print("DONE winkel=");
  Serial.println(winkel);
}

//bewegungsfunktion beide Motoren gleichzeitig 
//long ist gewählt weil int ist klein und kann zu owerflow führen
void runMotors(long steps1, long steps2) {
  motor1.move(steps1); // richtung motor 1 → positiv=vorwärts, negativ=rückwärts
  motor2.move(steps2); //richtung motor 2

  // beide Motoren gleichzeitig fahren bis Ziel erreicht
  while (motor1.distanceToGo() != 0 || motor2.distanceToGo() != 0) {
    motor1.run(); //beide Motoren machen einen Schritt (start Puls)
    motor2.run();
    //die bibliotheke AccelStepper übernimmt Timing automatisch und kein delayMicroseconds nötig hier
  }
}
//funktionen
//Forwärts gehen
void moveForward(long steps) {
  runMotors(steps, steps);
  Serial.println("moveForward: DONE");
}
//rückwärts gehen (wird vielleicht später verwendet)
void moveBackward(long steps) {
  runMotors(-steps, -steps);
  Serial.println("moveBackward: DONE");
}


//einzelmotordrehung (dient zu Kurven wird vielleicht später verwendet)
void motor1Move(long steps) {
  motor1.move(steps);
  while (motor1.distanceToGo() != 0) motor1.run();
  Serial.println("motor1Move: DONE");
}
void motor2Move(long steps) {
  motor2.move(steps);
  while (motor2.distanceToGo() != 0) motor2.run();
  Serial.println("motor2Move: DONE");
}
//stop 
void stopMotors() {
  motor1.stop();
  motor2.stop();
}
//main
void loop() {
  //check ob wir COMMAND haben
  if (!Serial.available()) return;
  command = Serial.readStringUntil('\n');
  command.trim();
  Serial.println("GOT: " + command); // nur für debugging

  if (command.length() == 0) return; 
  if (command.startsWith("STOP")) {
    stopMotors();
    } 
  else if (command.startsWith("FORWARD")) {
    long steps = strtol(command.substring(command.indexOf(':') + 1).c_str(), NULL, 10);
    moveForward(steps);
    }

  else if (command.startsWith("BACKWARD")) {
    long steps = strtol(command.substring(command.indexOf(':') + 1).c_str(), NULL, 10);
    moveBackward(steps);
    }
  else if (command.startsWith("ROTATE")) {
    float angle = strtol(command.substring(command.indexOf(':') + 1).c_str(), NULL, 10);
      rotateWithAngle(angle);
    }
  else if (command.startsWith("M1:")) {
    long steps = strtol(command.substring(command.indexOf(':') + 1).c_str(), NULL, 10);
    motor1Move(steps);
  }
  else if (command.startsWith("M2:")) {
    long steps = strtol(command.substring(command.indexOf(':') + 1).c_str(), NULL, 10);
    motor2Move(steps);
  }

  }