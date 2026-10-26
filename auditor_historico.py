
import glob
import os
import math
import numpy as np
import pandas as pd
import motor


# ============================================================
# CONFIGURAÇÕES DO AUDITOR
# ============================================================

PASTA_DADOS = "dados"
PASTA_RESULTADOS = "resultados_auditoria"

MINIMO_DADOS = motor.MINIMO_DADOS
MAX_OBSERVACAO = 60


# ============================================================
# PREPARAÇÃO DOS CSVs
# ============================================================

def preparar_csv(caminho):
    dados = pd.read_csv(caminho)

    # Normalizar nomes conhecidos sem alterar o motor.
    aliases = {
        "Date": "Data",
        "date": "Data",
        "Open": "Abertura",
        "High": "Maxima",
        "Low": "Minima",
        "Close": "Fechamento",
        "Volume": "Volume",
    }

    dados = dados.rename(columns=aliases)

    obrigatorias = [
        "Data",
        "Fechamento",
        "Maxima",
        "Minima",
        "Volume",
    ]

    faltantes = [
        coluna for coluna in obrigatorias
        if coluna not in dados.columns
    ]

    if faltantes:
        raise ValueError(
            f"Colunas ausentes em {caminho}: {faltantes}"
        )

    dados["Data"] = pd.to_datetime(
        dados["Data"],
        errors="coerce",
        dayfirst=True
    )

    for coluna in [
        "Fechamento", "Maxima", "Minima", "Volume"
    ]:
        dados[coluna] = pd.to_numeric(
            dados[coluna],
            errors="coerce"
        )

    dados = dados.dropna(
        subset=[
            "Data", "Fechamento",
            "Maxima", "Minima", "Volume"
        ]
    )

    dados = dados.sort_values("Data")
    dados = dados.drop_duplicates(
        subset=["Data"],
        keep="last"
    )
    dados = dados.reset_index(drop=True)

    return dados


# ============================================================
# VERIFICAR UM ALVO NO FUTURO
# ============================================================

def verificar_alvo(
    futuro,
    direcao,
    alvo,
    pregoes_estimados
):
    if pd.isna(alvo) or alvo <= 0:
        return {
            "status": "ALVO INVALIDO",
            "pregoes_reais": None,
            "data_atingimento": None,
        }

    for numero, (_, candle) in enumerate(
        futuro.iterrows(),
        start=1
    ):
        if direcao == "ALTA":
            atingiu = candle["Maxima"] >= alvo
        else:
            atingiu = candle["Minima"] <= alvo

        if atingiu:
            status = (
                "NO PRAZO"
                if numero <= pregoes_estimados
                else "DEPOIS DO PRAZO"
            )

            return {
                "status": status,
                "pregoes_reais": numero,
                "data_atingimento": candle["Data"],
            }

    return {
        "status": "NAO ATINGIU EM 60 PREGOES",
        "pregoes_reais": None,
        "data_atingimento": None,
    }


# ============================================================
# AUDITAR UM ATIVO
# ============================================================

def auditar_ativo(caminho):
    ticker = os.path.splitext(
        os.path.basename(caminho)
    )[0].upper()

    dados = preparar_csv(caminho)

    if len(dados) < MINIMO_DADOS + MAX_OBSERVACAO:
        print(
            f"{ticker}: dados insuficientes "
            f"({len(dados)} linhas)."
        )
        return []

    # Os indicadores são calculados de forma causal.
    # Os alvos auditados vêm exclusivamente da função
    # de projeção histórica do motor.
    dados = motor.calcular_indicadores(dados)

    resultados = []

    # Exigir 60 pregões futuros completos para cada sinal.
    ultimo_indice = len(dados) - MAX_OBSERVACAO

    for indice in range(MINIMO_DADOS, ultimo_indice):
        historico = dados.iloc[:indice + 1].copy()
        sinal = historico.iloc[-1]

        direcao = motor.classificar_tendencia(sinal)

        if direcao not in ("ALTA", "BAIXA"):
            continue

        # Esta função usa os movimentos históricos concluídos.
        projecao = motor.estimar_pregoes_historicos(
            historico,
            direcao
        )

        if not projecao:
            continue

        prazo = projecao.get(
            "pregoes_estimados_historico"
        )

        if prazo is None or pd.isna(prazo) or prazo <= 0:
            continue

        prazo = int(prazo)

        preco_entrada = float(sinal["Fechamento"])

        futuro = dados.iloc[
            indice + 1:
            indice + 1 + MAX_OBSERVACAO
        ].copy()

        alvos = [
            (
                "AMPLITUDE",
                projecao.get("alvo_amplitude_historica")
            ),
            (
                "PERCENTUAL",
                projecao.get("alvo_percentual_historico")
            ),
        ]

        for tipo_alvo, alvo in alvos:
            resultado = verificar_alvo(
                futuro=futuro,
                direcao=direcao,
                alvo=alvo,
                pregoes_estimados=prazo
            )

            resultados.append({
                "Ativo": ticker,
                "Data_Sinal": sinal["Data"],
                "Direcao": direcao,
                "Preco_Entrada": preco_entrada,
                "Tipo_Alvo": tipo_alvo,
                "Alvo_Projetado": alvo,
                "Amplitude_Media_R$": (
                    projecao.get(
                        "media_amplitude_historica"
                    )
                ),
                "Amplitude_Media_%": (
                    projecao.get(
                        "media_amplitude_pct_historica"
                    )
                ),
                "Tempo_Medio_Movimento": (
                    projecao.get("tempo_medio_movimento")
                ),
                "Pregoes_Estimados": prazo,
                "Resultado": resultado["status"],
                "Pregoes_Reais": resultado["pregoes_reais"],
                "Data_Atingimento": (
                    resultado["data_atingimento"]
                ),
            })

    print(f"{ticker}: {len(resultados)} alvos auditados.")
    return resultados


# ============================================================
# RESUMO DOS RESULTADOS
# ============================================================

def criar_resumo(detalhado):
    if detalhado.empty:
        return pd.DataFrame()

    resumo = (
        detalhado
        .groupby(["Ativo", "Tipo_Alvo", "Direcao"])
        .agg(
            Total=("Resultado", "size"),
            No_Prazo=(
                "Resultado",
                lambda serie: (serie == "NO PRAZO").sum()
            ),
            Depois_Do_Prazo=(
                "Resultado",
                lambda serie: (
                    serie == "DEPOIS DO PRAZO"
                ).sum()
            ),
            Nao_Atingiu=(
                "Resultado",
                lambda serie: (
                    serie == "NAO ATINGIU EM 60 PREGOES"
                ).sum()
            ),
            Prazo_Medio_Estimado=(
                "Pregoes_Estimados", "mean"
            ),
            Pregoes_Medios_Atingimento=(
                "Pregoes_Reais", "mean"
            ),
        )
        .reset_index()
    )

    resumo["Taxa_Atingimento_No_Prazo_%"] = (
        resumo["No_Prazo"] / resumo["Total"] * 100
    )

    resumo["Taxa_Atingimento_Em_60_%"] = (
        (
            resumo["No_Prazo"]
            + resumo["Depois_Do_Prazo"]
        )
        / resumo["Total"] * 100
    )

    return resumo


# ============================================================
# EXECUÇÃO
# ============================================================

def main():
    os.makedirs(
        PASTA_RESULTADOS,
        exist_ok=True
    )

    arquivos = glob.glob(
        os.path.join(PASTA_DADOS, "*.csv")
    )

    if not arquivos:
        raise FileNotFoundError(
            f"Nenhum CSV encontrado em '{PASTA_DADOS}'."
        )

    todos = []

    for caminho in sorted(arquivos):
        try:
            todos.extend(auditar_ativo(caminho))
        except Exception as erro:
            print(
                f"ERRO em {os.path.basename(caminho)}: {erro}"
            )

    if not todos:
        print(
            "Nenhum sinal pôde ser auditado. "
            "Confira os CSVs e a quantidade de dados."
        )
        return

    detalhado = pd.DataFrame(todos)
    resumo = criar_resumo(detalhado)

    arquivo_detalhado = os.path.join(
        PASTA_RESULTADOS,
        "auditoria_historica_detalhada.csv"
    )

    arquivo_resumo = os.path.join(
        PASTA_RESULTADOS,
        "auditoria_historica_resumo.csv"
    )

    detalhado.to_csv(
        arquivo_detalhado,
        index=False,
        encoding="utf-8-sig"
    )

    resumo.to_csv(
        arquivo_resumo,
        index=False,
        encoding="utf-8-sig"
    )

    print("\nAUDITORIA HISTÓRICA CONCLUÍDA")
    print(f"Sinais/alvos: {len(detalhado)}")
    print(f"Detalhado: {arquivo_detalhado}")
    print(f"Resumo: {arquivo_resumo}")
    print("\nRESUMO:")
    print(resumo.to_string(index=False))


if __name__ == "__main__":
    main()
