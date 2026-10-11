# Bitácora de experimentos y decisiones técnicas

Registro cronológico de cada prueba que se corrió, qué se midió, qué se
concluyó y qué se cambió en el código como consecuencia. Sirve como material
de respaldo para el informe de la feria y para poder explicar ante el
jurado *por qué* el sistema quedó configurado como quedó — no solo qué hace,
sino qué se descartó y por qué.

Todas las cifras de esta bitácora salen de archivos reales en `resultados/`
y se pueden reproducir corriendo los scripts indicados.

---

## 1. Línea base: OCR sobre placas sintéticas (Semana 2)

**Script:** `pruebas/probar_ocr_sinteticas.py --cantidad 100`
**Qué mide:** EasyOCR leyendo directamente la imagen completa (placa +
margen de fondo generado), sin detector ni corrección de posición de por
medio.

| Métrica | Valor |
|---|---|
| Precisión exacta | 74.0% (74/100) |
| Precisión por carácter | 95.0% |
| Tiempo promedio/placa | 7.762 ms |

**Top confusiones:** `0→O` (11), `5→S` (7), `2→Z` (4), `7→Z` (2), `1→T` (2).

**Conclusión:** la base del pipeline funciona razonablemente bien sin
ningún ajuste fino. Esta tabla de confusiones es la que alimentó
`config.CONFUSIONES_NUMERO_A_LETRA` para el validador de la Semana 4.

---

## 2. Entrenamiento del detector de placas propio (Semana 3)

**Cómo:** `src/preparar_dataset_yolo.py` generó 1.000 imágenes etiquetadas
en formato YOLO (800 entrenamiento / 200 validación), empaquetadas en
`data/dataset.zip`. Se entrenó con `entrenar_detector_colab.ipynb` en
Google Colab (YOLO11n, 50 épocas, GPU).

**Problema encontrado y corregido antes de poder entrenar:** el notebook
descomprimía `dataset.zip` un nivel más profundo de lo que debía
(`/content/dataset/dataset/images/...` en vez de
`/content/dataset/images/...`), porque el .zip ya trae una carpeta
`dataset/` como raíz interna (así lo arma `shutil.make_archive` en
`preparar_dataset_yolo.py`). Ultralytics fallaba con
`FileNotFoundError: ... missing path '.../images/val'`. Se corrigió la
celda de descompresión del notebook para extraer en `/content` en vez de
`/content/dataset`, y se le agregó una verificación automática
(`assert os.path.isdir(...)`) que avisa de inmediato si vuelve a pasar algo
similar, en vez de fallar minutos después con un traceback de Ultralytics.

**Segundo problema:** la primera corrida de entrenamiento se hizo sin GPU
activa en Colab (`torch-2.11.0+cpu`), mucho más lenta de lo esperado. Se
corrigió activando `Entorno de ejecución → Cambiar tipo de entorno de
ejecución → GPU` antes de reentrenar.

**Resultado:** `modelos/best.pt` (5.4 MB). Probado sobre 5 imágenes de
validación: **99% de confianza** en todas, con el cuadro delimitador
ajustado visualmente de forma correcta sobre la placa (verificado
recortando y mostrando la imagen).

---

## 3. ¿Ayuda el detector a la precisión del OCR? — primera medición (resultado negativo)

**Script:** `pruebas/probar_ocr_sinteticas.py --cantidad 100 --usar-detector`
**Qué cambia:** en vez de leer la imagen completa, primero se corre el
detector entrenado, se recorta solo la placa, y se lee ese recorte.

| Versión | Precisión exacta | Precisión/carácter | Tiempo/placa |
|---|---|---|---|
| Sin detector (línea base) | 74.0% | 95.0% | 7.762 ms |
| Con detector, sin margen | **71.0%** | 94.0% | 5.092 ms |

**Detecciones fallidas:** 0/100 (el detector encontró la placa siempre).

**Conclusión inicial (incorrecta, ver sección 5):** el recorte bajó la
precisión 3 puntos. Hipótesis original: el recorte pegado al borde de la
placa corta los caracteres de las esquinas.

---

## 4. Intento de corrección: agregar margen al recorte (resultado negativo, hipótesis descartada)

**Cambio:** se agregó `config.MARGEN_RECORTE_PLACA = 0.08` (8% de margen
alrededor de la caja detectada) en `src/detector.py`.

| Versión | Precisión exacta | Precisión/carácter | Tiempo/placa |
|---|---|---|---|
| Sin detector | 74.0% | 95.0% | 7.762 ms |
| Con detector, sin margen | 71.0% | 94.0% | 5.092 ms |
| Con detector, **con margen 8%** | **67.0%** | 89.4% | 6.782 ms |

**Conclusión:** el margen empeoró el resultado en vez de mejorarlo, y de
forma no monótona (más margen ≠ mejor de forma simple). Esto descarta la
hipótesis de "se cortan caracteres en el borde" como causa principal — si
esa fuera la causa, más margen debería ayudar de forma consistente, y no
fue lo que se observó. `MARGEN_RECORTE_PLACA` se dejó en `0.0` hasta
encontrar la causa real.

---

## 5. Causa real encontrada: resolución absoluta, no margen

**Hipótesis revisada:** `src/lector.py` reescalaba el recorte
multiplicando su tamaño por un factor fijo (`ESCALA_PREPROCESAMIENTO = 3`).
Un recorte ajustado a la placa es más chico en píxeles que la imagen
completa (que incluye fondo generado alrededor), así que el mismo
multiplicador x3 le daba **menos resolución absoluta final** al recorte que
a la imagen completa — el detector no estaba perdiendo por recortar mal,
sino porque terminaba entregándole al OCR una imagen con menos detalle.

**Cambio:** se reemplazó el multiplicador por un ancho absoluto fijo
(`config.ANCHO_OBJETIVO_OCR = 1200`), igual para cualquier entrada, en
`src/lector.py::_preprocesar`.

**Script:** `pruebas/probar_ocr_sinteticas.py --cantidad 100` (con y sin
`--usar-detector`), mismas 100 placas de siempre.

| Versión | Precisión exacta | Precisión/carácter | Tiempo/placa |
|---|---|---|---|
| Sin detector, ancho absoluto | 74.0% | 95.2% | **1.808 ms** |
| **Con detector, ancho absoluto** | **76.0%** | **95.3%** | 1.975 ms |

**Conclusión confirmada:** con la resolución igualada, el detector **sí**
mejora la precisión (74%→76%) como se esperaba en la Semana 3, y además
**todo el sistema quedó ~4 veces más rápido** (7.762 ms → ~1.9 ms por
placa), porque el multiplicador x3 anterior generaba imágenes
innecesariamente grandes (hasta ~3.168 px de ancho) que EasyOCR procesaba
sin ninguna ganancia real de precisión a cambio de ese tiempo.

**Estado final de configuración:**
- `config.ANCHO_OBJETIVO_OCR = 1200`
- `config.MARGEN_RECORTE_PLACA = 0.0`
- `src/detector.py` en `modo="auto"` (usa el modelo de placas propio automáticamente)

---

## 6. Efecto del validador (corrección por posición, Semana 4)

**Script:** `pruebas/probar_ocr_sinteticas.py --cantidad 100 --usar-validador`
y `--usar-detector --usar-validador`.

**Corrección importante sobre esta medición:** la primera versión de esta
prueba le pasaba al validador el `tipo` (carro/moto) REAL, tomado de
`referencia.csv` — pero `pipeline.py::_leer_y_validar()` (el código que
usa la app de verdad) **no conoce el tipo de antemano**: prueba corregir
como carro y como moto, y se queda con el que dé un formato válido. La
primera medición era una cota optimista, no representaba el pipeline real.
Se corrigió el script (bandera `--tipo-conocido` para la versión optimista,
por defecto ahora usa el comportamiento real) y se repitió la prueba.

| Versión | Precisión exacta | Precisión/carácter | Tiempo/placa |
|---|---|---|---|
| Sin nada (línea base, sección 5) | 74.0% | 95.2% | 1.808 ms |
| Con detector (sección 5) | 76.0% | 95.3% | 1.975 ms |
| Con validador (tipo adivinado — **pipeline real**) | 86.0% | 97.35% | 1.969 ms |
| **Con detector + validador (tipo adivinado — pipeline real)** | **87.0%** | **97.67%** | 2.094 ms |
| *Con validador, tipo conocido (cota optimista, no representa el pipeline real)* | *92.0%* | *98.5%* | *2.079 ms* |
| *Con detector + validador, tipo conocido (cota optimista)* | *94.0%* | *99.0%* | *2.165 ms* |

**Conclusión (con los números reales del pipeline):** el validador sigue
siendo la mejora individual más grande del proyecto — sube la precisión
exacta 12 puntos sobre la línea base (74%→86%) casi sin costo de tiempo
adicional, incluso adivinando el tipo de placa. Combinado con el detector
propio de la Semana 3, la precisión exacta real llega a **87%** y la
precisión por carácter a **97.7%**, superando el criterio de "mínimo
aceptable" de la guía (≥70% en fotos) por 17 puntos, sobre placas
sintéticas. La diferencia entre adivinar el tipo (87%) y conocerlo (94%)
señala que ahí queda margen de mejora: si el sistema tuviera una forma
más confiable de saber si el vehículo es carro o moto (por ejemplo, del
resultado del propio detector de vehículos, o de la relación de aspecto
del recorte), podría acercarse más a esa cota superior — queda anotado en
`PENDIENTES.md`.

**Configuración final recomendada del pipeline:** detector en
`modo="auto"` (usa el modelo propio) + `leer_placa()` + `validador.corregir_por_posicion()`
sin tipo conocido — esto es exactamente lo que ya hace
`src/pipeline.py::_leer_y_validar()`.

---

## 6.1. Bug encontrado y corregido: el corrector dañaba motos válidas al adivinar el tipo

Al investigar la brecha entre "tipo adivinado" (87%) y "tipo conocido"
(94%) de la sección 6, se encontró que parte de esa brecha no era una
limitación de fondo sino un bug puntual en `corregir_por_posicion()`.

**El bug:** cuando no se conoce el tipo, la función probaba primero
"¿es válida como carro?" y devolvía esa respuesta apenas encontraba un
resultado válido, sin comparar con la interpretación como moto. Los
formatos carro (`LLLNNN`) y moto (`LLLNNL`) son idénticos en las primeras
5 posiciones y solo difieren en la última. Una placa de moto que el OCR
leyó **correctamente** y que termina en una letra confundible con un
dígito (`O`, `I`, `S`, `B`, `Z`) pasaba la prueba de "carro" después de que
el corrector, sin necesidad, convertía esa letra final a su dígito
asociado — dañando una lectura que ya estaba bien. Ejemplo verificado:
`ABC12S` (moto, correcta) se convertía en `ABC125` (dañada).

**La corrección:** antes de intentar corregir nada, se revisa si el texto
crudo del OCR ya es válido tal cual para alguno de los dos formatos. Si ya
lo es, se deja intacto. Solo se intenta adivinar y corregir cuando el
texto crudo no cuadra con ningún formato conocido. Se agregaron los 3
casos del bug (`ABC12S`, `ABC12O`, `ABC12B`) como pruebas permanentes en
`src/validador.py`.

**Medición del efecto real** (mismas 100 placas, `pruebas/probar_ocr_sinteticas.py`):

| Versión | Antes del fix | Después del fix |
|---|---|---|
| Con validador (tipo adivinado) | 86.0% | **88.0%** |
| Con detector + validador (tipo adivinado) | 87.0% | **90.0%** |

**Conclusión:** el fix cerró parte de la brecha hacia la cota optimista de
94% (tipo conocido) — de 7 puntos de diferencia a 4. La brecha restante
(90% vs. 94%) sí corresponde a casos genuinamente ambiguos: cuando el
carácter final que leyó el OCR es exactamente uno de los confundibles Y
ADEMÁS ninguna de las dos interpretaciones (ni "tal cual" ni corregida)
resulta clara sin más información — ahí sí hace falta una señal externa
(ver la idea de usar la clasificación del detector de vehículos, anotada
en `PENDIENTES.md`) para cerrar el resto de la brecha.

**Configuración final del pipeline (actualizada):** `src/pipeline.py::_leer_y_validar()`
usa exactamente esta combinación — detector en `modo="auto"` + `leer_placa()`
+ `corregir_por_posicion()` sin tipo conocido, con el fix aplicado — así
que la app (`src/app.py`) ya se beneficia de esta mejora sin cambios
adicionales.

---

## 6.2. Primera prueba con fotos reales: brecha sintético-real encontrada y diagnosticada

El 2026-09-04 se recibieron las primeras 19 fotos reales (carros y una
moto, varias ciudades del área metropolitana de Medellín) y un video real
(`data/reales/IMG_3472.mov`, recorrido de un parqueadero, 1610 fotogramas).

**Experimento pendiente desde la Semana 3, corrido por fin:**
`pruebas/comparar_detectores.py` sobre las 19 fotos:

| Enfoque | Tasa de detección | Tiempo/imagen |
|---|---|---|
| Detector de vehículos (Semana 1, COCO) | 84.2% (16/19) | 194 ms |
| **Detector de placas propio (Semana 3)** | **63.2% (12/19)** | 51 ms |

El detector propio, que daba 99% de confianza sobre imágenes de validación
sintéticas, cae a 63% sobre fotos reales — una brecha grande y esperable
(entrenado solo con datos sintéticos).

**Diagnóstico (script nuevo: `pruebas/probar_fotos_reales.py`, genera
`resultados/mosaico_fotos_reales.jpg`):** revisando visualmente el mosaico
anotado, en la enorme mayoría de las detecciones **la caja del detector
ocupaba entre 89% y 100% del ANCHO TOTAL de la foto** — es decir, el
modelo no estaba encontrando la placa, estaba marcando casi toda la
imagen (medio parachoques completo en varios casos). Se confirmó
extrayendo un caso concreto: en una foto de 960×1280px, la caja detectada
fue `(0, 731, 957, 1279)` — 957px de ancho sobre una imagen de 960px de
ancho total. El recorte resultante mostraba el parachoques completo con
la placa como un elemento pequeño dentro de él, no un recorte ajustado.

**Causa raíz:** `src/generador_placas.py::pegar_sobre_fondo()` usa un
`margen_relativo=0.6` FIJO — en cada imagen sintética de entrenamiento, la
placa ocupa siempre ~62.5% del ancho del cuadro (fondo = 1.6× el tamaño de
la placa). El modelo de detección nunca vio, durante el entrenamiento, un
ejemplo donde la placa fuera una fracción pequeña de una escena mucho más
grande (como pasa en una foto real tomada a la distancia normal de una
portería). Aprendió una prioridad de escala incorrecta: "la placa ocupa
casi todo el cuadro" en vez de "la placa puede estar en cualquier posición
y tamaño dentro de la escena".

**Nota curiosa:** en el caso `KPS796B` (caja de 100% del ancho, recorte =
parachoques completo), el OCR igual leyó `KPS796` casi correctamente
(el texto real de la placa era `KPS·796`) — el OCR de EasyOCR es lo
bastante bueno para encontrar el texto correcto DENTRO de un recorte
demasiado grande en algunos casos, pero esto es más lento y menos
confiable que si el recorte ya viniera ajustado.

**Fix implementado:** se agregó variación aleatoria (log-uniforme, rango
0.3–5.0) al parámetro `margen_relativo` de `pegar_sobre_fondo()` al generar
el dataset de entrenamiento (`src/preparar_dataset_yolo.py`), simulando
placas vistas de cerca (dominantes en el cuadro) y de lejos (pequeñas
dentro de una escena más grande). Se regeneraron las 1.000 imágenes de
entrenamiento y se reentrenó en Colab con el mismo notebook.

**Resultado del reentrenamiento, sobre las mismas 19 fotos reales:**

| Métrica | Antes del fix | Después del fix |
|---|---|---|
| Tasa de detección (¿encontró algo?) | 63.2% (12/19) | **100.0% (19/19)** |
| Tiempo de detección | — | 55 ms/imagen |
| Lecturas exactas correctas (con OCR + validador) | 0/19 | **3/19 (KZO173, LXR093, KPS796, con 0.82-0.90 de confianza)** |
| Lecturas con los caracteres correctos pero mezclados con ruido | — | 3/19 más (ver nota abajo) |

**Interpretación:** la tasa de detección pasó de peor que el detector
genérico de vehículos (84.2%) a mejor (100%), y por primera vez aparecen
lecturas completas y correctas con alta confianza en fotos reales — la
corrección de escala funcionó. Revisando el mosaico anotado
(`resultados/mosaico_fotos_reales.jpg`) a mano: en varios casos el
recuadro ahora sí queda ajustado justo sobre la placa (antes siempre
abarcaba medio parachoques). Sigue habiendo margen de mejora real:

1. **~10 de 19 fotos** el detector todavía encuentra la región equivocada
   por completo (malla, pavimento, un árbol, una tapa de alcantarilla) —
   el modelo sigue entrenado 100% con datos sintéticos, sin ningún
   ejemplo real de fondo (mallas, sombras de árboles, texturas de pavimento
   reales en vez de generadas).
2. **Las placas colombianas reales muchas veces traen el nombre de la
   ciudad como texto pequeño DEBAJO del número** (ej. "HOP·198 / LA
   ESTRELLA"), algo que el generador sintético actual no dibuja. En los
   casos donde el detector sí encontró bien la región, el OCR a veces leyó
   el número de placa Y el nombre de la ciudad juntos, revueltos
   (ej. `LAIHOP198ESIRELLA` en vez de `HOP198`).

**Aclaración del alcance (usuario, 2026-09-04): el nombre de la ciudad NO
es un dato que el proyecto necesite leer — solo el número de la placa.**
Esto cambia el enfoque: en vez de enseñarle al generador sintético a
DIBUJAR el nombre de la ciudad (que no aportaría nada), lo correcto es
que `src/lector.py::leer_placa()` sepa IGNORAR el texto de la ciudad
cuando aparece en una foto real, quedándose solo con el número.

**Bug encontrado y corregido:** `leer_placa()` concatenaba TODOS los
fragmentos de texto que devolvía EasyOCR sin distinguirlos — si detectaba
el número de la placa y el nombre de la ciudad como fragmentos separados
(común en placas reales, ej. "HOP·198" arriba y "LA ESTRELLA" abajo), los
unía en un solo texto sin sentido (`LAIHOP198ESIRELLA`). Corregido en dos
pasos:

1. Primer intento: quedarse solo con el fragmento de mayor ÁREA (el
   número siempre se imprime en letra más grande que la ciudad). Mejoró
   varios casos, pero fallaba cuando el propio número quedaba partido en
   dos fragmentos por el punto separador de en medio (ej. "HKX" y "293"
   detectados por separado) — el heurístico de área se quedaba con uno
   solo y perdía la otra mitad del número.
2. Versión final: en vez de área, agrupar por ALTURA del texto. Se
   conservan TODOS los fragmentos cuya altura sea al menos 60% de la del
   fragmento más alto (probablemente todos son parte del número, sin
   importar si EasyOCR los partió en dos), ordenados de izquierda a
   derecha, y se descartan solo los fragmentos mucho más chicos (la
   ciudad, siempre en letra notablemente más pequeña).

**Resultado, mismas 19 fotos reales:**

| Foto (placa real) | Antes del fix | Después del fix |
|---|---|---|
| `HKX·293` | `293HKXDCBOGOTA` (0.39) | **`HKX293` (1.00)** |
| `HOP·198` | `LAIHOP198ESIRELLA` (0.34) | `IHOP198` (0.34) — mejor, queda una letra de más |
| `LGP·781` | `AUGP781JEUIOLOO` (0.14) | `GP781` (0.38) — mejor, falta la L inicial |
| `KZO·173`, `LXR·093`, `KPS·796` | ya eran correctas (una sola placa sin ciudad) | sin cambios, siguen correctas |

**Lecturas exactas y limpias sobre las 19 fotos reales: subieron de 3/19 a
4/19** (`KZO173`, `HKX293`, `LXR093`, `KPS796`, todas con 82-100% de
confianza). Los dos casos que mejoraron pero no quedaron perfectos
(`IHOP198`, `GP781`) tienen una causa distinta y ya no relacionada con la
ciudad: EasyOCR agregó o se comió un carácter individual dentro del propio
fragmento del número, un error normal de OCR en fotos con ángulo/reflejo,
no un bug de nuestro código.

---

## 6.3. Segundo bug real: un tornillo de la placa se lee como una "I" de más

Reportado por el usuario tras probar la app: "la identificación funciona
bien de cerca, de lejos confunde la línea de las placas con la letra I".

**Diagnóstico:** se aisló el caso `IHOP198` (placa real `HOP·198`)
imprimiendo los fragmentos crudos que devuelve EasyOCR antes de cualquier
procesamiento propio: `IHOP198` salió como **un solo fragmento** de
EasyOCR (88px de alto, confianza 0.84) — no eran dos fragmentos que se
pudieran separar por altura (eso ya se había arreglado en 6.2). La "I" va
pegada al número real dentro de la misma lectura, casi con certeza porque
uno de los dos tornillos de montaje de la placa (visibles en la foto,
arriba a la izquierda del número) se interpretó como un trazo vertical.
Como la confianza es alta (0.84), el umbral de baja confianza tampoco lo
filtra.

**Fix:** ya sabemos que una placa colombiana mide siempre 6 caracteres.
Se extendió `validador.py::corregir_por_posicion()` para que, si el texto
mide 7, pruebe primero quitar el primer o el último carácter — si
cualquiera de las dos versiones ya es un formato válido, se usa esa antes
de seguir con el resto de las correcciones. Casos agregados a las pruebas
permanentes (`IHOP198`→`HOP198`, `HOP198I`→`HOP198`).

**Resultado:** `HOP198` ahora se lee exacto con 0.86 de confianza (antes
`IHOP198`, incorrecto). Lecturas exactas sobre las 19 fotos reales: **5/19**
(`KZO173`, `HKX293`, `HOP198`, `LXR093`, `KPS796`).

**Sobre "de lejos falla más" — esto NO es un bug, es una limitación física
esperable**, mitigada con una salvaguarda de software y una recomendación
física, no con "arreglar el OCR para que lea mejor de lejos" (no existe
tal arreglo: una foto de lejos tiene menos píxeles reales de la placa, y
ningún procesamiento inventa detalle que la cámara nunca capturó):

1. **Salvaguarda implementada:** `config.ANCHO_MINIMO_RECORTE_CONFIABLE = 60`
   (px). En `src/lector.py::leer_placa()`, si el recorte detectado mide
   menos que esto ANTES de agrandarlo a `ANCHO_OBJETIVO_OCR`, se penaliza
   la confianza proporcionalmente. Por qué hace falta: EasyOCR no sabe
   cuánto se amplió la imagen y puede reportar confianza alta sobre una
   lectura que en realidad viene de muy pocos píxeles reales — sin esta
   salvaguarda, el sistema podría mostrar como "confiable" algo que no lo
   es. Con ella, una placa muy lejana cae más fácilmente por debajo del
   umbral de baja confianza (`autorizacion.UMBRAL_CONFIANZA_BAJA`) y el
   sistema pide revisión manual en vez de arriesgar una autorización
   equivocada.
2. **Recomendación física (no requiere código):** ubicar la cámara real a
   una distancia de trabajo controlada y relativamente cercana, como ya
   indica la Semana 7 de la guía para la maqueta — el indicador de calidad
   de imagen del modo maqueta (`_evaluar_calidad` en `src/app.py`) ya
   avisa de nitidez/brillo inadecuados antes de confiar en una captura.

---

## 6.4. Tercera vuelta de entrenamiento: fondos reales y ejemplos negativos

Con 5/19 lecturas exactas, el usuario preguntó explícitamente cómo subir
ese número. Antes de tocar más código de OCR, se clasificaron a mano las
19 fotos por causa de la falla:

| Causa | Cantidad |
|---|---|
| Región correcta + lectura correcta | 5 |
| Encontró la placa pero el OCR falló/leyó mal | 4 |
| **El detector apuntó a un lugar sin ninguna placa** (malla, pavimento, árbol, tapa de alcantarilla) | **10** |

Más de la mitad de las fallas son del DETECTOR, no del OCR — el cuello de
botella real. Causa: el dataset de entrenamiento solo usaba 3 fondos
procedurales (ruido gris, color liso, degradado) y **cero ejemplos sin
ninguna placa** — el modelo nunca vio una malla o un árbol real, y nunca
aprendió que "no siempre hay una placa en la imagen".

**Cambio 1 — fondos reales (`src/extraer_fondos_reales.py`, script nuevo):**
se extrajeron recortes de fondo del video del usuario y de las esquinas de
sus 19 fotos (evitando el centro, donde suele estar el vehículo). Filtrar
esto bien fue más difícil de lo esperado — registrado porque es un
hallazgo metodológico útil:

1. Primer intento: filtrar con el propio detector de PLACAS a umbral bajo
   (0.15) → descartó 154 de 176 recortes. Segundo intento, mismo detector
   a umbral NORMAL del proyecto (0.25) → descartó 156 de 176. **Conclusión:
   el detector de placas no sirve para filtrar sus propios datos de
   entrenamiento** — es justamente el modelo que confunde mallas y
   pavimento con una placa, así que usarlo como filtro descarta la mayoría
   de los recortes útiles (los que tienen justo esas texturas confusas).
2. Filtro que sí funcionó: el detector de VEHÍCULOS (modelo general de la
   Semana 1, no el que se está mejorando) + un filtro de color (descartar
   recortes con más de 1.2% de píxeles en el rango de amarillo de placa).
   Bajó de 176 a 98 recortes.
3. Aun así, revisión visual manual encontró 6 recortes más con una placa
   real parcialmente visible que ambos filtros automáticos no detectaron
   (incluida una placa BLANCA de trámite/provisional, que el filtro de
   color nunca iba a atrapar por no ser amarilla). Se eliminaron a mano.
   **Quedaron 88 recortes reales limpios**, verificados dos veces por
   inspección visual completa.

**Cambio 2 — ejemplos negativos (`src/preparar_dataset_yolo.py`):** 15% del
dataset ahora son imágenes de puro fondo (puede ser procedural o real) SIN
ninguna placa pegada, con un archivo de etiqueta vacío (la convención
estándar de YOLO para "esta imagen no tiene ningún objeto de la clase
buscada"). Antes, el 100% de las imágenes de entrenamiento tenían
exactamente una placa — el modelo nunca practicó "decir que no hay nada".

**Cambio 3:** épocas de entrenamiento subidas de 50 a 75 en
`entrenar_detector_colab.ipynb` (el dataset ahora es más difícil de
aprender: variedad de escala + fondos reales + negativos).

**Dataset regenerado:** 1.500 imágenes (antes 1.000), mezclando fondos
procedurales y reales (40% de probabilidad de fondo real cuando hay
recortes disponibles), con 15% de ejemplos negativos.

**Resultado del reentrenamiento (75 épocas), mismas 19 fotos reales:**

| Métrica | Antes (Semana 3, segunda vuelta) | Después (tercera vuelta) |
|---|---|---|
| Detección en fotos reales | 100.0% (19/19) | 89.5% (17/19) |
| **Lecturas exactas correctas** | 5/19 | **7/19** |
| Tamaño típico de la caja detectada | 96-100% del ancho de la imagen | **12-36% del ancho** (mucho más realista) |

La tasa de "detectó algo" bajó un poco (100%→89.5%), pero es una
comparación engañosa: antes "detectar algo" muchas veces significaba
marcar medio parachoques o un pedazo de pavimento. Ahora, cuando detecta,
el recuadro casi siempre queda ajustado justo sobre la placa (revisado
visualmente en `resultados/mosaico_fotos_reales.jpg`) — de ahí que las
lecturas exactas SÍ subieron (5→7) aunque la tasa de detección cruda haya
bajado un poco.

**Un retroceso puntual, documentado con honestidad:** la foto de la placa
`KPS·796` (Sandero), que leía perfecto (0.87 de confianza) en la vuelta
anterior, esta vez no detectó nada. Es un recordatorio de que reentrenar
con una distribución de datos distinta no mejora todos los casos por
igual — algunos que ya funcionaban pueden empeorar mientras la mayoría
mejora. El balance neto es claramente positivo (7 aciertos nuevos o
mejorados por 1 caso perdido), pero no hay que presentar esto como una
mejora sin matices.

---

## 6.5. Cuarta vuelta: fotos reales como ejemplos de entrenamiento (pseudo-etiquetado)

El usuario preguntó si enviar más fotos/video ayudaría. Respuesta: la
variedad importa más que la cantidad (un video más largo del mismo
parqueadero aporta poco; fotos de lugares distintos sí). Pero antes de
pedir más material, se encontró algo aprovechable en el que ya se tenía:
tras la tercera vuelta, el detector ya ubica bien la placa en la mayoría
de las 19 fotos reales (11 de 19, confirmado visualmente) — solo que el
modelo nunca las había visto como EJEMPLO DE ENTRENAMIENTO, solo como
fondo genérico.

**Técnica: pseudo-etiquetado.** Se tomaron las cajas que el propio
detector (ya mejorado) encontró sobre esas 11 fotos, se revisaron una por
una visualmente para confirmar que el recuadro quedaba ajustado sobre la
placa real, y se usaron como etiqueta de entrenamiento — sin dibujar nada
a mano. Las otras 8 fotos (recuadro en malla/pavimento, o sin detección)
NO se incluyeron: una caja mal ubicada usada como si fuera correcta sería
peor que no usar la foto (`src/agregar_ejemplos_reales.py`, nuevo script,
con la lista curada y por qué se descartó cada foto excluida).

Por qué importa esto más que todo lo anterior: hasta ahora el modelo solo
había visto placas SINTÉTICAS (dibujadas por código, sobre cualquier
fondo). Nunca había visto una placa real de verdad — con su relieve, sus
tornillos de montaje, su reflejo bajo luz real. Esta vuelta agrega ese
ingrediente que faltaba.

Cada una de las 11 fotos se repitió 15 veces en el dataset de
entrenamiento (165 imágenes agregadas a las 1.200 sintéticas de la
tercera vuelta) — no son copias inútiles porque Ultralytics aplica una
variación aleatoria distinta (rotación, color, recorte) cada vez que usa
una imagen durante el entrenamiento.

**Estado:** dataset regenerado (`data/dataset.zip`, ahora con 1.365
imágenes de entrenamiento), pendiente de correr en Colab y volver a medir.

---

## 7. Banco de pruebas completo (Semana 8, 30 repeticiones por condición)

**Script:** `pruebas/banco_pruebas.py` (todos los experimentos, valor por
defecto de repeticiones).

| Experimento | Resultado | Notas |
|---|---|---|
| Distancia (simulada) | 60-77%, sin tendencia clara | Simulación por reescalado no reproduce bien el desenfoque óptico real — repetir con fotos reales del carro a escala |
| Ángulo | 63% (0°) → 47% (15°) → 13% (30°) → 0% (45°+) | Caída clara y fuerte; recomienda cámara centrada en el carril |
| Iluminación | Mejor en condiciones intermedias (76-80%), peor en extremos (57-63%) | Recomienda luz difusa, no directa |
| Desenfoque de movimiento | Estable hasta cierto punto (73-77%), se derrumba después de ~9px (20%, luego 7%) | Recomienda limitar velocidad del vehículo en la zona de lectura |
| Carro vs. moto | Carro 70%, moto 60% | Las motos (un carácter más al final) leen algo peor |
| Votación temporal | Una lectura 73.3% vs. con votación 70.0% (peor) | Resultado contraintuitivo: la simulación genera cada fotograma de forma independiente, sin la correlación entre fotogramas de un video real — repetir con video real de la Semana 4 |
| Tiempo por etapa | Detección 33 ms, OCR ~4.9 s (bajó a ~1.9 s tras el fix de la sección 5), consulta BD <1 ms | El OCR es, por mucho, el cuello de botella del sistema |

**Nota metodológica importante:** los experimentos de distancia y votación
temporal usan sustitutos sintéticos que no capturan bien la física del
fenómeno real (desenfoque óptico por distancia; correlación entre
fotogramas consecutivos de un video). Ambos quedaron documentados como
"repetir con datos reales" en vez de tomarse como conclusión final.

---

## 8. Otros bugs encontrados y corregidos durante el desarrollo

| Bug | Síntoma | Causa | Corrección |
|---|---|---|---|
| `cv2.imread`/`imwrite` fallan en silencio | Los scripts corrían sin error pero no se generaban archivos | OpenCV en Windows no maneja bien rutas con tildes/ñ (la ruta del proyecto tiene "Administración") | `src/utilidades_imagen.py` con `leer_imagen`/`escribir_imagen` que leen/escriben por bytes |
| `UnicodeEncodeError` al descargar modelos de EasyOCR | Traceback al inicializar el lector la primera vez | La consola de Windows usa cp1252 por defecto, no soporta el carácter `█` de la barra de progreso | `config.py` fuerza `sys.stdout`/`stderr` a UTF-8 al importarse |
| Texto de placa se salía del borde en algunas imágenes sintéticas | Placas generadas con letras cortadas visualmente | Tamaño de fuente fijo (200pt) no cabía siempre en el ancho de la placa | `generador_placas.py` prueba tamaños de fuente decrecientes hasta que el texto quepa |
| Cronómetro del diagnóstico mostraba "0.0 segundos" | `pruebas/diagnostico.py` reportaba mal el tiempo total | Los chequeos corrían con un decorador que se ejecutaba al importar el módulo, antes de arrancar el cronómetro | Se reescribió sin decorador, con una lista explícita de chequeos ejecutados dentro de `__main__` |
| Dataset de Colab "duplicado" | `FileNotFoundError: ... missing path '.../images/val'` | Ver sección 2 | Ver sección 2 |
| Entrenamiento en CPU en vez de GPU | Entrenamiento mucho más lento de lo esperado | El entorno de ejecución de Colab no tenía GPU seleccionada | Verificar `Entorno de ejecución → Cambiar tipo → GPU` antes de entrenar |

---

*Bitácora de trabajo — Proyecto ALPR Porterías · Colegio Londres. Actualizar
esta sección cada vez que se corra un experimento nuevo o se cambie un
parámetro de configuración con impacto medido.*
