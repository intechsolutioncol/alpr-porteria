"""
Extrae recortes de fondo REALES (del video y de las fotos que subió el
usuario) para usarlos al generar placas sintéticas de entrenamiento.

Por qué hace falta (Semana 3, segunda vuelta de entrenamiento): el dataset
original solo usaba 3 fondos generados por código (ruido gris tipo
asfalto, color liso tipo pared, degradado tipo carrocería — ver
generador_placas.py::_generar_fondo). Al probar con fotos reales, el
detector confundía mallas, pavimento agrietado y árboles con una placa en
más de la mitad de los casos (ver BITACORA_EXPERIMENTOS.md sección 6.4):
el modelo nunca había visto esas texturas. Mezclar fondos reales en el
entrenamiento expone al modelo a la variedad real sin tener que fotografiar
miles de escenas.

Fuentes de fondo:
- El video (data/reales/*.mov): se recorren fotogramas espaciados y se
  sacan varios recortes aleatorios de cada uno.
- Las fotos reales (data/reales/*.jpg, *.jpeg, *.png): se recortan solo
  las ESQUINAS de cada foto (evitando el centro, donde suele estar el
  vehículo/la placa), para no arriesgarse a incluir una placa real sin
  etiquetar dentro de un fondo que se supone no tiene ninguna.
"""

import argparse
import glob
import random
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from utilidades_imagen import escribir_imagen, leer_imagen

TAMANO_MINIMO_RECORTE = 200
TAMANO_MAXIMO_RECORTE = 900


def _recortes_aleatorios(imagen, cantidad):
    alto, ancho = imagen.shape[:2]
    recortes = []
    intentos = 0
    while len(recortes) < cantidad and intentos < cantidad * 10:
        intentos += 1
        tamano = random.randint(TAMANO_MINIMO_RECORTE, min(TAMANO_MAXIMO_RECORTE, min(alto, ancho) - 1))
        if tamano >= min(alto, ancho):
            continue
        x = random.randint(0, ancho - tamano)
        y = random.randint(0, alto - tamano)
        recorte = imagen[y:y + tamano, x:x + tamano]

        # Descarta recortes casi sin variación (probablemente cielo despejado
        # o una superficie lisa sin ninguna textura útil para aprender).
        if recorte.std() < 8:
            continue
        recortes.append(recorte)
    return recortes


def extraer_de_video(ruta_video, carpeta_salida, fotogramas_a_muestrear=25, recortes_por_fotograma=4):
    captura = cv2.VideoCapture(str(ruta_video))
    if not captura.isOpened():
        print(f"  No se pudo abrir '{ruta_video}'.")
        return 0

    total_fotogramas = int(captura.get(cv2.CAP_PROP_FRAME_COUNT))
    indices = sorted(random.sample(range(total_fotogramas), min(fotogramas_a_muestrear, total_fotogramas)))

    guardados = 0
    for indice in indices:
        captura.set(cv2.CAP_PROP_POS_FRAMES, indice)
        leido, cuadro = captura.read()
        if not leido:
            continue
        for recorte in _recortes_aleatorios(cuadro, recortes_por_fotograma):
            escribir_imagen(carpeta_salida / f"video_{indice}_{guardados}.jpg", recorte)
            guardados += 1

    captura.release()
    return guardados


def extraer_de_fotos(carpeta_fotos, carpeta_salida, recortes_por_foto=4):
    extensiones = ("*.jpg", "*.jpeg", "*.png")
    rutas = [p for ext in extensiones for p in glob.glob(str(Path(carpeta_fotos) / ext))]

    guardados = 0
    for ruta in rutas:
        imagen = leer_imagen(ruta)
        if imagen is None:
            continue
        alto, ancho = imagen.shape[:2]

        # Solo las 4 esquinas (cada una hasta el 35% del ancho/alto), para
        # evitar el centro de la foto donde casi siempre está el vehículo.
        margen_x, margen_y = int(ancho * 0.35), int(alto * 0.35)
        esquinas = [
            imagen[0:margen_y, 0:margen_x],
            imagen[0:margen_y, ancho - margen_x:ancho],
            imagen[alto - margen_y:alto, 0:margen_x],
            imagen[alto - margen_y:alto, ancho - margen_x:ancho],
        ]
        random.shuffle(esquinas)

        for i, esquina in enumerate(esquinas[:recortes_por_foto]):
            if esquina.size == 0 or min(esquina.shape[:2]) < TAMANO_MINIMO_RECORTE:
                continue
            if esquina.std() < 8:
                continue
            nombre_base = Path(ruta).stem.replace(" ", "_")
            escribir_imagen(carpeta_salida / f"foto_{nombre_base}_{i}.jpg", esquina)
            guardados += 1

    return guardados


def _tiene_parche_amarillo_de_placa(imagen, proporcion_maxima=0.012):
    """
    Segundo filtro, más barato y más estricto que el detector: descarta un
    recorte si una porción notable de sus píxeles cae en el rango de
    amarillo característico de una placa colombiana (ver
    generador_placas.AMARILLO_PLACA). Complementa al filtro por vehículo:
    en la revisión visual quedaron un par de recortes con el BORDE de una
    placa real asomando en una esquina, de un vehículo que el detector de
    vehículos no alcanzó a reconocer completo.
    """
    hsv = cv2.cvtColor(imagen, cv2.COLOR_BGR2HSV)
    amarillo_bajo = np.array([18, 80, 80])
    amarillo_alto = np.array([35, 255, 255])
    mascara = cv2.inRange(hsv, amarillo_bajo, amarillo_alto)
    return (mascara > 0).mean() > proporcion_maxima


def filtrar_recortes_con_placa(carpeta, umbral_confianza=0.25):
    """
    Descarta cualquier recorte donde aparezca un VEHÍCULO, usando el
    detector genérico de la Semana 1 (entrenado con COCO, no con nuestros
    datos sintéticos). Es crítico: estos recortes se van a usar como fondo
    asumiendo que NO tienen ninguna placa (para ejemplos negativos) o como
    fondo sobre el que se pega una placa sintética — si ya traen un
    vehículo con su placa real sin etiquetar (pasó con una foto de un carro
    en el parqueadero, placa "FHD·707" visible en una esquina), el
    entrenamiento aprendería justo lo contrario de lo que queremos.

    Se usa el detector de VEHÍCULOS, no el de placas propio, a propósito:
    el de placas es justo el que estamos tratando de mejorar porque todavía
    confunde mallas/pavimento con una placa — filtrar con él descartaría de
    más (probado: eliminaba 154 de 176 recortes, la mayoría inocentes). El
    detector de vehículos es un modelo general ya probado, mucho menos
    propenso a falsos positivos sobre texturas como mallas o pavimento.
    """
    from detector import DetectorVehiculos

    # OJO: se probó agregar una tercera pasada con el detector de PLACAS
    # propio (a cualquier umbral razonable) y descartaba la inmensa mayoría
    # de los recortes (156 de 176) — confirma qué tan seguido dispara sobre
    # mallas, pavimento y concreto. Usarlo aquí como filtro sería
    # contraproducente (es justo el modelo que se quiere mejorar), así que
    # se descartó esa idea; solo se usa el detector de VEHÍCULOS (modelo
    # general ya probado) más el filtro de color amarillo.
    print("\nFiltrando recortes que puedan contener un vehículo (y su placa) real...")
    detector_vehiculos = DetectorVehiculos(modo="vehiculos")

    eliminados = 0
    for ruta in list(Path(carpeta).glob("*.jpg")):
        imagen = leer_imagen(ruta)
        if imagen is None:
            continue

        tiene_vehiculo = any(d["confianza"] >= umbral_confianza for d in detector_vehiculos.detectar_en_imagen(imagen))
        tiene_amarillo = _tiene_parche_amarillo_de_placa(imagen)

        if tiene_vehiculo or tiene_amarillo:
            ruta.unlink()
            eliminados += 1

    print(f"Se descartaron {eliminados} recortes por posible vehículo/placa real visible.")
    return eliminados


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extrae fondos reales del video y las fotos para mezclarlos en el dataset sintético.")
    parser.add_argument("--carpeta-salida", type=str, default=str(config.RAIZ / "data" / "fondos_reales"))
    args = parser.parse_args()

    carpeta_salida = Path(args.carpeta_salida)
    carpeta_salida.mkdir(parents=True, exist_ok=True)

    total = 0
    for ruta_video in glob.glob(str(config.DIR_DATA_REALES / "*.mov")) + glob.glob(str(config.DIR_DATA_REALES / "*.mp4")):
        print(f"Extrayendo de video: {Path(ruta_video).name}")
        total += extraer_de_video(ruta_video, carpeta_salida)

    print(f"Extrayendo de fotos en: {config.DIR_DATA_REALES}")
    total += extraer_de_fotos(config.DIR_DATA_REALES, carpeta_salida)

    print(f"\n{total} recortes de fondo real guardados en '{carpeta_salida}' (antes de filtrar).")

    if total > 0:
        eliminados = filtrar_recortes_con_placa(carpeta_salida)
        print(f"Quedan {total - eliminados} recortes de fondo real utilizables.")
    else:
        print("No se encontró video ni fotos en data/reales/ — el generador seguirá usando solo fondos procedurales.")
