"""
Agrega fotos reales, con su placa ya ubicada correctamente, como ejemplos
de entrenamiento adicionales (cuarta vuelta de entrenamiento del detector,
ver BITACORA_EXPERIMENTOS.md sección 6.5).

Hasta ahora el modelo solo había visto placas SINTÉTICAS (dibujadas por
código) pegadas sobre fondos reales o procedurales. Nunca había visto una
placa real de verdad — con su relieve, sus tornillos, su reflejo real bajo
luz real. Esto agrega ese ingrediente que faltaba.

De dónde salen las cajas: no se etiquetaron a mano. Se tomaron las cajas
que el propio detector (ya mejorado en la tercera vuelta) encontró sobre
las 19 fotos reales del usuario, y se revisaron una por una visualmente
(mosaico en la conversación del 2026-09-05): estas 11 quedaron con el
recuadro ajustado correctamente sobre la placa real, así que sirven como
etiqueta confiable aunque el OCR no siempre haya leído bien el texto (esta
técnica se llama "pseudo-etiquetado": usar las propias predicciones
confiables de un modelo como dato de entrenamiento adicional). Las otras
8 fotos (donde el recuadro cayó en malla/pavimento/etc., o no detectó
nada) NO se incluyen — usar una caja mal ubicada como si fuera correcta
sería peor que no usar la foto.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from utilidades_imagen import escribir_imagen, leer_imagen

# (archivo dentro de data/reales/, caja (x1, y1, x2, y2) en píxeles)
EJEMPLOS_REALES_CURADOS = [
    ("WhatsApp Image 2026-09-04 at 3.28.21 PM.jpeg", (372, 452, 630, 586)),
    ("WhatsApp Image 2026-09-04 at 3.28.22 PM (3).jpeg", (375, 446, 682, 604)),
    ("WhatsApp Image 2026-09-04 at 3.28.22 PM (4).jpeg", (79, 130, 816, 281)),
    ("WhatsApp Image 2026-09-04 at 3.28.22 PM.jpeg", (367, 189, 514, 265)),
    ("WhatsApp Image 2026-09-04 at 3.28.23 PM (2).jpeg", (339, 483, 665, 664)),
    ("WhatsApp Image 2026-09-04 at 3.28.23 PM (3).jpeg", (364, 520, 478, 578)),
    ("WhatsApp Image 2026-09-04 at 3.28.23 PM (4).jpeg", (4, 931, 262, 1017)),
    ("WhatsApp Image 2026-09-04 at 3.28.23 PM (5).jpeg", (451, 643, 624, 732)),
    ("WhatsApp Image 2026-09-04 at 3.28.24 PM (2).jpeg", (499, 983, 693, 1084)),
    ("WhatsApp Image 2026-09-04 at 3.28.24 PM (3).jpeg", (340, 782, 451, 840)),
    ("WhatsApp Image 2026-09-04 at 3.28.25 PM (1).jpeg", (264, 1002, 565, 1158)),
]

# Cuántas copias de cada ejemplo real se agregan al entrenamiento. Son solo
# 11 fotos frente a 1.200+ sintéticas, así que sin repetición el modelo
# casi no las vería; Ultralytics igual les aplica una variación distinta
# (rotación, color, recorte) cada vez que las usa, así que no son copias
# idénticas en la práctica del entrenamiento.
REPETICIONES = 15


def agregar_ejemplos_reales(carpeta_imagenes=None, carpeta_etiquetas=None, repeticiones=REPETICIONES):
    carpeta_imagenes = Path(carpeta_imagenes or config.DIR_DATA_DATASET / "images" / "train")
    carpeta_etiquetas = Path(carpeta_etiquetas or config.DIR_DATA_DATASET / "labels" / "train")
    carpeta_imagenes.mkdir(parents=True, exist_ok=True)
    carpeta_etiquetas.mkdir(parents=True, exist_ok=True)

    agregados = 0
    for archivo, caja in EJEMPLOS_REALES_CURADOS:
        ruta_origen = config.DIR_DATA_REALES / archivo
        imagen = leer_imagen(ruta_origen)
        if imagen is None:
            print(f"  ADVERTENCIA: no se pudo leer '{ruta_origen}', se omite.")
            continue

        alto_imagen, ancho_imagen = imagen.shape[:2]
        x1, y1, x2, y2 = caja
        x_centro = (x1 + x2) / 2 / ancho_imagen
        y_centro = (y1 + y2) / 2 / alto_imagen
        ancho_caja = (x2 - x1) / ancho_imagen
        alto_caja = (y2 - y1) / alto_imagen

        nombre_base = Path(archivo).stem.replace(" ", "_").replace("(", "").replace(")", "")
        for r in range(repeticiones):
            nombre = f"real_{nombre_base}_{r}"
            escribir_imagen(carpeta_imagenes / f"{nombre}.jpg", imagen)
            with open(carpeta_etiquetas / f"{nombre}.txt", "w", encoding="utf-8") as f:
                f.write(f"0 {x_centro:.6f} {y_centro:.6f} {ancho_caja:.6f} {alto_caja:.6f}\n")
            agregados += 1

    print(f"Se agregaron {agregados} imágenes ({len(EJEMPLOS_REALES_CURADOS)} fotos reales x {repeticiones} repeticiones) a '{carpeta_imagenes}'.")
    return agregados


if __name__ == "__main__":
    agregar_ejemplos_reales()
