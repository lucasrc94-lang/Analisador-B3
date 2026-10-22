
import pandas as pd

from intraday import (
    coletar_candles_intraday,
    gerar_sinais_intraday
)


def auditar_sinais(dados):
    """
    Audita cada rejeição e verifica se houve confirmação
    nos dois candles seguintes.
    """

    dados = dados.reset_index(drop=True).copy()

    confirmacoes = {}

    # Localiza as rejeições que originaram sinais confirmados.
    for i in range(len(dados)):

        sinal = dados.loc[i, "Sinal"]

        if sinal not in [
            "COMPRA CONFIRMADA",
            "VENDA CONFIRMADA"
        ]:
            continue

        tipo = (
            "COMPRA"
            if sinal == "COMPRA CONFIRMADA"
            else "VENDA"
        )

        # Procura a rejeição nos candles anteriores.
        for distancia in (1, 2):

            j = i - distancia

            if j < 0:
                continue

            if dados.loc[j, "Rejeicao"] != tipo:
                continue

            if tipo == "COMPRA":
                nivel = dados.loc[j, "Maxima"]

                cruzou = (
                    dados.loc[i - 1, "Fechamento"] <= nivel
                    and dados.loc[i, "Fechamento"] > nivel
                )

            else:
                nivel = dados.loc[j, "Minima"]

                cruzou = (
                    dados.loc[i - 1, "Fechamento"] >= nivel
                    and dados.loc[i, "Fechamento"] < nivel
                )

            if cruzou:
                confirmacoes[j] = {
                    "tipo": tipo,
                    "data_confirmacao": dados.loc[i, "Data"],
                    "fechamento_entrada": dados.loc[i, "Fechamento"],
                    "nivel_rompimento": nivel,
                    "candles_ate_confirmacao": distancia
                }
                break

    # Monta a auditoria de todas as rejeições.
    linhas = []

    for j in range(len(dados)):

        tipo = dados.loc[j, "Rejeicao"]

        if tipo not in ["COMPRA", "VENDA"]:
            continue

        linha = dados.loc[j]

        if tipo == "COMPRA":
            nivel_pullback = linha["Minima"]
            nivel_rompimento = linha["Maxima"]
        else:
            nivel_pullback = linha["Maxima"]
            nivel_rompimento = linha["Minima"]

        atr = linha["ATR14"]

        distancia_mme = (
            abs(nivel_pullback - linha["MME21"]) / atr
            if pd.notna(atr) and atr > 0
            else float("nan")
        )

        volume_medio = linha["Volume_medio_anterior"]

        razao_volume = (
            linha["Volume"] / volume_medio
            if pd.notna(volume_medio) and volume_medio > 0
            else float("nan")
        )

        confirmacao = confirmacoes.get(j)

        if confirmacao:
            status = "CONFIRMADA"
            data_confirmacao = confirmacao["data_confirmacao"]
            fechamento_entrada = confirmacao["fechamento_entrada"]
            candles_ate = confirmacao["candles_ate_confirmacao"]
        else:
            status = "SEM CONFIRMAÇÃO"
            data_confirmacao = None
            fechamento_entrada = None
            candles_ate = None

        linhas.append({
            "Data_rejeicao": linha["Data"],
            "Tipo": tipo,
            "Status": status,
            "Tendencia": linha["Tendencia"],
            "Fechamento_rejeicao": linha["Fechamento"],
            "MME21": linha["MME21"],
            "MME200": linha["MME200"],
            "ATR14": atr,
            "Distancia_MME_em_ATR": distancia_mme,
            "Volume": linha["Volume"],
            "Volume_medio_20": volume_medio,
            "Volume_relativo": razao_volume,
            "Nivel_rompimento": nivel_rompimento,
            "Data_confirmacao": data_confirmacao,
            "Fechamento_entrada": fechamento_entrada,
            "Candles_ate_confirmacao": candles_ate,
            "MME21_subindo": linha["MME21_subindo"],
            "MME21_caindo": linha["MME21_caindo"],
            "MME200_subindo": linha["MME200_subindo"],
            "MME200_caindo": linha["MME200_caindo"],
        })

    return pd.DataFrame(linhas)


def calcular_historico_movimento(dados, indice_entrada, tipo):
    """
    Calcula a média das últimas 3 ondas históricas concluídas,
    na janela de 6 meses anterior à entrada.

    Utiliza amplitude em reais e percentual, seguindo
    a metodologia do analisador diário. Não usa ATR
    para calcular as projeções históricas.
    """

    historico = dados.iloc[:indice_entrada + 1].copy()

    if historico.empty:
        return None

    data_entrada = historico["Data"].iloc[-1]
    data_inicial = data_entrada - pd.DateOffset(months=6)

    historico = historico[
        historico["Data"] >= data_inicial
    ].copy().reset_index(drop=True)

    if historico.empty:
        return None

    if tipo == "COMPRA":
        historico["Dentro_movimento"] = (
            historico["Fechamento"] > historico["MME21"]
        )
    else:
        historico["Dentro_movimento"] = (
            historico["Fechamento"] < historico["MME21"]
        )

    historico["Grupo"] = (
        historico["Dentro_movimento"]
        .ne(historico["Dentro_movimento"].shift())
        .cumsum()
    )

    ondas = []

    for _, grupo in historico.groupby("Grupo", sort=True):

        if not grupo["Dentro_movimento"].iloc[0]:
            continue

        if len(grupo) < 3:
            continue

        # Não usar a onda que ainda está ativa na entrada.
        if grupo.index[-1] == historico.index[-1]:
            continue

        preco_inicial = float(grupo["Fechamento"].iloc[0])

        if preco_inicial <= 0:
            continue

        if tipo == "COMPRA":
            extremo = float(grupo["Maxima"].max())
            indice_extremo = grupo["Maxima"].idxmax()
            amplitude = extremo - preco_inicial
        else:
            extremo = float(grupo["Minima"].min())
            indice_extremo = grupo["Minima"].idxmin()
            amplitude = preco_inicial - extremo

        if amplitude <= 0:
            continue

        percentual = amplitude / preco_inicial * 100
        duracao = int(indice_extremo - grupo.index[0] + 1)

        ondas.append({
            "DataInicial": grupo["Data"].iloc[0],
            "Amplitude": amplitude,
            "Percentual": percentual,
            "Duracao": duracao
        })

    # Segue o padrão de usar até as 3 ondas concluídas mais recentes.
    ondas = ondas[-3:]

    if not ondas:
        return None

    return {
        "Ondas_historicas": len(ondas),
        "Amplitude_media_historica": sum(
            onda["Amplitude"] for onda in ondas
        ) / len(ondas),
        "Percentual_medio_historico": sum(
            onda["Percentual"] for onda in ondas
        ) / len(ondas),
        "Duracao_media_historica": sum(
            onda["Duracao"] for onda in ondas
        ) / len(ondas)
    }



def avaliar_alvos_por_pregoes(dados, auditoria):
    """
    Verifica se os alvos históricos de amplitude e percentual
    foram atingidos em 5, 10, 15 ou 20 pregões futuros.

    Não utiliza stop.
    A entrada e os alvos são preservados conforme a metodologia atual.
    O dia da entrada conta como 0 pregões decorridos.
    """

    dados = (
        dados.sort_values("Data")
        .reset_index(drop=True)
        .copy()
    )

    # Cada data representa um pregão da Bolsa.
    datas = dados["Data"].dt.date
    datas_unicas = list(pd.unique(datas))
    ordem_pregoes = {
        data: posicao
        for posicao, data in enumerate(datas_unicas)
    }

    prazos = [5, 10, 15, 20]
    resultados = []

    confirmadas = auditoria[
        auditoria["Status"] == "CONFIRMADA"
    ]

    for _, sinal in confirmadas.iterrows():

        data_entrada = sinal["Data_confirmacao"]
        tipo = sinal["Tipo"]

        indices = dados.index[
            dados["Data"] == data_entrada
        ]

        if len(indices) == 0:
            continue

        indice_entrada = int(indices[0])
        preco_entrada = float(
            dados.loc[indice_entrada, "Fechamento"]
        )

        data_pregao_entrada = datas.iloc[indice_entrada]
        ordem_entrada = ordem_pregoes[data_pregao_entrada]

        historico = calcular_historico_movimento(
            dados,
            indice_entrada,
            tipo
        )

        if historico is None:
            alvos = [
                ("AMPLITUDE", None),
                ("PERCENTUAL", None)
            ]
        else:
            direcao = 1 if tipo == "COMPRA" else -1

            alvo_amplitude = (
                preco_entrada
                + direcao
                * historico["Amplitude_media_historica"]
            )

            alvo_percentual = (
                preco_entrada
                * (
                    1
                    + direcao
                    * historico["Percentual_medio_historico"]
                    / 100
                )
            )

            alvos = [
                ("AMPLITUDE", alvo_amplitude),
                ("PERCENTUAL", alvo_percentual)
            ]

        # Avalia separadamente cada tipo de alvo.
        for tipo_alvo, preco_alvo in alvos:

            indice_alvo = None
            pregoes_ate_alvo = None

            if preco_alvo is not None:

                # Começa no candle seguinte à entrada.
                # Não usa a máxima/mínima do próprio candle de entrada.
                for k in range(indice_entrada + 1, len(dados)):

                    if tipo == "COMPRA":
                        atingiu = (
                            dados.loc[k, "Maxima"] >= preco_alvo
                        )
                    else:
                        atingiu = (
                            dados.loc[k, "Minima"] <= preco_alvo
                        )

                    if atingiu:
                        indice_alvo = k
                        pregoes_ate_alvo = (
                            ordem_pregoes[datas.iloc[k]]
                            - ordem_entrada
                        )
                        break

            if indice_alvo is not None:
                data_alvo = dados.loc[indice_alvo, "Data"]
                candles_ate_alvo = indice_alvo - indice_entrada
            else:
                data_alvo = None
                candles_ate_alvo = None

            # Quantos pregões futuros existem para avaliar este sinal?
            pregões_futuros_disponiveis = sum(
                1 for data in datas_unicas
                if ordem_pregoes[data] > ordem_entrada
            )

            for prazo in prazos:

                if preco_alvo is None:
                    status = "SEM ALVO HISTORICO"

                elif indice_alvo is not None:
                    if pregoes_ate_alvo <= prazo:
                        status = "ATINGIU DENTRO DO PRAZO"
                    else:
                        status = "ATINGIU APOS O PRAZO"

                elif pregões_futuros_disponiveis >= prazo:
                    status = "NAO ATINGIU ATE O FIM DOS DADOS"

                else:
                    status = "INCONCLUSIVO - DADOS INSUFICIENTES"

                resultados.append({
                    "Data_entrada": data_entrada,
                    "Tipo": tipo,
                    "Preco_entrada": round(preco_entrada, 3),
                    "Tipo_alvo": tipo_alvo,
                    "Preco_alvo": (
                        round(float(preco_alvo), 3)
                        if preco_alvo is not None
                        else None
                    ),
                    "Prazo_pregoes": prazo,
                    "Status_alvo": status,
                    "Data_alvo": data_alvo,
                    "Pregoes_ate_alvo": pregoes_ate_alvo,
                    "Candles_ate_alvo": candles_ate_alvo,
                    "Pregoes_futuros_disponiveis":
                        pregões_futuros_disponiveis
                })

    return pd.DataFrame(resultados)


def resumir_alvos_por_pregoes(alvos):
    """
    Resume os alvos por tipo de operação, tipo de alvo e prazo.

    A taxa de atingimento dentro do prazo usa como denominador
    apenas os casos com resultado avaliável.
    """

    if alvos.empty:
        return pd.DataFrame()

    resultados = []

    status_dentro = "ATINGIU DENTRO DO PRAZO"
    status_depois = "ATINGIU APOS O PRAZO"
    status_nao_atingiu = "NAO ATINGIU ATE O FIM DOS DADOS"
    status_inconclusivo = "INCONCLUSIVO - DADOS INSUFICIENTES"
    status_sem_alvo = "SEM ALVO HISTORICO"

    for tipo in ["TODAS", "COMPRA", "VENDA"]:

        if tipo == "TODAS":
            grupo_tipo = alvos.copy()
        else:
            grupo_tipo = alvos[alvos["Tipo"] == tipo].copy()

        for tipo_alvo in ["AMPLITUDE", "PERCENTUAL"]:

            grupo_alvo = grupo_tipo[
                grupo_tipo["Tipo_alvo"] == tipo_alvo
            ].copy()

            for prazo in [5, 10, 15, 20]:

                grupo = grupo_alvo[
                    grupo_alvo["Prazo_pregoes"] == prazo
                ].copy()

                dentro = grupo[
                    grupo["Status_alvo"] == status_dentro
                ]

                depois = grupo[
                    grupo["Status_alvo"] == status_depois
                ]

                nao_atingiu = grupo[
                    grupo["Status_alvo"] == status_nao_atingiu
                ]

                inconclusivos = grupo[
                    grupo["Status_alvo"] == status_inconclusivo
                ]

                sem_alvo = grupo[
                    grupo["Status_alvo"] == status_sem_alvo
                ]

                avaliaveis = (
                    len(dentro)
                    + len(depois)
                    + len(nao_atingiu)
                )

                taxa = (
                    len(dentro) / avaliaveis * 100
                    if avaliaveis > 0
                    else None
                )

                # Tempo até o alvo entre todos os casos em que
                # o alvo foi atingido, inclusive depois do prazo.
                atingidos = grupo[
                    grupo["Data_alvo"].notna()
                ]

                mediana_tempo = (
                    round(
                        float(
                            atingidos["Pregoes_ate_alvo"].median()
                        ),
                        2
                    )
                    if not atingidos.empty
                    else None
                )

                resultados.append({
                    "Tipo": tipo,
                    "Tipo_alvo": tipo_alvo,
                    "Prazo_pregoes": prazo,
                    "Operacoes_avaliaveis": avaliaveis,
                    "Atingiu_dentro": len(dentro),
                    "Atingiu_depois": len(depois),
                    "Nao_atingiu_no_historico": len(nao_atingiu),
                    "Inconclusivos": len(inconclusivos),
                    "Sem_alvo_historico": len(sem_alvo),
                    "Taxa_atingimento_pct": (
                        round(taxa, 2)
                        if taxa is not None
                        else None
                    ),
                    "Mediana_pregoes_ate_alvo": mediana_tempo
                })

    return pd.DataFrame(resultados)



def testar():

    ativo = "PETR4"

    print("=" * 80)
    print("AUDITORIA DA ESTRATEGIA INTRADAY")
    print("=" * 80)

    dados = coletar_candles_intraday(ativo)

    if dados.empty:
        print("Nenhum candle foi coletado.")
        return

    print(f"\nAtivo: {ativo}")
    print(f"Total de candles: {len(dados)}")
    print(f"Primeiro candle: {dados['Data'].iloc[0]}")
    print(f"Ultimo candle: {dados['Data'].iloc[-1]}")

    dados = gerar_sinais_intraday(dados)
    auditoria = auditar_sinais(dados)
    alvos = avaliar_alvos_por_pregoes(dados, auditoria)
    resumo_alvos = resumir_alvos_por_pregoes(alvos)

    if auditoria.empty:
        print("\nNenhuma rejeicao encontrada.")
    else:
        pd.set_option("display.max_columns", None)
        pd.set_option("display.width", 240)
        pd.set_option("display.max_colwidth", 25)

        print("\n" + "=" * 80)
        print("DETALHAMENTO DAS REJEICOES")
        print("=" * 80)

        print(
            auditoria.round(3).to_string(index=False)
        )

        print("\n" + "=" * 80)
        print("RESUMO DA AUDITORIA")
        print("=" * 80)

        print(f"Rejeicoes encontradas: {len(auditoria)}")
        print(
            "Compras:",
            len(auditoria[auditoria["Tipo"] == "COMPRA"])
        )
        print(
            "Vendas:",
            len(auditoria[auditoria["Tipo"] == "VENDA"])
        )
        print(
            "Confirmadas:",
            len(auditoria[auditoria["Status"] == "CONFIRMADA"])
        )
        print(
            "Sem confirmacao:",
            len(auditoria[auditoria["Status"] == "SEM CONFIRMAÇÃO"])
        )

        print("\nSinais confirmados registrados pelo motor:")
        print(dados["Sinal"].value_counts().to_string())
        
        print("\n" + "=" * 80)
        print("AUDITORIA DOS ALVOS POR PRAZO EM PREGOES")
        print("=" * 80)

        if alvos.empty:
            print("Nenhuma entrada confirmada para avaliar.")
        else:
            print(alvos.to_string(index=False))

            print("\n" + "=" * 80)
            print("RESUMO ESTATISTICO DOS ALVOS")
            print("=" * 80)

            if resumo_alvos.empty:
                print("Nenhum resultado disponível para resumir.")
            else:
                print(resumo_alvos.to_string(index=False))


    print("\nAuditoria concluida!")


if __name__ == "__main__":
    testar()
