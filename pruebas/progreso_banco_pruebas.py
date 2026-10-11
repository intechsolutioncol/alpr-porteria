"""
Muestra el progreso del banco de pruebas (pruebas/banco_pruebas.py) mientras
corre en segundo plano.

Por qué no se puede leer el progreso línea por línea en vivo: cuando la
salida de un script de Python se redirige a un archivo (en vez de mostrarse
en una terminal interactiva), Python guarda las líneas en un búfer y solo
las escribe al archivo cuando ese búfer se llena o el programa termina. Eso
significa que el archivo de log de banco_pruebas.py puede quedarse "vacío"
durante minutos aunque el script sí esté avanzando.

Lo que SÍ es una señal confiable: cada experimento escribe su archivo
resultados/experimento_<nombre>.csv apenas termina, ni un segundo antes. Así
que este script calcula qué porcentaje del trabajo total ya se hizo
contando cuántas llamadas al OCR representó cada experimento (el OCR en CPU
es, por lejos, la parte más lenta de todo el pipeline — ver
resultados/experimento_tiempo_por_etapa.csv una vez exista), y con eso arma
una barra de progreso ponderada, no solo "cuántos experimentos de 7".
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

# Debe coincidir con el orden real de ejecución en banco_pruebas.py
# (diccionario EXPERIMENTOS) y con cuántas llamadas al OCR hace cada uno,
# para ponderar el progreso por trabajo real en vez de "1 de 7 = 14%".
REPETICIONES_POR_CONDICION = 30  # debe coincidir con banco_pruebas.py si se corrió con el valor por defecto

PLAN_EXPERIMENTOS = [
    ("distancia", 5 * REPETICIONES_POR_CONDICION),
    ("angulo", 5 * REPETICIONES_POR_CONDICION),
    ("iluminacion", 5 * REPETICIONES_POR_CONDICION),
    ("desenfoque", 5 * REPETICIONES_POR_CONDICION),
    ("carro_vs_moto", 2 * REPETICIONES_POR_CONDICION),
    ("votacion_temporal", 15 * REPETICIONES_POR_CONDICION),  # 15 fotogramas por repetición
    ("tiempo_por_etapa", 1 * REPETICIONES_POR_CONDICION),
]

TOTAL_LLAMADAS_OCR = sum(llamadas for _, llamadas in PLAN_EXPERIMENTOS)


def calcular_progreso(carpeta_resultados=None):
    carpeta_resultados = Path(carpeta_resultados or config.DIR_RESULTADOS)

    llamadas_completadas = 0
    estado_por_experimento = []

    for nombre, llamadas in PLAN_EXPERIMENTOS:
        terminado = (carpeta_resultados / f"experimento_{nombre}.csv").exists()
        if terminado:
            llamadas_completadas += llamadas
        estado_por_experimento.append((nombre, terminado))

    fraccion = llamadas_completadas / TOTAL_LLAMADAS_OCR
    return fraccion, estado_por_experimento


def _barra(fraccion, ancho=40):
    llenas = int(fraccion * ancho)
    return "█" * llenas + "░" * (ancho - llenas)


def mostrar_progreso(tiempo_inicio_estimado=None):
    fraccion, estado_por_experimento = calcular_progreso()

    print("Progreso del banco de pruebas (Semana 8)")
    print(f"[{_barra(fraccion)}] {fraccion * 100:.1f}%\n")

    for nombre, terminado in estado_por_experimento:
        icono = "✅" if terminado else ("⏳" if fraccion > 0 and not terminado else "⬜")
        print(f"  {icono} {nombre}")

    if tiempo_inicio_estimado and 0 < fraccion < 1:
        transcurrido = time.time() - tiempo_inicio_estimado
        estimado_total = transcurrido / fraccion
        restante = estimado_total - transcurrido
        print(f"\nTiempo transcurrido: {transcurrido / 60:.0f} min")
        print(f"Tiempo restante estimado: {restante / 60:.0f} min")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Muestra el % de avance del banco de pruebas en segundo plano.")
    parser.add_argument(
        "--inicio-epoch", type=float, default=None,
        help="Marca de tiempo (segundos, time.time()) de cuándo arrancó banco_pruebas.py, para estimar tiempo restante",
    )
    args = parser.parse_args()

    mostrar_progreso(tiempo_inicio_estimado=args.inicio_epoch)
