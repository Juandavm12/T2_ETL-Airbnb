# Airbnb ETL — extracción, EDA, transformación y carga

Importa CSV a MongoDB local y extrae `Listings`, `Reviews` y `Calendar`
a DataFrames pandas por lotes. El EDA recorre las tres colecciones completas,
con gráficos reales embebidos y evidencia JSON. La clase `Transformacion`
produce tablas limpias por lote y auditoría JSON; `Carga` las inserta en SQLite
nuevo y exporta XLSX particionados. La integración Extracción → Transformación →
Carga se ejecutó completa. Repositorio público:
[T2_ETL-Airbnb](https://github.com/Juandavm12/T2_ETL-Airbnb), rama `main`.
Estado de entrega: pipeline completo ejecutado; informe pendiente de exportación a PDF.

## Objetivo

Aplicar un proceso automatizado de extracción, transformación y carga (ETL)
a los datasets de Airbnb de Bogotá, Distrito Capital, Colombia, usando MongoDB
local como fuente, con EDA, logs y documentación del flujo de trabajo.

## Integrantes y responsabilidades asignadas

Reparto equitativo autorizado para organizar el trabajo; esta asignación no
atribuye contribuciones históricas individuales.

| Integrante | Responsabilidades asignadas |
| --- | --- |
| Juan David Velasquez Murillo | Extracción desde MongoDB, validación de fuentes y reproducibilidad. |
| Paula Andrea Calderon Quintero | EDA, visualizaciones e interpretación de hallazgos. |
| Jose David Vasquez Diaz | Transformación, carga SQLite/XLSX y validación de resultados. |
| Todos los integrantes | Pruebas, logs, documentación e informe PDF de entrega. |

## Preparación (Linux / Windows)

Requisitos: **Python 3.14.7** (versión probada), pip y MongoDB local para
el flujo real. No se afirma compatibilidad con versiones menores de Python.
La instalación limpia en un venv aislado del mismo equipo Linux fue verificada:
instalación, `pip check`, 53 pruebas y smoke de imports runtime/EDA correctos.
No se ejecutó nuevamente el notebook ni el ETL completo en ese entorno.
También se validó siguiendo este README en **otro equipo**: Fedora 44 (WSL) y
Windows 11 Pro (build 26200, Windows PowerShell 5.1), ambos con Python 3.14.7:
instalación, `pip check` y 53 pruebas correctos. En esos equipos no se ejecutó
importación, ETL, carga ni notebook (sin MongoDB ni datasets).
Todos los comandos siguientes se ejecutan desde la raíz del proyecto.

Para un equipo nuevo, clona el repositorio y entra en su raíz:

```bash
git clone https://github.com/Juandavm12/T2_ETL-Airbnb.git
cd T2_ETL-Airbnb
```

Los siguientes comandos de creación/instalación se ejecutan desde esa raíz.

Desde esta carpeta, en Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --no-cache-dir -r requirements.txt
.venv/bin/python -B -m pip check
.venv/bin/python -B -m unittest discover -s tests -v
```

En Windows PowerShell. Requiere Python real con el lanzador `py`; el alias
`python.exe` de Microsoft Store no basta. Si `py -3.14 --version` falla,
instala la versión probada para tu usuario y abre una terminal nueva:

```powershell
winget install --id Python.Python.3.14 --version 3.14.7 --scope user --exact
```

Luego, desde la raíz del proyecto:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-cache-dir -r requirements.txt
.\.venv\Scripts\python.exe -B -m pip check
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

`requirements.txt` fija **11 dependencias directas** con versiones exactas
verificadas en el entorno original y en la instalación limpia: pandas, pymongo,
numpy, XlsxWriter, defusedxml (validación XML), Matplotlib, IPython (display del
notebook), JupyterLab, ipykernel, nbclient y nbformat. Las pruebas usan mocks,
no necesitan MongoDB. pip resuelve las transitivas: este archivo no congela
el grafo completo y las resoluciones futuras pueden variar.

[requirements-entorno-verificado.txt](requirements-entorno-verificado.txt)
conserva byte a byte los **102 pins** del `pip freeze` histórico, incluidas
transitivas; es un snapshot de referencia, no el archivo de instalación habitual.
La instalación limpia no reproduce exactamente ese snapshot: se observaron
json5 0.16.0 y pycparser 3.1 frente a 0.15.0 y 3.0 históricos, sin conflictos.
El snapshot es de Linux: en Windows pip instala además colorama y pywinpty, y
no instala pexpect ni ptyprocess (dependencias según sistema operativo).

[.gitattributes](.gitattributes) excluye `evidencias/` y `logs/` de la conversión
de fin de línea, para que un clon en Windows con `core.autocrlf=true` conserve
los bytes y los SHA256 registrados en las evidencias JSON.

## Datos y ejecución

Conserva los CSV originales fuera del proyecto: por defecto se buscan
`../Datasets/listings.csv`, `reviews.csv` y `calendar.csv`. Cada uno puede
ser `.csv.gz`; si existen ambas variantes se prefiere CSV. Para el repositorio
independiente publicado, obtén los datos originales del
material del taller y usa `--ruta` hacia esa carpeta. No se copian ni se
incluyen los datasets en esta entrega; no se inventa una URL de descarga.

Con MongoDB local activo y una base vacía para importar:

```bash
.venv/bin/python main.py importar --ruta ../Datasets --base airbnb --batch 10000
.venv/bin/python main.py extraer --base airbnb --batch 10000
.venv/bin/python main.py cargar --base airbnb --batch 10000
```

`cargar` integra extracción y transformación y crea una salida nueva única en
`salidas/`; no reutilices una salida existente. Consulta los contratos y fallos
más abajo antes de ejecutar.

En Windows sustituye el intérprete por `.\.venv\Scripts\python.exe`.
La URI predeterminada es `mongodb://localhost:27017`; se admite `--uri`
o la variable `MONGO_URI`. No escribas credenciales en comandos compartidos.
Los logs nunca incluyen URI, documentos ni mensajes privados de excepciones.
Un archivo nuevo en `logs/` por ejecución registra timestamp e INFO/WARNING/ERROR.

## Contratos y recuperación

- Preflight verifica las **tres colecciones vacías** y los tres archivos
  antes de insertar. No borra, reemplaza ni reanuda colecciones.
- CSV se lee por registros, respeta multilínea/gzip y conserva strings,
  ceros iniciales, `NA` y vacíos. No hay inferencia numérica ni limpieza.
  Política fail-fast: `strict=True` rechaza errores de formato CSV, como
  comillas sin cerrar, registra ERROR y no declara éxito. Si falla el primer
  registro no inserta nada; si ya hubo lotes confirmados puede quedar parcial.
- Cada lote exige `acknowledged` y tantos `inserted_ids` como filas;
  luego compara conteo total. No se declara éxito solo por count final.
- `ordered=True` puede dejar una importación parcial; preflight no es
  transacción ni protección contra escritores concurrentes. Usa una base
  exclusiva, sin otros importadores activos.
- Ante fallo, detén el flujo y revisa logs y conteos con un administrador.
  Recuperación segura: elige una **nueva base vacía** con `--base` y repite
  los tres archivos completos. Conserva la base parcial para inspección;
  cualquier limpieza manual queda fuera de este programa.
- CLI extraer rechaza fuentes ausentes o vacías. La API permite DataFrame
  vacío para consultas vacías; el consumidor debe cerrar el generador si
  abandona una iteración (`lotes.close()`), además del contexto de conexión.

`Extraccion.iterar(nombre, batch)` entrega DataFrames acotados; la CLI
los consume y cuenta sin guardarlos. `Extraccion.completa()` y
`--completa` son opcionales, advierten del riesgo de RAM. Calendar tiene
7.003.255 filas: conteos del CSV y de MongoDB coinciden en la validación real.
Con 5,7 GiB de RAM total, usa lotes: no intentes materializar Calendar.
El conteo se consulta en MongoDB, no descargando documentos completos.

## Estado y fuentes

Estado actual: **53 pruebas OK y `pip check` sin conflictos**, verificación
independiente conforme. Históricamente etapa 1/EDA tuvieron 17 pruebas y
Transformación 29, luego 32 tras correcciones. Notebook ejecutado desde MongoDB:
8 celdas de código, 7 PNG, cero errores; 409,74 s observados.
Carga SQLite/XLSX e integración completa verificadas.
Repositorio público [T2_ETL-Airbnb](https://github.com/Juandavm12/T2_ETL-Airbnb)
publicado en `main`. Integrantes y responsabilidades asignadas se detallan arriba.

## Reproducir el EDA sin reimportar

Desde esta carpeta, con la base `airbnb` ya poblada y sin escritores concurrentes:

```bash
export JUPYTER_CONFIG_DIR="$PWD/.venv/eda_cache/config"
export JUPYTER_DATA_DIR="$PWD/.venv/share/jupyter"
export JUPYTER_RUNTIME_DIR="$PWD/.venv/eda_cache/runtime"
export IPYTHONDIR="$PWD/.venv/eda_cache/ipython"
.venv/bin/python -m ipykernel install --prefix "$PWD/.venv" --name etl-airbnb --display-name 'Python (venv etl_airbnb)'
.venv/bin/python -m jupyterlab --no-browser --ip=127.0.0.1
```

Abre `notebooks/exploracion_airbnb.ipynb`, selecciona **Python (venv etl_airbnb)**
y ejecuta todas las celdas. La primera verifica el intérprete del proyecto;
no basta un alias global. En PowerShell usa `.\.venv\Scripts\python.exe`
y variables `$env:JUPYTER_CONFIG_DIR`, `$env:JUPYTER_DATA_DIR`,
`$env:JUPYTER_RUNTIME_DIR`, `$env:IPYTHONDIR` con las mismas rutas locales;
`--prefix` debe apuntar a `.venv`. Windows no fue ejecutado en esta validación.

Alternativa batch (tras registrar el kernel local), sin tolerar errores:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
import nbformat
from nbclient import NotebookClient
root = Path.cwd()
path = root / 'notebooks/exploracion_airbnb.ipynb'
nb = nbformat.read(path, as_version=4)
NotebookClient(nb, timeout=900, kernel_name='etl-airbnb', allow_errors=False,
               resources={'metadata': {'path': str(root / 'notebooks')}}).execute()
nbformat.validate(nb)
nbformat.write(nb, path)
PY
```

La última celda sobrescribe `evidencias/resumen_eda.json`: conserva una copia
provisional bajo `.venv/eda_cache` si necesitas comparar una ejecución anterior.
Se leen solo colecciones MongoDB, no CSV; lotes de 10.000, Listings materializado,
Reviews/Calendar en streaming. No se deduplican ni borran documentos.

### Hallazgos y controles

- Claves de negocio sin duplicados: `id`, `id`, `(listing_id,date)`;
  `_id` artificial no participa de la prueba.
- Precio: 195 faltantes; mediana 161.460, media 446.026,55 y máximo
  448.176.567 unidades nominales. `$` no confirma COP/USD.
- IQR: precio 1.410, minimum_nights 4.053 y availability_365 1.129 atípicos;
  no se descartan automáticamente. Minimum_nights tiene 4 faltantes.
- Reviews: 2010-10-06–2026-06-21; Calendar: 2026-06-21–2027-06-21.
  Meses extremos pueden ser parciales; `available=f` no prueba reserva.
- Amenities: 19.187 listas JSON válidas; 12 columnas Listings totalmente vacías.

Tablas completas, conversiones auditadas, correlaciones con N por par y matriz
propuesta de transformación están en el notebook y el JSON. Correlación no
implica causa; Calendar es horizonte de captura, no disponibilidad actual.
Conteos se verifican, pero no hay snapshot transaccional. Los tiempos no son
garantía de rendimiento ni una medición de memoria del servidor.

## Transformación formal — comando sin persistencia

Fuente: guía del taller, página 4; decisiones basadas en
[evidencia EDA completa](evidencias/resumen_eda.json). Desde esta carpeta:

```bash
.venv/bin/python -B main.py transformar --base airbnb --batch 10000
.venv/bin/python -B -m unittest discover -s tests -v
.venv/bin/python -B -m pip check
```

La CLI imprime únicamente un JSON estricto pequeño con conteos y auditoría,
no documentos ni textos privados. No persiste tablas; consumirlas no equivale
 a cargarlas. Rechaza `--completa`. Reutiliza `Extraccion`, logger único `.log`
y entorno existente, sin nuevas dependencias.

### Contrato consumido por Carga

`Transformacion.lote(nombre, dataframe)` no modifica entrada ni MongoDB.
Devuelve `Resultado.tablas` y `Resultado.auditoria`. `iterar(extraccion, batch)`
entrega esos resultados en streaming: usar un consumidor por lote y cerrar el
 generador si se abandona; no hacer `list()` ni concat global para Calendar/Reviews.
Memoria proporcional al lote y su puente amenities; no retiene millones de claves.
Listings también se procesa por lotes aunque sus 19.187 filas sean materializables.

- Preflight **global antes del primer lote**: agregados `duplicados` del EDA,
  `allowDiskUse=True`, timeout 300 s, sin `$out`/`$merge`. Cualquier duplicado
  global, incluso exacto, rechaza explícitamente; no hay dedup silencioso entre lotes.
  Timeout/error propaga, nunca produce cero falso.
- IDs strings exactos, incluidos ceros iniciales y espacios, **sin trim ni coerción**.
  Falta, whitespace, marcadores y tipos no-string rechazan, sin cambiar valores.
  Calendar exige fecha clave canónica válida sin espacios: no convierte dos claves
  raw distintas a una sola ni errores de clave a NULL. Su fecha inválida rechaza;
  las demás fechas inválidas pasan a nulo auditado.
- Dentro de un lote, excluye `_id` y elimina solo filas completas idénticas antes
  de limpiar. Una clave repetida con contenido distinto rechaza; nunca first-wins.
  La API pura aislada no promete unicidad entre lotes: usar `iterar` con preflight.
- Strings vacíos/whitespace pasan a nulo, sin descartar filas. Marcadores
  `NA/N/A/NULL/NAN/NONE` solo en columnas declaradas numéricas, fechas, flags y
  `host_verifications`; nombres, comentarios y texto libre conservan marcadores
  legítimos y contenido no vacío exacto. Sin imputación ni trim general del texto.
- Conversiones separan válidos, faltantes, inválidos y no finitos. Precios aceptan
  `$` y comas de miles, no comas decimales. Numéricos nullable `Float64`; formatos
  inválidos pasan a nulo auditado. No se inventa `price` en Calendar.
- Fechas estrictas `YYYY-MM-DD`; `date_year/month/day/quarter` nullable `Int64`.
  Flags `t/f` a boolean nullable; `f` **no prueba reserva**. Auditoría de dominios
  señala precios no positivos, ingresos negativos, noches no positivas/fraccionarias
  y availability_365 fuera de 0–365 o fraccionaria; conserva valores para revisión.
- Rangos fijos **solo Listings.price**, unidades nominales, moneda no confirmada:
  Q1 `p <= 110000`; Q2 `110000 < p <= 161460`; Q3
  `161460 < p <= 230346.375`; Q4 `p > 230346.375`. Precio faltante/ inválido:
  categoría nula. No implica que un precio negativo sea aceptable: dominio lo señala.
  `price_outlier` usa cercas estrictas `-70519.5625` y `410865.9375`; frontera
  no atípica, ausencia flag nulo. Se preservan los 1.410 atípicos, sin winsorizar.
- Amenities JSON de strings: puente `ListingAmenities(listing_id, amenity)`,
  dedup intra-lista exacto, orden lexical determinista; originales conservados como
  JSON escalar. Lista inválida auditada, sin inventar amenities. Estructuras list/dict
  en otras columnas se serializan a JSON estricto, no objetos Python para SQLite.
  Host permanece plano: no se inventa dimensión ni dedup host sin reglas de negocio.
- Las **12 columnas completamente vacías** documentadas en el EDA se conservan
  nullable: preservan esquema/procedencia sin inventar información ni borrar columnas.
- INFO registra tareas y filas antes/después, WARNING calidad y ausencia de snapshot,
  ERROR solo clase de excepción, nunca URI, documentos, claves o textos privados.

### Evidencia real completa

[resumen_transformacion.json](evidencias/resumen_transformacion.json) procede de
la salida CLI real parseada con JSON estricto; [transformacion_real.txt](evidencias/transformacion_real.txt)
es copia byte a byte del log indicado en ese JSON, sin entradas añadidas.

| Tabla fuente | Antes = después = conteos MongoDB antes/después | Lotes |
| --- | ---: | ---: |
| Listings | 19.187 | 2 |
| Reviews | 527.731 | 53 |
| Calendar | 7.003.255 | 701 |

Puente: **505.595 filas**, 19.187 listas válidas, cero inválidas. Precio:
18.992 válidos, 195 faltantes, cero inválidos/no finitos y 1.410 atípicos preservados.
Cero duplicados globales/exactos; cero errores de conversión y dominios señalados.
Tiempo final observado: **199,99 s**, incluido preflight; no garantía de rendimiento
ni medición de RAM. Invariantes verificadas: cada conversión suma las filas y los
conteos de fuente/extracción/transformación coinciden. **Sin snapshot**: exige ausencia
 de escritores concurrentes; igualdad de conteos no demuestra contenido inalterado.
La validación de claves ocurre por lote después del preflight de unicidad: la API
puede entregar resultados previos antes de fallar por una clave inválida posterior;
Carga aplica la semántica de confirmación/publicación descrita abajo, sin asumir
éxito anticipado. En aquella unidad de Transformación no se ejecutaron Carga,
exportación, informe, notebook ni publicación Git; Carga se resolvió después.

## Carga SQLite/XLSX — integración completa

Fuente: guía del taller, página 5. Para reproducir (no necesario para revisar la
evidencia existente), con MongoDB poblado y sin escritores concurrentes:

```bash
.venv/bin/python -B main.py cargar --base airbnb --batch 10000
```

Sin `--salida`, crea una carpeta única nueva en `salidas/`. Opcionalmente usa
`--salida salidas/reproduccion_nueva` **solo si ese directorio no existe**;
reserva exclusiva, sin sobrescribir ni reanudar. `--completa` se rechaza.
Consume una sola corriente por lotes; no materializa Calendar/Reviews.

### Confirmación, disponibilidad y fallos

SQLite mantiene una transacción hasta cerrar/verificar los XLSX, comprobar
integridad, claves foráneas y conteos y verificar la fuente. **El commit SQLite
ocurre después de esos checks y antes de escribir/publicar el manifest**.
`listo.json` completo se publica mediante rename atómico en el mismo filesystem;
es el marcador de disponibilidad, no una transacción conjunta SQLite/XLSX/JSON.
Antes del commit, un fallo intenta rollback. Después del commit, un fallo de
dump/rename puede dejar SQLite confirmado y XLSX sin `listo.json`: no publicados.
Se conservan parciales diagnósticos, sin sobrescritura ni recuperación automática.
Un JSON malformado no autoriza declarar disponibilidad; comprobar manifest y
artefactos. Fallos de cierre impiden publicar y se registran sin ocultar el error.
No se probó corte de energía ni se promete durabilidad frente a él.

PK: Listings/Reviews `id`, Calendar `(listing_id,date)`, puente
`(listing_id,amenity)`; hijos referencian Listings. IDs TEXT exactos y NULL
preservados; INTEGER/REAL según contrato, no inferencia del primer lote.
Precios siguen en unidades nominales, moneda no confirmada; REAL conserva float
original y Excel no garantiza exactitud decimal para todos los floats.
Strings se escriben como texto, no fórmulas ni URLs activas; texto >32.767
caracteres falla, nunca se trunca. Identificadores SQL con NUL se rechazan.

### Evidencia persistida y verificación independiente

[validacion_carga.json](evidencias/validacion_carga.json) y
[carga_real.txt](evidencias/carga_real.txt) conservan la corrida histórica real,
no una nueva ejecución del verificador. También se incluye una
[copia histórica exacta en logs/](logs/etl_20261007_223144_ejemplo.txt),
revisada sin URI, credenciales ni documentos; el logger no cambia. Destino relativo:
`salidas/ejecucion_20261007_223144_602d1ed1c8cc4df299affc7375e7af17`.

| Tabla | Filas | XLSX |
| --- | ---: | ---: |
| Listings | 19.187 | 1 |
| Reviews | 527.731 | 1 |
| Calendar | 7.003.255 | 7 |
| ListingAmenities | 505.595 | 1 |

Total **8.055.768 filas**, SQLite **908.255.232 bytes**, 10 XLSX;
SQLite + XLSX **1.225.231.757 bytes**. Calendar conserva todas las filas:
6 partes de 1.048.575 y una de 711.805, más encabezado en cada archivo.
CLI histórica: **1.108,398 s**; Carga: **1.105,545 s**; RSS máximo cliente
**392.596 KiB**, no memoria MongoDB ni garantía de rendimiento.

Verificación independiente read-only reportada: 53 pruebas OK (0,865 s),
`pip check` conforme; SQLite URI read-only, integrity/FK, esquema/PK, tipos de
almacenamiento y conteos. Los 10 ZIP/XML contienen 8.055.768 filas de datos +
10 encabezados y 18.714.502 celdas inlineString, sin fórmulas ni hyperlinks.
Todos los 11 hashes, manifest y log byte a byte comprobados (430,157 s).
30 muestras por clave y 20 fronteras de partición (15,511 s) conservan Unicode
y NULL; ceros iniciales solo corroborados con pruebas, no muestra real.
Corpus de escapes XML/control pasa. MongoDB ping/conteos sin cambios; **sin
snapshot ni comparación exhaustiva del contenido fuente**. Windows no probado.

`salidas/` y logs operativos están ignorados; para repositorio público conservar
solo evidencia pequeña JSON/log revisada sin datos privados. Datasets, SQLite,
XLSX y comentarios privados no deben incorporarse a Git. No se modifican las
evidencias existentes durante este cierre documental.

## Evidencia de integración real

Base `airbnb`; importación y extracción CLI con `--batch 10000`.
La extracción recorrió todos los documentos por lotes sin conservar los
DataFrames; no se utilizó `--completa`.

| Colección | Filas CSV = documentos MongoDB = extraídos | Columnas CSV |
| --- | ---: | ---: |
| Listings | 19.187 | 90 |
| Reviews | 527.731 | 6 |
| Calendar | 7.003.255 | 5 |

| Ejecución | Tiempo (s) | Máximo RSS (KiB) | Salida | Log versionable |
| --- | ---: | ---: | ---: | --- |
| Importación | 110,96 | 265.844 | 0 | [importacion_real.txt](evidencias/importacion_real.txt) |
| Extracción | 37,01 | 295.600 | 0 | [extraccion_real.txt](evidencias/extraccion_real.txt) |
| Reimportación rechazada | 1,18 | 86.540 | 1 | [reimportacion_rechazada.txt](evidencias/reimportacion_rechazada.txt) |

**RSS mide el cliente Python**, no la memoria total de MongoDB ni del sistema.
Los tiempos son observaciones de esta ejecución, no garantías de rendimiento.
Los `.txt` son copias exactas de los logs originales, sin entradas añadidas;
las métricas de tiempo/RSS provienen de archivos separados de medición externa.

[validacion_mongodb.json](evidencias/validacion_mongodb.json) conserva el
resultado original, hashes SHA256, versiones, checks y procedencia de logs.
Ruta de revisión:

- Conteos completos coinciden para las tres colecciones.
- Comparación de contenido: primeros 100 documentos y último de cada colección,
  en todos los campos CSV; los valores muestreados siguen siendo strings.
- SHA256 de las tres fuentes sin cambios tras el flujo.
- Reimportación sobre la base poblada: salida 1 por preflight; conteos
  posteriores 19.187 / 527.731 / 7.003.255, sin nuevos documentos según
  verificación posterior documentada en la evidencia de medición externa.

La comparación **no verifica el contenido de todos los documentos**. El
recorrido completo de extracción y los conteos no sustituyen esa comparación.

Referencias oficiales: [insert_many y orden de inserción](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/crud/insert/)
y [lectura pandas](https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html).
Aquí se usa `csv.DictReader` para conservar strings sin inferencia; pandas
se utiliza para construir los DataFrames de extracción.

## Notas del equipo original — no reinstalar

La integración real se verificó en Ubuntu 24.04.4 amd64 bajo WSL,
Python 3.14.7 y MongoDB 8.0.32 local. El entorno `.venv` original conserva
pandas 3.0.6, pymongo 4.18.2 y XlsxWriter 3.2.9; 53 pruebas y `pip check`
fueron verificados allí. Para revisar ese entorno existente, sin reinstalar:

```bash
.venv/bin/python -B -m unittest discover -s tests -v
.venv/bin/python -B -m pip check
```

En ese equipo, `airbnb` ya está cargada: usa `extraer`, `transformar` o `cargar`.
Reimportar sobre esa base se rechaza para evitar duplicados.

### MongoDB local en WSL — configuración histórica

Instalación realizada con autorización: repositorio APT oficial MongoDB 8.0
para Ubuntu **Noble 24.04 amd64**, paquete `mongodb-org` **8.0.32**,
`mongosh` **2.13.0** y database-tools **100.19.1**. Para reproducir la
instalación en otro equipo, sigue la
[guía oficial para Ubuntu de MongoDB 8.0](https://www.mongodb.com/docs/v8.0/tutorial/install-mongodb-on-ubuntu/),
que soporta Noble: importa la clave, agrega el repositorio APT 8.0 y fija
la versión 8.0.32 de los paquetes según sus instrucciones. Aquí ya se hizo;
no es necesario reinstalar ni modificar la configuración del sistema.

| Elemento | Estado local |
| --- | --- |
| Clave APT | `/usr/share/keyrings/mongodb-server-8.0.gpg` |
| Fuente APT | `/etc/apt/sources.list.d/mongodb-org-8.0.list` |
| Configuración | `/etc/mongod.conf`, configuración del paquete intacta |
| Escucha | `127.0.0.1:27017` |
| Datos / log del servidor | `/var/lib/mongodb` / `/var/log/mongodb/mongod.log` |
| RAM / caché WiredTiger | 5,7 GiB / 0,5 GB (opción de arranque) |

WSL usa init de Ubuntu, **sin systemd activo**; no se cambió systemd ni se
configuró autostart. Tras reiniciar WSL puede requerirse arranque manual.
Primero comprueba disponibilidad:

```bash
mongosh --quiet --eval 'db.adminCommand({ping: 1})'
```

Resultado observado: `ok: 1`. Si responde, **no arranques otra instancia**.
Solo cuando no haya proceso `mongod` activo (un ping fallido por sí solo
no demuestra esto), el arranque manual usado fue:

```bash
sudo -u mongodb /usr/bin/mongod --config /etc/mongod.conf --fork --wiredTigerCacheSizeGB 0.5
```

Vuelve a comprobar el ping. No reinicies un servidor ya activo para repetir
esta evidencia. Sin autenticación: **solo uso académico local**, nunca
exponer el puerto a la red.
