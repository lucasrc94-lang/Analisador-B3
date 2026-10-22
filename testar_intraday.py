
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
            "Candles_ate_confirmacao": candles_ate
        })

    return pd.DataFrame(linhas)


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

    print("\nAuditoria concluida!")


if __name__ == "__main__":
    testar()
