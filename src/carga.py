"""Carga de una única corriente de Resultados, sin materializar colecciones.

SQLite mantiene una transacción hasta cerrar y verificar todos los XLSX. Solo
listo.json publica disponibilidad: una carpeta sin él es diagnóstico parcial.
Afinidades por contrato semántico, nunca por el dtype del primer lote.
"""
import hashlib
import json
import logging
import math
import platform
import re
import sqlite3
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4
from zipfile import ZipFile

import numpy as np
import pandas as pd
import pymongo
import xlsxwriter
from defusedxml import ElementTree as ET

from src.transformacion import BOOLEANOS, FECHAS, IDENTIFICADORES, NUMEROS, PRECIOS

CLAVES = {'Listings': ('id',), 'Reviews': ('id',),
          'Calendar': ('listing_id', 'date'), 'ListingAmenities': ('listing_id', 'amenity')}
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
ESCAPE = re.compile(r'_x([0-9A-Fa-f]{4})_')


@dataclass(frozen=True)
class ConfiguracionCarga:
    """Configuración pura; no crea carpetas ni conexiones."""

    salida: Path
    limite_filas: int = 1048575

    def __post_init__(self) -> None:
        if not 1 <= self.limite_filas <= 1048575:
            raise ValueError('Límite XLSX inválido')

    @classmethod
    def nueva(cls, base: Path) -> 'ConfiguracionCarga':
        """Propone un destino único; ejecutar exige mkdir exclusivo."""
        return cls(base / f'ejecucion_{datetime.now():%Y%m%d_%H%M%S}_{uuid4().hex}')


def afinidad(columna: str) -> str:
    """Contrato independiente de los valores y de los lotes vacíos."""
    if columna in BOOLEANOS or columna == 'price_outlier' or columna in {'date_year', 'date_month', 'date_day', 'date_quarter'}:
        return 'INTEGER'
    if columna in PRECIOS or columna in NUMEROS:
        return 'REAL'
    return 'TEXT'


def citar(nombre: str) -> str:
    """Identificador SQL entre comillas; columnas nunca interpoladas sin escape."""
    return '"' + nombre.replace('"', '""') + '"'


def escalar(valor, columna: str):
    """Produce tipos bind nativos; rechaza valores no finitos y claves coercibles."""
    if valor is None or valor is pd.NA or valor is pd.NaT:
        return None
    if isinstance(valor, np.generic):
        valor = valor.item()
    if isinstance(valor, float) and math.isinf(valor):
        raise ValueError('Número no finito')
    if pd.isna(valor):
        return None
    if columna in IDENTIFICADORES:
        if not isinstance(valor, str) or not valor.strip():
            raise ValueError('Identificador no textual o vacío')
        return valor
    tipo = afinidad(columna)
    if tipo == 'TEXT':
        if isinstance(valor, str):
            if columna in FECHAS:
                if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', valor):
                    raise ValueError('Fecha no canónica')
                date.fromisoformat(valor)
            return valor
        if isinstance(valor, (int, float, bool)):
            if isinstance(valor, float) and not math.isfinite(valor):
                raise ValueError('Número no finito')
            return str(valor)
        raise ValueError('Texto escalar inválido')
    if tipo == 'INTEGER':
        if not isinstance(valor, (int, bool)) or not -(2**63) <= int(valor) < 2**63:
            raise ValueError('Entero inválido')
        return int(valor)
    if not isinstance(valor, (int, float)) or not math.isfinite(valor):
        raise ValueError('Número inválido')
    return float(valor)


def hash_archivo(ruta: Path) -> dict:
    """Calcula SHA-256 con memoria acotada, sin incluir contenido en reportes."""
    digest = hashlib.sha256()
    with ruta.open('rb') as archivo:
        for bloque in iter(lambda: archivo.read(1024 * 1024), b''):
            digest.update(bloque)
    return {'archivo': ruta.name, 'bytes': ruta.stat().st_size, 'sha256': digest.hexdigest()}


def decodificar_excel(texto: str) -> str:
    """Un único pase conserva literales protegidos _x005F_xNNNN_."""
    return ESCAPE.sub(lambda m: chr(int(m[1], 16)), texto)


def verificar_xlsx(ruta: Path, columnas: tuple[str, ...], filas: int) -> None:
    """Verifica XML en streaming: filas físicas, encabezados y ausencia de fórmulas.

    Elimina cada fila de su padre; clear() aislado acumularía millones de nodos.
    XlsxWriter constant_memory usa inline strings, no sharedStrings.
    """
    with ZipFile(ruta) as archivo:
        if 'xl/sharedStrings.xml' in archivo.namelist():
            raise ValueError('XLSX no streaming')
        with archivo.open('xl/worksheets/sheet1.xml') as xml:
            pila = []
            cuenta = 0
            for evento, elemento in ET.iterparse(xml, events=('start', 'end')):
                if evento == 'start':
                    pila.append(elemento)
                    continue
                if elemento.tag == NS + 'f' or elemento.tag == NS + 'hyperlink':
                    raise ValueError('Contenido activo XLSX inesperado')
                if elemento.tag == NS + 'row':
                    cuenta += 1
                    if int(elemento.attrib['r']) != cuenta:
                        raise ValueError('Filas XLSX discontinuas')
                    if cuenta == 1:
                        encabezados = tuple(decodificar_excel(''.join(c.itertext()))
                                            for c in elemento.findall(NS + 'c'))
                        if encabezados != columnas:
                            raise ValueError('Encabezados XLSX inconsistentes')
                    if len(pila) > 1:
                        pila[-2].remove(elemento)
                    elemento.clear()
                pila.pop()
            if cuenta != filas + 1:
                raise ValueError('Conteo XLSX inconsistente')


class PartesXlsx:
    """Escritor monotónico de una tabla; no mantiene filas previas en RAM."""

    def __init__(self, nombre, columnas, config):
        self.nombre = nombre
        self.columnas = columnas
        self.config = config
        self.partes = []
        self.libro = None
        self.hoja: Any = None
        self.filas = 0
        self.total = 0

    def abrir(self):
        numero = len(self.partes) + 1
        ruta = self.config.salida / f'{self.nombre}_parte_{numero:03d}.xlsx'
        self.libro = xlsxwriter.Workbook(str(ruta), {
            'constant_memory': True, 'tmpdir': str(self.config.salida / 'tmp'),
            'strings_to_formulas': False, 'strings_to_urls': False,
            'strings_to_numbers': False, 'use_zip64': True})
        self.hoja = self.libro.add_worksheet(self.nombre)
        self.filas = 0
        self.partes.append({'ruta': ruta, 'filas': 0})
        for i, columna in enumerate(self.columnas):
            self.escribir(0, i, columna)

    def escribir(self, fila, columna, valor):
        if isinstance(valor, str):
            if len(valor) > 32767:
                raise ValueError('Texto excede límite XLSX; no se trunca')
            codigo = self.hoja.write_string(fila, columna, valor)
        elif valor is None:
            return  # Clave no nula garantiza una fila física aun con restantes NULL.
        else:
            # Excel solo garantiza 15 dígitos; enteros grandes se conservan en texto.
            if isinstance(valor, int) and abs(valor) >= 10**15:
                codigo = self.hoja.write_string(fila, columna, str(valor))
            else:
                codigo = self.hoja.write_number(fila, columna, valor)
        if codigo != 0:
            raise ValueError('Escritura XLSX rechazada')

    def agregar(self, valores):
        if self.filas == self.config.limite_filas:
            self.cerrar()
            self.abrir()
        for i, valor in enumerate(valores):
            self.escribir(self.filas + 1, i, valor)
        self.filas += 1
        self.total += 1
        self.partes[-1]['filas'] = self.filas

    def cerrar(self):
        if self.libro is not None:
            libro, self.libro = self.libro, None
            libro.close()

    def verificar(self):
        resultado = []
        for parte in self.partes:
            verificar_xlsx(parte['ruta'], self.columnas, parte['filas'])
            resultado.append(hash_archivo(parte['ruta']) | {'filas': parte['filas']})
        return resultado


class Carga:
    """Consume Resultado.tablas exactamente una vez y publica solo éxito verificado.

    Args:
        config: Destino nuevo exclusivo y límite físico de filas por archivo.
        logger: Logger reutilizable sin URI, SQL parametrizado ni valores privados.
    """

    def __init__(self, config: ConfiguracionCarga, logger=None):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)

    def ejecutar(self, resultados, verificar_fuente=None) -> dict:
        """Carga por lotes y conserva archivos diagnósticos ante fallos.

        Confirma SQLite tras los checks y el cierre/verificación de XLSX, antes
        de publicar atómicamente listo.json. Antes del commit intenta rollback;
        un fallo posterior al commit al escribir/renombrar el manifest puede
        dejar SQLite confirmado y XLSX sin listo.json: no están publicados.
        No sobrescribe destinos ni promete recuperación automática.
        """
        inicio = time.perf_counter()
        db = None
        escritores = {}
        columnas_tablas = {}
        inserciones = {}
        fuente = iter(resultados)
        exitoso = False
        try:
            self.config.salida.mkdir(parents=True, exist_ok=False)
            (self.config.salida / 'tmp').mkdir()
            self.logger.info('Carga iniciada; destino=%s', self.config.salida.name)
            db = sqlite3.connect(self.config.salida / 'airbnb.sqlite')
            db.execute('PRAGMA foreign_keys = ON')
            if db.execute('PRAGMA foreign_keys').fetchone() != (1,):
                raise ValueError('Claves foráneas no habilitadas')
            db.execute('BEGIN')
            # Listings se crea antes del puente y de los hijos, incluso si un
            # Resultado entrega el mapping en orden inverso.
            ultima = -1
            for resultado in fuente:
                orden = {'Listings': 0, 'Reviews': 1, 'Calendar': 2}
                if resultado.coleccion not in orden or orden[resultado.coleccion] < ultima:
                    raise ValueError('Orden de colecciones inválido')
                ultima = orden[resultado.coleccion]
                esperadas = {resultado.coleccion}
                if resultado.coleccion == 'Listings':
                    esperadas.add('ListingAmenities')
                if not set(resultado.tablas).issubset(esperadas) or resultado.coleccion not in resultado.tablas:
                    raise ValueError('Tablas incompatibles con colección')
                for nombre in sorted(resultado.tablas, key=lambda n: n != 'Listings'):
                    frame = resultado.tablas[nombre]
                    columnas = tuple(frame.columns)
                    if (not frame.columns.is_unique or not all(isinstance(c, str) and c and '\x00' not in c for c in columnas)
                            or len({c.casefold() for c in columnas}) != len(columnas)
                            or len(columnas) > min(16384, db.getlimit(sqlite3.SQLITE_LIMIT_COLUMN)) or not set(CLAVES[nombre]).issubset(columnas)):
                        raise ValueError('Esquema inválido')
                    if nombre not in escritores:
                        if nombre != 'Listings' and 'Listings' not in escritores:
                            raise ValueError('Listings requerido antes de hijos')
                        definiciones = [f'{citar(c)} {afinidad(c)}' +
                                        (' NOT NULL' if c in CLAVES[nombre] else '') for c in columnas]
                        definiciones.append('PRIMARY KEY (' + ','.join(map(citar, CLAVES[nombre])) + ')')
                        if nombre != 'Listings':
                            if 'listing_id' not in columnas:
                                raise ValueError('Clave foránea ausente')
                            definiciones.append('FOREIGN KEY (listing_id) REFERENCES Listings(id)')
                        db.execute(f'CREATE TABLE {citar(nombre)} ({",".join(definiciones)})')
                        columnas_tablas[nombre] = columnas
                        inserciones[nombre] = ''.join(('INSERT INTO ', citar(nombre),
                                                       ' (', ','.join(map(citar, columnas)), ') VALUES (',
                                                       ','.join('?' for _ in columnas), ')'))
                        escritores[nombre] = PartesXlsx(nombre, columnas, self.config)
                        escritores[nombre].abrir()
                    elif columnas != columnas_tablas[nombre]:
                        raise ValueError('Deriva de esquema entre lotes')
                    # Solo un lote escalarizado. Sin deepcopy, Calendar completo ni
                    # listas de colecciones; itertuples evita numpy bind no nativo.
                    valores = [tuple(escalar(v, c) for c, v in zip(columnas, fila, strict=True))
                               for fila in frame.itertuples(index=False, name=None)]
                    indices_clave = [columnas.index(c) for c in CLAVES[nombre]]
                    for fila in valores:
                        if any(not isinstance(v, str) or not v.strip()
                               for v in (fila[i] for i in indices_clave)):
                            raise ValueError('Clave vacía o no textual')
                        if any(isinstance(v, str) and len(v) > 32767 for v in fila):
                            raise ValueError('Texto excede límite XLSX')
                    # nombre pertenece a CLAVES (allowlist); todos los valores se enlazan.
                    db.executemany(inserciones[nombre], valores)
                    for fila in valores:
                        escritores[nombre].agregar(fila)
                    self.logger.info('Carga %s: lote=%d acumulado=%d', nombre, len(valores), escritores[nombre].total)
            if not escritores:
                raise ValueError('Corriente vacía')
            # Cerrar upstream antes de publicar, incluso si close() falla.
            if hasattr(fuente, 'close'):
                fuente.close()
            for escritor in escritores.values():
                escritor.cerrar()
            integridad = db.execute('PRAGMA integrity_check').fetchall()
            if integridad != [('ok',)] or db.execute('PRAGMA foreign_key_check').fetchone() is not None:
                raise ValueError('Integridad SQLite fallida')
            tablas = {}
            for nombre, escritor in escritores.items():
                filas = db.execute({
                    'Listings': 'SELECT count(*) FROM Listings',
                    'Reviews': 'SELECT count(*) FROM Reviews',
                    'Calendar': 'SELECT count(*) FROM Calendar',
                    'ListingAmenities': 'SELECT count(*) FROM ListingAmenities',
                }[nombre]).fetchone()[0]
                if filas != escritor.total:
                    raise ValueError('Conteo SQLite inconsistente')
                partes = escritor.verificar()
                if sum(p['filas'] for p in partes) != filas:
                    raise ValueError('Conteo entre formatos inconsistente')
                tablas[nombre] = {'filas': filas, 'columnas': list(escritor.columnas),
                                  'afinidades': [afinidad(c) for c in escritor.columnas], 'xlsx': partes}
            fuente_verificada = verificar_fuente({n: t['filas'] for n, t in tablas.items()}) \
                if verificar_fuente is not None else None
            db.commit()
            db.close()
            db = None
            informe = {'estado': 'listo', 'tablas': tablas,
                       'sqlite': hash_archivo(self.config.salida / 'airbnb.sqlite'),
                       'invariantes': {'integrity_check': True, 'foreign_key_check': True,
                                       'conteos_sqlite_xlsx': True, 'sin_formulas': True},
                       'versiones': {'python': platform.python_version(), 'sqlite': sqlite3.sqlite_version,
                                     'pandas': pd.__version__, 'pymongo': pymongo.version,
                                     'xlsxwriter': xlsxwriter.__version__},
                       'duracion_segundos': time.perf_counter() - inicio,
                       'fuente': fuente_verificada,
                       'precision': 'Identificadores TEXT exactos; REAL conserva float de origen, '
                                    'Excel no garantiza exactitud decimal de todos los floats.'}
            temporal = self.config.salida / 'listo.json.pendiente'
            destino = self.config.salida / 'listo.json'
            with temporal.open('x', encoding='utf-8') as archivo:
                json.dump(informe, archivo, ensure_ascii=False, allow_nan=False, indent=2)
            # Directorio reservado mediante mkdir exclusivo y SINGLE WRITER.
            # JSON completo y cerrado antes de rename atómico en el mismo FS.
            if destino.exists() or destino.is_symlink():
                raise FileExistsError('Manifest existente; no se reemplaza')
            temporal.rename(destino)
            exitoso = True
            self.logger.info('Carga verificada y lista; filas=%d duración=%.3fs',
                             sum(t['filas'] for t in tablas.values()), informe['duracion_segundos'])
            return informe
        except Exception as exc:
            self.logger.error('Carga fallida (%s); archivos parciales conservados', type(exc).__name__)
            raise
        finally:
            # Nunca enmascarar el error original con fallos de cierre. Los
            # errores de cierre se reportan, y solo el camino verificado publica.
            if not exitoso:
                acciones = []
                if db is not None:
                    acciones.extend([db.rollback, db.close])
                if hasattr(fuente, 'close'):
                    acciones.append(fuente.close)
                acciones.extend(e.cerrar for e in escritores.values())
                for cerrar in acciones:
                    try:
                        cerrar()
                    except Exception as exc:
                        self.logger.error('Cierre diagnóstico fallido (%s)', type(exc).__name__)
