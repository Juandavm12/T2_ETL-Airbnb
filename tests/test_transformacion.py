"""Contratos de transformación sin servicios ni documentos privados."""
import json
import logging
import unittest
from unittest.mock import Mock

import pandas as pd

from src.transformacion import Transformacion


class TransformacionTests(unittest.TestCase):
    def setUp(self):
        self.log = logging.getLogger('prueba_transformacion')
        self.t = Transformacion(self.log)

    def test_precio_fronteras_inmutabilidad(self):
        valores = ['$110,000', '161460', '230346.375', '410865.9375',
                   '410865.94', 'bad', '', 'NA', 'inf', '-1', '0']
        df = pd.DataFrame({'id': [f'{n:03}' for n in range(len(valores))],
                           'price': valores, '_id': list(range(len(valores)))})
        copia = df.copy(deep=True)
        r = self.t.lote('Listings', df)
        f = r.tablas['Listings']
        self.assertEqual(f.price.iloc[0], 110000)
        self.assertEqual(list(f.price_category.iloc[:3]), ['Q1', 'Q2', 'Q3'])
        self.assertFalse(f.price_outlier.iloc[3])
        self.assertTrue(f.price_outlier.iloc[4])
        self.assertTrue(f.price.isna().iloc[5:9].all())
        self.assertEqual(r.auditoria['conversiones']['price']['faltantes'], 2)
        self.assertNotIn('_id', f)
        pd.testing.assert_frame_equal(df, copia)

    def test_fecha_derivados_estrictos(self):
        df = pd.DataFrame({'id': ['1', '2', '3', '4'],
                           'date': ['2024-02-29', '2023-02-29', '2024-2-01', None]})
        r = self.t.lote('Reviews', df)
        f = r.tablas['Reviews']
        self.assertEqual(f.date.iloc[0], '2024-02-29')
        self.assertEqual(f.date_year.iloc[0], 2024)
        self.assertEqual(f.date_month.iloc[0], 2)
        self.assertEqual(f.date_day.iloc[0], 29)
        self.assertEqual(f.date_quarter.iloc[0], 1)
        self.assertTrue(f.date_year.iloc[1:].isna().all())
        self.assertEqual(r.auditoria['conversiones']['date']['invalidos'], 2)

    def test_claves_exactas_y_privacidad(self):
        df = pd.DataFrame({'id': ['001', '1', ' 1 '],
                           'comments': ['NA', ' texto privado ', 'NULL'],
                           'reviewer_name': ['NA', 'N/A', 'NONE']})
        r = self.t.lote('Reviews', df)
        pd.testing.assert_frame_equal(r.tablas['Reviews'], df)
        for valor in ['', '  ', 'NA', None, 1]:
            with self.subTest(valor=valor), self.assertRaises(ValueError):
                self.t.lote('Reviews', pd.DataFrame({'id': [valor]}))

    def test_duplicados_exactos_conflictos(self):
        df = pd.DataFrame({'id': ['1', '1'], 'comments': ['a', 'a'], '_id': [1, 2]})
        r = self.t.lote('Reviews', df)
        self.assertEqual(len(r.tablas['Reviews']), 1)
        self.assertEqual(r.auditoria['duplicados_exactos'], 1)
        df.loc[1, 'comments'] = 'b'
        with self.assertRaises(ValueError):
            self.t.lote('Reviews', df)

    def test_amenities_y_anidados(self):
        df = pd.DataFrame({'id': ['01', '02', '03'],
                           'amenities': ['["Wifi", "Wifi", "Kitchen"]', '[3]', ''],
                           'host_name': ['NA', 'Ana', 'B'],
                           'price_quote_raw': [{'a': [1]}, '{}', None]})
        r = self.t.lote('Listings', df)
        puente = r.tablas['ListingAmenities']
        self.assertEqual(puente.to_dict('records'), [
            {'listing_id': '01', 'amenity': 'Kitchen'},
            {'listing_id': '01', 'amenity': 'Wifi'}])
        self.assertEqual(r.auditoria['amenities']['invalidos'], 1)
        self.assertEqual(r.tablas['Listings'].host_name.iloc[0], 'NA')
        self.assertEqual(json.loads(r.tablas['Listings'].price_quote_raw.iloc[0]), {'a': [1]})
        self.assertEqual(df.price_quote_raw.iloc[0], {'a': [1]})

    def test_calendar_sin_precio_dominios(self):
        df = pd.DataFrame({'listing_id': ['01', '01', '01', '01'],
                           'date': ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04'],
                           'available': ['t', 'f', 'true', 'NA'],
                           'minimum_nights': ['1', '-1', '1.5', '']})
        r = self.t.lote('Calendar', df)
        f = r.tablas['Calendar']
        self.assertNotIn('price', f)
        self.assertEqual(list(f.available.iloc[:2]), [True, False])
        self.assertTrue(f.available.iloc[2:].isna().all())
        self.assertEqual(r.auditoria['dominios']['minimum_nights'], 2)

    def test_preflight_global_antes_extraer_crosslote(self):
        ext = Mock()
        col = Mock()
        col.count_documents.return_value = 2
        col.aggregate.side_effect = [iter([]), iter([]), iter([{'grupos': 1,
                                    'exceso': 1, 'filas': 2}])]
        ext.db.__getitem__ = Mock(return_value=col)
        with self.assertRaises(ValueError):
            list(self.t.iterar(ext, 1))
        ext.iterar.assert_not_called()
        for llamada in col.aggregate.call_args_list:
            self.assertTrue(llamada.kwargs['allowDiskUse'])
            self.assertFalse(any('$out' in etapa or '$merge' in etapa
                                 for etapa in llamada.args[0]))

    def test_lotes_cierre_y_error_sin_secretos(self):
        ext = Mock()
        col = Mock()
        col.count_documents.return_value = 2
        col.aggregate.side_effect = lambda *a, **kw: iter([])
        ext.db.__getitem__ = Mock(return_value=col)
        cerrados = []

        def lotes(nombre, batch):
            try:
                for n in range(2):
                    yield pd.DataFrame({'id': [str(n)]})
            finally:
                cerrados.append(nombre)

        ext.iterar.side_effect = lotes
        gen = self.t.iterar(ext, 1)
        self.assertEqual(len(next(gen).tablas['Listings']), 1)
        gen.close()
        self.assertEqual(cerrados, ['Listings'])
        with (self.assertLogs(self.log, level='ERROR') as captura,
              self.assertRaises(ValueError)):
            self.t.lote('Reviews', pd.DataFrame({'id': ['NA'], 'comments': ['secreto']}))
        self.assertNotIn('secreto', ''.join(captura.output))

    def test_invariante_por_lote(self):
        df = pd.DataFrame({'id': ['1', '2', '3'], 'price': ['110000', '161460', '500000']})
        completo = self.t.lote('Listings', df).tablas['Listings']
        partes = [self.t.lote('Listings', df.iloc[n:n+1]).tablas['Listings']
                  for n in range(3)]
        pd.testing.assert_frame_equal(completo, pd.concat(partes, ignore_index=True))

    def test_calendar_clave_fecha_no_normaliza_equivalencias(self):
        for fecha in [' 2024-01-01 ', '2024-1-01', '2024-02-30', '', None]:
            with self.subTest(fecha=fecha), self.assertRaises(ValueError):
                self.t.lote('Calendar', pd.DataFrame({'listing_id': ['001'],
                                                       'date': [fecha]}))

    def test_nulos_reglas_declaradas_sin_imputar(self):
        df = pd.DataFrame({'id': ['1'], 'price': [' NULL '],
                           'host_verifications': ['NA'], 'description': ['NA'],
                           'neighborhood_overview': ['  '], 'host_since': ['']})
        r = self.t.lote('Listings', df)
        f = r.tablas['Listings']
        self.assertTrue(pd.isna(f.price.iloc[0]))
        self.assertTrue(pd.isna(f.price_category.iloc[0]))
        self.assertTrue(pd.isna(f.price_outlier.iloc[0]))
        self.assertTrue(pd.isna(f.host_verifications.iloc[0]))
        self.assertTrue(pd.isna(f.neighborhood_overview.iloc[0]))
        self.assertEqual(f.description.iloc[0], 'NA')
        self.assertEqual(len(f), 1)
        json.dumps(r.auditoria, allow_nan=False)

    def test_regresion_fechas_cuatro_digitos(self):
        fechas = ['0001-01-01', '0999-12-31', '1000-01-01', '9999-12-31']
        calendar = pd.DataFrame({'listing_id': ['001'] * 4, 'date': fechas})
        f = self.t.lote('Calendar', calendar).tablas['Calendar']
        self.assertEqual(f.date.tolist(), fechas)
        self.assertEqual(f.date_year.tolist(), [1, 999, 1000, 9999])
        reviews = pd.DataFrame({'id': ['1', '2'], 'date': ['0001-01-01', '0999-02-30']})
        r = self.t.lote('Reviews', reviews).tablas['Reviews']
        self.assertEqual(r.date.iloc[0], fechas[0])
        self.assertTrue(pd.isna(r.date.iloc[1]))
        self.assertTrue(pd.isna(r.date_year.iloc[1]))

    def test_regresion_dedup_tipos_raw(self):
        pares = [({'a': 1}, '{"a": 1}'), ([1], '[1]'), (True, 1),
                 (1, 1.0), ({'a': True}, {'a': 1}), ([1], [1.0])]
        for primero, segundo in pares:
            df = pd.DataFrame({'id': ['001', '001'],
                               'comments': pd.Series([primero, segundo], dtype=object)})
            with self.subTest(par=(primero, segundo)), self.assertRaises(ValueError):
                self.t.lote('Reviews', df)

    def test_dedup_anidados_iguales_orden_e_inmutabilidad(self):
        import copy

        valores = [{'a': [1, {'x': 'v'}], 'b': 2},
                   {'b': 2, 'a': [1, {'x': 'v'}]}]
        originales = copy.deepcopy(valores)
        df = pd.DataFrame({'id': ['001', '001'], 'comments': valores, '_id': [1, 2]})
        r = self.t.lote('Reviews', df)
        self.assertEqual(r.auditoria['duplicados_exactos'], 1)
        self.assertEqual(json.loads(r.tablas['Reviews'].comments.iloc[0]), valores[0])
        self.assertEqual(df.comments.tolist(), originales)
        df = pd.DataFrame({'id': ['001', '001'], 'comments': [[1, 2], [1, 2]]})
        self.assertEqual(self.t.lote('Reviews', df).auditoria['duplicados_exactos'], 1)
        df.at[1, 'comments'] = [2, 1]
        with self.assertRaises(ValueError):
            self.t.lote('Reviews', df)

    def test_errores_timeout_vacio_batch(self):
        with self.assertRaises(ValueError):
            self.t.lote('Otra', pd.DataFrame())
        self.assertEqual(len(self.t.lote('Reviews', pd.DataFrame({'id': []})).tablas['Reviews']), 0)
        ext = Mock()
        with self.assertRaises(ValueError):
            list(self.t.iterar(ext, 0))
        col = Mock()
        col.count_documents.return_value = 1
        col.aggregate.side_effect = TimeoutError('credencial privada')
        ext.db.__getitem__ = Mock(return_value=col)
        with (self.assertLogs(self.log, level='ERROR') as captura,
              self.assertRaises(TimeoutError)):
            list(self.t.iterar(ext))
        self.assertNotIn('credencial', ''.join(captura.output))
        ext.iterar.assert_not_called()
