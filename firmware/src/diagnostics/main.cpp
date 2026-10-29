#include <Arduino.h>
#include <ESP32Servo.h>

#include "diagnostics/DiagnosticConfig.h"
#include "diagnostics/ServoSequence.h"
#include "diagnostics/UltrasonicSensor.h"

namespace hardware_diagnostic {

class DiagnosticApplication {
public:
    void begin() {
        Serial.begin(config::SERIAL_BAUD);
        sensor_.begin();
        disableServoOutput();
        last_measurement_ms_ = millis();
        printHelp();
    }

    void update() {
        // Límite de entrada para que el monitor no monopolice el loop.
        for (int count = 0; count < 16 && Serial.available() > 0; ++count) {
            const char command = static_cast<char>(Serial.read());
            if (command == 's' || command == 'S') {
                startServo();
            } else if (command == 'x' || command == 'X') {
                sequence_.stop();
                disableServoOutput();
                Serial.println("Servo detenido; PWM desactivado. Reinicia para otra prueba.");
            } else if (command == 'h' || command == '?') {
                printHelp();
            }
        }

        const uint32_t now_ms = millis();
        if (sequence_.update(now_ms)) {
            servo_.write(sequence_.angle());
            if (sequence_.state() == ServoSequence::State::Holding) {
                Serial.printf("Servo: consigna %d grados; pausa de %lu ms.\n",
                              sequence_.angle(),
                              static_cast<unsigned long>(config::SERVO_PAUSE_MS));
            }
        }
        if (sequence_.state() == ServoSequence::State::Finished && servo_.attached()) {
            disableServoOutput();
            Serial.println("Secuencia terminada en 90 grados; PWM desactivado.");
            Serial.println("No se repite. Reinicia y envia s para otra prueba.");
        }

        if (static_cast<uint32_t>(now_ms - last_measurement_ms_) >=
            config::MEASUREMENT_INTERVAL_MS) {
            last_measurement_ms_ = now_ms;
            printMeasurement(sensor_.measure());
        }
    }

private:
    static void printHelp() {
        Serial.println();
        Serial.println("Diagnostico local DOIT DevKit V1, 115200 baudios. Sin MQTT/Wi-Fi.");
        Serial.println("HC-SR04: TRIG=5, ECHO=18; SG90: senal=19.");
        Serial.println("s: una secuencia 90 -> 45 -> 90 -> 135 -> 90; x: detener; h: ayuda.");
        Serial.println("Pasos de 1 grado cada 25 ms y pausas de 1500 ms.");
        Serial.println("Al iniciar s, el servo recibe el centrado inicial a 90 grados.");
    }

    void startServo() {
        if (!sequence_.start(millis())) {
            Serial.println("Secuencia ya iniciada o consumida. Reinicia para habilitar otra.");
            return;
        }
        servo_.setPeriodHertz(config::SERVO_FREQUENCY_HZ);
        servo_.attach(config::SERVO_PIN, config::SERVO_MIN_PULSE_US,
                      config::SERVO_MAX_PULSE_US);
        if (!servo_.attached()) {
            sequence_.stop();
            disableServoOutput();
            Serial.println("Error: no se pudo asignar PWM al servo.");
            return;
        }
        servo_.write(sequence_.angle());
        Serial.println("Servo: centrado inicial a 90 grados; pausa antes de mover.");
    }

    void disableServoOutput() {
        if (servo_.attached()) {
            servo_.detach();
        }
        pinMode(config::SERVO_PIN, OUTPUT);
        digitalWrite(config::SERVO_PIN, LOW);
    }

    static void printMeasurement(const UltrasonicSensor::Measurement& reading) {
        if (reading.status == UltrasonicSensor::Status::NoEcho) {
            Serial.println("Distancia: sin eco (timeout de 30 ms), lectura invalida.");
        } else if (reading.status == UltrasonicSensor::Status::OutOfRange) {
            Serial.printf("Distancia: fuera de rango 2..400 cm (%.1f cm).\n",
                          reading.distance_cm);
        } else {
            Serial.printf("Distancia: %.1f cm | eco: %lu us\n",
                          reading.distance_cm, reading.echo_us);
        }
    }

    UltrasonicSensor sensor_;
    Servo servo_;
    ServoSequence sequence_;
    uint32_t last_measurement_ms_ = 0;
};

DiagnosticApplication application;
}  // namespace hardware_diagnostic

void setup() {
    hardware_diagnostic::application.begin();
}

void loop() {
    hardware_diagnostic::application.update();
    delay(1);
}
