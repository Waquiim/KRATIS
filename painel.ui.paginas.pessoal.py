"""Aba Despesa com Pessoal (conjunto 'Despesa com Pessoal' do TCE-MG) e limites da LRF."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ... import dados, indicadores
from ...config import CORES, LIMITES, MESES
from ...fontes import tce_sicom
from ...formatos import brl, brl_compacto, mes_ano, pct
from .. import comum
from .visao_geral import versao_dados


# cache_resource: guarda o objeto sem serializar (o pandas da versão web não desserializa datas)
@st.cache_resource(ttl=3600, show_spinner="Calculando a série de 12 meses…")
def _serie(versao: str) -> pd.DataFrame:
    anos = sorted(a for a in range(2000, 2100) if tce_sicom.caminho_zip(a, "desp_pessoal").exists())
    linhas = []
    for a in anos:
        for m in range(1, dados.ultimo_mes(a) + 1):
            est = indicadores.pessoal_12m(a, m)
            if est.get("completo"):
                linhas.append({"per": a * 100 + m, "Executivo": est["percentual_executivo"],
                               "Legislativo": est["percentual_legislativo"], "Município": est["percentual_municipio"]})
    return pd.DataFrame(linhas)


def pagina() -> None:
    ano, mes = comum.ano_selecionado(), comum.mes_selecionado()
    comum.cabecalho("Despesa com Pessoal", f"Despesa com pessoal informada ao SICOM e limites da LRF – até {mes_ano(ano, mes)}")
    p = comum.ate_mes(dados.pessoal(ano))
    if p.empty:
        comum.aviso_sem_dados("Despesa com Pessoal")
        return
    est = indicadores.pessoal_12m(ano, mes)
    c = comum.colunas_kpi(4, "pessoal-1")
    comum.kpi(c[0], "Executivo no ano", brl_compacto(p["executivo"].sum()), brl(p["executivo"].sum()))
    comum.kpi(c[1], "Legislativo no ano", brl_compacto(p["legislativo"].sum()), brl(p["legislativo"].sum()))
    comum.kpi(c[2], "Município no ano", brl_compacto(p["municipio"].sum()), brl(p["municipio"].sum()))
    comum.kpi(c[3], "Executivo / RCL ajustada", pct(est.get("percentual_executivo")),
              f"12 meses até {mes_ano(ano, mes)}, metodologia do MDF aplicada aos dados do SICOM.")

    esquerda, direita = st.columns(2)
    with esquerda:
        comum.secao("Despesa mensal", "Conjunto 'Despesa com Pessoal' do TCE-MG (valores brutos).")
        mensal = p.groupby("mes")[["executivo", "legislativo"]].sum()
        comum.colunas_mensais({"Executivo": mensal["executivo"], "Legislativo": mensal["legislativo"]},
                              {"Executivo": CORES["vermelho"], "Legislativo": CORES["azul"]}, chave="pes-mensal")
    with direita:
        comum.secao("Percentual da RCL ajustada em 12 meses", "Linha tracejada: limite máximo do Executivo (54%); pontilhadas: alerta e prudencial.")
        serie = _serie(versao_dados())
        if not serie.empty:
            x = [f"{MESES[p % 100 - 1]}/{str(p // 100)[2:]}" for p in serie["per"]]
            fig = go.Figure()
            for nome, cor in (("Executivo", CORES["vermelho"]), ("Legislativo", CORES["azul"])):
                fig.add_scatter(name=nome, x=x, y=serie[nome], mode="lines+markers", line=dict(color=cor, width=2.5),
                                marker=dict(size=7, line=dict(width=2, color="#fff")),
                                hovertemplate=f"{nome} · %{{x}}<br><b>%{{y:.2f}}%</b><extra></extra>")
            for valor, rotulo in ((LIMITES["pessoal_executivo"]["alerta"], "Alerta"),
                                  (LIMITES["pessoal_executivo"]["prudencial"], "Prudencial"),
                                  (LIMITES["pessoal_executivo"]["maximo"], "Máximo")):
                fig.add_hline(y=valor, line=dict(color="#8E1414" if rotulo == "Máximo" else "#9a9a9a",
                                                 dash="dash" if rotulo == "Máximo" else "dot", width=1),
                              annotation_text=f"{rotulo} {pct(valor, 1)}" if rotulo == "Máximo" else None,
                              annotation_position="top left", annotation_font_size=11)
            fig.update_yaxes(range=[0, 60])
            fig.update_layout(hovermode="x unified")
            comum.mostrar(fig, 340, titulo_y="% da RCL ajustada", chave="pes-serie")

    if est.get("completo"):
        comum.secao(f"Apuração dos 12 meses até {mes_ano(ano, mes)}", "Metodologia do MDF/STN (RGF Anexo 1) aplicada aos dados do SICOM.")
        c = comum.colunas_kpi(4, "pessoal-2")
        comum.kpi(c[0], "Bruta – Executivo", brl_compacto(est["bruta_executivo"]))
        comum.kpi(c[1], "Exclusões (art. 19)", brl_compacto(est["bruta_executivo"] - est["liquida_executivo"]))
        comum.kpi(c[2], "RCL ajustada", brl_compacto(est["rcl_ajustada"]))
        comum.kpi(c[3], "Legislativo / RCL aj.", pct(est["percentual_legislativo"]))
        comum.tabela(est["exclusoes"], moeda=("Executivo", "Legislativo"), chave="pes-exclusoes")

    comum.secao("Por natureza de despesa")
    por_natureza = p.groupby(["natureza_cod", "natureza"])[["executivo", "legislativo", "municipio"]].sum().reset_index()
    por_natureza = por_natureza[por_natureza["municipio"] != 0].sort_values("municipio", ascending=False)
    comum.tabela(por_natureza.rename(columns={"natureza_cod": "Natureza", "natureza": "Descrição", "executivo": "Executivo",
                                              "legislativo": "Legislativo", "municipio": "Município"}),
                 moeda=("Executivo", "Legislativo", "Município"), arquivo=f"pessoal_natureza_{ano}", chave="pes-natureza")
    comum.rodape()
