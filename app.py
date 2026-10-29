"""Painel Contábil e Fiscal do Município de Viçosa/MG.

Execute com:  .venv/bin/python -m streamlit run app.py
Versão web (qualquer aparelho): .venv/bin/python ferramentas/gerar_versao_web.py
"""
import streamlit as st

from painel.config import EXERCICIO_ATUAL, LOGO, NAVEGADOR
from painel.fontes import tce_sicom
from painel.ui import comum, navegacao
from painel.ui.paginas import (atualizacao, comparativo, consistencia, contratos, criticas, despesas, educacao, empenhos,
                               licitacoes, orgaos, pessoal, receitas, saude, veiculos, visao_geral)

st.set_page_config(page_title="Painel Contábil · Viçosa/MG", page_icon=str(LOGO), layout="wide",
                   initial_sidebar_state="auto")
comum.estilos()
if NAVEGADOR:
    tce_sicom.instalar_pacote_embutido()

paginas = {
    "visao_geral": st.Page(visao_geral.pagina, title="Visão geral", icon=":material/dashboard:", url_path="visao-geral", default=True),
    "receitas": st.Page(receitas.pagina, title="Receitas", icon=":material/payments:", url_path="receitas"),
    "despesas": st.Page(despesas.pagina, title="Despesas", icon=":material/account_balance_wallet:", url_path="despesas"),
    "empenhos": st.Page(empenhos.pagina, title="Empenho", icon=":material/receipt_long:", url_path="empenho"),
    "pessoal": st.Page(pessoal.pagina, title="Despesa com Pessoal", icon=":material/badge:", url_path="pessoal"),
    "saude": st.Page(saude.pagina, title="Saúde", icon=":material/health_and_safety:", url_path="saude"),
    "educacao": st.Page(educacao.pagina, title="Educação", icon=":material/school:", url_path="educacao"),
    "licitacoes": st.Page(licitacoes.pagina, title="Licitação", icon=":material/gavel:", url_path="licitacao"),
    "contratos": st.Page(contratos.pagina, title="Contratos", icon=":material/contract:", url_path="contratos"),
    "veiculos": st.Page(veiculos.pagina, title="Veículos", icon=":material/directions_car:", url_path="veiculos"),
    "orgaos": st.Page(orgaos.pagina, title="Órgão", icon=":material/apartment:", url_path="orgao"),
    "comparativo": st.Page(comparativo.pagina, title="Comparativo 3 exercícios", icon=":material/compare_arrows:", url_path="comparativo"),
    "criticas": st.Page(criticas.pagina, title=f"Críticas {EXERCICIO_ATUAL}", icon=":material/rule:", url_path="criticas"),
    "consistencia": st.Page(consistencia.pagina, title="Consistência dos dados", icon=":material/fact_check:", url_path="consistencia"),
    "atualizacao": st.Page(atualizacao.pagina, title="Atualização de dados", icon=":material/sync:", url_path="atualizacao"),
}
navegacao.PAGINAS.update(paginas)

pagina = st.navigation({
    "Dados do SICOM (TCE-MG)": [paginas[k] for k in ("visao_geral", "receitas", "despesas", "empenhos", "pessoal", "saude",
                                                     "educacao", "licitacoes", "contratos", "veiculos", "orgaos")],
    "Análises": [paginas[k] for k in ("comparativo", "criticas", "consistencia")],
    "Sistema": [paginas["atualizacao"]],
})
comum.traduzir_menu(len(paginas), paginas["atualizacao"].url_path)
comum.filtros(mostrar_orgaos=pagina.url_path not in {"orgao", "atualizacao", "criticas", "consistencia", "pessoal"})
comum.atualizacao_automatica()
pagina.run()
