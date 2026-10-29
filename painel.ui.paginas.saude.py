"""Aba Saúde (conjunto 'Saúde' do TCE-MG: ASPS custeadas com recursos de impostos)."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from ... import dados, indicadores
from ...config import COR_ANO, CORES, LIMITES, MESES
from ...formatos import brl, brl_compacto, mes_ano, pct
from .. import comum


def evolucao_percentual(funcao, anos: list[int], mes_max: int, chave: str, minimo: float, titulo_y: str) -> None:
    fig = go.Figure()
    for a in anos:
        ultimo = min(dados.ultimo_mes(a), mes_max if a == anos[-1] else 12)
        if not ultimo:
            continue
        meses = list(range(1, ultimo + 1))
        valores = [funcao(a, m)["percentual_liquidado"] for m in meses]
        fig.add_scatter(name=str(a), x=[MESES[m - 1] for m in meses], y=valores, mode="lines+markers",
                        line=dict(color=COR_ANO.get(a, CORES["cinza"]), width=2.5),
                        marker=dict(size=8, line=dict(width=2, color="#fff")),
                        hovertemplate=f"{a} · até %{{x}}<br><b>%{{y:.2f}}%</b><extra></extra>")
    fig.add_hline(y=minimo, line=dict(color="#8E1414", dash="dash", width=1), annotation_text=f"Mínimo {pct(minimo, 0)}",
                  annotation_position="top left", annotation_font_size=11)
    fig.update_layout(hovermode="x unified")
    comum.mostrar(fig, 330, titulo_y=titulo_y, chave=chave)


def pagina() -> None:
    ano, mes = comum.ano_selecionado(), comum.mes_selecionado()
    comum.cabecalho("Saúde", f"Ações e serviços públicos de saúde custeados com impostos (fonte 1.500, CO 1002) – até {mes_ano(ano, mes)}")
    sa = comum.ate_mes(dados.saude(ano))
    if sa.empty:
        comum.aviso_sem_dados("Saúde")
        return
    a = indicadores.asps(ano, mes)
    c = comum.colunas_kpi(5, "saude-1")
    comum.kpi(c[0], "Empenhado", brl_compacto(sa["empenhado"].sum()), brl(sa["empenhado"].sum()))
    comum.kpi(c[1], "Liquidado", brl_compacto(sa["liquidado"].sum()), brl(sa["liquidado"].sum()))
    comum.kpi(c[2], "Pago", brl_compacto(sa["pago"].sum()), brl(sa["pago"].sum()))
    comum.kpi(c[3], "Base de cálculo", brl_compacto(a["base"]), "Excluídas as cotas extras de 1% do FPM (LC 141/2012).")
    comum.kpi(c[4], "% ASPS (SICOM)", pct(a["percentual_liquidado"]),
              f"Despesas liquidadas ÷ base. Mínimo de {pct(LIMITES['asps_minimo'], 0)} no exercício.")

    esquerda, direita = st.columns(2)
    with esquerda:
        comum.secao("Percentual aplicado em ASPS, acumulado no ano")
        evolucao_percentual(indicadores.asps, [ano - 1, ano], mes, "sau-evolucao", LIMITES["asps_minimo"], "% da receita de impostos")
    with direita:
        comum.secao("Por subfunção", "Despesa liquidada no período.")
        comum.barras_horizontais(sa, "subfuncao", "liquidado", cor=CORES["vermelho"], chave="sau-subfuncao")

    comum.secao("Composição da base de cálculo")
    comum.tabela(a["itens_base"], moeda=("Valor",), chave="sau-base")

    comum.secao("Empenhos com recursos próprios em saúde")
    lista = sa.groupby(["empenho", "data_empenho", "subfuncao", "acao", "natureza_cod", "natureza"], dropna=False)[
        ["empenhado", "liquidado", "pago"]].sum().reset_index().sort_values("empenhado", ascending=False)
    comum.tabela(lista.rename(columns={"empenho": "Empenho", "data_empenho": "Data", "subfuncao": "Subfunção", "acao": "Ação",
                                       "natureza_cod": "Natureza", "natureza": "Descrição", "empenhado": "Empenhado",
                                       "liquidado": "Liquidado", "pago": "Pago"}),
                 moeda=("Empenhado", "Liquidado", "Pago"), datas=("Data",), altura=380, arquivo=f"saude_{ano}", chave="sau-lista")
    comum.rodape()
