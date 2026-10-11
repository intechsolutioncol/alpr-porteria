"""
Prueba de precisión de EasyOCR sobre placas sintéticas (Semana 2).

Como generamos las placas sintéticas por código, sabemos exactamente cuál es
el texto correcto de cada una (está en referencia.csv). Eso permite medir la
precisión del OCR sin revisar nada a mano, y además nos dice EXACTAMENTE qué
caracteres confunde más (por ejemplo "8" leído como "B"), información que
alimenta directamente la tabla de corrección de la Semana 4
(config.CONFUSIONES_NUMERO_A_LETRA).

Con --usar-detector (Semana 3): en vez de pasarle al OCR la imagen completa
(placa + margen de fondo, tal como la guarda generador_placas.py), primero
se corre el detector de placas entrenado para recortar SOLO la placa, y
recién ahí se lee. Es la comparación justa de "¿ayudó entrenar el detector
propio?": mismas imágenes, mismo OCR, la única diferencia es si hubo un
recorte ajustado de por medio. Los resultados se guardan con un prefijo
distinto para poder comparar ambos archivos lado a lado sin sobreescribirse.

Con --usar-validador (Semana 4): después de leer el texto, lo pasa por
validador.corregir_por_posicion() usando el "tipo" real de cada placa (columna
del referencia.csv, generada junto con la imagen — no es adivinado). Esta
prueba mide el efecto de la corrección por posición sola: la confusión más
frecuente medida hasta ahora es '0' leído como 'O', que corregir_por_posicion
revierte automáticamente cuando la posición esperada es un número.
"""

import argparse
import csv
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from src.lector import leer_placa
from src.utilidades_imagen import leer_imagen
from src.validador import corregir_por_posicion


def cargar_referencia(carpeta_sinteticas):
    ruta_csv = Path(carpeta_sinteticas) / "referencia.csv"
    if not ruta_csv.exists():
        raise FileNotFoundError(
            f"No se encontró '{ruta_csv}'. Genera primero las placas sintéticas con:\n"
            f"  python src/generador_placas.py --cantidad 200"
        )
    with open(ruta_csv, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def comparar_caracteres(esperado, obtenido):
    """
    Compara carácter por carácter dos textos de la misma posición.

    Retorna (aciertos, comparaciones, lista_de_confusiones). Si las
    longitudes no coinciden, solo se comparan las posiciones que existen en
    ambos (el resto cuenta como comparación fallida sin generar una
    confusión concreta, porque no sabemos a qué posición correspondería).
    """
    aciertos = 0
    confusiones = []
    largo_comun = min(len(esperado), len(obtenido))

    for i in range(largo_comun):
        if esperado[i] == obtenido[i]:
            aciertos += 1
        else:
            confusiones.append((esperado[i], obtenido[i]))

    comparaciones = max(len(esperado), len(obtenido))
    return aciertos, comparaciones, confusiones


def ejecutar_prueba(cantidad, carpeta_sinteticas=None, detector=None, usar_validador=False):
    carpeta_sinteticas = Path(carpeta_sinteticas or config.DIR_DATA_SINTETICAS)
    referencia = cargar_referencia(carpeta_sinteticas)

    if cantidad < len(referencia):
        referencia = referencia[:cantidad]

    if detector is not None:
        print(f"Probando OCR CON detector (recorte de placa) sobre {len(referencia)} placas sintéticas...\n")
    else:
        print(f"Probando OCR sobre {len(referencia)} placas sintéticas (imagen completa, sin detector)...\n")

    resultados = []
    total_confusiones = Counter()
    tiempos = []
    detecciones_fallidas = 0

    for i, fila in enumerate(referencia, start=1):
        ruta_imagen = carpeta_sinteticas / fila["archivo"]
        imagen = leer_imagen(ruta_imagen)
        if imagen is None:
            print(f"  ADVERTENCIA: no se pudo leer '{ruta_imagen}', se omite.")
            continue

        inicio = time.perf_counter()

        if detector is not None:
            detecciones = detector.detectar_en_imagen(imagen)
            if not detecciones:
                detecciones_fallidas += 1
                tiempos.append(time.perf_counter() - inicio)
                resultados.append({
                    "archivo": fila["archivo"], "esperado": fila["texto"], "obtenido": "",
                    "exacto": False, "aciertos_caracteres": 0,
                    "caracteres_comparados": len(fila["texto"]), "confianza_ocr": 0.0,
                })
                continue
            mejor_deteccion = max(detecciones, key=lambda d: d["confianza"])
            imagen_para_ocr = mejor_deteccion["recorte"]
        else:
            imagen_para_ocr = imagen

        lectura = leer_placa(imagen_para_ocr)

        esperado = fila["texto"]
        obtenido = lectura["texto"]

        if usar_validador == "tipo_conocido":
            # Solo para comparar: usa el tipo REAL (columna del referencia.csv)
            # en vez de dejar que el validador lo adivine. Es una cota
            # optimista ("oráculo"), no representa el pipeline real.
            obtenido = corregir_por_posicion(obtenido, tipo=fila["tipo"])
        elif usar_validador:
            # Esto es lo que hace pipeline.py::_leer_y_validar() de verdad:
            # no conoce el tipo de antemano, corregir_por_posicion() prueba
            # ambos formatos y se queda con el que dé un resultado válido.
            obtenido = corregir_por_posicion(obtenido)

        tiempos.append(time.perf_counter() - inicio)

        exacto = obtenido == esperado
        aciertos, comparaciones, confusiones = comparar_caracteres(esperado, obtenido)

        for confusion in confusiones:
            total_confusiones[confusion] += 1

        resultados.append({
            "archivo": fila["archivo"],
            "esperado": esperado,
            "obtenido": obtenido,
            "exacto": exacto,
            "aciertos_caracteres": aciertos,
            "caracteres_comparados": comparaciones,
            "confianza_ocr": round(lectura["confianza"], 3),
        })

        if i % max(1, len(referencia) // 10) == 0:
            print(f"  {i}/{len(referencia)} procesadas...")

    if detecciones_fallidas:
        print(f"  (el detector no encontró placa en {detecciones_fallidas}/{len(referencia)} imágenes)")

    return resultados, total_confusiones, tiempos, detecciones_fallidas


def resumir_y_guardar(resultados, confusiones, tiempos, carpeta_resultados=None, prefijo="ocr_sinteticas", detecciones_fallidas=0):
    carpeta_resultados = Path(carpeta_resultados or config.DIR_RESULTADOS)
    carpeta_resultados.mkdir(parents=True, exist_ok=True)

    total = len(resultados)
    if total == 0:
        print("No hay resultados para resumir (0 placas procesadas).")
        return

    exactos = sum(1 for r in resultados if r["exacto"])
    precision_exacta = exactos / total * 100

    total_aciertos = sum(r["aciertos_caracteres"] for r in resultados)
    total_caracteres = sum(r["caracteres_comparados"] for r in resultados)
    precision_caracter = (total_aciertos / total_caracteres * 100) if total_caracteres else 0.0

    tiempo_promedio = sum(tiempos) / len(tiempos) if tiempos else 0.0

    print("\n" + "=" * 50)
    print("RESULTADOS")
    print("=" * 50)
    print(f"Placas evaluadas:        {total}")
    print(f"Precisión exacta:        {precision_exacta:.1f}%  ({exactos}/{total})")
    print(f"Precisión por carácter:  {precision_caracter:.1f}%")
    print(f"Tiempo promedio/placa:   {tiempo_promedio * 1000:.0f} ms")
    if detecciones_fallidas:
        print(f"Placas sin detección:    {detecciones_fallidas}/{total} (el detector no encontró nada, no se llegó a leer)")

    print("\nTop 10 confusiones (esperado -> leído):")
    top_confusiones = confusiones.most_common(10)
    if not top_confusiones:
        print("  (ninguna: el OCR no cometió errores carácter por carácter)")
    for (esperado, obtenido), veces in top_confusiones:
        print(f"  '{esperado}' -> '{obtenido}'   ({veces} veces)")

    # Guardar resultado detallado por placa
    ruta_detalle = carpeta_resultados / f"{prefijo}_detalle.csv"
    with open(ruta_detalle, "w", newline="", encoding="utf-8") as f:
        campos = ["archivo", "esperado", "obtenido", "exacto", "aciertos_caracteres", "caracteres_comparados", "confianza_ocr"]
        escritor = csv.DictWriter(f, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(resultados)

    # Guardar tabla de confusiones
    ruta_confusiones = carpeta_resultados / f"{prefijo}_confusiones.csv"
    with open(ruta_confusiones, "w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(["caracter_esperado", "caracter_leido", "veces"])
        for (esperado, obtenido), veces in confusiones.most_common():
            escritor.writerow([esperado, obtenido, veces])

    # Guardar resumen general
    ruta_resumen = carpeta_resultados / f"{prefijo}_resumen.csv"
    with open(ruta_resumen, "w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(["metrica", "valor"])
        escritor.writerow(["placas_evaluadas", total])
        escritor.writerow(["precision_exacta_pct", round(precision_exacta, 2)])
        escritor.writerow(["precision_caracter_pct", round(precision_caracter, 2)])
        escritor.writerow(["tiempo_promedio_ms", round(tiempo_promedio * 1000, 1)])
        escritor.writerow(["detecciones_fallidas", detecciones_fallidas])

    print(f"\nResultados guardados en '{carpeta_resultados}':")
    print(f"  - {prefijo}_detalle.csv")
    print(f"  - {prefijo}_confusiones.csv")
    print(f"  - {prefijo}_resumen.csv")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mide la precisión de EasyOCR sobre placas sintéticas.")
    parser.add_argument("--cantidad", type=int, default=200, help="Cuántas placas sintéticas evaluar")
    parser.add_argument(
        "--usar-detector", action="store_true",
        help="Recorta la placa con el detector entrenado (Semana 3) antes de leerla, en vez de usar la imagen completa",
    )
    parser.add_argument(
        "--usar-validador", action="store_true",
        help="Aplica la corrección por posición (Semana 4), igual que hace pipeline.py (sin conocer el tipo carro/moto de antemano)",
    )
    parser.add_argument(
        "--tipo-conocido", action="store_true",
        help="Junto con --usar-validador: usa el tipo real (carro/moto) en vez de dejar que el validador lo adivine. "
             "Da una cota optimista, NO representa el pipeline real — solo para comparar.",
    )
    args = parser.parse_args()

    if args.tipo_conocido and not args.usar_validador:
        parser.error("--tipo-conocido solo tiene sentido junto con --usar-validador")

    detector = None
    partes_prefijo = ["ocr_sinteticas"]
    if args.usar_detector:
        from src.detector import DetectorVehiculos
        detector = DetectorVehiculos(modo="auto")
        partes_prefijo.append("con_detector")
    if args.usar_validador:
        partes_prefijo.append("con_validador_tipo_conocido" if args.tipo_conocido else "con_validador")

    usar_validador = "tipo_conocido" if args.tipo_conocido else args.usar_validador
    prefijo = "_".join(partes_prefijo)

    resultados, confusiones, tiempos, detecciones_fallidas = ejecutar_prueba(
        args.cantidad, detector=detector, usar_validador=usar_validador,
    )
    resumir_y_guardar(resultados, confusiones, tiempos, prefijo=prefijo, detecciones_fallidas=detecciones_fallidas)
