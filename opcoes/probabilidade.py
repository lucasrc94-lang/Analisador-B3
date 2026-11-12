
"""
Módulo de probabilidades do Analisador de Opções B3.

Calcula separadamente:
1. Probabilidade de terminar acima de um preço.
2. Probabilidade de terminar abaixo de um preço.
3. Probabilidade de tocar um alvo durante o período.
4. Probabilidade estimada de lucro de CALL ou PUT comprada
   no vencimento.

Modelo: movimento geométrico browniano/lognormal.

As probabilidades são estimativas condicionadas às premissas
do modelo. Não representam garantias de resultado.
"""

import math
from statistics import NormalDist


class ErroProbabilidade(Exception):
    """Erro nos parâmetros de probabilidade."""


NORMAL = NormalDist()


def validar_parametros(S, T, r, sigma, q):
    """Valida os parâmetros gerais do modelo."""

    valores = (S, T, r, sigma, q)

    if not all(math.isfinite(float(x)) for x in valores):
        raise ErroProbabilidade(
            "Todos os parâmetros devem ser números finitos."
        )

    if S <= 0:
        raise ErroProbabilidade(
            "O preço do ativo deve ser positivo."
        )

    if T <= 0:
        raise ErroProbabilidade(
            "O tempo até o vencimento deve ser positivo."
        )

    if sigma <= 0:
        raise ErroProbabilidade(
            "A volatilidade deve ser positiva."
        )


def limitar_probabilidade(valor):
    """Mantém o resultado dentro do intervalo de 0 a 1."""

    return max(0.0, min(1.0, float(valor)))


def probabilidade_terminar_acima(
    S, alvo, T, r, sigma, q
):
    """
    Probabilidade de o ativo terminar acima do alvo no vencimento.

    Retorno decimal:
    0.70 = 70%.
    """

    validar_parametros(S, T, r, sigma, q)

    if alvo <= 0:
        raise ErroProbabilidade(
            "O alvo deve ser positivo."
        )

    if S >= alvo:
        d2 = (
            math.log(S / alvo)
            + (r - q - 0.5 * sigma ** 2) * T
        ) / (sigma * math.sqrt(T))

    else:
        d2 = (
            math.log(S / alvo)
            + (r - q - 0.5 * sigma ** 2) * T
        ) / (sigma * math.sqrt(T))

    return limitar_probabilidade(NORMAL.cdf(d2))


def probabilidade_terminar_abaixo(
    S, alvo, T, r, sigma, q
):
    """
    Probabilidade de o ativo terminar abaixo do alvo no vencimento.
    """

    return limitar_probabilidade(
        1 - probabilidade_terminar_acima(
            S, alvo, T, r, sigma, q
        )
    )


def probabilidade_toque_superior(
    S, alvo, T, r, sigma, q
):
    """
    Probabilidade de o ativo tocar ou ultrapassar um alvo superior
    em algum momento até o vencimento.

    Considera a trajetória do preço, não apenas o fechamento final.
    """

    validar_parametros(S, T, r, sigma, q)

    if alvo <= 0:
        raise ErroProbabilidade(
            "O alvo deve ser positivo."
        )

    if alvo <= S:
        return 1.0

    a = math.log(alvo / S)
    mu = r - q - 0.5 * sigma ** 2
    desvio = sigma * math.sqrt(T)

    primeiro_termo = NORMAL.cdf(
        (mu * T - a) / desvio
    )

    expoente = 2 * mu * a / (sigma ** 2)

    try:
        segundo_termo = (
            math.exp(expoente)
            * NORMAL.cdf(
                (-mu * T - a) / desvio
            )
        )
    except OverflowError:
        segundo_termo = 0.0

    return limitar_probabilidade(
        primeiro_termo + segundo_termo
    )


def probabilidade_toque_inferior(
    S, alvo, T, r, sigma, q
):
    """
    Probabilidade de o ativo tocar ou ficar abaixo de um alvo
    inferior em algum momento até o vencimento.
    """

    validar_parametros(S, T, r, sigma, q)

    if alvo <= 0:
        raise ErroProbabilidade(
            "O alvo deve ser positivo."
        )

    if alvo >= S:
        return 1.0

    a = math.log(S / alvo)
    mu = r - q - 0.5 * sigma ** 2
    desvio = sigma * math.sqrt(T)

    primeiro_termo = NORMAL.cdf(
        (-mu * T - a) / desvio
    )

    expoente = -2 * mu * a / (sigma ** 2)

    try:
        segundo_termo = (
            math.exp(expoente)
            * NORMAL.cdf(
                (mu * T - a) / desvio
            )
        )
    except OverflowError:
        segundo_termo = 0.0

    return limitar_probabilidade(
        primeiro_termo + segundo_termo
    )


def probabilidade_lucro_opcao(
    tipo, S, ponto_equilibrio, T, r, sigma, q
):
    """
    Probabilidade estimada de lucro no vencimento
    para uma CALL ou PUT comprada.

    CALL: ativo acima do ponto de equilíbrio.
    PUT: ativo abaixo do ponto de equilíbrio.

    Não calcula a probabilidade de lucro de spreads.
    """

    tipo = str(tipo).upper()

    if tipo not in ("CALL", "PUT"):
        raise ErroProbabilidade(
            "O tipo deve ser CALL ou PUT."
        )

    if ponto_equilibrio <= 0:
        raise ErroProbabilidade(
            "O ponto de equilíbrio deve ser positivo."
        )

    if tipo == "CALL":
        return probabilidade_terminar_acima(
            S,
            ponto_equilibrio,
            T,
            r,
            sigma,
            q
        )

    return probabilidade_terminar_abaixo(
        S,
        ponto_equilibrio,
        T,
        r,
        sigma,
        q
    )


def analisar_probabilidades(
    S, alvo_superior, alvo_inferior,
    T, r, sigma, q
):
    """
    Consolida as probabilidades dos dois alvos.

    Os eventos de toque superior e inferior são apresentados
    separadamente. Não devem ser somados como se fossem
    eventos mutuamente exclusivos.
    """

    return {
        "modelo": "lognormal",
        "probabilidade_terminar_acima_alvo": (
            probabilidade_terminar_acima(
                S, alvo_superior, T, r, sigma, q
            )
        ),
        "probabilidade_terminar_abaixo_alvo": (
            probabilidade_terminar_abaixo(
                S, alvo_inferior, T, r, sigma, q
            )
        ),
        "probabilidade_tocar_alvo_superior": (
            probabilidade_toque_superior(
                S, alvo_superior, T, r, sigma, q
            )
        ),
        "probabilidade_tocar_alvo_inferior": (
            probabilidade_toque_inferior(
                S, alvo_inferior, T, r, sigma, q
            )
        ),
        "premissas": {
            "distribuicao": "lognormal",
            "taxa_livre_risco": r,
            "dividend_yield": q,
            "volatilidade_anualizada": sigma,
            "tempo_em_anos": T,
        },
        "aviso": (
            "Probabilidades estimadas pelo modelo. "
            "Não representam garantia de resultado."
        ),
    }


if __name__ == "__main__":

    resultado = analisar_probabilidades(
        S=35.00,
        alvo_superior=37.00,
        alvo_inferior=33.00,
        T=30 / 252,
        r=0.12,
        sigma=0.35,
        q=0.00,
    )

    for chave, valor in resultado.items():
        print(f"{chave}: {valor}")

