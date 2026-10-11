"""
Lectura y escritura de imágenes segura con rutas que tienen tildes o ñ.

Por qué existe este archivo: cv2.imread() y cv2.imwrite() fallan de forma
silenciosa (sin lanzar error, simplemente no leen o no escriben nada) cuando
la ruta contiene caracteres fuera de ASCII, como "ó" o "ñ". En Windows esto
pasa incluso con rutas normales de usuario, por ejemplo si el nombre de la
carpeta de usuario tiene tilde. Como Python sí maneja bien esas rutas, la
solución es leer/escribir los bytes con Python y decodificar/codificar la
imagen con OpenCV a partir de esos bytes, en vez de pasarle la ruta
directamente a OpenCV.

Usa estas funciones en vez de cv2.imread/cv2.imwrite en todo el proyecto.
"""

from pathlib import Path

import cv2
import numpy as np


def leer_imagen(ruta):
    """Reemplazo de cv2.imread() que funciona con cualquier ruta, incluida una con tildes."""
    ruta = Path(ruta)
    datos = np.fromfile(str(ruta), dtype=np.uint8)
    if datos.size == 0:
        return None
    return cv2.imdecode(datos, cv2.IMREAD_COLOR)


def escribir_imagen(ruta, imagen, calidad_jpg=95):
    """Reemplazo de cv2.imwrite() que funciona con cualquier ruta, incluida una con tildes."""
    ruta = Path(ruta)
    extension = ruta.suffix if ruta.suffix else ".jpg"

    parametros = []
    if extension.lower() in (".jpg", ".jpeg"):
        parametros = [cv2.IMWRITE_JPEG_QUALITY, calidad_jpg]

    exito, buffer = cv2.imencode(extension, imagen, parametros)
    if not exito:
        return False

    buffer.tofile(str(ruta))
    return True
