"""
Primer experimento formal del proyecto (Semana 3): compara el detector de
vehículos (Semana 1, modelo preentrenado COCO) contra el detector de placas
propio (Semana 3, entrenado con placas sintéticas) sobre el mismo conjunto
de fotos reales, midiendo precisión (tasa de detección) y velocidad.

Nota: el detector de vehículos encuentra el VEHÍCULO, no la placa — para
comparar "manzanas con manzanas" contamos cuántas fotos terminan con la
placa correctamente encuadrada, así que para el enfoque de vehículos
consideramos una detección "exitosa" cuando se encontró el vehículo (el
paso siguiente, leer la placa dentro del recorte, se mide aparte en
probar_ocr_sinteticas.py y en el banco de pruebas de la Semana 8).
"""

import argparse
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # no necesitamos ventana interactiva, solo guardar el PNG
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from src.detector import DetectorVehiculos

EXTENSIONES_IMAGEN = {".jpg", ".jpeg", ".png"}


def listar_imagenes(carpeta):
    carpeta = Path(carpeta)
    return sorted(p for p in carpeta.iterdir() if p.suffix.lower() in EXTENSIONES_IMAGEN)


def evaluar_enfoque(detector, imagenes):
    detecciones_exitosas = 0
    tiempos = []

    for ruta in imagenes:
        inicio = time.perf_counter()
        try:
            resultado = detector.detectar_vehiculos(ruta)
        except (FileNotFoundError, ValueError):
            resultado = []
        tiempos.append(time.perf_counter() - inicio)

        if resultado:
            detecciones_exitosas += 1

    total = len(imagenes)
    tasa_deteccion = (detecciones_exitosas / total * 100) if total else 0.0
    tiempo_promedio = (sum(tiempos) / len(tiempos)) if tiempos else 0.0

    return {
        "detecciones_exitosas": detecciones_exitosas,
        "total": total,
        "tasa_deteccion_pct": tasa_deteccion,
        "tiempo_promedio_seg": tiempo_promedio,
    }


def ejecutar_comparacion(carpeta_imagenes=None, limite=50):
    carpeta_imagenes = Path(carpeta_imagenes or config.DIR_DATA_REALES)
    imagenes = listar_imagenes(carpeta_imagenes)[:limite]

    if not imagenes:
        print(
            f"No hay fotos en '{carpeta_imagenes}'.\n"
            "Este experimento necesita fotos reales de vehículos (ver Verificación "
            "de la Semana 1: toma 10+ fotos con el celular y guárdalas en data/reales/).\n"
            "Sin fotos reales no hay nada que comparar; el script no puede generarlas "
            "por su cuenta (para eso está el generador SINTÉTICO de la Semana 2, que "
            "mide otra cosa: precisión del OCR, no del detector sobre fotos reales)."
        )
        return None

    print(f"Comparando detectores sobre {len(imagenes)} fotos de '{carpeta_imagenes}'...\n")

    print("Evaluando detector de VEHÍCULOS (Semana 1)...")
    detector_vehiculos = DetectorVehiculos(modo="vehiculos")
    resultado_vehiculos = evaluar_enfoque(detector_vehiculos, imagenes)

    print("\nEvaluando detector de PLACAS (Semana 3)...")
    try:
        detector_placas = DetectorVehiculos(modo="placas")
    except FileNotFoundError as error:
        print(f"\n{error}")
        print("No se puede comparar todavía: entrena el modelo propio primero (notebook de Colab).")
        return None
    resultado_placas = evaluar_enfoque(detector_placas, imagenes)

    return {"vehiculos": resultado_vehiculos, "placas": resultado_placas}


def mostrar_y_guardar(resultados, carpeta_resultados=None):
    if resultados is None:
        return

    carpeta_resultados = Path(carpeta_resultados or config.DIR_RESULTADOS)
    carpeta_resultados.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 55)
    print("RESULTADOS")
    print("=" * 55)
    for nombre, r in resultados.items():
        print(f"\n{nombre.upper()}:")
        print(f"  Detecciones exitosas: {r['detecciones_exitosas']}/{r['total']} ({r['tasa_deteccion_pct']:.1f}%)")
        print(f"  Tiempo promedio: {r['tiempo_promedio_seg'] * 1000:.0f} ms/imagen")

    ruta_csv = carpeta_resultados / "comparacion_detectores.csv"
    with open(ruta_csv, "w", newline="", encoding="utf-8") as f:
        f.write("enfoque,tasa_deteccion_pct,tiempo_promedio_ms,total_imagenes\n")
        for nombre, r in resultados.items():
            f.write(f"{nombre},{r['tasa_deteccion_pct']:.2f},{r['tiempo_promedio_seg'] * 1000:.1f},{r['total']}\n")

    nombres = list(resultados.keys())
    tasas = [resultados[n]["tasa_deteccion_pct"] for n in nombres]
    tiempos_ms = [resultados[n]["tiempo_promedio_seg"] * 1000 for n in nombres]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))

    ax1.bar(nombres, tasas, color=["#888888", "#2e8b57"])
    ax1.set_title("Tasa de detección")
    ax1.set_ylabel("% de imágenes con detección exitosa")
    ax1.set_ylim(0, 100)

    ax2.bar(nombres, tiempos_ms, color=["#888888", "#2e8b57"])
    ax2.set_title("Velocidad")
    ax2.set_ylabel("Tiempo promedio por imagen (ms)")

    fig.suptitle("Detector de vehículos (Semana 1) vs. detector de placas propio (Semana 3)")
    fig.tight_layout()

    ruta_png = carpeta_resultados / "comparacion_detectores.png"
    fig.savefig(ruta_png, dpi=150)

    print(f"\nResultados guardados en:\n  - {ruta_csv}\n  - {ruta_png}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compara el detector de vehículos vs. el detector de placas propio.")
    parser.add_argument("--limite", type=int, default=50, help="Máximo de imágenes a usar de data/reales/")
    args = parser.parse_args()

    resultados = ejecutar_comparacion(limite=args.limite)
    mostrar_y_guardar(resultados)
