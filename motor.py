"""Motor técnico baseado nas funções do analisador avançado original do usuário."""
import math
import numpy as np
import pandas as pd

MESES_PNF = 6
REVERSAO_PF = 3
MULTIPLICADOR_BOX = 0.25
PERIODO_ACELERACAO = 5
LIMITE_CONSOLIDACAO_ATR = 3
MINIMO_DADOS = 220
MULTIPLICADOR_STOP_ATR = 1.00

def calcular_indicadores(dados):

    dados = dados.copy()

    # --------------------------------------------------------
    # MME 21
    # --------------------------------------------------------

    dados["MME21"] = dados["Fechamento"].ewm(
        span=21,
        adjust=False
    ).mean()

    # --------------------------------------------------------
    # MME 200
    # --------------------------------------------------------

    dados["MME200"] = dados["Fechamento"].ewm(
        span=200,
        adjust=False
    ).mean()

    # --------------------------------------------------------
    # TRUE RANGE
    # --------------------------------------------------------

    fechamento_anterior = dados["Fechamento"].shift(1)

    tr1 = dados["Maxima"] - dados["Minima"]

    tr2 = (
        dados["Maxima"] -
        fechamento_anterior
    ).abs()

    tr3 = (
        dados["Minima"] -
        fechamento_anterior
    ).abs()

    dados["TR"] = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)

    # --------------------------------------------------------
    # ATR 14
    # --------------------------------------------------------

    dados["ATR14"] = dados["TR"].rolling(
        window=14,
        min_periods=14
    ).mean()

    # --------------------------------------------------------
    # VOLUME MÉDIO 20
    # --------------------------------------------------------

    dados["VolumeMedia20"] = dados["Volume"].rolling(
        window=20,
        min_periods=20
    ).mean()

    # --------------------------------------------------------
    # VELOCIDADE
    # ATR / PREÇO
    # --------------------------------------------------------

    dados["Velocidade"] = (
        dados["ATR14"] /
        dados["Fechamento"]
    )

    return dados


# ============================================================
# CLASSIFICAÇÃO DA VELOCIDADE
# ============================================================

def classificar_velocidade(dados):

    serie = dados["Velocidade"].dropna()

    if len(serie) < 20:
        return "DADOS INSUFICIENTES"

    ultimos = serie.tail(60)

    valor_atual = ultimos.iloc[-1]

    p25 = ultimos.quantile(0.25)
    p50 = ultimos.quantile(0.50)
    p75 = ultimos.quantile(0.75)

    if valor_atual <= p25:
        return "MUITO LENTA"

    elif valor_atual <= p50:
        return "LENTA"

    elif valor_atual <= p75:
        return "NORMAL"

    else:
        return "RÁPIDA"


# ============================================================
# ACELERAÇÃO / DESACELERAÇÃO
# ============================================================

def analisar_aceleracao(dados):

    if len(dados) <= PERIODO_ACELERACAO:
        return "DADOS INSUFICIENTES"

    atual = dados.iloc[-1]
    anterior = dados.iloc[-1 - PERIODO_ACELERACAO]

    mme21_atual = atual["MME21"]
    mme21_anterior = anterior["MME21"]

    atr = atual["ATR14"]

    velocidade_atual = atual["Velocidade"]
    velocidade_anterior = anterior["Velocidade"]

    if pd.isna(atr) or atr <= 0:
        return "DADOS INSUFICIENTES"

    variacao_mme = (
        mme21_atual -
        mme21_anterior
    ) / atr

    variacao_velocidade = (
        velocidade_atual -
        velocidade_anterior
    )

    if variacao_mme > 0.10:

        if variacao_velocidade > 0:
            return "ACELERANDO ALTA"

        return "ALTA SEM ACELERAÇÃO"

    elif variacao_mme < -0.10:

        if variacao_velocidade > 0:
            return "ACELERANDO BAIXA"

        return "BAIXA SEM ACELERAÇÃO"

    return "ESTÁVEL"


# ============================================================
# CLASSIFICAÇÃO DA TENDÊNCIA
# ============================================================


def classificar_tendencia(linha):

    preco = linha["Fechamento"]
    mme21 = linha["MME21"]
    mme200 = linha["MME200"]

    # ALTA — regra original
    if (
        preco > mme21
        and mme21 > mme200
    ):
        return "ALTA"

    # BAIXA — regra original
    elif (
        preco < mme21
        and mme21 < mme200
    ):
        return "BAIXA"

    # CONSOLIDAÇÃO — demais situações
    else:
        return "CONSOLIDAÇÃO"


# ============================================================
# PONTO E FIGURA
# ============================================================

def construir_pnf(dados, box, reversao=3):

    if box <= 0:
        return []

    colunas = []

    direcao = None

    coluna = None

    topo = None
    fundo = None

    for _, linha in dados.iterrows():

        maxima = linha["Maxima"]
        minima = linha["Minima"]

        if direcao is None:

            direcao = "X"

            fundo = (
                np.floor(minima / box)
                * box
            )

            topo = (
                np.floor(maxima / box)
                * box
            )

            if topo < fundo:
                topo = fundo

            coluna = {
                "tipo": "X",
                "boxes": [],
                "topo": topo,
                "fundo": fundo
            }

            quantidade = int(
                round(
                    (topo - fundo) / box
                )
            ) + 1

            coluna["boxes"] = [
                fundo + i * box
                for i in range(quantidade)
            ]

            continue

        # ====================================================
        # COLUNA DE ALTA - X
        # ====================================================

        if direcao == "X":

            novo_topo = (
                np.floor(maxima / box)
                * box
            )

            if novo_topo > topo:

                inicio = topo + box

                while inicio <= novo_topo + 1e-9:
                    coluna["boxes"].append(inicio)
                    inicio += box

                topo = novo_topo
                coluna["topo"] = topo

            # Reversão para O
            elif minima <= topo - reversao * box:

                colunas.append(coluna)

                novo_fundo = (
                    np.ceil(
                        (minima + (reversao - 1) * box)
                        / box
                    ) * box
                )

                novo_topo = topo - box

                if novo_fundo > novo_topo:
                    novo_fundo = novo_topo

                coluna = {
                    "tipo": "O",
                    "boxes": [],
                    "topo": novo_topo,
                    "fundo": novo_fundo
                }

                valor = novo_topo

                while valor >= novo_fundo - 1e-9:
                    coluna["boxes"].append(valor)
                    valor -= box

                topo = novo_topo
                fundo = novo_fundo

                direcao = "O"

        # ====================================================
        # COLUNA DE BAIXA - O
        # ====================================================

        elif direcao == "O":

            novo_fundo = (
                np.ceil(minima / box)
                * box
            )

            if novo_fundo < fundo:

                inicio = fundo - box

                while inicio >= novo_fundo - 1e-9:
                    coluna["boxes"].append(inicio)
                    inicio -= box

                fundo = novo_fundo
                coluna["fundo"] = fundo

            # Reversão para X
            elif maxima >= fundo + reversao * box:

                colunas.append(coluna)

                novo_topo = (
                    np.floor(
                        (maxima - (reversao - 1) * box)
                        / box
                    ) * box
                )

                novo_fundo = fundo + box

                if novo_topo < novo_fundo:
                    novo_topo = novo_fundo

                coluna = {
                    "tipo": "X",
                    "boxes": [],
                    "topo": novo_topo,
                    "fundo": novo_fundo
                }

                valor = novo_fundo

                while valor <= novo_topo + 1e-9:
                    coluna["boxes"].append(valor)
                    valor += box

                topo = novo_topo
                fundo = novo_fundo

                direcao = "X"

    if coluna is not None:
        colunas.append(coluna)

    return colunas


# ============================================================
# HISTÓRICO P&F - ÚLTIMOS 6 MESES
# ============================================================


def obter_historico_pnf(dados):

    if dados.empty:
        return dados

    dados = dados.copy()

    # Garantir que a coluna Data seja do tipo datetime
    dados["Data"] = pd.to_datetime(
        dados["Data"],
        errors="coerce"
    )

    dados = dados.dropna(subset=["Data"])

    if dados.empty:
        return dados

    data_final = dados["Data"].iloc[-1]

    data_inicial = (
        data_final -
        pd.DateOffset(months=MESES_PNF)
    )

    historico = dados[
        dados["Data"] >= data_inicial
    ].copy()

    return historico


# ============================================================
# SUPORTE / RESISTÊNCIA PELO P&F
# ============================================================

def encontrar_niveis_pnf(dados):

    historico = obter_historico_pnf(dados)

    if len(historico) < 20:
        return {
            "box": np.nan,
            "colunas": [],
            "resistencia": np.nan,
            "suporte": np.nan,
            "ultima_coluna": None
        }

    linha_atual = dados.iloc[-1]

    preco = linha_atual["Fechamento"]
    atr = linha_atual["ATR14"]

    if pd.isna(atr) or atr <= 0:
        return {
            "box": np.nan,
            "colunas": [],
            "resistencia": np.nan,
            "suporte": np.nan,
            "ultima_coluna": None
        }

    box = max(
        atr * MULTIPLICADOR_BOX,
        0.01
    )

    colunas = construir_pnf(
        historico,
        box,
        REVERSAO_PF
    )

    if len(colunas) == 0:
        return {
            "box": box,
            "colunas": [],
            "resistencia": np.nan,
            "suporte": np.nan,
            "ultima_coluna": None
        }

    # A coluna atual não é usada como resistência/suporte
    # histórico.
    colunas_historicas = colunas[:-1]

    resistencias = []

    suportes = []

    for coluna in colunas_historicas:

        if coluna["tipo"] == "X":

            if coluna["topo"] > preco:
                resistencias.append(
                    coluna["topo"]
                )

        elif coluna["tipo"] == "O":

            if coluna["fundo"] < preco:
                suportes.append(
                    coluna["fundo"]
                )

    resistencia = (
        min(resistencias)
        if resistencias
        else np.nan
    )

    suporte = (
        max(suportes)
        if suportes
        else np.nan
    )

    return {
        "box": box,
        "colunas": colunas,
        "resistencia": resistencia,
        "suporte": suporte,
        "ultima_coluna": colunas[-1]
    }


# ============================================================
# ALVO TÉCNICO
# ============================================================

def calcular_alvo_tecnico(
    tendencia,
    preco,
    atr,
    niveis
):

    resistencia = niveis["resistencia"]
    suporte = niveis["suporte"]

    if tendencia == "ALTA":

        if pd.notna(resistencia):

            distancia = resistencia - preco

            if distancia > 0:

                return {
                    "alvo": resistencia,
                    "distancia": distancia,
                    "distancia_atr": distancia / atr,
                    "tipo": "RESISTÊNCIA P&F"
                }

    elif tendencia == "BAIXA":

        if pd.notna(suporte):

            distancia = preco - suporte

            if distancia > 0:

                return {
                    "alvo": suporte,
                    "distancia": distancia,
                    "distancia_atr": distancia / atr,
                    "tipo": "SUPORTE P&F"
                }

    return {
        "alvo": np.nan,
        "distancia": np.nan,
        "distancia_atr": np.nan,
        "tipo": "SEM ALVO"
    }


# ============================================================
# PROJEÇÕES ATR
# ============================================================

def calcular_projecoes_atr(
    tendencia,
    preco,
    atr
):

    if pd.isna(atr) or atr <= 0:
        return {
            "ATR1": np.nan,
            "ATR2": np.nan,
            "ATR3": np.nan
        }

    if tendencia == "ALTA":

        return {
            "ATR1": preco + atr,
            "ATR2": preco + 2 * atr,
            "ATR3": preco + 3 * atr
        }

    elif tendencia == "BAIXA":

        return {
            "ATR1": preco - atr,
            "ATR2": preco - 2 * atr,
            "ATR3": preco - 3 * atr
        }

    return {
        "ATR1": np.nan,
        "ATR2": np.nan,
        "ATR3": np.nan
    }


# ============================================================
# ANÁLISE COMPLETA DE UMA DATA
# ============================================================



def estimar_pregoes_historicos(dados, tendencia, alvo=None, n_movimentos=3):
    """
    Reproduz os cálculos do analisador original:
    amplitude média em reais, amplitude percentual média,
    duração média e projeções históricas.
    """
   
    if tendencia not in ("ALTA", "BAIXA"):
        return None

    # Analisar somente os últimos seis meses de pregões.
    dados = obter_historico_pnf(dados)
    dados = dados.reset_index(drop=True).copy()

    if dados.empty:
        return None


    if tendencia == "ALTA":
        coluna_condicao = dados["Fechamento"] > dados["MME21"]
    else:
        coluna_condicao = dados["Fechamento"] < dados["MME21"]

    ondas = []
    onda_atual = []

    for i, ativo_na_onda in enumerate(coluna_condicao.tolist()):
        if ativo_na_onda:
            onda_atual.append(i)
        else:
            if len(onda_atual) >= 3:
                ondas.append(onda_atual)
            onda_atual = []

    if len(onda_atual) >= 3:
        ondas.append(onda_atual)

    # Mantém a regra do código original:
    # a última onda identificada é excluída da análise.
    if len(ondas) > n_movimentos:
        ondas_concluidas = ondas[-n_movimentos-1:-1]
    else:
        ondas_concluidas = ondas[:-1]

    if not ondas_concluidas:
        return None

    metricas = []

    for numero, indices in enumerate(
    ondas_concluidas,
    start=1
):
        onda = dados.iloc[indices].copy()

        preco_inicial = float(onda["Fechamento"].iloc[0])

        if tendencia == "ALTA":
            preco_extremo = float(onda["Maxima"].max())
            posicao_extremo = int(onda["Maxima"].to_numpy().argmax())
            amplitude = preco_extremo - preco_inicial
        else:
            preco_extremo = float(onda["Minima"].min())
            posicao_extremo = int(onda["Minima"].to_numpy().argmin())
            amplitude = preco_inicial - preco_extremo

        duracao = posicao_extremo + 1


        if preco_inicial <= 0 or amplitude <= 0 or duracao <= 0:
            continue

        amplitude_pct = amplitude / preco_inicial * 100

        metricas.append({
            "amplitude": amplitude,
            "amplitude_pct": amplitude_pct,
            "duracao": duracao,
            "movimento": f"{tendencia.title()} #{numero}",
            "inicio": pd.to_datetime(
                onda["Data"].iloc[0]
            ).strftime("%Y-%m-%d"),
            "data_extremo": pd.to_datetime(
                onda["Data"].iloc[posicao_extremo]
            ).strftime("%Y-%m-%d"),
            "preco_inicial": preco_inicial,
            "preco_extremo": preco_extremo,
        })

    if not metricas:
        return None

    media_amplitude = float(np.mean(
        [m["amplitude"] for m in metricas]
    ))
    media_amplitude_pct = float(np.mean(
        [m["amplitude_pct"] for m in metricas]
    ))
    media_duracao = float(np.mean(
        [m["duracao"] for m in metricas]
    ))

    preco_atual = float(dados["Fechamento"].iloc[-1])

    if tendencia == "ALTA":
        alvo_rs = preco_atual + media_amplitude
        alvo_pct = preco_atual * (1 + media_amplitude_pct / 100)
    else:
        alvo_rs = preco_atual - media_amplitude
        alvo_pct = preco_atual * (1 - media_amplitude_pct / 100)

    resultado = {
        "media_amplitude_historica": media_amplitude,
        "media_amplitude_pct_historica": media_amplitude_pct,
        "tempo_medio_movimento": media_duracao,
        "alvo_amplitude_historica": float(alvo_rs),
        "alvo_percentual_historico": float(alvo_pct),
        "movimentos_historicos": metricas,
    }

    # Estimativa proporcional até o alvo técnico, caso exista.
    if alvo is not None and not pd.isna(alvo) and media_amplitude > 0:
        distancia = abs(float(alvo) - preco_atual)
        resultado["pregoes_estimados_historico"] = max(
            1, int(math.ceil(distancia / media_amplitude * media_duracao))
        )
    else:
        resultado["pregoes_estimados_historico"] = None

    return resultado




def analisar(dados):

    dados = calcular_indicadores(dados)

    if dados.empty:
        return None

    linha = dados.iloc[-1]

    preco = linha["Fechamento"]
    atr = linha["ATR14"]

    if pd.isna(atr):
        return None

    tendencia = classificar_tendencia(linha)

    velocidade_classificacao = (
        classificar_velocidade(dados)
    )

    aceleracao = (
        analisar_aceleracao(dados)
    )

    niveis = encontrar_niveis_pnf(dados)

    alvo = calcular_alvo_tecnico(
        tendencia,
        preco,
        atr,
        niveis
    )

    projecoes = calcular_projecoes_atr(
        tendencia,
        preco,
        atr
    )

    volume_medio = linha["VolumeMedia20"]

    if (
        pd.notna(linha["Volume"])
        and linha["Volume"] > 0
        and pd.notna(volume_medio)
        and volume_medio > 0
    ):
        volume_relativo = (
            linha["Volume"] / volume_medio
        )
    else:
        volume_relativo = np.nan

    # Calcular o histórico ANTES do return.
    historico = estimar_pregoes_historicos(
        dados,
        tendencia,
        alvo.get("alvo") if isinstance(alvo, dict) else None
    )

    return {
        "data": linha["Data"],
        "preco": preco,
        "mme21": linha["MME21"],
        "mme200": linha["MME200"],
        "atr": atr,
        "volume": linha["Volume"],
        "volume_medio": volume_medio,
        "volume_relativo": volume_relativo,
        "velocidade": linha["Velocidade"],
        "velocidade_classificacao": velocidade_classificacao,
        "tendencia": tendencia,
        "aceleracao": aceleracao,
        "niveis": niveis,
        "alvo": alvo,
        "projecao_historica": historico,
        "pregoes_estimados_historico": (
            historico.get("pregoes_estimados_historico")
            if historico else None
        ),
        "projecoes": projecoes
    }




# Backtest original: alvo P&F, stop de 1 ATR e resolução candle a candle.
def executar_backtest(
    dados,
    data_inicio,
    data_fim,
    horizonte
):

    dados = dados.copy()

    resultados = []

    indices_periodo = dados.index[
        (dados["Data"] >= data_inicio)
        &
        (dados["Data"] <= data_fim)
    ].tolist()

    if not indices_periodo:
        return pd.DataFrame()

    for indice in indices_periodo:

        # ====================================================
        # HISTÓRICO DISPONÍVEL NA DATA DO SINAL
        # ====================================================

        if indice < MINIMO_DADOS:
            continue

        historico = dados.iloc[
            :indice + 1
        ].copy()

        resultado = analisar(
            historico
        )

        if resultado is None:
            continue

        tendencia = resultado["tendencia"]

        alvo = resultado["alvo"]["alvo"]

        atr = resultado["atr"]

        preco_entrada = resultado["preco"]

        # ====================================================
        # SOMENTE ALTA OU BAIXA
        # ====================================================

        if tendencia not in [
            "ALTA",
            "BAIXA"
        ]:
            continue

        if pd.isna(alvo):
            continue

        if pd.isna(atr) or atr <= 0:
            continue

        # ====================================================
        # STOP
        # ====================================================

        if tendencia == "ALTA":

            stop = (
                preco_entrada
                - MULTIPLICADOR_STOP_ATR * atr
            )

        else:

            stop = (
                preco_entrada
                + MULTIPLICADOR_STOP_ATR * atr
            )

        # ====================================================
        # RISCO
        # ====================================================

        risco = abs(
            preco_entrada - stop
        )

        if risco <= 0:
            continue

        distancia_alvo = abs(
            alvo - preco_entrada
        )

        # ====================================================
        # RELAÇÃO RISCO/RETORNO
        # ====================================================

        risco_retorno = (
            distancia_alvo / risco
        )

        # ====================================================
        # DADOS FUTUROS
        # ====================================================

        futuro = dados.iloc[
            indice + 1:
        ].head(horizonte)

        if futuro.empty:
            continue

        resultado_trade = "NAO ATINGIU"

        pregoes_resultado = np.nan

        data_resultado = pd.NaT

        resultado_r = np.nan

        # ====================================================
        # VERIFICAR PREGÃO POR PREGÃO
        # ====================================================

        for numero_pregao, (
            indice_futuro,
            linha_futura
        ) in enumerate(
            futuro.iterrows(),
            start=1
        ):

            maxima = linha_futura["Maxima"]

            minima = linha_futura["Minima"]

            # =================================================
            # ALTA
            # =================================================

            if tendencia == "ALTA":

                atingiu_alvo = (
                    maxima >= alvo
                )

                atingiu_stop = (
                    minima <= stop
                )

                # ---------------------------------------------
                # Ambos no mesmo candle
                # ---------------------------------------------

                if (
                    atingiu_alvo
                    and
                    atingiu_stop
                ):

                    resultado_trade = "AMBIGUO"

                    pregoes_resultado = (
                        numero_pregao
                    )

                    data_resultado = (
                        linha_futura["Data"]
                    )

                    break

                # ---------------------------------------------
                # Alvo
                # ---------------------------------------------

                if atingiu_alvo:

                    resultado_trade = "ALVO"

                    pregoes_resultado = (
                        numero_pregao
                    )

                    data_resultado = (
                        linha_futura["Data"]
                    )

                    resultado_r = (
                        distancia_alvo /
                        risco
                    )

                    break

                # ---------------------------------------------
                # Stop
                # ---------------------------------------------

                if atingiu_stop:

                    resultado_trade = "STOP"

                    pregoes_resultado = (
                        numero_pregao
                    )

                    data_resultado = (
                        linha_futura["Data"]
                    )

                    resultado_r = -1.0

                    break

            # =================================================
            # BAIXA
            # =================================================

            elif tendencia == "BAIXA":

                atingiu_alvo = (
                    minima <= alvo
                )

                atingiu_stop = (
                    maxima >= stop
                )

                # ---------------------------------------------
                # Ambos no mesmo candle
                # ---------------------------------------------

                if (
                    atingiu_alvo
                    and
                    atingiu_stop
                ):

                    resultado_trade = "AMBIGUO"

                    pregoes_resultado = (
                        numero_pregao
                    )

                    data_resultado = (
                        linha_futura["Data"]
                    )

                    break

                # ---------------------------------------------
                # Alvo
                # ---------------------------------------------

                if atingiu_alvo:

                    resultado_trade = "ALVO"

                    pregoes_resultado = (
                        numero_pregao
                    )

                    data_resultado = (
                        linha_futura["Data"]
                    )

                    resultado_r = (
                        distancia_alvo /
                        risco
                    )

                    break

                # ---------------------------------------------
                # Stop
                # ---------------------------------------------

                if atingiu_stop:

                    resultado_trade = "STOP"

                    pregoes_resultado = (
                        numero_pregao
                    )

                    data_resultado = (
                        linha_futura["Data"]
                    )

                    resultado_r = -1.0

                    break

        # ====================================================
        # SALVAR RESULTADO
        # ====================================================

        resultados.append({

            "Data_Entrada":
                resultado["data"],

            "Preco_Entrada":
                preco_entrada,

            "Direcao":
                tendencia,

            "ATR":
                atr,

            "Stop":
                stop,

            "Alvo":
                alvo,

            "Distancia":
                resultado["alvo"]["distancia"],

            "Distancia_ATR":
                resultado["alvo"]["distancia_atr"],

            "Risco_Retorno":
                risco_retorno,

            "Resultado":
                resultado_trade,

            "Resultado_R":
                resultado_r,

            "Pregoes_Resultado":
                pregoes_resultado,

            "Data_Resultado":
                data_resultado,

            "Horizonte":
                horizonte,

            "Aceleracao":
                resultado["aceleracao"],

            "Velocidade":
                resultado["velocidade"],

            "Volume_Relativo":
                resultado["volume_relativo"]

        })

    return pd.DataFrame(
        resultados
    )

