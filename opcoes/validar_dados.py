
"""
Validação de integridade dos dados do Analisador de Opções B3.

Verifica:
- Data de referência.
- Código da opção.
- Tipo CALL ou PUT.
- Ativo subjacente.
- Strike.
- Vencimento.
- Preço de fechamento.

Não substitui os filtros de liquidez nem a validação
do calendário oficial de pregões da B3.
"""

import math
from datetime import date

from opcoes.configuracao import (
    EXIGIR_DATA_REFERENCIA,
    EXIGIR_VENCIMENTO_REAL,
    EXIGIR_STRIKE_VALIDO,
    EXIGIR_PRECO_VALIDO,
    EXIGIR_ATIVO_SUBJACENTE,
)


class ErroValidacao(Exception):
    """Erro na validação dos dados."""


def converter_data(valor):
    """Converte uma data ISO para datetime.date."""

    if isinstance(valor, date):
        return valor

    if not isinstance(valor, str) or not valor.strip():
        return None

    try:
        return date.fromisoformat(valor[:10])
    except ValueError:
        return None


def numero_positivo(valor):
    """Verifica se o valor é numérico, finito e positivo."""

    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return False

    return math.isfinite(numero) and numero > 0


def validar_opcao(opcao, data_referencia):
    """
    Valida um registro individual de opção normalizada.

    Retorna o resultado da validação e os motivos de rejeição.
    """

    if not isinstance(opcao, dict):
        raise ErroValidacao(
            "Cada registro deve ser um dicionário."
        )

    motivos = []

    # 1. Código da opção

    if not opcao.get("codigo_opcao"):
        motivos.append("Código da opção ausente.")

    # 2. Tipo

    tipo = str(opcao.get("tipo", "")).upper()

    if tipo not in ("CALL", "PUT"):
        motivos.append("Tipo de opção inválido.")

    # 3. Ativo subjacente

    if EXIGIR_ATIVO_SUBJACENTE:
        if not opcao.get("ativo_subjacente"):
            motivos.append("Ativo subjacente ausente.")

    # 4. Strike

    if EXIGIR_STRIKE_VALIDO:
        if not numero_positivo(opcao.get("strike")):
            motivos.append("Strike ausente ou inválido.")

    # 5. Preço de fechamento

    if EXIGIR_PRECO_VALIDO:
        if not numero_positivo(opcao.get("preco_fechamento")):
            motivos.append("Preço de fechamento ausente ou inválido.")

    # 6. Vencimento

    vencimento = converter_data(opcao.get("vencimento"))

    if EXIGIR_VENCIMENTO_REAL:
        if vencimento is None:
            motivos.append("Vencimento ausente ou inválido.")
        elif vencimento < data_referencia:
            motivos.append("Vencimento anterior à data de referência.")

    valido = len(motivos) == 0

    return {
        "codigo_opcao": opcao.get("codigo_opcao"),
        "valido": valido,
        "status": "VALIDO" if valido else "INVALIDO",
        "motivos": motivos,
    }


def validar_conjunto(registros, data_referencia=None):
    """
    Valida uma lista de opções normalizadas.

    Args:
        registros: lista de dicionários normalizados.
        data_referencia: data ISO ou datetime.date.

    Returns:
        Dicionário com registros válidos, inválidos e resumo.
    """

    if not isinstance(registros, list):
        raise ErroValidacao(
            "Os registros devem ser fornecidos em uma lista."
        )

    data = converter_data(data_referencia)

    if EXIGIR_DATA_REFERENCIA and data is None:
        raise ErroValidacao(
            "Data de referência ausente ou inválida."
        )

    if data is None:
        raise ErroValidacao(
            "Não é possível validar vencimentos sem "
            "uma data de referência válida."
        )

    resultados = []

    for opcao in registros:
        resultados.append(
            validar_opcao(opcao, data)
        )

    validos = [
        resultado for resultado in resultados
        if resultado["valido"]
    ]

    invalidos = [
        resultado for resultado in resultados
        if not resultado["valido"]
    ]

    return {
        "data_referencia": data.isoformat(),
        "total_analisado": len(resultados),
        "total_validos": len(validos),
        "total_invalidos": len(invalidos),
        "validos": validos,
        "invalidos": invalidos,
        "resultados": resultados,
    }

