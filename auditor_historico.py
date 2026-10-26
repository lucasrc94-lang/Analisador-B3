
import glob
import os
import numpy as np
import pandas as pd
import motor


# ============================================================
# CONFIGURACOES DO AUDITOR
# ============================================================

PASTA_DADOS = "dados"
PASTA_RESULTADOS = "resultados_auditoria"

MINIMO_DADOS = motor.MINIMO_DADOS
MAX_OBSERVACAO = 60

HORIZONTES = [5, 10, 15, 20, 60]


# ============================================================
# PREPARACAO DOS CSVs
# ============================================================

def preparar_csv(caminho):
    dados = pd.read_csv(caminho)

    aliases = {
        "Date": "Data",
        "date": "Data",
        "Open": "Abertura",
        "High": "Maxima",
        "Low": "Minima",
        "Close": "Fechamento",
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
        coluna
        for coluna in obrigatorias
        if coluna not in dados.columns
    ]

    if faltantes:
        raise ValueError(
            f"Colunas ausentes em {caminho}: {faltantes}"
        )

    dados["Data"] = pd.to_datetime(
        dados["Data"],
        errors="coerce",
        dayfirst=True,
    )

    for coluna in [
        "Fechamento",
        "Maxima",
        "Minima",
        "Volume",
    ]:
        dados[coluna] = pd.to_numeric(
            dados[coluna],
            errors="coerce",
        )

    dados = dados.dropna(subset=obrigatorias)
    dados = dados.sort_values("Data")

    dados = dados.drop_duplicates(
        subset=["Data"],
        keep="last",
    )

    dados = dados.reset_index(drop=True)

    return dados


# ============================================================
# VERIFICAR ATINGIMENTO DO ALVO
# ============================================================

def verificar_alvo(
    futuro,
    direcao,
    alvo,
    preco_entrada,
    prazo_estimado,
):
    if (
        alvo is None
        or pd.isna(alvo)
        or not np.isfinite(alvo)
        or alvo <= 0
    ):
        return {
            "status": "ALVO INVALIDO",
            "pregoes_reais": None,
            "data_atingimento": None,
        }

    # O alvo precisa estar na direcao projetada.
    if direcao == "ALTA" and alvo <= preco_entrada:
        return {
            "status": "ALVO INVALIDO",
            "pregoes_reais": None,
            "data_atingimento": None,
        }

    if direcao == "BAIXA" and alvo >= preco_entrada:
        return {
            "status": "ALVO INVALIDO",
            "pregoes_reais": None,
            "data_atingimento": None,
        }

    for numero, (_, candle) in enumerate(
        futuro.iterrows(),
        start=1,
    ):
        if direcao == "ALTA":
            atingiu = candle["Maxima"] >= alvo
        else:
            atingiu = candle["Minima"] <= alvo

        if atingiu:
            status = (
                "NO PRAZO"
                if numero <= prazo_estimado
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

    # Mantem os indicadores calculados pelo motor.
    dados = motor.calcular_indicadores(dados)

    resultados = []

    # Cada sinal tera 60 pregoes futuros completos.
    ultimo_indice = len(dados) - MAX_OBSERVACAO

    for indice in range(MINIMO_DADOS, ultimo_indice):
        historico = dados.iloc[:indice + 1].copy()
        sinal = historico.iloc[-1]

        direcao = motor.classificar_tendencia(sinal)

        if direcao not in ("ALTA", "BAIXA"):
            continue

        # A projecao utiliza somente os dados disponiveis
        # ate a data do sinal.
        projecao = motor.estimar_pregoes_historicos(
            historico,
            direcao,
        )

        if not projecao:
            continue

        prazo = projecao.get(
            "pregoes_estimados_historico"
        )

        if (
            prazo is None
            or pd.isna(prazo)
            or not np.isfinite(prazo)
            or prazo <= 0
        ):
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
                projecao.get(
                    "alvo_amplitude_historica"
                ),
            ),
            (
                "PERCENTUAL",
                projecao.get(
                    "alvo_percentual_historico"
                ),
            ),
        ]

        for tipo_alvo, alvo in alvos:
            resultado = verificar_alvo(
                futuro=futuro,
                direcao=direcao,
                alvo=alvo,
                preco_entrada=preco_entrada,
                prazo_estimado=prazo,
            )

            if (
                alvo is None
                or pd.isna(alvo)
                or not np.isfinite(alvo)
            ):
                distancia_reais = np.nan
                distancia_pct = np.nan
            else:
                distancia_reais = abs(
                    float(alvo) - preco_entrada
                )

                distancia_pct = (
                    distancia_reais / preco_entrada * 100
                    if preco_entrada > 0
                    else np.nan
                )

            pregoes_reais = resultado["pregoes_reais"]

            linha = {
                "Ativo": ticker,
                "Data_Sinal": sinal["Data"],
                "Direcao": direcao,
                "Preco_Entrada": preco_entrada,
                "Tipo_Alvo": tipo_alvo,
                "Alvo_Projetado": alvo,
                "Distancia_Alvo_R$": distancia_reais,
                "Distancia_Alvo_%": distancia_pct,
                "Amplitude_Media_R$": projecao.get(
                    "media_amplitude_historica"
                ),
                "Amplitude_Media_%": projecao.get(
                    "media_amplitude_pct_historica"
                ),
                "Tempo_Medio_Movimento": projecao.get(
                    "tempo_medio_movimento"
                ),
                "Pregoes_Estimados": prazo,
                "Resultado": resultado["status"],
                "Pregoes_Reais": pregoes_reais,
                "Data_Atingimento": resultado[
                    "data_atingimento"
                ],
            }

            # Verifica o primeiro atingimento em cada horizonte.
            for horizonte in HORIZONTES:
                linha[
                    f"Atingiu_{horizonte}_Pregoes"
                ] = (
                    pregoes_reais is not None
                    and pregoes_reais <= horizonte
                )

            resultados.append(linha)

    print(
        f"{ticker}: {len(resultados)} alvos auditados."
    )

    return resultados


# ============================================================
# CLASSIFICAR DISTANCIAS EM TRES FAIXAS
# ============================================================

def classificar_faixa_distancia(detalhado):
    detalhado = detalhado.copy()

    detalhado["Faixa_Distancia"] = pd.NA

    grupos = [
        "Ativo",
        "Tipo_Alvo",
        "Direcao",
    ]

    for _, indices in detalhado.groupby(
        grupos,
        dropna=False,
    ).groups.items():

        distancias = detalhado.loc[
            indices,
            "Distancia_Alvo_%",
        ]

        validas = distancias.dropna()

        if validas.empty:
            continue

        # Divide cada grupo em tercis.
        posicoes = validas.rank(
            method="first",
            pct=True,
        )

        faixas = np.select(
            [
                posicoes <= 1 / 3,
                posicoes <= 2 / 3,
            ],
            [
                "MENORES",
                "INTERMEDIARIOS",
            ],
            default="MAIORES",
        )

        detalhado.loc[
            posicoes.index,
            "Faixa_Distancia",
        ] = faixas

    return detalhado


# ============================================================
# RESUMO POR ATIVO, ALVO, DIRECAO E DISTANCIA
# ============================================================

def criar_resumo(detalhado):
    validos = detalhado[
        detalhado["Distancia_Alvo_%"].notna()
    ].copy()

    if validos.empty:
        return pd.DataFrame()

    grupos = [
        "Ativo",
        "Tipo_Alvo",
        "Direcao",
        "Faixa_Distancia",
    ]

    agregacoes = {
        "Total": ("Resultado", "size"),
        "Distancia_Media_R$": (
            "Distancia_Alvo_R$",
            "mean",
        ),
        "Distancia_Media_%": (
            "Distancia_Alvo_%",
            "mean",
        ),
        "Distancia_Mediana_%": (
            "Distancia_Alvo_%",
            "median",
        ),
        "Prazo_Estimado_Medio": (
            "Pregoes_Estimados",
            "mean",
        ),
        "Prazo_Estimado_Mediano": (
            "Pregoes_Estimados",
            "median",
        ),
    }

    for horizonte in HORIZONTES:
        agregacoes[
            f"Atingidos_Em_{horizonte}"
        ] = (
            f"Atingiu_{horizonte}_Pregoes",
            "sum",
        )

    resumo = (
        validos
        .groupby(grupos, dropna=False)
        .agg(**agregacoes)
        .reset_index()
    )

    for horizonte in HORIZONTES:
        resumo[
            f"Taxa_Atingimento_{horizonte}_%"
        ] = (
            resumo[
                f"Atingidos_Em_{horizonte}"
            ]
            / resumo["Total"]
            * 100
        )

    return resumo


# ============================================================
# EXECUCAO
# ============================================================

def main():
    os.makedirs(
        PASTA_RESULTADOS,
        exist_ok=True,
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
            todos.extend(
                auditar_ativo(caminho)
            )
        except Exception as erro:
            print(
                f"ERRO em {os.path.basename(caminho)}: "
                f"{erro}"
            )

    if not todos:
        print(
            "Nenhum sinal foi auditado. "
            "Confira os CSVs e as funcoes do motor.py."
        )
        return

    detalhado = pd.DataFrame(todos)

    detalhado = classificar_faixa_distancia(
        detalhado
    )

    resumo = criar_resumo(detalhado)

    arquivo_detalhado = os.path.join(
        PASTA_RESULTADOS,
        "auditoria_historica_detalhada.csv",
    )

    arquivo_resumo = os.path.join(
        PASTA_RESULTADOS,
        "auditoria_historica_resumo.csv",
    )

    detalhado.to_csv(
        arquivo_detalhado,
        index=False,
        encoding="utf-8-sig",
    )

    resumo.to_csv(
        arquivo_resumo,
        index=False,
        encoding="utf-8-sig",
    )

    print("\nAUDITORIA HISTORICA CONCLUIDA")
    print(f"Registros auditados: {len(detalhado)}")
    print(f"Arquivo detalhado: {arquivo_detalhado}")
    print(f"Arquivo resumo: {arquivo_resumo}")

    if not resumo.empty:
        print("\nRESUMO POR DISTANCIA E DIRECAO:")
        print(resumo.to_string(index=False))


if __name__ == "__main__":
    main()
