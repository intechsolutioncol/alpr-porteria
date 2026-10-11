# Ética y protección de datos — Sistema ALPR Portería

Sección requerida para el cierre del proyecto (Semana 9). Un sistema de
vigilancia que se hace cargo de sus propias implicaciones es más maduro
ante un jurado que uno que las ignora — este documento es esa parte.

## 1. Qué datos personales maneja el sistema

El sistema, tal como está diseñado, guarda y consulta:

- **Placas vehiculares** — dato personal, porque junto con otra información
  permite identificar a una persona (el propietario del vehículo).
- **Nombres y documentos de identidad** de residentes y visitantes.
- **Número de apartamento y torre** asociado a cada persona.
- **Fotos del vehículo** capturadas en cada intento de ingreso
  (`registros_ingreso.ruta_foto`).
- **Horarios de entrada**: la tabla `registros_ingreso` registra fecha y
  hora exacta de cada lectura, con o sin autorización.

Combinados, estos datos permiten reconstruir **quién entró, cuándo, y a qué
apartamento se dirigía** — un patrón de movimiento, no solo un dato suelto.
Eso es justamente lo que la Ley 1581 de 2012 (Colombia, "Ley de Protección
de Datos Personales") regula.

## 2. Qué exige la Ley 1581 de 2012 y cómo aplica aquí

| Principio de la ley | Qué significa | Cómo aplica al proyecto |
|---|---|---|
| **Finalidad** | Los datos solo se usan para lo que se avisó que se usarían | El sistema debe usarse solo para control de acceso del conjunto, no para otro fin (ej. no vender los datos, no usarlos para perfilar personas) |
| **Consentimiento previo** | La persona debe saber y aceptar que sus datos se recolectan | Residentes y visitantes deberían ser informados de que su placa y foto quedan registradas al ingresar (ej. un aviso en la portería) |
| **Acceso restringido** | Solo personal autorizado ve los datos | Por eso la app separa roles (vigilante/propietario/administración) con contraseña — cada rol ve solo lo que necesita: un propietario no debería poder ver los registros de otro apartamento |
| **Seguridad** | Los datos deben protegerse contra pérdida o acceso indebido | La base de datos es un solo archivo SQLite sin cifrar: **suficiente para una demo de feria, no para producción real** (ver sección 4) |
| **Conservación limitada** | No guardar datos más tiempo del necesario | El proyecto no implementa borrado automático de registros antiguos; sería necesario definirlo antes de un uso real |

## 3. Quién debería tener acceso a qué (según el diseño actual de roles)

- **Vigilante**: ve los registros de ingreso en tiempo real y puede
  autorizar/rechazar. No necesita ver el historial completo de todos los
  apartamentos, aunque en esta versión de demostración sí puede.
- **Residente**: ve solo la información de **su propio** apartamento
  (vehículos, visitantes que autoriza, historial). Desde el 2026-10-10 cada
  residente tiene su propia cuenta (documento + contraseña individual, no
  un rol compartido), y el apartamento se deriva automáticamente de esa
  cuenta — ya no de un selector abierto donde cualquiera podía elegir
  cualquier apartamento.
- **Administración**: es el único rol que debería tener acceso a
  estadísticas agregadas y reportes de todo el conjunto.

## 4. Limitaciones reconocidas de esta implementación

Esta es una demostración escolar, no un producto listo para producción.
Puntos que un despliegue real tendría que resolver:

1. **Contraseñas compartidas en texto plano para Vigilante y Administración**
   (`CONTRASENAS_POR_ROL` en `src/app.py`) — aceptable para demostrar el
   concepto de esos dos roles ante un jurado, inaceptable para proteger
   datos reales. (Las contraseñas de los **residentes** ya NO están en
   este caso: desde el 2026-10-10 se guardan como hash con PBKDF2 y sal
   aleatoria por persona, nunca en texto plano — ver `base_datos.py`.)
2. **Base de datos sin cifrar** — cualquiera con acceso al archivo
   `alpr_porteria.db` puede leer todos los datos.
3. **Sin registro de quién consultó qué** (auditoría) — el sistema no deja
   rastro de qué vigilante o administrador accedió a según qué información.
4. **Fotos guardadas indefinidamente** — no hay una política de cuánto
   tiempo se conservan las capturas de `data/reales/capturas_ingreso/`.
5. **Sin mecanismo de que una persona pida que se borren sus datos**
   (derecho de supresión, también parte de la Ley 1581).

## 5. Por qué el sistema NO abre la talanquera automáticamente

Esta decisión (ver `arduino/talanquera/talanquera.ino` y
`src/talanquera.py`) también es, en el fondo, una decisión ética: el
reconocimiento automático de placas puede equivocarse (falsos positivos y
falsos negativos, medidos en el banco de pruebas de la Semana 8). Dejar que
un sistema con precisión imperfecta controle directamente el acceso físico
a un conjunto residencial sería irresponsable. Por eso la apertura siempre
requiere la confirmación de una persona (modo seguro).

## 6. Para la sustentación

Si el jurado pregunta "¿qué pasaría si esto se usara de verdad?", la
respuesta honesta es: se necesitarían al menos las mejoras de la sección 4,
además de un proceso claro de consentimiento informado a residentes y
visitantes, y una política escrita de cuánto tiempo se conservan los datos
y quién puede acceder a ellos.
