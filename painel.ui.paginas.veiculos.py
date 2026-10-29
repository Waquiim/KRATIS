"""Aba Veículos (conjunto 'Frotas' do TCE-MG: cadastro de veículos e gastos)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from ... import dados
from ...config import CORES
from ...formatos import brl, brl_compacto, mes_ano, numero
from .. import comum


def pagina() -> None:
    ano, mes = comum.ano_selecionado(), comum.mes_selecionado()
    comum.cabecalho("Veículos", f"Frota e gastos com combustível, lubrificantes e manutenção informados ao SICOM até {mes_ano(ano, mes)}")
    veiculos, gastos = dados.frota(ano)
    veiculos, gastos = comum.filtrar_orgaos(veiculos), comum.filtrar_orgaos(comum.ate_mes(gastos))
    if veiculos.empty and gastos.empty:
        comum.aviso_sem_dados("Veículos")
        return
    c = comum.colunas_kpi(4, "veiculos-1")
    comum.kpi(c[0], "Veículos/equip.", numero(len(veiculos), 0))
    proprios = veiculos["situacao"].str.upper().str.contains("PATRIM", na=False).sum() if not veiculos.empty else 0
    comum.kpi(c[1], "Próprios / terceirizados", f"{numero(proprios, 0)} / {numero(len(veiculos) - proprios, 0)}")
    comum.kpi(c[2], "Gastos no período", brl_compacto(gastos["vlr_gasto"].sum() if not gastos.empty else 0))
    comum.kpi(c[3], "Registros de gastos", numero(len(gastos), 0))

    esquerda, direita = st.columns(2)
    with esquerda:
        comum.secao("Gastos por mês e tipo")
        if not gastos.empty:
            principais = gastos.groupby("tipo_gasto")["vlr_gasto"].sum().nlargest(3).index
            agrupado = gastos.assign(tipo=gastos["tipo_gasto"].where(gastos["tipo_gasto"].isin(principais), "Outros"))
            tipos = agrupado.groupby(["tipo", "mes"])["vlr_gasto"].sum()
            ordem = [t for t in principais] + (["Outros"] if "Outros" in tipos.index.get_level_values(0) else [])
            paleta = [CORES["vermelho"], CORES["azul"], CORES["dourado"], CORES["cinza"]]
            series = {t: tipos.loc[t] for t in ordem}
            comum.colunas_mensais(series, {t: paleta[i] for i, t in enumerate(ordem)}, chave="vei-mensal")
    with direita:
        comum.secao("Veículos com maior gasto")
        if not gastos.empty:
            cadastros = [dados.frota(a)[0] for a in (ano, ano - 1, ano - 2)]
            cadastro = pd.concat([c for c in cadastros if not c.empty], ignore_index=True).drop_duplicates("seq_veiculo")
            nomes = dict(zip(cadastro["seq_veiculo"], cadastro["dsc_num_placa"].fillna("") + " – " + cadastro["dsc_modelo"].fillna("")))
            g = gastos.assign(veiculo=gastos["seq_veiculo"].map(nomes))
            sem_cadastro = g["veiculo"].isna()
            if sem_cadastro.any():
                st.markdown(f"<div class='pv-nota'>{brl(g.loc[sem_cadastro, 'vlr_gasto'].sum())} em gastos vinculados a veículos "
                            "sem cadastro nos pacotes do SICOM não aparecem no ranking.</div>", unsafe_allow_html=True)
            comum.barras_horizontais(g[~sem_cadastro], "veiculo", "vlr_gasto", cor=CORES["vermelho"], chave="vei-top")

    comum.secao("Frota cadastrada")
    if not veiculos.empty:
        comum.tabela(veiculos[["dsc_num_placa", "tipo", "subtipo", "dsc_marca", "dsc_modelo", "num_anofabricacao", "situacao",
                               "nom_proprietario", "orgao"]].rename(columns={
            "dsc_num_placa": "Placa", "tipo": "Tipo", "subtipo": "Subtipo", "dsc_marca": "Marca", "dsc_modelo": "Modelo",
            "num_anofabricacao": "Ano", "situacao": "Situação", "nom_proprietario": "Proprietário", "orgao": "Órgão"}),
            altura=360, arquivo=f"frota_{ano}", chave="vei-frota")
    comum.secao("Gastos registrados")
    if not gastos.empty:
        comum.tabela(gastos[["mes", "seq_veiculo", "tipo_gasto", "quantidade", "vlr_gasto", "dsc_especificacao", "orgao"]].rename(columns={
            "mes": "Mês", "seq_veiculo": "Veículo (código)", "tipo_gasto": "Tipo", "quantidade": "Quantidade", "vlr_gasto": "Valor",
            "dsc_especificacao": "Especificação", "orgao": "Órgão"}), moeda=("Valor",), altura=360, arquivo=f"gastos_frota_{ano}",
            chave="vei-gastos")
    comum.rodape()
