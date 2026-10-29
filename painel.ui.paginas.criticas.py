"""Aba Críticas: pontos dos dados do exercício passíveis de apontamento pelo TCE-MG."""
from __future__ import annotations

import io

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ... import indicadores
from ...config import CORES, LIMITES, MESES, SEVERIDADES
from ...criticas import GRUPOS
from ...formatos import pct
from .. import comum
from .visao_geral import _criticas, versao_dados


def _grafico_dc_rc() -> None:
    serie = indicadores.dc_rc_serie()
    if serie.empty:
        return
    x = [f"{MESES[p % 100 - 1]}/{str(p // 100)[2:]}" for p in serie["per"]]
    fig = go.Figure()
    fig.add_scatter(name="Metodologia TCE-MG (exclui superávit)", x=x, y=serie["percentual"], mode="lines+markers",
                    line=dict(color=CORES["vermelho"], width=2.5), marker=dict(size=8, line=dict(width=2, color="#fff")),
                    hovertemplate="%{x}<br><b>%{y:.2f}%</b><extra>TCE-MG</extra>")
    fig.add_scatter(name="Sem exclusão", x=x, y=serie["percentual_sem_exclusao"], mode="lines",
                    line=dict(color=CORES["azul"], width=2, dash="dot"),
                    hovertemplate="%{x}<br><b>%{y:.2f}%</b><extra>sem exclusão</extra>")
    for valor, rotulo in ((LIMITES["dc_rc"]["alerta"], "Alerta 85%"), (LIMITES["dc_rc"]["limite"], "Limite 95%")):
        fig.add_hline(y=valor, line=dict(color="#8E1414" if valor >= 95 else "#9a9a9a", dash="dash", width=1),
                      annotation_text=rotulo, annotation_position="top left", annotation_font_size=11)
    fig.update_layout(hovermode="x unified")
    comum.mostrar(fig, 320, titulo_y="% (12 meses móveis)", chave="crit-dcrc")


def _excel(lista: list[dict]) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as escritor:
        resumo = pd.DataFrame([{k: c[k] for k in ("codigo", "severidade", "grupo", "titulo", "resultado", "referencia", "fundamento",
                                                   "metodologia", "fonte", "recomendacao")} for c in lista])
        resumo.columns = ["Código", "Severidade", "Grupo", "Título", "Resultado", "Referência", "Fundamento", "Metodologia",
                          "Fonte", "Recomendação"]
        resumo.to_excel(escritor, sheet_name="Críticas", index=False)
        for c in lista:
            if isinstance(c.get("detalhe"), pd.DataFrame) and not c["detalhe"].empty:
                c["detalhe"].to_excel(escritor, sheet_name=c["codigo"][:31], index=False)
    return buffer.getvalue()


def pagina() -> None:
    ano = comum.ano_selecionado()
    comum.cabecalho(f"Críticas {ano}", "Pontos dos dados informados passíveis de apontamento pelo TCE-MG, com metodologia e fundamentação")
    st.markdown(
        "<div class='pv-nota'>As verificações aplicam as metodologias e parametrizações oficiais (MDF/STN, LRF, Constituição, "
        "normas e consultas do TCE-MG) aos dados do SICOM publicados no portal de dados abertos do TCE-MG. "
        "São indicativas e servem para correção preventiva; a apuração oficial é a do TCE-MG.</div>", unsafe_allow_html=True)
    lista = _criticas(ano, versao_dados())

    colunas = st.columns(len(SEVERIDADES))
    for coluna, (sev, info) in zip(colunas, SEVERIDADES.items()):
        n = sum(1 for c in lista if c["severidade"] == sev)
        coluna.markdown(f"<div class='pv-cartao-sev' style='border-color:{info['cor']}55;background:{info['fundo']}'>"
                        f"<div class='n' style='color:{info['cor']}'>{n}</div>"
                        f"<div class='r' style='color:{info['cor']}'>{info['icone']} {sev}</div></div>", unsafe_allow_html=True)

    filtros = st.columns([3, 3, 2])
    severidades = filtros[0].pills("Severidade", list(SEVERIDADES), default=["Crítico", "Alto", "Médio", "Baixo"],
                                   selection_mode="multi", key="crit-sev")
    grupos = filtros[1].multiselect("Grupo", GRUPOS, key="crit-grupo", placeholder="Todos os grupos")
    filtros[2].download_button("⬇ Exportar para Excel", _excel(lista), file_name=f"criticas_vicosa_{ano}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="crit-excel")
    visiveis = [c for c in lista if (not severidades or c["severidade"] in severidades) and (not grupos or c["grupo"] in grupos)]
    st.caption(f"{len(visiveis)} de {len(lista)} verificações exibidas.")

    for indice, c in enumerate(visiveis):
        info = SEVERIDADES.get(c["severidade"], SEVERIDADES["Sem dados"])
        with st.expander(f"{info['icone']} {c['severidade']} · {c['codigo']} · {c['titulo']}",
                         expanded=c["severidade"] in ("Crítico", "Alto")):
            st.markdown(f"{comum.selo_severidade(c['severidade'])} &nbsp;<span class='pv-nota'>{c['grupo']}</span>",
                        unsafe_allow_html=True)
            st.markdown(f"**Resultado:** {c['resultado']}")
            esquerda, direita = st.columns(2)
            with esquerda:
                if c["referencia"]:
                    st.markdown(f"**Referência / limite:** {c['referencia']}")
                if c["fundamento"]:
                    st.markdown(f"**Fundamentação:** {c['fundamento']}")
                if c["fonte"]:
                    st.markdown(f"**Fonte dos dados:** {c['fonte']}")
            with direita:
                if c["metodologia"]:
                    st.markdown(f"**Metodologia:** {c['metodologia']}")
                if c["recomendacao"]:
                    st.markdown(f"**Recomendação:** {c['recomendacao']}")
            if c.get("grafico") == "dc_rc":
                _grafico_dc_rc()
            detalhe = c.get("detalhe")
            if isinstance(detalhe, pd.DataFrame) and not detalhe.empty:
                numericas = tuple(col for col in detalhe.columns if pd.api.types.is_float_dtype(detalhe[col]))
                datas = tuple(col for col in detalhe.columns if pd.api.types.is_datetime64_any_dtype(detalhe[col]))
                comum.tabela(detalhe, moeda=numericas, datas=datas, arquivo=f"critica_{c['codigo']}_{ano}",
                             chave=f"crit-{indice}-{c['codigo']}")
    comum.rodape()
