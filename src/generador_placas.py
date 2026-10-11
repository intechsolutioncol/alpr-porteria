"""
Generador de placas sintéticas colombianas (Semana 2).

Por qué esto es el corazón científico del proyecto: entrenar un modelo
requiere datos etiquetados. Etiquetar 2.000 placas a mano son semanas de
trabajo tedioso. Generarlas por código toma minutos y las etiquetas salen
gratis, porque el programa sabe exactamente qué texto escribió en cada
placa. A esto se le llama "datos sintéticos" y es una técnica real de la
industria, no un atajo escolar.

Cada placa pasa luego por un módulo de degradación (rotación, perspectiva,
desenfoque, ruido, sombras, fondo variado) que imita cómo se ve una placa
real fotografiada en condiciones imperfectas. Si las placas sintéticas se
vieran "perfectas", un modelo entrenado con ellas fallaría en la vida real:
nunca habría visto una placa borrosa o en ángulo.
"""

import argparse
import csv
import random
import string
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from utilidades_imagen import escribir_imagen, leer_imagen

# ---------------------------------------------------------------------------
# Generación del texto de la placa
# ---------------------------------------------------------------------------

LETRAS = string.ascii_uppercase
NUMEROS = string.digits


def generar_texto_placa(tipo):
    """
    Genera un texto de placa aleatorio válido.

    tipo: "carro" (LLLNNN, ej. ABC123) o "moto" (LLLNNL, ej. ABC12D)
    """
    letras = "".join(random.choices(LETRAS, k=3))
    if tipo == "carro":
        numeros = "".join(random.choices(NUMEROS, k=3))
        return letras + numeros
    elif tipo == "moto":
        numeros = "".join(random.choices(NUMEROS, k=2))
        letra_final = random.choice(LETRAS)
        return letras + numeros + letra_final
    else:
        raise ValueError(f"Tipo de placa desconocido: '{tipo}' (use 'carro' o 'moto')")


# ---------------------------------------------------------------------------
# Dibujo de la placa base
# ---------------------------------------------------------------------------

# Proporción real de una placa colombiana de carro es aprox. 33cm x 16.5cm
# (2:1). La dibujamos a esta resolución y luego se escala si hace falta.
ANCHO_PLACA = 660
ALTO_PLACA = 330

AMARILLO_PLACA = (30, 200, 235)   # en BGR: un amarillo cálido tipo placa real
NEGRO = (20, 20, 20)

RUTAS_FUENTE_CANDIDATAS = [
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\arial.ttf",
]


def _cargar_fuente(tamano):
    for ruta in RUTAS_FUENTE_CANDIDATAS:
        if Path(ruta).exists():
            return ImageFont.truetype(ruta, tamano)
    # Si no hay ninguna fuente TrueType disponible, PIL usa una fuente
    # interna muy básica. El programa sigue funcionando, solo se ve peor.
    return ImageFont.load_default()


def dibujar_placa_base(texto):
    """
    Dibuja una placa "limpia" (sin degradación) con el texto dado.

    Retorna una imagen en formato OpenCV (BGR, array de numpy).
    """
    imagen_pil = Image.new("RGB", (ANCHO_PLACA, ALTO_PLACA), AMARILLO_PLACA[::-1])
    dibujo = ImageDraw.Draw(imagen_pil)

    # Borde negro, como el marco de una placa real
    grosor_borde = 10
    dibujo.rectangle(
        [0, 0, ANCHO_PLACA - 1, ALTO_PLACA - 1],
        outline=NEGRO[::-1],
        width=grosor_borde,
    )

    # El tamaño de fuente se calcula probando desde grande hacia abajo hasta
    # que el texto quepa dentro del margen disponible. Un tamaño fijo (p.ej.
    # 200pt) se ve bien para textos cortos pero se sale del borde en algunos
    # casos, según qué tan anchos sean los caracteres generados.
    margen_disponible = ANCHO_PLACA - 2 * grosor_borde - 40
    fuente = _cargar_fuente(tamano=200)
    for tamano in range(200, 40, -5):
        fuente = _cargar_fuente(tamano)
        caja_texto = dibujo.textbbox((0, 0), texto, font=fuente)
        if (caja_texto[2] - caja_texto[0]) <= margen_disponible:
            break

    caja_texto = dibujo.textbbox((0, 0), texto, font=fuente)
    ancho_texto = caja_texto[2] - caja_texto[0]
    alto_texto = caja_texto[3] - caja_texto[1]
    x = (ANCHO_PLACA - ancho_texto) / 2 - caja_texto[0]
    y = (ALTO_PLACA - alto_texto) / 2 - caja_texto[1]

    dibujo.text((x, y), texto, font=fuente, fill=NEGRO[::-1])

    return cv2.cvtColor(np.array(imagen_pil), cv2.COLOR_RGB2BGR)


# ---------------------------------------------------------------------------
# Degradación realista (Prompt 2.2)
# ---------------------------------------------------------------------------
#
# Cada función recibe y devuelve una imagen OpenCV (BGR). Están separadas y
# cada una se puede activar/desactivar por su cuenta porque la Semana 8
# incluye un experimento que compara el efecto individual de cada una sobre
# la precisión del OCR.


def aplicar_rotacion(imagen, grados_max=15):
    """Rota la imagen un ángulo aleatorio entre -grados_max y +grados_max."""
    alto, ancho = imagen.shape[:2]
    angulo = random.uniform(-grados_max, grados_max)
    matriz = cv2.getRotationMatrix2D((ancho / 2, alto / 2), angulo, 1.0)
    return cv2.warpAffine(
        imagen, matriz, (ancho, alto),
        borderMode=cv2.BORDER_REPLICATE,
    )


def aplicar_perspectiva(imagen, intensidad=0.15):
    """
    Deforma la placa como si se viera en ángulo (no de frente a la cámara).

    Mueve cada esquina un porcentaje aleatorio de las dimensiones de la
    imagen, simulando que la cámara no está perfectamente alineada.
    """
    alto, ancho = imagen.shape[:2]
    desplazamiento_x = ancho * intensidad
    desplazamiento_y = alto * intensidad

    origen = np.float32([[0, 0], [ancho, 0], [ancho, alto], [0, alto]])
    destino = np.float32([
        [random.uniform(0, desplazamiento_x), random.uniform(0, desplazamiento_y)],
        [ancho - random.uniform(0, desplazamiento_x), random.uniform(0, desplazamiento_y)],
        [ancho - random.uniform(0, desplazamiento_x), alto - random.uniform(0, desplazamiento_y)],
        [random.uniform(0, desplazamiento_x), alto - random.uniform(0, desplazamiento_y)],
    ])

    matriz = cv2.getPerspectiveTransform(origen, destino)
    return cv2.warpPerspective(
        imagen, matriz, (ancho, alto),
        borderMode=cv2.BORDER_REPLICATE,
    )


def aplicar_desenfoque_gaussiano(imagen, kernel_max=5):
    """Simula una imagen ligeramente fuera de foco."""
    k = random.choice(range(3, kernel_max + 1, 2))  # kernel debe ser impar
    return cv2.GaussianBlur(imagen, (k, k), 0)


def aplicar_desenfoque_movimiento(imagen, longitud_max=9):
    """Simula que el vehículo se movía mientras se tomaba la foto."""
    longitud = random.choice(range(3, longitud_max + 1, 2))
    kernel = np.zeros((longitud, longitud))
    kernel[longitud // 2, :] = 1.0 / longitud
    angulo = random.uniform(0, 360)
    matriz_rotacion = cv2.getRotationMatrix2D((longitud / 2, longitud / 2), angulo, 1)
    kernel = cv2.warpAffine(kernel, matriz_rotacion, (longitud, longitud))
    return cv2.filter2D(imagen, -1, kernel)


def aplicar_brillo_contraste(imagen, rango_brillo=(-40, 40), rango_contraste=(0.7, 1.3)):
    """Varía el brillo y contraste, simulando distintas condiciones de luz."""
    brillo = random.uniform(*rango_brillo)
    contraste = random.uniform(*rango_contraste)
    return cv2.convertScaleAbs(imagen, alpha=contraste, beta=brillo)


def aplicar_ruido(imagen, intensidad=12):
    """Agrega ruido tipo grano de cámara, más notorio en fotos con poca luz."""
    ruido = np.random.normal(0, intensidad, imagen.shape).astype(np.int16)
    resultado = imagen.astype(np.int16) + ruido
    return np.clip(resultado, 0, 255).astype(np.uint8)


def aplicar_sombra_parcial(imagen, opacidad_max=0.5):
    """Oscurece una franja diagonal de la imagen, como una sombra proyectada."""
    alto, ancho = imagen.shape[:2]
    mascara = np.zeros((alto, ancho), dtype=np.float32)

    x1, x2 = sorted(random.sample(range(ancho), 2))
    puntos = np.array([[x1, 0], [x2, 0], [ancho, alto], [0, alto]])
    cv2.fillPoly(mascara, [puntos], 1.0)

    opacidad = random.uniform(0.15, opacidad_max)
    factor = 1 - (mascara[..., None] * opacidad)
    return np.clip(imagen.astype(np.float32) * factor, 0, 255).astype(np.uint8)


_RUTAS_FONDOS_REALES = None  # se carga una sola vez, la primera vez que se necesita


def _listar_fondos_reales():
    global _RUTAS_FONDOS_REALES
    if _RUTAS_FONDOS_REALES is None:
        if config.DIR_FONDOS_REALES.exists():
            _RUTAS_FONDOS_REALES = list(config.DIR_FONDOS_REALES.glob("*.jpg"))
        else:
            _RUTAS_FONDOS_REALES = []
    return _RUTAS_FONDOS_REALES


def _ajustar_fondo_real(imagen, ancho, alto):
    """
    Ajusta un recorte real (de tamaño variable) al tamaño de fondo exacto
    que se necesita, sin deformarlo: lo agranda lo mínimo necesario
    manteniendo su proporción y recorta el sobrante al azar (como el
    "cover" de una imagen de fondo en una página web), en vez de estirarlo.
    """
    alto_actual, ancho_actual = imagen.shape[:2]
    escala = max(ancho / ancho_actual, alto / alto_actual) * 1.01
    nuevo_ancho, nuevo_alto = int(ancho_actual * escala) + 1, int(alto_actual * escala) + 1
    agrandada = cv2.resize(imagen, (nuevo_ancho, nuevo_alto))

    x0 = random.randint(0, max(0, nuevo_ancho - ancho))
    y0 = random.randint(0, max(0, nuevo_alto - alto))
    return agrandada[y0:y0 + alto, x0:x0 + ancho]


def _generar_fondo(ancho, alto, tipo=None):
    """
    Genera el fondo sobre el que se pega la placa. Además de los tres
    fondos procedurales originales (asfalto, pared, carrocería — simulados
    con ruido y gradiente, no eran fotos reales), a partir de la Semana 3
    (segunda vuelta de entrenamiento) se agregó un cuarto tipo, "real": un
    recorte de una foto o video real (ver src/extraer_fondos_reales.py), ya
    filtrado para no contener ningún vehículo/placa real. Se agregó porque
    el detector entrenado solo con fondos procedurales confundía mallas,
    pavimento agrietado y árboles reales con una placa — nunca había visto
    esas texturas (BITACORA_EXPERIMENTOS.md sección 6.4).
    """
    fondos_reales = _listar_fondos_reales()
    # "real" pesa el 40% de las veces cuando hay recortes disponibles: ni
    # tan poco que no aporte variedad real, ni tanto que el modelo termine
    # memorizando los ~90 fondos reales que se lograron reunir (muchos
    # menos que la variedad infinita de los procedurales).
    opciones = ["asfalto", "pared", "carroceria"] + (["real"] * 2 if fondos_reales else [])
    tipo = tipo or random.choice(opciones)

    if tipo == "real" and fondos_reales:
        real = leer_imagen(random.choice(fondos_reales))
        if real is not None:
            return _ajustar_fondo_real(real, ancho, alto)
        tipo = "asfalto"  # por si el archivo no se pudo leer

    if tipo == "asfalto":
        base = np.random.normal(70, 15, (alto, ancho, 3)).astype(np.uint8)
    elif tipo == "pared":
        color = np.array(random.choice([
            (180, 170, 160), (150, 140, 190), (170, 190, 170),
        ]))
        base = np.tile(color, (alto, ancho, 1)).astype(np.uint8)
        base = np.clip(base.astype(np.int16) + np.random.normal(0, 8, base.shape), 0, 255).astype(np.uint8)
    else:  # carroceria
        gradiente = np.linspace(30, 110, alto).astype(np.uint8)
        base = np.repeat(gradiente[:, None], ancho, axis=1)
        base = np.repeat(base[:, :, None], 3, axis=2)

    return cv2.GaussianBlur(base, (5, 5), 0)


def pegar_sobre_fondo(imagen_placa, margen_relativo=0.6):
    """Coloca la placa (ya degradada) sobre un fondo más grande, como se vería en una foto real."""
    alto_placa, ancho_placa = imagen_placa.shape[:2]
    ancho_fondo = int(ancho_placa * (1 + margen_relativo))
    alto_fondo = int(alto_placa * (1 + margen_relativo))

    fondo = _generar_fondo(ancho_fondo, alto_fondo)

    x_offset = (ancho_fondo - ancho_placa) // 2
    y_offset = (alto_fondo - alto_placa) // 2
    fondo[y_offset:y_offset + alto_placa, x_offset:x_offset + ancho_placa] = imagen_placa

    caja_placa = (x_offset, y_offset, x_offset + ancho_placa, y_offset + alto_placa)
    return fondo, caja_placa


AUMENTACIONES_DISPONIBLES = {
    "rotacion": aplicar_rotacion,
    "perspectiva": aplicar_perspectiva,
    "desenfoque_gaussiano": aplicar_desenfoque_gaussiano,
    "desenfoque_movimiento": aplicar_desenfoque_movimiento,
    "brillo_contraste": aplicar_brillo_contraste,
    "ruido": aplicar_ruido,
    "sombra_parcial": aplicar_sombra_parcial,
}


def generar_placa_degradada(texto, aumentaciones_activas=None, con_fondo=True, margen_relativo=0.6):
    """
    Genera una placa sintética completa: dibuja el texto y aplica las
    degradaciones indicadas (todas por defecto).

    margen_relativo: qué tan grande es el fondo respecto a la placa (ver
    pegar_sobre_fondo). El valor por defecto (0.6, placa ocupa ~62% del
    ancho del cuadro) es el que se usó siempre para las pruebas de OCR
    (data/sinteticas/) — se deja igual para no invalidar esas mediciones.
    Para el dataset de ENTRENAMIENTO DEL DETECTOR (preparar_dataset_yolo.py)
    hay que variarlo: un valor fijo le enseña al modelo que "la placa
    siempre ocupa la mayoría del cuadro", algo falso en fotos reales
    tomadas a distancia normal (ver BITACORA_EXPERIMENTOS.md sección 6.2).

    aumentaciones_activas: lista de nombres (ver AUMENTACIONES_DISPONIBLES)
    a aplicar. None = todas activas.

    Retorna (imagen_final, caja_placa_o_None). caja_placa solo se calcula
    si con_fondo=True, y son las coordenadas de la placa dentro del fondo
    (útil más adelante para el dataset de detección, Semana 3).
    """
    if aumentaciones_activas is None:
        aumentaciones_activas = list(AUMENTACIONES_DISPONIBLES.keys())

    imagen = dibujar_placa_base(texto)

    for nombre in aumentaciones_activas:
        if nombre not in AUMENTACIONES_DISPONIBLES:
            raise ValueError(
                f"Aumentación desconocida: '{nombre}'. "
                f"Disponibles: {list(AUMENTACIONES_DISPONIBLES.keys())}"
            )
        imagen = AUMENTACIONES_DISPONIBLES[nombre](imagen)

    caja_placa = None
    if con_fondo:
        imagen, caja_placa = pegar_sobre_fondo(imagen, margen_relativo=margen_relativo)

    return imagen, caja_placa


# ---------------------------------------------------------------------------
# Generación masiva + CSV de referencia
# ---------------------------------------------------------------------------


def generar_dataset(cantidad, proporcion_motos, carpeta_salida, aumentaciones_activas=None, con_fondo=True):
    """
    Genera `cantidad` placas sintéticas y guarda un CSV con el texto real
    de cada una (la "etiqueta" que hace posible medir precisión sin
    revisión manual).
    """
    carpeta_salida = Path(carpeta_salida)
    carpeta_salida.mkdir(parents=True, exist_ok=True)

    ruta_csv = carpeta_salida / "referencia.csv"
    filas = []

    for i in range(cantidad):
        tipo = "moto" if random.random() < proporcion_motos else "carro"
        texto = generar_texto_placa(tipo)

        imagen, _ = generar_placa_degradada(texto, aumentaciones_activas, con_fondo)

        nombre_archivo = f"placa_{i:05d}_{texto}.jpg"
        if not escribir_imagen(carpeta_salida / nombre_archivo, imagen):
            print(f"  ADVERTENCIA: no se pudo guardar '{nombre_archivo}'")

        filas.append({"archivo": nombre_archivo, "texto": texto, "tipo": tipo})

        if (i + 1) % max(1, cantidad // 10) == 0 or i == cantidad - 1:
            print(f"  {i + 1}/{cantidad} generadas...")

    with open(ruta_csv, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=["archivo", "texto", "tipo"])
        escritor.writeheader()
        escritor.writerows(filas)

    print(f"\n{cantidad} placas generadas en '{carpeta_salida}'.")
    print(f"Referencia guardada en '{ruta_csv}'.")
    return ruta_csv


def generar_mosaico(cantidad=25, carpeta_salida=None, ruta_mosaico=None):
    """Genera `cantidad` placas de muestra y las junta en una sola imagen para revisión visual rápida."""
    columnas = 5
    filas_mosaico = (cantidad + columnas - 1) // columnas

    miniaturas = []
    for _ in range(cantidad):
        tipo = random.choice(["carro", "moto"])
        texto = generar_texto_placa(tipo)
        imagen, _ = generar_placa_degradada(texto)
        miniatura = cv2.resize(imagen, (240, 160))
        # Escribimos el texto real encima para poder comparar a simple vista
        cv2.putText(
            miniatura, texto, (5, 20),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1, cv2.LINE_AA,
        )
        miniaturas.append(miniatura)

    alto_m, ancho_m = miniaturas[0].shape[:2]
    mosaico = np.full((filas_mosaico * alto_m, columnas * ancho_m, 3), 255, dtype=np.uint8)

    for i, miniatura in enumerate(miniaturas):
        fila, col = divmod(i, columnas)
        mosaico[fila * alto_m:(fila + 1) * alto_m, col * ancho_m:(col + 1) * ancho_m] = miniatura

    carpeta_salida = Path(carpeta_salida or config.DIR_DATA_SINTETICAS)
    carpeta_salida.mkdir(parents=True, exist_ok=True)
    ruta_mosaico = Path(ruta_mosaico or (carpeta_salida / "mosaico_muestra.jpg"))
    escribir_imagen(ruta_mosaico, mosaico)

    print(f"Mosaico de {cantidad} ejemplos guardado en '{ruta_mosaico}'.")
    return ruta_mosaico


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Genera placas sintéticas colombianas con degradación realista."
    )
    parser.add_argument("--cantidad", type=int, default=20, help="Cuántas placas generar")
    parser.add_argument("--prop-motos", type=float, default=0.3, help="Proporción de placas tipo moto (0.0 a 1.0)")
    parser.add_argument(
        "--carpeta-salida", type=str,
        default=str(config.DIR_DATA_SINTETICAS),
        help="Carpeta donde guardar las imágenes y el CSV de referencia",
    )
    parser.add_argument(
        "--mosaico", action="store_true",
        help="En vez de generar el dataset, genera un mosaico de 25 ejemplos para revisión visual",
    )
    args = parser.parse_args()

    if args.mosaico:
        generar_mosaico(cantidad=25, carpeta_salida=args.carpeta_salida)
    else:
        generar_dataset(args.cantidad, args.prop_motos, args.carpeta_salida)
