"""Coleta cotações diárias, executa o motor técnico e grava dados para o painel."""
from __future__ import annotations
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from motor import analisar, calcular_indicadores

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "dados"
OUTPUT_FILE = DATA_DIR / "analises.json"
TZ_BR = ZoneInfo("America/Sao_Paulo")
COLUNAS = ["Data", "Abertura", "Maxima", "Minima", "Fechamento", "Volume"]


def ler_ativos() -> list[str]:
    arquivo = ROOT / "ativos.txt"
    ativos = []
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        ticker = linha.split("#", 1)[0].strip().upper().replace(".SA", "")
        if ticker and ticker not in ativos:
            ativos.append(ticker)
    if not ativos:
        raise ValueError("O arquivo ativos.txt não contém nenhum ticker.")
    return ativos


def coletar_dados(ativo: str, tentativas: int = 3) -> pd.DataFrame:
    ticker = ativo if ativo.endswith(".SA") else f"{ativo}.SA"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {"range": "5y", "interval": "1d", "events": "history"}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125 Safari/537.36"}
    erro = None
    for tentativa in range(tentativas):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=30)
            resp.raise_for_status()
            payload = resp.json()
            chart = payload.get("chart", {})
            if chart.get("error"):
                raise RuntimeError(str(chart["error"]))
            result = chart.get("result")
            if not result:
                raise ValueError(f"Yahoo Finance não retornou dados para {ticker}.")
            result = result[0]
            timestamps = result.get("timestamp") or []
            quote = result.get("indicators", {}).get("quote", [{}])[0]
            if not timestamps:
                raise ValueError(f"Histórico vazio para {ticker}.")
            datas = pd.to_datetime(timestamps, unit="s", utc=True).tz_convert(TZ_BR).date
            df = pd.DataFrame({
                "Data": pd.to_datetime(datas).strftime("%Y-%m-%d"),
                "Abertura": quote.get("open"),
                "Maxima": quote.get("high"),
                "Minima": quote.get("low"),
                "Fechamento": quote.get("close"),
                "Volume": quote.get("volume"),
            })
            
            df = df[COLUNAS].dropna(subset=["Data", "Abertura", "Maxima", "Minima", "Fechamento", "Volume"])
            for c in COLUNAS[1:]:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            df = df.dropna().drop_duplicates("Data", keep="last").sort_values("Data")
            if len(df) < 220:
                raise ValueError(f"{ticker}: apenas {len(df)} pregões válidos; são necessários 220 para MME200 e análise robusta.")
            destino = DATA_DIR / f"{ativo}.csv"
            destino.parent.mkdir(parents=True, exist_ok=True)
            # Reconciliar com histórico salvo, mantendo a cotação mais recente por data.
            if destino.exists():
                antigo = pd.read_csv(destino)
                antigo = antigo[[c for c in COLUNAS if c in antigo.columns]]
                combinado = pd.concat([antigo, df], ignore_index=True)
                combinado["Data"] = pd.to_datetime(combinado["Data"], errors="coerce").dt.strftime("%Y-%m-%d")
                combinado = combinado.dropna(subset=COLUNAS).drop_duplicates("Data", keep="last").sort_values("Data")
                df = combinado[COLUNAS]
            df["Data"] = pd.to_datetime(df["Data"]).dt.strftime("%Y-%m-%d")
            df[COLUNAS[1:5]] = df[COLUNAS[1:5]].round(2)
            df.to_csv(destino, index=False)
            return df.reset_index(drop=True)
        except Exception as exc:
            erro = exc
            if tentativa < tentativas - 1:
                time.sleep(2 * (tentativa + 1))
    raise RuntimeError(f"Falha ao coletar {ticker}: {erro}")


def json_safe(value: Any):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items() if k != "colunas" and k != "boxes"}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    if hasattr(value, "item"):
        try:
            value = value.item()
        except Exception:
            pass
    if isinstance(value, float) and (pd.isna(value) or value in (float("inf"), float("-inf"))):
        return None
    if pd.isna(value) if not isinstance(value, (dict, list, tuple)) else False:
        return None
    return value


def simplificar(resultado: dict, ativo: str) -> dict:
    niveis = resultado.get("niveis", {})
    alvo = resultado.get("alvo", {})
    proj = resultado.get("projecoes", {})
    ultima = niveis.get("ultima_coluna") or {}
    return json_safe({
        "ativo": ativo,
        "data": resultado.get("data"),
        "preco": resultado.get("preco"),
        "mme21": resultado.get("mme21"),
        "mme200": resultado.get("mme200"),
        "atr14": resultado.get("atr"),
        "volume": resultado.get("volume"),
        "volume_medio20": resultado.get("volume_medio"),
        "volume_relativo": resultado.get("volume_relativo"),
        "velocidade": resultado.get("velocidade"),
        "velocidade_classificacao": resultado.get("velocidade_classificacao"),
        "tendencia": resultado.get("tendencia"),
        "aceleracao": resultado.get("aceleracao"),
        "box_pnf": niveis.get("box"),
        "colunas_pnf": len(niveis.get("colunas", [])),
        "ultima_coluna_pnf": ultima.get("tipo"),
        "topo_pnf": ultima.get("topo"),
        "fundo_pnf": ultima.get("fundo"),
        "suporte_pnf": niveis.get("suporte"),
        "resistencia_pnf": niveis.get("resistencia"),
        
        "situacao_preco": (
            resultado.get("situacao_preco") or {}
        ).get("situacao_preco"),

        "distancia_suporte_atr": (
            resultado.get("situacao_preco") or {}
        ).get("distancia_suporte_atr"),

        "distancia_resistencia_atr": (
            resultado.get("situacao_preco") or {}
        ).get("distancia_resistencia_atr"),
        
        "alvo_tecnico": alvo.get("alvo"),
        "distancia_alvo": alvo.get("distancia"),
        "distancia_alvo_atr": alvo.get("distancia_atr"),

        "alvo_amplitude_historica": (
            resultado.get("projecao_historica") or {}
        ).get("alvo_amplitude_historica"),

        "alvo_percentual_historico": (
            resultado.get("projecao_historica") or {}
        ).get("alvo_percentual_historico"),

        "media_amplitude_historica": (
            resultado.get("projecao_historica") or {}
        ).get("media_amplitude_historica"),

        "media_amplitude_pct_historica": (
            resultado.get("projecao_historica") or {}
        ).get("media_amplitude_pct_historica"),

        "tempo_medio_movimento": (
            resultado.get("projecao_historica") or {}
        ).get("tempo_medio_movimento"),

        "movimentos_historicos": (
            resultado.get("projecao_historica") or {}
        ).get("movimentos_historicos"),

        "pregoes_estimados": resultado.get(
        "pregoes_estimados_historico"
),
        "tipo_alvo": alvo.get("tipo"),
        "projecao_atr1": proj.get("ATR1"),
        "projecao_atr2": proj.get("ATR2"),
        "projecao_atr3": proj.get("ATR3"),
    })


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ativos = ler_ativos()
    resultados = []
    erros = []
    for ativo in ativos:
        try:
            dados = coletar_dados(ativo)
            resultado = analisar(dados)
            if not resultado:
                raise ValueError("Motor não conseguiu produzir uma análise (ATR/histórico insuficiente).")
            resultados.append(simplificar(resultado, ativo))
            print(f"OK {ativo}: {resultado['data']} | preço={resultado['preco']}")
        except Exception as exc:
            erros.append({"ativo": ativo, "erro": str(exc)})
            print(f"ERRO {ativo}: {exc}")
    documento = {
        "gerado_em_utc": datetime.now(timezone.utc).isoformat(),
        "gerado_em_brasilia": datetime.now(TZ_BR).isoformat(),
        "fonte": "Yahoo Finance chart API; dados diários, sujeitos a atraso/indisponibilidade",
        "ativos_configurados": ativos,
        "quantidade_analisada": len(resultados),
        "resultados": resultados,
        "erros": erros,
    }
    OUTPUT_FILE.write_text(json.dumps(documento, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    if not resultados:
        raise SystemExit("Nenhum ativo foi analisado; verifique os erros no log do workflow.")
    print(f"Painel atualizado: {len(resultados)} ativos; erros: {len(erros)}")

if __name__ == "__main__":
    main()
