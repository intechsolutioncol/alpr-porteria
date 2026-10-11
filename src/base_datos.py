"""
Base de datos SQLite del sistema (Semana 5).

Por qué SQLite: no necesita instalar ni configurar un servidor de base de
datos aparte; todo vive en un solo archivo (config.BASE_DATOS_SQLITE) que se
puede copiar, respaldar o llevar en un USB el día de la feria.

Tablas:
- apartamentos: unidades del conjunto (número, torre, propietario, teléfono)
- residentes: personas asociadas a un apartamento
- vehiculos: placas de residentes, asociadas a un residente
- visitantes: placas autorizadas temporalmente por un apartamento
- registros_ingreso: cada intento de reconocimiento, con su resultado — esta
  tabla es la que permite medir la precisión real del sistema en operación
  (Semana 8), así que guarda tanto la placa leída en crudo como la corregida.
"""

import hashlib
import secrets
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

# ---------------------------------------------------------------------------
# Conexión y creación de esquema
# ---------------------------------------------------------------------------


def conectar():
    """
    Abre una conexión a la base de datos del proyecto.

    row_factory = sqlite3.Row permite acceder a las columnas de cada fila
    por nombre (fila["placa"]) además de por posición, lo cual hace el resto
    del código mucho más legible.
    """
    conexion = sqlite3.connect(config.BASE_DATOS_SQLITE)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON")
    return conexion


ESQUEMA = """
CREATE TABLE IF NOT EXISTS apartamentos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    numero          TEXT NOT NULL,
    torre           TEXT NOT NULL,
    propietario     TEXT NOT NULL,
    telefono        TEXT,
    UNIQUE (numero, torre)
);

CREATE TABLE IF NOT EXISTS residentes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT NOT NULL,
    documento       TEXT NOT NULL UNIQUE,
    apartamento_id  INTEGER NOT NULL REFERENCES apartamentos(id),
    es_propietario  INTEGER NOT NULL DEFAULT 0, -- 0/1 (SQLite no tiene booleano nativo)
    password_hash   TEXT                        -- NULL = todavía no activó su acceso individual (ver establecer_contrasena_residente)
);

CREATE TABLE IF NOT EXISTS vehiculos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    placa           TEXT NOT NULL UNIQUE,
    tipo            TEXT NOT NULL CHECK (tipo IN ('carro', 'moto')),
    marca           TEXT,
    color           TEXT,
    residente_id    INTEGER NOT NULL REFERENCES residentes(id)
);

CREATE TABLE IF NOT EXISTS visitantes (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    placa               TEXT NOT NULL,
    nombre_visitante    TEXT NOT NULL,
    apartamento_id      INTEGER NOT NULL REFERENCES apartamentos(id),
    fecha_inicio        TEXT NOT NULL,  -- formato ISO: AAAA-MM-DD
    fecha_fin           TEXT NOT NULL,
    motivo              TEXT,
    recurrente          INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS registros_ingreso (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    placa_leida         TEXT NOT NULL,     -- texto crudo que devolvió el OCR
    placa_corregida     TEXT NOT NULL,     -- texto después del validador
    marca_tiempo        TEXT NOT NULL,     -- formato ISO: AAAA-MM-DD HH:MM:SS
    resultado           TEXT NOT NULL CHECK (resultado IN ('residente', 'visitante', 'desconocido')),
    confianza           REAL,
    ruta_foto           TEXT,
    autorizado_manual   INTEGER            -- NULL = sin decisión del vigilante, 0/1 en otro caso
);
"""


def crear_tablas():
    """Crea todas las tablas si todavía no existen. Es seguro llamarla varias veces."""
    with conectar() as conexion:
        conexion.executescript(ESQUEMA)
        # Migración: si la base de datos ya existía de antes del login individual
        # de residentes, le falta la columna password_hash. CREATE TABLE IF NOT
        # EXISTS no la agrega sola a una tabla que ya existe, así que se intenta
        # agregar aparte; si ya está (bases de datos nuevas, creadas con el
        # ESQUEMA de arriba) SQLite avisa con un error que simplemente se ignora.
        try:
            conexion.execute("ALTER TABLE residentes ADD COLUMN password_hash TEXT")
        except sqlite3.OperationalError:
            pass  # la columna ya existe


# ---------------------------------------------------------------------------
# Contraseñas de residentes
#
# No usamos una librería externa de hashing (como bcrypt) para no agregar
# una dependencia nueva al stack del proyecto solo para esto — hashlib viene
# incluido en Python. PBKDF2 con una sal (salt) aleatoria por persona es un
# estándar reconocido para guardar contraseñas: nunca se guarda la
# contraseña en texto plano, así que ni siquiera alguien con acceso directo
# al archivo de la base de datos puede leerla, solo comprobar si una
# contraseña ingresada coincide con el hash guardado.
# ---------------------------------------------------------------------------

_ITERACIONES_HASH = 200_000


def _hash_contrasena(contrasena, sal=None):
    sal = sal or secrets.token_hex(16)
    derivado = hashlib.pbkdf2_hmac("sha256", contrasena.encode("utf-8"), bytes.fromhex(sal), _ITERACIONES_HASH)
    return f"{sal}${derivado.hex()}"


def _verificar_contrasena(contrasena, hash_guardado):
    if not hash_guardado:
        return False
    sal, _ = hash_guardado.split("$", 1)
    return secrets.compare_digest(_hash_contrasena(contrasena, sal), hash_guardado)


# ---------------------------------------------------------------------------
# Apartamentos
# ---------------------------------------------------------------------------


def insertar_apartamento(numero, torre, propietario, telefono=None):
    with conectar() as conexion:
        cursor = conexion.execute(
            "INSERT INTO apartamentos (numero, torre, propietario, telefono) VALUES (?, ?, ?, ?)",
            (numero, torre, propietario, telefono),
        )
        return cursor.lastrowid


def obtener_apartamento(apartamento_id):
    with conectar() as conexion:
        fila = conexion.execute(
            "SELECT * FROM apartamentos WHERE id = ?", (apartamento_id,)
        ).fetchone()
        return dict(fila) if fila else None


def listar_apartamentos():
    with conectar() as conexion:
        filas = conexion.execute("SELECT * FROM apartamentos ORDER BY torre, numero").fetchall()
        return [dict(f) for f in filas]


def eliminar_apartamento(apartamento_id):
    """
    Elimina un apartamento. Solo tiene sentido si ya no tiene residentes
    asociados (la tabla residentes tiene una referencia a apartamentos sin
    ON DELETE CASCADE a propósito, para no borrar residentes por accidente
    al dar de baja un apartamento) — por eso se valida antes de intentarlo.
    """
    with conectar() as conexion:
        quedan_residentes = conexion.execute(
            "SELECT COUNT(*) FROM residentes WHERE apartamento_id = ?", (apartamento_id,)
        ).fetchone()[0]
        if quedan_residentes:
            raise ValueError(
                f"No se puede eliminar: todavía hay {quedan_residentes} residente(s) "
                "asociados a este apartamento. Elimínalos primero."
            )
        conexion.execute("DELETE FROM apartamentos WHERE id = ?", (apartamento_id,))


# ---------------------------------------------------------------------------
# Residentes
# ---------------------------------------------------------------------------


def insertar_residente(nombre, documento, apartamento_id, es_propietario=False, contrasena=None):
    """
    contrasena es opcional: si se da, el residente queda con su acceso
    individual activado desde el registro (caso típico de autoregistro).
    Si no se da (por ejemplo, cuando lo registra administración), el
    residente queda sin contraseña hasta que la active él mismo — ver
    establecer_contrasena_residente().
    """
    password_hash = _hash_contrasena(contrasena) if contrasena else None
    with conectar() as conexion:
        cursor = conexion.execute(
            "INSERT INTO residentes (nombre, documento, apartamento_id, es_propietario, password_hash) VALUES (?, ?, ?, ?, ?)",
            (nombre, documento, apartamento_id, int(es_propietario), password_hash),
        )
        return cursor.lastrowid


def establecer_contrasena_residente(residente_id, contrasena):
    with conectar() as conexion:
        conexion.execute(
            "UPDATE residentes SET password_hash = ? WHERE id = ?",
            (_hash_contrasena(contrasena), residente_id),
        )


def obtener_residente_por_documento(documento):
    with conectar() as conexion:
        fila = conexion.execute("SELECT * FROM residentes WHERE documento = ?", (documento,)).fetchone()
        return dict(fila) if fila else None


def autenticar_residente(documento, contrasena):
    """Retorna el residente (dict) si el documento y la contraseña coinciden, o None si no."""
    residente = obtener_residente_por_documento(documento)
    if residente and _verificar_contrasena(contrasena, residente["password_hash"]):
        return residente
    return None


def listar_residentes_de_apartamento(apartamento_id):
    with conectar() as conexion:
        filas = conexion.execute(
            "SELECT * FROM residentes WHERE apartamento_id = ?", (apartamento_id,)
        ).fetchall()
        return [dict(f) for f in filas]


def eliminar_residente(residente_id):
    """Igual que eliminar_apartamento: no borra si el residente todavía tiene vehículos a su nombre."""
    with conectar() as conexion:
        quedan_vehiculos = conexion.execute(
            "SELECT COUNT(*) FROM vehiculos WHERE residente_id = ?", (residente_id,)
        ).fetchone()[0]
        if quedan_vehiculos:
            raise ValueError(
                f"No se puede eliminar: todavía hay {quedan_vehiculos} vehículo(s) "
                "registrados a nombre de este residente. Elimínalos primero."
            )
        conexion.execute("DELETE FROM residentes WHERE id = ?", (residente_id,))


# ---------------------------------------------------------------------------
# Vehículos
# ---------------------------------------------------------------------------


def insertar_vehiculo(placa, tipo, residente_id, marca=None, color=None):
    with conectar() as conexion:
        cursor = conexion.execute(
            "INSERT INTO vehiculos (placa, tipo, marca, color, residente_id) VALUES (?, ?, ?, ?, ?)",
            (placa.upper(), tipo, marca, color, residente_id),
        )
        return cursor.lastrowid


def buscar_vehiculo_por_placa(placa):
    with conectar() as conexion:
        fila = conexion.execute(
            "SELECT * FROM vehiculos WHERE placa = ?", (placa.upper(),)
        ).fetchone()
        return dict(fila) if fila else None


def listar_vehiculos_de_apartamento(apartamento_id):
    """Todos los vehículos de todos los residentes de un apartamento, con el nombre del residente incluido."""
    with conectar() as conexion:
        filas = conexion.execute(
            """SELECT vehiculos.*, residentes.nombre AS nombre_residente
               FROM vehiculos
               JOIN residentes ON residentes.id = vehiculos.residente_id
               WHERE residentes.apartamento_id = ?
               ORDER BY vehiculos.placa""",
            (apartamento_id,),
        ).fetchall()
        return [dict(f) for f in filas]


def eliminar_vehiculo(vehiculo_id):
    with conectar() as conexion:
        conexion.execute("DELETE FROM vehiculos WHERE id = ?", (vehiculo_id,))


# ---------------------------------------------------------------------------
# Visitantes
# ---------------------------------------------------------------------------


def insertar_visitante(placa, nombre_visitante, apartamento_id, fecha_inicio, fecha_fin, motivo=None, recurrente=False):
    with conectar() as conexion:
        cursor = conexion.execute(
            """INSERT INTO visitantes
               (placa, nombre_visitante, apartamento_id, fecha_inicio, fecha_fin, motivo, recurrente)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (placa.upper(), nombre_visitante, apartamento_id, fecha_inicio, fecha_fin, motivo, int(recurrente)),
        )
        return cursor.lastrowid


def listar_visitantes_activos_de_apartamento(apartamento_id):
    hoy = date.today().isoformat()
    with conectar() as conexion:
        filas = conexion.execute(
            """SELECT * FROM visitantes
               WHERE apartamento_id = ? AND fecha_inicio <= ? AND fecha_fin >= ?
               ORDER BY fecha_fin""",
            (apartamento_id, hoy, hoy),
        ).fetchall()
        return [dict(f) for f in filas]


def cancelar_visitante(visitante_id):
    """Cancela un visitante activo poniendo su fecha de fin en el pasado (ayer)."""
    ayer = (date.today() - timedelta(days=1)).isoformat()
    with conectar() as conexion:
        conexion.execute("UPDATE visitantes SET fecha_fin = ? WHERE id = ?", (ayer, visitante_id))


# ---------------------------------------------------------------------------
# Registros de ingreso
# ---------------------------------------------------------------------------


def insertar_registro_ingreso(placa_leida, placa_corregida, resultado, confianza=None, ruta_foto=None, autorizado_manual=None):
    with conectar() as conexion:
        cursor = conexion.execute(
            """INSERT INTO registros_ingreso
               (placa_leida, placa_corregida, marca_tiempo, resultado, confianza, ruta_foto, autorizado_manual)
               VALUES (?, ?, datetime('now', 'localtime'), ?, ?, ?, ?)""",
            (placa_leida.upper(), placa_corregida.upper(), resultado, confianza, ruta_foto, autorizado_manual),
        )
        return cursor.lastrowid


def listar_ultimos_registros(cantidad=10):
    with conectar() as conexion:
        filas = conexion.execute(
            "SELECT * FROM registros_ingreso ORDER BY id DESC LIMIT ?", (cantidad,)
        ).fetchall()
        return [dict(f) for f in filas]


def registros_por_rango_fechas(fecha_inicio, fecha_fin):
    with conectar() as conexion:
        filas = conexion.execute(
            """SELECT * FROM registros_ingreso
               WHERE date(marca_tiempo) BETWEEN ? AND ?
               ORDER BY marca_tiempo""",
            (fecha_inicio, fecha_fin),
        ).fetchall()
        return [dict(f) for f in filas]


# ---------------------------------------------------------------------------
# Consulta central de autorización
# ---------------------------------------------------------------------------


def consultar_placa(placa):
    """
    Determina el estado de autorización completo de una placa.

    Retorna un diccionario con al menos la clave "estado", que es una de:
    "residente", "visitante_activo", "visitante_vencido", "desconocido".

    Este es el punto único que usa tanto el pipeline (Semana 4) como la
    capa de autorización de la app (Semana 5/6), para que la lógica de
    "qué significa cada estado" viva en un solo lugar.
    """
    placa = placa.upper()

    vehiculo = buscar_vehiculo_por_placa(placa)
    if vehiculo:
        with conectar() as conexion:
            residente = conexion.execute(
                "SELECT * FROM residentes WHERE id = ?", (vehiculo["residente_id"],)
            ).fetchone()
            apartamento = conexion.execute(
                "SELECT * FROM apartamentos WHERE id = ?", (residente["apartamento_id"],)
            ).fetchone()

        return {
            "estado": "residente",
            "placa": placa,
            "vehiculo": vehiculo,
            "residente": dict(residente),
            "apartamento": dict(apartamento),
        }

    hoy = date.today().isoformat()
    with conectar() as conexion:
        visitante = conexion.execute(
            """SELECT * FROM visitantes
               WHERE placa = ?
               ORDER BY fecha_fin DESC LIMIT 1""",
            (placa,),
        ).fetchone()

    if visitante:
        apartamento = obtener_apartamento(visitante["apartamento_id"])
        vigente = visitante["fecha_inicio"] <= hoy <= visitante["fecha_fin"]
        return {
            "estado": "visitante_activo" if vigente else "visitante_vencido",
            "placa": placa,
            "visitante": dict(visitante),
            "apartamento": apartamento,
        }

    return {"estado": "desconocido", "placa": placa}


def buscar_coincidencias_parciales(placa_parcial, limite=3):
    """
    Busca placas de residentes o visitantes parecidas a un texto parcial.

    Se usa cuando el OCR lee con baja confianza: en vez de decir simplemente
    "desconocido", se le sugieren al vigilante las placas más parecidas
    registradas en el sistema.
    """
    placa_parcial = placa_parcial.upper()
    with conectar() as conexion:
        vehiculos = conexion.execute(
            "SELECT placa, 'residente' AS origen FROM vehiculos"
        ).fetchall()
        visitantes = conexion.execute(
            "SELECT DISTINCT placa, 'visitante' AS origen FROM visitantes"
        ).fetchall()

    candidatas = [dict(f) for f in vehiculos] + [dict(f) for f in visitantes]

    def distancia_simple(a, b):
        # Distancia de Hamming simplificada: cuenta posiciones distintas
        # entre textos de igual longitud, y penaliza fuerte si difieren en
        # longitud. Es suficiente para "parecido" sin agregar una librería
        # nueva al proyecto solo para esto.
        if len(a) != len(b):
            return abs(len(a) - len(b)) + 10
        return sum(1 for x, y in zip(a, b) if x != y)

    candidatas.sort(key=lambda c: distancia_simple(placa_parcial, c["placa"]))
    return candidatas[:limite]


# ---------------------------------------------------------------------------
# Datos de ejemplo
# ---------------------------------------------------------------------------

_NOMBRES = [
    "Carlos Ramírez", "María Gómez", "Andrés Torres", "Laura Pérez", "Juan Rodríguez",
    "Camila Herrera", "Diego Castro", "Valentina Ríos", "Santiago Moreno", "Isabella Vargas",
    "Felipe Ortiz", "Daniela Suárez", "Mateo Jiménez", "Sofía Cárdenas", "Nicolás Peña",
    "Gabriela Reyes", "Sebastián Duarte", "Paula Navarro", "Alejandro Cruz", "Manuela Rojas",
]

_TORRES = ["A", "B", "C"]


def cargar_datos_ejemplo():
    """
    Crea 15 apartamentos, ~20 residentes, 25 vehículos y varios visitantes
    en distintos estados (activo, vencido, recurrente), para poder probar
    el resto del sistema sin depender de datos reales todavía.
    """
    crear_tablas()

    with conectar() as conexion:
        ya_hay_datos = conexion.execute("SELECT COUNT(*) FROM apartamentos").fetchone()[0] > 0
    if ya_hay_datos:
        print("Ya existen datos en la base. No se vuelven a cargar (evita duplicados).")
        print("Si quieres regenerarlos, borra el archivo alpr_porteria.db y vuelve a ejecutar este script.")
        return

    apartamento_ids = []
    for i in range(15):
        numero = str(100 + (i % 5) * 100 + (i % 5) + 1).zfill(3)
        torre = _TORRES[i % len(_TORRES)]
        propietario = _NOMBRES[i % len(_NOMBRES)]
        apartamento_ids.append(
            insertar_apartamento(numero, torre, propietario, telefono=f"300{1000000 + i}")
        )

    residente_ids = []
    for i, apartamento_id in enumerate(apartamento_ids):
        nombre = _NOMBRES[i % len(_NOMBRES)]
        residente_ids.append(
            insertar_residente(nombre, documento=f"CC{100000 + i}", apartamento_id=apartamento_id, es_propietario=True)
        )
        # Un segundo residente (no propietario) en algunos apartamentos, para variar los datos
        if i % 3 == 0:
            residente_ids.append(
                insertar_residente(
                    _NOMBRES[(i + 7) % len(_NOMBRES)],
                    documento=f"CC{200000 + i}",
                    apartamento_id=apartamento_id,
                    es_propietario=False,
                )
            )

    marcas_carro = ["Chevrolet", "Renault", "Mazda", "Toyota", "Kia"]
    marcas_moto = ["Yamaha", "Suzuki", "AKT", "Honda"]
    colores = ["blanco", "gris", "negro", "rojo", "azul"]

    from src.generador_placas import generar_texto_placa

    placas_usadas = set()

    def placa_nueva(tipo):
        while True:
            placa = generar_texto_placa(tipo)
            if placa not in placas_usadas:
                placas_usadas.add(placa)
                return placa

    for i in range(25):
        residente_id = residente_ids[i % len(residente_ids)]
        tipo = "moto" if i % 4 == 0 else "carro"
        placa = placa_nueva(tipo)
        marca = (marcas_moto if tipo == "moto" else marcas_carro)[i % 5 if tipo == "carro" else i % 4]
        insertar_vehiculo(placa, tipo, residente_id, marca=marca, color=colores[i % len(colores)])

    hoy = date.today()
    visitantes_ejemplo = [
        # (offset_inicio_dias, offset_fin_dias, motivo, recurrente)
        (-1, 1, "Visita familiar", False),     # activo ahora
        (-10, -2, "Entrega", False),           # vencido
        (0, 0, "Domicilio", False),            # activo solo hoy
        (-30, 60, "Servicio doméstico", True), # recurrente de largo plazo
        (2, 5, "Visita programada", False),    # empieza en el futuro (aún no vigente hoy)
    ]
    for i, (ini, fin, motivo, recurrente) in enumerate(visitantes_ejemplo):
        apartamento_id = apartamento_ids[i % len(apartamento_ids)]
        placa = placa_nueva("carro")
        insertar_visitante(
            placa,
            nombre_visitante=_NOMBRES[(i + 3) % len(_NOMBRES)],
            apartamento_id=apartamento_id,
            fecha_inicio=(hoy + timedelta(days=ini)).isoformat(),
            fecha_fin=(hoy + timedelta(days=fin)).isoformat(),
            motivo=motivo,
            recurrente=recurrente,
        )

    print("Datos de ejemplo cargados: 15 apartamentos, "
          f"{len(residente_ids)} residentes, 25 vehículos, {len(visitantes_ejemplo)} visitantes.")


if __name__ == "__main__":
    crear_tablas()
    print(f"Base de datos lista en: {config.BASE_DATOS_SQLITE}")
    cargar_datos_ejemplo()

    apartamentos = listar_apartamentos()
    print(f"\nApartamentos registrados: {len(apartamentos)}")

    # Prueba rápida de consultar_placa con una placa real de la base
    with conectar() as conexion:
        alguna_placa = conexion.execute("SELECT placa FROM vehiculos LIMIT 1").fetchone()
    if alguna_placa:
        resultado = consultar_placa(alguna_placa["placa"])
        print(f"\nPrueba consultar_placa('{alguna_placa['placa']}'):")
        print(f"  Estado: {resultado['estado']}")
