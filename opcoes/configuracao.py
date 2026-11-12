
"""
Configuracao central do Analisador de Opcoes da B3.

Este arquivo concentra os parametros e as regras gerais do sistema.
Os demais modulos devem importar suas configuracoes daqui.
"""

from pathlib import Path


# ============================================================
# 1. IDENTIFICACAO DO SISTEMA
# ============================================================

NOME_SISTEMA = "Analisador de Opcoes B3"
VERSAO = "0.1.0"

FUSO_HORARIO = "America/Sao_Paulo"

# Fonte inicial provisoria de dados.
# A compatibilidade e a qualidade dos dados serao validadas
# pelo modulo coletar_opcoes.py.
FONTE_DADOS = "b3quant"


# ============================================================
# 2. CAMINHOS DO PROJETO
# ============================================================

RAIZ_PROJETO = Path(__file__).resolve().parent.parent

PASTA_DADOS = RAIZ_PROJETO / "dados"

ARQUIVO_DADOS_OPCOES = PASTA_DADOS / "opcoes.json"


# ============================================================
# 3. REGRAS DAS ESTRATEGIAS
# ============================================================

# Travas: somente operacoes de debito.
REGRA_TRAVAS = "debit"

# Pozinhos: analisar CALL e PUT.
REGRA_POZINHOS = "both"

# Sugestoes de estrategias realizadas automaticamente.
REGRA_SUGESTOES = "automatic"

# Percentual maximo de debito em relacao a largura da trava.
PERCENTUAL_MAXIMO_DEBITO_TRAVA = 0.20

# Estrategias autorizadas para analise inicial.
ESTRATEGIAS_PERMITIDAS = [
    "CALL_COMPRA",
    "PUT_COMPRA",
    "CALL_DEBIT_SPREAD",
    "PUT_DEBIT_SPREAD",
    "CALL_POZINHO",
    "PUT_POZINHO",
]


# ============================================================
# 4. FILTROS DE LIQUIDEZ
# ============================================================

# Parametros iniciais de triagem.
# Serao revisados apos a validacao da fonte de dados.

VOLUME_MINIMO_OPCAO = 1

OPEN_INTEREST_MINIMO = 10

# Spread maximo entre bid e ask em relacao ao preco medio.
# 0.30 = 30%.
SPREAD_MAXIMO_RELATIVO = 0.30

# Sem bid ou ask valido, a operacao nao sera considerada
# executavel. Precos teoricos devem ser identificados separadamente.
EXIGIR_BID_ASK_VALIDOS = True


# ============================================================
# 5. PARAMETROS DE VOLATILIDADE
# ============================================================

PERIODO_VOLATILIDADE_HISTORICA = 20

PERIODO_ATR = 14

# Limites de alerta para volatilidade implicita.
# Valores expressos em decimal: 1.00 = 100%.
IV_MINIMA_ALERTA = 0.00

IV_MAXIMA_ALERTA = 3.00

DIAS_UTEIS_ANO = 252

# ============================================================
# 6. PARAMETROS DE PROBABILIDADE
# ============================================================

# Modelo inicial de probabilidade:
# distribuicao lognormal, sujeito a validacao e calibracao.

MODELO_PROBABILIDADE = "lognormal"

# A taxa livre de risco devera ser fornecida por uma fonte
# validada. Nao utilizar um valor fixo sem atualizacao.
TAXA_LIVRE_RISCO = None

# Probabilidades devem ser apresentadas como estimativas.
PROBABILIDADE_E_GARANTIA = False


# ============================================================
# 7. CONTROLE DE DADOS
# ============================================================

# Dados antigos ou incompletos nao devem gerar recomendacoes.

IDADE_MAXIMA_DADOS_HORAS = 24

EXIGIR_DATA_REFERENCIA = True

EXIGIR_VENCIMENTO_REAL = True

EXIGIR_STRIKE_VALIDO = True

EXIGIR_PRECO_VALIDO = True

EXIGIR_ATIVO_SUBJACENTE = True


# ============================================================
# 8. CONTROLE DE RISCO
# ============================================================

# A perda maxima deve ser calculada para cada estrutura.
# Nao existe limite monetario universal definido neste arquivo.

CALCULAR_PERDA_MAXIMA = True

CALCULAR_LUCRO_MAXIMO = True

CALCULAR_PONTO_EQUILIBRIO = True

CALCULAR_PROBABILIDADE_LUCRO = True

CALCULAR_TEMPO_ESTIMADO_ALVO = True

ALERTA_THETA = True


# ============================================================
# 9. VALIDACAO DAS CONFIGURACOES
# ============================================================

def validar_configuracao():
    """
    Verifica se os parametros essenciais estao coerentes.
    """

    if not 0 < PERCENTUAL_MAXIMO_DEBITO_TRAVA <= 1:
        raise ValueError(
            "O percentual maximo de debito da trava deve "
            "estar entre 0 e 1."
        )

    if REGRA_TRAVAS != "debit":
        raise ValueError(
            "A configuracao atual permite somente travas de debito."
        )

    if REGRA_POZINHOS not in ("call", "put", "both"):
        raise ValueError(
            "Regra de pozinhos invalida."
        )

    if REGRA_SUGESTOES != "automatic":
        raise ValueError(
            "A regra de sugestoes deve ser automatic."
        )

    if VOLUME_MINIMO_OPCAO < 0:
        raise ValueError(
            "O volume minimo nao pode ser negativo."
        )

    if OPEN_INTEREST_MINIMO < 0:
        raise ValueError(
            "O open interest minimo nao pode ser negativo."
        )

    if SPREAD_MAXIMO_RELATIVO <= 0:
        raise ValueError(
            "O spread maximo relativo deve ser positivo."
        )

    return True


if __name__ == "__main__":
    validar_configuracao()
    print(f"{NOME_SISTEMA} - configuracao validada.")
    print(f"Versao: {VERSAO}")
    print(f"Fonte inicial: {FONTE_DADOS}")

