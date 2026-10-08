"""Contratos del EDA sin servicios ni datos privados."""
import unittest
from unittest.mock import Mock

import pandas as pd

from src.analisis import (
    Perfil,
    amenities,
    convertir,
    describir_frecuencias,
    duplicados,
    iqr,
)


class AnalisisTest(unittest.TestCase):
    def test_perfil_invariante_lotes(self):
        df = pd.DataFrame({'x': [None, '', '  ', 'NA', '0', 'NULL']})
        uno, dos = Perfil(), Perfil()
        uno.agregar(df)
        dos.agregar(df.iloc[:2])
        dos.agregar(df.iloc[2:])
        self.assertEqual(uno.resultado(), dos.resultado())
        self.assertEqual(uno.resultado()['columnas']['x']['null'], 1)
        self.assertEqual(uno.resultado()['columnas']['x']['vacio'], 2)
        self.assertEqual(uno.resultado()['columnas']['x']['marcador_candidato'], 2)

    def test_precios_y_originales(self):
        s = pd.Series(['$1,200.50', '0', 'bad', 'inf', '', None])
        copia = s.copy()
        v, c = convertir(s, 'precio')
        self.assertEqual(v.iloc[0], 1200.5)
        self.assertEqual(v.iloc[1], 0)
        self.assertEqual(c, {'validos': 2, 'faltantes': 2, 'invalidos': 1, 'no_finitos': 1})
        pd.testing.assert_series_equal(s, copia)

    def test_fecha_estricta(self):
        _, c = convertir(pd.Series(['2025-01-01', '2025-02-30', '2025-1-1', '']), 'fecha')
        self.assertEqual(c['validos'], 1)
        self.assertEqual(c['invalidos'], 2)

    def test_iqr_preserva_frontera(self):
        s = pd.Series([0, 1, 2, 3, 6])
        r = iqr(s)
        self.assertEqual(r['superior'], 6)
        self.assertEqual(r['atipicos'], 0)
        self.assertEqual(len(s), 5)

    def test_frecuencias_exactas_sin_materializar(self):
        r = describir_frecuencias({0: 1, 1: 1, 2: 1, 3: 1, 10: 1})
        self.assertEqual(r['q1'], 1)
        self.assertEqual(r['q3'], 3)
        self.assertEqual(r['atipicos'], 1)
        self.assertEqual(r['media'], 3.2)

    def test_duplicados_exactos_y_timeout(self):
        col = Mock()
        col.aggregate.return_value = iter([{'grupos': 2, 'exceso': 3, 'filas': 5}])
        self.assertEqual(duplicados(col, ['listing_id', 'date'])['exceso'], 3)
        args, kwargs = col.aggregate.call_args
        self.assertTrue(kwargs['allowDiskUse'])
        self.assertEqual(kwargs['maxTimeMS'], 300000)
        self.assertEqual(args[0][0]['$group']['_id'],
                         {'listing_id': '$listing_id', 'date': '$date'})
        col.aggregate.side_effect = TimeoutError('agregado')
        with self.assertRaises(TimeoutError):
            duplicados(col, ['id'])

    def test_amenities_invalidos_y_presencia(self):
        r = amenities(pd.Series(['["Wifi", "Wifi"]', '{}', '[3]', '', 'bad']))
        self.assertEqual(r['validos'], 1)
        self.assertEqual(r['invalidos'], 3)
        self.assertEqual(r['vacios'], 1)
        self.assertEqual(r['top'], {'Wifi': 1})

    def test_booleanos(self):
        _, c = convertir(pd.Series(['t', 'f', 'true', '']), 'booleano')
        self.assertEqual(c['validos'], 2)
        self.assertEqual(c['invalidos'], 1)
