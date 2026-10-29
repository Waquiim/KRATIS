"""Aba Educação (conjunto 'Educação' do TCE-MG: MDE com impostos) e FUNDEB, com dados do SICOM."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from ... import dados, indicadores
from ...config import CORES, LIMITES
from ...formatos import brl, brl_compacto, mes_ano, pct
from .. import comum
from .saude import evolucao_percentual


def pagina() -> None:
    ano, mes = comum.ano_selecionado(), comum.mes_selecionado()
    comum.cabecalho("Educação", f"Manutenção e desenvolvimento do ensino e FUNDEB – até {mes_ano(ano, mes)}")
    ed = comum.ate_mes(dados.educacao(ano))
    if ed.empty:
        comum.aviso_sem_dados("Educação")
        return
    m = indicadores.mde(ano, mes)
    f = indicadores.fundeb(ano, mes)
    c = comum.colunas_kpi(5, "educacao-1")
    comum.kpi(c[0], "MDE com impostos", brl_compacto(ed["liquidado"].sum()), "Liquidado com fonte 1.500 e CO 1001.")
    comum.kpi(c[1], "Contribuição FUNDEB", brl_compacto(m["contribuicao_fundeb"]), "20% retidos das transferências; conta como aplicação em MDE.")
    comum.kpi(c[2], "% MDE (SICOM)", pct(m["percentual_liquidado"]), f"Mínimo de {pct(LIMITES['mde_minimo'], 0)} no exercício.")
    comum.kpi(c[3], "Receitas FUNDEB", brl_compacto(f.get("receita")), "Fontes 540–546, inclusive rendimentos.")
    comum.kpi(c[4], "FUNDEB 70%", pct(f.get("percentual_remuneracao")), "Mínimo de 70% no exercício (CO 1070).")

    esquerda, direita = st.columns(2)
    with esquerda:
        comum.secao("Percentual aplicado em MDE, acumulado no ano")
        evolucao_percentual(indicadores.mde, [ano - 1, ano], mes, "edu-evolucao", LIMITES["mde_minimo"], "% da receita de impostos")
    with direita:
        comum.secao("Por subfunção", "Despesa liquidada com impostos (MDE).")
        comum.barras_horizontais(ed, "subfuncao", "liquidado", cor=CORES["azul"], chave="edu-subfuncao")

    comum.secao("FUNDEB no exercício", "Receitas das fontes 540–546 (inclusive rendimentos) e sua aplicação, conforme o SICOM.")
    if f:
        tabela = pd.DataFrame([
            {"Item": "Receitas do FUNDEB", "Valor": f["receita"]},
            {"Item": "Despesa empenhada com FUNDEB", "Valor": f["despesa_empenhada"]},
            {"Item": "Despesa liquidada com FUNDEB", "Valor": f["despesa_liquidada"]},
            {"Item": "Remuneração dos profissionais – liquidada (CO 1070)", "Valor": f["remuneracao_liquidada"]},
            {"Item": "Receitas ainda não empenhadas", "Valor": f["nao_aplicado"]},
        ])
        comum.tabela(tabela, moeda=("Valor",), chave="edu-fundeb")

    comum.secao("Composição da base de cálculo do MDE")
    comum.tabela(m["itens_base"], moeda=("Valor",), chave="edu-base")

    comum.secao("Empenhos em MDE com recursos de impostos")
    lista = ed.groupby(["empenho", "data_empenho", "subfuncao", "acao", "natureza_cod", "natureza"], dropna=False)[
        ["empenhado", "liquidado", "pago"]].sum().reset_index().sort_values("empenhado", ascending=False)
    comum.tabela(lista.rename(columns={"empenho": "Empenho", "data_empenho": "Data", "subfuncao": "Subfunção", "acao": "Ação",
                                       "natureza_cod": "Natureza", "natureza": "Descrição", "empenhado": "Empenhado",
                                       "liquidado": "Liquidado", "pago": "Pago"}),
                 moeda=("Empenhado", "Liquidado", "Pago"), datas=("Data",), altura=380, arquivo=f"educacao_{ano}", chave="edu-lista")
    comum.rodape()
