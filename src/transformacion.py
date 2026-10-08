"""Transformación pura por lote y preflight MongoDB de solo lectura.

Identificadores exactos (sin trim/coerción) permiten usar las claves raw del
EDA. No existe snapshot: ejecutar sin escritores concurrentes. Los cuartiles
son de Listings EDA completo, nunca del lote; moneda no confirmada.
"""
import json
import logging
from collections.abc import Generator
from dataclasses import dataclass
from typing import Any, cast

import pandas as pd

from src.analisis import MARCADORES, convertir, duplicados
from src.extraccion import COLECCIONES

CLAVES = {'Listings': ['id'], 'Reviews': ['id'], 'Calendar': ['listing_id', 'date']}
IDENTIFICADORES = {'id', 'listing_id', 'host_id', 'host_profile_id', 'reviewer_id',
                   'scrape_id'}
FECHAS = {'date', 'host_since', 'first_review', 'last_review', 'last_scraped',
          'calendar_last_scraped', 'price_quote_checkin_date', 'price_quote_checkout_date'}
PRECIOS = {'price', 'price_quote_price_per_night', 'price_quote_total_price',
           'estimated_revenue_l365d'}
BOOLEANOS = {'available', 'has_availability', 'host_is_superhost', 'host_has_profile_pic',
             'host_identity_verified', 'instant_bookable'}
NUMEROS = set('latitude longitude accommodates bathrooms bedrooms beds minimum_nights '
              'maximum_nights minimum_minimum_nights maximum_minimum_nights '
              'minimum_maximum_nights maximum_maximum_nights minimum_nights_avg_ntm '
              'maximum_nights_avg_ntm availability_30 availability_60 availability_90 '
              'availability_365 availability_eoy number_of_reviews number_of_reviews_ltm '
              'number_of_reviews_l30d number_of_reviews_ly estimated_occupancy_l365d '
              'host_listings_count host_total_listings_count hosts_time_as_host_months '
              'hosts_time_as_host_years hosts_time_as_user_months hosts_time_as_user_years '
              'calculated_host_listings_count calculated_host_listings_count_entire_homes '
              'calculated_host_listings_count_private_rooms '
              'calculated_host_listings_count_shared_rooms review_scores_rating '
              'review_scores_accuracy review_scores_cleanliness review_scores_checkin '
              'review_scores_communication review_scores_location review_scores_value '
              'reviews_per_month'.split())
# Solo estas columnas interpretan marcadores como ausencia. Texto libre no.
MARCADORES_NULOS = FECHAS | PRECIOS | BOOLEANOS | NUMEROS | {'host_verifications'}
Q1, MEDIANA, Q3 = 110000.0, 161460.0, 230346.375
CERCA_INFERIOR, CERCA_SUPERIOR = -70519.5625, 410865.9375


@dataclass
class Resultado:
    """Tablas escalares listas para futura Carga y auditoría sin valores privados."""

    coleccion: str
    tablas: dict[str, pd.DataFrame]
    auditoria: dict


def escalar(valor: Any) -> Any:
    """Serializa estructuras sin mutarlas; no deja objetos list/dict para SQLite."""
    if isinstance(valor, (list, dict)):
        return json.dumps(valor, ensure_ascii=False, sort_keys=True, allow_nan=False)
    if isinstance(valor, (str, int, float, bool)) or pd.isna(valor):
        return valor
    raise ValueError('Tipo no escalar no soportado')


def huella_raw(valor: Any) -> tuple:
    """Compara tipos/valores antes de serializar; mappings ignoran orden.

    Listas conservan orden y tipos recursivos; nulos del mismo tipo son iguales.
    Se compara el valor que recibió el DataFrame, no tipos perdidos por inferencia.
    """
    tipo = type(valor)
    if isinstance(valor, dict):
        return tipo, frozenset((huella_raw(k), huella_raw(v)) for k, v in valor.items())
    if isinstance(valor, list):
        return tipo, tuple(huella_raw(v) for v in valor)
    return tipo, None if pd.isna(valor) else valor


class Transformacion:
    """Produce copias limpias acotadas, sin imputar ni eliminar atípicos.

    Args:
        logger: Logger existente; no crea archivos ni registra documentos.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger(__name__)

    def lote(self, coleccion: str, entrada: pd.DataFrame) -> Resultado:
        """Transforma un lote sin estado global ni modificar entrada.

        Deduplica filas idénticas excluyendo _id antes de conversiones; claves
        conflictivas rechazan todo el lote. No deduplica errores de conversión.

        Args:
            coleccion: Listings, Reviews o Calendar.
            entrada: DataFrame fuente; identificadores deben ser strings exactos.
        Returns:
            Resultado con tabla principal, puente amenities y conteos auditados.
        """
        try:
            return self._lote(coleccion, entrada)
        except Exception as exc:
            self.logger.error('Transformación fallida (%s)', type(exc).__name__)
            raise

    def _lote(self, coleccion: str, entrada: pd.DataFrame) -> Resultado:
        if coleccion not in CLAVES or not entrada.columns.is_unique:
            raise ValueError('Colección o columnas inválidas')
        f = entrada.drop(columns=['_id'], errors='ignore').copy(deep=True)
        claves = CLAVES[coleccion]
        if not set(claves).issubset(f.columns):
            raise ValueError('Claves requeridas ausentes')
        for col in IDENTIFICADORES.intersection(f.columns):
            s = f[col]
            validos = s.map(lambda v: isinstance(v, str) and bool(v.strip())
                            and v.strip().upper() not in MARCADORES)
            if not bool(cast(Any, validos).all()):
                raise ValueError('Identificador ausente o inválido')
        antes = len(f)
        f = f.reset_index(drop=True)
        repetidas = f.duplicated(claves, keep=False)
        if repetidas.any():
            # Solo candidatos dentro del lote: sin serialización ni coerción
            # de tipos para decidir identidad, y sin estado entre lotes.
            firmas = f.loc[repetidas].map(huella_raw)
            f = f.drop(index=firmas.index[firmas.duplicated()]).reset_index(drop=True)
            if f.duplicated(claves).any():
                raise ValueError('Claves conflictivas; sin resolución arbitraria')
        for col in f:
            if f[col].dtype == object:
                f[col] = f[col].map(escalar)
        audit = {'antes': antes, 'despues': len(f), 'duplicados_exactos': antes - len(f),
                 'nulos_normalizados': {}, 'conversiones': {}, 'dominios': {}}
        for col in f:
            if col in IDENTIFICADORES or col in claves:
                continue
            texto = f[col].astype('string').str.strip()
            vacio = texto.eq('').fillna(False)
            marcador = texto.str.upper().isin(MARCADORES) if col in MARCADORES_NULOS else False
            mascara = vacio | marcador
            audit['nulos_normalizados'][col] = int(mascara.sum())
            f[col] = f[col].mask(mascara, pd.NA)
        for col in sorted((FECHAS | PRECIOS | NUMEROS | BOOLEANOS).intersection(f.columns)):
            clase = ('fecha' if col in FECHAS else 'precio' if col in PRECIOS
                     else 'booleano' if col in BOOLEANOS else 'numero')
            # date es clave Calendar: exige forma exacta antes de convertir para
            # no colapsar claves globalmente únicas tras trim o error -> NULL.
            if coleccion == 'Calendar' and col == 'date':
                texto = f[col].astype('string')
                if not texto.str.fullmatch(r'\d{4}-\d{2}-\d{2}').fillna(False).all():
                    raise ValueError('Fecha clave Calendar no canónica')
            v, conteo = convertir(cast(pd.Series, f[col]), clase)
            audit['conversiones'][col] = conteo
            if clase == 'fecha':
                if coleccion == 'Calendar' and col == 'date' and v.isna().any():
                    raise ValueError('Fecha clave Calendar inválida')
                # %Y depende de libc y no siempre rellena años < 1000.
                f[col] = (v.dt.year.astype('Int64').astype('string').str.zfill(4)
                          + v.dt.strftime('-%m-%d').astype('string'))
                if col == 'date':
                    for nombre, valores in [('year', v.dt.year), ('month', v.dt.month),
                                            ('day', v.dt.day), ('quarter', v.dt.quarter)]:
                        f['date_' + nombre] = valores.astype('Int64')
            elif clase == 'booleano':
                f[col] = v.map({1.0: True, 0.0: False}).astype('boolean')
            else:
                f[col] = v.astype('Float64')
                dominio = pd.Series(False, index=f.index)
                if col in PRECIOS:
                    # Ingresos estimados pueden ser cero; un precio cero se
                    # señala para revisión, pero ninguno se descarta.
                    dominio = v < 0 if col == 'estimated_revenue_l365d' else v <= 0
                elif 'nights' in col and not col.endswith('avg_ntm'):
                    dominio = (v <= 0) | (v.notna() & v.mod(1).ne(0))
                elif col == 'availability_365':
                    dominio = (v < 0) | (v > 365) | (v.notna() & v.mod(1).ne(0))
                audit['dominios'][col] = int(dominio.sum())
        if coleccion == 'Listings' and 'price' in f:
            p = f.price
            categoria = pd.Series(pd.NA, index=f.index, dtype='string')
            for etiqueta, mascara in [('Q1', p <= Q1), ('Q2', (p > Q1) & (p <= MEDIANA)),
                                     ('Q3', (p > MEDIANA) & (p <= Q3)), ('Q4', p > Q3)]:
                categoria.loc[mascara.fillna(False)] = etiqueta
            f['price_category'] = categoria
            f['price_outlier'] = ((p < CERCA_INFERIOR) | (p > CERCA_SUPERIOR)).astype('boolean')
            audit['price_outliers'] = int(f.price_outlier.sum())
        tablas = {coleccion: f}
        if coleccion == 'Listings':
            filas = []
            cuenta = {'validos': 0, 'invalidos': 0, 'faltantes': 0,
                      'duplicados_intralista': 0}
            if 'amenities' in f:
                for identificador, valor in zip(f.id, f.amenities, strict=True):
                    if pd.isna(valor):
                        cuenta['faltantes'] += 1
                        continue
                    try:
                        lista = json.loads(valor)
                        if not isinstance(lista, list) or not all(isinstance(x, str) for x in lista):
                            raise ValueError('Amenities no textual')
                    except (ValueError, TypeError):
                        cuenta['invalidos'] += 1
                        continue
                    cuenta['validos'] += 1
                    cuenta['duplicados_intralista'] += len(lista) - len(set(lista))
                    filas.extend((identificador, x) for x in sorted(set(lista)))
            tablas['ListingAmenities'] = pd.DataFrame(filas, columns=['listing_id', 'amenity'])
            audit['amenities'] = cuenta
        self.logger.info('%s transformación: antes=%d después=%d; nulos, conversiones, '
                         'dominios, fechas y anidados auditados', coleccion, antes, len(f))
        problemas = sum(c['invalidos'] + c['no_finitos'] for c in audit['conversiones'].values())
        problemas += sum(audit['dominios'].values())
        problemas += audit.get('amenities', {}).get('invalidos', 0)
        if problemas:
            self.logger.warning('Transformación: %d errores de valores/dominio conservados '
                                'o convertidos a nulo; sin imputar', problemas)
        return Resultado(coleccion, tablas, audit)

    def preflight(self, extraccion: Any) -> dict:
        """Rechaza duplicados globales raw antes de consumir cualquier colección.

        Incluso duplicados idénticos globales rechazan: no se decide entre lotes.
        Claves exactas evitan equivalencias introducidas por normalización.
        La validez de claves se verifica además en cada lote (fail-fast).
        """
        try:
            self.logger.warning('Sin snapshot transaccional: no ejecutar con escritores concurrentes')
            resultado = {}
            for nombre in COLECCIONES:
                col = extraccion.db[nombre]
                total = col.count_documents({})
                if not total:
                    raise ValueError('Fuente ausente o vacía')
                d = duplicados(col, CLAVES[nombre])
                if d['grupos']:
                    raise ValueError('Duplicados globales ambiguos; transformación rechazada')
                resultado[nombre] = {'fuente': total, 'duplicados_clave': d}
            self.logger.info('Preflight global sin duplicados; claves exactas')
            return resultado
        except Exception as exc:
            self.logger.error('Preflight fallido (%s)', type(exc).__name__)
            raise

    def iterar(self, extraccion: Any, batch: int = 10000) -> Generator[Resultado, None, None]:
        """Genera tablas para futura Carga, cerrando el cursor si se abandona.

        Args:
            extraccion: Extraccion abierta; solo consultas de lectura.
            batch: Tamaño positivo; memoria acotada a un lote y su puente.
        Returns:
            Generador de Resultados; cerrar explícitamente si se abandona.
        """
        if batch <= 0:
            raise ValueError('batch debe ser positivo')
        self.preflight(extraccion)
        for nombre in COLECCIONES:
            lotes = extraccion.iterar(nombre, batch)
            try:
                for frame in lotes:
                    yield self.lote(nombre, frame)
            finally:
                lotes.close()
