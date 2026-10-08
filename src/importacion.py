"""Importación CSV reproducible sin eliminar colecciones existentes."""
import csv
import gzip
from pathlib import Path

from src.extraccion import COLECCIONES


def importar_csv(path: Path, coleccion, batch: int, logger) -> int:
    """Inserta strings por lotes y compara filas, acuses y conteo final."""
    if batch <= 0:
        raise ValueError('batch debe ser positivo')
    try:
        if coleccion.count_documents({}):
            raise ValueError('Colección no vacía; importación rechazada')
        abrir = gzip.open if path.suffix == '.gz' else open
        total = 0
        with abrir(path, 'rt', encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream, strict=True)
            if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
                raise ValueError('Cabecera ausente o duplicada')
            if '_id' in reader.fieldnames:
                raise ValueError('_id reservado para MongoDB')
            lote = []
            for fila in reader:
                if None in fila or None in fila.values():
                    raise ValueError('Fila incompatible con cabecera')
                lote.append(fila)
                if len(lote) == batch:
                    total += insertar(coleccion, lote)
                    lote = []
            if lote:
                total += insertar(coleccion, lote)
        if coleccion.count_documents({}) != total:
            raise ValueError('Conteo final distinto de filas confirmadas')
        logger.info('Importadas y verificadas %d filas', total)
        return total
    except Exception as exc:
        logger.error('Importación fallida (%s); revisar posible estado parcial',
                     type(exc).__name__)
        raise


def insertar(coleccion, lote: list[dict]) -> int:
    """Exige confirmación del servidor para cada fila del lote."""
    esperado = len(lote)
    resultado = coleccion.insert_many(lote, ordered=True)
    if not resultado.acknowledged or len(resultado.inserted_ids) != esperado:
        raise ValueError('Inserción no confirmada completamente')
    return esperado


def importar_todas(db, directorio: Path, batch: int, logger) -> dict[str, int]:
    """Preflight global antes de la primera inserción; no es una transacción."""
    try:
        paths = {}
        for nombre in COLECCIONES:
            if db[nombre].count_documents({}):
                raise ValueError('Preflight: colección no vacía')
            path = directorio / f'{nombre.lower()}.csv'
            if not path.is_file():
                path = path.with_suffix('.csv.gz')
            if not path.is_file():
                raise FileNotFoundError('CSV requerido ausente')
            paths[nombre] = path
        return {nombre: importar_csv(path, db[nombre], batch, logger)
                for nombre, path in paths.items()}
    except Exception as exc:
        logger.error('Importación global fallida (%s)', type(exc).__name__)
        raise
