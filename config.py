"""
Configuración centralizada del proyecto ALPR Portería.

Por qué existe este archivo: si cada script escribiera sus propias rutas
("data/reales", "modelos/best.pt", etc.) a mano, mover una carpeta o renombrar
un modelo obligaría a editar diez archivos distintos. Aquí vive una sola vez
cada ruta y cada parámetro ajustable, y todo lo demás importa desde aquí.
"""

import sys
from pathlib import Path

# La consola de Windows usa por defecto una codificación (cp1252) que no
# soporta muchos caracteres Unicode. Algunas librerías (EasyOCR, al
# descargar sus modelos) imprimen caracteres como "█" en su barra de
# progreso y provocan un UnicodeEncodeError si no se cambia esto. Como
# config.py lo importan todos los scripts del proyecto, forzar UTF-8 aquí
# lo arregla en un solo lugar.
for _flujo in (sys.stdout, sys.stderr):
    if hasattr(_flujo, "reconfigure"):
        _flujo.reconfigure(encoding="utf-8")

# ---------------------------------------------------------------------------
# Rutas base del proyecto
# ---------------------------------------------------------------------------

# Path(__file__) es la ubicación de este archivo; .resolve().parent sube a la
# carpeta raíz del proyecto sin importar desde dónde se ejecute el script.
RAIZ = Path(__file__).resolve().parent

DIR_DATA = RAIZ / "data"
DIR_DATA_REALES = DIR_DATA / "reales"
DIR_FONDOS_REALES = DIR_DATA / "fondos_reales"  # recortes reales para mezclar en el generador (ver src/extraer_fondos_reales.py)
DIR_DATA_SINTETICAS = DIR_DATA / "sinteticas"
DIR_DATA_DATASET = DIR_DATA / "dataset"

DIR_MODELOS = RAIZ / "modelos"
DIR_SRC = RAIZ / "src"
DIR_PRUEBAS = RAIZ / "pruebas"
DIR_RESULTADOS = RAIZ / "resultados"

BASE_DATOS_SQLITE = RAIZ / "alpr_porteria.db"

# Modelo YOLO preentrenado usado en la Semana 1 para detectar vehículos
# completos (todavía no la placa). Se reemplaza en la Semana 3 por un modelo
# propio entrenado para detectar placas directamente.
MODELO_VEHICULOS = "yolo11n.pt"

# Ruta donde queda el modelo propio de detección de placas una vez entrenado
# en Colab (Semana 3). Mientras no exista, detector.py debe avisar y seguir
# funcionando con MODELO_VEHICULOS.
MODELO_PLACAS = DIR_MODELOS / "best.pt"

# ---------------------------------------------------------------------------
# Parámetros del detector
# ---------------------------------------------------------------------------

# Confianza mínima para aceptar una detección de YOLO. Si el detector no
# encuentra nada, este es el primer parámetro que hay que bajar (ver PARTE F
# de la guía: "El detector no encuentra nada").
UMBRAL_CONFIANZA_DETECTOR = 0.25

# Tamaño (en píxeles, lado cuadrado) al que YOLO reescala la imagen antes de
# procesarla. 640 es el valor estándar de Ultralytics; subirlo mejora un poco
# la precisión pero vuelve el procesamiento más lento en CPU.
TAMANO_IMAGEN_YOLO = 640

# Margen que se agrega alrededor de la caja detectada por el modelo de
# placas antes de recortarla para el OCR (fracción del ancho/alto de la
# caja). MEDIDO Y DESCARTADO: se probó con 0.08 pensando que un recorte
# pegado al borde cortaba caracteres, pero midiendo con
# pruebas/probar_ocr_sinteticas.py --usar-detector dio PEOR resultado
# (67.0%) que sin margen (71.0%) y que la imagen completa (74.0%), sobre
# las mismas 100 placas — la hipótesis del margen era incorrecta. Se deja en
# 0 hasta identificar la causa real (ver ANCHO_OBJETIVO_OCR más abajo).
MARGEN_RECORTE_PLACA = 0.0

# Clases de COCO que consideramos "vehículo" al usar el modelo preentrenado
# genérico de la Semana 1. IDs según el dataset COCO estándar de Ultralytics.
CLASES_VEHICULOS_COCO = {
    2: "carro",
    3: "motocicleta",
    5: "bus",
    7: "camion",
}

# ---------------------------------------------------------------------------
# Parámetros del lector OCR
# ---------------------------------------------------------------------------

# Caracteres que EasyOCR puede devolver. Restringirlo a letras y números
# evita que el OCR "invente" símbolos que nunca aparecen en una placa.
ALFABETO_OCR = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

# Ancho (px) al que se reescala SIEMPRE la imagen antes de leerla, sin
# importar si es la imagen completa o un recorte ajustado del detector.
#
# Antes se usaba un multiplicador fijo (x3) del tamaño de entrada, pero eso
# mezclaba dos cosas distintas: "cuánta ampliación se aplica" y "cuántos
# píxeles absolutos termina viendo el OCR". Un recorte ajustado es más chico
# en píxeles que la imagen completa, así que x3 le daba MENOS resolución
# final al recorte que a la imagen completa — probablemente la razón real
# por la que el recorte salía con peor precisión en las pruebas
# (pruebas/probar_ocr_sinteticas.py --usar-detector: 71% recorte vs. 74%
# imagen completa). Fijar un ancho absoluto iguala la cancha: los dos casos
# terminan con la misma resolución final, y el recorte debería ganar porque
# concentra esos mismos píxeles solo en la placa, no en fondo alrededor.
ANCHO_OBJETIVO_OCR = 1200

# Ancho mínimo (px) del recorte de la placa ANTES de agrandarlo a
# ANCHO_OBJETIVO_OCR. Por debajo de esto, agrandar la imagen no recupera
# detalle real: son los mismos pocos píxeles borrosos estirados más
# grandes. Un vehículo fotografiado muy lejos de la cámara cae en este
# caso — EasyOCR puede reportar confianza alta igual (no sabe cuánto se
# amplió la imagen), así que leer_placa() penaliza la confianza final
# cuando esto pasa, en vez de confiar ciegamente en el número de EasyOCR.
ANCHO_MINIMO_RECORTE_CONFIABLE = 60

# Parámetros de CLAHE (Contrast Limited Adaptive Histogram Equalization),
# la técnica usada para realzar el contraste antes del OCR.
CLAHE_LIMITE_CLIP = 2.0
CLAHE_TAMANO_GRILLA = (8, 8)

# ---------------------------------------------------------------------------
# Formatos de placa colombiana
# ---------------------------------------------------------------------------

# Automóviles: 3 letras + 3 números → ABC123
PATRON_PLACA_CARRO = r"^[A-Z]{3}[0-9]{3}$"

# Motocicletas: 3 letras + 2 números + 1 letra → ABC12D
PATRON_PLACA_MOTO = r"^[A-Z]{3}[0-9]{2}[A-Z]{1}$"

# Posiciones (0-indexadas) que deben ser letra o número en cada formato.
# Se usa en el validador para saber qué corrección aplicar en cada posición.
POSICIONES_CARRO = "LLLNNN"   # L = letra, N = número
POSICIONES_MOTO = "LLLNNL"

# Tabla de confusiones típicas del OCR, position-aware. Clave = carácter
# leído, valor = carácter probable en esa posición.
#
# Confirmado con el experimento de la Semana 2 (pruebas/probar_ocr_sinteticas.py,
# 100 placas sintéticas, resultados/ocr_sinteticas_confusiones.csv):
# precisión exacta 74%, precisión por carácter 95%. Las confusiones más
# frecuentes fueron 0->O (11 veces), 5->S (7), 2->Z (4), 7->Z (2), 1->I/T (1-2).
# 8->B se deja por ser una confusión conocida en la práctica aunque no haya
# aparecido en esta muestra de 100; vuelvan a correr el experimento con más
# placas para confirmar o ajustar esta tabla.
CONFUSIONES_NUMERO_A_LETRA = {
    "0": "O",
    "1": "I",
    "5": "S",
    "8": "B",
    "2": "Z",
}
CONFUSIONES_LETRA_A_NUMERO = {valor: clave for clave, valor in CONFUSIONES_NUMERO_A_LETRA.items()}

# ---------------------------------------------------------------------------
# Votación temporal en video (Semana 4)
# ---------------------------------------------------------------------------

TAMANO_VENTANA_VOTACION = 15       # cuántas lecturas recientes se acumulan
SEGUNDOS_ENFRIAMIENTO_PLACA = 8    # tiempo antes de volver a procesar la misma placa

# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def asegurar_carpetas():
    """Crea todas las carpetas de datos/resultados si no existen todavía."""
    for carpeta in (
        DIR_DATA_REALES,
        DIR_DATA_SINTETICAS,
        DIR_DATA_DATASET,
        DIR_MODELOS,
        DIR_RESULTADOS,
    ):
        carpeta.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    # Ejecutar este archivo directamente sirve para confirmar visualmente
    # que las rutas apuntan donde uno espera.
    asegurar_carpetas()
    print("Raíz del proyecto:", RAIZ)
    print("Base de datos:", BASE_DATOS_SQLITE)
    print("Modelo de placas:", MODELO_PLACAS, "(existe)" if MODELO_PLACAS.exists() else "(aún no entrenado)")
    print("Carpetas de datos verificadas/creadas.")
