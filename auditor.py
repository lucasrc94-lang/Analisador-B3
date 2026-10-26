
"""
AUDITOR DAS PROJEÇÕES HISTÓRICAS DO ANALISADOR B3

Valida os alvos por amplitude histórica e percentual histórico
calculados por motor.estimar_pregoes_historicos().

Não utiliza alvo P&F nem stop por ATR para avaliar as projeções.
Não modifica motor.py.
"""

import argparse
import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd


COLUNAS_OBRIGATORIAS = [
    "Data", "Fechamento", "Maxima", "Minima", "Volume"
]

HORIZONTES_PADRAO = [5, 10, 15, 20]
JANELA_MAXIMA_OBSERVACAO = 60


# ============================================================
# LEITURA E PREPARAÇÃO DOS DADOS
# ============================================================

def ler_csv(caminho):
    caminho = Path(caminho)

    if not caminho.exists():
        raise FileNotFoundError(
            f"Arquivo não encontrado: {caminho}"
        )

    dados = pd.read_csv(
        caminho,
        sep=None,
        engine="python"
    )

    dados.columns = [
        str(coluna).strip()
        for coluna in dados.columns
    ]

    aliases = {
        "Data": ["data", "Date", "date"],
        "Fechamento": [
            "fechamento", "Close", "close", "Adj Close"
        ],
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

    dados = dados.rename(columns=renomear)

    faltantes = [
        coluna for coluna in COLUNAS_OBRIGATORIAS
        if coluna not in dados.columns
    ]

    if faltantes:
        raise ValueError(
            f"Colunas obrigatórias ausentes: {faltantes}. "
            f"Encontradas: {list(dados.columns)}"
        )

    dados["Data"] = pd.to_datetime(
        dados["Data"],
        errors="coerce",
        dayfirst=True
    )

    for coluna in [
        "Fechamento", "Maxima", "Minima",
        "Volume", "Abertura"
    ]:
        if coluna not in dados.columns:
            continue

        if dados[coluna].dtype == object:
            texto = dados[coluna].astype(str).str.strip()
            texto = texto.str.replace("R$", "", regex=False)
            texto = texto.str.replace(" ", "", regex=False)

            # Compatibilidade com números decimais brasileiros.
            texto = texto.str.replace(
                ".", "", regex=False
            ).str.replace(
                ",", ".", regex=False
            )

            dados[coluna] = texto

        dados[coluna] = pd.to_numeric(
            dados[coluna],
            errors="coerce"
        )

    return dados


# ============================================================
# AUDITORIA DA QUALIDADE
# ============================================================

def auditar_qualidade(dados):
    verificacoes = []

    def registrar(teste, quantidade, gravidade, detalhe):
        verificacoes.append({
            "Verificacao": teste,
            "Quantidade": int(quantidade),
            "Gravidade": gravidade,
            "Detalhe": detalhe,
        })

    total = len(dados)

    registrar(
        "Linhas no CSV", total, "INFO",
        "Total de registros lidos."
    )

    registrar(
        "Datas inválidas",
        dados["Data"].isna().sum(),
        "ERRO",
        "Registros sem data válida serão removidos."
    )

    registrar(
        "Datas duplicadas",
        dados["Data"].duplicated(keep=False).sum(),
        "ALERTA",
        "Será mantido o último registro de cada data."
    )

    for coluna in COLUNAS_OBRIGATORIAS[1:]:
        quantidade = dados[coluna].isna().sum()

        registrar(
            f"{coluna} ausente/inválido",
            quantidade,
            "ERRO" if quantidade else "OK",
            "Registros inválidos serão removidos."
        )

    invalidos_precos = (
        (dados["Fechamento"] <= 0)
        | (dados["Maxima"] <= 0)
        | (dados["Minima"] <= 0)
    )

    registrar(
        "Preços não positivos",
        invalidos_precos.sum(),
        "ERRO",
        "Registros com preços não positivos serão removidos."
    )

    max_menor_min = dados["Maxima"] < dados["Minima"]

    registrar(
        "Máxima menor que mínima",
        max_menor_min.sum(),
        "ERRO",
        "Registros inconsistentes serão removidos."
    )

    fechamento_fora = (
        (dados["Fechamento"] > dados["Maxima"])
        | (dados["Fechamento"] < dados["Minima"])
    )

    registrar(
        "Fechamento fora da faixa",
        fechamento_fora.sum(),
        "ALERTA",
        "Esses registros serão preservados para inspeção."
    )

    volume_negativo = dados["Volume"] < 0

    registrar(
        "Volume negativo",
        volume_negativo.sum(),
        "ERRO",
        "Registros com volume negativo serão removidos."
    )

    limpos = dados.dropna(
        subset=COLUNAS_OBRIGATORIAS
    ).copy()

    limpos = limpos[
        (limpos["Fechamento"] > 0)
        & (limpos["Maxima"] > 0)
        & (limpos["Minima"] > 0)
        & (limpos["Maxima"] >= limpos["Minima"])
        & (limpos["Volume"] >= 0)
    ].copy()

    limpos = limpos.sort_values("Data")
    limpos = limpos.drop_duplicates(
        subset=["Data"],
        keep="last"
    )
    limpos = limpos.reset_index(drop=True)

    registrar(
        "Linhas válidas após limpeza",
        len(limpos),
        "INFO",
        "Registros disponíveis para a análise."
    )

    registrar(
        "Linhas removidas",
        total - len(limpos),
        "INFO",
        "Diferença entre registros originais e registros válidos."
    )

    if not limpos.empty:
        registrar(
            "Primeira data válida",
            1,
            "INFO",
            str(limpos["Data"].iloc[0].date())
        )

        registrar(
            "Última data válida",
            1,
            "INFO",
            str(limpos["Data"].iloc[-1].date())
        )

    return pd.DataFrame(verificacoes), limpos


# ============================================================
# VERIFICAR QUANDO UM ALVO FOI ATINGIDO
# ============================================================

def verificar_alvo(futuro, direcao, alvo):
    if pd.isna(alvo):
        return None, None

    for numero, (_, candle) in enumerate(
        futuro.iterrows(),
        start=1
    ):
        if direcao == "ALTA":
            atingiu = candle["Maxima"] >= alvo
        else:
            atingiu = candle["Minima"] <= alvo

        if atingiu:
            return numero, candle["Data"]

    return None, None


# ============================================================
# AUDITORIA DAS PROJEÇÕES HISTÓRICAS
# ============================================================

def auditar_projecoes(
    motor,
    dados,
    inicio,
    fim,
    horizontes,
    ticker
):
    resultados = []

    minimo_dados = getattr(
        motor, "MINIMO_DADOS", 220
    )

    janela = max(
        JANELA_MAXIMA_OBSERVACAO,
        max(horizontes)
    )

    # Exige uma janela futura completa para comparar os sinais.
    # Assim, os sinais próximos do fim da série não são tratados
    # injustamente como alvos não atingidos.
    ultimo_indice = len(dados) - janela

    if ultimo_indice <= minimo_dados:
        print(
            f"{ticker}: histórico insuficiente para "
            f"{janela} pregões futuros completos."
        )
        return resultados

    for indice in range(minimo_dados, ultimo_indice):
        linha_sinal = dados.iloc[indice]
        data_sinal = linha_sinal["Data"]

        if data_sinal < inicio or data_sinal > fim:
            continue

        # Importante: somente dados até a data do sinal.
        historico = dados.iloc[:indice + 1].copy()

        historico = motor.calcular_indicadores(
            historico
        )

        sinal = historico.iloc[-1]

        direcao = motor.classificar_tendencia(
            sinal
        )

        if direcao not in ("ALTA", "BAIXA"):
            continue

        # Esta é a função de projeção histórica do motor.
        # Não chamar analisar() nem executar_backtest(), pois
        # essas funções também calculam alvos P&F/ATR.
        projecao = motor.estimar_pregoes_historicos(
            historico,
            direcao
        )

        if not projecao:
            continue

        prazo_estimado = projecao.get(
            "pregoes_estimados_historico"
        )

        if (
            prazo_estimado is None
            or pd.isna(prazo_estimado)
            or prazo_estimado <= 0
        ):
            continue

        prazo_estimado = int(prazo_estimado)

        preco_entrada = float(
            sinal["Fechamento"]
        )

        futuro = dados.iloc[
            indice + 1: indice + 1 + janela
        ].copy()

        alvos = [
            (
                "AMPLITUDE",
                projecao.get(
                    "alvo_amplitude_historica"
                )
            ),
            (
                "PERCENTUAL",
                projecao.get(
                    "alvo_percentual_historico"
                )
            ),
        ]

        for tipo_alvo, alvo in alvos:
            if alvo is None or pd.isna(alvo):
                continue

            alvo = float(alvo)

            pregoes_reais, data_atingimento = (
                verificar_alvo(
                    futuro,
                    direcao,
                    alvo
                )
            )

            if pregoes_reais is None:
                status_prazo = (
                    "NAO ATINGIU NA JANELA"
                )
                erro_pregoes = None
            else:
                erro_pregoes = (
                    pregoes_reais - prazo_estimado
                )

                if pregoes_reais <= prazo_estimado:
                    status_prazo = "NO PRAZO"
                else:
                    status_prazo = "DEPOIS DO PRAZO"

            # Cada horizonte recebe uma avaliação própria.
            for horizonte in horizontes:
                atingiu_no_horizonte = (
                    pregoes_reais is not None
                    and pregoes_reais <= horizonte
                )

                resultados.append({
                    "Ativo": ticker,
                    "Data_Sinal": data_sinal,
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
                        projecao.get(
                            "tempo_medio_movimento"
                        )
                    ),
                    "Pregoes_Estimados": prazo_estimado,
                    "Horizonte_Avaliacao": horizonte,
                    "Atingiu_No_Horizonte": (
                        atingiu_no_horizonte
                    ),
                    "Pregoes_Reais_Ate_Alvo": (
                        pregoes_reais
                    ),
                    "Erro_Pregoes_vs_Estimativa": (
                        erro_pregoes
                    ),
                    "Status_vs_Prazo_Estimado": (
                        status_prazo
                    ),
                    "Data_Atingimento": data_atingimento,
                })

    return resultados


# ============================================================
# RESUMO ESTATÍSTICO
# ============================================================

def criar_resumo(detalhado):
    if detalhado.empty:
        return pd.DataFrame()

    agrupado = detalhado.groupby(
        [
            "Ativo",
            "Tipo_Alvo",
            "Direcao",
            "Horizonte_Avaliacao"
        ],
        dropna=False
    )

    linhas = []

    for chaves, grupo in agrupado:
        total = len(grupo)

        atingidos = int(
            grupo["Atingiu_No_Horizonte"].sum()
        )

        no_prazo = int(
            (
                grupo["Status_vs_Prazo_Estimado"]
                == "NO PRAZO"
            ).sum()
        )

        depois = int(
            (
                grupo["Status_vs_Prazo_Estimado"]
                == "DEPOIS DO PRAZO"
            ).sum()
        )

        nao_atingidos = int(
            (
                grupo["Status_vs_Prazo_Estimado"]
                == "NAO ATINGIU NA JANELA"
            ).sum()
        )

        tempos = pd.to_numeric(
            grupo["Pregoes_Reais_Ate_Alvo"],
            errors="coerce"
        )

        erros = pd.to_numeric(
            grupo["Erro_Pregoes_vs_Estimativa"],
            errors="coerce"
        )

        ativo, tipo_alvo, direcao, horizonte = chaves

        linhas.append({
            "Ativo": ativo,
            "Tipo_Alvo": tipo_alvo,
            "Direcao": direcao,
            "Horizonte": horizonte,
            "Sinais": total,
            "Atingidos_No_Horizonte": atingidos,
            "Taxa_Atingimento_Horizonte_%": (
                round(atingidos / total * 100, 2)
                if total else np.nan
            ),
            "No_Prazo_Estimado": no_prazo,
            "Depois_Do_Prazo": depois,
            "Nao_Atingiu_Janela": nao_atingidos,
            "Taxa_No_Prazo_Estimado_%": (
                round(no_prazo / total * 100, 2)
                if total else np.nan
            ),
            "Pregoes_Reais_Medios": (
                round(tempos.mean(), 2)
                if tempos.notna().any() else np.nan
            ),
            "Erro_Medio_Pregoes": (
                round(erros.mean(), 2)
                if erros.notna().any() else np.nan
            ),
            "Erro_Absoluto_Medio_Pregoes": (
                round(erros.abs().mean(), 2)
                if erros.notna().any() else np.nan
            ),
        })

    return pd.DataFrame(linhas)


# ============================================================
# EXECUÇÃO
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Auditoria das projeções históricas "
            "do Analisador B3."
        )
    )

    parser.add_argument(
        "--arquivo",
        required=True,
        help="Caminho do CSV histórico."
    )

    parser.add_argument(
        "--inicio",
        default=None,
        help="Data inicial YYYY-MM-DD."
    )

    parser.add_argument(
        "--fim",
        default=None,
        help="Data final YYYY-MM-DD."
    )

    parser.add_argument(
        "--horizontes",
        default="5,10,15,20",
        help="Horizontes de avaliação separados por vírgula."
    )

    parser.add_argument(
        "--saida",
        default="resultado_auditoria",
        help="Pasta dos relatórios."
    )

    args = parser.parse_args()

    try:
        motor = importlib.import_module("motor")
    except Exception as erro:
        print("ERRO: não consegui importar motor.py.")
        print(f"Detalhe: {erro}")
        sys.exit(2)

    dados_brutos = ler_csv(args.arquivo)

    qualidade, dados = auditar_qualidade(
        dados_brutos
    )

    if dados.empty:
        print("ERRO: não existem registros válidos.")
        sys.exit(2)

    inicio = (
        pd.to_datetime(args.inicio)
        if args.inicio
        else dados["Data"].iloc[0]
    )

    fim = (
        pd.to_datetime(args.fim)
        if args.fim
        else dados["Data"].iloc[-1]
    )

    horizontes = []

    for item in args.horizontes.split(","):
        item = item.strip()

        if not item:
            continue

        valor = int(item)

        if valor < 1:
            raise ValueError(
                "Os horizontes devem ser inteiros positivos."
            )

        horizontes.append(valor)

    horizontes = sorted(set(horizontes))

    if not horizontes:
        raise ValueError(
            "Informe ao menos um horizonte válido."
        )

    dados = dados.sort_values(
        "Data"
    ).reset_index(drop=True)

    pasta_saida = Path(args.saida)
    pasta_saida.mkdir(
        parents=True,
        exist_ok=True
    )

    qualidade.to_csv(
        pasta_saida / "auditoria_qualidade.csv",
        index=False,
        encoding="utf-8-sig"
    )

    dados_periodo = dados[
        (dados["Data"] >= inicio)
        & (dados["Data"] <= fim)
    ]

    if dados_periodo.empty:
        print(
            "ERRO: não há dados dentro do período selecionado."
        )
        sys.exit(2)

    ticker = Path(args.arquivo).stem.upper()

    print(f"Ativo: {ticker}")
    print(f"Período dos sinais: {inicio.date()} a {fim.date()}")
    print(f"Registros válidos: {len(dados)}")
    print(f"Horizontes: {horizontes}")
    print(
        "Validando projeções históricas; "
        "não serão utilizados alvos P&F ou stops ATR."
    )

    resultados = auditar_projecoes(
        motor=motor,
        dados=dados,
        inicio=inicio,
        fim=fim,
        horizontes=horizontes,
        ticker=ticker
    )

    if not resultados:
        print(
            "Nenhuma projeção foi auditada. "
            "Verifique a quantidade de dados, as datas "
            "e a existência de movimentos históricos concluídos."
        )
        sys.exit(0)

    detalhado = pd.DataFrame(resultados)
    resumo = criar_resumo(detalhado)

    detalhado.to_csv(
        pasta_saida / "projecoes_historicas_detalhadas.csv",
        index=False,
        encoding="utf-8-sig"
    )

    resumo.to_csv(
        pasta_saida / "resumo_projecoes_historicas.csv",
        index=False,
        encoding="utf-8-sig"
    )

    relatorio = [
        "AUDITORIA DAS PROJEÇÕES HISTÓRICAS",
        "=" * 60,
        f"Ativo: {ticker}",
        f"Arquivo: {args.arquivo}",
        f"Período dos sinais: {inicio.date()} a {fim.date()}",
        f"Registros válidos: {len(dados)}",
        f"Horizontes avaliados: {horizontes}",
        f"Janela máxima de observação: "
        f"{max(JANELA_MAXIMA_OBSERVACAO, max(horizontes))} pregões",
        f"Linhas detalhadas: {len(detalhado)}",
        "",
        "RESUMO ESTATÍSTICO",
        "-" * 60,
        resumo.to_string(index=False),
        "",
        "OBSERVAÇÕES METODOLÓGICAS",
        "-" * 60,
        "1. Cada projeção foi calculada usando somente dados até a data do sinal.",
        "2. Os alvos testados são amplitude histórica e percentual histórico.",
        "3. A avaliação considera máxima para ALTA e mínima para BAIXA.",
        "4. Os horizontes medem atingimento em até N pregões futuros.",
        "5. O prazo estimado é comparado com o tempo real de atingimento.",
        "6. Os sinais próximos ao fim do histórico são excluídos quando não têm uma janela futura completa.",
        "7. Esta auditoria não usa alvo P&F nem stop por ATR.",
        "8. A taxa de atingimento de alvo não representa, isoladamente, rentabilidade de opções.",
        "",
        "ARQUIVOS GERADOS",
        "- auditoria_qualidade.csv",
        "- projecoes_historicas_detalhadas.csv",
        "- resumo_projecoes_historicas.csv",
    ]

    (pasta_saida / "relatorio_auditoria.txt").write_text(
        "\n".join(relatorio),
        encoding="utf-8"
    )

    print("\nAUDITORIA CONCLUÍDA")
    print(f"Pasta: {pasta_saida}")
    print("Arquivos gerados:")
    print("- auditoria_qualidade.csv")
    print("- projecoes_historicas_detalhadas.csv")
    print("- resumo_projecoes_historicas.csv")
    print("- relatorio_auditoria.txt")
    print("\nResumo:")
    print(resumo.to_string(index=False))


if __name__ == "__main__":
    main()
