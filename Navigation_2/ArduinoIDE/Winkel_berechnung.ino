#include <Arduino.h>
#include <Wire.h>
#include <L3G.h>

L3G gyro;

float winkel = 0.0;
unsigned long letzteZeit = 0;

#define SENSITIVITAET 0.00875
#define DEADBAND 20

void setup() {
  Serial.begin(9600);
  Wire.begin();
  
  if (gyro.init(L3G::device_4200D, L3G::sa0_high)) {
    gyro.enableDefault();
    Serial.println("READY");
  } else {
    Serial.println("Sensor nicht gefunden!");
  }
  letzteZeit = micros();
}

// Sensor kontinuierlich aktualisieren (im Hintergrund)
void updateGyro() {
  gyro.read();
  
  unsigned long jetzt = micros();
  float dt = (jetzt - letzteZeit) / 1000000.0;
  letzteZeit = jetzt;
  
  int16_t z_raw = gyro.g.z;
  if (abs(z_raw) > DEADBAND) {
    winkel += z_raw * SENSITIVITAET * dt;
  }
}

void loop() {
  // im Hintergrund integrieren
  updateGyro();
  
  // nur wenn Serial Befehl kommt
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    
    // aktuelle Position 
    if (cmd == "GET_ANGLE") {
      Serial.print("ANGLE:");
      Serial.println(winkel);
    }
    // Position zurücksetzen auf 0
    else if (cmd == "RESET_ANGLE") {
      winkel = 0.0;
      Serial.println("DONE: winkel = 0.0 ");
    }
  }
}

// RESET_ANGLE  → setzt auf 0 zurück
// Roboterbewegung oder manuelle Sensordrehung 
// GET_ANGLE    → gibt aktuelle Position 