"""Aba Empenho (conjunto 'Empenho' do portal de dados abertos do TCE-MG)."""
from __future__ import annotations

import streamlit as st

from ... import dados
from ...config import CORES
from ...formatos import brl, brl_compacto, mes_ano, numero
from .. import comum


def pagina() -> None:
    ano, mes = comum.ano_selecionado(), comum.mes_selecionado()
    comum.cabecalho("Empenho", f"Empenhos, credores e restos a pagar informados ao SICOM até {mes_ano(ano, mes)} – {comum.legenda_orgaos()}")
    emp = comum.filtrar_orgaos(comum.ate_mes(dados.empenhos(ano)))
    if emp.empty:
        comum.aviso_sem_dados("Empenho")
        return
    c = comum.colunas_kpi(4, "empenhos-1")
    comum.kpi(c[0], "Empenhos emitidos", numero(len(emp), 0))
    comum.kpi(c[1], "Valor empenhado", brl_compacto(emp["empenhado"].sum()), "Valor original + reforços − anulações")
    comum.kpi(c[2], "Credores distintos", numero(emp["credor_doc"].nunique(), 0))
    comum.kpi(c[3], "Anulações", brl_compacto(emp["anulado"].sum()), brl(emp["anulado"].sum()))

    esquerda, direita = st.columns(2)
    with esquerda:
        sem_credor = emp["credor"].isna()
        comum.secao("Maiores credores", f"Valor empenhado no período. Não inclui {numero(int(sem_credor.sum()), 0)} empenho(s) sem "
                                        f"credor informado ao SICOM (ex.: folha de pagamento), que somam {brl(emp.loc[sem_credor, 'empenhado'].sum())}.")
        comum.barras_horizontais(emp[~sem_credor], "credor", "empenhado", cor=CORES["azul"], n=15, chave="emp-credores")
    with direita:
        comum.secao("Por modalidade de empenho e origem da contratação")
        mod = emp.groupby("modalidade").agg(Empenhos=("numero", "count"), Valor=("empenhado", "sum")).reset_index()
        comum.tabela(mod.rename(columns={"modalidade": "Modalidade"}), moeda=("Valor",), chave="emp-mod")
        orig = emp.groupby("origem_contratacao").agg(Empenhos=("numero", "count"), Valor=("empenhado", "sum")).reset_index()
        comum.tabela(orig.rename(columns={"origem_contratacao": "Vínculo informado"}), moeda=("Valor",), chave="emp-orig")

    comum.secao("Consulta de empenhos")
    filtros = st.columns([3, 2, 2])
    busca = filtros[0].text_input("Credor, CPF/CNPJ ou histórico", key="emp-busca")
    funcoes = filtros[1].multiselect("Função", sorted(emp["funcao"].dropna().unique()), key="emp-funcao")
    valor_min = filtros[2].number_input("Valor mínimo (R$)", min_value=0.0, value=0.0, step=1000.0, key="emp-min")
    lista = emp
    if busca:
        alvo = (lista["credor"].fillna("") + " " + lista["credor_doc"].fillna("") + " " + lista["historico"].fillna(""))
        lista = lista[alvo.str.contains(busca, case=False, na=False)]
    if funcoes:
        lista = lista[lista["funcao"].isin(funcoes)]
    if valor_min:
        lista = lista[lista["empenhado"] >= valor_min]
    exibir = lista.sort_values("data", ascending=False)[["numero", "data", "orgao", "credor", "credor_doc", "historico", "funcao",
                                                          "natureza", "modalidade", "fonte", "empenhado", "liquidado", "pago"]]
    st.caption(f"{numero(len(exibir), 0)} empenho(s) · {brl(exibir['empenhado'].sum())}")
    comum.tabela(exibir.rename(columns={"numero": "Nº", "data": "Data", "orgao": "Órgão", "credor": "Credor", "credor_doc": "CPF/CNPJ",
                                        "historico": "Histórico", "funcao": "Função", "natureza": "Elemento",
                                        "modalidade": "Modalidade", "fonte": "Fonte", "empenhado": "Empenhado",
                                        "liquidado": "Liquidado", "pago": "Pago"}),
                 moeda=("Empenhado", "Liquidado", "Pago"), datas=("Data",), altura=420, arquivo=f"empenhos_{ano}", chave="emp-lista")

    comum.secao("Restos a pagar", "Saldo de empenhos de exercícios anteriores e movimentações no exercício.")
    estoque, mov = dados.restos_a_pagar(ano)
    if not estoque.empty:
        estoque = comum.filtrar_orgaos(estoque)
        inicial = estoque.drop_duplicates("seq_rsp")
        c = comum.colunas_kpi(3, "empenhos-2")
        comum.kpi(c[0], "RP processados", brl_compacto(inicial["vlr_saldo_ant_proc"].sum()))
        comum.kpi(c[1], "RP não processados", brl_compacto(inicial["vlr_saldo_ant_nao_proc"].sum()))
        if not mov.empty:
            canc = comum.filtrar_orgaos(mov[mov["movimento"].str.upper().str.contains("CANCELAMENTO", na=False)])
            comum.kpi(c[2], "RP cancelados", brl_compacto(canc["vlr_movimentacao"].sum()))
        por_ano = inicial.groupby("num_ano_emp_origem")[["vlr_saldo_ant_proc", "vlr_saldo_ant_nao_proc"]].sum().reset_index()
        comum.tabela(por_ano.rename(columns={"num_ano_emp_origem": "Exercício de origem", "vlr_saldo_ant_proc": "Processados",
                                             "vlr_saldo_ant_nao_proc": "Não processados"}),
                     moeda=("Processados", "Não processados"), chave="emp-rp-ano")
    if not mov.empty:
        mov = comum.filtrar_orgaos(comum.ate_mes(mov))
        resumo = mov.groupby(["tipo_rp", "movimento"]).agg(Movimentos=("seq_mov_rsp", "count"),
                                                           Valor=("vlr_movimentacao", "sum")).reset_index()
        comum.tabela(resumo.rename(columns={"tipo_rp": "Tipo de RP", "movimento": "Movimentação"}), moeda=("Valor",), chave="emp-rp-mov")
        with st.expander("Movimentações detalhadas de restos a pagar"):
            comum.tabela(mov[["num_emp_origem", "num_ano_emp_origem", "dsc_dotacao_origem", "tipo_rp", "movimento", "dat_movimentacao",
                              "vlr_movimentacao", "dsc_ato_cancelamento", "dsc_justificativa"]].rename(columns={
                "num_emp_origem": "Empenho", "num_ano_emp_origem": "Ano", "dsc_dotacao_origem": "Dotação", "tipo_rp": "Tipo",
                "movimento": "Movimentação", "dat_movimentacao": "Data", "vlr_movimentacao": "Valor",
                "dsc_ato_cancelamento": "Ato", "dsc_justificativa": "Justificativa"}),
                moeda=("Valor",), datas=("Data",), arquivo=f"restos_a_pagar_mov_{ano}", chave="emp-rp-det")
    comum.rodape()
