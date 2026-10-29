"""Aba Contratos (conjunto 'Contratos' do TCE-MG)."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from ... import dados
from ...config import CORES
from ...formatos import brl, brl_compacto, mes_ano, numero
from .. import comum


def pagina() -> None:
    ano, mes = comum.ano_selecionado(), comum.mes_selecionado()
    comum.cabecalho("Contratos", f"Contratos, aditivos e vigências informados ao SICOM até {mes_ano(ano, mes)}")
    ct = comum.filtrar_orgaos(comum.ate_mes(dados.contratos(ano)))
    if ct.empty:
        comum.aviso_sem_dados("Contratos")
        return
    hoje = pd.Timestamp(date.today())
    vigentes = ct[(ct["dat_iniciovigencia"] <= hoje) & (ct["dat_fimvigencia"] >= hoje)]
    vencendo = ct[(ct["dat_fimvigencia"] >= hoje) & (ct["dat_fimvigencia"] <= hoje + pd.Timedelta(days=60))]
    c = comum.colunas_kpi(4, "contratos-1")
    comum.kpi(c[0], "Contratos cadastrados", numero(len(ct), 0))
    comum.kpi(c[1], "Valor contratado", brl_compacto(ct["vlr_contrato"].sum()), brl(ct["vlr_contrato"].sum()))
    comum.kpi(c[2], "Termos aditivos", numero(int(ct["aditivos"].sum()), 0), f"Valor dos aditivos: {brl(ct['valor_aditivos'].sum())}")
    comum.kpi(c[3], "Vigentes hoje", numero(len(vigentes), 0), f"{len(vencendo)} vencem nos próximos 60 dias")

    esquerda, direita = st.columns(2)
    with esquerda:
        comum.secao("Maiores contratados")
        comum.barras_horizontais(ct.assign(contratado=ct["contratado"].fillna("(não informado)")), "contratado", "vlr_contrato",
                                 cor=CORES["azul"], chave="ct-contratados")
    with direita:
        comum.secao("Por natureza do objeto e origem")
        resumo = ct.groupby(["natureza_objeto", "origem"]).agg(Contratos=("seq_contrato", "count"),
                                                                Valor=("vlr_contrato", "sum")).reset_index()
        comum.tabela(resumo.rename(columns={"natureza_objeto": "Natureza do objeto", "origem": "Origem"}), moeda=("Valor",),
                     chave="ct-natureza")

    if not vencendo.empty:
        comum.secao("Contratos que vencem nos próximos 60 dias")
        comum.tabela(vencendo[["num_contrato", "num_ano_contrato", "contratado", "objeto", "dat_fimvigencia", "vlr_contrato"]].rename(
            columns={"num_contrato": "Contrato", "num_ano_contrato": "Ano", "contratado": "Contratado", "objeto": "Objeto",
                     "dat_fimvigencia": "Fim da vigência", "vlr_contrato": "Valor"}), moeda=("Valor",), datas=("Fim da vigência",),
            chave="ct-vencendo")

    comum.secao("Contratos do exercício")
    busca = st.text_input("Filtrar por contratado, CNPJ ou objeto", key="ct-busca")
    lista = ct
    if busca:
        alvo = lista["contratado"].fillna("") + " " + lista["contratado_doc"].fillna("") + " " + lista["objeto"].fillna("")
        lista = lista[alvo.str.contains(busca, case=False)]
    comum.tabela(lista[["num_contrato", "num_ano_contrato", "dat_assinatura", "contratado", "contratado_doc", "objeto",
                        "natureza_objeto", "origem", "dat_iniciovigencia", "dat_fimvigencia", "vlr_contrato", "aditivos",
                        "valor_aditivos", "orgao"]].rename(columns={
        "num_contrato": "Contrato", "num_ano_contrato": "Ano", "dat_assinatura": "Assinatura", "contratado": "Contratado",
        "contratado_doc": "CPF/CNPJ", "objeto": "Objeto", "natureza_objeto": "Natureza", "origem": "Origem",
        "dat_iniciovigencia": "Início", "dat_fimvigencia": "Fim", "vlr_contrato": "Valor", "aditivos": "Aditivos",
        "valor_aditivos": "Valor dos aditivos", "orgao": "Órgão"}),
        moeda=("Valor", "Valor dos aditivos"), datas=("Assinatura", "Início", "Fim"), altura=420, arquivo=f"contratos_{ano}",
        chave="ct-lista")
    comum.rodape()
