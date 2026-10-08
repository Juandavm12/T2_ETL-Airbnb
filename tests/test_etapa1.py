"""Contratos deterministas sin servidor MongoDB."""
import csv
import gzip
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from src.extraccion import Extraccion, crear_logger
from src.importacion import importar_csv, importar_todas


class EtapaUnoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.log = crear_logger(self.root)
        self.addCleanup(lambda: [h.close() for h in self.log.handlers])

    def archivo(self, comprimido=False):
        path = self.root / ('datos.csv.gz' if comprimido else 'datos.csv')
        abrir = gzip.open if comprimido else open
        with abrir(path, 'wt', encoding='utf-8', newline='') as stream:
            stream.write('id,texto\n001,"dos\nlineas"\n002,NA\n003,\n')
        return path

    def coleccion(self):
        col = MagicMock()
        col.count_documents.side_effect = [0, 3]
        col.insert_many.side_effect = lambda lote, **kw: type(
            'Acuse', (), {'acknowledged': True, 'inserted_ids': list(range(len(lote)))})()
        return col

    def test_csv_gzip_multilinea_lote_final_strings(self):
        for compressed in (False, True):
            with self.subTest(gzip=compressed):
                col = self.coleccion()
                self.assertEqual(importar_csv(self.archivo(compressed), col, 2, self.log), 3)
                batches = [c.args[0] for c in col.insert_many.call_args_list]
                self.assertEqual([len(b) for b in batches], [2, 1])
                self.assertEqual(batches[0][0], {'id': '001', 'texto': 'dos\nlineas'})
                self.assertEqual(batches[0][1]['texto'], 'NA')
                self.assertEqual(batches[1][0]['texto'], '')

    def test_csv_truncado_falla_sin_insertar_ni_reportar_exito(self):
        path = self.root / 'truncado.csv'
        path.write_text('id,texto\n001,"texto sin cerrar\n002,otro\n', encoding='utf-8')
        col = self.coleccion()
        col.count_documents.side_effect = [0, 1]
        with self.assertRaises(csv.Error):
            importar_csv(path, col, 2, self.log)
        col.insert_many.assert_not_called()
        text = next(self.root.glob('*.log')).read_text()
        self.assertIn('ERROR', text)
        self.assertNotIn('Importadas y verificadas', text)

    def test_preflight_global_y_acuses(self):
        db = MagicMock()
        db.__getitem__.side_effect = lambda nombre: cols[nombre]
        cols = {n: MagicMock() for n in ('Listings', 'Reviews', 'Calendar')}
        for n, col in cols.items():
            col.count_documents.return_value = int(n == 'Calendar')
            (self.root / f'{n.lower()}.csv').write_text('id\n1\n')
        with self.assertRaises(ValueError):
            importar_todas(db, self.root, 2, self.log)
        for col in cols.values():
            col.insert_many.assert_not_called()
        for acknowledged, ids in ((False, [1, 2]), (True, [1])):
            col = self.coleccion()
            col.insert_many.side_effect = None
            col.insert_many.return_value.acknowledged = acknowledged
            col.insert_many.return_value.inserted_ids = ids
            with self.assertRaises(ValueError):
                importar_csv(self.archivo(), col, 2, self.log)

    def test_no_vacias(self):
        col = MagicMock()
        col.count_documents.return_value = 1
        with self.assertRaises(ValueError):
            importar_csv(self.archivo(), col, 2, self.log)
        col.insert_many.assert_not_called()

    def test_error_insercion_y_conteo(self):
        for error in (True, False):
            col = self.coleccion()
            if error:
                col.insert_many.side_effect = RuntimeError('fallo privado')
            else:
                col.count_documents.side_effect = [0, 2]
            with self.assertRaises((RuntimeError, ValueError)):
                importar_csv(self.archivo(), col, 2, self.log)
        text = next(self.root.glob('*.log')).read_text()
        self.assertIn('ERROR', text)
        self.assertNotIn('fallo privado', text)

    def test_extraccion_lotes_completa_cierre(self):
        client = MagicMock()
        col = client.__getitem__.return_value.__getitem__.return_value
        col.count_documents.return_value = 3
        col.find.side_effect = lambda *a: iter([{'id': '001'}, {'id': '002'}, {'id': '003'}])
        with Extraccion(logger=self.log, cliente_factory=lambda *a, **kw: client) as ext:
            self.assertEqual([len(df) for df in ext.iterar('Listings', 2)], [2, 1])
            self.assertEqual(len(ext.completa('Listings', 2)), 3)
        client.close.assert_called_once()
        text = next(self.root.glob('*.log')).read_text()
        self.assertIn('INFO', text)
        self.assertIn('WARNING', text)

    def test_falla_conexion_cierra_sin_filtrar_secretos(self):
        client = MagicMock()
        client.admin.command.side_effect = RuntimeError('mongodb://secreto')
        with self.assertRaises(RuntimeError), Extraccion(
                logger=self.log, cliente_factory=lambda *a, **kw: client):
            pass
        client.close.assert_called_once()
        self.assertNotIn('secreto', next(self.root.glob('*.log')).read_text())

    def test_logs_unicos_y_cursor_parcial_cerrado(self):
        otro = crear_logger(self.root)
        self.addCleanup(lambda: [h.close() for h in otro.handlers])
        self.assertEqual(len(list(self.root.glob('*.log'))), 2)
        client = MagicMock()
        cursor = MagicMock()
        cursor.batch_size.return_value = cursor

        def documentos():
            yield {'id': '001'}
            yield {'id': '002'}
            raise RuntimeError('error privado')

        cursor.__iter__.side_effect = documentos
        client.__getitem__.return_value.__getitem__.return_value.find.return_value = cursor
        with Extraccion(logger=self.log, cliente_factory=lambda *a, **kw: client) as ext:
            lotes = ext.iterar('Calendar', 2)
            self.assertEqual(len(next(lotes)), 2)
            with self.assertRaises(RuntimeError):
                next(lotes)
            cursor.close.assert_called_once()
            cursor.close.reset_mock()
            lotes = ext.iterar('Calendar', 2)
            next(lotes)
            lotes.close()
            cursor.close.assert_called_once()

    def test_error_cursor_y_batch_invalido(self):
        client = MagicMock()
        col = client.__getitem__.return_value.__getitem__.return_value
        col.find.side_effect = RuntimeError('cursor privado')
        with Extraccion(logger=self.log, cliente_factory=lambda *a, **kw: client) as ext:
            with self.assertRaises(RuntimeError):
                list(ext.iterar('Reviews', 2))
            with self.assertRaises(ValueError):
                list(ext.iterar('Calendar', 0))
        with self.assertRaises(ValueError):
            importar_csv(self.archivo(), self.coleccion(), 0, self.log)


if __name__ == '__main__':
    unittest.main()
