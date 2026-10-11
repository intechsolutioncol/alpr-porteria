"""
Pipeline completo: detector + lector + validador, con votación temporal
para video (Semana 4).

Por qué la votación temporal mejora tanto la precisión: en una foto fija,
una sola lectura mala del OCR arruina el resultado. En video, la misma
placa aparece en decenas de fotogramas mientras el carro pasa. Si en vez de
confiar en un solo fotograma acumulamos las últimas N lecturas y nos
quedamos con la que más se repite, un par de lecturas erróneas (ruido,
reflejo, desenfoque en un instante) quedan "diluidas" por las lecturas
correctas de los demás fotogramas. Es la misma idea que promediar varias
mediciones en un experimento de física en vez de confiar en una sola.
"""

import argparse
import sys
import time
from collections import Counter, deque
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from src.detector import DetectorVehiculos
from src.lector import leer_placa
from src.validador import calcular_confianza, corregir_por_posicion, validar_formato


def procesar_imagen(ruta_imagen, detector=None):
    """
    Corre el pipeline completo (detectar -> leer -> validar) sobre una sola
    imagen. Retorna una lista de resultados, uno por vehículo detectado.
    """
    detector = detector or DetectorVehiculos()
    vehiculos = detector.detectar_vehiculos(ruta_imagen)

    resultados = []
    for vehiculo in vehiculos:
        resultados.append(_leer_y_validar(vehiculo["recorte"], vehiculo))
    return resultados


def _leer_y_validar(recorte, info_extra=None):
    lectura = leer_placa(recorte)
    texto_corregido = corregir_por_posicion(lectura["texto"])
    tipo = validar_formato(texto_corregido)
    confianza_final = calcular_confianza(texto_corregido, lectura["confianza"])

    resultado = {
        "texto_crudo": lectura["texto"],
        "texto_corregido": texto_corregido,
        "tipo": tipo,
        "confianza_ocr": lectura["confianza"],
        "confianza_final": confianza_final,
    }
    if info_extra:
        resultado.update(info_extra)
    return resultado


# ---------------------------------------------------------------------------
# Votación temporal (para video)
# ---------------------------------------------------------------------------


class VotadorTemporal:
    """
    Acumula las últimas N lecturas y decide por votación cuál es la placa
    correcta. También implementa el "enfriamiento": una vez consolidada una
    placa, la ignora por unos segundos para no volver a procesar el mismo
    vehículo mientras sigue frente a la cámara.
    """

    def __init__(self, tamano_ventana=None, segundos_enfriamiento=None):
        self.tamano_ventana = tamano_ventana or config.TAMANO_VENTANA_VOTACION
        self.segundos_enfriamiento = segundos_enfriamiento or config.SEGUNDOS_ENFRIAMIENTO_PLACA
        self.lecturas = deque(maxlen=self.tamano_ventana)
        self._placas_en_enfriamiento = {}  # texto -> momento en que se puede volver a considerar

    def _limpiar_enfriamiento_vencido(self, ahora):
        vencidas = [placa for placa, hasta in self._placas_en_enfriamiento.items() if ahora >= hasta]
        for placa in vencidas:
            del self._placas_en_enfriamiento[placa]

    def agregar_lectura(self, texto, confianza, ahora=None):
        """Agrega una lectura de un fotograma. Ignora textos vacíos y placas en enfriamiento."""
        ahora = ahora if ahora is not None else time.time()
        self._limpiar_enfriamiento_vencido(ahora)

        if not texto or texto in self._placas_en_enfriamiento:
            return

        self.lecturas.append(texto)

    def lectura_mas_frecuente(self):
        """Retorna (texto, veces, proporcion) de la lectura más común en la ventana actual, o None si está vacía."""
        if not self.lecturas:
            return None
        conteo = Counter(self.lecturas)
        texto, veces = conteo.most_common(1)[0]
        proporcion = veces / len(self.lecturas)
        return texto, veces, proporcion

    def consolidar_si_corresponde(self, minimo_votos=None, ahora=None):
        """
        Si la ventana ya tiene suficientes votos para una misma placa, la
        marca como consolidada, la pone en enfriamiento y limpia la ventana.

        Retorna el texto consolidado, o None si todavía no hay consenso
        suficiente.
        """
        minimo_votos = minimo_votos or max(3, self.tamano_ventana // 2)
        resultado = self.lectura_mas_frecuente()
        if resultado is None:
            return None

        texto, veces, _ = resultado
        if veces < minimo_votos:
            return None

        ahora = ahora if ahora is not None else time.time()
        self._placas_en_enfriamiento[texto] = ahora + self.segundos_enfriamiento
        self.lecturas.clear()
        return texto


# ---------------------------------------------------------------------------
# Procesamiento de video / webcam
# ---------------------------------------------------------------------------


def procesar_video(fuente):
    """
    Procesa un archivo de video o una webcam (mismo código para ambos:
    OpenCV solo necesita un índice de cámara en vez de una ruta de archivo).

    Muestra en pantalla la lectura del fotograma actual y, cuando hay
    suficiente consenso, la lectura consolidada. Presiona 'q' para salir.
    """
    captura = cv2.VideoCapture(fuente)
    if not captura.isOpened():
        print(f"ERROR: no se pudo abrir la fuente de video '{fuente}'.")
        print("Si es una webcam, prueba otros índices: 0, 1, 2...")
        return

    detector = DetectorVehiculos()
    votador = VotadorTemporal()
    ultima_consolidada = None

    print("Procesando video. Presiona 'q' en la ventana para salir.")

    while True:
        leido, cuadro = captura.read()
        if not leido:
            break

        vehiculos = detector.detectar_en_imagen(cuadro)

        texto_actual = ""
        if vehiculos:
            resultado = _leer_y_validar(vehiculos[0]["recorte"])
            texto_actual = resultado["texto_corregido"]
            votador.agregar_lectura(texto_actual, resultado["confianza_final"])

            x1, y1, x2, y2 = vehiculos[0]["caja"]
            cv2.rectangle(cuadro, (x1, y1), (x2, y2), (0, 255, 0), 2)

        consolidada = votador.consolidar_si_corresponde()
        if consolidada:
            ultima_consolidada = consolidada

        cv2.putText(cuadro, f"Lectura actual: {texto_actual}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        if ultima_consolidada:
            cv2.putText(cuadro, f"Consolidada: {ultima_consolidada}", (10, 65),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

        cv2.imshow("Pipeline ALPR (q para salir)", cuadro)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    captura.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Corre el pipeline completo sobre una imagen o un video/webcam.")
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--imagen", type=str, help="Ruta a una imagen")
    grupo.add_argument("--video", type=str, help="Ruta a un archivo de video")
    grupo.add_argument("--camara", type=int, help="Índice de la webcam (usualmente 0)")
    args = parser.parse_args()

    if args.imagen:
        resultados = procesar_imagen(args.imagen)
        if not resultados:
            print("No se detectó ningún vehículo en la imagen.")
        for i, r in enumerate(resultados, start=1):
            print(f"Vehículo {i} ({r['clase']}): '{r['texto_corregido']}' "
                  f"(tipo: {r['tipo']}, confianza: {r['confianza_final']:.2f})")
    else:
        fuente = args.video if args.video else args.camara
        procesar_video(fuente)
