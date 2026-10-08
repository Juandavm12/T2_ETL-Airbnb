# ODD — primera unidad

## Objetivo y aceptación

- [x] Importar tres CSV/gzip por lotes, preservar strings y verificar acuses/conteos.
- [x] Rechazar colecciones no vacías con preflight global y explicar estado parcial.
- [x] Extraccion entrega DataFrames por lotes, registra errores y cierra recursos.
- [x] CLI configurable, logs únicos sin secretos y entorno reproducible.
- [x] Pruebas sin servicios; instalación y uso documentados en README.

## Progreso y evidencia

1. RED: unittest falló con `ModuleNotFoundError: No module named 'src'`
   tras crear los contratos antes de la implementación.
2. GREEN: 7 pruebas iniciales pasaron tras implementar; triangulación inicial:
   **8 pruebas pasaron**, incluyendo cursor parcial/cierre y logs únicos.
3. Desde esta carpeta: `.venv/bin/python -m unittest discover -s tests -v`;
   `.venv/bin/python main.py --help` y `.venv/bin/python -m pip check` pasan.
4. Python 3.14.7, versiones verificadas en requirements; configuración local
   de editor en pyrightconfig.json, seleccionar intérprete `.venv/bin/python`
   (Windows: `.venv/Scripts/python.exe`). No instalar paquetes globales.

## Corrección CSV truncado

- Regresión: `test_csv_truncado_falla_sin_insertar_ni_reportar_exito`.
- RED observado: `AssertionError: Error not raised` antes de `strict=True`.
- GREEN: regresión pasa; suite completa pasa **9 pruebas**. Comprueba ERROR,
  ausencia de éxito y ninguna inserción cuando el primer registro está truncado.
- Comandos desde esta carpeta:
  `.venv/bin/python -B -m unittest discover -s tests -p test_etapa1.py -k test_csv_truncado_falla_sin_insertar_ni_reportar_exito -v`
  y `.venv/bin/python -B -m unittest discover -s tests -v`.

## Verificación independiente

- Revisión y revalidación independientes: **9/9 pruebas pasan**; caso truncado
  reproducido con conteos `[0, 1]`, sin inserciones ni éxito falso. Hallazgo cerrado.
- CLI sin MongoDB: salida 1 y log ERROR `ServerSelectionTimeoutError`, no éxito.
- Revisión nativa no disponible por un repositorio Git anidado preexistente en
  otra materia; evaluación no calculable, cubierta con verificación independiente.
- LSP de la raíz del semestre no resuelve pandas/pymongo del entorno anidado;
  importaciones con `.venv/bin/python` verificadas. No equivale a un fallo runtime
  ni se afirma diagnóstico LSP limpio.

## Bloqueo y límites

Bloqueo histórico de la primera unidad: MongoDB no disponible; integración y
conteos entonces pendientes. **Resuelto** con instalación autorizada e integración
real documentadas abajo. En aquella unidad no se operaron servicios ni se hicieron
commits, git init, transformaciones o notebook ficticio.
Preflight no garantiza atomicidad; recuperación documentada en README.
La instalación inicial de pip no usó `--no-cache-dir`: pudo tocar caché de
pip fuera de la carpeta; no se hizo limpieza externa. Comandos de instalación
reproducibles del README ya desactivan esa caché.
Tamaño al cerrar la corrección: 521 líneas antes de incorporar los integrantes
y esta evidencia final; fuentes/pruebas/documentación/configuración,
exceso moderado sobre el objetivo aproximado de 400 líneas para preservar
cobertura y legibilidad; no se recortaron pruebas para ajustarlo.

## Integración real — bloqueo resuelto

- MongoDB oficial APT 8.0.32 en Ubuntu 24.04.4 amd64 WSL; mongosh 2.13.0,
  database-tools 100.19.1. Ping `ok: 1`; arranque manual sin systemd/autostart.
- Configuración del paquete intacta, escucha solo en localhost y caché
  WiredTiger de 0,5 GB mediante opción de arranque. Sin auth, uso académico local.
- `.venv` inalterado: Python 3.14.7, pandas 3.0.6, pymongo 4.18.2.
  Padre y verificador independiente confirman 9 pruebas OK y `pip check` OK;
  la escritura documental no operó sobre MongoDB ni cambió dependencias.
- Importación real: salida 0, 110,96 s, RSS máximo cliente Python 265.844 KiB.
- Extracción real: salida 0, 37,01 s, RSS máximo cliente Python 295.600 KiB;
  recorrió todas las colecciones con lotes de 10.000, sin retener DataFrames.
- Conteos CSV/MongoDB/extracción: Listings 19.187, Reviews 527.731,
  Calendar 7.003.255. No se materializó Calendar completo.
- Primeros 100 y último documento por colección coinciden en todos los campos
  CSV; valores muestreados strings. SHA256 de las tres fuentes sin cambios.
- Reimportación rechazada: salida 1, 1,18 s, RSS 86.540 KiB; conteos posteriores
  iguales, sin nuevas inserciones según validación del padre.

### Evidencia y revisión

1. [Validación JSON](evidencias/validacion_mongodb.json): resultado fuente
   conservado con métricas, procedencia y conteos posteriores reportados.
2. Logs exactos: [importación](evidencias/importacion_real.txt),
   [extracción](evidencias/extraccion_real.txt) y
   [rechazo](evidencias/reimportacion_rechazada.txt).
3. [README](README.md): tabla de resultados, límites y guía oficial de instalación.
4. Verificación independiente final conforme, sin hallazgos: ping, opciones del
   servidor, conteos actuales, 100 documentos por colección mediante `Extraccion`,
   hashes/tamaños de los CSV, JSON y copias byte a byte de los logs comprobados.
   La extracción completa y los últimos documentos se corroboraron con evidencia
   histórica, sin repetir ese recorrido. No constituye aprobación nativa.

Las fuentes temporales `/tmp/airbnb-etl-*-metrics.txt` y
`/tmp/airbnb-etl-real-validation.json` no son enlaces durables de entrega;
el JSON identifica su procedencia. Los logs originales están en `logs/`;
las copias en `evidencias/` permiten revisar sin versionar ese directorio.

### Límites de esta unidad documental

- RED/GREEN de comportamiento: no aplican a evidencia pasiva; no se cambió
  código ni se volvió a importar, extraer o arrancar MongoDB.
- Verificación documental: JSON parseable, resultado fuente preservado,
  métricas coincidentes, logs idénticos byte a byte y enlaces locales existentes.
- Muestreo de contenido, no comparación exhaustiva de todos los documentos.
  RSS no incluye el servidor MongoDB. No se generaliza el rendimiento medido.
- Se conserva el histórico de revisión nativa no disponible y la limitación
  LSP del entorno anidado; no se afirma revisión nativa ni diagnóstico limpio.
- Pendientes al cierre de aquella unidad: EDA, Transformacion, Carga, SQLite,
  XLSX, informe y publicación. EDA queda resuelto en la unidad siguiente.
  Responsabilidades entonces por confirmar; asignación actual en README.
  Sin entregables simulados.

## ODD — unidad EDA completo (interrupción resuelta)

La interrupción anterior no constituye evidencia de ejecución. Se retomaron
helper, pruebas y notebook existentes sin reimplementarlos desde cero.

- [x] Fuente exclusiva MongoDB local `airbnb`, lotes 10.000, sin CSV ni escrituras DB.
- [x] Perfiles completos 19.187 × 90, 527.731 × 6 y 7.003.255 × 5; `_id` excluido.
- [x] Null/NaN, strings vacíos, marcadores candidatos y ausencia separados.
- [x] Duplicados exactos de negocio con `$group`, allowDiskUse; sin borrar datos.
- [x] Descriptivos, conversiones, fechas, IQR, categorías, correlaciones y N por par.
- [x] Reviews/Calendar streaming; frecuencias exactas sin expandir Calendar.
- [x] Amenities JSON, host plano y matriz propuesta transformación/razón/riesgo.
- [x] Notebook real guardado con 7 PNG e interpretaciones; JSON de la misma ejecución.
- [x] README runtime local, batch reproducible y límites; integrantes preservados.

### Validación observada en esta retomada

Comandos desde `etl_airbnb`:

1. `.venv/bin/python -B -m unittest discover -s tests -v`: **17/17 OK**,
   0,062 s (8 EDA y 9 etapa 1).
2. `.venv/bin/python -m pip check`: sin conflictos.
3. `.venv/bin/python -m pip freeze`: coincide con requirements, sin instalar deps.
4. `.venv/bin/python -m ipykernel install --prefix "$PWD/.venv" --name etl-airbnb
   --display-name 'Python (venv etl_airbnb)'`: kernel registrado bajo `.venv`.
   Variables Jupyter/IPython de README mantienen cachés/runtime bajo `.venv`.
5. `NotebookClient(..., timeout=900, kernel_name='etl-airbnb', allow_errors=False,
   resources={'metadata': {'path': .../notebooks}}).execute()` mediante
   `.venv/bin/python -B -`: **409,74 s**, 8 celdas código ejecutadas, 0 errores,
   **7 PNG**; `nbformat.validate` pasa. Primera celda afirma intérprete local.
   Validación posterior: firmas PNG decodificadas con Pillow verificadas,
   JSON parseable, conteos de ejecución presentes y kernel local confirmado.
   Se añadió backend inline explícito y selección de ruta Windows/Linux.
   Windows no se ejecutó. Advertencia TCP sin cifrado del kernel observada;
   runtime académico local, no exponerlo a red.

Notebook: **527.768 bytes**; JSON: **77.500 bytes**. Notebook fuente: **231 líneas**,
198 de código; el volumen JSON/base64 PNG no representa líneas authored.
Helper/pruebas existentes: 151/80 líneas. Unidad de varios cientos de líneas y
outputs autorizada explícitamente; no se recortó evidencia para llegar a 400.

JSON anterior conservado como **provisional no revalidado** en
`.venv/eda_cache/resumen_eda_previo_provisional.json`. Comparación global no
idéntica: la fuente actual añade cotizaciones, fechas y columnas vacías y amplía
resúmenes; no se interpreta como cambio de datos. Conteos/outliers de la nueva
corrida son evidencia fresca, no copia del resumen anterior.

### Hallazgos frescos (sin aplicar limpieza)

- Cero grupos/exceso de claves duplicadas en las tres colecciones; claves
  presentes y únicas implican filas completas únicas excluyendo `_id`.
- Precio: 195 faltantes, 1.410 atípicos IQR entre 18.992 válidos.
- Precio mediana 161.460, media 446.026,55, máximo 448.176.567;
  unidades nominales, moneda no confirmada y extremos por revisar.
- Minimum_nights: 4 faltantes y 4.053 atípicos; availability_365: 1.129 atípicos.
- Reviews 2010-10-06–2026-06-21; Calendar 2026-06-21–2027-06-21.
- Amenities: 19.187 listas válidas, cero inválidas; Wifi en 17.918 anuncios.
- Listings: 12 columnas totalmente vacías; no imputar información inexistente.

### Disciplina y límites

No se reconstruye un RED/GREEN histórico para helper/pruebas previos: no hay
registro de su creación anterior. La retomada preservó esos comportamientos;
los cambios fueron configuración de kernel, ejecución del notebook y documentación.
Corresponde verificación funcional ordinaria, reportada arriba, sin exigir un
interruptor de TDD ni inventar un RED para cambios pasivos.
No fallaron comandos de esta retomada antes de corregirlos.

No hay snapshot transaccional: evitar escritores concurrentes. Conteo no
sustituye comparación exhaustiva de documentos. IQR no prueba error; correlación
no implica causa. Calendar f no prueba reserva, meses extremos pueden ser
parciales y horizonte de captura no equivale a todas fechas futuras hoy.
No se modificaron logs ni JSON históricos de integración, no se operaron
servicios, no se reimportó, no se hizo Git ni se implementaron Transformacion,
Carga, SQLite/XLSX o informe.

### Cierre de verificación

Verificación independiente conforme: 17/17 pruebas y `pip check` pasan; se
recalcularon faltantes, cercas IQR y descriptivos de Listings desde MongoDB sin
usar los helpers. Notebook válido con 8 ejecuciones únicas, 7 PNG inspeccionados
(en particular precio, correlación y disponibilidad) y cero errores. JSON estricto,
perfiles, denominadores mensuales y 69 histogramas de prueba corroborados.
No se repitió el recorrido completo ni la agregación de claves de Calendar;
se revisaron su código y evidencia persistida. No constituye aprobación nativa.

El sondeo estático encontró 18 avisos auxiliares de `int()`/`float()` sin
`try/except`: el triage read-only confirmó conversiones de conteos o estadísticas
numéricas ya controladas, no parseo directo de texto sin validar. No se cambiaron
las reglas ni se agregaron excepciones cosméticas; no se afirma limpieza global
por ausencia de diagnósticos.

## ODD — Transformación formal completa (solo lectura)

Unidad completa de varios cientos de líneas autorizada; guía página 4 y cuartiles
Listings del EDA gobiernan las decisiones. SINGLE WRITER, sin delegar ni Git.

- [x] API pura por lote y generador para futura Carga, sin concat global/set 7M.
- [x] Preflight global de duplicados raw con helper EDA antes de consumir datos.
- [x] IDs exactos y fecha clave Calendar canónica: no colisiones por trim/coerción.
- [x] Dedup exacto excluyendo _id, conflictos rechazan, sin first-wins.
- [x] Nulos declarados, marcadores por columna, sin imputar/borrar filas.
- [x] Precios/fechas/flags nullable, dominios y errores auditados.
- [x] Cuartiles y cercas precio fijos EDA; outliers conservados, moneda no confirmada.
- [x] Amenities puente determinista, JSON escalar, host plano, 12 columnas vacías retenidas.
- [x] CLI transformar consume tablas sin cargarlas y emite JSON estricto de auditoría.
- [x] Logs reutilizados, sin secretos; copia exacta y JSON real persistidos.

### TDD y validaciones observadas

Comandos desde `etl_airbnb`, intérprete `.venv/bin/python -B`, sin instalaciones:

1. RED real antes de crear `src/transformacion.py`:
   `-m unittest discover -s tests -p test_transformacion.py -v`:
   salida 1, `ModuleNotFoundError: No module named 'src.transformacion'`,
   0,000 s. Diez contratos de comportamiento ya escritos; no RED reconstruido.
2. GREEN enfocado, mismo comando: **10 pruebas OK**, 0,095 s.
3. GREEN completo inicial: `-m unittest discover -s tests -v`:
   **27 pruebas OK**, 0,116 s (17 existentes + 10 nuevas).
4. Triangulación de fecha clave no canónica y nulos por columna; refactor de
   anotaciones, zip estricto, orden de conversiones y dominio ingresos estimados
   (cero legítimo, no señal negativa). Suite final: **29/29 OK**, 0,136 s.
5. `-m pip check`: `No broken requirements found`; `main.py --help`: salida 0,
   acción transformar disponible. Dependencias y entorno intactos.
6. `main.py transformar --base airbnb --batch 10000`: salida 0, dos recorridos
   reales completos observados: 208,72 s inicialmente y **199,99 s** después
   del ajuste de dominio ingresos cero. Evidencia durable corresponde solo al
   segundo; logs originales de ambas ejecuciones conservados sin alterarlos.

El wrapper de validación invocó la CLI con subprocess, parseó stdout rechazando
NaN/Infinity, guardó JSON `allow_nan=False` y copió bytes del log original.
Verificó conteos antes/después, ausencia de duplicados globales/exactos y suma de
estados de conversión = filas por colección. No registró documentos privados.

Resultado final: Listings **19.187 / 2 lotes**, Reviews **527.731 / 53**,
Calendar **7.003.255 / 701**, todas sin pérdida de filas; puente **505.595**.
Precio **18.992 válidos / 195 faltantes / 0 inválidos-no finitos**, **1.410**
atípicos preservados. Amenities **19.187 válidas / 0 inválidas / 0 repetidas**.
Cero errores de conversión/dominio final; cero duplicados globales.

### Tamaño, alcance y límites

Fuentes nuevas authored: **242 líneas** transformacion y **176** pruebas;
`main.py` final **109** líneas (incluye código previo): **527 líneas** fuente/pruebas/CLI
revisables, más documentación. JSON/log generado no cuenta como authored.
No se recortaron contratos para forzar una unidad de 400 líneas.

No snapshot transaccional: evitar escritores concurrentes. Conteos iguales no
prueban contenido idéntico. Preflight garantiza unicidad raw observada, no todas
las validaciones de valor antes del primer yield; futuros consumidores deben
cerrar generadores y definir recuperación si hay fallo posterior.
El lote puro por sí solo no garantiza unicidad cross-lote; usar generador MongoDB.
Calendar fechas clave inválidas rechazan en vez de colapsar claves a NULL.
No se realizó Carga SQLite/XLSX, informe, EDA/notebook nuevo, operaciones sobre
servicios, importaciones MongoDB ni cambios de dependencias. Sin aprobación nativa
ni afirmación de ETL final. Cambios ajenos preexistentes preservados.

Evidencias: `evidencias/resumen_transformacion.json`,
`evidencias/transformacion_real.txt`, log original indicado por el JSON.
Temporales de las 17 pruebas previas creados/limpiados exclusivamente por sus
propios TemporaryDirectory autorizados; no limpieza manual de temporales previos.

## Corrección de revisión — dos P2 confirmadas

Revisión independiente READONLY reportada por el padre: 29 pruebas OK, conteos
MongoDB y Listings/rangos/IQR/puente corroborados. Se corrigieron únicamente:

1. Año < 1000: `%Y` de libc omitía ceros. Ahora se compone año nullable `Int64`
   a string con `zfill(4)` más mes/día; 0001, 0999, 1000 y 9999 conservan
   exactamente YYYY-MM-DD. Fechas imposibles conservan nulo y derivados nulos.
2. Dedup antes de serializar: huella raw recursiva con etiqueta de tipo.
   Dict vs string JSON, list vs string JSON, bool vs int e int vs float
   son conflictos, incluso dentro de estructuras. Dicts iguales ignoran orden
   de inserción; listas conservan orden. `_id` excluido, entrada inmutable.
   Solo se calculan huellas para claves repetidas dentro del lote; no estado
   global ni nuevas estructuras para millones de claves.

Comandos desde `etl_airbnb`:

- RED real: `.venv/bin/python -B -m unittest discover -s tests -p
  test_transformacion.py -k regresion -v`: salida 1; 2 pruebas, **5 failures**,
  0,037 s. Cuatro colisiones no rechazadas y años 1/999 sin ceros.
- Primera validación enfocada tras fix: 15 pruebas, dos errores de triangulación:
  asignar lista con `.loc` y fixture año 0000 aceptado por pandas pero no por
  strftime/Python. Se corrigieron fixture `.at` y fecha imposible 0999-02-30;
  no se amplió la implementación a calendarios fuera del rango 0001–9999.
- GREEN regresiones: mismo comando RED, **2/2 OK**, 0,027 s.
- GREEN completo: `.venv/bin/python -B -m unittest discover -s tests -v`:
  **32/32 OK**, 0,166 s (29 previas + 3 nuevas).

Límites: la huella conserva tipos recibidos por el DataFrame, no puede recuperar
coerciones previas de pandas. Nulos del mismo tipo se consideran iguales.
No se repitió CLI 7M: datos reales CSV strings únicos no ejercen las colisiones
ni años antiguos; evidencia real anterior y logs intactos. Año 0000 queda fuera
 del rango validado (pandas puede parsearlo, Python strftime lo rechaza).
Sin nuevas dependencias, servicios, DB writes, Git ni aprobación nativa.

### Cierre independiente de las correcciones

- Revalidación read-only: **32/32 pruebas OK**, 0,194 s; `pip check` sin conflictos.
- Adversarios propios corroboran fechas 0001–9999, derivados nullable y nueve
  conflictos tipados; ambas P2 cerradas sin hallazgos nuevos en este alcance.
- Listings completo con código corregido: 19.187 filas, 18.992 precios válidos,
  195 faltantes, 1.410 atípicos preservados y 505.595 pares amenities únicos.
- Log original y copia versionable siguen idénticos; SHA256
  `36a3e38c9ef922074b909b67680ea0ffd0c93229602ac1af5429118084ed097a`.
- No se repitió CLI/Calendar completo; se conservó la evidencia real previa.
  La evaluación nativa siguió no calculable por el repositorio anidado de otra
  materia; se realizó verificación independiente, no aprobación nativa.
- Sondeo LSP final sobre tres archivos: tres avisos auxiliares `int(sum)` en
  transformación, corroborados como conteos controlados, no parseo de texto.
  No se suprimieron reglas ni se afirma limpieza global.

Al cierre histórico de Transformación, la siguiente unidad era Carga SQLite y
XLSX por lotes; entonces no se implementaron Carga, informe ni publicación.
Carga queda resuelta en la unidad siguiente; informe/publicación siguen pendientes.

## ODD — Carga SQLite/XLSX e integración completa

Guía página 5: SQLite obligatorio, exportación XLSX, verificación y logs.

- [x] `Carga` consume una corriente Extracción → Transformación por lotes.
- [x] SQLite nuevo con afinidades semánticas, PK/FK e integridad verificada.
- [x] XLSX streaming particionados, encabezados y todas las filas conservados.
- [x] Destino exclusivo; sin overwrite, dedup silencioso ni truncamiento de texto.
- [x] Checks, cierre/verificación XLSX y fuente antes del commit SQLite.
- [x] Manifest completo publicado atómicamente **después** del commit SQLite.
- [x] Logs y evidencia real persistida; verificación independiente conforme.
- [ ] Publicación del repositorio; después PDF según orden solicitado.
- [x] Integrantes exactos registrados en README.
- [x] Responsabilidades asignadas con autorización del usuario, detalladas en README;
  reparto equitativo, no atribución de contribuciones históricas.

### Historial de pruebas e incidente de ejecución

Reporte histórico del worker: seis contratos iniciales tuvieron RED
`ModuleNotFoundError` antes de implementar Carga. No se reconstruye ni se
atribuye RED previo a las 21 pruebas finales. Resultado ordinario final:
**53 pruebas = 32 previas + 21 Carga**, XlsxWriter **3.2.9** y requirements ya
actualizados, `pip check` conforme; este cierre no instala dependencias.
Un mensaje de fallo del worker no sustituye el resultado de la corrida real:
la evidencia persistida registra CLI salida 0 y artefactos verificados.
No se inventa una nueva corrida ni un RED a partir de ese incidente.

Comando histórico desde esta carpeta:
`.venv/bin/python -B main.py cargar --base airbnb --batch 10000`.
[validacion_carga.json](evidencias/validacion_carga.json) y
[carga_real.txt](evidencias/carga_real.txt) documentan el resultado:

- Destino `salidas/ejecucion_20261007_223144_602d1ed1c8cc4df299affc7375e7af17`.
- Listings 19.187, Reviews 527.731, Calendar 7.003.255, puente 505.595;
  **8.055.768 filas** en total, sin pérdida.
- SQLite 908.255.232 bytes; 10 XLSX; total combinado 1.225.231.757 bytes.
- Calendar: seis partes de 1.048.575 + 711.805 filas, cada una con encabezado.
- CLI 1.108,398 s, Carga 1.105,545 s; RSS cliente 392.596 KiB,
  no memoria del servidor. Métricas históricas, no rendimiento garantizado.

### Readiness y recuperación: alcance exacto

El commit SQLite ocurre tras checks/cierre/verificación XLSX y fuente, pero
**antes** del dump y rename atómico de `listo.json`. Antes del commit se intenta
rollback; fallo posterior de escritura/rename puede conservar SQLite confirmado
más XLSX sin manifest: diagnóstico parcial, no publicación. Manifest es marcador
de disponibilidad, no atomicidad entre formatos ni promesa de recuperación.
No declarar listo por JSON malformado; verificar manifest y artefactos.
No overwrite/reanudación/limpieza automática prometidos. Cierre fallido se
registra y no autoriza disponibilidad. Corte de energía no probado.

IDs TEXT exactos y NULL; precios REAL nominales, moneda no confirmada y precisión
Excel limitada. Strings no son fórmulas/URLs; >32.767 caracteres falla sin
truncar. NUL en identificador SQL se rechaza. Sondeo SQL estático STOP fue
triado: quote de identificadores + bind de valores + allowlist de tablas,
sin suprimir reglas. LSP: cuatro avisos auxiliares de cast con guards y dos
inconclusos; no diagnóstico global limpio. Evaluación nativa UNASSESSABLE por
Git independiente de otra materia, cubierta por revisión independiente,
**no aprobación nativa**.

### Verificación independiente recibida y cierre documental

- `.venv/bin/python -B -m unittest discover -s tests -v`: 53/53 OK,
  0,865 s; `.venv/bin/python -B -m pip check`: sin conflictos.
- SQLite URI read-only: integrity/FK, esquema/PK, storage types y conteos.
- Los 10 ZIP/XML: 8.055.768 filas de datos + 10 encabezados,
  18.714.502 inlineString cells, cero fórmulas/hyperlinks. Los 11 hashes,
  manifest y copia de log byte idénticos comprobados; 430,157 s.
- 30 muestras por clave + 20 fronteras (15,511 s): Unicode/NULL preservados;
  ceros iniciales solo prueba sintética, no muestra real. Corpus de escapes
  XML/control conforme.
- MongoDB ping/conteos sin cambios: sin snapshot, no comparación exhaustiva
  de contenido fuente. Windows y corte de energía no probados.
- TemporaryDirectory propios de pruebas cerrados/limpiados por las pruebas;
  `tests/tmp_carga` preexistente conservado para diagnóstico, sin limpieza manual.

Esta unidad de cierre es DOCS-only: README/PLAN actualizados y solo docstring de
`Carga.ejecutar` precisado; ninguna modificación de comportamiento, evidencia,
manifest o log. RED/GREEN no aplican a este cambio pasivo; no se repiten tests,
CLI real, DB writes, servicios, dependencias o Git. Se verifican estructura,
enlaces y coherencia con JSON persistido. Integración ETL ejecutada completa;
publicación y PDF aún pendientes. Outputs/datasets/comentarios privados no van
a Git; evidencia pública pequeña requiere revisión de privacidad.
