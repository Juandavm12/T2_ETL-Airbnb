"""Carga SQLite/XLSX: pruebas de comportamiento sin MongoDB."""
import logging
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4
from zipfile import ZipFile

import pandas as pd
from defusedxml import ElementTree as ET

from src import carga as carga_modulo
from src.carga import Carga, ConfiguracionCarga, decodificar_excel
from src.transformacion import Resultado

ROOT = Path(__file__).resolve().parent


def resultado(nombre, filas):
    return Resultado(nombre, {nombre: pd.DataFrame(filas)}, {})


class TestCarga(unittest.TestCase):
    def setUp(self):
        self.temporal = TemporaryDirectory(dir=ROOT, prefix='tmp_carga_nueva_')
        self.addCleanup(self.temporal.cleanup)

    def directorio(self):
        return Path(self.temporal.name) / uuid4().hex

    def cargar(self, resultados, limite=1048575):
        destino = self.directorio()
        carga = Carga(ConfiguracionCarga(destino, limite))
        return destino, carga.ejecutar(iter(resultados))

    def test_tipos_exactos_y_partes(self):
        destino, informe = self.cargar([
            resultado('Listings', [{'id': '0001', 'host_id': '0002', 'price': None,
                                    'name': '=1+1', 'host_is_superhost': True}]),
            resultado('Listings', [{'id': '0003', 'host_id': '0004', 'price': 2.5,
                                    'name': 'https://example.org', 'host_is_superhost': None}]),
            resultado('Calendar', [{'listing_id': '0001', 'date': f'2026-01-0{i}',
                                     'price': float(i)} for i in range(1, 6)])], 2)
        with closing(sqlite3.connect(destino / 'airbnb.sqlite')) as db:
            self.assertEqual(db.execute('SELECT id, typeof(id), price, typeof(price), '
                                        'host_is_superhost FROM Listings ORDER BY id').fetchall(),
                             [('0001', 'text', None, 'null', 1), ('0003', 'text', 2.5, 'real', None)])
        self.assertEqual(informe['tablas']['Calendar']['filas'], 5)
        self.assertEqual([p['filas'] for p in informe['tablas']['Calendar']['xlsx']], [2, 2, 1])
        self.assertTrue((destino / 'listo.json').is_file())

    def test_duplicado_y_huerfano_rollback(self):
        for resultados in ([resultado('Listings', [{'id': '1'}, {'id': '1'}])],
                           [resultado('Listings', [{'id': '1'}]),
                            resultado('Reviews', [{'id': 'r', 'listing_id': '2'}])]):
            destino = self.directorio()
            with self.assertRaises(sqlite3.IntegrityError):
                Carga(ConfiguracionCarga(destino)).ejecutar(iter(resultados))
            self.assertFalse((destino / 'listo.json').exists())
            with closing(sqlite3.connect(destino / 'airbnb.sqlite')) as db:
                self.assertEqual(db.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0], 0)

    def test_no_sobrescribe(self):
        destino = self.directorio()
        destino.mkdir(parents=True)
        with self.assertRaises(FileExistsError):
            Carga(ConfiguracionCarga(destino)).ejecutar(iter([]))

    def test_rechaza_largo_infinito_esquema_y_claves(self):
        casos = [ [{'id': '1', 'name': 'x' * 32768}],
                  [{'id': '1', 'price': float('inf')}], [{'id': 1}], [{'id': ''}] ]
        for filas in casos:
            with self.assertRaises(ValueError):
                self.cargar([resultado('Listings', filas)])
        with self.assertRaises(ValueError):
            self.cargar([resultado('Listings', [{'id': '1'}]),
                         resultado('Listings', [{'id': '2', 'name': 'nuevo'}])])

    def test_texto_xml_literal_unicode(self):
        texto = '_x0001_\x01😀 =+-@ https://example.org'
        destino, informe = self.cargar([resultado('Listings', [{'id': '001', 'name': texto}])])
        self.assertEqual(informe['tablas']['Listings']['filas'], 1)
        with closing(sqlite3.connect(destino / 'airbnb.sqlite')) as db:
            self.assertEqual(db.execute('SELECT name FROM Listings').fetchone()[0], texto)

    def test_cierra_generador_en_error(self):
        cerrado = []
        def generar():
            try:
                yield resultado('Listings', [{'id': '1', 'name': 'x' * 32768}])
                self.fail('No debe consumir después del error')
            finally:
                cerrado.append(True)
        with self.assertRaises(ValueError):
            Carga(ConfiguracionCarga(self.directorio())).ejecutar(generar())
        self.assertEqual(cerrado, [True])


    def test_publicacion_dump_fallido_no_listo(self):
        destino = self.directorio()
        def fallo(informe, archivo, **kwargs):
            archivo.write('{')
            raise OSError('fallo privado no registrable')
        with patch('src.carga.json.dump', side_effect=fallo), self.assertRaises(OSError):
            Carga(ConfiguracionCarga(destino)).ejecutar(
                iter([resultado('Listings', [{'id': '1'}])]))
        self.assertFalse((destino / 'listo.json').exists())

    def test_publicacion_rename_fallido_no_listo(self):
        destino = self.directorio()
        with patch.object(Path, 'rename', side_effect=OSError('fallo')), self.assertRaises(OSError):
            Carga(ConfiguracionCarga(destino)).ejecutar(
                iter([resultado('Listings', [{'id': '1'}])]))
        self.assertFalse((destino / 'listo.json').exists())

    def test_nul_columna_y_limite_sqlite(self):
        for columnas in ([ 'id', 'mal\x00nombre' ],
                         ['id'] + [f'c{i}' for i in range(2000)]):
            frame = pd.DataFrame(columns=columnas)
            with self.assertRaises(ValueError):
                self.cargar([Resultado('Listings', {'Listings': frame}, {})])

    def test_xlsx_texto_real_sin_formulas_ni_urls(self):
        textos = ['=1+1', '+123', '-123', '@hola', 'https://example.org',
                  '00001234567890123456789', '_x0001_\x01\x00\ufffe😀', 'x' * 32767]
        destino, informe = self.cargar([resultado('Listings',
            [{'id': str(i), 'name': t} for i, t in enumerate(textos)])])
        with ZipFile(destino / informe['tablas']['Listings']['xlsx'][0]['archivo']) as z:
            raiz = ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
        ns = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        self.assertEqual(raiz.findall('.//m:f', ns), [])
        self.assertEqual(raiz.findall('.//m:hyperlink', ns), [])
        celdas = [fila.findall('m:c', ns)[1] for fila in raiz.findall('.//m:row', ns)[1:]]
        self.assertTrue(all(c.attrib['t'] == 'inlineStr' for c in celdas))
        self.assertEqual([decodificar_excel(''.join(c.itertext())) for c in celdas], textos)


    def test_columnas_citadas_y_payload_no_ejecutado(self):
        columna = 'nombre\" TEXT); DROP TABLE Listings; --'
        payload = "'); DROP TABLE Listings; --"
        destino, informe = self.cargar([resultado('Listings', [{'id': '0001', columna: payload}])])
        with closing(sqlite3.connect(destino / 'airbnb.sqlite')) as db:
            self.assertEqual(db.execute('SELECT * FROM Listings').fetchall(), [('0001', payload)])
        self.assertEqual(informe['tablas']['Listings']['columnas'], ['id', columna])

    def test_limites_exactos_sin_parte_extra(self):
        for total, partes in [(0, [0]), (1, [1]), (2, [2]), (3, [2, 1]), (4, [2, 2])]:
            frame = pd.DataFrame({'id': [str(i) for i in range(total)]})
            _, informe = self.cargar([Resultado('Listings', {'Listings': frame}, {})], 2)
            self.assertEqual([p['filas'] for p in informe['tablas']['Listings']['xlsx']], partes)

    def test_esquema_independiente_dtype_y_lote_vacio(self):
        for inicial in (pd.DataFrame({'id': [], 'host_is_superhost': [], 'price': []}),
                        pd.DataFrame({'id': ['1'], 'host_is_superhost': [None], 'price': [None]})):
            final = pd.DataFrame({'id': ['2'], 'host_is_superhost': pd.Series([True], dtype='boolean'),
                                  'price': pd.Series([1.5], dtype='Float64')})
            destino, informe = self.cargar([Resultado('Listings', {'Listings': inicial}, {}),
                                            Resultado('Listings', {'Listings': final}, {})])
            with closing(sqlite3.connect(destino / 'airbnb.sqlite')) as db:
                self.assertEqual([r[2] for r in db.execute('PRAGMA table_info(Listings)')],
                                 ['TEXT', 'INTEGER', 'REAL'])
            self.assertEqual(informe['tablas']['Listings']['afinidades'], ['TEXT', 'INTEGER', 'REAL'])

    def test_cuatro_tablas_puente_primero_y_fechas_extremas(self):
        principal = pd.DataFrame({'id': ['001']})
        puente = pd.DataFrame({'listing_id': ['001'], 'amenity': ['Wifi']})
        r = Resultado('Listings', {'ListingAmenities': puente, 'Listings': principal}, {})
        fechas = ['0001-01-01', '0999-02-28', '1000-01-01', '9999-12-31']
        destino, informe = self.cargar([r,
            resultado('Reviews', [{'id': '000000000000000000001', 'listing_id': '001', 'comments': None}]),
            resultado('Calendar', [{'listing_id': '001', 'date': f, 'date_year': int(f[:4]),
                                     'available': None} for f in fechas])])
        self.assertEqual(set(informe['tablas']), {'Listings', 'ListingAmenities', 'Reviews', 'Calendar'})
        with closing(sqlite3.connect(destino / 'airbnb.sqlite')) as db:
            self.assertEqual([r[0] for r in db.execute('SELECT date FROM Calendar ORDER BY date')], fechas)
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])

    def test_fk_y_pk_hijos_entre_lotes(self):
        for nombre, filas in [('Calendar', [{'listing_id': '2', 'date': '2026-01-01'}]),
                              ('Reviews', [{'id': 'r', 'listing_id': '1'}, {'id': 'r', 'listing_id': '1'}])]:
            with self.assertRaises(sqlite3.IntegrityError):
                self.cargar([resultado('Listings', [{'id': '1'}]), resultado(nombre, filas)])
        for nombre, fila in [('Calendar', {'listing_id': '1', 'date': '2026-01-01'}),
                             ('Listings', {'id': '1'})]:
            datos = [resultado('Listings', [{'id': '1'}])]
            if nombre == 'Calendar':
                datos.append(resultado(nombre, [fila]))
            datos.append(resultado(nombre, [fila]))
            with self.assertRaises(sqlite3.IntegrityError):
                self.cargar(datos)

    def test_no_sobrescribe_archivo_y_nuevo_destino(self):
        destino = self.directorio()
        destino.write_text('intacto', encoding='utf-8')
        with self.assertRaises(FileExistsError):
            Carga(ConfiguracionCarga(destino)).ejecutar(iter([]))
        self.assertEqual(destino.read_text(encoding='utf-8'), 'intacto')
        self.assertNotEqual(ConfiguracionCarga.nueva(Path(self.temporal.name)).salida,
                            ConfiguracionCarga.nueva(Path(self.temporal.name)).salida)

    def test_apertura_y_cierre_libro_fallidos_no_listo(self):
        cierre_original = carga_modulo.xlsxwriter.Workbook.close
        def cerrar_falla(libro):
            cierre_original(libro)
            raise OSError('privado')
        for objetivo, fallo in [('src.carga.xlsxwriter.Workbook', OSError('privado')),
                                ('src.carga.xlsxwriter.Workbook.close', cerrar_falla)]:
            destino = self.directorio()
            with patch(objetivo, side_effect=fallo, autospec=True), self.assertRaises(OSError):
                Carga(ConfiguracionCarga(destino)).ejecutar(
                    iter([resultado('Listings', [{'id': '1'}])]))
            self.assertFalse((destino / 'listo.json').exists())
            with closing(sqlite3.connect(destino / 'airbnb.sqlite')) as db:
                self.assertEqual(db.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0], 0)

    def test_verificacion_xlsx_fallida_rollback(self):
        destino = self.directorio()
        with patch('src.carga.verificar_xlsx', side_effect=ValueError('fallo')), self.assertRaises(ValueError):
            Carga(ConfiguracionCarga(destino)).ejecutar(iter([resultado('Listings', [{'id': '1'}])]))
        self.assertFalse((destino / 'listo.json').exists())
        with closing(sqlite3.connect(destino / 'airbnb.sqlite')) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0], 0)

    def test_privacidad_error_no_exito(self):
        logger = logging.getLogger('carga-prueba-privacidad')
        with self.assertLogs(logger, level='INFO') as capturado, self.assertRaises(ValueError):
            Carga(ConfiguracionCarga(self.directorio()), logger).ejecutar(
                iter([resultado('Listings', [{'id': 'dato-secreto', 'price': float('inf')}])]))
        texto = '\n'.join(capturado.output)
        self.assertNotIn('dato-secreto', texto)
        self.assertNotIn('verificada y lista', texto)
        self.assertIn('ValueError', texto)

    def test_fallo_fuente_verificada_hace_rollback(self):
        destino = self.directorio()
        def verificar(conteos):
            self.assertEqual(conteos, {'Listings': 1})
            raise ValueError('fuente cambió')
        with self.assertRaises(ValueError):
            Carga(ConfiguracionCarga(destino)).ejecutar(
                iter([resultado('Listings', [{'id': '1'}])]), verificar)
        self.assertFalse((destino / 'listo.json').exists())
        with closing(sqlite3.connect(destino / 'airbnb.sqlite')) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0], 0)

    def test_write_retorno_error_y_config_invalida(self):
        for limite in (0, -1, 1048576):
            with self.assertRaises(ValueError):
                ConfiguracionCarga(self.directorio(), limite)
        destino = self.directorio()
        with patch('src.carga.xlsxwriter.worksheet.Worksheet.write_string', return_value=-2), self.assertRaises(ValueError):
            Carga(ConfiguracionCarga(destino)).ejecutar(iter([resultado('Listings', [{'id': '1'}])]))
        self.assertFalse((destino / 'listo.json').exists())


if __name__ == '__main__':
    unittest.main()
