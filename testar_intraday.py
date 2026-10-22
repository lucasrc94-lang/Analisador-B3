
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

def avaliar_movimentos(dados, auditoria):
    """
    Mede o movimento favorável e contrário após cada entrada confirmada.
    Os horizontes são de 3, 5 e 10 candles após a entrada.
    """

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

        indice_entrada = dados.index.get_loc(indices[0])
        preco_entrada = float(
            dados.loc[indices[0], "Fechamento"]
        )

        resultado = {
            "Data_entrada": data_entrada,
            "Tipo": tipo,
            "Preco_entrada": preco_entrada,
        }

        for horizonte in [3, 5, 10]:

            inicio = indice_entrada + 1
            fim = min(
                indice_entrada + horizonte,
                len(dados) - 1
            )

            if inicio > fim:
                resultado[f"Favoravel_{horizonte}"] = None
                resultado[f"Contrario_{horizonte}"] = None
                resultado[f"Candles_disponiveis_{horizonte}"] = 0
                continue

            janela = dados.iloc[inicio:fim + 1]

            if tipo == "COMPRA":
                movimento_favoravel = (
                    janela["Maxima"].max() - preco_entrada
                )
                movimento_contrario = (
                    preco_entrada - janela["Minima"].min()
                )

            else:
                movimento_favoravel = (
                    preco_entrada - janela["Minima"].min()
                )
                movimento_contrario = (
                    janela["Maxima"].max() - preco_entrada
                )

            resultado[f"Favoravel_{horizonte}"] = round(
                float(movimento_favoravel), 3
            )
            resultado[f"Contrario_{horizonte}"] = round(
                float(movimento_contrario), 3
            )
            resultado[f"Candles_disponiveis_{horizonte}"] = len(
                janela
            )

        resultados.append(resultado)

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

    print("\nAuditoria concluida!")


if __name__ == "__main__":
    testar()
