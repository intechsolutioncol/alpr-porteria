"""
Demo de respaldo (Semana 9): reproduce una secuencia pregrabada mostrando el
sistema funcionando, por si la demostración en vivo falla el día de la
feria (luz distinta, cable desconectado, portátil que se suspende...).

Cómo funciona: la PRIMERA vez que se corre sobre un video, procesa cada
fotograma con el pipeline completo (detector + lector + validador +
autorización) y guarda el resultado de cada fotograma en un archivo JSON
al lado del video. Las siguientes veces, en vez de volver a correr el
reconocimiento (lento, ~1-8 segundos por fotograma en CPU), simplemente
reproduce el video leyendo ese JSON: instantáneo y 100% reproducible, sin
depender de que el reconocimiento en vivo salga bien justo en ese momento.

Uso:
    python pruebas/demo_grabada.py --grabar ruta/al/video.mp4   (una sola vez, con tiempo)
    python pruebas/demo_grabada.py                              (el día de la feria)
"""

import argparse
import json
import sys
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from src import autorizacion
from src.detector import DetectorVehiculos
from src.pipeline import VotadorTemporal, _leer_y_validar

CARPETA_DEMO = config.DIR_DATA_REALES / "demo"
VIDEO_DEMO = CARPETA_DEMO / "demo_grabada.mp4"
CACHE_DEMO = CARPETA_DEMO / "demo_grabada_resultados.json"


def procesar_y_guardar_cache(ruta_video):
    """Corre el pipeline completo sobre el video y guarda un resultado por fotograma."""
    detector = DetectorVehiculos(modo="auto")
    votador = VotadorTemporal()

    captura = cv2.VideoCapture(str(ruta_video))
    if not captura.isOpened():
        raise FileNotFoundError(f"No se pudo abrir el video '{ruta_video}'.")

    resultados_por_fotograma = []
    total_fotogramas = int(captura.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"Procesando {total_fotogramas} fotogramas (esto se hace una sola vez)...")

    indice = 0
    ultima_consolidada = None
    inicio = time.perf_counter()

    while True:
        leido, cuadro = captura.read()
        if not leido:
            break

        vehiculos = detector.detectar_en_imagen(cuadro)
        cajas = [v["caja"] for v in vehiculos]
        texto_actual = ""

        if vehiculos:
            lectura = _leer_y_validar(vehiculos[0]["recorte"])
            texto_actual = lectura["texto_corregido"]
            votador.agregar_lectura(texto_actual, lectura["confianza_final"])

        consolidada = votador.consolidar_si_corresponde()
        if consolidada:
            ultima_consolidada = consolidada

        resultados_por_fotograma.append({
            "cajas": cajas,
            "texto_actual": texto_actual,
            "consolidada": ultima_consolidada,
        })

        indice += 1
        if indice % 20 == 0:
            print(f"  {indice}/{total_fotogramas}")

    captura.release()
    print(f"Procesamiento completo en {time.perf_counter() - inicio:.1f} segundos.")

    with open(CACHE_DEMO, "w", encoding="utf-8") as f:
        json.dump(resultados_por_fotograma, f, ensure_ascii=False)

    print(f"Cache guardado en '{CACHE_DEMO}'. Ya puedes correr la demo sin --grabar.")
    return resultados_por_fotograma


def reproducir_demo():
    if not VIDEO_DEMO.exists():
        print(
            f"No se encontró el video de demo en '{VIDEO_DEMO}'.\n\n"
            "Cómo prepararlo:\n"
            f"  1. Graba un video corto del carro a escala pasando frente a la cámara,\n"
            f"     y guárdalo como '{VIDEO_DEMO}'.\n"
            "  2. Corre: python pruebas/demo_grabada.py --grabar\n"
            "  3. Desde ese momento, correr este script sin argumentos reproduce la demo."
        )
        return

    if not CACHE_DEMO.exists():
        print("Existe el video pero todavía no se procesó. Procesando ahora (una sola vez)...")
        procesar_y_guardar_cache(VIDEO_DEMO)

    with open(CACHE_DEMO, encoding="utf-8") as f:
        resultados_por_fotograma = json.load(f)

    captura = cv2.VideoCapture(str(VIDEO_DEMO))
    print("Reproduciendo demo grabada. Presiona 'q' para salir.")

    for resultado in resultados_por_fotograma:
        leido, cuadro = captura.read()
        if not leido:
            break

        for x1, y1, x2, y2 in resultado["cajas"]:
            cv2.rectangle(cuadro, (x1, y1), (x2, y2), (0, 255, 0), 2)

        cv2.putText(cuadro, f"Lectura actual: {resultado['texto_actual']}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        if resultado["consolidada"]:
            cv2.putText(cuadro, f"Consolidada: {resultado['consolidada']}", (10, 65),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

        cv2.imshow("Demo grabada ALPR (q para salir)", cuadro)
        if cv2.waitKey(33) & 0xFF == ord("q"):  # ~30 fps
            break

    captura.release()
    cv2.destroyAllWindows()

    if resultados_por_fotograma:
        consolidada_final = next(
            (r["consolidada"] for r in reversed(resultados_por_fotograma) if r["consolidada"]),
            None,
        )
        if consolidada_final:
            resultado_autorizacion = autorizacion.evaluar_ingreso(consolidada_final, 0.9)
            print(f"\nResultado final de la demo: {resultado_autorizacion['mensaje']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reproduce (o graba) la demo de respaldo.")
    parser.add_argument("--grabar", action="store_true", help="Procesa el video y guarda el cache antes de la feria")
    args = parser.parse_args()

    CARPETA_DEMO.mkdir(parents=True, exist_ok=True)

    if args.grabar:
        if not VIDEO_DEMO.exists():
            print(f"Primero coloca el video en '{VIDEO_DEMO}'.")
            sys.exit(1)
        procesar_y_guardar_cache(VIDEO_DEMO)
    else:
        reproducir_demo()
