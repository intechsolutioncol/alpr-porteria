"""
Corre el pipeline completo (detector + lector + validador) sobre las fotos
reales de data/reales/ y arma un mosaico anotado para revisión visual.

A diferencia de probar_ocr_sinteticas.py, aquí NO hay un texto de
referencia conocido de antemano (son fotos reales, nadie las etiquetó a
mano) — este script no calcula un porcentaje de precisión automático, es
una herramienta de inspección visual: para cada foto, dibuja la caja que
encontró el detector y el texto que leyó el OCR, y guarda el mosaico en
resultados/ para poder revisarlo de un vistazo.
"""

import argparse
import glob
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from src.detector import DetectorVehiculos
from src.pipeline import _leer_y_validar
from src.utilidades_imagen import escribir_imagen, leer_imagen

EXTENSIONES_IMAGEN = {".jpg", ".jpeg", ".png"}


def probar_carpeta(carpeta_reales=None, carpeta_resultados=None, ancho_miniatura=300):
    carpeta_reales = Path(carpeta_reales or config.DIR_DATA_REALES)
    carpeta_resultados = Path(carpeta_resultados or config.DIR_RESULTADOS)
    carpeta_resultados.mkdir(parents=True, exist_ok=True)

    rutas = sorted(p for p in carpeta_reales.iterdir() if p.suffix.lower() in EXTENSIONES_IMAGEN)
    if not rutas:
        print(f"No hay fotos en '{carpeta_reales}'.")
        return None

    detector = DetectorVehiculos(modo="placas")
    miniaturas = []

    for ruta in rutas:
        imagen = leer_imagen(ruta)
        if imagen is None:
            print(f"  ADVERTENCIA: no se pudo leer '{ruta.name}', se omite.")
            continue

        detecciones = detector.detectar_en_imagen(imagen)
        etiqueta = "SIN DETECCION"

        if detecciones:
            mejor = max(detecciones, key=lambda d: d["confianza"])
            x1, y1, x2, y2 = mejor["caja"]
            cv2.rectangle(imagen, (x1, y1), (x2, y2), (0, 255, 0), 8)

            resultado = _leer_y_validar(mejor["recorte"])
            etiqueta = f"{resultado['texto_corregido']} ({resultado['confianza_final']:.2f})"
            cv2.putText(imagen, etiqueta, (x1, max(y1 - 20, 40)),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 4)

            # También se guarda el ancho/alto de la caja como % de la imagen:
            # una caja que ocupa casi todo el ancho probablemente no es un
            # recorte ajustado a la placa (ver BITACORA_EXPERIMENTOS.md,
            # hallazgo sobre la brecha sintético-real).
            porcentaje_ancho = (x2 - x1) / imagen.shape[1] * 100
            print(f"{ruta.name} -> {etiqueta}  [caja: {porcentaje_ancho:.0f}% del ancho de la imagen]")
        else:
            cv2.putText(imagen, etiqueta, (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 4)
            print(f"{ruta.name} -> {etiqueta}")

        alto_mini = int(ancho_miniatura * imagen.shape[0] / imagen.shape[1])
        miniaturas.append(cv2.resize(imagen, (ancho_miniatura, alto_mini)))

    alto_max = max(m.shape[0] for m in miniaturas)
    columnas = 4
    filas = (len(miniaturas) + columnas - 1) // columnas
    mosaico = np.full((filas * alto_max, columnas * ancho_miniatura, 3), 255, dtype=np.uint8)
    for i, m in enumerate(miniaturas):
        f, c = divmod(i, columnas)
        mosaico[f * alto_max:f * alto_max + m.shape[0], c * ancho_miniatura:c * ancho_miniatura + ancho_miniatura] = m

    ruta_mosaico = carpeta_resultados / "mosaico_fotos_reales.jpg"
    escribir_imagen(ruta_mosaico, mosaico)
    print(f"\nMosaico guardado en '{ruta_mosaico}'.")
    return ruta_mosaico


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prueba el pipeline sobre las fotos reales y arma un mosaico anotado.")
    parser.add_argument("--carpeta", type=str, default=None, help="Carpeta con fotos reales (por defecto: data/reales)")
    args = parser.parse_args()

    probar_carpeta(carpeta_reales=args.carpeta)
