
import time
import requests
import pandas as pd

from intraday import (
    coletar_candles_intraday,
    gerar_sinais_intraday
)


TZ_BR = "America/Sao_Paulo"


def coletar_candles_diarios(ativo, tentativas=3):
    """Coleta candles diários para calcular ondas históricas concluídas."""
    ticker = ativo.upper().strip()
    if not ticker.endswith(".SA"):
        ticker = f"{ticker}.SA"

    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{ticker}"
    )
    params = {"range": "5y", "interval": "1d", "events": "history"}
    headers = {"User-Agent": "Mozilla/5.0"}
    erro = None

    for tentativa in range(tentativas):
        try:
            resposta = requests.get(
                url, params=params, headers=headers, timeout=30
            )
            resposta.raise_for_status()
            payload = resposta.json()
            chart = payload.get("chart", {})
            if chart.get("error"):
                raise RuntimeError(str(chart["error"]))

            resultados = chart.get("result")
            if not resultados:
                raise ValueError(f"Nenhum candle diário retornado para {ticker}.")

            resultado = resultados[0]
            timestamps = resultado.get("timestamp") or []
            cotacoes = resultado.get("indicators", {}).get("quote", [{}])[0]
            if not timestamps:
                raise ValueError("Histórico diário vazio.")

            datas = pd.to_datetime(
                timestamps, unit="s", utc=True
            ).tz_convert(TZ_BR)

            diarios = pd.DataFrame({
                "Data": datas,
                "Abertura": cotacoes.get("open"),
                "Maxima": cotacoes.get("high"),
                "Minima": cotacoes.get("low"),
                "Fechamento": cotacoes.get("close"),
                "Volume": cotacoes.get("volume"),
            })

            colunas = ["Abertura", "Maxima", "Minima", "Fechamento", "Volume"]
            for coluna in colunas:
                diarios[coluna] = pd.to_numeric(diarios[coluna], errors="coerce")

            diarios = (
                diarios.dropna(subset=colunas)
                .sort_values("Data")
                .drop_duplicates("Data", keep="last")
                .reset_index(drop=True)
            )
            if diarios.empty:
                raise ValueError("Não há candles diários válidos.")

            # A MME21 é calculada exclusivamente com fechamentos diários.
            diarios["MME21"] = diarios["Fechamento"].ewm(
                span=21, adjust=False
            ).mean()
            return diarios

        except Exception as exc:
            erro = exc
            if tentativa < tentativas - 1:
                time.sleep(2 * (tentativa + 1))

    raise RuntimeError(f"Falha ao coletar candles diários de {ticker}: {erro}")


def auditar_sinais(dados):
    """
    Audita cada rejeição e verifica se houve confirmação
    nos dois candles seguintes.
    """

    dados = dados.reset_index(drop=True).copy()
