
"""
Filtros de liquidez e qualidade dos dados do Analisador de Opções B3.

Classifica opções em:
- APROVADA_EXECUTAVEL
- APROVADA_TEORICA
- REPROVADA

Uma opção sem Bid e Ask válidos não será considerada
executável, mesmo que tenha passado pelos demais filtros.
"""

import math

from opcoes.configuracao import (
    VOLUME_MINIMO_OPCAO,
    OPEN_INTEREST_MINIMO,
    SPREAD_MAXIMO_RELATIVO,
    EXIGIR_BID_ASK_VALIDOS,
)


class ErroFiltros(Exception):
    """Erro na aplicação dos filtros."""


def numero_valido(valor):
    """Verifica se um valor é numérico, finito e não negativo."""

    try:
        valor = float(valor)
    except (TypeError, ValueError):
        return False

    return math.isfinite(valor) and valor >= 0


def calcular_spread_relativo(bid, ask):
    """
    Calcula o spread relativo em relação ao preço médio.

    Retorna None quando os preços não são válidos.
    """

    if not numero_valido(bid) or not numero_valido(ask):
        return None

    bid = float(bid)
    ask = float(ask)

    if bid <= 0 or ask <= 0 or ask < bid:
        return None

    preco_medio = (bid + ask) / 2

    if preco_medio <= 0:
        return None

    return (ask - bid) / preco_medio


def avaliar_opcao(opcao):
    """
    Avalia individualmente uma opção normalizada.

    Espera os campos:
    codigo_opcao, tipo, strike, vencimento,
    preco_fechamento, ativo_subjacente,
    volume, bid, ask e open_interest.
    """

    if not isinstance(opcao, dict):
        raise ErroFiltros(
            "A opção deve ser fornecida como dicionário."
        )

    motivos = []

    # 1. Identificação básica

    if not opcao.get("codigo_opcao"):
        motivos.append("Código da opção ausente.")

    if str(opcao.get("tipo", "")).upper() not in (
        "CALL", "PUT"
    ):
        motivos.append("Tipo de opção inválido.")

    if not opcao.get("ativo_subjacente"):
        motivos.append("Ativo subjacente ausente.")

    if not opcao.get("vencimento"):
        motivos.append("Vencimento ausente.")

    # 2. Strike e preço

    if not numero_valido(opcao.get("strike")):
        motivos.append("Strike inválido ou ausente.")
    elif float(opcao["strike"]) <= 0:
        motivos.append("Strike deve ser positivo.")

    if not numero_valido(opcao.get("preco_fechamento")):
        motivos.append("Preço de fechamento inválido.")
    elif float(opcao["preco_fechamento"]) <= 0:
        motivos.append("Preço de fechamento deve ser positivo.")

    # 3. Volume negociado

    volume = opcao.get("volume")

    if not numero_valido(volume):
        motivos.append("Volume ausente ou inválido.")
    elif float(volume) < VOLUME_MINIMO_OPCAO:
        motivos.append("Volume abaixo do mínimo configurado.")

    # 4. Contratos em aberto

    open_interest = opcao.get("open_interest")

    if not numero_valido(open_interest):
        motivos.append("Open interest ausente ou inválido.")
    elif float(open_interest) < OPEN_INTEREST_MINIMO:
        motivos.append("Open interest abaixo do mínimo configurado.")

    # 5. Bid e Ask

    bid = opcao.get("bid")
    ask = opcao.get("ask")

    spread_relativo = calcular_spread_relativo(bid, ask)

    bid_ask_validos = spread_relativo is not None

    if not bid_ask_validos:
        motivos.append(
            "Bid e Ask válidos não disponíveis."
        )

    elif spread_relativo > SPREAD_MAXIMO_RELATIVO:
        motivos.append(
            "Spread entre Bid e Ask acima do limite."
        )

    # 6. Classificação final

    motivos_reprovacao = [
        motivo for motivo in motivos
        if motivo != "Bid e Ask válidos não disponíveis."
    ]

    if motivos_reprovacao:
        status = "REPROVADA"
        executavel = False

    elif not bid_ask_validos:
        status = "APROVADA_TEORICA"
        executavel = False

    else:
        status = "APROVADA_EXECUTAVEL"
        executavel = True

    if (
        not bid_ask_validos
        and EXIGIR_BID_ASK_VALIDOS
        and status == "APROVADA_TEORICA"
    ):
        observacao = (
            "Aprovada apenas para análise teórica. "
            "Não pode gerar recomendação executável."
        )
    elif status == "APROVADA_EXECUTAVEL":
        observacao = (
            "Dados aprovados nos filtros básicos. "
            "A execução ainda depende da validação "
            "das demais condições da operação."
        )
    else:
        observacao = "Opção reprovada nos filtros de qualidade."

    return {
        "codigo_opcao": opcao.get("codigo_opcao"),
        "status": status,
        "aprovada": status != "REPROVADA",
        "executavel": executavel,
        "spread_relativo": spread_relativo,
        "motivos": motivos,
        "observacao": observacao,
    }


def filtrar_opcoes(registros):
    """
    Aplica os filtros a uma lista de opções.

    Retorna aprovadas, reprovadas e resumo quantitativo.
    """

    if not isinstance(registros, list):
        raise ErroFiltros(
            "Os registros devem ser fornecidos em uma lista."
        )

    resultados = []

    for opcao in registros:
        resultados.append(avaliar_opcao(opcao))

    aprovadas = [
        resultado for resultado in resultados
        if resultado["aprovada"]
    ]

    reprovadas = [
        resultado for resultado in resultados
        if not resultado["aprovada"]
    ]

    executaveis = [
        resultado for resultado in aprovadas
        if resultado["executavel"]
    ]

    teoricas = [
        resultado for resultado in aprovadas
        if not resultado["executavel"]
    ]

    return {
        "total_analisado": len(resultados),
        "total_aprovado": len(aprovadas),
        "total_executavel": len(executaveis),
        "total_teorico": len(teoricas),
        "total_reprovado": len(reprovadas),
        "resultados": resultados,
        "aprovadas": aprovadas,
        "executaveis": executaveis,
        "teoricas": teoricas,
        "reprovadas": reprovadas,
    }

