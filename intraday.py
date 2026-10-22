
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
    """
    Estratégia intraday:
    tendência MME21/MME200 + pullback + rejeição
    + confirmação por rompimento.

    O sinal é registrado no fechamento do candle
    que confirma o rompimento.
    """

    dados = dados.copy()

    if dados.empty:
        return dados

    dados = (
        dados.sort_values("Data")
        .reset_index(drop=True)
    )

    # --------------------------------------------------
    # 1. MÉDIAS MÓVEIS
    # --------------------------------------------------

    dados["MME21"] = dados["Fechamento"].ewm(
        span=PERIODO_MME21,
        adjust=False
    ).mean()

    dados["MME200"] = dados["Fechamento"].ewm(
        span=PERIODO_MME200,
        adjust=False
    ).mean()

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

    # --------------------------------------------------
    # 2. ATR DE 14 CANDLES
    # --------------------------------------------------

    fechamento_anterior = dados["Fechamento"].shift(1)

    tr1 = dados["Maxima"] - dados["Minima"]

    tr2 = (
        dados["Maxima"] - fechamento_anterior
    ).abs()

    tr3 = (
        dados["Minima"] - fechamento_anterior
    ).abs()

    dados["TR"] = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)

    dados["ATR14"] = dados["TR"].rolling(14).mean()

    # --------------------------------------------------
    # 3. VOLUME: MÉDIA DOS 20 CANDLES ANTERIORES
    # --------------------------------------------------

    dados["Volume_medio_anterior"] = (
        dados["Volume"]
        .shift(1)
        .rolling(20)
        .mean()
    )

    dados["Volume_confirmado"] = (
        dados["Volume"]
        >= dados["Volume_medio_anterior"]
    )

    # --------------------------------------------------
    # 4. FORMATO DO CANDLE
    # --------------------------------------------------

    corpo = (
        dados["Fechamento"] - dados["Abertura"]
    ).abs()

    amplitude = dados["Maxima"] - dados["Minima"]

    pavio_inferior = (
        pd.concat(
            [dados["Abertura"], dados["Fechamento"]],
            axis=1
        ).min(axis=1)
        - dados["Minima"]
    )

    pavio_superior = (
        dados["Maxima"]
        - pd.concat(
            [dados["Abertura"], dados["Fechamento"]],
            axis=1
        ).max(axis=1)
    )

    # Fechamento no quarto superior ou inferior do candle.
    fechamento_perto_maxima = (
        dados["Fechamento"]
        >= dados["Minima"] + 0.75 * amplitude
    )

    fechamento_perto_minima = (
        dados["Fechamento"]
        <= dados["Minima"] + 0.25 * amplitude
    )

    # --------------------------------------------------
    # 5. PULLBACK + REJEIÇÃO
    # --------------------------------------------------

    distancia_maxima = 0.3 * dados["ATR14"]

    pullback_compra = (
        (dados["Minima"] <= dados["MME21"] + distancia_maxima)
        & (dados["Minima"] >= dados["MME21"] - distancia_maxima)
    )

    pullback_venda = (
        (dados["Maxima"] >= dados["MME21"] - distancia_maxima)
        & (dados["Maxima"] <= dados["MME21"] + distancia_maxima)
    )

    rejeicao_compra = (
        (dados["Tendencia"] == "ALTA")
        & pullback_compra
        & (pavio_inferior >= corpo)
        & fechamento_perto_maxima
        & dados["Volume_confirmado"]
        & (amplitude > 0)
    )

    rejeicao_venda = (
        (dados["Tendencia"] == "BAIXA")
        & pullback_venda
        & (pavio_superior >= corpo)
        & fechamento_perto_minima
        & dados["Volume_confirmado"]
        & (amplitude > 0)
    )

    dados["Rejeicao"] = np.select(
        [rejeicao_compra, rejeicao_venda],
        ["COMPRA", "VENDA"],
        default="NENHUMA"
    )

    # --------------------------------------------------
    # 6. CONFIRMAÇÃO EM ATÉ DOIS CANDLES POSTERIORES
    # --------------------------------------------------

    dados["Sinal"] = "SEM SINAL"

    dados.loc[
        rejeicao_compra | rejeicao_venda,
        "Sinal"
    ] = "AGUARDANDO CONFIRMAÇÃO"

    # Confirmação somente em candle posterior.
    for i in range(2, len(dados)):

        # Compra: fechamento cruza a máxima do candle
        # de rejeição, ocorrido um ou dois candles antes.
        if dados.loc[i, "Tendencia"] == "ALTA":

            for distancia in (1, 2):
                j = i - distancia

                if dados.loc[j, "Rejeicao"] != "COMPRA":
                    continue

                if dados.loc[i - 1, "Fechamento"] <= dados.loc[j, "Maxima"] \
                        and dados.loc[i, "Fechamento"] > dados.loc[j, "Maxima"]:

                    dados.loc[i, "Sinal"] = "COMPRA CONFIRMADA"
                    break

        # Venda: fechamento cruza a mínima do candle
        # de rejeição, ocorrido um ou dois candles antes.
        if dados.loc[i, "Tendencia"] == "BAIXA":

            for distancia in (1, 2):
                j = i - distancia

                if dados.loc[j, "Rejeicao"] != "VENDA":
                    continue

                if dados.loc[i - 1, "Fechamento"] >= dados.loc[j, "Minima"] \
                        and dados.loc[i, "Fechamento"] < dados.loc[j, "Minima"]:

                    dados.loc[i, "Sinal"] = "VENDA CONFIRMADA"
                    break

    return dados


    return dados
