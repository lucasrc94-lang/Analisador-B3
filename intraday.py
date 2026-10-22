
import time
import requests
import numpy as np
import pandas as pd


TZ_BR = "America/Sao_Paulo"
INTERVALO = "60m"
PERIODO = "730d"

PERIODO_MME21 = 21
PERIODO_MME200 = 200
PERIODO_ROMPIMENTO = 10
PERIODO_VOLUME = 20
MULTIPLICADOR_VOLUME = 1.2


def coletar_candles_intraday(
    ativo: str,
    tentativas: int = 3
) -> pd.DataFrame:
    """Coleta candles de 60 minutos sem alterar os dados diários."""

    ticker = ativo.upper().strip()

    if not ticker.endswith(".SA"):
        ticker = f"{ticker}.SA"

    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{ticker}"
    )

    params = {
        "range": PERIODO,
        "interval": INTERVALO,
        "events": "history"
    }

    headers = {"User-Agent": "Mozilla/5.0"}
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

            cotacoes = (
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
                "Abertura": cotacoes.get("open"),
                "Maxima": cotacoes.get("high"),
                "Minima": cotacoes.get("low"),
                "Fechamento": cotacoes.get("close"),
                "Volume": cotacoes.get("volume")
            })

            colunas = [
                "Abertura",
                "Maxima",
                "Minima",
                "Fechamento",
                "Volume"
            ]

            for coluna in colunas:
                dados[coluna] = pd.to_numeric(
                    dados[coluna],
                    errors="coerce"
                )

            dados = (
                dados
                .dropna(subset=colunas)
                .sort_values("Data")
                .drop_duplicates("Data", keep="last")
                .reset_index(drop=True)
            )

            # Mantém apenas candles cuja hora de encerramento passou.
            agora = pd.Timestamp.now(tz=TZ_BR)

            encerrado = (
                dados["Data"] + pd.Timedelta(minutes=60)
                <= agora
            )

            dados = dados.loc[encerrado].reset_index(drop=True)

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
    """Calcula tendência, rompimento, volume e sinais."""

    dados = dados.copy()

    if dados.empty:
        return dados

    dados = (
        dados
        .sort_values("Data")
        .reset_index(drop=True)
    )

    # Médias móveis exponenciais.
    dados["MME21"] = dados["Fechamento"].ewm(
        span=PERIODO_MME21,
        adjust=False
    ).mean()

    dados["MME200"] = dados["Fechamento"].ewm(
        span=PERIODO_MME200,
        adjust=False
    ).mean()

    # Tendência.
    dados["Tendencia"] = np.select(
        [
            (
                (dados["MME21"] > dados["MME200"])
                & (dados["Fechamento"] > dados["MME21"])
            ),
            (
                (dados["MME21"] < dados["MME200"])
                & (dados["Fechamento"] < dados["MME21"])
            )
        ],
        ["ALTA", "BAIXA"],
        default="LATERAL"
    )

    # Rompimento calculado apenas com candles anteriores.
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

    # Volume médio dos candles anteriores.
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

    # Compra: tendência de alta, rompimento e volume.
    compra = (
        (dados["Tendencia"] == "ALTA")
        & (
            dados["Fechamento"]
            > dados["Maxima_anterior"]
        )
        & dados["Volume_confirmado"]
    )

    # Venda: tendência de baixa, rompimento e volume.
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
