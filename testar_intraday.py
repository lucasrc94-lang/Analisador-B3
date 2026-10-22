
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


def avaliar_movimentos(dados, auditoria):
    """
    Mede o movimento favorável e contrário após cada entrada
    confirmada, nos horizontes de 3, 5 e 10 candles.

    Compara os resultados com a amplitude e o percentual
    históricos das ondas concluídas nos 6 meses anteriores.
    """

    dados = dados.reset_index(drop=True).copy()
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

        historico = calcular_historico_movimento(
            dados,
            indice_entrada,
            tipo
        )

        resultado = {
            "Data_entrada": data_entrada,
            "Tipo": tipo,
            "Preco_entrada": preco_entrada
        }

        if historico is None:
            resultado.update({
                "Ondas_historicas": 0,
                "Amplitude_media_historica": None,
                "Percentual_medio_historico": None,
                "Duracao_media_historica": None,
                "Alvo_amplitude_historica": None,
                "Alvo_percentual_historico": None
            })
        else:
            amplitude_media = historico[
                "Amplitude_media_historica"
            ]
            percentual_medio = historico[
                "Percentual_medio_historico"
            ]

            sinal_direcao = 1 if tipo == "COMPRA" else -1

            resultado.update(historico)
            resultado["Alvo_amplitude_historica"] = (
                preco_entrada + sinal_direcao * amplitude_media
            )
            resultado["Alvo_percentual_historico"] = (
                preco_entrada
                * (1 + sinal_direcao * percentual_medio / 100)
            )

        for horizonte in [3, 5, 10]:

            inicio = indice_entrada + 1
            fim = min(
                indice_entrada + horizonte,
                len(dados) - 1
            )

            if inicio > fim:
                resultado[f"Favoravel_{horizonte}"] = None
                resultado[f"Contrario_{horizonte}"] = None
                resultado[f"Favoravel_pct_{horizonte}"] = None
                resultado[f"Contrario_pct_{horizonte}"] = None
                resultado[f"Candles_disponiveis_{horizonte}"] = 0
                continue

            janela = dados.iloc[inicio:fim + 1]

            if tipo == "COMPRA":
                favoravel = (
                    janela["Maxima"].max() - preco_entrada
                )
                contrario = (
                    preco_entrada - janela["Minima"].min()
                )
            else:
                favoravel = (
                    preco_entrada - janela["Minima"].min()
                )
                contrario = (
                    janela["Maxima"].max() - preco_entrada
                )

            resultado[f"Favoravel_{horizonte}"] = round(
                float(favoravel), 3
            )
            resultado[f"Contrario_{horizonte}"] = round(
                float(contrario), 3
            )
            resultado[f"Favoravel_pct_{horizonte}"] = round(
                float(favoravel / preco_entrada * 100), 3
            )
            resultado[f"Contrario_pct_{horizonte}"] = round(
                float(contrario / preco_entrada * 100), 3
            )
            resultado[f"Candles_disponiveis_{horizonte}"] = len(
                janela
            )

        resultados.append(resultado)

    return pd.DataFrame(resultados)


def resumir_movimentos(movimentos):
    """
    Resume amplitudes favoráveis e contrárias em reais e percentual.
    Considera somente horizontes com todos os candles disponíveis.
    """

    resultados = []

    if movimentos.empty:
        return pd.DataFrame()

    for tipo in ["TODAS", "COMPRA", "VENDA"]:

        if tipo == "TODAS":
            grupo = movimentos.copy()
        else:
            grupo = movimentos[
                movimentos["Tipo"] == tipo
            ].copy()

        for horizonte in [3, 5, 10]:

            coluna_candles = f"Candles_disponiveis_{horizonte}"

            completo = grupo[
                grupo[coluna_candles] == horizonte
            ].copy()

            linha = {
                "Tipo": tipo,
                "Horizonte_candles": horizonte,
                "Operacoes": len(completo)
            }

            for nome, coluna in [
                ("Media_favoravel_R$", f"Favoravel_{horizonte}"),
                ("Mediana_favoravel_R$", f"Favoravel_{horizonte}"),
                ("Media_contraria_R$", f"Contrario_{horizonte}"),
                ("Mediana_contraria_R$", f"Contrario_{horizonte}"),
                ("Media_favoravel_pct", f"Favoravel_pct_{horizonte}"),
                ("Mediana_favoravel_pct", f"Favoravel_pct_{horizonte}"),
                ("Media_contraria_pct", f"Contrario_pct_{horizonte}"),
                ("Mediana_contraria_pct", f"Contrario_pct_{horizonte}")
            ]:
                valores = completo[coluna].dropna()

                if valores.empty:
                    linha[nome] = None
                elif nome.startswith("Media"):
                    linha[nome] = round(float(valores.mean()), 3)
                else:
                    linha[nome] = round(float(valores.median()), 3)

            resultados.append(linha)

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
    movimentos = avaliar_movimentos(dados, auditoria)
    resumo = resumir_movimentos(movimentos)

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
        print("AVALIACAO DOS MOVIMENTOS APOS A ENTRADA")
        print("=" * 80)

        if movimentos.empty:
            print("Nenhuma entrada confirmada para avaliar.")
        else:
            print(movimentos.round(3).to_string(index=False))
            print("\n" + "=" * 80)
            print("RESUMO ESTATISTICO — AMPLITUDE E PERCENTUAL")
            print("=" * 80)

            if resumo.empty:
                print("Nenhum movimento disponível para resumir.")
            else:
                print(resumo.to_string(index=False))

    print("\nAuditoria concluida!")


if __name__ == "__main__":
    testar()
