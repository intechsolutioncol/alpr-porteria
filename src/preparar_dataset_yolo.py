"""
Arma el dataset en formato YOLO para entrenar el detector de placas
(Semana 3), a partir del generador de placas sintéticas de la Semana 2.

Formato de etiqueta YOLO (una línea por objeto, en un .txt con el mismo
nombre que la imagen):

    clase  x_centro  y_centro  ancho  alto

Todos los valores excepto "clase" están NORMALIZADOS entre 0 y 1 (se dividen
entre el ancho/alto de la imagen). Por qué normalizado: así la etiqueta no
depende de la resolución de la imagen, y el modelo aprende una posición
"relativa" (por ejemplo, "la placa ocupa el 60% del ancho, centrada un poco
a la izquierda") en vez de coordenadas absolutas en píxeles que solo
servirían para imágenes de un tamaño exacto.

x_centro, y_centro: el CENTRO del rectángulo que contiene la placa (no la
esquina, como en otros formatos como Pascal VOC o COCO).
ancho, alto: el tamaño del rectángulo, también normalizado.

Este proyecto detecta una sola clase ("placa" = clase 0), así que la
primera columna siempre es 0.
"""

import argparse
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from generador_placas import _generar_fondo, generar_placa_degradada, generar_texto_placa
from utilidades_imagen import escribir_imagen

NOMBRE_CLASE_PLACA = "placa"


def _caja_a_formato_yolo(caja, ancho_imagen, alto_imagen):
    x1, y1, x2, y2 = caja
    x_centro = (x1 + x2) / 2 / ancho_imagen
    y_centro = (y1 + y2) / 2 / alto_imagen
    ancho = (x2 - x1) / ancho_imagen
    alto = (y2 - y1) / alto_imagen
    return x_centro, y_centro, ancho, alto


# Rango de qué tan grande se ve la placa dentro del cuadro. Un valor fijo
# (como se usaba antes) le enseña al modelo que la placa siempre ocupa la
# mayoría de la imagen — falso en una foto real tomada a distancia normal.
# Se elige log-uniforme para no concentrar de más los valores grandes.
# margen 0.3 -> placa ~77% del ancho (de cerca); margen 5.0 -> placa ~17% (lejos)
MARGEN_RELATIVO_MIN = 0.3
MARGEN_RELATIVO_MAX = 5.0


def _margen_relativo_aleatorio():
    log_min, log_max = math.log10(MARGEN_RELATIVO_MIN), math.log10(MARGEN_RELATIVO_MAX)
    return 10 ** random.uniform(log_min, log_max)


def generar_ejemplo(indice, carpeta_imagenes, carpeta_etiquetas):
    tipo = random.choice(["carro", "moto"])
    texto = generar_texto_placa(tipo)
    imagen, caja_placa = generar_placa_degradada(
        texto, con_fondo=True, margen_relativo=_margen_relativo_aleatorio(),
    )

    alto_imagen, ancho_imagen = imagen.shape[:2]
    x_centro, y_centro, ancho, alto = _caja_a_formato_yolo(caja_placa, ancho_imagen, alto_imagen)

    nombre_base = f"placa_{indice:05d}_{texto}"

    ruta_imagen = carpeta_imagenes / f"{nombre_base}.jpg"
    escribir_imagen(ruta_imagen, imagen)

    ruta_etiqueta = carpeta_etiquetas / f"{nombre_base}.txt"
    with open(ruta_etiqueta, "w", encoding="utf-8") as f:
        f.write(f"0 {x_centro:.6f} {y_centro:.6f} {ancho:.6f} {alto:.6f}\n")


# Proporción del dataset que son ejemplos NEGATIVOS (fondo sin ninguna
# placa). El dataset original no tenía ninguno — el modelo solo veía
# imágenes CON una placa siempre presente, así que nunca aprendió que una
# malla, un pedazo de pavimento o un árbol NO es una placa (ver
# BITACORA_EXPERIMENTOS.md sección 6.4).
PROPORCION_EJEMPLOS_NEGATIVOS = 0.15


def generar_ejemplo_negativo(indice, carpeta_imagenes, carpeta_etiquetas):
    """
    Genera una imagen de puro fondo (puede ser procedural o un recorte
    real, ver generador_placas._generar_fondo), SIN ninguna placa pegada.

    Un archivo de etiqueta VACÍO es la forma estándar en YOLO de decir
    "esta imagen no tiene ningún objeto de la clase que se busca" — no hay
    que escribir nada especial, basta con que el .txt exista y esté vacío.
    """
    ancho = random.randint(400, 1400)
    alto = random.randint(300, 1000)
    imagen = _generar_fondo(ancho, alto)

    nombre_base = f"negativo_{indice:05d}"
    escribir_imagen(carpeta_imagenes / f"{nombre_base}.jpg", imagen)
    (carpeta_etiquetas / f"{nombre_base}.txt").touch()


def armar_dataset(cantidad, proporcion_val=0.2):
    carpetas = {
        "train_img": config.DIR_DATA_DATASET / "images" / "train",
        "val_img": config.DIR_DATA_DATASET / "images" / "val",
        "train_lbl": config.DIR_DATA_DATASET / "labels" / "train",
        "val_lbl": config.DIR_DATA_DATASET / "labels" / "val",
    }
    for carpeta in carpetas.values():
        carpeta.mkdir(parents=True, exist_ok=True)

    cantidad_val = int(cantidad * proporcion_val)
    cantidad_train = cantidad - cantidad_val

    negativos_train = int(cantidad_train * PROPORCION_EJEMPLOS_NEGATIVOS)
    positivos_train = cantidad_train - negativos_train
    negativos_val = int(cantidad_val * PROPORCION_EJEMPLOS_NEGATIVOS)
    positivos_val = cantidad_val - negativos_val

    print(
        f"Generando entrenamiento: {positivos_train} con placa + {negativos_train} sin placa. "
        f"Validación: {positivos_val} con placa + {negativos_val} sin placa."
    )

    for i in range(positivos_train):
        generar_ejemplo(i, carpetas["train_img"], carpetas["train_lbl"])
        if (i + 1) % max(1, positivos_train // 10) == 0:
            print(f"  entrenamiento (con placa): {i + 1}/{positivos_train}")

    for i in range(negativos_train):
        generar_ejemplo_negativo(i, carpetas["train_img"], carpetas["train_lbl"])
        if (i + 1) % max(1, negativos_train // 10) == 0:
            print(f"  entrenamiento (sin placa): {i + 1}/{negativos_train}")

    for i in range(positivos_val):
        generar_ejemplo(i, carpetas["val_img"], carpetas["val_lbl"])
        if (i + 1) % max(1, positivos_val // 10) == 0:
            print(f"  validación (con placa): {i + 1}/{positivos_val}")

    for i in range(negativos_val):
        generar_ejemplo_negativo(i, carpetas["val_img"], carpetas["val_lbl"])
        if (i + 1) % max(1, negativos_val // 10) == 0:
            print(f"  validación (sin placa): {i + 1}/{negativos_val}")

    ruta_yaml = config.DIR_DATA_DATASET / "dataset.yaml"
    with open(ruta_yaml, "w", encoding="utf-8") as f:
        f.write(f"path: {config.DIR_DATA_DATASET.as_posix()}\n")
        f.write("train: images/train\n")
        f.write("val: images/val\n")
        f.write("nc: 1\n")
        f.write(f"names: ['{NOMBRE_CLASE_PLACA}']\n")

    print(f"\nDataset listo en '{config.DIR_DATA_DATASET}'.")
    print(f"Archivo de configuración para Ultralytics: '{ruta_yaml}'")
    return ruta_yaml


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Arma el dataset YOLO de placas para entrenar el detector.")
    parser.add_argument("--cantidad", type=int, default=500, help="Total de imágenes a generar (train + val)")
    parser.add_argument("--proporcion-val", type=float, default=0.2, help="Proporción para validación (0.0 a 1.0)")
    args = parser.parse_args()

    armar_dataset(args.cantidad, args.proporcion_val)
