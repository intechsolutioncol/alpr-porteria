"""
Banco de pruebas (Semana 8): experimentos sistemáticos que generan las
tablas y gráficas del póster.

Nota importante sobre los experimentos 1-4: lo ideal es correrlos con FOTOS
REALES tomadas a distancias/ángulos/iluminación controladas (protocolo de
la guía: 30 repeticiones mínimo por condición). Como todavía no hay fotos
reales del carro a escala (Semana 7), estos cuatro experimentos usan el
generador sintético con el parámetro exacto controlado (no un rango
aleatorio), cambiando una sola variable a la vez, tal como pide el
protocolo. Son un sustituto razonable para tener el framework funcionando
de punta a punta; en cuanto existan fotos reales, hay que repetirlos con
ellas y comparar (eso mismo es, otra vez, un resultado interesante para
el póster: ¿qué tanto se parece el mundo sintético al real?).
"""

import argparse
import sys
import time
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from src.detector import DetectorVehiculos
from src.generador_placas import dibujar_placa_base, generar_texto_placa
from src.lector import leer_placa
from src.pipeline import VotadorTemporal
from src import base_datos

REPETICIONES_POR_CONDICION = 30  # mínimo que pide el protocolo de la guía (PARTE D, Semana 8)


# ---------------------------------------------------------------------------
# Variantes controladas (una sola variable a la vez)
# ---------------------------------------------------------------------------


def _con_angulo(imagen, grados):
    alto, ancho = imagen.shape[:2]
    matriz = cv2.getRotationMatrix2D((ancho / 2, alto / 2), grados, 1.0)
    return cv2.warpAffine(imagen, matriz, (ancho, alto), borderMode=cv2.BORDER_REPLICATE)


def _con_iluminacion(imagen, factor_brillo):
    # factor_brillo: -100 (muy oscuro) a +100 (muy sobreexpuesto), 0 = sin cambio
    return cv2.convertScaleAbs(imagen, alpha=1.0, beta=factor_brillo)


def _con_desenfoque_movimiento(imagen, longitud):
    if longitud <= 1:
        return imagen
    longitud = longitud if longitud % 2 == 1 else longitud + 1
    kernel = np.zeros((longitud, longitud))
    kernel[longitud // 2, :] = 1.0 / longitud
    return cv2.filter2D(imagen, -1, kernel)


def _con_distancia_simulada(imagen, factor_escala):
    # factor_escala < 1 = placa más pequeña dentro del cuadro, como si el
    # vehículo estuviera más lejos de la cámara.
    alto, ancho = imagen.shape[:2]
    pequena = cv2.resize(imagen, (max(1, int(ancho * factor_escala)), max(1, int(alto * factor_escala))))
    return cv2.resize(pequena, (ancho, alto))  # se vuelve a agrandar, pero ya se perdió detalle


def _ocr_exacto(texto_esperado, imagen):
    lectura = leer_placa(imagen)
    return lectura["texto"] == texto_esperado


def _correr_experimento_parametrico(nombre, valores, funcion_variante, repeticiones=None):
    """
    Para cada valor del parámetro: genera `repeticiones` placas distintas,
    les aplica la variante controlada, mide el % de lecturas exactas.
    """
    # No se usa REPETICIONES_POR_CONDICION directo como valor por defecto del
    # parámetro porque Python evalúa los valores por defecto UNA sola vez, al
    # definir la función: si luego cambiamos la constante global (--repeticiones
    # en la línea de comandos), ese valor por defecto ya fijado no se enteraría.
    repeticiones = repeticiones or REPETICIONES_POR_CONDICION

    print(f"\nExperimento: {nombre}")
    resultados = []

    for valor in valores:
        aciertos = 0
        for _ in range(repeticiones):
            tipo = "carro" if _ % 2 == 0 else "moto"
            texto = generar_texto_placa(tipo)
            imagen = dibujar_placa_base(texto)
            imagen = funcion_variante(imagen, valor)
            if _ocr_exacto(texto, imagen):
                aciertos += 1

        precision = aciertos / repeticiones * 100
        resultados.append({"valor": valor, "precision_pct": precision})
        print(f"  {valor}: {precision:.1f}%")

    return resultados


def experimento_distancia():
    valores = [1.0, 0.7, 0.5, 0.35, 0.2]  # 1.0 = tamaño original, 0.2 = "muy lejos"
    return _correr_experimento_parametrico("Precisión vs. distancia (simulada)", valores, _con_distancia_simulada)


def experimento_angulo():
    valores = [0, 15, 30, 45, 60]
    return _correr_experimento_parametrico("Precisión vs. ángulo", valores, _con_angulo)


def experimento_iluminacion():
    valores = [-80, -40, 0, 40, 80]
    return _correr_experimento_parametrico("Precisión vs. iluminación", valores, _con_iluminacion)


def experimento_desenfoque():
    valores = [1, 5, 9, 13, 17]
    return _correr_experimento_parametrico("Precisión vs. desenfoque de movimiento", valores, _con_desenfoque_movimiento)


def experimento_carro_vs_moto(repeticiones=None):
    repeticiones = repeticiones or REPETICIONES_POR_CONDICION
    print("\nExperimento: carro vs. moto")
    resultados = []
    for tipo in ("carro", "moto"):
        aciertos = 0
        for _ in range(repeticiones):
            texto = generar_texto_placa(tipo)
            imagen = dibujar_placa_base(texto)
            if _ocr_exacto(texto, imagen):
                aciertos += 1
        precision = aciertos / repeticiones * 100
        resultados.append({"tipo": tipo, "precision_pct": precision})
        print(f"  {tipo}: {precision:.1f}%")
    return resultados


def experimento_votacion_temporal(repeticiones=None, fotogramas_por_video=15):
    """
    Simula un "video": genera la MISMA placa degradada de forma distinta en
    cada fotograma (ruido/desenfoque distintos cada vez, como pasaría con
    una cámara real cuadro a cuadro) y compara UNA lectura contra el
    resultado de acumular varias y votar.
    """
    repeticiones = repeticiones or REPETICIONES_POR_CONDICION
    print("\nExperimento: con votación temporal vs. sin ella")
    import random

    from src.generador_placas import (
        aplicar_brillo_contraste, aplicar_desenfoque_gaussiano,
        aplicar_desenfoque_movimiento, aplicar_ruido,
    )

    # Una cámara real no da fotogramas igual de malos todo el tiempo: la
    # mayoría salen razonablemente nítidos y de vez en cuando uno sale
    # arruinado (el carro se movió justo ahí, un reflejo, etc.). Si TODOS los
    # fotogramas se degradaran igual de fuerte, votar no ayudaría más que una
    # sola lectura (todas serían igual de malas) — por eso se simula esa
    # mezcla realista en vez de aplicar la misma degradación siempre.
    PROBABILIDAD_FOTOGRAMA_MALO = 0.35

    aciertos_sin_votacion = 0
    aciertos_con_votacion = 0

    for _ in range(repeticiones):
        tipo = "carro" if _ % 2 == 0 else "moto"
        texto = generar_texto_placa(tipo)

        votador = VotadorTemporal(tamano_ventana=fotogramas_por_video, segundos_enfriamiento=0)
        primera_lectura = None

        for indice_fotograma in range(fotogramas_por_video):
            imagen = dibujar_placa_base(texto)
            if random.random() < PROBABILIDAD_FOTOGRAMA_MALO:
                imagen = aplicar_ruido(aplicar_desenfoque_movimiento(aplicar_brillo_contraste(imagen)))
            else:
                imagen = aplicar_desenfoque_gaussiano(aplicar_brillo_contraste(imagen, rango_brillo=(-15, 15)))
            lectura = leer_placa(imagen)["texto"]

            if indice_fotograma == 0:
                primera_lectura = lectura

            votador.agregar_lectura(lectura, confianza=0.7, ahora=indice_fotograma)

        if primera_lectura == texto:
            aciertos_sin_votacion += 1

        consolidada = votador.consolidar_si_corresponde(ahora=fotogramas_por_video)
        if consolidada == texto:
            aciertos_con_votacion += 1

    resultados = [
        {"metodo": "una sola lectura", "precision_pct": aciertos_sin_votacion / repeticiones * 100},
        {"metodo": "votación temporal", "precision_pct": aciertos_con_votacion / repeticiones * 100},
    ]
    for r in resultados:
        print(f"  {r['metodo']}: {r['precision_pct']:.1f}%")
    return resultados


def experimento_tiempo_por_etapa(repeticiones=None):
    repeticiones = repeticiones or REPETICIONES_POR_CONDICION
    print("\nExperimento: tiempo de procesamiento por etapa")

    detector = DetectorVehiculos(modo="auto")
    base_datos.crear_tablas()

    tiempos = {"deteccion": [], "ocr": [], "consulta_bd": []}

    for _ in range(repeticiones):
        tipo = "carro" if _ % 2 == 0 else "moto"
        texto = generar_texto_placa(tipo)
        imagen = dibujar_placa_base(texto)

        # "Detección" aquí es sobre la placa ya recortada (no hay un fondo
        # con vehículo real de por medio en este experimento sintético), así
        # que mide el costo de correr el modelo, no de encontrar el objeto.
        inicio = time.perf_counter()
        detector.detectar_en_imagen(imagen)
        tiempos["deteccion"].append(time.perf_counter() - inicio)

        inicio = time.perf_counter()
        leer_placa(imagen)
        tiempos["ocr"].append(time.perf_counter() - inicio)

        inicio = time.perf_counter()
        base_datos.consultar_placa(texto)
        tiempos["consulta_bd"].append(time.perf_counter() - inicio)

    resultados = [
        {"etapa": etapa, "tiempo_promedio_ms": (sum(valores) / len(valores)) * 1000}
        for etapa, valores in tiempos.items()
    ]
    for r in resultados:
        print(f"  {r['etapa']}: {r['tiempo_promedio_ms']:.1f} ms")
    return resultados


# ---------------------------------------------------------------------------
# Guardado de resultados (CSV + PNG)
# ---------------------------------------------------------------------------


def _guardar_csv(nombre_archivo, resultados, carpeta_resultados):
    ruta = carpeta_resultados / nombre_archivo
    campos = list(resultados[0].keys())
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        f.write(",".join(campos) + "\n")
        for fila in resultados:
            f.write(",".join(str(fila[c]) for c in campos) + "\n")
    return ruta


def _graficar_linea(nombre_archivo, resultados, clave_x, clave_y, titulo, etiqueta_x, etiqueta_y, carpeta_resultados):
    fig, ax = plt.subplots(figsize=(6, 4))
    x = [r[clave_x] for r in resultados]
    y = [r[clave_y] for r in resultados]
    ax.plot(x, y, marker="o", color="#2e8b57")
    ax.set_title(titulo)
    ax.set_xlabel(etiqueta_x)
    ax.set_ylabel(etiqueta_y)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    ruta = carpeta_resultados / nombre_archivo
    fig.savefig(ruta, dpi=150)
    plt.close(fig)
    return ruta


def _graficar_barras(nombre_archivo, resultados, clave_x, clave_y, titulo, etiqueta_x, etiqueta_y, carpeta_resultados):
    fig, ax = plt.subplots(figsize=(6, 4))
    x = [str(r[clave_x]) for r in resultados]
    y = [r[clave_y] for r in resultados]
    ax.bar(x, y, color="#2e8b57")
    ax.set_title(titulo)
    ax.set_xlabel(etiqueta_x)
    ax.set_ylabel(etiqueta_y)
    fig.tight_layout()
    ruta = carpeta_resultados / nombre_archivo
    fig.savefig(ruta, dpi=150)
    plt.close(fig)
    return ruta


EXPERIMENTOS = {
    "distancia": (experimento_distancia, "valor", "precision_pct", "Precisión vs. distancia (simulada)", "Factor de escala de la placa (1.0 = tamaño real)", "Precisión exacta (%)", "linea"),
    "angulo": (experimento_angulo, "valor", "precision_pct", "Precisión vs. ángulo", "Ángulo de inclinación (grados)", "Precisión exacta (%)", "linea"),
    "iluminacion": (experimento_iluminacion, "valor", "precision_pct", "Precisión vs. iluminación", "Ajuste de brillo (-80 oscuro, +80 sobreexpuesto)", "Precisión exacta (%)", "linea"),
    "desenfoque": (experimento_desenfoque, "valor", "precision_pct", "Precisión vs. desenfoque de movimiento", "Longitud del kernel de desenfoque (px)", "Precisión exacta (%)", "linea"),
    "carro_vs_moto": (experimento_carro_vs_moto, "tipo", "precision_pct", "Precisión: carro vs. moto", "Tipo de vehículo", "Precisión exacta (%)", "barras"),
    "votacion_temporal": (experimento_votacion_temporal, "metodo", "precision_pct", "Con votación temporal vs. sin ella", "Método", "Precisión exacta (%)", "barras"),
    "tiempo_por_etapa": (experimento_tiempo_por_etapa, "etapa", "tiempo_promedio_ms", "Tiempo de procesamiento por etapa", "Etapa del pipeline", "Tiempo promedio (ms)", "barras"),
}


def ejecutar_todos(nombres=None, carpeta_resultados=None, repeticiones=None):
    carpeta_resultados = Path(carpeta_resultados or config.DIR_RESULTADOS)
    carpeta_resultados.mkdir(parents=True, exist_ok=True)
    nombres = nombres or list(EXPERIMENTOS.keys())

    global REPETICIONES_POR_CONDICION
    if repeticiones is not None:
        REPETICIONES_POR_CONDICION = repeticiones

    for nombre in nombres:
        funcion, clave_x, clave_y, titulo, etiqueta_x, etiqueta_y, tipo_grafica = EXPERIMENTOS[nombre]
        resultados = funcion()

        ruta_csv = _guardar_csv(f"experimento_{nombre}.csv", resultados, carpeta_resultados)
        graficar = _graficar_linea if tipo_grafica == "linea" else _graficar_barras
        ruta_png = graficar(f"experimento_{nombre}.png", resultados, clave_x, clave_y, titulo, etiqueta_x, etiqueta_y, carpeta_resultados)

        print(f"  Guardado: {ruta_csv.name}, {ruta_png.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Corre los experimentos del banco de pruebas (Semana 8).")
    parser.add_argument(
        "--experimentos", nargs="+", choices=list(EXPERIMENTOS.keys()) + ["todos"], default=["todos"],
        help="Qué experimentos correr (por defecto: todos)",
    )
    parser.add_argument(
        "--repeticiones", type=int, default=None,
        help=f"Repeticiones por condición (por defecto {REPETICIONES_POR_CONDICION}, el mínimo del protocolo; "
             "usa un número bajo solo para probar rápido que el script funciona)",
    )
    args = parser.parse_args()

    nombres = list(EXPERIMENTOS.keys()) if "todos" in args.experimentos else args.experimentos
    ejecutar_todos(nombres, repeticiones=args.repeticiones)
