"""
Consolida todos los resultados de resultados/ en un solo informe HTML
(Semana 8), con tablas, gráficas y una conclusión automática por
experimento (por ejemplo: "la precisión cae por debajo del 70% a partir de
los 45 grados de inclinación").

Para exportarlo a PDF (pedirlo la guía para el informe de la feria): abre
el archivo HTML generado en el navegador y usa "Imprimir → Guardar como
PDF". No agregamos una librería nueva al proyecto solo para generar PDF
directamente, porque el navegador ya lo resuelve sin dependencias extra.
"""

import base64
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

UMBRAL_PRECISION_ACEPTABLE = 70.0  # el mismo criterio de "mínimo aceptable" de la guía (PARTE G)


def _imagen_a_base64(ruta_png):
    with open(ruta_png, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _tabla_html(df):
    return df.to_html(index=False, classes="tabla-datos", border=0)


def _conclusion_parametrica(nombre_amigable, df, clave_x, unidad_x=""):
    """Para experimentos tipo 'precisión vs. algo': dice a partir de qué valor cae por debajo del umbral."""
    bajo_umbral = df[df["precision_pct"] < UMBRAL_PRECISION_ACEPTABLE]
    if bajo_umbral.empty:
        return (
            f"La precisión se mantuvo por encima del {UMBRAL_PRECISION_ACEPTABLE:.0f}% "
            f"en todo el rango de {nombre_amigable} probado."
        )
    primer_valor_malo = bajo_umbral.iloc[0][clave_x]
    return (
        f"La precisión cae por debajo del {UMBRAL_PRECISION_ACEPTABLE:.0f}% a partir de "
        f"{nombre_amigable} = {primer_valor_malo}{unidad_x}."
    )


def _conclusion_comparativa(df, clave_categoria, clave_valor, mayor_es_mejor=True):
    fila_mejor = df.loc[df[clave_valor].idxmax() if mayor_es_mejor else df[clave_valor].idxmin()]
    fila_peor = df.loc[df[clave_valor].idxmin() if mayor_es_mejor else df[clave_valor].idxmax()]
    diferencia = abs(fila_mejor[clave_valor] - fila_peor[clave_valor])
    return (
        f"'{fila_mejor[clave_categoria]}' superó a '{fila_peor[clave_categoria]}' "
        f"por {diferencia:.1f} puntos."
    )


# Cada entrada: (nombre de archivo csv, título, tipo de conclusión, argumentos extra)
EXPERIMENTOS_CONOCIDOS = [
    ("experimento_distancia.csv", "Precisión vs. distancia (simulada)", "parametrica", {"nombre_amigable": "el factor de escala", "unidad_x": ""}),
    ("experimento_angulo.csv", "Precisión vs. ángulo", "parametrica", {"nombre_amigable": "el ángulo", "unidad_x": "°"}),
    ("experimento_iluminacion.csv", "Precisión vs. iluminación", "parametrica", {"nombre_amigable": "el ajuste de brillo", "unidad_x": ""}),
    ("experimento_desenfoque.csv", "Precisión vs. desenfoque de movimiento", "parametrica", {"nombre_amigable": "la longitud de desenfoque", "unidad_x": "px"}),
    ("experimento_carro_vs_moto.csv", "Carro vs. moto", "comparativa", {"clave_categoria": "tipo", "clave_valor": "precision_pct"}),
    ("experimento_votacion_temporal.csv", "Con votación temporal vs. sin ella", "comparativa", {"clave_categoria": "metodo", "clave_valor": "precision_pct"}),
    ("experimento_tiempo_por_etapa.csv", "Tiempo de procesamiento por etapa", "comparativa", {"clave_categoria": "etapa", "clave_valor": "tiempo_promedio_ms", "mayor_es_mejor": False}),
    ("comparacion_detectores.csv", "Detector de vehículos vs. detector de placas propio (Semana 3)", "comparativa", {"clave_categoria": "enfoque", "clave_valor": "tasa_deteccion_pct"}),
]

ESTILO = """
<style>
  body { font-family: Arial, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; color: #222; }
  h1 { border-bottom: 3px solid #2e8b57; padding-bottom: 0.5rem; }
  h2 { color: #2e8b57; margin-top: 3rem; }
  .conclusion { background: #eaf6ec; border-left: 4px solid #2e8b57; padding: 0.8rem 1rem; margin: 1rem 0; }
  .tabla-datos { border-collapse: collapse; width: 100%; margin: 1rem 0; }
  .tabla-datos th, .tabla-datos td { border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: right; }
  .tabla-datos th { background: #f0f0f0; }
  img { max-width: 100%; margin: 1rem 0; border: 1px solid #ddd; }
  .aviso { color: #8a6d00; }
</style>
"""


def generar_informe(carpeta_resultados=None, ruta_salida=None):
    carpeta_resultados = Path(carpeta_resultados or config.DIR_RESULTADOS)
    ruta_salida = Path(ruta_salida or (carpeta_resultados / "informe.html"))

    secciones_html = []
    algo_encontrado = False

    for nombre_csv, titulo, tipo_conclusion, argumentos in EXPERIMENTOS_CONOCIDOS:
        ruta_csv = carpeta_resultados / nombre_csv
        if not ruta_csv.exists():
            continue

        algo_encontrado = True
        df = pd.read_csv(ruta_csv)

        if tipo_conclusion == "parametrica":
            conclusion = _conclusion_parametrica(df=df, clave_x="valor", **argumentos)
        else:
            conclusion = _conclusion_comparativa(df, **argumentos)

        ruta_png = ruta_csv.with_suffix(".png")
        html_imagen = ""
        if ruta_png.exists():
            b64 = _imagen_a_base64(ruta_png)
            html_imagen = f'<img src="data:image/png;base64,{b64}" alt="{titulo}">'

        secciones_html.append(f"""
        <h2>{titulo}</h2>
        {html_imagen}
        {_tabla_html(df)}
        <div class="conclusion"><strong>Conclusión automática:</strong> {conclusion}</div>
        """)

    # Todas las variantes de la prueba de OCR sobre sintéticas (imagen
    # completa / con detector / con validador / combinadas). Cada una tiene
    # un esquema distinto (metrica,valor) al de los experimentos del banco
    # de pruebas, así que se arma una sola tabla comparativa aparte en vez
    # de tratarlas como los demás experimentos.
    _ETIQUETAS_VARIANTES_OCR = {
        "ocr_sinteticas": "Imagen completa (línea base)",
        "ocr_sinteticas_con_detector": "Con detector (Semana 3)",
        "ocr_sinteticas_con_validador": "Con validador (Semana 4, pipeline real)",
        "ocr_sinteticas_con_detector_con_validador": "Con detector + validador (pipeline real)",
        "ocr_sinteticas_con_validador_tipo_conocido": "Con validador (tipo conocido — cota optimista, NO representa el pipeline real)",
        "ocr_sinteticas_con_detector_con_validador_tipo_conocido": "Con detector + validador (tipo conocido — cota optimista, NO representa el pipeline real)",
    }
    filas_comparacion_ocr = []
    for prefijo, etiqueta in _ETIQUETAS_VARIANTES_OCR.items():
        ruta = carpeta_resultados / f"{prefijo}_resumen.csv"
        if not ruta.exists():
            continue
        df_variante = pd.read_csv(ruta).set_index("metrica")["valor"]
        filas_comparacion_ocr.append({
            "variante": etiqueta,
            "precision_exacta_pct": df_variante.get("precision_exacta_pct"),
            "precision_caracter_pct": df_variante.get("precision_caracter_pct"),
            "tiempo_promedio_ms": df_variante.get("tiempo_promedio_ms"),
        })

    if filas_comparacion_ocr:
        algo_encontrado = True
        df_comparacion = pd.DataFrame(filas_comparacion_ocr)

        # Las variantes "tipo conocido" son una cota optimista de referencia,
        # no una configuración real del pipeline — se excluyen de "mejor
        # configuración real" para no recomendar por error algo que el
        # sistema no puede hacer en producción (no conoce el tipo de antemano).
        df_real = df_comparacion[~df_comparacion["variante"].str.contains("tipo conocido")]
        mejor = df_real.loc[df_real["precision_exacta_pct"].idxmax()]
        peor = df_real.loc[df_real["precision_exacta_pct"].idxmin()]
        conclusion_ocr = (
            f"Entre las configuraciones que el pipeline puede correr de verdad, "
            f"'{mejor['variante']}' fue la mejor ({mejor['precision_exacta_pct']:.1f}% de "
            f"precisión exacta), {mejor['precision_exacta_pct'] - peor['precision_exacta_pct']:.1f} "
            f"puntos por encima de '{peor['variante']}' ({peor['precision_exacta_pct']:.1f}%). "
            f"Las filas marcadas \"tipo conocido\" son una cota optimista de referencia (usan "
            f"el tipo real carro/moto en vez de dejar que el sistema lo adivine) y no representan "
            f"una configuración que el sistema pueda usar en producción."
        )
        secciones_html.insert(0, f"""
        <h2>Comparación de configuraciones de OCR sobre placas sintéticas</h2>
        {_tabla_html(df_comparacion)}
        <div class="conclusion"><strong>Conclusión automática:</strong> {conclusion_ocr}</div>
        """)

    if not algo_encontrado:
        print(
            f"No se encontraron resultados en '{carpeta_resultados}'.\n"
            "Corre primero pruebas/probar_ocr_sinteticas.py y/o pruebas/banco_pruebas.py."
        )
        return None

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Informe de resultados — ALPR Portería</title>
{ESTILO}
</head>
<body>
<h1>Informe de resultados — Sistema ALPR Portería</h1>
<p>Generado automáticamente el {datetime.now().strftime('%Y-%m-%d %H:%M')}.</p>
<p class="aviso">Los experimentos de distancia, ángulo, iluminación y desenfoque de esta
versión usan placas SINTÉTICAS con el parámetro controlado (ver pruebas/banco_pruebas.py).
Repetir con fotos reales del carro a escala en cuanto estén disponibles (Semana 7) y comparar.</p>
{"".join(secciones_html)}
</body>
</html>
"""

    with open(ruta_salida, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Informe generado en '{ruta_salida}'.")
    print("Para exportarlo a PDF: ábrelo en el navegador y usa Imprimir -> Guardar como PDF.")
    return ruta_salida


if __name__ == "__main__":
    generar_informe()
