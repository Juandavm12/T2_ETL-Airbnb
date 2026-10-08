"""Perfiles completos por lotes y conversiones temporales, sin modificar MongoDB."""
import json
from collections import Counter
from typing import Any, cast

import numpy as np
import pandas as pd

MARCADORES = {'NA', 'N/A', 'NULL', 'NAN', 'NONE'}


class Perfil:
    """Acumula tipos y ausencia por columna sin conservar registros."""

    def __init__(self) -> None:
        self.filas = 0
        self.columnas: dict[str, Counter] = {}

    def agregar(self, frame: pd.DataFrame) -> None:
        """Incluye un lote completo y contabiliza columnas ausentes."""
        for col in set(self.columnas) - set(frame.columns):
            self.columnas[col]['ausente'] += len(frame)
        for col in frame:
            if col not in self.columnas:
                self.columnas[col] = Counter(ausente=self.filas)
            s: Any = frame[col]
            c = self.columnas[col]
            c['null'] += int(s.isna().sum())
            texto = s.astype('string').str.strip()
            c['vacio'] += int(texto.eq('').sum())
            c['marcador_candidato'] += int(texto.str.upper().isin(MARCADORES).sum())
            for tipo, n in s.map(lambda x: type(x).__name__).value_counts().items():
                c['tipo:' + str(tipo)] += int(n)
        self.filas += len(frame)

    def resultado(self) -> dict:
        """Devuelve un resumen JSON estable, independiente del tamaño de lote."""
        return {'filas': self.filas, 'n_columnas': len(self.columnas),
                'columnas': {k: dict(sorted(v.items()))
                             for k, v in sorted(self.columnas.items())}}


def convertir(s: pd.Series, clase: str = 'numero') -> tuple[pd.Series, dict]:
    """Convierte una copia; distingue ausencia, errores y números no finitos.

    Los marcadores textuales son candidatos, no ausencia automática.
    Precio acepta dólar opcional y comas de miles, no comas decimales.
    """
    t = s.astype('string').str.strip()
    falta = s.isna() | t.eq('').fillna(False)
    no_finito = pd.Series(False, index=s.index)
    if clase == 'fecha':
        formato = t.str.fullmatch(r'\d{4}-\d{2}-\d{2}').fillna(False)
        v = pd.to_datetime(t.where(formato), format='%Y-%m-%d', errors='coerce')
    elif clase == 'booleano':
        v = t.map({'t': 1.0, 'f': 0.0})
    else:
        if clase == 'precio':
            formato = t.str.fullmatch(
                r'\$?[+-]?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?'
            ).fillna(False)
            especial = t.str.lower().isin({'inf', '-inf', '+inf', 'infinity'})
            t = t.where(formato | especial).str.replace('$', '', regex=False)
            t = t.str.replace(',', '', regex=False)
        v = cast(Any, pd.to_numeric(t, errors='coerce')).astype(float)
        no_finito = v.notna() & ~np.isfinite(v)
        v = v.mask(no_finito)
    valido = v.notna()
    return v, {'validos': int(valido.sum()), 'faltantes': int(falta.sum()),
               'invalidos': int((~valido & ~falta & ~no_finito).sum()),
               'no_finitos': int(no_finito.sum())}


def iqr(s: pd.Series) -> dict:
    """Cuenta valores fuera de cercas estrictas 1,5 IQR, sin descartarlos."""
    v = s.dropna()
    q1, q3 = v.quantile([.25, .75])
    inferior, superior = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
    return {'n': len(v), 'q1': float(q1), 'q3': float(q3),
            'inferior': float(inferior), 'superior': float(superior),
            'atipicos': int(((v < inferior) | (v > superior)).sum())}


def describir_frecuencias(frecuencias: dict) -> dict:
    """Descriptivos e IQR exactos de frecuencias completas, sin expandir filas.

    Usa cuantiles con interpolación lineal, equivalente al default pandas.
    Memoria proporcional al número de valores distintos, no a filas.
    """
    n = sum(frecuencias.values())
    if not n:
        return {'n': 0}
    orden = sorted(frecuencias)

    def valor_posicion(posicion: int) -> float:
        acumulado = 0
        for valor in orden:
            acumulado += frecuencias[valor]
            if posicion < acumulado:
                return float(valor)
        raise ValueError('Posición fuera del histograma')

    def cuantil(q: float) -> float:
        posicion = (n - 1) * q
        bajo, alto = int(np.floor(posicion)), int(np.ceil(posicion))
        return valor_posicion(bajo) + (posicion - bajo) * (
            valor_posicion(alto) - valor_posicion(bajo))

    q1, q3 = cuantil(.25), cuantil(.75)
    inferior, superior = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
    return {'n': n, 'min': float(orden[0]), 'max': float(orden[-1]),
            'media': sum(k * v for k, v in frecuencias.items()) / n,
            'mediana': cuantil(.5), 'q1': q1, 'q3': q3,
            'inferior': inferior, 'superior': superior,
            'atipicos': sum(v for k, v in frecuencias.items()
                           if k < inferior or k > superior)}


def duplicados(coleccion: Any, claves: list[str]) -> dict:
    """Cuenta grupos y exceso exactos en servidor; propaga timeout, nunca cero falso."""
    pipeline = [
        {'$group': {'_id': {k: '$' + k for k in claves}, 'n': {'$sum': 1}}},
        {'$match': {'n': {'$gt': 1}}},
        {'$group': {'_id': None, 'grupos': {'$sum': 1},
                    'exceso': {'$sum': {'$subtract': ['$n', 1]}},
                    'filas': {'$sum': '$n'}}},
        {'$project': {'_id': 0}},
    ]
    r = list(coleccion.aggregate(pipeline, allowDiskUse=True, maxTimeMS=300000))
    return r[0] if r else {'grupos': 0, 'exceso': 0, 'filas': 0}


def amenities(s: pd.Series) -> dict:
    """Cuenta presencia por anuncio de listas JSON de strings; informa errores."""
    cuenta = Counter()
    validos = invalidos = vacios = 0
    for valor in s:
        if pd.isna(valor) or not str(valor).strip():
            vacios += 1
            continue
        try:
            lista = json.loads(valor)
            if not isinstance(lista, list) or not all(isinstance(x, str) for x in lista):
                raise ValueError('Lista no textual')
        except (ValueError, TypeError):
            invalidos += 1
            continue
        validos += 1
        cuenta.update(set(lista))
    return {'validos': validos, 'invalidos': invalidos, 'vacios': vacios,
            'top': dict(sorted(cuenta.items(), key=lambda x: (-x[1], x[0]))[:15])}
