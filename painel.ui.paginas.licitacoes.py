"""Aba Licitação (conjunto 'Licitação' do TCE-MG: licitações, dispensas, inexigibilidades e adesões)."""
from __future__ import annotations

import streamlit as st

from ... import dados
from ...config import CORES
from ...fontes import tce_sicom
from ...formatos import brl, brl_compacto, mes_ano, numero
from .. import comum


def pagina() -> None:
    ano, mes = comum.ano_selecionado(), comum.mes_selecionado()
    comum.cabecalho("Licitação", f"Processos licitatórios e contratações diretas informados ao SICOM até {mes_ano(ano, mes)}")
    lic = comum.filtrar_orgaos(comum.ate_mes(dados.licitacoes(ano)))
    disp = comum.filtrar_orgaos(comum.ate_mes(dados.dispensas(ano)))
    adesoes = comum.filtrar_orgaos(comum.ate_mes(tce_sicom.ler(ano, "licitacao", "regadesao")))
    if lic.empty and disp.empty:
        comum.aviso_sem_dados("Licitação")
        return
    aviso = tce_sicom.ler(ano, "licitacao", "licitacao").attrs.get("aviso")
    if aviso:
        st.warning(aviso, icon="⚠️")
    c = comum.colunas_kpi(4, "licitacoes-1")
    comum.kpi(c[0], "Licitações", numero(len(lic), 0))
    comum.kpi(c[1], "Valor homologado", brl_compacto(lic["valor_homologado"].sum() if "valor_homologado" in lic else 0))
    comum.kpi(c[2], "Contratações diretas", numero(len(disp), 0))
    comum.kpi(c[3], "Adesões a atas", numero(len(adesoes), 0))

    esquerda, direita = st.columns(2)
    with esquerda:
        comum.secao("Licitações por modalidade")
        if not lic.empty and "modalidade" in lic:
            resumo = lic.groupby("modalidade").agg(Processos=("seq_licitacao", "count"),
                                                    Homologado=("valor_homologado", "sum")).reset_index()
            comum.tabela(resumo.rename(columns={"modalidade": "Modalidade"}), moeda=("Homologado",), chave="lic-mod")
    with direita:
        comum.secao("Contratações diretas por tipo")
        if not disp.empty:
            resumo = disp.groupby("tipo").agg(Processos=("seq_dispensa", "count"), Valor=("valor_estimado", "sum")).reset_index()
            comum.tabela(resumo.rename(columns={"tipo": "Tipo"}), moeda=("Valor",), chave="disp-tipo")
            st.markdown("<div class='pv-nota'>Valor: soma de quantidade × preço dos fornecedores informados no processo.</div>",
                        unsafe_allow_html=True)

    comum.secao("Processos licitatórios")
    if not lic.empty and "objeto" in lic:
        busca = st.text_input("Filtrar por objeto ou número", key="lic-busca")
        lista = lic
        if busca:
            lista = lista[(lista["objeto"].fillna("") + " " + lista["num_processo"].fillna("")).str.contains(busca, case=False)]
        colunas = [c for c in ("num_processo", "num_ano_processo", "modalidade", "natureza_objeto", "objeto", "dat_abert_proc_adm",
                               "valor_homologado", "vencedores", "orgao") if c in lista.columns]
        comum.tabela(lista[colunas].rename(columns={
            "num_processo": "Processo", "num_ano_processo": "Ano", "modalidade": "Modalidade", "natureza_objeto": "Natureza",
            "objeto": "Objeto", "dat_abert_proc_adm": "Abertura", "valor_homologado": "Valor homologado",
            "vencedores": "Vencedores", "orgao": "Órgão"}), moeda=("Valor homologado",), datas=("Abertura",), altura=360,
            arquivo=f"licitacoes_{ano}", chave="lic-lista")

    comum.secao("Contratações diretas")
    if not disp.empty:
        lista = disp[["num_processo", "num_ano_processo", "tipo", "natureza_objeto", "objeto", "dat_abertura", "valor_estimado",
                      "fornecedores", "orgao"]]
        comum.tabela(lista.rename(columns={"num_processo": "Processo", "num_ano_processo": "Ano", "tipo": "Tipo",
                                           "natureza_objeto": "Natureza", "objeto": "Objeto", "dat_abertura": "Abertura",
                                           "valor_estimado": "Valor", "fornecedores": "Fornecedor(es)", "orgao": "Órgão"}),
                     moeda=("Valor",), datas=("Abertura",), altura=360, arquivo=f"dispensas_{ano}", chave="disp-lista")

    if not adesoes.empty:
        comum.secao("Adesões a atas")
        colunas = [c for c in ("num_processo", "num_ano_processo", "dsc_org_gerenciador", "dsc_objeto_adesao", "dat_ata_reg_preco",
                               "dat_validade") if c in adesoes.columns]
        comum.tabela(adesoes[colunas].rename(columns={"num_processo": "Processo", "num_ano_processo": "Ano",
                                                      "dsc_org_gerenciador": "Órgão gerenciador", "dsc_objeto_adesao": "Objeto",
                                                      "dat_ata_reg_preco": "Data da ata", "dat_validade": "Validade"}),
                     datas=("Data da ata", "Validade"), arquivo=f"adesoes_{ano}", chave="ades-lista")
    comum.rodape()
