"""Comparativo do exercício atual com os dois anteriores (mesmo período e exercício completo)."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ... import dados, indicadores
from ...config import COR_ANO, CORES, MESES
from ...formatos import brl, mes_ano, pct
from .. import comum


def _agregados(ano: int, ate: int, orgaos: list[str] | None) -> dict:
    r = dados.receitas(ano)
    d = dados.despesas(ano)
    if r.empty or d.empty:
        return {}
    if orgaos:
        r, d = r[r["cod_orgao"].isin(orgaos)], d[d["cod_orgao"].isin(orgaos)]
    r, d = r[(r["mes"] <= ate) & ~r["intra"]], d[(d["mes"] <= ate) & ~d["intra"]]
    linha = {
        "Receitas correntes (líquidas)": r.loc[r["categoria_cod"] == "1", "realizado"].sum(),
        "Receitas de capital": r.loc[r["categoria_cod"] == "2", "realizado"].sum(),
        "Receita total arrecadada": r["realizado"].sum(),
        "Impostos municipais (IPTU, ISS, ITBI, IRRF)": r.loc[r["natureza_cod"].str.match(r"^1\.1\.1\.(2\.5[03]|3\.03|4\.51)") & ~r["deducao"], "realizado"].sum(),
        "Transferências correntes (brutas)": r.loc[r["origem_cod"].eq("1.7.0.0.00.0.0") & ~r["deducao"], "realizado"].sum(),
        "Despesa empenhada": d["empenhado"].sum(),
        "Despesa liquidada": d["liquidado"].sum(),
        "Despesa paga": d["pago"].sum(),
        "Pessoal e encargos (liquidado)": d.loc[d["grupo_cod"] == "3.1", "liquidado"].sum(),
        "Outras despesas correntes (liquidado)": d.loc[d["grupo_cod"] == "3.3", "liquidado"].sum(),
        "Investimentos (liquidado)": d.loc[d["grupo_cod"] == "4.4", "liquidado"].sum(),
    }
    linha["Resultado (receita − despesa liquidada)"] = linha["Receita total arrecadada"] - linha["Despesa liquidada"]
    return linha


def _indices(ano: int, ate: int) -> dict:
    saida = {"MDE – % aplicado (liquidado)": indicadores.mde(ano, ate)["percentual_liquidado"],
             "ASPS – % aplicado (liquidado)": indicadores.asps(ano, ate)["percentual_liquidado"],
             "FUNDEB – % na remuneração": indicadores.fundeb(ano, ate).get("percentual_remuneracao")}
    dc = indicadores.dc_rc(ano, ate)
    saida["DC/RC 12 meses – TCE-MG (%)"] = dc.get("percentual") if dc.get("completo") else None
    rcl = indicadores.rcl(ano, ate)
    saida["RCL 12 meses (SICOM)"] = rcl.get("rcl") if rcl.get("completo") else None
    return saida


def _variacao(atual, anterior):
    if atual is None or anterior in (None, 0) or pd.isna(atual) or pd.isna(anterior):
        return None
    return (atual / anterior - 1) * 100


def pagina() -> None:
    ano, mes = comum.ano_selecionado(), comum.mes_selecionado()
    anos = [ano - 2, ano - 1, ano]
    comum.cabecalho("Comparativo entre exercícios", f"{ano} comparado a {ano - 1} e {ano - 2} – {comum.legenda_orgaos()}")
    modo = st.segmented_control("Período", [f"Mesmo período (jan–{MESES[mes - 1].lower()})", "Exercícios completos"],
                                default=f"Mesmo período (jan–{MESES[mes - 1].lower()})", key="cmp-modo")
    mesmo_periodo = not modo or modo.startswith("Mesmo")
    orgaos = comum.orgaos_selecionados() or None
    linhas = {}
    for a in anos:
        ate = mes if (mesmo_periodo or a == ano) else 12
        linhas[a] = _agregados(a, ate, orgaos)
    linhas = {a: v for a, v in linhas.items() if v}
    if ano not in linhas:
        comum.aviso_sem_dados()
        return
    if not mesmo_periodo:
        st.info(f"{ano} aparece até {mes_ano(ano, mes)}; os exercícios anteriores, completos.", icon="ℹ️")

    tabela = pd.DataFrame(linhas)
    tabela.columns = [str(c) for c in tabela.columns]
    if str(ano - 1) in tabela:
        tabela[f"Var. {ano}/{ano - 1} (%)"] = [_variacao(x, y) for x, y in zip(tabela[str(ano)], tabela[str(ano - 1)])]
    if str(ano - 2) in tabela and str(ano - 1) in tabela:
        tabela[f"Var. {ano - 1}/{ano - 2} (%)"] = [_variacao(x, y) for x, y in zip(tabela[str(ano - 1)], tabela[str(ano - 2)])]
    tabela = tabela.reset_index().rename(columns={"index": "Indicador"})
    comum.secao("Receitas e despesas (R$)", "Valores sem intraorçamentárias; receitas líquidas das deduções do FUNDEB.")
    comum.tabela(tabela, moeda=tuple(str(a) for a in linhas), percentual=tuple(c for c in tabela.columns if c.startswith("Var.")),
                 arquivo=f"comparativo_{ano}", chave="cmp-tabela")

    comum.secao("Índices fiscais", "Estimativas com dados do SICOM; DC/RC e RCL em 12 meses encerrados no mês de referência.")
    indices = pd.DataFrame({str(a): _indices(a, mes if (mesmo_periodo or a == ano) else 12) for a in linhas}).reset_index()
    indices = indices.rename(columns={"index": "Indicador"})
    comum.tabela(indices, moeda=tuple(str(a) for a in linhas), chave="cmp-indices")

    esquerda, direita = st.columns(2)
    for coluna, titulo, categoria, campo, chave in (
            (esquerda, "Receitas correntes acumuladas", "receitas", "realizado", "cmp-rec"),
            (direita, "Despesa liquidada acumulada", "despesas", "liquidado", "cmp-desp")):
        with coluna:
            comum.secao(titulo)
            fig = go.Figure()
            for a in linhas:
                base = getattr(dados, categoria)(a)
                if orgaos:
                    base = base[base["cod_orgao"].isin(orgaos)]
                base = base[~base["intra"]]
                if categoria == "receitas":
                    base = base[base["categoria_cod"] == "1"]
                limite = mes if (mesmo_periodo or a == ano) else 12
                serie = base[base["mes"] <= limite].groupby("mes")[campo].sum().cumsum()
                fig.add_scatter(name=str(a), x=[MESES[m - 1] for m in serie.index], y=serie.values / 1e6, mode="lines+markers",
                                line=dict(color=COR_ANO.get(a), width=2.5), marker=dict(size=8, line=dict(width=2, color="#fff")),
                                customdata=[brl(v) for v in serie.values],
                                hovertemplate=f"{a} · até %{{x}}<br><b>%{{customdata}}</b><extra></extra>")
            fig.update_layout(hovermode="x unified")
            comum.mostrar(fig, 340, chave=chave)

    comum.secao("Receita por origem", "Valores brutos no período comparado.")
    partes = []
    for a in linhas:
        r = dados.receitas(a)
        r = r[(r["mes"] <= (mes if (mesmo_periodo or a == ano) else 12)) & ~r["intra"] & ~r["deducao"]]
        if orgaos:
            r = r[r["cod_orgao"].isin(orgaos)]
        partes.append(r.groupby("origem")["realizado"].sum().rename(str(a)))
    _barras_agrupadas(pd.concat(partes, axis=1).fillna(0.0), "cmp-origem")

    comum.secao("Despesa liquidada por função (10 maiores)")
    partes = []
    for a in linhas:
        d = dados.despesas(a)
        d = d[(d["mes"] <= (mes if (mesmo_periodo or a == ano) else 12)) & ~d["intra"]]
        if orgaos:
            d = d[d["cod_orgao"].isin(orgaos)]
        partes.append(d.groupby("funcao")["liquidado"].sum().rename(str(a)))
    funcoes = pd.concat(partes, axis=1).fillna(0.0)
    _barras_agrupadas(funcoes.loc[funcoes[str(ano)].nlargest(10).index], "cmp-funcao")
    comum.rodape()


def _barras_agrupadas(tabela: pd.DataFrame, chave: str) -> None:
    tabela = tabela.sort_values(tabela.columns[-1])
    fig = go.Figure()
    for coluna in tabela.columns:
        fig.add_bar(name=coluna, y=tabela.index, x=tabela[coluna] / 1e6, orientation="h",
                    marker=dict(color=COR_ANO.get(int(coluna), CORES["cinza"])),
                    customdata=[brl(v) for v in tabela[coluna]],
                    hovertemplate=f"%{{y}} · {coluna}<br><b>%{{customdata}}</b><extra></extra>")
    fig.update_layout(barmode="group")
    fig.update_xaxes(title_text="R$ milhões")
    comum.mostrar(fig, max(300, 70 * len(tabela) + 60), titulo_y=None, chave=chave)
