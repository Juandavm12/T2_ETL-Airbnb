"""Extracción por lotes desde MongoDB; no transforma los datos."""
import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
from pymongo import MongoClient

COLECCIONES = ('Listings', 'Reviews', 'Calendar')


def crear_logger(directorio: Path) -> logging.Logger:
    """Crea un archivo único por ejecución sin registrar URI ni documentos."""
    directorio.mkdir(parents=True, exist_ok=True)
    nombre = f"etl_{datetime.now():%Y%m%d_%H%M%S}_{uuid4().hex}"
    logger = logging.getLogger(nombre)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = logging.FileHandler(directorio / f'{nombre}.log', encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logger.addHandler(handler)
    return logger


class Extraccion:
    """Gestiona conexión y DataFrames; usar como administrador de contexto."""

    def __init__(self, uri: str = 'mongodb://localhost:27017', base: str = 'airbnb',
                 logger: logging.Logger | None = None,
                 cliente_factory: Callable[..., Any] = MongoClient):
        self.logger = logger or crear_logger(Path(__file__).resolve().parents[1] / 'logs')
        self.cliente = cliente_factory(uri, serverSelectionTimeoutMS=5000)
        self.db = self.cliente[base]

    def __enter__(self):
        try:
            self.cliente.admin.command('ping')
            self.logger.info('Conexión MongoDB establecida')
            return self
        except Exception as exc:
            self.logger.error('Conexión fallida (%s)', type(exc).__name__)
            self.cliente.close()
            raise

    def __exit__(self, exc_type, exc_value, traceback):
        self.cliente.close()
        self.logger.info('Conexión cerrada')

    def iterar(self, coleccion: str, batch: int = 10000):
        """Entrega DataFrames acotados; excluye únicamente el _id de MongoDB."""
        if batch <= 0 or coleccion not in COLECCIONES:
            raise ValueError('Lote positivo y colección conocida requeridos')
        cursor = None
        try:
            col = self.db[coleccion]
            self.logger.info('%s: %d documentos', coleccion, col.count_documents({}))
            cursor = col.find({}, {'_id': 0})
            if hasattr(cursor, 'batch_size'):
                cursor = cursor.batch_size(batch)
            filas = []
            total = 0
            for documento in cursor:
                filas.append(documento)
                if len(filas) == batch:
                    total += len(filas)
                    yield pd.DataFrame(filas)
                    filas = []
            if filas:
                total += len(filas)
                yield pd.DataFrame(filas)
            self.logger.info('%s: extraídos %d', coleccion, total)
        except Exception as exc:
            self.logger.error('Extracción fallida (%s)', type(exc).__name__)
            raise
        finally:
            if cursor is not None and hasattr(cursor, 'close'):
                cursor.close()

    def completa(self, coleccion: str, batch: int = 10000) -> pd.DataFrame:
        """Materializa toda la colección, con riesgo de agotar RAM."""
        self.logger.warning('Extracción completa: puede agotar memoria')
        partes = list(self.iterar(coleccion, batch))
        return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()
