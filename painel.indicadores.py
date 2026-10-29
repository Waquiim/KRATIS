"""Indicadores fiscais apurados com os dados do SICOM segundo as metodologias oficiais.

Fonte única: pacotes do SICOM do portal de dados abertos do TCE-MG.
Referências: Manual de Demonstrativos Fiscais (MDF/STN), LRF (LC 101/2000), CF/88,
LC 141/2012, Lei 14.113/2020, Lei 14.133/2021, IN TCEMG 03/2015 e Consulta TCE-MG
nº 1.160.617 (art. 167-A). Cada função devolve os componentes do cálculo para que
a tela mostre a memória de cálculo, e não apenas o percentual.
"""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

from . import dados
from .config import LIMITES, carregar_parametros
from .fontes import tce_sicom

IMPOSTOS = [("IPTU", "1.1.1.2.50"), ("ITBI", "1.1.1.2.53"), ("IRRF", "1.1.1.3.03"), ("ISS", "1.1.1.4.51")]
TODOS = {"MDE", "ASPS", "29A"}
TRANSFERENCIAS = [
    ("Cota-parte FPM (art. 159, I, b)", "1.7.1.1.51.1", TODOS),
    ("Cota-parte FPM – parcelas extras de 1% (art. 159, I, d, e, f)", "1.7.1.1.51.2", {"MDE", "29A"}),
    ("Cota-parte ITR", "1.7.1.1.52", TODOS),
    ("IOF-Ouro", "1.7.1.1.53", TODOS),
    ("Cota-parte ICMS", "1.7.2.1.50", TODOS),
    ("Cota-parte IPVA", "1.7.2.1.51", TODOS),
    ("Cota-parte IPI-Exportação", "1.7.2.1.52", TODOS),
    ("Cota-parte CIDE-Combustíveis", "1.7.2.1.53", {"29A"}),
]
FONTES_FUNDEB = ("540", "541", "542", "543", "544", "545", "546")
FONTES_RPPS = ("800", "801", "802")


def _ate(df: pd.DataFrame, ate_mes: int | None) -> pd.DataFrame:
    return df if not ate_mes or df.empty else df[df["mes"] <= ate_mes]


def janela(ano: int, mes: int) -> list[int]:
    """Períodos AAAAMM dos 12 meses que terminam em ano/mes."""
    saida = []
    a, m = ano, mes
    for _ in range(12):
        saida.append(a * 100 + m)
        m -= 1
        if m == 0:
            a, m = a - 1, 12
    return sorted(saida)


def _com_periodo(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    return df.assign(per=df["ano"].astype(int) * 100 + df["mes"].astype(int))


def _receitas_anos(anos) -> pd.DataFrame:
    partes = [dados.receitas(a) for a in anos]
    partes = [p for p in partes if not p.empty]
    return _com_periodo(pd.concat(partes, ignore_index=True)) if partes else pd.DataFrame()


def _despesas_anos(anos) -> pd.DataFrame:
    partes = [dados.despesas(a) for a in anos]
    partes = [p for p in partes if not p.empty]
    return _com_periodo(pd.concat(partes, ignore_index=True)) if partes else pd.DataFrame()


def _pct(numerador: float | None, denominador: float | None) -> float | None:
    if numerador is None or not denominador:
        return None
    return numerador / denominador * 100


def meses_com_dados(ano: int) -> list[int]:
    r = dados.receitas(ano)
    return sorted(r["mes"].unique().tolist()) if not r.empty else []


# ----------------------------------------------------------------------------- bases de cálculo

def base_vinculacao(ano: int, ate_mes: int | None = None, finalidade: str = "MDE") -> dict:
    """Receita de impostos e transferências constitucionais (valores brutos, antes da dedução do FUNDEB)."""
    r = dados.receitas(ano)
    if r.empty:
        return {"total": None, "itens": pd.DataFrame(columns=["Item", "Grupo", "Valor"])}
    r = _ate(r[~r["deducao"]], ate_mes)
    linhas = []
    if finalidade == "29A":
        trib = r[r["natureza_cod"].str.startswith("1.1")]
        linhas.append({"Item": "Receita tributária (impostos, taxas e contribuições de melhoria)",
                       "Grupo": "Receita tributária", "Valor": trib["realizado"].sum()})
    else:
        for nome, codigo in IMPOSTOS:
            linhas.append({"Item": nome, "Grupo": "Impostos municipais",
                           "Valor": r.loc[r["natureza_cod"].str.startswith(codigo), "realizado"].sum()})
    for nome, codigo, usos in TRANSFERENCIAS:
        if finalidade in usos:
            linhas.append({"Item": nome, "Grupo": "Transferências constitucionais",
                           "Valor": r.loc[r["natureza_cod"].str.startswith(codigo), "realizado"].sum()})
    itens = pd.DataFrame(linhas)
    return {"total": float(itens["Valor"].sum()), "itens": itens}


def contribuicao_fundeb(ano: int, ate_mes: int | None = None) -> float:
    r = _ate(dados.receitas(ano), ate_mes)
    if r.empty:
        return 0.0
    filtro = r["deducao"] & r["tipo_deducao"].str.contains("FUNDEB", case=False, na=False)
    return float(-r.loc[filtro, "realizado"].sum())


# ----------------------------------------------------------------------------- educação e saúde

def mde(ano: int, ate_mes: int | None = None) -> dict:
    """Aplicação em MDE (CF art. 212): contribuição ao FUNDEB + despesas com impostos (fonte 1.500, CO 1001)."""
    base = base_vinculacao(ano, ate_mes, "MDE")
    contribuicao = contribuicao_fundeb(ano, ate_mes)
    ed = _ate(dados.educacao(ano), ate_mes)
    liquidado = float(ed["liquidado"].sum()) if not ed.empty else 0.0
    empenhado = float(ed["empenhado"].sum()) if not ed.empty else 0.0
    return {
        "base": base["total"], "itens_base": base["itens"], "contribuicao_fundeb": contribuicao,
        "despesas_liquidadas": liquidado, "despesas_empenhadas": empenhado,
        "aplicado_liquidado": contribuicao + liquidado, "aplicado_empenhado": contribuicao + empenhado,
        "percentual_liquidado": _pct(contribuicao + liquidado, base["total"]),
        "percentual_empenhado": _pct(contribuicao + empenhado, base["total"]),
        "minimo": LIMITES["mde_minimo"],
        "valor_minimo": (base["total"] or 0) * LIMITES["mde_minimo"] / 100,
    }


def asps(ano: int, ate_mes: int | None = None) -> dict:
    """Aplicação em ASPS (LC 141/2012 art. 7º): despesas com fonte 1.500 e CO 1002."""
    base = base_vinculacao(ano, ate_mes, "ASPS")
    sa = _ate(dados.saude(ano), ate_mes)
    liquidado = float(sa["liquidado"].sum()) if not sa.empty else 0.0
    empenhado = float(sa["empenhado"].sum()) if not sa.empty else 0.0
    return {
        "base": base["total"], "itens_base": base["itens"],
        "despesas_liquidadas": liquidado, "despesas_empenhadas": empenhado,
        "percentual_liquidado": _pct(liquidado, base["total"]),
        "percentual_empenhado": _pct(empenhado, base["total"]),
        "minimo": LIMITES["asps_minimo"],
        "valor_minimo": (base["total"] or 0) * LIMITES["asps_minimo"] / 100,
    }


def fundeb(ano: int, ate_mes: int | None = None) -> dict:
    """Receitas do FUNDEB (fontes 540–546, inclusive rendimentos) e aplicação na remuneração (CO 1070)."""
    r = _ate(dados.receitas(ano), ate_mes)
    d = _ate(dados.despesas(ano), ate_mes)
    if r.empty or d.empty:
        return {}
    rec = r[~r["deducao"] & r["fonte_grupo"].isin(FONTES_FUNDEB) & r["fonte_exercicio"].eq("1")]
    desp = d[d["fonte_grupo"].isin(FONTES_FUNDEB) & d["fonte_exercicio"].eq("1")]
    receita = float(rec["realizado"].sum())
    remuneracao = desp[desp["co"].eq("1070")]
    return {
        "receita": receita,
        "despesa_empenhada": float(desp["empenhado"].sum()),
        "despesa_liquidada": float(desp["liquidado"].sum()),
        "remuneracao_liquidada": float(remuneracao["liquidado"].sum()),
        "remuneracao_empenhada": float(remuneracao["empenhado"].sum()),
        "percentual_remuneracao": _pct(float(remuneracao["liquidado"].sum()), receita),
        "nao_aplicado": receita - float(desp["empenhado"].sum()),
        "percentual_nao_aplicado": _pct(receita - float(desp["empenhado"].sum()), receita),
    }


def fundeb_saldo_anterior(ano: int) -> dict:
    """Saldo do FUNDEB não aplicado no exercício anterior (receitas − despesas empenhadas, SICOM),
    que deve ser aplicado até o fim do 1º quadrimestre (Lei 14.113/2020, art. 25, §3º)."""
    anterior = fundeb(ano - 1)
    saldo = anterior.get("nao_aplicado") if anterior else None
    d = dados.despesas(ano)
    aplicado = 0.0
    if not d.empty:
        anteriores = d[d["fonte_grupo"].isin(FONTES_FUNDEB) & d["fonte_exercicio"].eq("2") & (d["mes"] <= 4)]
        aplicado = float(anteriores["empenhado"].sum())
    return {"saldo": saldo, "percentual_nao_aplicado": anterior.get("percentual_nao_aplicado") if anterior else None,
            "aplicado_1o_quadrimestre": aplicado}


# ----------------------------------------------------------------------------- receita corrente líquida

def rcl(ano: int, mes: int) -> dict:
    """RCL dos 12 meses encerrados em ano/mes (LRF art. 2º, IV; MDF – RREO Anexo 3)."""
    periodos = janela(ano, mes)
    r = _receitas_anos({p // 100 for p in periodos})
    if r.empty:
        return {"completo": False, "faltantes": periodos}
    w = r[r["per"].isin(periodos) & r["categoria_cod"].eq("1")]
    disponiveis = set(w["per"].unique())
    faltantes = [p for p in periodos if p not in disponiveis]
    bruta = w[~w["deducao"]]

    def por_mes(mascara) -> pd.Series:
        return bruta[mascara].groupby("per")["realizado"].sum().reindex(periodos, fill_value=0.0)

    tabela = pd.DataFrame({
        "Receitas correntes": bruta.groupby("per")["realizado"].sum().reindex(periodos, fill_value=0.0),
        "Contribuição do servidor ao RPPS": por_mes(bruta["natureza_cod"].str.startswith("1.2.1.5.01")),
        "Compensação financeira entre regimes": por_mes(bruta["natureza_cod"].str.startswith("1.9.9.9.03")),
        "Rendimentos de recursos previdenciários": por_mes(bruta["natureza_cod"].str.startswith("1.3.2") & bruta["fonte_grupo"].isin(FONTES_RPPS)),
        "Dedução para formação do FUNDEB": (-w[w["deducao"]].groupby("per")["realizado"].sum()).reindex(periodos, fill_value=0.0),
        "Emendas individuais (CO 3110)": por_mes(bruta["co"].eq("3110")),
        "Emendas de bancada (CO 3120)": por_mes(bruta["co"].eq("3120")),
    })
    tabela["RCL"] = (tabela["Receitas correntes"] - tabela["Contribuição do servidor ao RPPS"]
                     - tabela["Compensação financeira entre regimes"] - tabela["Rendimentos de recursos previdenciários"]
                     - tabela["Dedução para formação do FUNDEB"])
    totais = tabela.sum()
    return {
        "periodos": periodos, "completo": not faltantes, "faltantes": faltantes, "mensal": tabela,
        "receitas_correntes": totais["Receitas correntes"],
        "deducoes": totais[["Contribuição do servidor ao RPPS", "Compensação financeira entre regimes",
                            "Rendimentos de recursos previdenciários", "Dedução para formação do FUNDEB"]].sum(),
        "rcl": totais["RCL"],
        "emendas_individuais": totais["Emendas individuais (CO 3110)"],
        "emendas_bancada": totais["Emendas de bancada (CO 3120)"],
        "rcl_ajustada_endividamento": totais["RCL"] - totais["Emendas individuais (CO 3110)"],
        "rcl_ajustada_pessoal": totais["RCL"] - totais["Emendas individuais (CO 3110)"] - totais["Emendas de bancada (CO 3120)"],
    }


# ----------------------------------------------------------------------------- despesa com pessoal

def pessoal_12m(ano: int, mes: int) -> dict:
    """Despesa com pessoal (LRF arts. 18–20) dos 12 meses encerrados em ano/mes.

    Bruta: conjunto 'Despesa com Pessoal' do TCE-MG (executivo/legislativo por natureza).
    Exclusões (LRF art. 19 §1º): estimadas pela execução liquidada no SICOM."""
    periodos = janela(ano, mes)
    partes = [dados.pessoal(a) for a in {p // 100 for p in periodos}]
    partes = [p for p in partes if not p.empty]
    if not partes:
        return {"completo": False}
    p = _com_periodo(pd.concat(partes, ignore_index=True))
    p = p[p["per"].isin(periodos)]
    faltantes = [x for x in periodos if x not in set(p["per"])]
    mensal = p.groupby("per")[["executivo", "legislativo", "municipio"]].sum().reindex(periodos, fill_value=0.0)

    d = _despesas_anos({x // 100 for x in periodos})
    exclusoes = pd.DataFrame(columns=["Exclusão (LRF art. 19 §1º)", "Executivo", "Legislativo"])
    if not d.empty:
        d = d[d["per"].isin(periodos) & d["grupo_cod"].eq("3.1")]
        regras = [
            ("Indenizações por demissão e incentivos à demissão voluntária (elemento 94)", d["elemento"].eq("94")),
            ("Decorrentes de decisão judicial – sentenças (elemento 91)", d["elemento"].eq("91")),
            ("Despesas de exercícios anteriores (elemento 92)", d["elemento"].eq("92")),
            ("Inativos e pensionistas custeados com recursos vinculados ao RPPS",
             d["elemento"].isin(["01", "03"]) & d["fonte_grupo"].isin(FONTES_RPPS)),
        ]
        linhas = []
        for rotulo, mascara in regras:
            sel = d[mascara]
            linhas.append({"Exclusão (LRF art. 19 §1º)": rotulo,
                           "Executivo": float(sel.loc[sel["cod_orgao"] != "01", "liquidado"].sum()),
                           "Legislativo": float(sel.loc[sel["cod_orgao"] == "01", "liquidado"].sum())})
        exclusoes = pd.DataFrame(linhas)
    base = rcl(ano, mes)
    bruta_exec, bruta_leg = float(mensal["executivo"].sum()), float(mensal["legislativo"].sum())
    exc_exec = float(exclusoes["Executivo"].sum()) if not exclusoes.empty else 0.0
    exc_leg = float(exclusoes["Legislativo"].sum()) if not exclusoes.empty else 0.0
    rcl_aj = base.get("rcl_ajustada_pessoal")
    return {
        "periodos": periodos, "completo": not faltantes and base.get("completo", False), "faltantes": faltantes,
        "mensal": mensal, "exclusoes": exclusoes,
        "bruta_executivo": bruta_exec, "bruta_legislativo": bruta_leg,
        "liquida_executivo": bruta_exec - exc_exec, "liquida_legislativo": bruta_leg - exc_leg,
        "rcl_ajustada": rcl_aj, "rcl": base.get("rcl"),
        "percentual_executivo": _pct(bruta_exec - exc_exec, rcl_aj),
        "percentual_legislativo": _pct(bruta_leg - exc_leg, rcl_aj),
        "percentual_municipio": _pct(bruta_exec - exc_exec + bruta_leg - exc_leg, rcl_aj),
    }


# ----------------------------------------------------------------------------- art. 167-A

def dc_rc(ano: int, mes: int) -> dict:
    """Relação despesas correntes / receitas correntes em 12 meses (CF art. 167-A).

    Metodologia TCE-MG (Consulta nº 1.160.617, de 11/12/2024): despesas correntes empenhadas,
    excluídas as custeadas por créditos abertos com superávit financeiro do exercício anterior
    (fontes de exercícios anteriores, prefixo 2). Receitas correntes realizadas, líquidas das
    deduções. Intraorçamentárias excluídas dos dois lados."""
    periodos = janela(ano, mes)
    anos = {p // 100 for p in periodos}
    d = _despesas_anos(anos)
    r = _receitas_anos(anos)
    if d.empty or r.empty:
        return {"completo": False}
    d = d[d["per"].isin(periodos) & d["categoria_cod"].eq("3") & ~d["intra"]]
    r = r[r["per"].isin(periodos) & r["categoria_cod"].eq("1")]
    faltantes = [p for p in periodos if p not in set(r["per"]) or p not in set(d["per"])]
    dc_total = float(d["empenhado"].sum())
    dc_superavit = float(d.loc[d["fonte_exercicio"].eq("2"), "empenhado"].sum())
    rc = float(r["realizado"].sum())
    return {
        "periodos": periodos, "completo": not faltantes, "faltantes": faltantes,
        "despesas_correntes": dc_total, "despesas_superavit": dc_superavit,
        "despesas_consideradas": dc_total - dc_superavit, "receitas_correntes": rc,
        "percentual": _pct(dc_total - dc_superavit, rc),
        "percentual_sem_exclusao": _pct(dc_total, rc),
    }


def dc_rc_serie() -> pd.DataFrame:
    """Série mensal da relação DC/RC (12 meses móveis) com todos os meses disponíveis."""
    anos = sorted({a for a in range(2000, 2100) if tce_sicom.caminho_zip(a, "receita").exists()})
    if not anos:
        return pd.DataFrame()
    d = _despesas_anos(anos)
    r = _receitas_anos(anos)
    dc = d[d["categoria_cod"].eq("3") & ~d["intra"]]
    dcm = dc.groupby("per")["empenhado"].sum()
    dcs = dc[dc["fonte_exercicio"].eq("2")].groupby("per")["empenhado"].sum()
    rcm = r[r["categoria_cod"].eq("1")].groupby("per")["realizado"].sum()
    todos = sorted(set(rcm.index) | set(dcm.index))
    serie = pd.DataFrame(index=todos)
    serie["dc"] = dcm.reindex(todos, fill_value=0.0)
    serie["dc_superavit"] = dcs.reindex(todos, fill_value=0.0)
    serie["rc"] = rcm.reindex(todos, fill_value=0.0)
    janela12 = serie.rolling(12).sum()
    janela12["percentual"] = (janela12["dc"] - janela12["dc_superavit"]) / janela12["rc"] * 100
    janela12["percentual_sem_exclusao"] = janela12["dc"] / janela12["rc"] * 100
    janela12 = janela12.dropna()
    janela12["data"] = [date(p // 100, p % 100, 1) for p in janela12.index]
    return janela12.reset_index(names="per")


# ----------------------------------------------------------------------------- Câmara (art. 29-A)

def percentual_29a(populacao: int | None) -> float:
    if not populacao or populacao <= 100_000:
        return 7.0
    if populacao <= 300_000:
        return 6.0
    if populacao <= 500_000:
        return 5.0
    if populacao <= 3_000_000:
        return 4.5
    if populacao <= 8_000_000:
        return 4.0
    return 3.5


def camara(ano: int) -> dict:
    """Limite do total da despesa do Legislativo (CF art. 29-A) e folha da Câmara (§1º)."""
    base = base_vinculacao(ano - 1, None, "29A")
    populacao = int(carregar_parametros().get("populacao") or 0) or None
    percentual = percentual_29a(populacao)
    limite = (base["total"] or 0) * percentual / 100
    d = dados.despesas(ano)
    if d.empty or not base["total"]:
        return {}
    c = d[d["cod_orgao"].eq("01")]
    inativos = c["elemento"].isin(["01", "03"]) & c["grupo_cod"].eq("3.1")
    ultimo = dados.ultimo_mes(ano) or int(c["mes"].max())
    liquidado = float(c.loc[~inativos, "liquidado"].sum())
    folha_mask = c["grupo_cod"].eq("3.1") & ~c["elemento"].isin(["01", "03", "13"]) & ~c["intra"]
    folha = float(c.loc[folha_mask, "liquidado"].sum())
    dotacao = float(c.loc[~inativos, "dotacao_atualizada"].sum())
    # Projeção pela despesa liquidada: os empenhos globais/estimativos se concentram no início do ano.
    projecao = liquidado / ultimo * 12 if ultimo else None
    return {
        "base": base["total"], "itens_base": base["itens"], "populacao": populacao, "percentual_limite": percentual,
        "limite": limite, "dotacao_inicial": float(c.loc[~inativos, "dotacao_inicial"].sum()), "dotacao_atualizada": dotacao,
        "empenhado": float(c.loc[~inativos, "empenhado"].sum()), "liquidado": liquidado, "ultimo_mes": ultimo,
        "projecao_anual": projecao,
        "percentual_dotacao": _pct(dotacao, base["total"]),
        "percentual_projecao": _pct(projecao, base["total"]),
        "folha_liquidada": folha,
        "percentual_folha_dotacao": _pct(folha / ultimo * 12 if ultimo else None, dotacao),
    }


# ----------------------------------------------------------------------------- orçamento

def creditos_adicionais(ano: int) -> dict:
    dec = dados.decretos(ano)
    d = dados.despesas(ano)
    if dec.empty or d.empty:
        return {}
    dotacao_inicial = float(d["dotacao_inicial"].sum())
    resumo = dec.groupby("tipo").agg(Decretos=("num_decreto", "count"), Valor=("vlr_aberto", "sum")).reset_index()
    parametros = carregar_parametros()
    sup = dec[dec["tipo_cod"].eq("01")]
    lei_loa = str(parametros.get("lei_loa_numero") or "").strip()
    if not lei_loa and not sup.empty:
        contagem = sup["leis"].str.split(", ").explode().value_counts()
        lei_loa = contagem.index[0] if not contagem.empty else ""
    especiais = dec[dec["tipo_cod"].eq("02")].copy()
    especiais["sem_lei_especifica"] = especiais["leis"].fillna("").eq("") | especiais["leis"].fillna("").eq(lei_loa)
    lei_posterior = dec[dec["data_lei"].notna() & (dec["data_lei"] > dec["dat_ass_decreto"])]
    movimentacoes = dec[dec["tipo_cod"].isin(["09", "10", "11"])]
    return {
        "dotacao_inicial": dotacao_inicial, "resumo": resumo, "decretos": dec, "lei_loa": lei_loa,
        "suplementares": float(sup["vlr_aberto"].sum()),
        "percentual_suplementado": _pct(float(sup["vlr_aberto"].sum()), dotacao_inicial),
        "especiais_sem_lei": especiais[especiais["sem_lei_especifica"]],
        "decretos_antes_da_lei": lei_posterior,
        "movimentacoes": movimentacoes,
        "limite_loa": parametros.get("limite_suplementacao_loa_pct"),
    }


def dotacoes_excedidas(ano: int, ate_mes: int | None = None, por_fonte: bool = True) -> pd.DataFrame:
    """Dotações em que a despesa empenhada supera o crédito autorizado (CF art. 167, II).

    por_fonte=False soma todas as fontes da mesma dotação (órgão, unidade, funcional-programática e
    elemento): o excesso que persiste nessa visão não se explica por classificação de fonte."""
    d = _ate(dados.despesas(ano), ate_mes)
    if d.empty:
        return pd.DataFrame()
    chave = d["dotacao_chave"] if por_fonte else d["dotacao_chave"].str.rsplit("|", n=1).str[0]
    g = d.assign(chave=chave).groupby("chave").agg(
        orgao=("orgao", "first"), funcao=("funcao", "first"), acao=("acao", "first"), natureza_cod=("natureza_cod", "first"),
        natureza=("natureza", "first"), fonte=("fonte", lambda s: ", ".join(sorted(set(s)))), dotacao=("dotacao_atualizada", "sum"),
        empenhado=("empenhado", "sum")).reset_index().rename(columns={"chave": "dotacao_chave"})
    g["natureza_cod"] = g["natureza_cod"].str[:9]
    g["excesso"] = g["empenhado"] - g["dotacao"]
    return g[g["excesso"] > 0.01].sort_values("excesso", ascending=False)


def execucao_por_fonte(ano: int, ate_mes: int | None = None) -> pd.DataFrame:
    r = _ate(dados.receitas(ano), ate_mes)
    d = _ate(dados.despesas(ano), ate_mes)
    if r.empty or d.empty:
        return pd.DataFrame()
    rec = r[r["fonte_exercicio"].eq("1")].groupby(["fonte", "fonte_desc"])["realizado"].sum()
    desp = d[d["fonte_exercicio"].eq("1")].groupby(["fonte", "fonte_desc"])[["empenhado", "liquidado"]].sum()
    tabela = pd.concat([rec, desp], axis=1).fillna(0.0).reset_index()
    tabela["resultado"] = tabela["realizado"] - tabela["empenhado"]
    return tabela.sort_values("resultado")


def realizacao_receita(ano: int, ate_mes: int) -> dict:
    """Arrecadação até o mês comparada ao esperado pela sazonalidade do exercício anterior (LRF art. 9º).

    Calculada separadamente para receitas correntes e de capital (exceto intraorçamentárias)."""
    atual, anterior = dados.receitas(ano), dados.receitas(ano - 1)
    if atual.empty or anterior.empty:
        return {}
    atual, anterior = atual[~atual["intra"]], anterior[~anterior["intra"]]
    saida = {}
    for categoria, nome in (("1", "correntes"), ("2", "capital")):
        a = atual[atual["categoria_cod"].eq(categoria)]
        b = anterior[anterior["categoria_cod"].eq(categoria)]
        total_ant = float(b["realizado"].sum())
        proporcao = float(b.loc[b["mes"] <= ate_mes, "realizado"].sum()) / total_ant if total_ant else ate_mes / 12
        previsao = float(a["previsao_atualizada"].sum())
        realizado = float(a.loc[a["mes"] <= ate_mes, "realizado"].sum())
        esperado = previsao * proporcao
        saida[nome] = {"realizado": realizado, "previsao_atualizada": previsao, "proporcao_sazonal": proporcao,
                       "esperado": esperado, "percentual": _pct(realizado, esperado),
                       "percentual_da_previsao": _pct(realizado, previsao)}
    return saida


# ----------------------------------------------------------------------------- prazos e remessas

def _fim_mes(ano: int, mes: int) -> date:
    return date(ano, mes, calendar.monthrange(ano, mes)[1])


def remessas_sicom(ano: int) -> pd.DataFrame:
    """Remessas do AM (prazo: último dia do mês subsequente – IN TCEMG 03/2015)."""
    df = tce_sicom.remessas(ano)
    if df.empty:
        return df
    carga = tce_sicom.data_publicacao_tce(ano)
    referencia = carga.date() if carga else date.today()
    df = df.copy()
    df["prazo"] = [_fim_mes(ano + (m == 12), 1 if m == 12 else m + 1) for m in df["mes"].astype(int)]
    df["vencido_na_carga"] = df["prazo"] < referencia
    df["referencia"] = referencia
    df["situacao_prazo"] = np.where(df["dsc_situacao"].str.upper().str.startswith("ENVIADO"), "Enviado",
                                    np.where(df["vencido_na_carga"], "Não enviado após o prazo", "Ainda no prazo"))
    return df


# ----------------------------------------------------------------------------- qualidade dos dados

def anomalias_mensais(ano: int) -> pd.DataFrame:
    """Meses com valor muito abaixo da mediana do exercício (indício de remessa incompleta)."""
    series = {}
    p = dados.pessoal(ano)
    if not p.empty:
        series["Despesa com pessoal (conjunto do TCE-MG)"] = p.groupby("mes")["municipio"].sum()
    r = dados.receitas(ano)
    if not r.empty:
        series["Receitas correntes"] = r[r["categoria_cod"].eq("1") & ~r["deducao"]].groupby("mes")["realizado"].sum()
    d = dados.despesas(ano)
    if not d.empty:
        series["Despesa liquidada"] = d[~d["intra"]].groupby("mes")["liquidado"].sum()
    linhas = []
    for nome, serie in series.items():
        if len(serie) < 4:
            continue
        for mes, valor in serie.items():
            outros = serie.drop(mes)
            mediana = float(outros.median())
            if mediana > 0 and valor < 0.5 * mediana:
                linhas.append({"Série": nome, "Mês": int(mes), "Valor": float(valor), "Mediana dos demais meses": mediana,
                               "Proporção": valor / mediana * 100})
    return pd.DataFrame(linhas)


# ----------------------------------------------------------------------------- licitações e restos a pagar

def dispensas_por_valor(ano: int) -> pd.DataFrame:
    df = dados.dispensas(ano)
    if df.empty:
        return df
    limites = carregar_parametros().get("dispensa_limites", {}).get(str(ano), {})
    df = df[df["tipo"].str.upper().str.startswith("DISPENSA")].copy()
    eh_obra = df["natureza_objeto"].str.upper().str.contains("OBRA|ENGENHARIA", regex=True)
    df["limite"] = np.where(eh_obra, limites.get("obras", np.nan), limites.get("outros", np.nan))
    df["acima_do_limite"] = df["fundamento_valor"] & (df["valor_estimado"] > df["limite"])
    return df


def possivel_fracionamento(ano: int) -> pd.DataFrame:
    df = dispensas_por_valor(ano)
    if df.empty:
        return df
    df = df[df["fundamento_valor"] & df["fornecedor_doc"].fillna("").ne("")]
    g = df.groupby(["fornecedor_doc", "natureza_objeto"]).agg(
        fornecedor=("fornecedores", "first"), processos=("seq_dispensa", "nunique"),
        valor=("valor_estimado", "sum"), limite=("limite", "first")).reset_index()
    return g[(g["processos"] >= 2) & (g["valor"] > g["limite"])]


def rp_cancelamentos(ano: int) -> pd.DataFrame:
    _, mov = dados.restos_a_pagar(ano)
    if mov.empty:
        return mov
    return mov[mov["movimento"].str.upper().str.contains("CANCELAMENTO", na=False)]
