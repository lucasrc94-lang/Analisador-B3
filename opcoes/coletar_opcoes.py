
"""
Coleta de dados históricos de opções da B3 utilizando b3quant.

Importante:
- A fonte inicial é o COTAHIST da B3.
- A coleta é histórica, não representa cotação em tempo real.
- Não substitui dados de bid e ask.
- Não utiliza datas anteriores automaticamente quando a coleta falha.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd

from opcoes.configuracao import FONTE_DADOS


FUSO_HORARIO = ZoneInfo("America/Sao_Paulo")


class ErroColetaOpcoes(Exception):
    """Erro específico durante a coleta de opções."""


def obter_data_referencia():
    """Obtém a data atual no fuso horário definido para o projeto."""
    return datetime.now(FUSO_HORARIO).date()


def converter_valor(valor):
    """Converte valores do Pandas para tipos compatíveis com JSON."""

    if pd.isna(valor):
        return None

    if isinstance(valor, (pd.Timestamp, datetime, date)):
        return valor.isoformat()

    if hasattr(valor, "item"):
        return valor.item()

    return valor


def coletar_opcoes(data_referencia=None):
    """
    Coleta as opções negociadas em uma data específica.

    Args:
        data_referencia: objeto datetime.date.
                         Se não informado, utiliza a data atual.

    Returns:
        Dicionário contendo metadados e registros coletados.

    Raises:
        ErroColetaOpcoes: quando a coleta falhar ou não houver dados.
    """

    if data_referencia is None:
        data_referencia = obter_data_referencia()

    if not isinstance(data_referencia, date):
        raise ErroColetaOpcoes(
            "A data de referência deve ser um objeto datetime.date."
        )

    if data_referencia > obter_data_referencia():
        raise ErroColetaOpcoes(
            "Não é permitido consultar uma data futura."
        )

    try:
        import b3quant

    except ImportError as erro:
        raise ErroColetaOpcoes(
            "Biblioteca b3quant não instalada. "
            "Verifique o requirements.txt."
        ) from erro

    try:
        dados = b3quant.get_options(
            year=data_referencia.year,
            month=data_referencia.month,
            day=data_referencia.day
        )

    except Exception as erro:
        raise ErroColetaOpcoes(
            f"Falha ao consultar o b3quant: {erro}"
        ) from erro

    if dados is None or dados.empty:
        raise ErroColetaOpcoes(
            f"Nenhum dado de opções encontrado para "
            f"{data_referencia.isoformat()}. "
            "Não será utilizada outra data automaticamente."
        )

    registros = []

    for registro in dados.to_dict(orient="records"):
        registro_limpo = {
            chave: converter_valor(valor)
            for chave, valor in registro.items()
        }

        registros.append(registro_limpo)

    resultado = {
        "fonte": FONTE_DADOS,
        "tipo_dado": "historico_cotahist",
        "data_referencia": data_referencia.isoformat(),
        "coletado_em": datetime.now(FUSO_HORARIO).isoformat(),
        "quantidade_registros": len(registros),
        "dados": registros
    }

    return resultado


if __name__ == "__main__":

    try:
        resultado = coletar_opcoes()

        print("Coleta concluída.")
        print(f"Fonte: {resultado['fonte']}")
        print(f"Data: {resultado['data_referencia']}")
        print(
            f"Registros encontrados: "
            f"{resultado['quantidade_registros']}"
        )

    except ErroColetaOpcoes as erro:
        print(f"ERRO NA COLETA: {erro}")
