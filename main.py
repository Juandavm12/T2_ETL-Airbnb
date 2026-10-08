"""CLI de importación, extracción, transformación auditada y Carga SQLite/XLSX."""
import argparse
import json
import os
import time
from pathlib import Path

from src.carga import Carga, ConfiguracionCarga
from src.extraccion import COLECCIONES, Extraccion, crear_logger
from src.importacion import importar_todas
from src.transformacion import Transformacion

ROOT = Path(__file__).resolve().parent


def main() -> int:
    """Ejecuta una operación y devuelve código de salida sin exponer errores privados."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('accion', choices=('importar', 'extraer', 'transformar', 'cargar'))
    parser.add_argument('--uri', default=os.environ.get('MONGO_URI', 'mongodb://localhost:27017'))
    parser.add_argument('--base', default='airbnb')
    parser.add_argument('--ruta', type=Path, default=ROOT.parent / 'Datasets')
    parser.add_argument('--batch', type=int, default=10000)
    parser.add_argument('--salida', type=Path, help='Directorio NUEVO para SQLite/XLSX')
    parser.add_argument('--completa', action='store_true', help='Riesgo alto de agotar RAM')
    args = parser.parse_args()
    if args.batch <= 0:
        parser.error('--batch debe ser positivo')
    logger = crear_logger(ROOT / 'logs')
    try:
        with Extraccion(args.uri, args.base, logger) as ext:
            if args.accion == 'importar':
                for nombre, total in importar_todas(ext.db, args.ruta, args.batch, logger).items():
                    print(f'{nombre}: {total} filas confirmadas')
            elif args.accion == 'transformar':
                if args.completa:
                    raise ValueError('Transformar exige streaming; no admite --completa')
                resumen = auditar_transformacion(ext, args.batch, logger)
                print(json.dumps(resumen, ensure_ascii=False, allow_nan=False, indent=2))
            elif args.accion == 'cargar':
                if args.completa:
                    raise ValueError('Cargar exige streaming; no admite --completa')
                config = (ConfiguracionCarga(args.salida) if args.salida is not None
                          else ConfiguracionCarga.nueva(ROOT / 'salidas'))
                resumen = cargar_datos(ext, args.batch, logger, config)
                print(json.dumps(resumen, ensure_ascii=False, allow_nan=False, indent=2))
            else:
                if any(ext.db[nombre].count_documents({}) == 0 for nombre in COLECCIONES):
                    raise ValueError('Fuente ausente o vacía; importar primero')
                for nombre in COLECCIONES:
                    if args.completa:
                        total = len(ext.completa(nombre, args.batch))
                    else:
                        total = sum(len(df) for df in ext.iterar(nombre, args.batch))
                    print(f'{nombre}: {total} filas extraídas')
        return 0
    except Exception as exc:
        logger.error('Ejecución fallida (%s)', type(exc).__name__)
        print('Operación fallida; consulte logs; no se declara éxito.')
        return 1
    finally:
        for handler in logger.handlers:
            handler.close()


def auditar_transformacion(ext, batch: int, logger) -> dict:
    """Consume tablas sin cargarlas ni retenerlas; verifica conteos y auditoría."""
    inicio = time.perf_counter()
    fuente = {n: ext.db[n].count_documents({}) for n in COLECCIONES}
    resumen = {'fuente': 'MongoDB solo lectura', 'batch': batch,
               'snapshot': False, 'carga_ejecutada': False,
               'precio_unidades': 'nominales; moneda no confirmada',
               'rangos': {'Q1': 'p <= 110000', 'Q2': '110000 < p <= 161460',
                          'Q3': '161460 < p <= 230346.375', 'Q4': 'p > 230346.375'},
               'colecciones': {n: {'fuente_antes': fuente[n], 'lotes': 0,
                                   'antes': 0, 'despues': 0, 'duplicados_exactos': 0,
                                   'conversiones': {}, 'dominios': {},
                                   'nulos_normalizados': {}, 'tablas': {}}
                               for n in COLECCIONES}}
    generador = Transformacion(logger).iterar(ext, batch)
    try:
        for resultado in generador:
            acumulado = resumen['colecciones'][resultado.coleccion]
            acumulado['lotes'] += 1
            for clave, valor in resultado.auditoria.items():
                if isinstance(valor, dict):
                    destino = acumulado.setdefault(clave, {})
                    for columna, cuenta in valor.items():
                        if isinstance(cuenta, dict):
                            contadores = destino.setdefault(columna, {})
                            for estado, n in cuenta.items():
                                contadores[estado] = contadores.get(estado, 0) + n
                        else:
                            destino[columna] = destino.get(columna, 0) + cuenta
                else:
                    acumulado[clave] = acumulado.get(clave, 0) + valor
            for nombre, frame in resultado.tablas.items():
                acumulado['tablas'][nombre] = acumulado['tablas'].get(nombre, 0) + len(frame)
            for conteo in resultado.auditoria['conversiones'].values():
                if sum(conteo.values()) != resultado.auditoria['despues']:
                    raise ValueError('Auditoría de conversión no conserva filas')
    finally:
        generador.close()
    for nombre, conteo in resumen['colecciones'].items():
        conteo['fuente_despues'] = ext.db[nombre].count_documents({})
        if not (conteo['antes'] == conteo['despues'] == fuente[nombre]
                == conteo['fuente_despues']):
            raise ValueError('Fuente cambió o transformación perdió filas')
        conteo['duplicados_globales'] = 0  # Preflight de iterar completó sin excepción.
    resumen['duracion_segundos'] = time.perf_counter() - inicio
    resumen['log'] = str(Path(logger.handlers[0].baseFilename).relative_to(ROOT))
    resumen['invariantes'] = 'conteos antes/después y conversiones conservan filas'
    logger.info('Auditoría completa; tablas consumidas sin Carga')
    return resumen


def cargar_datos(ext, batch: int, logger, config: ConfiguracionCarga) -> dict:
    """Encadena extracción, transformación y carga sin repetir ni retener tablas."""
    fuente = {n: ext.db[n].count_documents({}) for n in COLECCIONES}
    if batch <= 0 or any(n <= 0 for n in fuente.values()):
        raise ValueError('Lote o fuente inválidos')

    def verificar(conteos):
        despues = {n: ext.db[n].count_documents({}) for n in COLECCIONES}
        if (set(conteos) != set(COLECCIONES) | {'ListingAmenities'}
                or any(conteos[n] != fuente[n] or despues[n] != fuente[n] for n in COLECCIONES)):
            raise ValueError('Fuente cambió o se perdieron filas')
        return {'modo': 'MongoDB solo lectura; sin snapshot', 'batch': batch,
                'antes': fuente, 'despues': despues}

    informe = Carga(config, logger).ejecutar(Transformacion(logger).iterar(ext, batch), verificar)
    log = Path(logger.handlers[0].baseFilename).relative_to(ROOT)
    return {'estado': informe['estado'], 'salida': str(config.salida),
            'manifest': str(config.salida / 'listo.json'), 'log': str(log),
            'filas': {n: t['filas'] for n, t in informe['tablas'].items()},
            'duracion_segundos': informe['duracion_segundos']}


if __name__ == '__main__':
    raise SystemExit(main())
