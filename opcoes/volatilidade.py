
"""
Módulo de volatilidade do Analisador de Opções B3.

Calcula:
- Volatilidade histórica (HV).
- Volatilidade implícita (IV), quando fornecida.
- ATR.
- Velocidade histórica de movimentação.

Não confunde volatilidade histórica com implícita.
"""

import math

import pandas as pd

from opcoes.configuracao import (
    PERIODO_VOLATILIDADE_HISTORICA,
    PERIODO_ATR,
    DIAS_UTEIS_ANO,
)


class ErroVolatilidade(Exception):
    """Erro nos cálculos de volatilidade."""


def validar_precos(df):
    """Valida a série histórica de preços."""

    if not isinstance(df, pd.DataFrame):
        raise ErroVolatilidade(
            "Os preços devem ser fornecidos em um DataFrame."
        )

    if "Fechamento" not in df.columns:
        raise ErroVolatilidade(
            "Coluna Fechamento não encontrada."
        )

    if df.empty:
        raise ErroVolatilidade(
            "A série histórica está vazia."
        )


def calcular_volatilidade_historica(
    df,
    periodo=PERIODO_VOLATILIDADE_HISTORICA
):
    """
    Calcula HV anualizada pela volatilidade dos retornos logarítmicos.

    Retorno em formato decimal:
    0.30 = 30% ao ano.
    """

    validar_precos(df)

    if periodo < 2:
        raise ErroVolatilidade(
            "O período deve ser de pelo menos 2 observações."
        )

    precos = pd.to_numeric(
        df["Fechamento"],
        errors="coerce"
    ).dropna()

    if (precos <= 0).any():
        raise ErroVolatilidade(
            "Os preços devem ser positivos."
        )

    retornos = (
        (precos / precos.shift(1))
        .apply(math.log)
        .dropna()
    )

    if len(retornos) < periodo:
        return None

    hv = retornos.tail(periodo).std(ddof=1) * math.sqrt(
        DIAS_UTEIS_ANO
    )

    return float(hv)


def validar_iv(iv):
    """Valida uma volatilidade implícita fornecida pela fonte."""

    if iv is None:
        return None

    try:
        iv = float(iv)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(iv) or iv <= 0:
        return None

    return iv


def calcular_atr(
    df,
    periodo=PERIODO_ATR
):
    """Calcula o Average True Range."""

    validar_precos(df)

    colunas = ["Maxima", "Minima", "Fechamento"]

    if not all(coluna in df.columns for coluna in colunas):
        raise ErroVolatilidade(
            "São necessárias as colunas Maxima, Minima e Fechamento."
        )

    if periodo < 1:
        raise ErroVolatilidade(
            "O período do ATR deve ser positivo."
        )

    dados = df[colunas].apply(
        pd.to_numeric,
        errors="coerce"
    ).dropna()

    if len(dados) < periodo + 1:
        return None

    fechamento_anterior = dados["Fechamento"].shift(1)

    true_range = pd.concat(
        [
            dados["Maxima"] - dados["Minima"],
            (dados["Maxima"] - fechamento_anterior).abs(),
            (dados["Minima"] - fechamento_anterior).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr = true_range.ewm(
        alpha=1 / periodo,
        adjust=False,
        min_periods=periodo
    ).mean().iloc[-1]

    if pd.isna(atr):
        return None

    return float(atr)


def calcular_velocidade(df, periodo=5):
    """
    Calcula a movimentação percentual média por pregão.

    É uma medida histórica simples, não uma previsão.
    """

    validar_precos(df)

    precos = pd.to_numeric(
        df["Fechamento"],
        errors="coerce"
    ).dropna()

    if periodo < 1 or len(precos) <= periodo:
        return None

    variacao = (
        precos.iloc[-1] / precos.iloc[-periodo - 1]
    ) - 1

    velocidade = (
        (1 + variacao) ** (1 / periodo)
    ) - 1

    return float(velocidade)


def analisar_volatilidade(df, iv=None):
    """
    Consolida os indicadores de volatilidade.

    A IV somente será informada quando houver um valor
    válido fornecido pela fonte de dados.
    """

    hv = calcular_volatilidade_historica(df)
    atr = calcular_atr(df)
    velocidade = calcular_velocidade(df)

    fechamento = float(
        pd.to_numeric(
            df["Fechamento"],
            errors="coerce"
        ).dropna().iloc[-1]
    )

    iv_validada = validar_iv(iv)

    return {
        "hv_anualizada": hv,
        "iv_anualizada": iv_validada,
        "iv_disponivel": iv_validada is not None,
        "atr": atr,
        "velocidade_media_por_pregao": velocidade,
        "atr_percentual": (
            atr / fechamento
            if atr is not None and fechamento > 0
            else None
        ),
        "dias_uteis_ano": DIAS_UTEIS_ANO,
    }

