# Guía de uso — Sistema ALPR Portería

Manual paso a paso de la aplicación (`src/app.py`), para quien la va a usar
en la demostración o en la sustentación. No requiere saber programar.

---

## 1. Cómo arrancar la aplicación

1. Abre una terminal en la carpeta del proyecto.
2. Activa el entorno virtual:
   ```
   .venv\Scripts\activate
   ```
3. Corre:
   ```
   streamlit run src/app.py
   ```
4. Se abre sola una pestaña del navegador (normalmente en
   `http://localhost:8501`). Si no se abre sola, entra a esa dirección a mano.

Ver `README.md` para el diagnóstico rápido antes de arrancar y qué hacer si
algo falla.

---

## 2. Pantalla de ingreso

La pantalla de **Ingreso** tiene dos pestañas principales: **🏠 Residentes**
y **🪪 Vigilante / Administración**.

### 2.1 Vigilante / Administración

Funciona como antes: un menú desplegable con el rol (`Vigilante` o
`Administración`) y una contraseña compartida.

| Rol | Contraseña |
|---|---|
| Vigilante | `vigilante123` |
| Administración | `admin123` |

**Nota importante:** estas dos contraseñas están escritas directamente en
el código (`src/app.py`, variable `CONTRASENAS_POR_ROL`) — sirven para
demostrar el concepto ante el jurado, no son seguridad real. Ver
`ETICA_Y_PROTECCION_DE_DATOS.md` para la explicación completa de esta
limitación (que sí sigue aplicando a estos dos roles).

### 2.2 Residentes — login individual

Este es el cambio más importante de la última actualización: **ya no se
elige el apartamento de una lista abierta**. Cada residente tiene su
propia cuenta (documento + contraseña propia), con tres sub-pestañas:

- **Iniciar sesión**: documento y contraseña, para quien ya tiene cuenta activa.
- **Activar mi acceso**: para un residente que administración YA registró
  en el sistema (por ejemplo, al dar de alta el apartamento) pero que
  todavía no ha creado su propia contraseña. Solo pide el documento; si lo
  encuentra sin contraseña, deja crear una ahí mismo.
- **Soy nuevo/a**: para registrarse desde cero — elige el apartamento,
  escribe nombre, documento y una contraseña (mínimo 4 caracteres), y la
  cuenta queda lista para usar de inmediato.

Las contraseñas de los residentes **nunca se guardan en texto plano**: se
guardan como un *hash* (una huella digital de la contraseña, calculada con
una técnica estándar llamada PBKDF2) en la base de datos — ni siquiera
alguien con el archivo de la base de datos en la mano puede leer la
contraseña real.

---

## 3. Panel del vigilante

Es la pantalla principal del proyecto — la que se usa durante la
demostración en vivo.

### Barra lateral izquierda

- **Botón "Cerrar sesión"** arriba del todo
- **🔧 Modo maqueta (Semana 7)**: un desplegable con una casilla
  "Activar modo maqueta". Al activarla aparecen controles de:
  - **ROI** (región de interés): 4 controles deslizantes que definen qué
    parte del encuadre se procesa (útil para ignorar todo lo que no sea la
    franja de calle de la maqueta)
  - **Calibración de distancia**: dos campos numéricos de referencia
    (mínima/máxima en cm)
- **Buscador manual**: un campo de texto para escribir una placa completa o
  parcial y ver coincidencias registradas en el sistema (útil cuando el
  reconocimiento automático falla)
- **Últimos 10 ingresos**: lista con un ícono de color por cada registro
  (🟢 residente, 🟡 visitante, 🔴 desconocido)

### Panel central: tres pestañas

1. **📷 Subir foto** — sube una imagen (jpg/png) de un vehículo. El sistema
   la procesa y muestra el resultado abajo.
2. **🎞️ Subir video** — sube un video (mp4/avi/mov). Se reproduce
   fotograma a fotograma en pantalla mostrando la lectura actual y, cuando
   hay suficiente consenso entre fotogramas, la "lectura consolidada"
   (votación temporal, Semana 4). Al terminar el video muestra el resultado
   de autorización de la última placa consolidada.
3. **🎥 Cámara en vivo** — toma una sola foto con la webcam (no es video
   continuo: ver la nota técnica en el código sobre por qué).

### Qué aparece después de procesar una imagen

Un recuadro grande de color:
- 🟢 **Verde**: autorizado (residente o visitante con vigencia activa)
- 🟡 **Amarillo**: hay que revisar (lectura de baja confianza, muestra
  sugerencias de placas parecidas)
- 🔴 **Rojo**: no autorizado (placa desconocida o visitante vencido)

Debajo: la foto capturada, el apartamento/torre (destacado), el nombre del
residente o visitante, y quién autorizó (si es visitante).

Al final, dos o tres botones:
- **✅ Autorizar** / **❌ Rechazar** — registran la decisión del vigilante
  en la base de datos (tabla `registros_ingreso`), junto con la foto.
- **🚧 Abrir talanquera** — SOLO aparece si hay un Arduino conectado
  (`src/talanquera.py`) y la placa está autorizada. Nunca se abre sola: es
  siempre el vigilante quien presiona el botón (ver "modo seguro" en
  `ETICA_Y_PROTECCION_DE_DATOS.md`).

---

## 4. Panel del propietario

Pensado para que cada apartamento gestione sus propios datos sin depender
de administración. El apartamento ya **no se elige de una lista**: se
deriva automáticamente de qué residente inició sesión (ver sección 2.2).
Arriba de todo se muestra "Conectado como [nombre] — apto. [número],
Torre [letra]".

### Pestaña "Mis datos y vehículos"

- **Residentes de este apartamento**: lista de personas ya registradas, con
  botón "Eliminar" en cada una (no deja eliminar si el residente todavía
  tiene vehículos a su nombre, para no dejar datos huérfanos)
- **➕ Registrarme / registrar otro residente**: formulario con nombre,
  documento y casilla "Es propietario"
- **Vehículos registrados**: lista de vehículos del apartamento, con botón
  "Eliminar" en cada uno
- **➕ Registrar un vehículo autorizado permanente**: formulario para
  agregar un vehículo propio — elige a nombre de qué residente queda,
  la placa (se valida el formato colombiano), tipo, marca y color

### Pestaña "Registrar visitante"

Formulario: placa, nombre del visitante, motivo, y tipo de vigencia
("Solo hoy", "Rango de fechas" o "Recurrente" con fecha de fin).

### Pestaña "Visitantes activos"

Lista de visitantes con autorización vigente en este momento, con botón
"Cancelar" en cada uno (adelanta la fecha de fin a ayer, así deja de estar
vigente).

### Pestaña "Historial"

Todos los visitantes que ha tenido el apartamento alguna vez, vigentes o no.

---

## 5. Panel de administración

Vista de todo el conjunto residencial.

### Pestaña "Apartamentos"

Crear apartamentos (número, torre, propietario, teléfono) y eliminarlos
(no deja eliminar uno que todavía tenga residentes).

### Pestaña "Residentes"

Ver TODOS los residentes de TODOS los apartamentos, registrar uno nuevo
eligiendo a qué apartamento pertenece, y eliminarlos (no deja eliminar uno
que todavía tenga vehículos).

### Pestaña "Vehículos"

Ver todos los vehículos del conjunto, registrar uno nuevo eligiendo a qué
residente pertenece, y eliminarlos.

### Pestaña "Reportes"

Selector de rango de fechas + botón "Generar reporte": muestra una tabla
con todos los registros de ingreso en ese rango, y un botón para
descargarla como CSV.

### Pestaña "Estadísticas"

Tres números grandes (ingresos totales, tasa de reconocimiento, placas
desconocidas), más dos gráficas de barras: ingresos por día, y las placas
desconocidas más frecuentes.

---

## 6. Mapa rápido de quién puede hacer qué

| Acción | Vigilante | Propietario | Administración |
|---|---|---|---|
| Leer una placa y ver si está autorizada | ✅ | ❌ | ❌ |
| Autorizar/rechazar un ingreso | ✅ | ❌ | ❌ |
| Abrir la talanquera | ✅ | ❌ | ❌ |
| Registrarse a sí mismo como residente | ❌ | ✅ (de su apartamento) | ✅ (de cualquiera) |
| Registrar su propio vehículo | ❌ | ✅ | ✅ |
| Registrar un visitante | ❌ | ✅ (de su apartamento) | — |
| Crear/eliminar apartamentos | ❌ | ❌ | ✅ |
| Ver reportes y estadísticas de todo el conjunto | ❌ | ❌ | ✅ |

---

## 7. Sobre la idea de una "app web para residentes" independiente

Al inicio del proyecto se había pensado en una app web aparte donde los
residentes diligenciaran sus datos y los de sus vehículos autorizados. Esa
funcionalidad **ya existe dentro de la app actual** (sección 4 de esta
guía, pestaña "Mis datos y vehículos") — no hace falta construir una
aplicación separada, porque Streamlit ya sirve la interfaz completa como
una página web.

**Estado actual (actualizado 2026-10-10):**

1. **Acceso por red local:** ✅ funcionando. Mientras `streamlit run src/app.py`
   esté corriendo en un computador, cualquier celular conectado a la misma
   red (mismo Wi-Fi/router) puede entrar desde su navegador a
   `http://<IP del computador>:8501` sin instalar nada.
2. **Login individual por residente:** ✅ implementado (ver sección 2.2).
   Cada residente tiene su propio documento y contraseña, ya no se elige
   el apartamento de una lista abierta.
3. **Acceso público desde cualquier lugar (no solo la red local):**
   pendiente de decidir dónde alojarla de forma permanente — ver
   `PENDIENTES.md`. Para la feria, se puede publicar temporalmente con un
   servicio de hospedaje gratuito (Streamlit Community Cloud) para tener
   un enlace que cualquiera pueda abrir desde su propio celular, sin estar
   en la red del conjunto.
