/*
  Control de la talanquera con servo motor (Semana 9, objetivo opcional).

  MODO SEGURO: este Arduino NUNCA decide abrir la talanquera por su cuenta.
  Solo mueve el servo cuando recibe la orden explícita "ABRIR" por el puerto
  serial, y esa orden solo la envía la app cuando el VIGILANTE presiona el
  botón. El reconocimiento automático de placas nunca está conectado
  directamente al servo. Esto es a propósito: un falso positivo del OCR
  (leer mal una placa y confundirla con una autorizada) no debe poder abrir
  una talanquera física sin que una persona lo confirme. La cámara y el OCR
  pueden equivocarse; que un vigilante confirme es la última barrera de
  seguridad real del sistema.

  Comandos por serial (9600 baudios, uno por línea):
    ABRIR   -> mueve el servo a la posición abierta
    CERRAR  -> mueve el servo a la posición cerrada
    ESTADO  -> responde "ABIERTA" o "CERRADA"
*/

#include <Servo.h>

const int PIN_SERVO = 9;
const int ANGULO_CERRADO = 0;
const int ANGULO_ABIERTO = 90;

Servo servoTalanquera;
bool talanqueraAbierta = false;

void setup() {
  Serial.begin(9600);
  servoTalanquera.attach(PIN_SERVO);
  servoTalanquera.write(ANGULO_CERRADO);
  Serial.println("LISTO");
}

void loop() {
  if (Serial.available() > 0) {
    String comando = Serial.readStringUntil('\n');
    comando.trim();
    comando.toUpperCase();

    if (comando == "ABRIR") {
      servoTalanquera.write(ANGULO_ABIERTO);
      talanqueraAbierta = true;
      Serial.println("OK ABIERTA");
    } else if (comando == "CERRAR") {
      servoTalanquera.write(ANGULO_CERRADO);
      talanqueraAbierta = false;
      Serial.println("OK CERRADA");
    } else if (comando == "ESTADO") {
      Serial.println(talanqueraAbierta ? "ABIERTA" : "CERRADA");
    } else if (comando.length() > 0) {
      Serial.println("ERROR comando desconocido: " + comando);
    }
  }
}
