
import time
import requests
import numpy as np
import pandas as pd


TZ_BR = "America/Sao_Paulo"
INTERVALO = "60m"
PERIODO = "730d"

PERIODO_EMA_RAPIDA = 9
PERIODO_EMA_LENTA = 21
PERIODO_ROMPIMENTO = 10
PERIODO_VOLUME = 20
MULTIPLICADOR_VOLUME = 1.2


def coletar_candles_intraday(
    ativo: str,
    tentativas: int = 3
) -> pd.DataFrame:
    """
    Coleta candles de 60 minutos do Yahoo Finance.
    Não modifica o CSV diário do analisador.
    """

    ticker = (
        ativo
        if ativo.endswith(".SA")
        else f"{ativo}.SA"
    )

    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{ticker}"
    )

    params = {
        "range": PERIODO,
        "interval": INTERVALO,
        "events": "history"
    }

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    erro = None

    for tentativa in range(tentativas):
        try:
            resposta = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=30
            )

            resposta.raise_for_status()
            payload = resposta.json()

            chart = payload.get("chart", {})

            if chart.get("error"):
                raise RuntimeError(str(chart["error"]))

            resultados = chart.get("result")

            if not resultados:
                raise ValueError(
                    f"Nenhum candle retornado para {ticker}."
                )

            resultado = resultados[0]
            timestamps = resultado.get("timestamp") or []

            cotacao = (
                resultado.get("indicators", {})
                .get("quote", [{}])[0]
            )

            if not timestamps:
                raise ValueError("Histórico intraday vazio.")

            datas = pd.to_datetime(
                timestamps,
                unit="s",
                utc=True
            ).tz_convert(TZ_BR)

            dados = pd.DataFrame({
                "Data": datas,
                "Abertura": cotacao.get("open"),
                "Maxima": cotacao.get("high"),
                "Minima": cotacao.get("low"),
                "Fechamento": cotacao.get("close"),
                "Volume": cotacao.get("volume")
            })

            colunas_numericas = [
                "Abertura",
                "Maxima",
                "Minima",
                "Fechamento",
                "Volume"
            ]

            for coluna in colunas_numericas:
                dados[coluna] = pd.to_numeric(
                    dados[coluna],
                    errors="coerce"
                )

            dados = (
                dados
                .dropna(subset=["Data"] + colunas_numericas)
                .sort_values("Data")
                .drop_duplicates("Data", keep="last")
                .reset_index(drop=True)
            )

            # Exclui candles que ainda não deveriam ter terminado.
            agora = pd.Timestamp.now(tz=TZ_BR)

            candle_encerrado = (
                dados["Data"] + pd.Timedelta(minutes=60)
                <= agora
            )

            dados = dados.loc[
                candle_encerrado
            ].reset_index(drop=True)

            if dados.empty:
                raise ValueError(
                    "Não há candles encerrados disponíveis."
                )

            return dados

        except Exception as exc:
            erro = exc

            if tentativa < tentativas - 1:
                time.sleep(2 * (tentativa + 1))

    raise RuntimeError(
        f"Falha ao coletar {ticker}: {erro}"
    )


def gerar_sinais_intraday(
    dados: pd.DataFrame
) -> pd.DataFrame:
    """
    Gera sinais após o fechamento de cada candle.

    Compra:
    tendência de alta + rompimento de máxima
    + confirmação de volume.

    Venda:
    tendência de baixa + rompimento de mínima
    + confirmação de volume.
    """

    dados = dados.copy()

    if dados.empty:
        return dados

    dados = dados.sort_values("Data").reset_index(drop=True)

    # Tendência
    dados["EMA9"] = dados["Fechamento"].ewm(
        span=PERIODO_EMA_RAPIDA,
        adjust=False
    ).mean()

    dados["EMA21"] = dados["Fechamento"].ewm(
        span=PERIODO_EMA_LENTA,
        adjust=False
    ).mean()

    dados["Tendencia"] = np.select(
        [
            (
                (dados["EMA9"] > dados["EMA21"])
                & (dados["Fechamento"] > dados["EMA21"])
            ),
            (
                (dados["EMA9"] < dados["EMA21"])
                & (dados["Fechamento"] < dados["EMA21"])
            )
        ],
        ["ALTA", "BAIXA"],
        default="LATERAL"
    )

    # Rompimento: usa somente os candles anteriores.
    dados["Maxima_anterior"] = (
        dados["Maxima"]
        .shift(1)
        .rolling(PERIODO_ROMPIMENTO)
        .max()
    )

    dados["Minima_anterior"] = (
        dados["Minima"]
        .shift(1)
        .rolling(PERIODO_ROMPIMENTO)
        .min()
    )

    # Volume médio dos 20 candles anteriores.
    dados["Volume_medio_anterior"] = (
        dados["Volume"]
        .shift(1)
        .rolling(PERIODO_VOLUME)
        .mean()
    )

    dados["Volume_confirmado"] = (
        dados["Volume"]
        > dados["Volume_medio_anterior"]
        * MULTIPLICADOR_VOLUME
    )

    compra = (
        (dados["Tendencia"] == "ALTA")
        & (
            dados["Fechamento"]
            > dados["Maxima_anterior"]
        )
        & dados["Volume_confirmado"]
    )

    venda = (
        (dados["Tendencia"] == "BAIXA")
        & (
            dados["Fechamento"]
            < dados["Minima_anterior"]
        )
        & dados["Volume_confirmado"]
    )

    dados["Sinal"] = np.select(
        [compra, venda],
        ["COMPRA", "VENDA"],
        default="SEM SINAL"
    )

    return dados
