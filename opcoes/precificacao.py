
"""
Precificação teórica de opções pelo modelo Black-Scholes.

Modelo de referência para opções europeias.
Os resultados não representam necessariamente o preço
justo de opções americanas negociadas na B3.
"""

import math


class ErroPrecificacao(Exception):
    """Erro nos parâmetros de precificação."""


def validar_parametros(S, K, T, r, sigma):
    """Valida os parâmetros do modelo."""

    if S <= 0 or K <= 0:
        raise ErroPrecificacao(
            "Preço do ativo e strike devem ser positivos."
        )

    if T <= 0:
        raise ErroPrecificacao(
            "O tempo até o vencimento deve ser positivo."
        )

    if sigma <= 0:
        raise ErroPrecificacao(
            "A volatilidade deve ser positiva."
        )

    if not all(
        math.isfinite(x)
        for x in (S, K, T, r, sigma)
    ):
        raise ErroPrecificacao(
            "Todos os parâmetros devem ser números finitos."
        )


def distribuicao_normal(x):
    """Função de distribuição acumulada normal padrão."""

    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def densidade_normal(x):
    """Função densidade da distribuição normal padrão."""

    return (
        math.exp(-0.5 * x ** 2)
        / math.sqrt(2 * math.pi)
    )


def calcular_precificacao(S, K, T, r, sigma, tipo):
    """
    Calcula preço teórico e gregas.

    S: preço atual do ativo.
    K: strike.
    T: tempo até o vencimento em anos.
    r: taxa livre de risco anualizada em decimal.
    sigma: volatilidade anualizada em decimal.
    tipo: CALL ou PUT.
    """

    validar_parametros(S, K, T, r, sigma)

    tipo = str(tipo).upper()

    if tipo not in ("CALL", "PUT"):
        raise ErroPrecificacao(
            "O tipo deve ser CALL ou PUT."
        )

    raiz_T = math.sqrt(T)

    d1 = (
        math.log(S / K)
        + (r + 0.5 * sigma ** 2) * T
    ) / (sigma * raiz_T)

    d2 = d1 - sigma * raiz_T

    nd1 = distribuicao_normal(d1)
    nd2 = distribuicao_normal(d2)

    n_d1 = densidade_normal(d1)

    desconto = math.exp(-r * T)

    gamma = n_d1 / (S * sigma * raiz_T)

    vega = (
        S * n_d1 * raiz_T
    ) / 100

    if tipo == "CALL":

        preco = (
            S * nd1
            - K * desconto * nd2
        )

        delta = nd1

        theta = (
            -(S * n_d1 * sigma) / (2 * raiz_T)
            - r * K * desconto * nd2
        ) / 365

    else:

        preco = (
            K * desconto * (1 - nd2)
            - S * (1 - nd1)
        )

        delta = nd1 - 1

        theta = (
            -(S * n_d1 * sigma) / (2 * raiz_T)
            + r * K * desconto * (1 - nd2)
        ) / 365

    return {
        "modelo": "Black-Scholes",
        "tipo": tipo,
        "preco_teorico": float(preco),
        "delta": float(delta),
        "gamma": float(gamma),
        "theta_dia": float(theta),
        "vega_1pp": float(vega),
        "d1": float(d1),
        "d2": float(d2),
        "volatilidade_anualizada": float(sigma),
        "tempo_anos": float(T),
        "premissa": (
            "Modelo europeu; não representa garantia "
            "de preço executável na B3."
        ),
    }


if __name__ == "__main__":

    resultado = calcular_precificacao(
        S=35.00,
        K=36.00,
        T=30 / 252,
        r=0.12,
        sigma=0.35,
        tipo="CALL",
    )

    for chave, valor in resultado.items():
        print(f"{chave}: {valor}")

