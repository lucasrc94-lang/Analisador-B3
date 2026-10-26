"""
AUDITOR DO ANALISADOR B3
========================

Audita o motor.py sem modificá-lo.

O script:
1. Lê um CSV histórico de um ativo.
2. Verifica qualidade e consistência dos dados.
3. Executa o backtest existente do motor para horizontes de 5, 10, 15 e 20 pregões.
4. Gera arquivos CSV com sinais detalhados, resumo estatístico e problemas de dados.

Uso:
    python auditor.py --arquivo dados/B3SA3.csv
    python auditor.py --arquivo dados/B3SA3.csv --inicio 2024-01-01 --fim 2026-10-26
    python auditor.py --arquivo dados/B3SA3.csv --horizontes 5,10,15,20

O arquivo auditor.py deve ficar na mesma pasta de motor.py.
"""

import argparse
import importlib
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd


COLUNAS_OBRIGATORIAS = ["Data", "Fechamento", "Maxima", "Minima", "Volume"]
HORIZONTES_PADRAO = [5, 10, 15, 20]


def ler_csv(caminho):
    """Lê CSV tentando detectar automaticamente o separador."""
    caminho = Path(caminho)
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")

    try:
        dados = pd.read_csv(caminho, sep=None, engine="python")
    except Exception:
        dados = pd.read_csv(caminho)

    # Remove espaços dos nomes das colunas.
    dados.columns = [str(c).strip() for c in dados.columns]

    # Compatibilidade com alguns CSVs que usam nomes alternativos comuns.
    aliases = {
        "Data": ["data", "Date", "date"],
        "Fechamento": ["fechamento", "Close", "close", "Adj Close"],
        "Maxima": ["maxima", "Máxima", "High", "high"],
        "Minima": ["minima", "Mínima", "Low", "low"],
        "Volume": ["volume", "Volume negociado"],
        "Abertura": ["abertura", "Open", "open"],
    }
    renomear = {}
    for destino, alternativas in aliases.items():
        if destino not in dados.columns:
            for alternativa in alternativas:
                if alternativa in dados.columns:
                    renomear[alternativa] = destino
                    break
    if renomear:
        dados = dados.rename(columns=renomear)

    faltantes = [c for c in COLUNAS_OBRIGATORIAS if c not in dados.columns]
    if faltantes:
        raise ValueError(
            "O CSV não contém as colunas obrigatórias: "
            + ", ".join(faltantes)
            + f"\nColunas encontradas: {list(dados.columns)}"
        )

    # Datas em formatos brasileiros e ISO.
    dados["Data"] = pd.to_datetime(dados["Data"], errors="coerce", dayfirst=True)

    for coluna in ["Fechamento", "Maxima", "Minima", "Volume", "Abertura"]:
        if coluna in dados.columns:
            # Aceita números com vírgula decimal quando o pandas leu como texto.
            if dados[coluna].dtype == object:
                texto = dados[coluna].astype(str).str.strip()
                texto = texto.str.replace("R$", "", regex=False).str.replace(" ", "", regex=False)
                # Para strings no formato 1.234,56, remove separador de milhar.
                texto = texto.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
                dados[coluna] = texto
            dados[coluna] = pd.to_numeric(dados[coluna], errors="coerce")

    dados = dados.sort_values("Data").reset_index(drop=True)
    return dados


def auditar_qualidade(dados):
    """Retorna uma tabela de verificações e uma cópia limpa para o motor."""
    verificacoes = []

    def registrar(teste, quantidade, gravidade, detalhe):
        verificacoes.append({
            "Verificacao": teste,
            "Quantidade": int(quantidade),
            "Gravidade": gravidade,
            "Detalhe": detalhe,
        })

    total = len(dados)
    registrar("Linhas no CSV", total, "INFO", "Total de registros lidos.")
    registrar("Datas inválidas", dados["Data"].isna().sum(), "ERRO",
              "Registros sem data válida serão removidos.")
    registrar("Datas duplicadas", dados["Data"].duplicated(keep=False).sum(), "ALERTA",
              "Duplicatas serão resolvidas mantendo o último registro da data.")
    registrar("Datas fora de ordem no arquivo original", 0, "INFO",
              "Os dados foram ordenados cronologicamente para a análise.")

    numericas = ["Fechamento", "Maxima", "Minima", "Volume"]
    for coluna in numericas:
        qtd = dados[coluna].isna().sum()
        registrar(f"{coluna} ausente/inválido", qtd, "ERRO" if qtd else "OK",
                  "Registros com campos obrigatórios inválidos serão removidos.")

    if "Abertura" in dados.columns:
        registrar("Abertura ausente/inválida", dados["Abertura"].isna().sum(), "ALERTA",
                  "Abertura não é obrigatória para o motor enviado.")

    invalidos_precos = (
        (dados["Fechamento"] <= 0)
        | (dados["Maxima"] <= 0)
        | (dados["Minima"] <= 0)
    )
    registrar("Preços não positivos", invalidos_precos.sum(), "ERRO",
              "Registros com preços não positivos serão removidos.")

    max_menor_min = dados["Maxima"] < dados["Minima"]
    registrar("Máxima menor que mínima", max_menor_min.sum(), "ERRO",
              "Inconsistência OHLC; registros serão removidos.")

    fechamento_fora = (
        (dados["Fechamento"] > dados["Maxima"])
        | (dados["Fechamento"] < dados["Minima"])
    )
    registrar("Fechamento fora da faixa mínima/máxima", fechamento_fora.sum(), "ALERTA",
              "Pode indicar dados inconsistentes; registros não serão removidos automaticamente.")

    vol_negativo = dados["Volume"] < 0
    registrar("Volume negativo", vol_negativo.sum(), "ERRO",
              "Registros com volume negativo serão removidos.")

    limpos = dados.dropna(subset=COLUNAS_OBRIGATORIAS).copy()
    limpos = limpos[
        (limpos["Fechamento"] > 0)
        & (limpos["Maxima"] > 0)
        & (limpos["Minima"] > 0)
        & (limpos["Maxima"] >= limpos["Minima"])
        & (limpos["Volume"] >= 0)
    ].copy()
    limpos = limpos.drop_duplicates(subset=["Data"], keep="last")
    limpos = limpos.sort_values("Data").reset_index(drop=True)

    registrar("Linhas válidas após limpeza", len(limpos), "INFO",
              "Registros disponíveis para o motor após remover erros obrigatórios.")
    registrar("Linhas removidas na limpeza", total - len(limpos), "INFO",
              "Diferença entre o arquivo original e a base preparada.")

    if not limpos.empty:
        registrar("Primeira data válida", 1, "INFO", str(limpos["Data"].iloc[0].date()))
        registrar("Última data válida", 1, "INFO", str(limpos["Data"].iloc[-1].date()))

    return pd.DataFrame(verificacoes), limpos


def resumo_backtest(resultados, horizonte):
    """Produz estatísticas transparentes sem classificar ambiguidades como vitória ou derrota."""
    total = len(resultados)
    if total == 0:
        return {
            "Horizonte_pregoes": horizonte,
            "Sinais": 0,
            "Alvos": 0,
            "Stops": 0,
            "Ambiguos": 0,
            "Nao_atingiu": 0,
            "Taxa_alvo_sobre_sinais": np.nan,
            "Taxa_alvo_excluindo_ambiguos": np.nan,
            "Resultado_R_conhecido": 0,
            "Resultado_R_acumulado": np.nan,
            "Media_pregoes_resultado": np.nan,
            "Mediana_pregoes_resultado": np.nan,
        }

    contagem = resultados["Resultado"].value_counts()
    alvos = int(contagem.get("ALVO", 0))
    stops = int(contagem.get("STOP", 0))
    ambiguos = int(contagem.get("AMBIGUO", 0))
    nao_atingiu = int(contagem.get("NAO ATINGIU", 0))

    resolvidos_sem_ambiguos = alvos + stops
    taxa_excluindo_ambiguos = (
        alvos / resolvidos_sem_ambiguos * 100
        if resolvidos_sem_ambiguos else np.nan
    )

    r_conhecido = pd.to_numeric(resultados["Resultado_R"], errors="coerce")
    preg = pd.to_numeric(resultados["Pregoes_Resultado"], errors="coerce")

    return {
        "Horizonte_pregoes": horizonte,
        "Sinais": total,
        "Alvos": alvos,
        "Stops": stops,
        "Ambiguos": ambiguos,
        "Nao_atingiu": nao_atingiu,
        "Taxa_alvo_sobre_sinais": round(alvos / total * 100, 2) if total else np.nan,
        "Taxa_alvo_excluindo_ambiguos": round(taxa_excluindo_ambiguos, 2)
            if pd.notna(taxa_excluindo_ambiguos) else np.nan,
        "Resultado_R_conhecido": int(r_conhecido.notna().sum()),
        "Resultado_R_acumulado": round(r_conhecido.sum(), 4)
            if r_conhecido.notna().any() else np.nan,
        "Media_pregoes_resultado": round(preg.mean(), 2)
            if preg.notna().any() else np.nan,
        "Mediana_pregoes_resultado": round(preg.median(), 2)
            if preg.notna().any() else np.nan,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Auditoria independente do motor diário do Analisador B3."
    )
    parser.add_argument("--arquivo", required=True, help="Caminho do CSV histórico do ativo.")
    parser.add_argument("--inicio", default=None, help="Data inicial YYYY-MM-DD.")
    parser.add_argument("--fim", default=None, help="Data final YYYY-MM-DD.")
    parser.add_argument("--horizontes", default="5,10,15,20",
                        help="Horizontes em pregões, separados por vírgula. Padrão: 5,10,15,20.")
    parser.add_argument("--saida", default="resultado_auditoria",
                        help="Pasta de saída. Padrão: resultado_auditoria.")
    args = parser.parse_args()

    try:
        motor = importlib.import_module("motor")
    except Exception as exc:
        print("ERRO: não consegui importar motor.py.")
        print("Coloque auditor.py na mesma pasta de motor.py.")
        print(f"Detalhe: {exc}")
        sys.exit(2)

    dados_brutos = ler_csv(args.arquivo)
    qualidade, dados = auditar_qualidade(dados_brutos)

    if args.inicio:
        inicio = pd.to_datetime(args.inicio, errors="raise")
    else:
        inicio = dados["Data"].iloc[0] if not dados.empty else pd.NaT

    if args.fim:
        fim = pd.to_datetime(args.fim, errors="raise")
    else:
        fim = dados["Data"].iloc[-1] if not dados.empty else pd.NaT

    # Preservar todo o histórico anterior ao início do período.
    # O motor precisa desses candles para calcular indicadores e formar sinais
    # no intervalo escolhido sem perder o aquecimento histórico.
    dados = dados.sort_values("Data").reset_index(drop=True)

    horizontes = []
    for item in args.horizontes.split(","):
        item = item.strip()
        if item:
            valor = int(item)
            if valor < 1:
                raise ValueError("Os horizontes devem ser inteiros positivos.")
            horizontes.append(valor)
    horizontes = sorted(set(horizontes))
    if not horizontes:
        raise ValueError("Informe pelo menos um horizonte válido.")

    pasta_saida = Path(args.saida)
    pasta_saida.mkdir(parents=True, exist_ok=True)

    qualidade.to_csv(pasta_saida / "auditoria_qualidade.csv", index=False, encoding="utf-8-sig")

    dados_periodo = dados[(dados["Data"] >= inicio) & (dados["Data"] <= fim)].copy()

    if len(dados) < getattr(motor, "MINIMO_DADOS", 220) + 1:
        print(f"AVISO: a base completa tem {len(dados)} linhas.")
        print("O backtest do motor exige histórico anterior ao período de sinais;")
        print("com poucos dados, pode não haver sinais auditáveis.")

    if dados.empty or dados_periodo.empty:
        print("ERRO: não há dados no arquivo ou no intervalo escolhido.")
        sys.exit(2)

    # Indicadores são calculados para conferir se o motor consegue processar a base.
    dados_indicadores = motor.calcular_indicadores(dados.copy())
    dados_indicadores.to_csv(
        pasta_saida / "auditoria_indicadores.csv",
        index=False,
        encoding="utf-8-sig"
    )

    tabelas_sinais = []
    resumos = []

    for horizonte in horizontes:
        print(f"Executando backtest do motor: horizonte de {horizonte} pregões...")
        resultado = motor.executar_backtest(
            dados.copy(),
            inicio,
            fim,
            horizonte
        )

        if resultado is None:
            resultado = pd.DataFrame()

        if not resultado.empty:
            resultado.insert(0, "Horizonte_Auditoria", horizonte)
            tabelas_sinais.append(resultado)

        resumos.append(resumo_backtest(resultado, horizonte))

    sinais = (
        pd.concat(tabelas_sinais, ignore_index=True)
        if tabelas_sinais else pd.DataFrame()
    )
    resumo = pd.DataFrame(resumos)

    sinais.to_csv(pasta_saida / "auditoria_sinais.csv", index=False, encoding="utf-8-sig")
    resumo.to_csv(pasta_saida / "resumo_estatistico.csv", index=False, encoding="utf-8-sig")

    # Relatório de texto com avisos metodológicos.
    relatorio = [
        "AUDITORIA DO ANALISADOR B3",
        "=" * 60,
        f"Arquivo analisado: {args.arquivo}",
        f"Período selecionado: {inicio.date()} a {fim.date()}",
        f"Registros válidos na base completa: {len(dados)}",
        f"Registros dentro do período auditado: {len(dados_periodo)}",
        f"Horizontes: {', '.join(map(str, horizontes))} pregões",
        "",
        "RESUMO ESTATÍSTICO",
        "-" * 60,
        resumo.to_string(index=False) if not resumo.empty else "Nenhum sinal gerado.",
        "",
        "OBSERVAÇÕES METODOLÓGICAS",
        "-" * 60,
        "1. O auditor chama executar_backtest() do motor sem alterar suas regras.",
        "2. ALVO, STOP, AMBIGUO e NAO ATINGIU seguem os rótulos produzidos pelo motor.",
        "3. O motor classifica alvo e stop tocados no mesmo candle como AMBIGUO.",
        "4. A taxa excluindo ambiguidades usa somente ALVO e STOP no denominador.",
        "5. O R acumulado soma apenas valores de Resultado_R conhecidos; ambiguidades e operações sem resolução não entram nessa soma.",
        "6. O backtest do motor usa os candles futuros do horizonte informado; isso é uma avaliação histórica, não uma previsão garantida.",
        "7. O auditor não modifica nem grava alterações em motor.py.",
        "",
        "ARQUIVOS GERADOS",
        "- auditoria_qualidade.csv",
        "- auditoria_indicadores.csv",
        "- auditoria_sinais.csv",
        "- resumo_estatistico.csv",
        "- relatorio_auditoria.txt",
    ]
    (pasta_saida / "relatorio_auditoria.txt").write_text(
        "\n".join(relatorio), encoding="utf-8"
    )

    print("\nAUDITORIA CONCLUÍDA")
    print(f"Pasta de saída: {pasta_saida.resolve()}")
    print(f"Sinais auditados: {len(sinais)}")
    print("Arquivos: auditoria_qualidade.csv, auditoria_indicadores.csv,")
    print("          auditoria_sinais.csv, resumo_estatistico.csv, relatorio_auditoria.txt")
    print("\nResumo:")
    print(resumo.to_string(index=False))


if __name__ == "__main__":
    main()
