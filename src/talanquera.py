"""
Comunicación con el Arduino de la talanquera (Semana 9, objetivo opcional).

Usa pyserial, que NO está en el stack original del proyecto (Ultralytics,
EasyOCR, OpenCV, SQLite, Streamlit, Matplotlib): se agrega solo para esta
función opcional, porque es la librería estándar de Python para hablar por
puerto serial con un Arduino, y no hay una alternativa razonable dentro del
stack ya aprobado. Está declarada aparte en requirements-talanquera.txt para
que instalarla sea opcional (no todos los equipos tendrán el Arduino armado).

MODO SEGURO: este módulo solo EXPONE la posibilidad de abrir; la decisión de
cuándo llamarlo es del vigilante (ver el botón en src/app.py), nunca
automática a partir de una lectura del OCR. Además, si el Arduino no está
conectado, todo el resto del sistema debe seguir funcionando: por eso cada
función atrapa los errores de conexión en vez de dejar que se propaguen.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

BAUDIOS = 9600
TIEMPO_ESPERA_RESET_ARDUINO = 2.0  # el Arduino se reinicia solo al abrir el puerto serial; hay que esperar


class Talanquera:
    """
    Envoltorio sobre pyserial. Si no se puede conectar (Arduino no
    conectado, puerto equivocado, o pyserial no instalado), self.conectado
    queda en False y todos los métodos devuelven un resultado de error en
    vez de lanzar una excepción — así el resto de la app no tiene que estar
    llena de try/except para usar esta clase.
    """

    def __init__(self, puerto=None):
        self.conectado = False
        self._conexion = None

        try:
            import serial
        except ImportError:
            print(
                "AVISO: no está instalada 'pyserial'. La talanquera física no está "
                "disponible, pero el resto del sistema funciona igual.\n"
                "Para instalarla: pip install -r requirements-talanquera.txt"
            )
            return

        puerto = puerto or self._detectar_puerto(serial)
        if puerto is None:
            print("AVISO: no se detectó ningún Arduino conectado. La talanquera física no está disponible.")
            return

        try:
            self._conexion = serial.Serial(puerto, BAUDIOS, timeout=2)
            time.sleep(TIEMPO_ESPERA_RESET_ARDUINO)
            self.conectado = True
            print(f"Talanquera conectada en el puerto {puerto}.")
        except serial.SerialException as error:
            print(f"AVISO: no se pudo conectar al Arduino en '{puerto}': {error}")

    @staticmethod
    def _detectar_puerto(serial_modulo):
        from serial.tools import list_ports
        puertos = list(list_ports.comports())
        return puertos[0].device if puertos else None

    def _enviar_comando(self, comando):
        if not self.conectado:
            return {"ok": False, "mensaje": "Talanquera no conectada."}
        try:
            self._conexion.write(f"{comando}\n".encode("utf-8"))
            respuesta = self._conexion.readline().decode("utf-8").strip()
            return {"ok": True, "mensaje": respuesta}
        except Exception as error:
            return {"ok": False, "mensaje": f"Error de comunicación: {error}"}

    def abrir(self):
        """Abre la talanquera. Debe llamarse SOLO por acción explícita del vigilante."""
        return self._enviar_comando("ABRIR")

    def cerrar(self):
        return self._enviar_comando("CERRAR")

    def consultar_estado(self):
        return self._enviar_comando("ESTADO")


if __name__ == "__main__":
    talanquera = Talanquera()

    if not talanquera.conectado:
        print("\nNo se pudo conectar con el Arduino. Verifica:")
        print("  - Que esté conectado por USB")
        print("  - Que el sketch arduino/talanquera/talanquera.ino esté cargado")
        print("  - Que ningún otro programa (como el IDE de Arduino) tenga el puerto abierto")
        sys.exit(1)

    print("\nProbando comandos...")
    print("ESTADO:", talanquera.consultar_estado())
    print("ABRIR:", talanquera.abrir())
    time.sleep(1)
    print("ESTADO:", talanquera.consultar_estado())
    print("CERRAR:", talanquera.cerrar())
