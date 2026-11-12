
"""
Calendário de opções da B3.

Calcula dias corridos e pregões entre a data de referência
e o vencimento de uma opção.

O calendário de feriados deve ser fornecido por uma fonte
oficial ou validada. Sem essa informação, o sistema não
deve afirmar que conhece a quantidade exata de pregões.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo


FUSO_HORARIO = ZoneInfo("America/Sao_Paulo")


class ErroCalendario(Exception):
    """Erro de calendário ou vencimento."""


def obter_data_atual():
    """Retorna a data atual no horário de Brasília."""
    return datetime.now(FUSO_HORARIO).date()


def validar_datas(data_referencia, vencimento):
    """Valida as datas recebidas."""

    if not isinstance(data_referencia, date):
        raise ErroCalendario(
            "A data de referência deve ser datetime.date."
        )

    if not isinstance(vencimento, date):
        raise ErroCalendario(
            "O vencimento deve ser datetime.date."
        )

    if vencimento < data_referencia:
        raise ErroCalendario(
            "O vencimento não pode ser anterior à data de referência."
        )


def dias_corridos(data_referencia, vencimento):
    """Calcula a quantidade de dias corridos."""

    validar_datas(data_referencia, vencimento)

    return (vencimento - data_referencia).days


def calcular_pregoes(
    data_referencia,
    vencimento,
    feriados=None,
    calendario_validado=False
):
    """
    Calcula pregões restantes.

    feriados:
        Conjunto ou lista de datas sem negociação.

    calendario_validado:
        Deve ser True somente quando a lista de feriados
        vier de uma fonte oficial ou validada.

    Sem calendário validado, o resultado é apenas uma
    estimativa de dias úteis, nunca uma contagem oficial.
    """

    validar_datas(data_referencia, vencimento)

    if not calendario_validado:
        raise ErroCalendario(
            "Calendário de feriados não validado. "
            "Não é possível calcular pregões com precisão."
        )

    if feriados is None:
        raise ErroCalendario(
            "É necessário informar a lista de feriados."
        )

    feriados = set(feriados)

    for feriado in feriados:
        if not isinstance(feriado, date):
            raise ErroCalendario(
                "Todos os feriados devem ser objetos datetime.date."
            )

    quantidade = 0

    dia = data_referencia

    while dia < vencimento:

        dia = date.fromordinal(dia.toordinal() + 1)

        dia_semana = dia.weekday()

        if dia_semana < 5 and dia not in feriados:
            quantidade += 1

    return quantidade


def analisar_vencimento(
    data_referencia,
    vencimento,
    feriados=None,
    calendario_validado=False
):
    """
    Retorna um resumo temporal da opção.

    Se o calendário não estiver validado, os pregões
    serão informados como indisponíveis.
    """

    validar_datas(data_referencia, vencimento)

    resultado = {
        "data_referencia": data_referencia.isoformat(),
        "vencimento": vencimento.isoformat(),
        "dias_corridos": dias_corridos(
            data_referencia,
            vencimento
        ),
        "pregoes": None,
        "calendario_validado": calendario_validado,
    }

    if calendario_validado and feriados is not None:

        resultado["pregoes"] = calcular_pregoes(
            data_referencia=data_referencia,
            vencimento=vencimento,
            feriados=feriados,
            calendario_validado=True,
        )

    return resultado


if __name__ == "__main__":

    hoje = obter_data_atual()

    print("Calendário do Analisador de Opções")
    print(f"Data de referência: {hoje}")
    print("Calendário de feriados: aguardando integração.")

