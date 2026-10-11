"""
Diagnóstico rápido (Semana 9): verifica en menos de 30 segundos que todo
esté listo para la demostración, sin correr el pipeline completo (eso
tomaría minutos por el OCR en CPU — aquí solo se comprueba que las piezas
EXISTAN y respondan, no la precisión del sistema).

Por qué existe este script: el día de la feria no hay tiempo para depurar.
Correr esto apenas se llega y antes de empezar a mostrar el sistema evita
sorpresas ("¿por qué no abre la cámara?", "¿se me olvidó copiar el modelo
entrenado?").
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config


def _revisar_librerias():
    faltantes = []
    for lib in ["ultralytics", "easyocr", "cv2", "streamlit", "pandas", "matplotlib", "PIL"]:
        try:
            __import__(lib)
        except ImportError:
            faltantes.append(lib)
    if faltantes:
        raise RuntimeError(f"Faltan: {', '.join(faltantes)} (pip install -r requirements.txt)")
    return "todas presentes"


def _revisar_base_datos():
    from src import base_datos
    if not config.BASE_DATOS_SQLITE.exists():
        raise RuntimeError(f"No existe '{config.BASE_DATOS_SQLITE}'. Ejecuta: python src/base_datos.py")
    with base_datos.conectar() as conexion:
        n_apartamentos = conexion.execute("SELECT COUNT(*) FROM apartamentos").fetchone()[0]
        n_vehiculos = conexion.execute("SELECT COUNT(*) FROM vehiculos").fetchone()[0]
    if n_apartamentos == 0:
        raise RuntimeError("La base de datos existe pero no tiene apartamentos cargados.")
    return f"{n_apartamentos} apartamentos, {n_vehiculos} vehículos"


def _revisar_modelo_vehiculos():
    ruta = Path(config.MODELO_VEHICULOS)
    # Ultralytics lo descarga en el directorio de trabajo si no existe; si ya
    # se corrió detector.py alguna vez, debería estar cacheado localmente.
    if not ruta.exists():
        return "no está descargado todavía (se descargará solo la primera vez que se use)"
    return f"presente ({ruta.stat().st_size // 1_000_000} MB)"


def _revisar_modelo_placas():
    if not config.MODELO_PLACAS.exists():
        return "AVISO: no entrenado todavía; el sistema usará el detector de vehículos (Semana 1) mientras tanto"
    return f"presente ({config.MODELO_PLACAS.stat().st_size // 1_000_000} MB)"


def _revisar_easyocr():
    carpeta_modelos = Path.home() / ".EasyOCR" / "model"
    if not carpeta_modelos.exists() or not any(carpeta_modelos.glob("*.pth")):
        raise RuntimeError(
            f"No se encontraron modelos en '{carpeta_modelos}'. "
            "Corre 'python src/lector.py <alguna_imagen>' una vez con internet para descargarlos."
        )
    archivos = list(carpeta_modelos.glob("*.pth"))
    return f"{len(archivos)} archivo(s) de modelo encontrados"


def _revisar_camara():
    import cv2
    for indice in (0, 1, 2):
        captura = cv2.VideoCapture(indice)
        if captura.isOpened():
            leido, _ = captura.read()
            captura.release()
            if leido:
                return f"disponible en el índice {indice}"
    raise RuntimeError("No se pudo abrir ninguna cámara en los índices 0, 1 o 2 (revisa que esté conectada)")


def _revisar_carpetas():
    faltantes = [
        str(carpeta) for carpeta in (
            config.DIR_DATA_REALES, config.DIR_DATA_SINTETICAS,
            config.DIR_MODELOS, config.DIR_RESULTADOS,
        ) if not carpeta.exists()
    ]
    if faltantes:
        raise RuntimeError(f"No existen: {', '.join(faltantes)}. Ejecuta: python config.py")
    return "todas presentes"


# Orden en el que se muestran los chequeos. Se listan aquí (en vez de correr
# cada función apenas se define) para poder medir el tiempo total real de
# principio a fin, incluyendo el de cada chequeo.
CHEQUEOS = [
    ("Librerías instaladas", _revisar_librerias),
    ("Base de datos", _revisar_base_datos),
    ("Modelo de vehículos (COCO)", _revisar_modelo_vehiculos),
    ("Modelo de placas propio", _revisar_modelo_placas),
    ("Modelos de EasyOCR descargados", _revisar_easyocr),
    ("Cámara web", _revisar_camara),
    ("Carpetas del proyecto", _revisar_carpetas),
]


def ejecutar_diagnostico():
    print("=" * 60)
    print("DIAGNÓSTICO DEL SISTEMA ALPR PORTERÍA")
    print("=" * 60)

    todo_ok = True
    for nombre, funcion in CHEQUEOS:
        inicio = time.perf_counter()
        try:
            detalle = funcion()
            ok = True
        except Exception as error:
            detalle = str(error)
            ok = False
            todo_ok = False
        duracion = time.perf_counter() - inicio

        icono = "✅" if ok else "❌"
        print(f"{icono} {nombre} ({duracion:.1f}s)")
        print(f"    {detalle}")

    print("\n" + "=" * 60)
    if todo_ok:
        print("TODO LISTO. El sistema puede arrancar sin problemas conocidos.")
    else:
        print("HAY PROBLEMAS. Revisa los ❌ de arriba antes de la demostración.")
        print("Si la cámara falla pero vas a usar demo_grabada.py, no es bloqueante.")
    print("=" * 60)

    return todo_ok


if __name__ == "__main__":
    inicio_total = time.perf_counter()
    exito = ejecutar_diagnostico()
    print(f"\nDiagnóstico completo en {time.perf_counter() - inicio_total:.1f} segundos.")
    sys.exit(0 if exito else 1)
