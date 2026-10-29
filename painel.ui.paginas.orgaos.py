"""Aba Órgão (conjunto 'Órgão' do TCE-MG: órgãos, unidades, responsáveis e remessas)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from ... import dados, indicadores
from ...config import MESES
from ...formatos import mes_ano
from .. import comum


def pagina() -> None:
    ano = comum.ano_selecionado()
    comum.cabecalho("Órgão", "Órgãos, unidades orçamentárias, responsáveis e remessas do Acompanhamento Mensal")
    info = dados.orgaos(ano)
    if info["orgaos"].empty:
        comum.aviso_sem_dados("Órgão")
        return
    comum.secao("Órgãos do Município")
    comum.tabela(info["orgaos"][["cod_orgao", "nom_orgao", "tipo_orgao"]].rename(columns={
        "cod_orgao": "Código", "nom_orgao": "Órgão", "tipo_orgao": "Tipo"}), chave="org-orgaos")

    comum.secao("Remessas do SICOM (Acompanhamento Mensal)",
                "Situação informada no pacote 'Órgão' do portal; prazo de envio: último dia do mês subsequente (IN TCEMG 03/2015).")
    rem = indicadores.remessas_sicom(ano)
    if not rem.empty:
        rem = rem.assign(Mês=[MESES[m - 1] for m in rem["mes"]])
        comum.tabela(rem[["Mês", "tpo_remessa", "dsc_situacao", "prazo", "situacao_prazo"]].rename(columns={
            "tpo_remessa": "Módulo", "dsc_situacao": "Situação no TCE", "prazo": "Prazo", "situacao_prazo": "Avaliação"}),
            datas=("Prazo",), chave="org-remessas")

    comum.secao("Responsáveis")
    resp = info["responsaveis"]
    if not resp.empty:
        resp = resp.sort_values("mes").drop_duplicates(["cod_orgao", "num_documento_resp", "dsc_tipo_resp"], keep="last")
        resp["Órgão"] = resp["cod_orgao"].map(dict(zip(info["orgaos"]["cod_orgao"], info["orgaos"]["nom_orgao"])))
        hoje = pd.Timestamp.today()
        resp["Vigente"] = resp["dat_fim_vig"].isna() | (resp["dat_fim_vig"] >= hoje)
        so_vigentes = st.toggle("Mostrar apenas responsáveis vigentes", value=True, key="org-vigentes")
        if so_vigentes:
            resp = resp[resp["Vigente"]]
        comum.tabela(resp[["Órgão", "dsc_tipo_resp", "nom_pessoa_resp", "dsc_cargo_ordenador", "num_crc_contador", "dsc_email_resp",
                           "dat_inicio_vig", "dat_fim_vig"]].rename(columns={
            "dsc_tipo_resp": "Responsabilidade", "nom_pessoa_resp": "Nome", "dsc_cargo_ordenador": "Cargo",
            "num_crc_contador": "CRC", "dsc_email_resp": "E-mail", "dat_inicio_vig": "Início", "dat_fim_vig": "Fim"}),
            datas=("Início", "Fim"), arquivo=f"responsaveis_{ano}", chave="org-resp")

    comum.secao("Unidades orçamentárias")
    un = info["unidades"]
    if not un.empty:
        un = un.drop_duplicates(["cod_orgao", "cod_unidade", "cod_subunidade"], keep="last")
        comum.tabela(un[["cod_orgao", "cod_unidade", "dsc_unidade", "cod_subunidade", "dsc_subunidade"]].rename(columns={
            "cod_orgao": "Órgão", "cod_unidade": "Unidade", "dsc_unidade": "Descrição", "cod_subunidade": "Subunidade",
            "dsc_subunidade": "Descrição da subunidade"}), altura=360, chave="org-unidades")
    comum.rodape()
