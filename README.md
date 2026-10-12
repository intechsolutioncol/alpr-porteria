# Sistema de Reconocimiento de Placas para Porterías (ALPR)

Proyecto de feria de la ciencia — Institución Educativa Consejo Municipal La Estrella, Grado 11.

Detecta la placa de un vehículo (foto, video o webcam), lee sus caracteres y
consulta una base de datos para decidir si el vehículo es residente,
visitante autorizado o desconocido. El sistema **muestra** la información al
vigilante; no abre la barrera automáticamente.

## Arranque en 2 minutos (el día de la feria)

```bash
# 1. Activar el entorno virtual (siempre, cada vez que se abre una terminal nueva)
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Mac / Linux

# 2. Diagnóstico rápido: confirma que cámara, modelos y base de datos están OK (~10s)
python pruebas/diagnostico.py

# 3. Levantar la aplicación
streamlit run src/app.py
```

Streamlit abre automáticamente una pestaña del navegador (normalmente en
http://localhost:8501). Si no se abre sola, entra a esa dirección a mano.

**Contraseñas de demostración** (ver `src/app.py`, `CONTRASENAS_POR_ROL`):
Vigilante `vigilante123` — Propietario `propietario123` — Administración `admin123`.

## Si algo falla justo antes de presentar

1. Corre `python pruebas/diagnostico.py` — te dice exactamente qué pieza falló.
2. Si la cámara no responde pero hay tiempo, usa la pestaña "Subir foto" o
   "Subir video" del panel del vigilante en vez de "Cámara en vivo".
3. Si nada funciona, usa el respaldo grabado: `python pruebas/demo_grabada.py`
   (ver PARTE F de `GUIA-PROYECTO-ALPR.md` y la Semana 9 para prepararlo con
   anticipación — no la noche anterior).

## Primera vez en un equipo nuevo

```bash
python -m venv .venv
.venv\Scripts\activate                     # Windows
pip install --upgrade pip
pip install -r requirements.txt            # ~2 GB, incluye PyTorch
python verificar_instalacion.py            # confirma que todo se instaló bien
python config.py                           # crea las carpetas de datos/resultados
python src/base_datos.py                   # crea la base de datos con datos de ejemplo
```

La talanquera física (Arduino, objetivo opcional) necesita además
`pip install -r requirements-talanquera.txt`.

## Estructura

Ver [CLAUDE.md](CLAUDE.md) para el contexto completo del proyecto y la
estructura detallada de carpetas.

## Estado del proyecto

Ver la guía de desarrollo (`GUIA-PROYECTO-ALPR.md` en la carpeta superior)
para las nueve fases y sus criterios de verificación.
