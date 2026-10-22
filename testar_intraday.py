
import pandas as pd

from intraday import (
    coletar_candles_intraday,
    gerar_sinais_intraday
)


def testar():
    ativo = "PETR4"

    print("=" * 60)
    print("TESTE DO MÓDULO INTRADAY")
    print("=" * 60)

    dados = coletar_candles_intraday(ativo)

    print(f"\nAtivo: {ativo}")
    print(f"Quantidade de candles: {len(dados)}")
    print(f"Primeiro candle: {dados['Data'].iloc[0]}")
    print(f"Último candle: {dados['Data'].iloc[-1]}")

    dados = gerar_sinais_intraday(dados)

    colunas = [
        "Data",
        "Fechamento",
        "MME21",
        "MME200",
        "Tendencia",
        "Volume",
        "Sinal"
    ]

    print("\nÚltimos 10 candles:")
    print(dados[colunas].tail(10).to_string(index=False))

    print("\nQuantidade de sinais:")
    print(dados["Sinal"].value_counts().to_string())

    print("\nTeste concluído!")


if __name__ == "__main__":
    testar()
