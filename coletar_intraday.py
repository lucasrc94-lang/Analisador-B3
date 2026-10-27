"""Coleta e resume candles intraday do Yahoo Finance, sem alterar o motor diário."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "dados"
TZ_BR = ZoneInfo("America/Sao_Paulo")
COLUNAS = ["Data", "Abertura", "Maxima", "Minima", "Fechamento", "Volume"]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125 Safari/537.36"
}

# Yahoo costuma limitar 15m a aproximadamente 60 dias. 60m usa uma janela menor
# que o limite histórico usual, para reduzir falhas e manter o volume de dados controlado.
CONFIG = {
    "1h": {"interval": "60m", "range": "6mo", "min_candles": 200},
    "15m": {"interval": "15m", "range": "60d", "min_candles": 200},
}


def _baixar_candles(ativo: str, intervalo: str, periodo: str, tentativas: int = 3) -> pd.DataFrame:
    ticker = ativo if ativo.endswith(".SA") else f"{ativo}.SA"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {"range": periodo, "interval": intervalo, "events": "history"}
    ultimo_erro: Exception | None = None

    for tentativa in range(tentativas):
        try:
            resposta = requests.get(url, params=params, headers=HEADERS, timeout=30)
            resposta.raise_for_status()
            payload = resposta.json().get("chart", {})
            if payload.get("error"):
                raise RuntimeError(str(payload["error"]))
            resultados = payload.get("result") or []
            if not resultados:
                raise ValueError(f"Yahoo Finance não retornou candles para {ticker} ({intervalo}).")

            resultado = resultados[0]
            timestamps = resultado.get("timestamp") or []
            if not timestamps:
                raise ValueError(f"Histórico intraday vazio para {ticker} ({intervalo}).")

            datas = pd.to_datetime(timestamps, unit="s", utc=True).tz_convert(TZ_BR)
            quote = resultado.get("indicators", {}).get("quote", [{}])[0]
            df = pd.DataFrame({
                "Data": datas.strftime("%Y-%m-%d %H:%M:%S%z"),
                "Abertura": quote.get("open"),
                "Maxima": quote.get("high"),
                "Minima": quote.get("low"),
                "Fechamento": quote.get("close"),
                "Volume": quote.get("volume"),
            })
            df = df[COLUNAS]
            for coluna in COLUNAS[1:]:
                df[coluna] = pd.to_numeric(df[coluna], errors="coerce")
            df = df.dropna(subset=COLUNAS).drop_duplicates("Data", keep="last").sort_values("Data")
            if df.empty:
                raise ValueError(f"Nenhum candle válido para {ticker} ({intervalo}).")

            destino = DATA_DIR / f"{ativo}_{'1h' if intervalo == '60m' else '15m'}.csv"
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            if destino.exists():
                antigo = pd.read_csv(destino)
                if all(coluna in antigo.columns for coluna in COLUNAS):
                    combinado = pd.concat([antigo[COLUNAS], df], ignore_index=True)
                    for coluna in COLUNAS[1:]:
                        combinado[coluna] = pd.to_numeric(combinado[coluna], errors="coerce")
                    combinado = combinado.dropna(subset=COLUNAS).drop_duplicates("Data", keep="last").sort_values("Data")
                    df = combinado[COLUNAS]
            df.to_csv(destino, index=False)
            return df.reset_index(drop=True)
        except Exception as erro:
            ultimo_erro = erro
            if tentativa < tentativas - 1:
                time.sleep(2 * (tentativa + 1))

    raise RuntimeError(f"Falha ao coletar {ticker} ({intervalo}): {ultimo_erro}")


def _analisar_candles(dados: pd.DataFrame, intervalo_nome: str) -> dict[str, Any]:
    df = dados.copy()
    for coluna in ["Abertura", "Maxima", "Minima", "Fechamento", "Volume"]:
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce")
    df = df.dropna(subset=["Maxima", "Minima", "Fechamento", "Volume"]).sort_values("Data")

    if df.empty:
        raise ValueError("Não há candles válidos para analisar.")

    df["MME21"] = df["Fechamento"].ewm(span=21, adjust=False).mean()
    df["MME200"] = df["Fechamento"].ewm(span=200, adjust=False, min_periods=200).mean()
    fechamento_anterior = df["Fechamento"].shift(1)
    tr = pd.concat([
        df["Maxima"] - df["Minima"],
        (df["Maxima"] - fechamento_anterior).abs(),
        (df["Minima"] - fechamento_anterior).abs(),
    ], axis=1).max(axis=1)
    df["ATR14"] = tr.rolling(14, min_periods=14).mean()
    df["VolumeMedia20"] = df["Volume"].rolling(20, min_periods=20).mean()

    atual = df.iloc[-1]
    preco = float(atual["Fechamento"])
    mme21 = float(atual["MME21"]) if pd.notna(atual["MME21"]) else None
    mme200 = float(atual["MME200"]) if pd.notna(atual["MME200"]) else None

    if mme200 is None or mme21 is None:
        tendencia = "DADOS INSUFICIENTES"
    elif preco > mme21 and mme21 > mme200:
        tendencia = "ALTA"
    elif preco < mme21 and mme21 < mme200:
        tendencia = "BAIXA"
    else:
        tendencia = "NEUTRA / MISTA"

    def numero(valor):
        return float(valor) if pd.notna(valor) else None

    return {
        "intervalo": intervalo_nome,
        "candles_disponiveis": int(len(df)),
        "ultimo_candle": str(atual["Data"]),
        "preco": preco,
        "mme21": mme21,
        "mme200": mme200,
        "atr14": numero(atual["ATR14"]),
        "volume": numero(atual["Volume"]),
        "volume_medio20": numero(atual["VolumeMedia20"]),
        "tendencia": tendencia,
        "fonte": "Yahoo Finance chart API; intraday sujeito a atraso, limites e indisponibilidade",
    }


def coletar_e_analisar_intraday(ativo: str) -> dict[str, Any]:
    """Coleta 1h e 15m. Erros de um intervalo não impedem o outro."""
    saida: dict[str, Any] = {}
    for nome, config in CONFIG.items():
        try:
            dados = _baixar_candles(ativo, config["interval"], config["range"])
            minimo = config["min_candles"]
            if len(dados) < minimo:
                raise ValueError(f"Apenas {len(dados)} candles válidos; recomendado mínimo de {minimo}.")
            saida[nome] = _analisar_candles(dados, nome)
        except Exception as erro:
            saida[nome] = {"status": "ERRO", "erro": str(erro)}
    return saida
