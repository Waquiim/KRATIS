"""Aba Receitas (conjunto 'Receitas' do portal de dados abertos do TCE-MG)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from ... import dados
from ...config import CORES
from ...formatos import brl, brl_compacto, mes_ano, pct
from .. import comum

NIVEIS = {
    "Origem": ("origem_cod", "origem"),
    "Espécie": ("especie_cod", "especie"),
    "Rubrica": ("rubrica_cod", "rubrica"),
    "Alínea": ("alinea_cod", "alinea"),
    "Subalínea": ("subalinea_cod", "subalinea"),
    "Natureza detalhada": ("natureza_cod", "natureza"),
}
CATEGORIAS = {"Correntes": ["1"], "Capital": ["2"], "Intraorçamentárias": ["7", "8"]}


def _resumo(df: pd.DataFrame, mes: int, codigo: str, descricao: str) -> pd.DataFrame:
    previsto = df.groupby([codigo, descricao])[["previsao_inicial", "previsao_atualizada"]].sum()
    realizado = df[df["mes"] <= mes].groupby([codigo, descricao])["realizado"].sum()
    tabela = previsto.join(realizado, how="outer").fillna(0.0).reset_index()
    tabela["% realizado"] = (tabela["realizado"] / tabela["previsao_atualizada"].where(tabela["previsao_atualizada"] != 0) * 100).round(2)
    tabela = tabela.rename(columns={codigo: "Código", descricao: "Descrição", "previsao_inicial": "Previsão inicial",
                                    "previsao_atualizada": "Previsão atualizada", "realizado": "Arrecadado"})
    return tabela.sort_values("Arrecadado", ascending=False)


def pagina() -> None:
    ano, mes = comum.ano_selecionado(), comum.mes_selecionado()
    comum.cabecalho("Receitas", f"Previsão e arrecadação informadas ao SICOM até {mes_ano(ano, mes)} – {comum.legenda_orgaos()}")
    base = comum.filtrar_orgaos(dados.receitas(ano))
    if base.empty:
        comum.aviso_sem_dados("Receitas")
        return
    escolha = st.pills("Categorias econômicas", list(CATEGORIAS), default=["Correntes", "Capital"], selection_mode="multi",
                       key="rec-categorias")
    codigos = [c for nome in (escolha or list(CATEGORIAS)) for c in CATEGORIAS[nome]]
    df = base[base["categoria_cod"].isin(codigos)]
    periodo = df[df["mes"] <= mes]

    c = comum.colunas_kpi(5, "receitas-1")
    prev_ini, prev_atu = df["previsao_inicial"].sum(), df["previsao_atualizada"].sum()
    arrecadado = periodo["realizado"].sum()
    deducoes = periodo.loc[periodo["deducao"], "realizado"].sum()
    comum.kpi(c[0], "Previsão inicial", brl_compacto(prev_ini), brl(prev_ini))
    comum.kpi(c[1], "Previsão atualizada", brl_compacto(prev_atu), brl(prev_atu))
    comum.kpi(c[2], "Arrecadado", brl_compacto(arrecadado), f"{brl(arrecadado)} – já descontadas as deduções")
    comum.kpi(c[3], "Realizado / previsto", pct(arrecadado / prev_atu * 100 if prev_atu else None, 1))
    comum.kpi(c[4], "Deduções (FUNDEB)", brl_compacto(-deducoes), "Parcela retida para a formação do FUNDEB (20%).")

    esquerda, direita = st.columns(2)
    with esquerda:
        comum.secao("Arrecadação mensal")
        bruta = periodo[~periodo["deducao"]]
        series = {nome: bruta[bruta["categoria_cod"].isin(CATEGORIAS[nome])].groupby("mes")["realizado"].sum()
                  for nome in (escolha or list(CATEGORIAS))}
        series = {k: v for k, v in series.items() if not v.empty}
        cores = {"Correntes": CORES["azul"], "Capital": CORES["vermelho"], "Intraorçamentárias": CORES["dourado"]}
        comum.colunas_mensais(series, cores, chave="rec-mensal")
    with direita:
        comum.secao("Arrecadação por origem", "Valores brutos, antes das deduções.")
        comum.barras_horizontais(periodo[~periodo["deducao"]], "origem", "realizado", cor=CORES["azul"], chave="rec-origem")

    comum.secao("Receitas por natureza (classificação da receita)")
    nivel = st.segmented_control("Nível", list(NIVEIS), default="Espécie", key="rec-nivel") or "Espécie"
    tabela = _resumo(df, mes, *NIVEIS[nivel])
    busca = st.text_input("Filtrar por código ou descrição", key="rec-busca", placeholder="ex.: IPTU, 1.7.1, FPM")
    if busca:
        filtro = tabela["Descrição"].str.contains(busca, case=False, na=False) | tabela["Código"].str.contains(busca, case=False, na=False)
        tabela = tabela[filtro]
    comum.tabela(tabela, moeda=("Previsão inicial", "Previsão atualizada", "Arrecadado"), percentual=("% realizado",),
                 arquivo=f"receitas_{ano}_{nivel.lower()}", chave="rec-tabela")

    comum.secao("Receitas por fonte de recursos")
    fontes = _resumo(df, mes, "fonte", "fonte_desc")
    comum.tabela(fontes, moeda=("Previsão inicial", "Previsão atualizada", "Arrecadado"), percentual=("% realizado",),
                 arquivo=f"receitas_{ano}_fontes", chave="rec-fontes")
    comum.rodape()
