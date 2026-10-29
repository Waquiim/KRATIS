"""Componentes compartilhados: estilo, cabeçalho, filtros, cartões, gráficos e tabelas."""
from __future__ import annotations

import base64
import html
import threading
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .. import dados, estado
from ..atualizar import em_andamento, executar, precisa_atualizar
from ..config import ANOS, COR_ANO, CORES, LOGO, MESES, NAVEGADOR, ORGAOS, SEVERIDADES
from ..fontes import tce_sicom
from ..formatos import brl, brl_compacto, mes_ano, numero, pct

CSS = f"""
<style>
:root {{ --pv-vermelho: {CORES['vermelho']}; --pv-azul: {CORES['azul']}; --pv-amarelo: {CORES['amarelo']};
        --pv-grafite: {CORES['grafite']}; --pv-borda: {CORES['borda']}; --pv-fundo: {CORES['fundo']}; }}
.block-container {{ padding-top: 3.4rem; padding-bottom: 3rem; max-width: 1500px; }}
div[class*="st-key-kpis-"] > div[data-testid="stElementContainer"] {{ flex: 1 1 150px; min-width: 150px; }}
.pv-cabecalho {{ display: flex; flex-wrap: wrap; align-items: center; gap: 18px 24px; background: #fff; border: 1px solid var(--pv-borda);
        border-radius: 12px; padding: 14px 22px 16px; margin-bottom: 18px; position: relative; overflow: hidden; }}
.pv-cabecalho::after {{ content: ""; position: absolute; left: 0; right: 0; bottom: 0; height: 5px;
        background: linear-gradient(90deg, var(--pv-vermelho) 0 70%, var(--pv-amarelo) 70% 85%, var(--pv-azul) 85% 100%); }}
.pv-cabecalho img {{ height: 64px; width: auto; flex: 0 0 auto; }}
.pv-titulo {{ flex: 1 1 320px; min-width: 260px; border-left: 2px solid var(--pv-borda); padding-left: 22px; }}
.pv-titulo .pv-sistema {{ font-size: .78rem; letter-spacing: .08em; text-transform: uppercase; color: var(--pv-vermelho); font-weight: 700; }}
.pv-titulo h1 {{ font-size: 1.65rem; line-height: 1.2; margin: 2px 0 2px; padding: 0; color: var(--pv-grafite); font-weight: 700; }}
.pv-titulo .pv-sub {{ color: #5b5b5b; font-size: .92rem; }}
.pv-carimbo {{ text-align: right; font-size: .82rem; color: #4a4a4a; line-height: 1.45; flex: 0 0 auto; }}
.pv-carimbo b {{ color: var(--pv-grafite); }}
.pv-carimbo span {{ color: #7a7a7a; }}
@media (max-width: 900px) {{ .pv-cabecalho {{ flex-wrap: wrap; gap: 12px; }} .pv-titulo {{ border-left: 0; padding-left: 0; }}
        .pv-carimbo {{ text-align: left; }} .pv-cabecalho img {{ height: 48px; }} }}
div[data-testid="stMetric"] {{ background: #fff; }}
div[data-testid="stMetricLabel"] p {{ font-size: .86rem; color: #4d4d4d; }}
div[data-testid="stMetricValue"] {{ font-size: 1.55rem; color: var(--pv-grafite); }}
.pv-sev {{ display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: .8rem; font-weight: 600; border: 1px solid; white-space: nowrap; }}
.pv-cartao-sev {{ border-radius: 10px; padding: 12px 14px; border: 1px solid var(--pv-borda); background: #fff; }}
.pv-cartao-sev .n {{ font-size: 1.9rem; font-weight: 700; line-height: 1.1; }}
.pv-cartao-sev .r {{ font-size: .85rem; }}
.pv-nota {{ font-size: .84rem; color: #555; }}
.pv-secao {{ font-size: 1.1rem; font-weight: 700; color: var(--pv-grafite); margin: 1.2rem 0 .3rem; padding-bottom: 4px;
        border-bottom: 2px solid var(--pv-borda); }}
section[data-testid="stSidebar"] .pv-fonte {{ font-size: .8rem; line-height: 1.35; margin-bottom: 6px; }}
.pv-rodape {{ margin-top: 2.5rem; padding-top: 10px; border-top: 1px solid var(--pv-borda); font-size: .78rem; color: #777; }}
@media (max-width: 640px) {{
  .block-container {{ padding-left: 1rem; padding-right: 1rem; padding-top: 2.8rem; }}
  div[class*="st-key-kpis-"] > div[data-testid="stElementContainer"] {{ flex-basis: 140px; min-width: 140px; }}
  [data-testid="stMetricLabel"] p {{ white-space: normal !important; }}
  .pv-cabecalho {{ padding: 12px 14px 14px; }}
  .pv-titulo {{ border-left: none; padding-left: 0; min-width: 0; }}
}}
</style>
"""


_trava_thread = threading.Lock()
_thread_atualizacao: threading.Thread | None = None


def estilos() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def _logo_base64() -> str:
    return base64.b64encode(LOGO.read_bytes()).decode()


# ----------------------------------------------------------------------------- estado dos filtros

def anos_disponiveis() -> list[int]:
    disponiveis = [a for a in sorted(ANOS, reverse=True) if tce_sicom.caminho_zip(a, "receita").exists()]
    return disponiveis or sorted(ANOS, reverse=True)


def ano_selecionado() -> int:
    if "ano" not in st.session_state:
        st.session_state.ano = anos_disponiveis()[0]
    return int(st.session_state.ano)


def mes_selecionado() -> int:
    ultimo = dados.ultimo_mes(ano_selecionado()) or 12
    mes = st.session_state.get("mes_ate", ultimo)
    return min(int(mes), ultimo)


def orgaos_selecionados() -> list[str]:
    return list(st.session_state.get("orgaos", []))


def _ao_trocar_ano() -> None:
    st.session_state.mes_ate = dados.ultimo_mes(int(st.session_state.ano)) or 12


def filtros(mostrar_orgaos: bool = True) -> None:
    with st.sidebar:
        st.markdown("**Filtros**")
        st.selectbox("Exercício", anos_disponiveis(), key="ano", on_change=_ao_trocar_ano)
        ultimo = dados.ultimo_mes(ano_selecionado()) or 12
        if "mes_ate" not in st.session_state or st.session_state.mes_ate > ultimo:
            st.session_state.mes_ate = ultimo
        if ultimo > 1:
            st.select_slider("Até o mês", options=list(range(1, ultimo + 1)), key="mes_ate",
                             format_func=lambda m: MESES[m - 1],
                             help="Último mês considerado nos acumulados. O padrão é o último mês enviado ao SICOM.")
        if mostrar_orgaos:
            st.multiselect("Órgãos", options=list(ORGAOS), key="orgaos", format_func=lambda c: ORGAOS[c],
                           placeholder="Todos (consolidado)")
        status_fontes()


def status_fontes() -> None:
    st.markdown("**Situação dos dados**")
    est = estado.ler()
    ano = ano_selecionado()
    carga = tce_sicom.data_publicacao_tce(ano)
    ultimo = dados.ultimo_mes(ano)
    linhas = [f"<div class='pv-fonte'><b>SICOM (TCE-MG)</b><br>dados até {mes_ano(ano, ultimo) if ultimo else '—'}"
              f"{f' · carga do TCE em {carga:%d/%m/%Y}' if carga else ''}</div>"]
    item = est.get("tce_sicom", {})
    quando = item.get("ultima_tentativa")
    linhas.append(f"<div class='pv-fonte'>Última verificação de pacotes novos: "
                  f"{datetime.fromisoformat(quando):%d/%m/%Y %H:%M}{'' if item.get('ok', True) else ' ⚠️'}</div>"
                  if quando else "<div class='pv-fonte'>Nenhuma importação registrada</div>")
    st.markdown("".join(linhas), unsafe_allow_html=True)
    if em_andamento() or (_thread_atualizacao is not None and _thread_atualizacao.is_alive()):
        st.caption("🔄 Atualização em andamento…")


# ----------------------------------------------------------------------------- atualização automática

def atualizacao_automatica() -> None:
    """Dispara a atualização diária em segundo plano quando os dados automáticos têm mais de 20 horas."""
    global _thread_atualizacao
    if NAVEGADOR:
        # No navegador não há pasta Downloads nem threads: os pacotes chegam pela aba Atualização de dados.
        return
    with _trava_thread:
        if _thread_atualizacao is not None and _thread_atualizacao.is_alive():
            return
        if em_andamento() or not precisa_atualizar(20):
            return
        _thread_atualizacao = threading.Thread(target=executar, kwargs={"log": lambda _: None}, daemon=True,
                                               name="atualizacao-diaria")
        _thread_atualizacao.start()
    st.toast("Atualização diária dos dados iniciada em segundo plano.", icon="🔄")


# ----------------------------------------------------------------------------- cabeçalho e rodapé

def cabecalho(titulo: str, subtitulo: str = "") -> None:
    ano = ano_selecionado()
    ultimo = dados.ultimo_mes(ano)
    carga = tce_sicom.data_publicacao_tce(ano)
    st.markdown(
        f"""<div class="pv-cabecalho">
<img src="data:image/jpeg;base64,{_logo_base64()}" alt="Prefeitura de Viçosa – Gestão que transforma"/>
<div class="pv-titulo"><div class="pv-sistema">Painel Contábil e Fiscal</div><h1>{html.escape(titulo)}</h1>
<div class="pv-sub">{html.escape(subtitulo)}</div></div>
<div class="pv-carimbo">Exercício <b>{ano}</b><br>SICOM até <b>{mes_ano(ano, ultimo) if ultimo else '—'}</b>
<br><span>{f'carga TCE-MG {carga:%d/%m/%Y}' if carga else 'sem pacote do TCE'}</span></div></div>""",
        unsafe_allow_html=True)


def rodape() -> None:
    st.markdown(
        "<div class='pv-rodape'>Fonte única: portal de dados abertos do TCE-MG (dadosabertos.tce.mg.gov.br), dados "
        "informados pelo Município ao SICOM. As críticas aplicam as metodologias oficiais a esses dados e são indicativas, "
        "não substituindo a análise técnica.</div>",
        unsafe_allow_html=True)


def secao(titulo: str, nota: str = "") -> None:
    st.markdown(f"<div class='pv-secao'>{html.escape(titulo)}</div>", unsafe_allow_html=True)
    if nota:
        st.markdown(f"<div class='pv-nota'>{nota}</div>", unsafe_allow_html=True)


def aviso_sem_dados(categoria: str = "") -> None:
    st.info(f"Não há dados do SICOM{f' ({categoria})' if categoria else ''} para o exercício selecionado. "
            "Importe os pacotes na aba **Atualização de dados**.", icon="📭")


def selo_severidade(severidade: str) -> str:
    s = SEVERIDADES.get(severidade, SEVERIDADES["Sem dados"])
    return (f"<span class='pv-sev' style='color:{s['cor']};background:{s['fundo']};border-color:{s['cor']}55'>"
            f"{s['icone']} {html.escape(severidade)}</span>")


# ----------------------------------------------------------------------------- cartões

def colunas_kpi(quantidade: int, chave: str) -> list:
    """Linha de cartões que quebra para a linha seguinte em telas estreitas."""
    caixa = st.container(horizontal=True, gap="small", key=f"kpis-{chave}")
    return [caixa] * quantidade


def kpi(coluna, rotulo: str, valor: str, ajuda: str | None = None, delta: str | None = None,
        cor_delta: str = "normal") -> None:
    coluna.metric(rotulo, valor, delta=delta, delta_color=cor_delta, help=ajuda, border=True, width="stretch")


# ----------------------------------------------------------------------------- gráficos

def _layout(fig: go.Figure, altura: int, titulo_y: str | None, legenda: bool) -> go.Figure:
    fig.update_layout(
        height=altura, margin=dict(l=8, r=16, t=40 if legenda else 16, b=8), separators=",.",
        font=dict(family="'Source Sans Pro', 'Segoe UI', system-ui, sans-serif", size=13, color=CORES["grafite"]),
        plot_bgcolor="#ffffff", paper_bgcolor="rgba(0,0,0,0)", barcornerradius=4, bargap=0.25, bargroupgap=0.06,
        hoverlabel=dict(bgcolor="#ffffff", bordercolor=CORES["borda"], font=dict(size=13, color=CORES["grafite"])),
        showlegend=legenda,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title_text="", font=dict(size=12)),
    )
    fig.update_xaxes(showgrid=False, linecolor=CORES["borda"], ticks="", tickfont=dict(size=12))
    fig.update_yaxes(gridcolor="#EFEAE4", zeroline=True, zerolinecolor=CORES["borda"], tickfont=dict(size=12),
                     title_text=titulo_y or "", title_font=dict(size=12, color="#6b6b6b"))
    return fig


def mostrar(fig: go.Figure, altura: int = 360, titulo_y: str | None = "R$ milhões", legenda: bool = True,
            chave: str | None = None) -> None:
    _layout(fig, altura, titulo_y, legenda)
    st.plotly_chart(fig, use_container_width=True, key=chave,
                    config={"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"]})


def barras_horizontais(df: pd.DataFrame, categoria: str, valor: str, cor: str = CORES["vermelho"], n: int = 12,
                       altura: int | None = None, chave: str | None = None) -> None:
    d = df[[categoria, valor]].groupby(categoria, as_index=False)[valor].sum()
    d = d[d[valor] != 0].nlargest(n, valor).sort_values(valor)
    if d.empty:
        st.caption("Sem valores para exibir.")
        return
    rotulos = [r if len(str(r)) <= 42 else str(r)[:40] + "…" for r in d[categoria]]
    fig = go.Figure(go.Bar(
        x=d[valor] / 1e6, y=rotulos, orientation="h", marker=dict(color=cor, line=dict(width=0)),
        text=[brl_compacto(v) for v in d[valor]], textposition="outside", cliponaxis=False,
        customdata=[[str(c), brl(v)] for c, v in zip(d[categoria], d[valor])],
        hovertemplate="%{customdata[0]}<br><b>%{customdata[1]}</b><extra></extra>"))
    maximo = float((d[valor] / 1e6).max())
    minimo = float(min(0.0, (d[valor] / 1e6).min()))
    fig.update_xaxes(showticklabels=False, showgrid=False, zeroline=False, range=[minimo * 1.45, maximo * 1.45 if maximo > 0 else 1])
    mostrar(fig, altura or max(220, 34 * len(d) + 40), titulo_y=None, legenda=False, chave=chave)


def colunas_mensais(series: dict[str, pd.Series], cores: dict[str, str], acumulado: bool = False,
                    tipo: str = "barra", altura: int = 340, chave: str | None = None) -> None:
    """Uma ou mais séries mensais (índice = mês 1..12) no mesmo eixo, em R$ milhões."""
    fig = go.Figure()
    for nome, serie in series.items():
        s = serie.sort_index()
        if acumulado:
            s = s.cumsum()
        x = [MESES[m - 1] for m in s.index]
        custom = [brl(v) for v in s.values]
        if tipo == "barra":
            fig.add_bar(name=nome, x=x, y=s.values / 1e6, marker=dict(color=cores.get(nome), line=dict(width=0)),
                        customdata=custom, hovertemplate=f"{nome} · %{{x}}<br><b>%{{customdata}}</b><extra></extra>")
        else:
            fig.add_scatter(name=nome, x=x, y=s.values / 1e6, mode="lines+markers",
                            line=dict(color=cores.get(nome), width=2.5), marker=dict(size=8, line=dict(width=2, color="#fff")),
                            customdata=custom, hovertemplate=f"{nome} · %{{x}}<br><b>%{{customdata}}</b><extra></extra>")
    fig.update_layout(hovermode="x unified" if tipo != "barra" else "closest", barmode="group")
    mostrar(fig, altura, legenda=len(series) > 1, chave=chave)


# ----------------------------------------------------------------------------- tabelas

def tabela(df: pd.DataFrame, moeda: tuple[str, ...] = (), percentual: tuple[str, ...] = (), datas: tuple[str, ...] = (),
           altura: int | None = None, arquivo: str | None = None, chave: str | None = None) -> None:
    if df is None or df.empty:
        st.caption("Sem registros.")
        return
    df = df.copy()
    for c in (*moeda, *percentual):
        if c in df.columns and pd.api.types.is_numeric_dtype(df[c]):
            df[c] = df[c].round(2)
    config = {c: st.column_config.NumberColumn(c, format="localized") for c in moeda if c in df.columns}
    config.update({c: st.column_config.NumberColumn(c, format="localized") for c in percentual if c in df.columns})
    config.update({c: st.column_config.DateColumn(c, format="DD/MM/YYYY") for c in datas if c in df.columns})
    st.dataframe(df, width="stretch", hide_index=True, column_config=config, height=altura or "auto", key=chave)
    if arquivo:
        csv = df.to_csv(sep=";", decimal=",", index=False, date_format="%d/%m/%Y").encode("utf-8-sig")
        st.download_button("⬇ Baixar CSV", csv, file_name=f"{arquivo}.csv", mime="text/csv",
                           key=f"baixar-{chave or arquivo}")


def filtrar_orgaos(df: pd.DataFrame) -> pd.DataFrame:
    orgaos = orgaos_selecionados()
    if df.empty or not orgaos or "cod_orgao" not in df.columns:
        return df
    return df[df["cod_orgao"].isin(orgaos)]


def ate_mes(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "mes" not in df.columns:
        return df
    return df[df["mes"] <= mes_selecionado()]


def legenda_orgaos() -> str:
    orgaos = orgaos_selecionados()
    return "Consolidado (todos os órgãos)" if not orgaos else ", ".join(ORGAOS[o] for o in orgaos)


__all__ = ["COR_ANO", "brl", "brl_compacto", "numero", "pct", "mes_ano"]
