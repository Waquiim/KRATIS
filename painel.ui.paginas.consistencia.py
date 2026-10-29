"""Aba Consistência dos dados: confronto entre os conjuntos do próprio portal de dados abertos do TCE-MG."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from ... import consistencia
from .. import comum
from .visao_geral import versao_dados

CORES_SITUACAO = {"Consistente": "#E8F3E8", "Diferença pequena": "#FFF6D6", "Inconsistente": "#FBE9E9"}
ABAS = [
    ("Pessoal", "Despesa com Pessoal × Despesas (grupo 3.1)",
     "A folha do mês no conjunto 'Despesa com Pessoal' deve ser igual à despesa liquidada do grupo 3.1 em 'Despesas'."),
    ("Execução", "Despesas × Empenho",
     "Empenhado, liquidado e pago do mês em 'Despesas' devem coincidir com o detalhamento por fonte do conjunto 'Empenho'."),
    ("Educação (MDE)", "Educação × Despesas",
     "O conjunto 'Educação' deve coincidir com a despesa de 'Despesas' na fonte 1.500 com CO 1001."),
    ("Saúde (ASPS)", "Saúde × Despesas",
     "O conjunto 'Saúde' deve coincidir com a despesa de 'Despesas' na fonte 1.500 com CO 1002."),
    ("Alterações orçamentárias", "Decretos × alterações",
     "O valor aberto por decreto deve igualar os acréscimos por dotação; remanejamentos e transferências anulam o mesmo valor."),
    ("Remessas", "Remessas × dados", "Meses com remessa enviada devem ter dados publicados, e vice-versa."),
]


# cache_resource: guarda o objeto sem serializar (o pandas da versão web não desserializa datas)
@st.cache_resource(ttl=3600, show_spinner="Confrontando os conjuntos do portal…")
def _todas(ano: int, versao: str) -> pd.DataFrame:
    return consistencia.todas(ano)


def _mostrar(df: pd.DataFrame, chave: str, arquivo: str) -> None:
    if df.empty:
        st.caption("Nenhuma diferença encontrada ou sem dados para comparar.")
        return
    colunas = ["Item", "Período", "Conjunto A", "Valor A", "Conjunto B", "Valor B", "Diferença (B − A)", "Diferença %",
               "Situação", "Observação"]
    tabela = df[colunas]
    estilo = tabela.style.apply(lambda linha: [f"background-color: {CORES_SITUACAO.get(linha['Situação'], '')}"
                                               if col == "Situação" else "" for col in linha.index], axis=1)
    estilo = estilo.format({"Valor A": "{:,.2f}", "Valor B": "{:,.2f}", "Diferença (B − A)": "{:,.2f}", "Diferença %": "{:,.2f}"},
                           na_rep="–", thousands=".", decimal=",")
    st.dataframe(estilo, width="stretch", hide_index=True, key=chave)
    csv = tabela.to_csv(sep=";", decimal=",", index=False).encode("utf-8-sig")
    st.download_button("⬇ Baixar CSV", csv, file_name=f"{arquivo}.csv", mime="text/csv", key=f"baixar-{chave}")


def pagina() -> None:
    ano = comum.ano_selecionado()
    comum.cabecalho("Consistência dos dados", "Confronto entre os conjuntos publicados no portal de dados abertos do TCE-MG")
    todas = _todas(ano, versao_dados())
    if todas.empty:
        comum.aviso_sem_dados()
        return
    st.markdown(
        "<div class='pv-nota'>O mesmo fato contábil aparece em mais de um conjunto do portal (por exemplo, a folha em "
        "'Despesa com Pessoal' e no grupo 3.1 de 'Despesas'). Diferenças indicam remessa incompleta, retificação parcial "
        "ou erro de classificação no SICOM.</div>", unsafe_allow_html=True)
    colunas = st.columns(3)
    for coluna, situacao in zip(colunas, ["Inconsistente", "Diferença pequena", "Consistente"]):
        coluna.metric(situacao, int((todas["Situação"] == situacao).sum()), border=True)
    resumo = todas.pivot_table(index="Tema", columns="Situação", values="Item", aggfunc="count", fill_value=0).reset_index()
    st.dataframe(resumo, width="stretch", hide_index=True, key="cons-resumo")

    somente = st.toggle("Mostrar apenas diferenças", value=True, key="cons-somente")
    abas = st.tabs([rotulo for _, rotulo, _ in ABAS])
    for aba, (tema, rotulo, regra) in zip(abas, ABAS):
        with aba:
            st.markdown(f"<div class='pv-nota'>{regra}</div>", unsafe_allow_html=True)
            parte = todas[todas["Tema"].eq(tema)]
            if somente:
                parte = parte[parte["Situação"].ne("Consistente")]
            _mostrar(parte, f"cons-{tema}", f"consistencia_{ano}_{tema.split(' ')[0].lower()}")
    comum.rodape()
