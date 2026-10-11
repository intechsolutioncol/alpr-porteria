"""
Capa de autorización (Semana 5): conecta lo que lee el pipeline con la base
de datos y decide qué debe ver el vigilante en pantalla.

base_datos.py sabe *consultar* datos (consultar_placa, buscar coincidencias).
Este módulo sabe *decidir qué significa* el resultado de esa consulta para
la persona en la portería: si mostrar verde/amarillo/rojo, qué mensaje dar,
y qué hacer cuando el OCR no está seguro de lo que leyó.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from src import base_datos

# Confianza mínima para confiar en la lectura tal cual. Por debajo de este
# umbral, en vez de dar una respuesta tajante ("desconocido"), el sistema
# ayuda al vigilante sugiriendo las placas más parecidas registradas.
UMBRAL_CONFIANZA_BAJA = 0.55


def evaluar_ingreso(placa_corregida, confianza):
    """
    Decide el resultado de autorización para una placa ya corregida por el
    validador, junto con el mensaje y color que debe mostrar la interfaz.

    Retorna un diccionario con, como mínimo:
      - "estado": "residente" | "visitante_activo" | "visitante_vencido"
                  | "desconocido" | "baja_confianza"
      - "color": "verde" | "amarillo" | "rojo"
      - "mensaje": texto para mostrar al vigilante
      - datos adicionales según el caso (apartamento, residente, visitante,
        o "sugerencias" en el caso de baja confianza)
    """
    if confianza < UMBRAL_CONFIANZA_BAJA:
        sugerencias = base_datos.buscar_coincidencias_parciales(placa_corregida, limite=3)
        return {
            "estado": "baja_confianza",
            "color": "amarillo",
            "mensaje": (
                f"Lectura poco confiable ('{placa_corregida}', {confianza:.0%}). "
                "Verifica con el vigilante cuál de estas coincide:"
            ),
            "placa_leida": placa_corregida,
            "confianza": confianza,
            "sugerencias": sugerencias,
        }

    consulta = base_datos.consultar_placa(placa_corregida)
    estado = consulta["estado"]

    if estado == "residente":
        apartamento = consulta["apartamento"]
        residente = consulta["residente"]
        return {
            "estado": "residente",
            "color": "verde",
            "mensaje": f"Autorizado — Residente de apto. {apartamento['numero']} torre {apartamento['torre']}",
            "placa": consulta["placa"],
            "apartamento": apartamento,
            "residente": residente,
            "vehiculo": consulta["vehiculo"],
        }

    if estado == "visitante_activo":
        apartamento = consulta["apartamento"]
        visitante = consulta["visitante"]
        return {
            "estado": "visitante_activo",
            "color": "verde",
            "mensaje": (
                f"Autorizado — Visitante de {visitante['nombre_visitante']}, "
                f"autorizado por apto. {apartamento['numero']} torre {apartamento['torre']} "
                f"hasta {visitante['fecha_fin']}"
            ),
            "placa": consulta["placa"],
            "apartamento": apartamento,
            "visitante": visitante,
        }

    if estado == "visitante_vencido":
        apartamento = consulta["apartamento"]
        visitante = consulta["visitante"]
        return {
            "estado": "visitante_vencido",
            "color": "rojo",
            "mensaje": (
                f"NO autorizado — La autorización de visitante venció el {visitante['fecha_fin']} "
                f"(apto. {apartamento['numero']} torre {apartamento['torre']})"
            ),
            "placa": consulta["placa"],
            "apartamento": apartamento,
            "visitante": visitante,
        }

    # estado == "desconocido"
    return {
        "estado": "desconocido",
        "color": "rojo",
        "mensaje": f"NO autorizado — Placa '{consulta['placa']}' no está registrada",
        "placa": consulta["placa"],
    }


if __name__ == "__main__":
    base_datos.crear_tablas()
    base_datos.cargar_datos_ejemplo()

    with base_datos.conectar() as conexion:
        placa_residente = conexion.execute("SELECT placa FROM vehiculos LIMIT 1").fetchone()
        placa_visitante = conexion.execute("SELECT placa FROM visitantes LIMIT 1").fetchone()

    casos_prueba = [
        (placa_residente["placa"], 0.9, "residente conocido"),
        (placa_visitante["placa"], 0.9, "visitante (activo o vencido según los datos de ejemplo)"),
        ("ZZZ999", 0.9, "placa inexistente"),
        (placa_residente["placa"], 0.3, "misma placa de residente pero con baja confianza del OCR"),
    ]

    print("Pruebas de autorizacion.py\n" + "-" * 50)
    for placa, confianza, descripcion in casos_prueba:
        resultado = evaluar_ingreso(placa, confianza)
        print(f"\nCaso: {descripcion}")
        print(f"  Estado: {resultado['estado']} ({resultado['color']})")
        print(f"  Mensaje: {resultado['mensaje']}")
