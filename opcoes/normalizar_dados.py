
"""
Normalização dos dados históricos de opções da B3.

Padroniza os registros recebidos pela coleta e identifica
campos essenciais ausentes ou inválidos.
"""

from datetime import datetime
import re
import unicodedata

import pandas as pd


CAMPOS_OBRIGATORIOS = [
    "codigo_opcao",
    "tipo",
    "strike",
    "vencimento",
    "preco_fechamento",
    "ativo_subjacente",
]

ALIASES = {
    "codigo_opcao": [
        "codigo_opcao", "codigo", "ticker", "symbol",
        "instrumento", "nome"
    ],
    "tipo": [
        "tipo", "tipo_opcao", "option_type", "call_put"
    ],
    "strike": [
        "strike", "preco_exercicio", "preco_exercicio_opcao"
    ],
    "vencimento": [
        "vencimento", "data_vencimento", "expiration",
        "expiration_date"
    ],
    "preco_fechamento": [
        "preco_fechamento", "fechamento", "preco",
        "ultimo", "last", "close"
    ],
    "ativo_subjacente": [
        "ativo_subjacente", "ativo", "underlying",
        "codigo_ativo", "ticker_ativo"
    ],
    "volume": [
        "volume", "quantidade_negociada", "volume_negociado"
    ],
    "bid": [
        "bid", "melhor_compra", "preco_compra"
    ],
    "ask": [
        "ask", "melhor_venda", "preco_venda"
    ],
    "open_interest": [
        "open_interest", "interesse_aberto"
    ],
}


def normalizar_nome_coluna(nome):
    """Padroniza nomes de colunas."""

    texto = str(nome).strip().lower()

    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )

    texto = re.sub(r"[^a-z0-9]+", "_", texto)

    return texto.strip("_")


def identificar_colunas(df):
    """Relaciona os nomes originais aos campos padronizados."""

    mapa = {}

    colunas_normalizadas = {
        coluna: normalizar_nome_coluna(coluna)
        for coluna in df.columns
    }

    for campo, alternativas in ALIASES.items():

        alternativas_normalizadas = [
            normalizar_nome_coluna(item)
            for item in alternativas
        ]

        for original, normalizado in colunas_normalizadas.items():

            if normalizado in alternativas_normalizadas:
                mapa[campo] = original
                break

    return mapa


def converter_numero(valor):
    """Converte valores numéricos sem inventar valores ausentes."""

    if valor is None or pd.isna(valor):
        return None

    try:
        return float(valor)

    except (ValueError, TypeError):
        return None


def converter_data(valor):
    """Converte datas para o padrão ISO."""

    if valor is None or pd.isna(valor):
        return None

    try:
        data = pd.to_datetime(
            valor,
            errors="coerce",
            dayfirst=True
        )

        if pd.isna(data):
            return None

        return data.date().isoformat()

    except (ValueError, TypeError):
        return None


def normalizar_tipo(valor):
    """Identifica CALL ou PUT quando a informação está disponível."""

    if valor is None or pd.isna(valor):
        return None

    texto = str(valor).strip().upper()

    if texto in ("CALL", "C"):
        return "CALL"

    if texto in ("PUT", "P"):
        return "PUT"

    return None


def normalizar_registros(dados):
    """
    Recebe os dados retornados por coletar_opcoes()
    e produz registros padronizados.

    Registros incompletos são preservados na auditoria,
    mas não são considerados válidos para estratégias.
    """

    if not isinstance(dados, dict):
        raise ValueError("Os dados recebidos devem ser um dicionário.")

    registros = dados.get("dados")

    if not isinstance(registros, list) or not registros:
        raise ValueError("Não existem registros para normalizar.")

    df = pd.DataFrame(registros)

    if df.empty:
        raise ValueError("A tabela de opções está vazia.")

    mapa = identificar_colunas(df)

    resultado = []

    for _, linha in df.iterrows():

        registro = {}

        for campo, coluna in mapa.items():
            registro[campo] = linha[coluna]

        registro_padronizado = {
            "codigo_opcao": (
                str(registro.get("codigo_opcao")).strip()
                if registro.get("codigo_opcao") is not None
                and not pd.isna(registro.get("codigo_opcao"))
                else None
            ),
            "tipo": normalizar_tipo(registro.get("tipo")),
            "strike": converter_numero(registro.get("strike")),
            "vencimento": converter_data(registro.get("vencimento")),
            "preco_fechamento": converter_numero(
                registro.get("preco_fechamento")
            ),
            "ativo_subjacente": (
                str(registro.get("ativo_subjacente")).strip().upper()
                if registro.get("ativo_subjacente") is not None
                and not pd.isna(registro.get("ativo_subjacente"))
                else None
            ),
            "volume": converter_numero(registro.get("volume")),
            "bid": converter_numero(registro.get("bid")),
            "ask": converter_numero(registro.get("ask")),
            "open_interest": converter_numero(
                registro.get("open_interest")
            ),
        }

        pendencias = []

        for campo in CAMPOS_OBRIGATORIOS:

            valor = registro_padronizado.get(campo)

            if valor is None:
                pendencias.append(campo)

        if registro_padronizado["strike"] is not None:
            if registro_padronizado["strike"] <= 0:
                pendencias.append("strike_invalido")

        if registro_padronizado["preco_fechamento"] is not None:
            if registro_padronizado["preco_fechamento"] < 0:
                pendencias.append("preco_fechamento_invalido")

        if (
            registro_padronizado["vencimento"] is not None
            and registro_padronizado["vencimento"]
            < dados["data_referencia"]
        ):
            pendencias.append("vencimento_expirado")

        registro_padronizado["valido"] = len(pendencias) == 0
        registro_padronizado["pendencias"] = pendencias

        resultado.append(registro_padronizado)

    validos = sum(
        1 for registro in resultado
        if registro["valido"]
    )

    return {
        "fonte": dados.get("fonte"),
        "data_referencia": dados.get("data_referencia"),
        "normalizado_em": datetime.now().isoformat(),
        "total_registros": len(resultado),
        "registros_validos": validos,
        "registros_invalidos": len(resultado) - validos,
        "dados": resultado,
    }
