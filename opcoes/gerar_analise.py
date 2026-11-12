
"""
Integração central do Analisador de Opções B3.

Responsabilidades:
- Receber dados coletados.
- Normalizar registros.
- Validar integridade.
- Aplicar filtros de qualidade.
- Gerar estratégias candidatas.
- Realizar seleção automática.
- Consolidar indicadores de volatilidade.

Esta versão não emite recomendação definitiva.
Probabilidade e risco financeiro serão integrados
após a conferência das interfaces dos respectivos módulos.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from opcoes.normalizar_dados import normalizar_registros
from opcoes.validar_dados import validar_conjunto
from opcoes.filtros import filtrar_opcoes
from opcoes.estrategias import (
    gerar_candidatos,
    selecionar_automaticamente,
)
from opcoes.volatilidade import analisar_volatilidade


FUSO_HORARIO = ZoneInfo("America/Sao_Paulo")


class ErroAnalise(Exception):
    """Erro durante a geração da análise consolidada."""


def extrair_registros_normalizados(resultado):
    """Extrai os registros válidos da normalização."""

    if not isinstance(resultado, dict):
        raise ErroAnalise(
            "Resultado da normalização em formato inválido."
        )

    registros = resultado.get("validos")

    if registros is None:
        registros = resultado.get("registros_validos")

    if registros is None:
        raise ErroAnalise(
            "A normalização não retornou a lista de registros válidos."
        )

    if not isinstance(registros, list):
        raise ErroAnalise(
            "A lista de registros normalizados é inválida."
        )

    return registros


def obter_registros_por_codigo(registros, codigos):
    """Recupera os registros originais pelos códigos aprovados."""

    codigos = set(codigos)

    return [
        registro
        for registro in registros
        if registro.get("codigo_opcao") in codigos
    ]


def gerar_analise(
    dados_coletados,
    historico_precos=None,
    direcao=None,
    preco_ativo=None,
    premio_maximo_pozinho=None,
):
    """
    Gera análise consolidada das opções de um ativo.

    Args:
        dados_coletados:
            Dicionário retornado por coletar_opcoes().

        historico_precos:
            DataFrame histórico do ativo subjacente.

        direcao:
            ALTA, BAIXA ou NEUTRA.
            Deve vir de uma análise direcional validada.

        preco_ativo:
            Preço atual validado do ativo subjacente.

        premio_maximo_pozinho:
            Limite de prêmio definido para a triagem dos pozinhos.

    Returns:
        Dicionário com validações, filtros, volatilidade
        e estratégias candidatas.
    """

    if not isinstance(dados_coletados, dict):
        raise ErroAnalise(
            "Os dados coletados devem ser um dicionário."
        )

    data_referencia = dados_coletados.get("data_referencia")

    if not data_referencia:
        raise ErroAnalise(
            "Data de referência ausente nos dados coletados."
        )

    registros_brutos = dados_coletados.get("dados")

    if not isinstance(registros_brutos, list):
        raise ErroAnalise(
            "A coleta não apresentou uma lista válida de dados."
        )

    # 1. Normalização

    resultado_normalizacao = normalizar_registros(
        dados_coletados
    )

    registros = extrair_registros_normalizados(
        resultado_normalizacao
    )

    # 2. Validação de integridade

    resultado_validacao = validar_conjunto(
        registros,
        data_referencia=data_referencia,
    )

    codigos_validos = {
        item["codigo_opcao"]
        for item in resultado_validacao["validos"]
        if item.get("codigo_opcao")
    }

    registros_validos = obter_registros_por_codigo(
        registros,
        codigos_validos,
    )

    # 3. Filtros de liquidez e qualidade

    resultado_filtros = filtrar_opcoes(
        registros_validos
    )

    codigos_aprovados = {
        item["codigo_opcao"]
        for item in resultado_filtros["aprovadas"]
        if item.get("codigo_opcao")
    }

    registros_aprovados = obter_registros_por_codigo(
        registros_validos,
        codigos_aprovados,
    )

    # 4. Indicadores de volatilidade

    resultado_volatilidade = None

    if historico_precos is not None:
        try:
            resultado_volatilidade = analisar_volatilidade(
                historico_precos
            )

        except Exception as erro:
            resultado_volatilidade = {
                "disponivel": False,
                "erro": str(erro),
            }

    # 5. Geração das estratégias candidatas

    resultado_estrategias = gerar_candidatos(
        registros_aprovados,
        preco_ativo=preco_ativo,
        premio_maximo_pozinho=premio_maximo_pozinho,
    )

    # 6. Seleção automática

    resultado_selecao = None

    if direcao is not None:
        resultado_selecao = selecionar_automaticamente(
            resultado_estrategias["candidatos"],
            direcao,
        )

    # 7. Consolidação

    relatorio = {
        "sistema": "Analisador de Opções B3",
        "versao": "0.1.0",
        "gerado_em": datetime.now(
            FUSO_HORARIO
        ).isoformat(),

        "fonte_dados": dados_coletados.get("fonte"),
        "tipo_dado": dados_coletados.get("tipo_dado"),
        "data_referencia": data_referencia,

        "resumo": {
            "total_coletado": len(registros_brutos),
            "total_normalizado": len(registros),
            "total_validado": len(registros_validos),
            "total_aprovado_filtros": (
                resultado_filtros["total_aprovado"]
            ),
            "total_reprovado_filtros": (
                resultado_filtros["total_reprovado"]
            ),
            "total_candidatos": (
                resultado_estrategias["total_candidatos"]
            ),
            "total_candidatos_executaveis": len(
                resultado_estrategias["executaveis"]
            ),
            "total_candidatos_teoricos": len(
                resultado_estrategias["teoricos"]
            ),
        },

        "normalizacao": resultado_normalizacao,
        "validacao": resultado_validacao,
        "filtros": resultado_filtros,
        "volatilidade": resultado_volatilidade,
        "estrategias": resultado_estrategias,
        "selecao_automatica": resultado_selecao,

        "status_recomendacao": "NAO_EMITIDA",

        "pendencias": [
            "Validar a compatibilidade real da fonte de dados.",
            "Confirmar bid e ask executáveis.",
            "Integrar probabilidades calibradas.",
            "Integrar cálculos de risco por estratégia.",
            "Validar multiplicadores e características dos contratos.",
            "Validar vencimentos e calendário oficial da B3.",
        ],

        "observacao": (
            "Este relatório apresenta candidatas para análise. "
            "Não constitui recomendação de investimento."
        ),
    }

    return relatorio


if __name__ == "__main__":
    print(
        "Módulo gerar_analise.py carregado. "
        "A execução depende de dados coletados e normalizados."
    )

