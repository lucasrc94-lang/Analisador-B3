
"""
Módulo de gestão de risco do Analisador de Opções B3.

Calcula:
- Perda máxima.
- Lucro máximo.
- Ponto de equilíbrio.
- Exposição financeira total.

Os cálculos são feitos por unidade do ativo e ajustados
pelo multiplicador e pela quantidade de contratos.

Custos operacionais, corretagem e impostos não estão
incluídos nesta versão.
"""

import math


class ErroRisco(Exception):
    """Erro nos parâmetros de risco."""


def validar_valor(nome, valor, permitir_zero=False):
    """Valida valores numéricos."""

    try:
        valor = float(valor)
    except (TypeError, ValueError):
        raise ErroRisco(f"{nome} deve ser numérico.")

    if not math.isfinite(valor):
        raise ErroRisco(f"{nome} deve ser finito.")

    if permitir_zero:
        if valor < 0:
            raise ErroRisco(f"{nome} não pode ser negativo.")
    elif valor <= 0:
        raise ErroRisco(f"{nome} deve ser positivo.")

    return valor


def validar_estrutura(tipo, quantidade, multiplicador):
    """Valida o tipo e a quantidade da operação."""

    tipo = str(tipo).upper()

    if tipo not in ("CALL", "PUT"):
        raise ErroRisco("Tipo deve ser CALL ou PUT.")

    if (
        isinstance(quantidade, bool)
        or not isinstance(quantidade, int)
        or quantidade <= 0
    ):
        raise ErroRisco(
            "A quantidade de contratos deve ser um inteiro positivo."
        )

    multiplicador = validar_valor(
        "Multiplicador",
        multiplicador
    )

    return tipo, quantidade, multiplicador


def calcular_risco_compra(
    tipo,
    strike,
    premio,
    quantidade=1,
    multiplicador=1
):
    """
    Calcula o risco de compra simples de CALL ou PUT.

    strike: preço de exercício por unidade do ativo.
    premio: prêmio pago por unidade do ativo.
    quantidade: número de contratos.
    multiplicador: unidades do ativo por contrato.
    """

    tipo, quantidade, multiplicador = validar_estrutura(
        tipo,
        quantidade,
        multiplicador
    )

    strike = validar_valor("Strike", strike)
    premio = validar_valor("Prêmio", premio)

    investimento = premio * quantidade * multiplicador

    if tipo == "CALL":
        ponto_equilibrio = strike + premio
        lucro_maximo = None
        observacao = "Lucro máximo teoricamente ilimitado."

    else:
        ponto_equilibrio = strike - premio
        lucro_maximo = (
            max(strike - premio, 0)
            * quantidade
            * multiplicador
        )
        observacao = (
            "Lucro máximo limitado pelo preço mínimo "
            "teórico do ativo igual a zero."
        )

    return {
        "estrategia": f"COMPRA_{tipo}",
        "quantidade_contratos": quantidade,
        "multiplicador": multiplicador,
        "premio_unitario": premio,
        "investimento_total": investimento,
        "perda_maxima": investimento,
        "lucro_maximo": lucro_maximo,
        "ponto_equilibrio": ponto_equilibrio,
        "custos_incluidos": False,
        "observacao": observacao,
    }


def calcular_trava_debito(
    tipo,
    strike_comprado,
    strike_vendido,
    premio_comprado,
    premio_vendido,
    quantidade=1,
    multiplicador=1
):
    """
    Calcula o risco de uma trava vertical de débito.

    CALL:
    - Compra o strike inferior.
    - Vende o strike superior.

    PUT:
    - Compra o strike superior.
    - Vende o strike inferior.
    """

    tipo, quantidade, multiplicador = validar_estrutura(
        tipo,
        quantidade,
        multiplicador
    )

    strike_comprado = validar_valor(
        "Strike comprado",
        strike_comprado
    )

    strike_vendido = validar_valor(
        "Strike vendido",
        strike_vendido
    )

    premio_comprado = validar_valor(
        "Prêmio da opção comprada",
        premio_comprado,
        permitir_zero=True
    )

    premio_vendido = validar_valor(
        "Prêmio da opção vendida",
        premio_vendido,
        permitir_zero=True
    )

    if tipo == "CALL":
        if strike_comprado >= strike_vendido:
            raise ErroRisco(
                "Na trava de CALL, o strike comprado "
                "deve ser inferior ao vendido."
            )

    else:
        if strike_comprado <= strike_vendido:
            raise ErroRisco(
                "Na trava de PUT, o strike comprado "
                "deve ser superior ao vendido."
            )

    largura = abs(strike_vendido - strike_comprado)

    debito = premio_comprado - premio_vendido

    if debito <= 0:
        raise ErroRisco(
            "A estrutura não apresenta débito positivo."
        )

    if debito >= largura:
        raise ErroRisco(
            "O débito deve ser inferior à largura da trava."
        )

    perda_maxima = debito * quantidade * multiplicador

    lucro_maximo = (
        (largura - debito)
        * quantidade
        * multiplicador
    )

    if tipo == "CALL":
        ponto_equilibrio = strike_comprado + debito
    else:
        ponto_equilibrio = strike_comprado - debito

    return {
        "estrategia": f"{tipo}_DEBIT_SPREAD",
        "quantidade_contratos": quantidade,
        "multiplicador": multiplicador,
        "strike_comprado": strike_comprado,
        "strike_vendido": strike_vendido,
        "largura_trava": largura,
        "premio_comprado": premio_comprado,
        "premio_vendido": premio_vendido,
        "debito_unitario": debito,
        "debito_total": perda_maxima,
        "perda_maxima": perda_maxima,
        "lucro_maximo": lucro_maximo,
        "ponto_equilibrio": ponto_equilibrio,
        "custos_incluidos": False,
        "observacao": (
            "Resultado calculado para manutenção da estrutura "
            "até o vencimento, sem custos operacionais."
        ),
    }


if __name__ == "__main__":

    resultado = calcular_trava_debito(
        tipo="CALL",
        strike_comprado=30.00,
        strike_vendido=32.00,
        premio_comprado=1.20,
        premio_vendido=0.80,
        quantidade=1,
        multiplicador=100,
    )

    for chave, valor in resultado.items():
        print(f"{chave}: {valor}")

