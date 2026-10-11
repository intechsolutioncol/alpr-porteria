# Pendientes del proyecto

Estado al 2026-09-04. Ver `BITACORA_EXPERIMENTOS.md` para el detalle de lo
ya medido y `GUIA_DE_USO.md` para cómo usar lo que ya está construido.

## ACCIÓN INMEDIATA: reentrenar el detector con el dataset corregido

Las primeras fotos reales revelaron que el detector de placas (entrenado
solo con datos sintéticos donde la placa siempre ocupaba ~62% del cuadro)
no generaliza bien: 63.2% de detección en fotos reales, y en la mayoría de
los casos la caja detectada ocupaba 89-100% del ancho de la foto (agarraba
medio parachoques, no la placa). Causa raíz diagnosticada y corregida en
`src/generador_placas.py`/`src/preparar_dataset_yolo.py` (ver bitácora
sección 6.2): ahora el dataset de entrenamiento varía la escala de la
placa dentro del cuadro (de dominante a pequeña), simulando distintas
distancias de cámara.

**Ya está regenerado un nuevo `data/dataset.zip` con esta corrección — el
siguiente paso es subirlo a Drive y repetir el entrenamiento en Colab**
(mismo notebook, `entrenar_detector_colab.ipynb`), reemplazando
`modelos/best.pt` cuando termine.

## 0. Checklist contra los requerimientos originales (PARTE G de la guía)

**Mínimo aceptable:**

| Requisito | Estado |
|---|---|
| Reconoce placas en fotos con ≥70% de precisión | ⚠️ 90% en placas sintéticas, pero **63.2% de detección en fotos reales** (ver "Acción inmediata" arriba) — esperando el reentrenamiento para volver a medir |
| Reconoce en video con votación temporal con ≥80% | ⚠️ No confirmado — el único dato disponible es sintético y salió contraintuitivo (ver bitácora sección 7); necesita video real |
| Base de datos funcional con residentes y visitantes | ✅ Completo |
| Panel del vigilante operativo | ✅ Completo |
| Demostración con carro a escala | ❌ Pendiente — necesita maqueta física (punto 2) |
| Tablas y gráficas de al menos 4 experimentos | ✅ 7 del banco de pruebas + 6 variantes de OCR |

**Deseable:**

| Requisito | Estado |
|---|---|
| ≥90% en video | ⚠️ Igual que arriba: pendiente de video real |
| Corrección por posición funcionando y medida | ✅ Medida a fondo, con un bug encontrado y corregido |
| Módulo de propietario completo | ✅ Completo (con autoregistro agregado) |
| 7 experimentos con análisis | ✅ Completo |

**Opcional:**

| Requisito | Estado |
|---|---|
| Talanquera automatizada | ⚠️ Código listo, falta el Arduino físico |
| App en celular | ⚠️ La app ya es accesible desde el navegador de un celular en la misma red (Streamlit es una app web), pero no es una app nativa instalable |
| Informe HTML/PDF automatizado | ✅ Completo (`resultados/informe.html`) |

**Conclusión: el software ya cumple o supera todo lo que depende de código.
Lo único que falta para cerrar el "mínimo aceptable" son los dos ⚠️/❌ de
arriba, y ambos dependen de que aportes fotos/video reales y la maqueta
física — no de más desarrollo.**

---

## Software: prácticamente completo

Todo el pipeline (detector entrenado, OCR, validador, base de datos, app
con tres roles) está construido, probado y documentado. Lo que falta de
software es menor y está listado en la sección "Mejoras opcionales" más
abajo.

---

## 1. Insumos que solo tú puedes aportar (bloqueado sin intervención física)

| Qué | Cuántas | Para qué | Dónde va |
|---|---|---|---|
| Fotos de placas reales, de frente, bien iluminadas | 10 mínimo, 50 idealmente | Verificación Semana 1 y `pruebas/comparar_detectores.py` | `data/reales/` |
| Video de carros pasando | 1-2 | Probar `pipeline.py` con votación temporal en condiciones reales (el experimento sintético dio un resultado contraintuitivo que solo un video real puede aclarar — ver bitácora sección 7) | `data/reales/` |
| Fotos del carro a escala a distintas distancias/ángulos | ~30 por condición | Repetir los experimentos de distancia y ángulo del banco de pruebas con datos reales en vez de la simulación sintética | `data/reales/` |
| Video del carro a escala en la maqueta terminada | 1 | `pruebas/demo_grabada.py` (respaldo Semana 9) | `data/reales/demo/demo_grabada.mp4` |

## 2. Hardware físico (Semana 7)

- Carro RC escala 1:10 o 1:14
- Placas impresas a escala, plastificadas
- Webcam 1080p con soporte fijo
- Iluminación LED fija — **según el banco de pruebas, difusa, no directa**
  (la placa amarilla reflectiva pierde precisión con luz directa fuerte)
- (Opcional) Arduino + servo para la talanquera — código ya listo en
  `arduino/talanquera/` y `src/talanquera.py`

## 3. Experimentos a repetir con datos reales una vez existan los insumos de arriba

- `pruebas/comparar_detectores.py` — nunca se ha podido correr (necesita
  fotos reales en `data/reales/`)
- `pruebas/banco_pruebas.py`, específicamente distancia y votación
  temporal — los resultados sintéticos actuales están marcados como no
  concluyentes en la bitácora
- `pruebas/probar_ocr_sinteticas.py --usar-detector --usar-validador`
  sobre fotos reales (no solo sintéticas) para confirmar que la ganancia
  medida (74%→90%) se sostiene fuera del mundo sintético

## 4. Trabajo humano, no técnico

- Póster con las gráficas de `resultados/` y las tablas de `BITACORA_EXPERIMENTOS.md`
- Ensayos de sustentación — usar `GUIA_DE_USO.md` para explicar la interfaz
  y `ETICA_Y_PROTECCION_DE_DATOS.md` para la parte de Ley 1581
- Decidir si cambian las contraseñas de demo (`src/app.py`,
  `CONTRASENAS_POR_ROL`) antes de la feria

---

## 5. Mejoras opcionales (no bloquean la feria, quedan para "trabajo futuro")

### ~~Portal de residentes — login individual~~ ✅ Hecho (2026-10-10)

Implementado: cada residente tiene su propia cuenta (documento +
contraseña, guardada como hash con PBKDF2, nunca en texto plano), con
flujos de registro nuevo, activación de cuenta para residentes ya creados
por administración, e inicio de sesión. El apartamento ya se deriva del
login, no de un selector abierto. Ver `GUIA_DE_USO.md` sección 2.2.

### Publicar la app con un enlace público (no solo red local)

Ahora mismo la app es accesible por red local (cualquier celular en el
mismo Wi-Fi puede entrar sin instalar nada) pero necesita que alguien la
tenga corriendo en su computador. Para un enlace público permanente, usar
un servicio de hospedaje — por ejemplo Streamlit Community Cloud (gratis).
Pendiente: decidir si se publica solo para la feria (temporal) o de forma
permanente.

### Seguridad real de la base de datos

Las contraseñas de los residentes ya están protegidas (hash, no texto
plano). Pendiente: las contraseñas compartidas de Vigilante/Administración
siguen en texto plano en el código, y la base de datos en sí sigue sin
cifrar — aceptable para una demo de feria, no para producción real. Detallado en
`ETICA_Y_PROTECCION_DE_DATOS.md` sección 4.

### Otras ideas de mejora de precisión sin explorar todavía

- **Adivinar mejor el tipo carro/moto antes de corregir.** Ya se corrigió
  un bug que hacía perder 3 puntos (87%→90%, ver bitácora sección 6.1);
  sabiendo el tipo de antemano se llegaría a 94%. Si el tipo se pudiera
  inferir de forma confiable (p. ej. de la clasificación del detector de
  vehículos original, carro/moto/bus/camión), se podría cerrar esos 4
  puntos que faltan.
- Ablación de CLAHE (¿ayuda de verdad en imágenes sintéticas limpias, o
  solo en fotos reales con mala luz?)
- Barrido de `config.ANCHO_OBJETIVO_OCR` (probar 900/1500/1800 en vez de
  solo 1200) para encontrar el punto óptimo entre precisión y velocidad
- Volver a probar `config.MARGEN_RECORTE_PLACA` > 0 ahora que ya no hay
  confusión de resolución de por medio (se descartó antes por una causa
  distinta — ver bitácora sección 4-5)
- Ampliar el dataset sintético con desgaste de placa (suciedad, rayones)
  una vez haya fotos reales que muestren qué tan sucio es el entorno real

### Talanquera física

Código completo (`arduino/talanquera/talanquera.ino`, `src/talanquera.py`,
botón integrado en la app), falta solo el hardware.
