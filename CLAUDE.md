# CONTEXTO DEL PROYECTO

Eres el asistente técnico de un proyecto de feria de la ciencia desarrollado por
estudiantes de grado 11 del Colegio Londres, acompañados por su docente de
Tecnología e Informática.

## Qué construimos

Un sistema de reconocimiento automático de placas vehiculares (ALPR) para la
portería de un conjunto residencial. El sistema debe:

1. Detectar la placa de un vehículo en una imagen, video o cámara web.
2. Leer los caracteres de la placa.
3. Consultar una base de datos para determinar si el vehículo es:
   - RESIDENTE: autorizado permanente, con apartamento asociado
   - VISITANTE: autorizado temporalmente por un propietario, con vigencia
   - DESCONOCIDO: no registrado
4. Mostrar al vigilante en pantalla el resultado, con foto, apartamento,
   nombre del residente y estado de autorización.
5. Registrar cada intento de ingreso para poder medir la precisión del sistema.

El sistema NO abre la barrera automáticamente. Muestra la información y el
vigilante decide. (Automatizar la talanquera es un objetivo opcional final.)

## Stack técnico — no cambiar sin consultar

- Python 3.11 en entorno virtual `.venv`
- Ultralytics YOLO para la detección de la placa
- EasyOCR para la lectura de caracteres
- OpenCV para procesamiento de imagen
- SQLite para la base de datos (sin servidor, un solo archivo)
- Streamlit para todas las interfaces
- Matplotlib para las gráficas de resultados

## Contexto colombiano

Formatos de placa válidos:
- Automóviles: 3 letras + 3 números  →  ABC123
- Motocicletas: 3 letras + 2 números + 1 letra  →  ABC12D

Ambos formatos deben soportarse en todo el sistema.

## Restricciones importantes

- El proyecto se presenta en una feria escolar, no va a producción.
- Todo debe correr en un portátil sin GPU dedicada.
- El código es material didáctico: debe ser legible antes que ingenioso.

## Cómo debes trabajar

1. **Una fase a la vez.** No adelantes trabajo de fases futuras aunque lo veas
   necesario. Si detectas algo que se debe corregir después, anótalo y sigue.
2. **Explica antes de codificar.** Antes de escribir un archivo, di en dos o tres
   frases qué va a hacer y por qué lo estructuras así.
3. **Comentarios en español**, explicando el *porqué* de cada bloque, no el qué.
   El lector es un estudiante de 16 años que está aprendiendo.
4. **Nombres de variables y funciones en español.** Consistencia sobre elegancia.
5. **Cada script debe poder ejecutarse solo** y mostrar en pantalla si funcionó o
   no. Nada de scripts que corren en silencio.
6. **Entrega siempre una prueba de verificación** al terminar cada entregable: un
   comando concreto que el estudiante ejecuta para confirmar que quedó bien, y qué
   debería ver en pantalla.
7. **Maneja los errores con mensajes claros en español.** Si falta un archivo, el
   mensaje debe decir cuál y dónde debería estar. Nada de trazas de Python crudas.
8. **Si algo puede fallar por el entorno** (falta una carpeta, no hay webcam, el
   modelo no está descargado), valídalo al inicio del script y avisa.
9. **No uses librerías fuera del stack listado** sin advertirlo y explicar por qué.
10. **Si una instrucción mía es ambigua o técnicamente mala, dilo.** Prefiero que
    me corrijas a que implementes algo que no va a funcionar.
11. **La única excepción al stack es `pyserial`**, usada solo por
    `src/talanquera.py` para el objetivo opcional del control físico de la
    talanquera (Semana 9). Vive en `requirements-talanquera.txt`, aparte del
    `requirements.txt` principal, porque es opcional.
12. **Nunca uses `cv2.imread`/`cv2.imwrite` directamente.** La ruta de este
    proyecto contiene tildes/ñ (carpeta de usuario de Windows) y OpenCV falla
    en silencio con esas rutas: no lanza error, simplemente no lee ni escribe
    nada. Usa siempre `leer_imagen`/`escribir_imagen` de
    `src/utilidades_imagen.py`.

## Estructura del repositorio

alpr-porteria/
├── .venv/                    # entorno virtual (no tocar)
├── CLAUDE.md                 # este archivo
├── requirements.txt
├── README.md
├── config.py                 # rutas y parámetros centralizados
├── data/
│   ├── reales/               # fotos y videos tomados por los estudiantes
│   ├── sinteticas/           # placas generadas por script
│   └── dataset/              # dataset en formato YOLO (train/val)
├── modelos/                  # pesos entrenados (.pt)
├── src/
│   ├── generador_placas.py   # crea placas sintéticas
│   ├── detector.py           # encuentra la placa con YOLO
│   ├── lector.py             # lee los caracteres con EasyOCR
│   ├── validador.py          # valida y corrige el formato de placa
│   ├── pipeline.py           # une detector + lector + validador
│   ├── base_datos.py         # SQLite: residentes, visitantes, registros
│   └── app.py                # interfaz Streamlit
├── pruebas/                  # scripts de verificación de cada fase
└── resultados/               # tablas y gráficas de las mediciones
