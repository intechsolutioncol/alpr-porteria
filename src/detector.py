"""
Detector de vehículos / placas.

Semana 1: todavía no había un modelo entrenado para encontrar placas
directamente, así que se usaba un modelo YOLO ya entrenado por Ultralytics
sobre el dataset COCO (sabe encontrar carros, motos, buses y camiones);
había que recortar el vehículo y buscar la placa dentro de ese recorte.

Semana 3: ya existe un modelo propio (config.MODELO_PLACAS, entrenado con
placas sintéticas en Colab) que encuentra la placa directamente, sin pasar
por el vehículo completo. Este módulo mantiene los dos modos disponibles
(parámetro `modo`) porque la Semana 3 pide comparar ambos enfoques en
precisión y velocidad (ver pruebas/comparar_detectores.py); en producción
normal se usaría siempre modo="placas".
"""

import sys
from pathlib import Path

import cv2

# Permite ejecutar "python src/detector.py" desde cualquier carpeta y que
# encuentre config.py en la raíz del proyecto.
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from utilidades_imagen import leer_imagen


class DetectorVehiculos:
    """
    Envuelve un modelo YOLO para encontrar vehículos o placas en una imagen.

    Parámetros
    ----------
    modo : str
        "placas": usa el modelo propio entrenado en la Semana 3
            (config.MODELO_PLACAS). Encuentra la placa directamente.
        "vehiculos": usa el modelo preentrenado de Ultralytics sobre COCO
            (config.MODELO_VEHICULOS). Encuentra el vehículo completo; el
            recorte hay que pasarlo luego por el lector para buscar la placa
            dentro de él.
        "auto" (por defecto): usa "placas" si ya existe un modelo propio
            entrenado; si no, cae a "vehiculos" y avisa por qué.
    """

    def __init__(self, modo="auto"):
        # La importación de ultralytics se hace aquí (no al inicio del
        # archivo) para que un error de "librería no instalada" señale
        # claramente que el problema es ese, no un import roto en otro lado.
        try:
            from ultralytics import YOLO
        except ImportError:
            print(
                "ERROR: no está instalada la librería 'ultralytics'.\n"
                "Activa el entorno virtual (.venv) y ejecuta:\n"
                "  pip install -r requirements.txt"
            )
            sys.exit(1)

        if modo == "auto":
            if config.MODELO_PLACAS.exists():
                modo = "placas"
            else:
                modo = "vehiculos"
                print(
                    f"AVISO: todavía no existe un modelo propio en '{config.MODELO_PLACAS}'.\n"
                    "Usando el detector de vehículos preentrenado en su lugar "
                    "(ver Semana 3 de la guía para entrenar el modelo propio)."
                )

        if modo not in ("placas", "vehiculos"):
            raise ValueError(f"Modo desconocido: '{modo}' (use 'placas', 'vehiculos' o 'auto')")

        self.modo = modo
        ruta_modelo = config.MODELO_PLACAS if modo == "placas" else config.MODELO_VEHICULOS

        if modo == "placas" and not Path(ruta_modelo).exists():
            raise FileNotFoundError(
                f"No se encontró el modelo entrenado en '{ruta_modelo}'.\n"
                "Entrena el detector de placas primero (Semana 3, notebook de Colab) "
                "o usa modo='vehiculos' mientras tanto."
            )

        print(f"Cargando modelo '{ruta_modelo}' (modo: {modo})...")
        print("(La primera vez que se usa un modelo preentrenado, lo descarga de internet)")
        self.modelo = YOLO(str(ruta_modelo))
        print("Modelo cargado.")

    def detectar_vehiculos(self, ruta_imagen):
        """
        Busca vehículos en una imagen.

        Parámetros
        ----------
        ruta_imagen : str o Path
            Ruta a la imagen a analizar.

        Retorna
        -------
        list[dict]
            Un diccionario por vehículo encontrado, con:
            - "recorte": la imagen (array de OpenCV) recortada al vehículo
            - "caja": (x1, y1, x2, y2) coordenadas del recuadro en la imagen original
            - "clase": nombre de la clase COCO detectada (carro, motocicleta, etc.)
            - "confianza": qué tan seguro está el modelo (0.0 a 1.0)
        """
        ruta_imagen = Path(ruta_imagen)
        if not ruta_imagen.exists():
            raise FileNotFoundError(
                f"No se encontró la imagen '{ruta_imagen}'. Verifica la ruta."
            )

        imagen = leer_imagen(ruta_imagen)
        if imagen is None:
            raise ValueError(
                f"'{ruta_imagen}' existe pero OpenCV no pudo leerla. "
                "¿Es un formato de imagen válido (jpg, png)?"
            )

        return self.detectar_en_imagen(imagen)

    def detectar_en_imagen(self, imagen):
        """
        Igual que detectar_vehiculos(), pero recibe directamente una imagen
        ya cargada en memoria (array de OpenCV) en vez de una ruta de
        archivo. Se usa para procesar fotogramas de video, donde no tendría
        sentido guardar cada fotograma a disco solo para poder leerlo de
        nuevo.
        """
        resultados = self.modelo.predict(
            source=imagen,
            conf=config.UMBRAL_CONFIANZA_DETECTOR,
            imgsz=config.TAMANO_IMAGEN_YOLO,
            verbose=False,
        )

        detecciones = []
        for resultado in resultados:
            for caja in resultado.boxes:
                id_clase = int(caja.cls[0])

                if self.modo == "vehiculos":
                    if id_clase not in config.CLASES_VEHICULOS_COCO:
                        continue  # no nos interesa (persona, semáforo, etc.)
                    nombre_clase = config.CLASES_VEHICULOS_COCO[id_clase]
                else:
                    nombre_clase = "placa"  # el modelo propio solo tiene esta clase

                x1, y1, x2, y2 = map(int, caja.xyxy[0])
                confianza = float(caja.conf[0])

                if self.modo == "placas":
                    # Un recorte pegado exacto al borde de la placa corta un
                    # poco los caracteres de las esquinas (ver
                    # config.MARGEN_RECORTE_PLACA). "caja" se deja como la
                    # detección original sin margen — es la que se dibuja en
                    # pantalla y la que se usa como referencia de posición;
                    # solo el recorte que recibe el OCR se agranda un poco.
                    xr1, yr1, xr2, yr2 = self._agrandar_caja(x1, y1, x2, y2, imagen.shape)
                else:
                    xr1, yr1, xr2, yr2 = x1, y1, x2, y2

                recorte = imagen[yr1:yr2, xr1:xr2]

                detecciones.append(
                    {
                        "recorte": recorte,
                        "caja": (x1, y1, x2, y2),
                        "clase": nombre_clase,
                        "confianza": confianza,
                    }
                )

        return detecciones

    @staticmethod
    def _agrandar_caja(x1, y1, x2, y2, forma_imagen):
        """Expande una caja un margen (config.MARGEN_RECORTE_PLACA) sin salirse de la imagen."""
        alto_imagen, ancho_imagen = forma_imagen[:2]
        margen_x = int((x2 - x1) * config.MARGEN_RECORTE_PLACA)
        margen_y = int((y2 - y1) * config.MARGEN_RECORTE_PLACA)

        return (
            max(0, x1 - margen_x),
            max(0, y1 - margen_y),
            min(ancho_imagen, x2 + margen_x),
            min(alto_imagen, y2 + margen_y),
        )


def detectar_vehiculos(ruta_imagen):
    """
    Función de conveniencia: crea el detector y detecta en una sola llamada.

    Para procesar muchas imágenes seguidas es más eficiente crear una
    instancia de DetectorVehiculos una sola vez y reutilizarla, en vez de
    llamar esta función repetidamente (cada llamada recarga el modelo).
    """
    return DetectorVehiculos().detectar_vehiculos(ruta_imagen)


def _dibujar_y_mostrar(ruta_imagen, vehiculos):
    """Dibuja los recuadros de detección sobre la imagen y la muestra en pantalla."""
    imagen = leer_imagen(ruta_imagen)

    for vehiculo in vehiculos:
        x1, y1, x2, y2 = vehiculo["caja"]
        etiqueta = f"{vehiculo['clase']} {vehiculo['confianza']:.2f}"

        cv2.rectangle(imagen, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(
            imagen, etiqueta, (x1, max(y1 - 10, 10)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2,
        )

    cv2.imshow("Deteccion de vehiculos (presiona una tecla para cerrar)", imagen)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Detecta vehículos o placas en una imagen.")
    parser.add_argument("ruta_imagen", help="Ruta a la imagen a analizar")
    parser.add_argument(
        "--modo", choices=["auto", "placas", "vehiculos"], default="auto",
        help="Qué modelo usar (por defecto: auto, usa el propio si ya existe)",
    )
    args = parser.parse_args()

    ruta = args.ruta_imagen
    detector = DetectorVehiculos(modo=args.modo)

    try:
        vehiculos = detector.detectar_vehiculos(ruta)
    except (FileNotFoundError, ValueError) as error:
        print(f"ERROR: {error}")
        sys.exit(1)

    if not vehiculos:
        print(
            f"No se detectó ningún vehículo en '{ruta}'.\n"
            f"Prueba bajar UMBRAL_CONFIANZA_DETECTOR en config.py "
            f"(ahora está en {config.UMBRAL_CONFIANZA_DETECTOR})."
        )
    else:
        print(f"Se encontraron {len(vehiculos)} vehículo(s):")
        for i, v in enumerate(vehiculos, start=1):
            print(f"  {i}. {v['clase']} — confianza {v['confianza']:.2f} — caja {v['caja']}")
        _dibujar_y_mostrar(ruta, vehiculos)
