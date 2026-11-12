
"""
Motor de geração de estratégias do Analisador de Opções B3.

Estratégias contempladas:
- Compra de CALL.
- Compra de PUT.
- Trava de débito de CALL.
- Trava de débito de PUT.
- Pozinho de CALL.
- Pozinho de PUT.

As estratégias são geradas como candidatas.
A geração de uma candidata não representa recomendação
nem garante que a operação seja executável.
"""

import math

from opcoes.configuracao import (
    REGRA_TRAVAS,
    REGRA_POZINHOS,
    REGRA_SUGESTOES,
    PERCENTUAL_MAXIMO_DEBITO_TRAVA,
    ESTRATEGIAS_PERMITIDAS,
)


class ErroEstrategia(Exception):
    """Erro na geração ou seleção de estratégias."""


def numero_valido(valor):
    """Verifica se um valor é numérico, finito e positivo."""

    try:
        valor = float(valor)
    except (TypeError, ValueError):
        return False

    return math.isfinite(valor) and valor > 0


def obter_preco_compra(opcao):
    """
    Obtém o preço para compra.

    Prioriza o Ask válido.
    Sem Ask, utiliza fechamento apenas para análise teórica.
    """

    ask = opcao.get("ask")
    bid = opcao.get("bid")

    if numero_valido(ask):
        ask = float(ask)

        if numero_valido(bid) and float(bid) > ask:
            return None, False

        return ask, True

    fechamento = opcao.get("preco_fechamento")

    if numero_valido(fechamento):
        return float(fechamento), False

    return None, False


def obter_preco_venda(opcao):
    """
    Obtém o preço para venda.

    Prioriza o Bid válido.
    Sem Bid, utiliza fechamento apenas para análise teórica.
    """

    bid = opcao.get("bid")
    ask = opcao.get("ask")

    if numero_valido(bid):
        bid = float(bid)

        if numero_valido(ask) and float(ask) < bid:
            return None, False

        return bid, True

    fechamento = opcao.get("preco_fechamento")

    if numero_valido(fechamento):
        return float(fechamento), False

    return None, False


def identificar_pozi​​nho(opcao, preco_ativo, premio_maximo):
    """
    Identifica opção fora do dinheiro com prêmio limitado.

    O limite de prêmio precisa ser informado explicitamente.
    Não existe limite arbitrário definido pelo sistema.
    """

    if premio_maximo is None:
        return False

    if not numero_valido(preco_ativo):
        return False

    if not numero_valido(premio_maximo):
        return False

    strike = opcao.get("strike")

    if not numero_valido(strike):
        return False

    tipo = str(opcao.get("tipo", "")).upper()

    if tipo == "CALL":
        fora_do_dinheiro = float(strike) > float(preco_ativo)

    elif tipo == "PUT":
        fora_do_dinheiro = float(strike) < float(preco_ativo)

    else:
        return False

    premio, _ = obter_preco_compra(opcao)

    return (
        fora_do_dinheiro
        and premio is not None
        and premio <= float(premio_maximo)
    )


def gerar_compra(opcao):
    """Gera uma candidata de compra simples de CALL ou PUT."""

    tipo = str(opcao.get("tipo", "")).upper()

    if tipo not in ("CALL", "PUT"):
        return None

    preco, executavel = obter_preco_compra(opcao)

    if preco is None:
        return None

    estrategia = f"{tipo}_COMPRA"

    if estrategia not in ESTRATEGIAS_PERMITIDAS:
        return None

    return {
        "estrategia": estrategia,
        "codigo_opcao": opcao.get("codigo_opcao"),
        "ativo_subjacente": opcao.get("ativo_subjacente"),
        "tipo": tipo,
        "strike": float(opcao["strike"]),
        "vencimento": opcao.get("vencimento"),
        "premio_estimado": preco,
        "executavel": executavel,
        "tipo_preco": "ask" if executavel else "fechamento_teorico",
        "status": (
            "CANDIDATA_EXECUTAVEL"
            if executavel
            else "CANDIDATA_TEORICA"
        ),
    }


def gerar_pozinho(opcao, preco_ativo, premio_maximo):
    """Gera uma candidata de pozinho CALL ou PUT."""

    if REGRA_POZINHOS == "call":
        if str(opcao.get("tipo", "")).upper() != "CALL":
            return None

    elif REGRA_POZINHOS == "put":
        if str(opcao.get("tipo", "")).upper() != "PUT":
            return None

    elif REGRA_POZINHOS != "both":
        return None

    if not identificar_pozi​​nho(
        opcao,
        preco_ativo,
        premio_maximo
    ):
        return None

    compra = gerar_compra(opcao)

    if compra is None:
        return None

    tipo = compra["tipo"]
    estrategia = f"{tipo}_POZINHO"

    if estrategia not in ESTRATEGIAS_PERMITIDAS:
        return None

    compra["estrategia"] = estrategia

    return compra


def gerar_travas(opcoes):
    """
    Gera travas verticais de débito.

    CALL:
    compra strike inferior e vende strike superior.

    PUT:
    compra strike superior e vende strike inferior.

    As duas opções devem ter o mesmo ativo, tipo e vencimento.
    """

    if REGRA_TRAVAS != "debit":
        return []

    travas = []

    grupos = {}

    for opcao in opcoes:

        tipo = str(opcao.get("tipo", "")).upper()

        if tipo not in ("CALL", "PUT"):
            continue

        chave = (
            opcao.get("ativo_subjacente"),
            tipo,
            opcao.get("vencimento"),
        )

        grupos.setdefault(chave, []).append(opcao)

    for chave, grupo in grupos.items():

        ativo, tipo, vencimento = chave

        if tipo == "CALL":
            estrategia = "CALL_DEBIT_SPREAD"
        else:
            estrategia = "PUT_DEBIT_SPREAD"

        if estrategia not in ESTRATEGIAS_PERMITIDAS:
            continue

        grupo = sorted(
            grupo,
            key=lambda item: float(item["strike"])
            if numero_valido(item.get("strike"))
            else float("inf"),
        )

        for i, primeira in enumerate(grupo):

            for segunda in grupo[i + 1:]:

                if not numero_valido(primeira.get("strike")):
                    continue

                if not numero_valido(segunda.get("strike")):
                    continue

                strike_a = float(primeira["strike"])
                strike_b = float(segunda["strike"])

                if strike_a == strike_b:
                    continue

                if tipo == "CALL":
                    comprada = primeira
                    vendida = segunda

                else:
                    comprada = segunda
                    vendida = primeira

                preco_compra, compra_executavel = (
                    obter_preco_compra(comprada)
                )

                preco_venda, venda_executavel = (
                    obter_preco_venda(vendida)
                )

                if preco_compra is None or preco_venda is None:
                    continue

                debito = preco_compra - preco_venda

                largura = abs(strike_a - strike_b)

                if debito <= 0:
                    continue

                if debito >= largura:
                    continue

                percentual_debito = debito / largura

                if (
                    percentual_debito
                    > PERCENTUAL_MAXIMO_DEBITO_TRAVA
                ):
                    continue

                executavel = (
                    compra_executavel and venda_executavel
                )

                travas.append({
                    "estrategia": estrategia,
                    "ativo_subjacente": ativo,
                    "tipo": tipo,
                    "vencimento": vencimento,
                    "codigo_opcao_comprada": (
                        comprada.get("codigo_opcao")
                    ),
                    "codigo_opcao_vendida": (
                        vendida.get("codigo_opcao")
                    ),
                    "strike_comprado": float(
                        comprada["strike"]
                    ),
                    "strike_vendido": float(
                        vendida["strike"]
                    ),
                    "premio_comprado": preco_compra,
                    "premio_vendido": preco_venda,
                    "debito": debito,
                    "largura": largura,
                    "percentual_debito": percentual_debito,
                    "executavel": executavel,
                    "tipo_preco": (
                        "ask_bid"
                        if executavel
                        else "fechamento_teorico"
                    ),
                    "status": (
                        "CANDIDATA_EXECUTAVEL"
                        if executavel
                        else "CANDIDATA_TEORICA"
                    ),
                })

    return travas


def gerar_candidatos(
    opcoes,
    preco_ativo=None,
    premio_maximo_pozinho=None
):
    """
    Gera todas as estratégias compatíveis com as regras.

    As opções recebidas devem ter passado previamente
    pela validação e pelos filtros de qualidade.

    preco_ativo:
        Preço atual validado do ativo subjacente.

    premio_maximo_pozinho:
        Limite máximo de prêmio definido pelo usuário.
        Sem esse parâmetro, pozinhos não são gerados.
    """

    if not isinstance(opcoes, list):
        raise ErroEstrategia(
            "As opções devem ser fornecidas em uma lista."
        )

    candidatos = []

    for opcao in opcoes:

        if not isinstance(opcao, dict):
            continue

        compra = gerar_compra(opcao)

        if compra is not None:
            candidatos.append(compra)

        pozinho = gerar_pozinho(
            opcao,
            preco_ativo,
            premio_maximo_pozinho
        )

        if pozinho is not None:
            candidatos.append(pozinho)

    candidatos.extend(gerar_travas(opcoes))

    return {
        "total_candidatos": len(candidatos),
        "candidatos": candidatos,
        "executaveis": [
            item for item in candidatos
            if item["executavel"]
        ],
        "teoricos": [
            item for item in candidatos
            if not item["executavel"]
        ],
        "observacao": (
            "Candidatas ainda dependem de análise de "
            "probabilidade, risco, volatilidade e vencimento."
        ),
    }


def selecionar_automaticamente(candidatos, direcao):
    """
    Filtra candidatas conforme a direção esperada do ativo.

    ALTA:
        CALLs e travas de CALL.

    BAIXA:
        PUTs e travas de PUT.

    NEUTRA:
        Não seleciona operações direcionais.

    A volatilidade e a probabilidade serão consideradas
    em uma etapa posterior de classificação.
    """

    if REGRA_SUGESTOES != "automatic":
        raise ErroEstrategia(
            "A seleção automática não está habilitada."
        )

    direcao = str(direcao).upper()

    if direcao not in ("ALTA", "BAIXA", "NEUTRA"):
        raise ErroEstrategia(
            "Direção deve ser ALTA, BAIXA ou NEUTRA."
        )

    if direcao == "NEUTRA":
        return {
            "direcao": direcao,
            "total_selecionado": 0,
            "selecionados": [],
            "motivo": (
                "Não há direção definida para selecionar "
                "estratégias direcionais."
            ),
        }

    if direcao == "ALTA":
        tipos_permitidos = (
            "CALL_COMPRA",
            "CALL_DEBIT_SPREAD",
            "CALL_POZINHO",
        )

    else:
        tipos_permitidos = (
            "PUT_COMPRA",
            "PUT_DEBIT_SPREAD",
            "PUT_POZINHO",
        )

    selecionados = [
        item for item in candidatos
        if (
            item.get("estrategia") in tipos_permitidos
            and item.get("executavel") is True
        )
    ]

    return {
        "direcao": direcao,
        "total_selecionado": len(selecionados),
        "selecionados": selecionados,
        "motivo": (
            "Seleção direcional automática. "
            "Ainda não representa recomendação final."
        ),
    }

