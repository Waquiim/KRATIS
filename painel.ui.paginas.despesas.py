"""Aba Despesas (conjunto 'Despesas' do portal de dados abertos do TCE-MG)."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ... import dados
from ...config import CORES, MESES
from ...formatos import brl, brl_compacto, mes_ano, pct
from .. import comum

DIMENSOES = {
    "Órgão": ["orgao"],
    "Função": ["funcao_cod", "funcao"],
    "Subfunção": ["subfuncao_cod", "subfuncao"],
    "Programa": ["programa_cod", "programa"],
    "Ação": ["acao_cod", "acao"],
    "Grupo de natureza": ["grupo_cod", "grupo"],
    "Elemento de despesa": ["natureza_cod", "natureza"],
    "Fonte de recursos": ["fonte", "fonte_desc"],
}


def _resumo(df: pd.DataFrame, mes: int, chaves: list[str]) -> pd.DataFrame:
    ate = df[df["mes"] <= mes]
    inicial = df.groupby(chaves)["dotacao_inicial"].sum()
    alteracoes = ate.assign(_alt=ate["acrescimo"] - ate["reducao"]).groupby(chaves)["_alt"].sum()
    execucao = ate.groupby(chaves)[["empenhado", "liquidado", "pago"]].sum()
    tabela = pd.concat([inicial, alteracoes.rename("alteracoes"), execucao], axis=1).fillna(0.0)
    # Dotação atualizada = dotação inicial (LOA) + créditos adicionais − anulações registrados até o mês.
    tabela["dotacao_atualizada"] = tabela["dotacao_inicial"] + tabela["alteracoes"]
    tabela = tabela.reset_index()[chaves + ["dotacao_inicial", "dotacao_atualizada", "empenhado", "liquidado", "pago"]]
    tabela["% empenhado"] = (tabela["empenhado"] / tabela["dotacao_atualizada"].where(tabela["dotacao_atualizada"] != 0) * 100).round(2)
    return tabela.rename(columns={"dotacao_inicial": "Dotação inicial", "dotacao_atualizada": "Dotação atualizada",
                                  "empenhado": "Empenhado", "liquidado": "Liquidado", "pago": "Pago",
                                  "orgao": "Órgão", "funcao_cod": "Código", "funcao": "Função", "subfuncao_cod": "Código",
                                  "subfuncao": "Subfunção", "programa_cod": "Código", "programa": "Programa",
                                  "acao_cod": "Código", "acao": "Ação", "grupo_cod": "Código", "grupo": "Grupo",
                                  "natureza_cod": "Código", "natureza": "Elemento", "fonte": "Código",
                                  "fonte_desc": "Fonte"}).sort_values("Empenhado", ascending=False)


def pagina() -> None:
    ano, mes = comum.ano_selecionado(), comum.mes_selecionado()
    comum.cabecalho("Despesas", f"Dotação e execução orçamentária informadas ao SICOM até {mes_ano(ano, mes)} – {comum.legenda_orgaos()}")
    base = comum.filtrar_orgaos(dados.despesas(ano))
    if base.empty:
        comum.aviso_sem_dados("Despesas")
        return
    intra = st.toggle("Incluir despesas intraorçamentárias", value=False, key="desp-intra",
                      help="Operações entre órgãos do próprio Município (ex.: contribuição patronal ao RPPS).")
    df = base if intra else base[~base["intra"]]
    resumo = _resumo(df.assign(total="Total"), mes, ["total"]).iloc[0]

    c = comum.colunas_kpi(5, "despesas-1")
    comum.kpi(c[0], "Dotação inicial", brl_compacto(resumo["Dotação inicial"]), brl(resumo["Dotação inicial"]))
    comum.kpi(c[1], "Dotação atualizada", brl_compacto(resumo["Dotação atualizada"]), brl(resumo["Dotação atualizada"]))
    comum.kpi(c[2], "Empenhado", brl_compacto(resumo["Empenhado"]), brl(resumo["Empenhado"]),
              delta=f"{pct(resumo['% empenhado'], 1)} da dotação", cor_delta="off")
    comum.kpi(c[3], "Liquidado", brl_compacto(resumo["Liquidado"]), brl(resumo["Liquidado"]))
    comum.kpi(c[4], "Pago", brl_compacto(resumo["Pago"]), brl(resumo["Pago"]))

    periodo = df[df["mes"] <= mes]
    esquerda, direita = st.columns(2)
    with esquerda:
        comum.secao("Execução acumulada no exercício")
        mensal = periodo.groupby("mes")[["empenhado", "liquidado", "pago"]].sum()
        comum.colunas_mensais({"Empenhado": mensal["empenhado"], "Liquidado": mensal["liquidado"], "Pago": mensal["pago"]},
                              {"Empenhado": CORES["vermelho"], "Liquidado": CORES["azul"], "Pago": CORES["dourado"]},
                              acumulado=True, tipo="linha", chave="desp-acumulado")
    with direita:
        comum.secao("Por grupo de natureza da despesa")
        grupos = periodo.groupby("grupo")[["empenhado", "liquidado", "pago"]].sum().sort_values("empenhado")
        fig = go.Figure()
        for coluna, nome, cor in (("empenhado", "Empenhado", CORES["vermelho"]), ("liquidado", "Liquidado", CORES["azul"]),
                                  ("pago", "Pago", CORES["dourado"])):
            fig.add_bar(name=nome, y=grupos.index, x=grupos[coluna] / 1e6, orientation="h", marker=dict(color=cor),
                        customdata=[brl(v) for v in grupos[coluna]],
                        hovertemplate=f"%{{y}} · {nome}<br><b>%{{customdata}}</b><extra></extra>")
        fig.update_layout(barmode="group")
        fig.update_xaxes(title_text="R$ milhões")
        comum.mostrar(fig, 340, titulo_y=None, chave="desp-grupos")

    comum.secao("Despesa empenhada por função")
    comum.barras_horizontais(periodo, "funcao", "empenhado", n=15, chave="desp-funcao")

    comum.secao("Detalhamento da dotação e da execução")
    dimensao = st.segmented_control("Agrupar por", list(DIMENSOES), default="Função", key="desp-dim") or "Função"
    tabela = _resumo(df, mes, DIMENSOES[dimensao])
    busca = st.text_input("Filtrar", key="desp-busca", placeholder="código ou descrição")
    if busca:
        mascara = tabela.astype(str).apply(lambda col: col.str.contains(busca, case=False, na=False)).any(axis=1)
        tabela = tabela[mascara]
    comum.tabela(tabela, moeda=("Dotação inicial", "Dotação atualizada", "Empenhado", "Liquidado", "Pago"),
                 percentual=("% empenhado",), arquivo=f"despesas_{ano}_{dimensao.lower().replace(' ', '_')}", chave="desp-tabela")

    comum.secao("Alterações orçamentárias (decretos)", "Créditos suplementares, especiais, remanejamentos, transposições e transferências.")
    dec = dados.decretos(ano)
    if dec.empty:
        st.caption("Sem decretos no exercício.")
    else:
        dec = comum.filtrar_orgaos(dec[dec["mes"] <= mes])
        resumo_tipos = dec.groupby("tipo").agg(Decretos=("num_decreto", "count"), Valor=("vlr_aberto", "sum")).reset_index()
        c = st.columns([2, 3])
        with c[0]:
            comum.tabela(resumo_tipos.rename(columns={"tipo": "Tipo"}), moeda=("Valor",), chave="desp-dec-resumo")
        with c[1]:
            lista = dec[["num_decreto", "dat_ass_decreto", "tipo", "vlr_aberto", "leis", "data_lei", "orgao"]].sort_values("dat_ass_decreto")
            comum.tabela(lista.rename(columns={"num_decreto": "Decreto", "dat_ass_decreto": "Data", "tipo": "Tipo",
                                               "vlr_aberto": "Valor", "leis": "Lei(s)", "data_lei": "Data da lei", "orgao": "Órgão"}),
                         moeda=("Valor",), datas=("Data", "Data da lei"), arquivo=f"decretos_{ano}", chave="desp-dec-lista", altura=320)
    comum.rodape()
