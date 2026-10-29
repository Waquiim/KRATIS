"""Consistência interna dos dados do SICOM: confronto entre conjuntos do próprio portal do TCE-MG.

O mesmo fato contábil aparece em mais de um conjunto (ex.: a folha em 'Despesa com Pessoal' e no grupo 3.1
de 'Despesas'). Diferenças indicam remessa incompleta, retificação parcial ou erro de classificação.
"""
from __future__ import annotations

import pandas as pd

from . import dados
from .config import MESES, carregar_parametros
from .fontes import tce_sicom


def _tolerancia() -> float:
    return float(carregar_parametros().get("tolerancia_consistencia_valor", 1.0))


def _linha(tema: str, item: str, periodo: str, conjunto_a: str, valor_a: float, conjunto_b: str, valor_b: float,
           observacao: str = "") -> dict:
    diferenca = valor_b - valor_a
    relativo = abs(diferenca) / abs(valor_a) * 100 if valor_a else (0.0 if not diferenca else 100.0)
    if abs(diferenca) <= _tolerancia():
        situacao = "Consistente"
    elif relativo <= 0.5:
        situacao = "Diferença pequena"
    else:
        situacao = "Inconsistente"
    return {"Tema": tema, "Item": item, "Período": periodo, "Conjunto A": conjunto_a, "Valor A": valor_a,
            "Conjunto B": conjunto_b, "Valor B": valor_b, "Diferença (B − A)": diferenca,
            "Diferença %": None if not valor_a else diferenca / abs(valor_a) * 100, "Situação": situacao,
            "Observação": observacao}


def _mensal(ano: int, a: pd.Series, b: pd.Series, tema: str, item: str, conj_a: str, conj_b: str) -> list[dict]:
    meses = sorted(set(a.index) | set(b.index))
    return [_linha(tema, item, f"{MESES[int(m) - 1]}/{ano}", conj_a, float(a.get(m, 0.0)), conj_b, float(b.get(m, 0.0)))
            for m in meses]


def pessoal_x_despesas(ano: int) -> pd.DataFrame:
    p, d = dados.pessoal(ano), dados.despesas(ano)
    if p.empty or d.empty:
        return pd.DataFrame()
    return pd.DataFrame(_mensal(ano, p.groupby("mes")["municipio"].sum(),
                                d[d["grupo_cod"].eq("3.1")].groupby("mes")["liquidado"].sum(),
                                "Pessoal", "Despesa com pessoal do mês (liquidada)", "Despesa com Pessoal",
                                "Despesas – grupo 3.1"))


def empenhos_x_despesas(ano: int) -> pd.DataFrame:
    f, d = tce_sicom.ler(ano, "empenho", "empenhoFonte"), dados.despesas(ano)
    if f.empty or d.empty:
        return pd.DataFrame()
    f = f.assign(empenhado=f["vlr_empenho"] + f["vlr_reforco_emp"] - f["vlr_anulacao_emp"],
                 liquidado=f["vlr_liquidacao"] - f["vlr_anu_liquidacao"], pago=f["vlr_pagamento"] - f["vlr_anu_pagamento"])
    linhas = []
    for campo, rotulo in (("empenhado", "Empenhado"), ("liquidado", "Liquidado"), ("pago", "Pago")):
        linhas += _mensal(ano, d.groupby("mes")[campo].sum(), f.groupby("mes")[campo].sum(), "Execução",
                          f"{rotulo} no mês", "Despesas", "Empenho (por fonte)")
    return pd.DataFrame(linhas)


def funcoes_x_despesas(ano: int) -> pd.DataFrame:
    d = dados.despesas(ano)
    if d.empty:
        return pd.DataFrame()
    linhas = []
    for conjunto, co, nome in (("educacao", "1001", "Educação (MDE)"), ("saude", "1002", "Saúde (ASPS)")):
        e = getattr(dados, conjunto)(ano)
        if e.empty:
            continue
        base = d[d["fonte"].eq("1.500.000") & d["co"].eq(co)]
        linhas += _mensal(ano, base.groupby("mes")["liquidado"].sum(), e.groupby("mes")["liquidado"].sum(), nome,
                          "Liquidado com impostos no mês", f"Despesas – fonte 1.500, CO {co}", nome.split(" ")[0])
    return pd.DataFrame(linhas)


def decretos_x_alteracoes(ano: int) -> pd.DataFrame:
    dec, alt = dados.decretos(ano), dados.alteracoes(ano)
    if dec.empty or alt.empty:
        return pd.DataFrame()
    acresc = alt[alt["dsc_tipo_alteracao"].eq("A")].groupby("seq_decreto_alt")["vlr_acres_red"].sum()
    reduc = alt[alt["dsc_tipo_alteracao"].eq("R")].groupby("seq_decreto_alt")["vlr_acres_red"].sum()
    linhas = []
    for _, r in dec.sort_values("dat_ass_decreto").iterrows():
        a, red = float(acresc.get(r["seq_decreto_alt"], 0.0)), float(reduc.get(r["seq_decreto_alt"], 0.0))
        periodo = f"Decreto {r['num_decreto']} ({r['dat_ass_decreto']:%d/%m/%Y})"
        linhas.append(_linha("Alterações orçamentárias", f"{r['tipo'].capitalize()}: valor aberto x acréscimos", periodo,
                             "Decretos (valor aberto)", float(r["vlr_aberto"]), "Alterações (acréscimos)", a))
        if r["tipo_cod"] in ("09", "10", "11", "05"):
            linhas.append(_linha("Alterações orçamentárias", "Movimentação: acréscimos x reduções", periodo,
                                 "Alterações (reduções)", red, "Alterações (acréscimos)", a,
                                 "Remanejamento, transposição, transferência e troca de fonte devem anular o mesmo valor que acrescentam"))
    return pd.DataFrame(linhas)


def remessas_x_dados(ano: int) -> pd.DataFrame:
    rem, r = tce_sicom.remessas(ano), dados.receitas(ano)
    if rem.empty:
        return pd.DataFrame()
    meses_com_dados = set(r["mes"].unique()) if not r.empty else set()
    linhas = []
    for _, x in rem.iterrows():
        enviado = str(x["dsc_situacao"]).upper().startswith("ENVIADO")
        tem = int(x["mes"]) in meses_com_dados
        if enviado != tem:
            linhas.append({"Tema": "Remessas", "Item": "Situação da remessa x dados publicados",
                           "Período": f"{MESES[int(x['mes']) - 1]}/{ano}", "Conjunto A": "Órgão (remessas)",
                           "Valor A": 1.0 if enviado else 0.0, "Conjunto B": "Receitas (meses com dados)",
                           "Valor B": 1.0 if tem else 0.0, "Diferença (B − A)": None, "Diferença %": None,
                           "Situação": "Inconsistente",
                           "Observação": "Mês marcado como enviado sem dados publicados" if enviado else "Dados publicados de mês marcado como não enviado"})
    return pd.DataFrame(linhas)


def todas(ano: int) -> pd.DataFrame:
    partes = [pessoal_x_despesas(ano), empenhos_x_despesas(ano), funcoes_x_despesas(ano), decretos_x_alteracoes(ano),
              remessas_x_dados(ano)]
    partes = [p for p in partes if not p.empty]
    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()
