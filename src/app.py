"""
Interfaz Streamlit del sistema (Semana 6), con tres roles: vigilante,
propietario y administración. También incluye el "modo maqueta" de la
Semana 7 (ROI, calibración e indicador de calidad de imagen) dentro del
panel del vigilante.

Por qué Streamlit: permite construir una interfaz completa sin escribir
HTML/CSS/JavaScript por separado — todo el proyecto se queda en Python,
que es lo que los estudiantes ya conocen del resto del stack.

Nota sobre el video: Streamlit no tiene un widget nativo de video en vivo
continuo sin librerías adicionales fuera de nuestro stack (como
streamlit-webrtc). Aquí se implementa video en vivo con el patrón estándar
de OpenCV + un contenedor `st.empty()` que se actualiza en bucle mientras
una casilla de activación esté marcada (ver PARTE F de la guía: "Streamlit
no refresca el video").
"""

import sqlite3
import sys
import time
from datetime import date, datetime
from pathlib import Path

import cv2
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from src import autorizacion, base_datos
from src.detector import DetectorVehiculos
from src.pipeline import VotadorTemporal, _leer_y_validar
from src.utilidades_imagen import escribir_imagen, leer_imagen
from src.validador import validar_formato

# ---------------------------------------------------------------------------
# Autenticación simple por rol
#
# No es seguridad real (las contraseñas están en texto plano en el código):
# el objetivo es demostrar el CONCEPTO de separar roles, no proteger datos
# sensibles de verdad. Así lo pide explícitamente el Prompt 6.2.
# ---------------------------------------------------------------------------

CONTRASENAS_POR_ROL = {
    "Vigilante": "vigilante123",
    "Administración": "admin123",
}


def pantalla_login():
    st.title("Sistema ALPR Portería — Ingreso")

    tab_residente, tab_personal = st.tabs(["🏠 Residentes", "🪪 Vigilante / Administración"])

    with tab_residente:
        _pantalla_login_residente()

    with tab_personal:
        st.caption("Para el vigilante de la portería y para administración del conjunto.")
        rol = st.selectbox("Rol", list(CONTRASENAS_POR_ROL.keys()))
        contrasena = st.text_input("Contraseña", type="password", key="contrasena_personal")

        if st.button("Entrar", type="primary", key="entrar_personal"):
            if contrasena == CONTRASENAS_POR_ROL[rol]:
                st.session_state.rol = rol
                st.rerun()
            else:
                st.error("Contraseña incorrecta.")

        with st.expander("Contraseñas de demostración (quitar antes de la feria si se desea)"):
            for r, c in CONTRASENAS_POR_ROL.items():
                st.write(f"- **{r}**: `{c}`")


def _pantalla_login_residente():
    """
    Login individual por residente (documento + contraseña propia), en vez
    de elegir el apartamento de una lista abierta como en la primera
    versión de la app. Cada residente es dueño de su propia cuenta: la
    contraseña se guarda como un hash (ver base_datos._hash_contrasena),
    nunca en texto plano.
    """
    sub_ingresar, sub_activar, sub_nuevo = st.tabs(["Iniciar sesión", "Activar mi acceso", "Soy nuevo/a"])

    with sub_ingresar:
        documento = st.text_input("Número de documento", key="login_documento")
        contrasena = st.text_input("Contraseña", type="password", key="login_contrasena_residente")
        if st.button("Entrar", type="primary", key="entrar_residente"):
            residente = base_datos.autenticar_residente(documento, contrasena)
            if residente:
                st.session_state.rol = "Residente"
                st.session_state.residente_actual = residente
                st.rerun()
            else:
                st.error(
                    "Documento o contraseña incorrectos. Si administración ya te registró pero "
                    "todavía no tienes contraseña, usa la pestaña 'Activar mi acceso'."
                )

    with sub_activar:
        st.caption(
            "Para residentes que administración YA registró en el sistema, pero que "
            "todavía no han creado su contraseña de acceso."
        )
        documento_activar = st.text_input("Número de documento", key="activar_documento")
        if documento_activar:
            residente = base_datos.obtener_residente_por_documento(documento_activar)
            if not residente:
                st.warning("Ese documento no está registrado todavía. Usa la pestaña 'Soy nuevo/a'.")
            elif residente["password_hash"]:
                st.info("Esta cuenta ya tiene una contraseña activa. Usa la pestaña 'Iniciar sesión'.")
            else:
                st.success(f"Encontrado: {residente['nombre']}. Crea tu contraseña:")
                nueva_contrasena = st.text_input("Nueva contraseña", type="password", key="activar_contrasena")
                if st.button("Activar acceso", key="boton_activar"):
                    if len(nueva_contrasena) < 4:
                        st.error("La contraseña debe tener al menos 4 caracteres.")
                    else:
                        base_datos.establecer_contrasena_residente(residente["id"], nueva_contrasena)
                        st.success("Acceso activado. Ya puedes iniciar sesión en la otra pestaña.")

    with sub_nuevo:
        st.caption("Para residentes que todavía no están registrados en el sistema.")
        apartamentos = base_datos.listar_apartamentos()
        if not apartamentos:
            st.info("Todavía no hay apartamentos creados — pídele a administración que registre el tuyo primero.")
        else:
            with st.form("form_residente_nuevo"):
                opciones_apto = {f"{a['numero']} — Torre {a['torre']}": a["id"] for a in apartamentos}
                apto_seleccionado = st.selectbox("Tu apartamento", list(opciones_apto.keys()))
                nombre_nuevo = st.text_input("Nombre completo")
                documento_nuevo = st.text_input("Número de documento")
                es_propietario_nuevo = st.checkbox("Soy propietario del apartamento")
                contrasena_nueva = st.text_input("Crea una contraseña", type="password")
                if st.form_submit_button("Registrarme"):
                    if not nombre_nuevo or not documento_nuevo or len(contrasena_nueva) < 4:
                        st.error("Nombre, documento y una contraseña de al menos 4 caracteres son obligatorios.")
                    else:
                        try:
                            base_datos.insertar_residente(
                                nombre_nuevo, documento_nuevo, opciones_apto[apto_seleccionado],
                                es_propietario=es_propietario_nuevo, contrasena=contrasena_nueva,
                            )
                            st.success("Cuenta creada. Ya puedes iniciar sesión en la pestaña 'Iniciar sesión'.")
                        except sqlite3.IntegrityError:
                            st.error(f"Ya existe un residente con el documento '{documento_nuevo}'.")


def cerrar_sesion():
    if st.sidebar.button("Cerrar sesión"):
        st.session_state.rol = None
        st.session_state.residente_actual = None
        st.rerun()


# ---------------------------------------------------------------------------
# Recursos costosos: cargar una sola vez por sesión de servidor, no en cada
# recarga del script (Streamlit vuelve a correr el archivo completo en cada
# interacción del usuario, así que sin cache el modelo se recargaría todo
# el tiempo).
# ---------------------------------------------------------------------------


@st.cache_resource
def obtener_detector():
    return DetectorVehiculos(modo="auto")


@st.cache_resource
def obtener_talanquera():
    # Objetivo opcional (Semana 9). Si pyserial no está instalado o no hay
    # Arduino conectado, talanquera.conectado queda en False y el resto de
    # la app sigue funcionando normal (no se muestra el botón).
    from src.talanquera import Talanquera
    return Talanquera()


def _calidad_imagen(imagen_gris):
    """
    Indicador simple de calidad, útil en el modo maqueta (Semana 7): si la
    luz del salón de la feria es distinta a la del ensayo, esto avisa antes
    de que el sistema falle en silencio.

    - Nitidez: varianza del filtro Laplaciano. Una imagen borrosa tiene
      transiciones de intensidad más suaves, así que su varianza es baja.
    - Brillo: promedio de intensidad de los píxeles (0 = negro, 255 = blanco).
    """
    nitidez = cv2.Laplacian(imagen_gris, cv2.CV_64F).var()
    brillo = imagen_gris.mean()
    return nitidez, brillo


def _evaluar_calidad(nitidez, brillo):
    if nitidez < 50:
        return "⚠️ Imagen borrosa — revisa el enfoque de la cámara", "amarillo"
    if brillo < 60:
        return "⚠️ Muy poca luz — acerca una fuente de luz a la maqueta", "amarillo"
    if brillo > 200:
        return "⚠️ Demasiada luz / reflejo — reduce la iluminación directa", "amarillo"
    return "✅ Condiciones de imagen adecuadas", "verde"


# ---------------------------------------------------------------------------
# Panel del vigilante (Prompt 6.1)
# ---------------------------------------------------------------------------


def _mostrar_resultado_autorizacion(resultado, imagen_bgr=None, contexto="default"):
    # Streamlit vuelve a correr TODO el script en cada interacción, y las
    # pestañas no impiden que el código de las otras se ejecute (solo
    # esconden visualmente su contenido) — si el vigilante ya subió una
    # foto en una pestaña Y tiene una captura de cámara pendiente en otra,
    # esta función se llama más de una vez en la misma corrida, y sin una
    # `key` única cada botón "Autorizar"/"Rechazar" chocaría con el mismo
    # ID autogenerado (StreamlitDuplicateElementId). `contexto` distingue
    # de qué pestaña vino cada llamada para que las claves no se repitan.
    color_fondo = {"verde": "#1e6b2e", "amarillo": "#8a6d00", "rojo": "#7a1e1e"}[resultado["color"]]

    st.markdown(
        f"""
        <div style="background-color:{color_fondo}; padding:1.2rem; border-radius:0.5rem;">
            <h1 style="color:white; margin:0; font-size:3rem;">{resultado.get('placa', resultado.get('placa_leida', '?'))}</h1>
            <p style="color:white; font-size:1.3rem; margin-top:0.5rem;">{resultado['mensaje']}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_foto, col_datos = st.columns([1, 2])

    with col_foto:
        if imagen_bgr is not None:
            st.image(cv2.cvtColor(imagen_bgr, cv2.COLOR_BGR2RGB), caption="Vehículo capturado")

    with col_datos:
        if resultado["estado"] == "residente":
            apto = resultado["apartamento"]
            st.markdown(f"### Apartamento **{apto['numero']} — Torre {apto['torre']}**")
            st.write(f"Residente: {resultado['residente']['nombre']}")
            st.write(f"Vehículo: {resultado['vehiculo']['tipo']} {resultado['vehiculo'].get('marca') or ''} {resultado['vehiculo'].get('color') or ''}")

        elif resultado["estado"] in ("visitante_activo", "visitante_vencido"):
            apto = resultado["apartamento"]
            visitante = resultado["visitante"]
            st.markdown(f"### Apartamento **{apto['numero']} — Torre {apto['torre']}**")
            st.write(f"Visitante: {visitante['nombre_visitante']}")
            st.write(f"Autorizado por: {apto['propietario']}")
            st.write(f"Vigencia: {visitante['fecha_inicio']} a {visitante['fecha_fin']}")

        elif resultado["estado"] == "baja_confianza":
            st.write("Coincidencias sugeridas:")
            for sugerencia in resultado.get("sugerencias", []):
                st.write(f"- `{sugerencia['placa']}` ({sugerencia['origen']})")

        else:
            st.write("Esta placa no está registrada en el sistema.")

    talanquera = obtener_talanquera()
    mostrar_boton_talanquera = talanquera.conectado and resultado["estado"] in ("residente", "visitante_activo")

    columnas = st.columns(3) if mostrar_boton_talanquera else st.columns(2)
    col_ok, col_no = columnas[0], columnas[1]

    if col_ok.button("✅ Autorizar", use_container_width=True, key=f"autorizar_{contexto}"):
        _registrar_decision(resultado, autorizado=True, imagen_bgr=imagen_bgr)
        st.success("Ingreso autorizado y registrado.")
    if col_no.button("❌ Rechazar", use_container_width=True, key=f"rechazar_{contexto}"):
        _registrar_decision(resultado, autorizado=False, imagen_bgr=imagen_bgr)
        st.warning("Ingreso rechazado y registrado.")

    if mostrar_boton_talanquera:
        # MODO SEGURO: este botón solo existe si el vigilante lo presiona a
        # propósito, nunca se abre solo a partir de la lectura del OCR (ver
        # arduino/talanquera/talanquera.ino y src/talanquera.py).
        if columnas[2].button("🚧 Abrir talanquera", use_container_width=True, key=f"talanquera_{contexto}"):
            resultado_comando = talanquera.abrir()
            if resultado_comando["ok"]:
                st.success(f"Talanquera: {resultado_comando['mensaje']}")
            else:
                st.error(f"No se pudo abrir la talanquera: {resultado_comando['mensaje']}")


def _registrar_decision(resultado, autorizado, imagen_bgr=None):
    ruta_foto = None
    if imagen_bgr is not None:
        carpeta_capturas = config.DIR_DATA_REALES / "capturas_ingreso"
        carpeta_capturas.mkdir(parents=True, exist_ok=True)
        nombre = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{resultado.get('placa', 'NA')}.jpg"
        ruta_foto = carpeta_capturas / nombre
        escribir_imagen(ruta_foto, imagen_bgr)

    placa = resultado.get("placa") or resultado.get("placa_leida", "")
    estado_bd = "residente" if resultado["estado"] == "residente" else (
        "visitante" if resultado["estado"].startswith("visitante") else "desconocido"
    )
    base_datos.insertar_registro_ingreso(
        placa_leida=placa,
        placa_corregida=placa,
        resultado=estado_bd,
        confianza=resultado.get("confianza"),
        ruta_foto=str(ruta_foto) if ruta_foto else None,
        autorizado_manual=int(autorizado),
    )


def _procesar_captura(imagen_bgr, detector, contexto="captura"):
    vehiculos = detector.detectar_en_imagen(imagen_bgr)
    if not vehiculos:
        st.info("No se detectó ningún vehículo en la imagen.")
        return

    vehiculo = max(vehiculos, key=lambda v: v["confianza"])
    lectura = _leer_y_validar(vehiculo["recorte"])
    resultado = autorizacion.evaluar_ingreso(lectura["texto_corregido"], lectura["confianza_final"])
    _mostrar_resultado_autorizacion(resultado, imagen_bgr=imagen_bgr, contexto=contexto)


def _seccion_modo_maqueta():
    """Ajustes del Prompt 7.1: ROI, calibración de distancia e indicador de calidad."""
    with st.sidebar.expander("🔧 Modo maqueta (Semana 7)"):
        activo = st.checkbox("Activar modo maqueta", value=False)
        if not activo:
            return None

        st.caption("Región de interés (ROI): solo se procesa esta zona del encuadre.")
        x1 = st.slider("ROI - borde izquierdo (%)", 0, 100, 0)
        x2 = st.slider("ROI - borde derecho (%)", 0, 100, 100)
        y1 = st.slider("ROI - borde superior (%)", 0, 100, 0)
        y2 = st.slider("ROI - borde inferior (%)", 0, 100, 100)

        st.caption("Calibración de distancia (referencia informativa, en cm)")
        distancia_min = st.number_input("Distancia mínima", value=15, min_value=1)
        distancia_max = st.number_input("Distancia máxima", value=60, min_value=1)

        return {"roi": (x1, y1, x2, y2), "distancia_min": distancia_min, "distancia_max": distancia_max}


def _aplicar_roi(imagen, roi):
    if roi is None:
        return imagen
    alto, ancho = imagen.shape[:2]
    x1, y1, x2, y2 = roi["roi"]
    return imagen[int(alto * y1 / 100):int(alto * y2 / 100), int(ancho * x1 / 100):int(ancho * x2 / 100)]


def panel_vigilante():
    st.title("🚗 Panel del vigilante")

    config_maqueta = _seccion_modo_maqueta()
    detector = obtener_detector()

    st.sidebar.markdown("---")
    with st.sidebar:
        st.subheader("Buscador manual")
        placa_manual = st.text_input("Placa (completa o parcial)")
        if placa_manual:
            coincidencias = base_datos.buscar_coincidencias_parciales(placa_manual, limite=5)
            for c in coincidencias:
                st.write(f"`{c['placa']}` — {c['origen']}")

    # Solo cámara en vivo: se quitaron "Subir foto" y "Subir video" porque en
    # el uso real de la portería el vigilante siempre captura con la webcam,
    # no sube archivos — menos opciones, menos confusión en el momento.
    st.caption(
        "Modo 'un vistazo': toma una foto con la webcam (Streamlit no soporta "
        "video continuo sin librerías fuera del stack del proyecto)."
    )

    # El botón interno de la cámara dice "Take Photo" en inglés y Streamlit no
    # da una forma oficial de cambiarle el texto — se renombra con un truco de
    # CSS: se oculta el texto original y se dibuja "Validar Ingreso" encima,
    # apuntando al mismo botón exacto que usa Streamlit internamente
    # (data-testid="stCameraInputButton"). Si una futura versión de Streamlit
    # cambia ese nombre interno, este truco deja de aplicarse (el botón sigue
    # funcionando igual, solo volvería a decir "Take Photo").
    st.markdown(
        """
        <style>
        button[data-testid="stCameraInputButton"] {
            font-size: 0;
            position: relative;
        }
        button[data-testid="stCameraInputButton"]::after {
            content: "Validar Ingreso";
            font-size: 1rem;
            position: absolute;
            inset: 0;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Recorte a un tercio del ancho: el recuadro de la cámara a ancho completo
    # queda demasiado grande y hace difícil encuadrar bien la placa.
    # La cámara va en la columna angosta (un tercio) y el resultado de la
    # validación en la columna ancha de al lado, en la misma fila — antes el
    # resultado aparecía debajo, obligando a bajar la pantalla para verlo.
    col_camara, col_resultado = st.columns([1, 2])
    with col_camara:
        foto_camara = st.camera_input("Capturar")

    with col_resultado:
        if foto_camara:
            import numpy as np
            datos = np.frombuffer(foto_camara.getvalue(), dtype="uint8")
            imagen = cv2.imdecode(datos, cv2.IMREAD_COLOR)
            imagen = _aplicar_roi(imagen, config_maqueta)
            _procesar_captura(imagen, detector, contexto="camara")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Últimos 10 ingresos")
    for registro in base_datos.listar_ultimos_registros(10):
        icono = {"residente": "🟢", "visitante": "🟡", "desconocido": "🔴"}.get(registro["resultado"], "⚪")
        st.sidebar.write(f"{icono} `{registro['placa_corregida']}` — {registro['marca_tiempo']}")


# ---------------------------------------------------------------------------
# Panel del propietario (Prompt 6.2)
# ---------------------------------------------------------------------------


def panel_propietario():
    residente_actual = st.session_state.get("residente_actual")
    apartamento_id = residente_actual["apartamento_id"]
    apartamento = base_datos.obtener_apartamento(apartamento_id)

    st.title("🏠 Panel del propietario")
    st.caption(
        f"Conectado como **{residente_actual['nombre']}** — "
        f"apto. {apartamento['numero']}, Torre {apartamento['torre']}"
    )

    tab_vehiculos, tab_nuevo, tab_activos, tab_historial = st.tabs(
        ["Mis datos y vehículos", "Registrar visitante", "Visitantes activos", "Historial"]
    )

    with tab_vehiculos:
        residentes = base_datos.listar_residentes_de_apartamento(apartamento_id)

        st.subheader("Residentes de este apartamento")
        for residente in residentes:
            col1, col2 = st.columns([4, 1])
            etiqueta_propietario = " (propietario)" if residente["es_propietario"] else ""
            etiqueta_yo = " — **tú**" if residente["id"] == residente_actual["id"] else ""
            col1.write(f"👤 {residente['nombre']}{etiqueta_propietario}{etiqueta_yo} — documento {residente['documento']}")
            if residente["id"] != residente_actual["id"] and col2.button("Eliminar", key=f"eliminar_residente_{residente['id']}"):
                try:
                    base_datos.eliminar_residente(residente["id"])
                    st.success("Residente eliminado.")
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))

        with st.expander("➕ Registrar otro residente de este apartamento (familiar, etc.)"):
            st.caption(
                "La persona que registres aquí podrá crear su propia contraseña después, "
                "desde la pestaña 'Activar mi acceso' de la pantalla de ingreso, usando su documento."
            )
            with st.form("form_nuevo_residente"):
                nombre_residente = st.text_input("Nombre completo")
                documento_residente = st.text_input("Número de documento")
                es_propietario = st.checkbox("Es propietario del apartamento")
                if st.form_submit_button("Registrar residente"):
                    if not nombre_residente or not documento_residente:
                        st.error("Nombre y documento son obligatorios.")
                    else:
                        try:
                            base_datos.insertar_residente(nombre_residente, documento_residente, apartamento_id, es_propietario)
                            st.success(f"Residente '{nombre_residente}' registrado.")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error(f"Ya existe un residente con el documento '{documento_residente}'.")

        st.markdown("---")
        st.subheader("Vehículos registrados")
        vehiculos = base_datos.listar_vehiculos_de_apartamento(apartamento_id)
        if not vehiculos:
            st.info("Todavía no hay vehículos registrados en este apartamento.")
        for v in vehiculos:
            col1, col2 = st.columns([4, 1])
            col1.write(f"🚙 `{v['placa']}` — {v['tipo']} {v['marca'] or ''} {v['color'] or ''} (de: {v['nombre_residente']})")
            if col2.button("Eliminar", key=f"eliminar_vehiculo_{v['id']}"):
                base_datos.eliminar_vehiculo(v["id"])
                st.success("Vehículo eliminado.")
                st.rerun()

        if not residentes:
            st.caption("Registra al menos un residente arriba antes de poder agregar un vehículo.")
        else:
            with st.expander("➕ Registrar un vehículo autorizado permanente"):
                with st.form("form_nuevo_vehiculo_propio"):
                    opciones_residente = {r["nombre"]: r["id"] for r in residentes}
                    nombre_dueno = st.selectbox("¿A nombre de quién?", list(opciones_residente.keys()))
                    placa_vehiculo = st.text_input("Placa").upper()
                    tipo_vehiculo = st.radio("Tipo", ["carro", "moto"], horizontal=True)
                    marca_vehiculo = st.text_input("Marca (opcional)")
                    color_vehiculo = st.text_input("Color (opcional)")
                    if st.form_submit_button("Registrar vehículo"):
                        formato_ok = validar_formato(placa_vehiculo) is not None
                        if not placa_vehiculo or not formato_ok:
                            st.error(
                                "La placa no tiene un formato colombiano válido "
                                "(ABC123 para carro, ABC12D para moto)."
                            )
                        else:
                            try:
                                base_datos.insertar_vehiculo(
                                    placa_vehiculo, tipo_vehiculo,
                                    opciones_residente[nombre_dueno],
                                    marca=marca_vehiculo or None, color=color_vehiculo or None,
                                )
                                st.success(f"Vehículo '{placa_vehiculo}' registrado.")
                                st.rerun()
                            except sqlite3.IntegrityError:
                                st.error(f"La placa '{placa_vehiculo}' ya está registrada.")

    with tab_nuevo:
        with st.form("form_nuevo_visitante"):
            placa = st.text_input("Placa del visitante").upper()
            nombre = st.text_input("Nombre del visitante")
            motivo = st.text_input("Motivo de la visita")
            tipo_vigencia = st.radio("Vigencia", ["Solo hoy", "Rango de fechas", "Recurrente"])

            if tipo_vigencia == "Solo hoy":
                fecha_inicio = fecha_fin = date.today()
                recurrente = False
            elif tipo_vigencia == "Rango de fechas":
                fecha_inicio = st.date_input("Desde", value=date.today())
                fecha_fin = st.date_input("Hasta", value=date.today())
                recurrente = False
            else:
                fecha_inicio = st.date_input("Desde", value=date.today())
                fecha_fin = st.date_input("Hasta (fin de la autorización recurrente)", value=date.today())
                recurrente = True

            if st.form_submit_button("Registrar visitante"):
                if not placa or not nombre:
                    st.error("La placa y el nombre son obligatorios.")
                else:
                    base_datos.insertar_visitante(
                        placa, nombre, apartamento_id,
                        fecha_inicio.isoformat(), fecha_fin.isoformat(),
                        motivo=motivo, recurrente=recurrente,
                    )
                    st.success(f"Visitante '{nombre}' registrado con placa {placa}.")

    with tab_activos:
        activos = base_datos.listar_visitantes_activos_de_apartamento(apartamento_id)
        if not activos:
            st.info("No hay visitantes activos en este momento.")
        for v in activos:
            col1, col2 = st.columns([4, 1])
            col1.write(f"`{v['placa']}` — {v['nombre_visitante']} — hasta {v['fecha_fin']} ({v['motivo'] or 'sin motivo'})")
            if col2.button("Cancelar", key=f"cancelar_{v['id']}"):
                base_datos.cancelar_visitante(v["id"])
                st.rerun()

    with tab_historial:
        with base_datos.conectar() as conexion:
            historial = conexion.execute(
                "SELECT * FROM visitantes WHERE apartamento_id = ? ORDER BY fecha_inicio DESC", (apartamento_id,)
            ).fetchall()
        for v in historial:
            st.write(f"`{v['placa']}` — {v['nombre_visitante']} — {v['fecha_inicio']} a {v['fecha_fin']}")


# ---------------------------------------------------------------------------
# Panel de administración (Prompt 6.2)
# ---------------------------------------------------------------------------


def panel_administracion():
    st.title("🛠️ Panel de administración")

    tab_apartamentos, tab_residentes, tab_vehiculos, tab_reportes, tab_estadisticas = st.tabs(
        ["Apartamentos", "Residentes", "Vehículos", "Reportes", "Estadísticas"]
    )

    with tab_apartamentos:
        with st.form("form_nuevo_apartamento"):
            st.write("Nuevo apartamento")
            numero = st.text_input("Número")
            torre = st.text_input("Torre")
            propietario = st.text_input("Propietario")
            telefono = st.text_input("Teléfono")
            if st.form_submit_button("Crear apartamento"):
                if not numero or not torre or not propietario:
                    st.error("Número, torre y propietario son obligatorios.")
                else:
                    try:
                        base_datos.insertar_apartamento(numero, torre, propietario, telefono or None)
                        st.success("Apartamento creado.")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error(f"Ya existe un apartamento {numero} en la torre {torre}.")

        st.markdown("---")
        st.write("Apartamentos existentes")
        for a in base_datos.listar_apartamentos():
            col1, col2 = st.columns([4, 1])
            col1.write(f"**{a['numero']} — Torre {a['torre']}** — {a['propietario']} — {a['telefono'] or 'sin teléfono'}")
            if col2.button("Eliminar", key=f"admin_eliminar_apto_{a['id']}"):
                try:
                    base_datos.eliminar_apartamento(a["id"])
                    st.success("Apartamento eliminado.")
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))

    with tab_residentes:
        apartamentos = base_datos.listar_apartamentos()
        if not apartamentos:
            st.info("Crea primero un apartamento en la pestaña anterior.")
        else:
            opciones_apto = {f"{a['numero']} — Torre {a['torre']}": a["id"] for a in apartamentos}

            with st.form("form_nuevo_residente_admin"):
                st.write("Nuevo residente")
                apto_seleccionado = st.selectbox("Apartamento", list(opciones_apto.keys()))
                nombre_residente = st.text_input("Nombre completo")
                documento_residente = st.text_input("Documento")
                es_propietario = st.checkbox("Es propietario")
                if st.form_submit_button("Registrar residente"):
                    if not nombre_residente or not documento_residente:
                        st.error("Nombre y documento son obligatorios.")
                    else:
                        try:
                            base_datos.insertar_residente(
                                nombre_residente, documento_residente,
                                opciones_apto[apto_seleccionado], es_propietario,
                            )
                            st.success(f"Residente '{nombre_residente}' registrado.")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error(f"Ya existe un residente con el documento '{documento_residente}'.")

            st.markdown("---")
            st.write("Residentes existentes")
            for apto in apartamentos:
                residentes = base_datos.listar_residentes_de_apartamento(apto["id"])
                for r in residentes:
                    col1, col2 = st.columns([4, 1])
                    etiqueta = " (propietario)" if r["es_propietario"] else ""
                    col1.write(f"👤 {r['nombre']}{etiqueta} — doc. {r['documento']} — apto. {apto['numero']} torre {apto['torre']}")
                    if col2.button("Eliminar", key=f"admin_eliminar_residente_{r['id']}"):
                        try:
                            base_datos.eliminar_residente(r["id"])
                            st.success("Residente eliminado.")
                            st.rerun()
                        except ValueError as error:
                            st.error(str(error))

    with tab_vehiculos:
        with base_datos.conectar() as conexion:
            todos_residentes = [dict(f) for f in conexion.execute("SELECT * FROM residentes ORDER BY nombre").fetchall()]

        if not todos_residentes:
            st.info("Registra primero al menos un residente en la pestaña anterior.")
        else:
            opciones_residente = {r["nombre"]: r["id"] for r in todos_residentes}

            with st.form("form_nuevo_vehiculo_admin"):
                st.write("Nuevo vehículo")
                dueno_seleccionado = st.selectbox("Residente", list(opciones_residente.keys()))
                placa_nueva = st.text_input("Placa").upper()
                tipo_nuevo = st.radio("Tipo", ["carro", "moto"], horizontal=True)
                marca_nueva = st.text_input("Marca (opcional)")
                color_nuevo = st.text_input("Color (opcional)")
                if st.form_submit_button("Registrar vehículo"):
                    if not placa_nueva or not validar_formato(placa_nueva):
                        st.error("La placa no tiene un formato colombiano válido (ABC123 o ABC12D).")
                    else:
                        try:
                            base_datos.insertar_vehiculo(
                                placa_nueva, tipo_nuevo, opciones_residente[dueno_seleccionado],
                                marca=marca_nueva or None, color=color_nuevo or None,
                            )
                            st.success(f"Vehículo '{placa_nueva}' registrado.")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error(f"La placa '{placa_nueva}' ya está registrada.")

            st.markdown("---")
            st.write("Vehículos existentes")
            with base_datos.conectar() as conexion:
                vehiculos = conexion.execute(
                    """SELECT vehiculos.*, residentes.nombre AS nombre_residente
                       FROM vehiculos JOIN residentes ON residentes.id = vehiculos.residente_id
                       ORDER BY vehiculos.placa"""
                ).fetchall()
            for v in vehiculos:
                col1, col2 = st.columns([4, 1])
                col1.write(f"🚙 `{v['placa']}` — {v['tipo']} {v['marca'] or ''} {v['color'] or ''} (de: {v['nombre_residente']})")
                if col2.button("Eliminar", key=f"admin_eliminar_vehiculo_{v['id']}"):
                    base_datos.eliminar_vehiculo(v["id"])
                    st.success("Vehículo eliminado.")
                    st.rerun()

    with tab_reportes:
        col1, col2 = st.columns(2)
        fecha_inicio = col1.date_input("Desde", value=date.today())
        fecha_fin = col2.date_input("Hasta", value=date.today())

        if st.button("Generar reporte"):
            registros = base_datos.registros_por_rango_fechas(fecha_inicio.isoformat(), fecha_fin.isoformat())
            if not registros:
                st.info("No hay registros en ese rango de fechas.")
            else:
                import pandas as pd
                df = pd.DataFrame(registros)
                st.dataframe(df, use_container_width=True)
                st.download_button(
                    "Descargar CSV",
                    df.to_csv(index=False).encode("utf-8"),
                    file_name=f"reporte_ingresos_{fecha_inicio}_{fecha_fin}.csv",
                    mime="text/csv",
                )

    with tab_estadisticas:
        with base_datos.conectar() as conexion:
            todos = conexion.execute("SELECT * FROM registros_ingreso").fetchall()

        if not todos:
            st.info("Todavía no hay registros de ingreso para calcular estadísticas.")
            return

        import pandas as pd
        df = pd.DataFrame([dict(r) for r in todos])
        df["fecha"] = pd.to_datetime(df["marca_tiempo"]).dt.date

        col1, col2, col3 = st.columns(3)
        col1.metric("Ingresos totales", len(df))
        tasa_reconocidos = (df["resultado"] != "desconocido").mean() * 100
        col2.metric("Tasa de reconocimiento", f"{tasa_reconocidos:.1f}%")
        col3.metric("Placas desconocidas", int((df["resultado"] == "desconocido").sum()))

        st.subheader("Ingresos por día")
        st.bar_chart(df.groupby("fecha").size())

        st.subheader("Placas desconocidas más frecuentes")
        desconocidas = df[df["resultado"] == "desconocido"]["placa_corregida"].value_counts().head(10)
        st.bar_chart(desconocidas)


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------


# Integrantes del proyecto, para el pie de página (requisito de la feria de
# la ciencia: el nombre del proyecto y de las autoras deben verse en la
# plataforma, no solo en el informe escrito).
NOMBRE_PROYECTO = "Sistema ALPR Portería"
INTEGRANTES = [
    "Keisy Ruiz",
    "Mariajosé Urrego",
    "Isabela Hernández",
    "Xiomara Echavarría",
    "Nicole Arteaga",
]


def _pie_de_pagina():
    st.markdown("---")
    st.markdown(
        f"""
        <div style="text-align:center; padding: 0.5rem 0 1.5rem 0; opacity: 0.7; font-size: 0.85rem;">
            <strong>{NOMBRE_PROYECTO}</strong> — Proyecto de Feria de la Ciencia<br>
            Institución Educativa Consejo Municipal La Estrella · Grado Once<br>
            Desarrollado por: {" · ".join(INTEGRANTES)}
        </div>
        """,
        unsafe_allow_html=True,
    )


def main():
    st.set_page_config(page_title="ALPR Portería", page_icon="🚧", layout="wide")
    base_datos.crear_tablas()
    # En un servidor nuevo (por ejemplo, recién publicado en la nube) la base
    # de datos arranca vacía — sin esto, no habría ni un solo apartamento
    # para que un residente se registre. cargar_datos_ejemplo() no hace nada
    # si ya hay datos (ver base_datos.py), así que es seguro llamarla siempre.
    base_datos.cargar_datos_ejemplo()

    if "rol" not in st.session_state:
        st.session_state.rol = None
    if "residente_actual" not in st.session_state:
        st.session_state.residente_actual = None

    if st.session_state.rol is None:
        pantalla_login()
        _pie_de_pagina()
        return

    cerrar_sesion()
    if st.session_state.rol == "Residente":
        st.sidebar.success(f"Sesión: {st.session_state.residente_actual['nombre']}")
    else:
        st.sidebar.success(f"Sesión: {st.session_state.rol}")

    if st.session_state.rol == "Vigilante":
        panel_vigilante()
    elif st.session_state.rol == "Residente":
        panel_propietario()
    elif st.session_state.rol == "Administración":
        panel_administracion()

    _pie_de_pagina()


if __name__ == "__main__":
    main()
