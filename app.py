from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from motor import executar_backtest
from datetime import date, timedelta

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "dados"
JSON_FILE = DATA_DIR / "analises.json"

st.set_page_config(page_title="Analisador B3 — Painel", page_icon="📈", layout="wide")
st.title("📈 Analisador técnico da B3")
st.caption("Execução diária após o fechamento • MME21/MME200 • ATR14 • velocidade • aceleração • Ponto e Figura")

@st.cache_data(ttl=300)
def carregar_resultados():
    if not JSON_FILE.exists():
        return None
    return json.loads(JSON_FILE.read_text(encoding="utf-8"))

@st.cache_data(ttl=300)
def carregar_historico(ativo: str):
    path = DATA_DIR / f"{ativo}.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if "Data" in df:
        df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
    return df.dropna(subset=["Data", "Fechamento"]).sort_values("Data")

def moeda(v):
    if v is None or pd.isna(v): return "N/D"
    return "R$ " + f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def numero(v, casas=2):
    if v is None or pd.isna(v): return "N/D"
    return f"{float(v):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def percentual(v):
    if v is None or pd.isna(v): return "N/D"
    return f"{float(v)*100:.2f}%".replace(".", ",")

payload = carregar_resultados()
if not payload:
    st.warning("Ainda não existem resultados publicados. Execute o workflow ‘Atualizar analisador B3’ no GitHub ou aguarde a execução diária após configurar o repositório.")
    st.stop()

resultados = payload.get("resultados", [])
if not resultados:
    st.error("O último processamento não gerou análises. Consulte a seção de erros no final do painel.")
    st.stop()

col1, col2 = st.columns(2)

col1.metric(
    "Ativos analisados",
    len(resultados)
)

col2.metric(
    "Fonte",
    "Yahoo Finance · diário"
)

data_geracao = payload.get("gerado_em_brasilia")

if data_geracao:
    try:
        data_hora = datetime.fromisoformat(str(data_geracao))
        data_formatada = data_hora.strftime("%d/%m/%Y às %H:%M:%S")

        st.info(
            f"🕒 **Última atualização:** {data_formatada} "
            "(horário de Brasília)"
        )
    except (ValueError, TypeError):
        st.warning("Não foi possível interpretar a data da atualização.")
else:
    st.warning("Data e hora da última atualização não disponíveis.")

st.caption(
    "O horário indica quando o arquivo de análises foi gerado."
)
df = pd.DataFrame(resultados)
ativos = sorted(df["ativo"].dropna().unique().tolist())
selecionado = st.selectbox("Escolha um ativo para detalhar", options=ativos)
r = df[df["ativo"] == selecionado].iloc[0].to_dict()

# Tabela de comparação de todos os ativos
with st.expander("Ver comparação de todos os ativos", expanded=True):
    cols = ["ativo", "data", "preco", "tendencia", "aceleracao", "velocidade_classificacao", "volume_relativo", "tipo_alvo", "alvo_tecnico", "pregoes_estimados"]
    tabela = df[[c for c in cols if c in df.columns]].copy()
    tabela = tabela.rename(columns={"ativo":"Ativo", "data":"Data do candle", "preco":"Fechamento", "tendencia":"Tendência", "aceleracao":"Aceleração", "velocidade_classificacao":"Velocidade", "volume_relativo":"Volume relativo (x)", "tipo_alvo":"Tipo de alvo", "alvo_tecnico":"Alvo técnico", "pregoes_estimados":"Pregões estimados"})
    st.dataframe(tabela, use_container_width=True, hide_index=True)

st.header(f"{selecionado} — análise detalhada")
metricas = st.columns(4)
metricas[0].metric("Fechamento", moeda(r.get("preco")))
metricas[1].metric("MME 21", moeda(r.get("mme21")))
metricas[2].metric("MME 200", moeda(r.get("mme200")))
metricas[3].metric("ATR 14", moeda(r.get("atr14")))

m2 = st.columns(4)
m2[0].metric("Tendência", r.get("tendencia") or "N/D")
m2[1].metric("Aceleração", r.get("aceleracao") or "N/D")
m2[2].metric("Velocidade", r.get("velocidade_classificacao") or "N/D", percentual(r.get("velocidade")))
m2[3].metric("Volume relativo", (numero(r.get("volume_relativo")) + "x") if r.get("volume_relativo") is not None else "N/D")

hist = carregar_historico(selecionado)
if not hist.empty:
    # Recalcula médias apenas para visualização, com os mesmos spans do motor.
    hist["MME21"] = hist["Fechamento"].ewm(span=21, adjust=False).mean()
    hist["MME200"] = hist["Fechamento"].ewm(span=200, adjust=False).mean()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hist["Data"], y=hist["Fechamento"], name="Fechamento", line=dict(width=2)))
    fig.add_trace(go.Scatter(x=hist["Data"], y=hist["MME21"], name="MME 21", line=dict(width=1.5)))
    fig.add_trace(go.Scatter(x=hist["Data"], y=hist["MME200"], name="MME 200", line=dict(width=1.5)))
    fig.update_layout(height=450, margin=dict(l=10,r=10,t=30,b=10), xaxis_title="Data", yaxis_title="Preço (R$)", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0))
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Histórico CSV ainda não está disponível para este ativo.")

st.subheader("Ponto e Figura — janela de 6 meses")
pnf = st.columns(4)
pnf[0].metric("Tamanho da caixa", moeda(r.get("box_pnf")))
pnf[1].metric("Colunas P&F", str(r.get("colunas_pnf", "N/D")))
pnf[2].metric("Suporte P&F", moeda(r.get("suporte_pnf")))
pnf[3].metric("Resistência P&F", moeda(r.get("resistencia_pnf")))
st.caption(f"Última coluna: {r.get('ultima_coluna_pnf') or 'N/D'} · Topo: {moeda(r.get('topo_pnf'))} · Fundo: {moeda(r.get('fundo_pnf'))}")

st.subheader("Alvo técnico e projeções por ATR")
a, b, c, d = st.columns(4)
a.metric("Alvo técnico", moeda(r.get("alvo_tecnico")))
b.metric("Tipo de alvo", r.get("tipo_alvo") or "SEM ALVO")
c.metric("Distância / ATR", (numero(r.get("distancia_alvo_atr")) + " ATR") if r.get("distancia_alvo_atr") is not None else "N/D")
d.metric("Pregões estimados", numero(r.get("pregoes_estimados")))
proj = st.columns(3)
proj[0].metric("Projeção 1 ATR", moeda(r.get("projecao_atr1")))
proj[1].metric("Projeção 2 ATR", moeda(r.get("projecao_atr2")))
proj[2].metric("Projeção 3 ATR", moeda(r.get("projecao_atr3")))
st.caption("Pregões estimados = distância até o alvo dividida pelo ATR14 atual. É uma estimativa mecânica, não uma previsão nem garantia de prazo. As projeções ATR são cenários de distância, não recomendações de compra ou venda.")

st.divider()
st.header("Backtest histórico do motor original")
st.caption("Usa as regras do código fornecido: mínimo de 220 pregões antes do sinal, alvo técnico P&F, stop de 1 ATR, horizonte escolhido em pregões e classificação AMBÍGUO quando alvo e stop aparecem no mesmo candle.")
if not hist.empty and len(hist) > 220:
    data_max = hist["Data"].max().date()
    data_min = hist["Data"].min().date()
    default_inicio = max(data_min, data_max - timedelta(days=365))
    with st.form("form_backtest"):
        intervalo = st.date_input("Período para procurar sinais", value=(default_inicio, data_max), min_value=data_min, max_value=data_max)
        horizonte = st.selectbox("Horizonte máximo do trade (pregões)", options=[5, 10, 15, 20, 30, 40], index=3)
        executar = st.form_submit_button("Executar backtest")
    if executar:
        if not isinstance(intervalo, (tuple, list)) or len(intervalo) != 2:
            st.error("Selecione uma data inicial e uma data final.")
        else:
            inicio = pd.Timestamp(intervalo[0])
            fim = pd.Timestamp(intervalo[1])
            with st.spinner("Executando o backtest candle a candle. Em históricos longos isso pode levar algum tempo..."):
                bt = executar_backtest(hist.copy(), inicio, fim, int(horizonte))
            if bt.empty:
                st.warning("Nenhum sinal válido foi encontrado nesse período. São necessários 220 pregões anteriores ao sinal e um alvo técnico válido.")
            else:
                total = len(bt)
                alvos = int((bt["Resultado"] == "ALVO").sum())
                stops = int((bt["Resultado"] == "STOP").sum())
                ambiguos = int((bt["Resultado"] == "AMBIGUO").sum())
                nao_atingiu = int((bt["Resultado"] == "NAO ATINGIU").sum())
                definidos = alvos + stops
                taxa = alvos / definidos if definidos else None
                b1, b2, b3, b4, b5 = st.columns(5)
                b1.metric("Sinais", total)
                b2.metric("Alvos", alvos)
                b3.metric("Stops", stops)
                b4.metric("Ambíguos", ambiguos)
                b5.metric("Não atingiu", nao_atingiu)
                st.metric("Taxa de alvo entre trades definidos (ALVO/ALVO+STOP)", percentual(taxa))
                st.caption("Casos AMBÍGUO e NAO ATINGIU ficam fora do denominador da taxa. Resultados históricos não garantem desempenho futuro.")
                st.dataframe(bt, use_container_width=True, hide_index=True)
                st.download_button("Baixar resultados do backtest (CSV)", data=bt.to_csv(index=False).encode("utf-8-sig"), file_name=f"backtest_{selecionado}.csv", mime="text/csv")
else:
    st.info("O backtest ficará disponível quando houver pelo menos 221 candles históricos válidos para o ativo selecionado.")

if payload.get("erros"):
    with st.expander(f"Ativos com falha de coleta/análise ({len(payload['erros'])})"):
        st.dataframe(pd.DataFrame(payload["erros"]), use_container_width=True, hide_index=True)

st.divider()
st.caption("Uso educacional. Não é recomendação de investimento. Dados diários de fonte pública podem conter atrasos, ajustes ou indisponibilidades.")
