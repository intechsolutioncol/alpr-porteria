"""
Lector de caracteres de placa con EasyOCR (Semana 1).

Por qué "instancia única": EasyOCR carga varios modelos de redes neuronales
al inicializarse, lo cual toma unos segundos. Si creáramos un lector nuevo
por cada placa a leer, el programa pasaría la mayor parte del tiempo
recargando modelos en vez de leyendo placas. Por eso este módulo guarda una
sola instancia (patrón "singleton") y la reutiliza en cada llamada.
"""

import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from utilidades_imagen import leer_imagen

_lector_easyocr = None  # instancia única, se crea la primera vez que se necesita


def _obtener_lector():
    """Crea el lector de EasyOCR la primera vez que se llama; luego lo reutiliza."""
    global _lector_easyocr

    if _lector_easyocr is None:
        try:
            import easyocr
        except ImportError:
            print(
                "ERROR: no está instalada la librería 'easyocr'.\n"
                "Activa el entorno virtual (.venv) y ejecuta:\n"
                "  pip install -r requirements.txt"
            )
            sys.exit(1)

        print("Inicializando EasyOCR...")
        print(
            "(La primera vez descarga sus modelos de reconocimiento, "
            "unos 100 MB. Puede tardar uno o dos minutos; no está colgado.)"
        )
        _lector_easyocr = easyocr.Reader(["en"], gpu=False)
        print("EasyOCR listo.")

    return _lector_easyocr


def _preprocesar(recorte):
    """
    Prepara el recorte de la placa para que EasyOCR la lea mejor.

    Pasos y por qué ayudan cada uno:
    1. Escala de grises: el color no aporta información para leer texto y
       solo agrega ruido a la red neuronal del OCR.
    2. Reescalado a un ancho absoluto fijo (config.ANCHO_OBJETIVO_OCR): sin
       importar si la entrada es la imagen completa o un recorte ajustado
       del detector, el OCR siempre recibe la misma resolución final. Si se
       usara un multiplicador (p.ej. "agrandar 3x"), un recorte más chico
       terminaría con MENOS píxeles absolutos que la imagen completa, y el
       OCR perdería detalle justo en el caso donde el recorte debería
       ayudar más (ver el comentario en config.py junto a esta constante).
    3. CLAHE (ecualización de contraste adaptativa): reparte mejor los
       niveles de gris en zonas de la imagen con poca luz o reflejos,
       sin "quemar" el resto de la imagen como haría un ajuste de
       contraste global.
    """
    if recorte is None or recorte.size == 0:
        raise ValueError("El recorte de la placa está vacío.")

    gris = cv2.cvtColor(recorte, cv2.COLOR_BGR2GRAY)

    factor = config.ANCHO_OBJETIVO_OCR / gris.shape[1]
    ancho = config.ANCHO_OBJETIVO_OCR
    alto = max(1, int(gris.shape[0] * factor))
    interpolacion = cv2.INTER_CUBIC if factor >= 1 else cv2.INTER_AREA
    agrandada = cv2.resize(gris, (ancho, alto), interpolation=interpolacion)

    clahe = cv2.createCLAHE(
        clipLimit=config.CLAHE_LIMITE_CLIP,
        tileGridSize=config.CLAHE_TAMANO_GRILLA,
    )
    con_contraste = clahe.apply(agrandada)

    return con_contraste


def leer_placa(imagen_recorte):
    """
    Lee el texto de una placa a partir del recorte de un vehículo o de la placa.

    Parámetros
    ----------
    imagen_recorte : np.ndarray
        Imagen (formato OpenCV/BGR) que contiene la placa, idealmente ya
        recortada de forma ajustada.

    Retorna
    -------
    dict con:
        - "texto": el texto leído, en mayúsculas y sin espacios (puede ser "")
        - "confianza": confianza promedio del OCR (0.0 a 1.0)
    """
    lector = _obtener_lector()
    procesada = _preprocesar(imagen_recorte)

    detecciones = lector.readtext(
        procesada,
        allowlist=config.ALFABETO_OCR,
        detail=1,
    )

    if not detecciones:
        return {"texto": "", "confianza": 0.0}

    # Muchas placas colombianas reales traen el nombre de la ciudad como
    # texto pequeño debajo del número (ej. "HOP·198" con "LA ESTRELLA"
    # debajo). A este proyecto solo le interesa el número de la placa, NO
    # la ciudad. El punto separador de en medio a veces hace que EasyOCR
    # detecte el número mismo como dos fragmentos ("HOP" y "198") en vez de
    # uno solo — por eso no basta con quedarse con "el fragmento más
    # grande"; hay que quedarse con TODOS los fragmentos de altura similar
    # al más alto (probablemente todos son parte del número, sin importar
    # si quedaron partidos) y descartar solo los mucho más chicos (la
    # ciudad, siempre impresa en letra bastante más pequeña).
    def _alto_bbox(deteccion):
        ys = [punto[1] for punto in deteccion[0]]
        return max(ys) - min(ys)

    def _x_izquierda_bbox(deteccion):
        return min(punto[0] for punto in deteccion[0])

    alto_maximo = max(_alto_bbox(d) for d in detecciones)
    UMBRAL_ALTO_RELATIVO = 0.6  # un fragmento cuenta como "parte del número" si mide al menos esto del más alto
    fragmentos_numero = [d for d in detecciones if _alto_bbox(d) >= alto_maximo * UMBRAL_ALTO_RELATIVO]
    fragmentos_numero.sort(key=_x_izquierda_bbox)  # de izquierda a derecha, como se lee

    texto = "".join(d[1] for d in fragmentos_numero).upper().replace(" ", "")
    confianza = sum(d[2] for d in fragmentos_numero) / len(fragmentos_numero)

    # Un vehículo fotografiado muy lejos de la cámara llega aquí como un
    # recorte de pocos píxeles. Agrandarlo a config.ANCHO_OBJETIVO_OCR no
    # inventa detalle que la cámara nunca capturó, y EasyOCR no tiene forma
    # de saber cuánto se amplió la imagen — puede reportar confianza alta
    # sobre una lectura que en realidad viene de muy poca información real.
    # Se penaliza la confianza en ese caso para que el sistema no la trate
    # como si fuera tan confiable como una foto tomada de cerca.
    ancho_original = imagen_recorte.shape[1]
    if ancho_original < config.ANCHO_MINIMO_RECORTE_CONFIABLE:
        confianza *= ancho_original / config.ANCHO_MINIMO_RECORTE_CONFIABLE

    return {"texto": texto, "confianza": confianza}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python src/lector.py ruta/a/imagen_placa.jpg")
        sys.exit(1)

    ruta = Path(sys.argv[1])
    if not ruta.exists():
        print(f"ERROR: no se encontró la imagen '{ruta}'.")
        sys.exit(1)

    imagen = leer_imagen(ruta)
    if imagen is None:
        print(f"ERROR: '{ruta}' existe pero no se pudo leer como imagen.")
        sys.exit(1)

    resultado = leer_placa(imagen)

    if resultado["texto"]:
        print(f"Texto leído: {resultado['texto']}")
        print(f"Confianza: {resultado['confianza']:.2f}")
    else:
        print("No se logró leer ningún texto en la imagen.")
        print("Verifica que el recorte contenga la placa de forma clara.")
