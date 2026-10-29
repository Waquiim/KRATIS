"""Tabelas de domínio montadas a partir dos pacotes do SICOM (TCE-MG).

Todos os valores vêm dos arquivos publicados pelo TCE-MG; aqui só se renomeiam
colunas, separam-se códigos de descrições e somam-se movimentos mensais.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from .config import ORGAOS
from .fontes import tce_sicom

GRUPOS_DESPESA = {
    "3.1": "Pessoal e encargos sociais",
    "3.2": "Juros e encargos da dívida",
    "3.3": "Outras despesas correntes",
    "4.4": "Investimentos",
    "4.5": "Inversões financeiras",
    "4.6": "Amortização da dívida",
    "9.9": "Reserva de contingência",
}
CATEGORIAS_RECEITA = {
    "1": "Receitas correntes",
    "2": "Receitas de capital",
    "7": "Receitas correntes intraorçamentárias",
    "8": "Receitas de capital intraorçamentárias",
}


def _versao(ano: int, categoria: str) -> float:
    caminho = tce_sicom.caminho_zip(ano, categoria)
    return caminho.stat().st_mtime if caminho.exists() else 0.0


def separar(serie: pd.Series) -> tuple[pd.Series, pd.Series]:
    """'1.500.000 - RECURSOS ...' -> ('1.500.000', 'RECURSOS ...')."""
    partes = serie.fillna("").astype(str).str.split(" - ", n=1, expand=True)
    if partes.shape[1] == 1:
        partes[1] = ""
    return partes[0].str.strip(), partes[1].fillna("").str.strip()


def _orgao_nome(cod: pd.Series) -> pd.Series:
    return cod.map(ORGAOS).fillna("Órgão " + cod.astype(str))


def _fonte(df: pd.DataFrame, coluna: str, prefixo: str = "fonte") -> pd.DataFrame:
    cod, desc = separar(df[coluna])
    df[prefixo] = cod
    df[f"{prefixo}_desc"] = desc
    df[f"{prefixo}_exercicio"] = cod.str[:1]           # 1 = exercício corrente; 2 = exercícios anteriores
    df[f"{prefixo}_grupo"] = cod.str[2:5]              # ex.: 500, 540, 600
    return df


def _co(df: pd.DataFrame, coluna: str) -> pd.DataFrame:
    cod, desc = separar(df[coluna])
    df["co"] = cod.where(cod.str.match(r"^\d{4}$"), "")
    df["co_desc"] = desc
    return df


def _sem_cache(funcao):
    def chamar(ano: int, *args):
        return funcao(ano, *args).copy()
    chamar.__name__ = funcao.__name__
    chamar.__doc__ = funcao.__doc__
    return chamar


# ----------------------------------------------------------------------------- receitas

@lru_cache(maxsize=16)
def _receitas(ano: int, versao: float) -> pd.DataFrame:
    df = tce_sicom.ler(ano, "receita", "receita")
    if df.empty:
        return pd.DataFrame()
    saida = pd.DataFrame({"ano": df["ano"].astype(int), "mes": df["mes"].astype(int), "cod_orgao": df["cod_orgao"]})
    saida["orgao"] = _orgao_nome(saida["cod_orgao"])
    for origem, destino in (("dsc_cateconomica", "categoria"), ("dsc_origem", "origem"), ("dsc_especie", "especie"),
                            ("dsc_rubrica", "rubrica"), ("dsc_alinea", "alinea"), ("dsc_subalinea", "subalinea"),
                            ("dsc_tipo", "natureza")):
        cod, desc = separar(df[origem])
        saida[f"{destino}_cod"] = cod
        saida[destino] = desc
    saida["categoria_cod"] = saida["categoria_cod"].str[:1]
    saida = _fonte(saida.assign(_f=df["dsc_fonterecurso"].values), "_f").drop(columns="_f")
    saida = _co(saida.assign(_c=df["dsc_codorcamentario"].values), "_c").drop(columns="_c")
    saida["deducao"] = df["dsc_tipodeducao"].fillna("-").str.strip().ne("-").values
    saida["tipo_deducao"] = df["dsc_tipodeducao"].values
    saida["intra"] = saida["categoria_cod"].isin(["7", "8"])
    saida["previsao_inicial"] = df["vlr_previsaoinicial"].values
    saida["previsao_atualizada"] = df["vlr_previsaoatualizada"].values
    saida["realizado"] = df["vlr_realizadoateperiodo"].values
    return saida


receitas = _sem_cache(lambda ano: _receitas(ano, _versao(ano, "receita")))
receitas.__doc__ = "Receitas por natureza, fonte e mês (valores mensais; deduções negativas)."


# ----------------------------------------------------------------------------- despesas (dotação e execução)

@lru_cache(maxsize=16)
def _despesas(ano: int, versao: float) -> pd.DataFrame:
    df = tce_sicom.ler(ano, "despesa", "despesa")
    if df.empty:
        return pd.DataFrame()
    saida = pd.DataFrame({"ano": df["ano"].astype(int), "mes": df["mes"].astype(int), "cod_orgao": df["cod_orgao"],
                          "cod_unidade": df["cod_unidade"], "cod_subunidade": df["cod_subunidade"]})
    saida["orgao"] = _orgao_nome(saida["cod_orgao"])
    for origem, destino in (("dsc_funcao", "funcao"), ("dsc_subfuncao", "subfuncao"), ("dsc_programa", "programa"),
                            ("dsc_acao", "acao"), ("dsc_naturezadespesa", "natureza")):
        cod, desc = separar(df[origem])
        saida[f"{destino}_cod"] = cod
        saida[destino] = desc
    nat = saida["natureza_cod"]
    saida["categoria_cod"] = nat.str[:1]
    saida["grupo_cod"] = nat.str[:3]
    saida["grupo"] = saida["grupo_cod"].map(GRUPOS_DESPESA).fillna("Outros")
    saida["modalidade"] = nat.str[4:6]
    saida["elemento"] = nat.str[7:9]
    saida["intra"] = saida["modalidade"].eq("91")
    saida = _fonte(saida.assign(_f=df["dsc_fonterecurso"].values), "_f").drop(columns="_f")
    saida = _co(saida.assign(_c=df["dsc_cod_orcamentario"].values), "_c").drop(columns="_c")
    saida["dotacao_inicial"] = df["vlr_previsto"].values
    saida["acrescimo"] = df["vlr_acrescimo"].values
    saida["reducao"] = df["vlr_deducao"].values
    saida["dotacao_atualizada"] = saida["dotacao_inicial"] + saida["acrescimo"] - saida["reducao"]
    saida["empenhado"] = df["vlr_empenhado"].values
    saida["liquidado"] = df["vlr_liquidado"].values
    saida["pago"] = df["vlr_pago"].values
    saida["a_pagar_processado"] = df["vlr_rspprocessado"].values
    saida["a_liquidar"] = df["vlr_rspnprocessado"].values
    # A LOA fixa a dotação no nível de elemento (ex.: 3.3.90.39); a execução vem por subelemento.
    saida["dotacao_chave"] = (saida["cod_orgao"] + "|" + saida["cod_unidade"] + "|" + saida["cod_subunidade"] + "|"
                              + saida["funcao_cod"] + "|" + saida["subfuncao_cod"] + "|" + saida["programa_cod"] + "|"
                              + saida["acao_cod"] + "|" + nat.str[:9] + "|" + saida["fonte"])
    return saida


despesas = _sem_cache(lambda ano: _despesas(ano, _versao(ano, "despesa")))
despesas.__doc__ = "Despesa por dotação e mês: dotação, créditos adicionais, empenhado, liquidado e pago."


# ----------------------------------------------------------------------------- empenhos

@lru_cache(maxsize=8)
def _empenhos(ano: int, versao: float) -> pd.DataFrame:
    emp = tce_sicom.ler(ano, "empenho", "empenho")
    if emp.empty:
        return pd.DataFrame()
    credores = tce_sicom.ler(ano, "empenho", "credorEmpenho")[["seq_empenho", "num_doc_credor", "nom_credor"]]
    credores = credores.drop_duplicates("seq_empenho")
    fontes = tce_sicom.ler(ano, "empenho", "empenhoFonte")
    # O valor empenhado vem do detalhamento por fonte: o arquivo 'empenho' não registra todas as anulações.
    exec_fonte = fontes.assign(
        empenhado_fonte=fontes["vlr_empenho"] + fontes["vlr_reforco_emp"] - fontes["vlr_anulacao_emp"],
        anulado_fonte=fontes["vlr_anulacao_emp"],
        liquidado=fontes["vlr_liquidacao"] - fontes["vlr_anu_liquidacao"],
        pago=fontes["vlr_pagamento"] - fontes["vlr_anu_pagamento"],
    ).groupby("seq_empenho").agg(empenhado_fonte=("empenhado_fonte", "sum"), anulado_fonte=("anulado_fonte", "sum"),
                                 liquidado=("liquidado", "sum"), pago=("pago", "sum"),
                                 fonte=("dsc_fonte_recurso", "first"))
    saida = pd.DataFrame({
        "seq_empenho": emp["seq_empenho"], "ano": emp["ano"].astype(int), "mes": emp["mes"].astype(int),
        "cod_orgao": emp["cod_orgao"], "numero": emp["num_empenho"], "data": emp["dat_empenho"],
        "modalidade": separar(emp["dsc_modalidade"])[1], "historico": emp["dsc_empenho"],
        "funcao": separar(emp["dsc_funcao"])[1], "subfuncao": separar(emp["dsc_subfuncao"])[1],
        "natureza_cod": separar(emp["dsc_naturezadespesa"])[0], "natureza": separar(emp["dsc_naturezadespesa"])[1],
        "empenhado": emp["vlr_empenhado"] + emp["vlr_reforco"] - emp["vlr_anulempenho"],
        "valor_original": emp["vlr_empenhado"], "reforco": emp["vlr_reforco"], "anulado": emp["vlr_anulempenho"],
        "seq_contrato": emp["seq_contrato"], "seq_licitacao": emp["seq_licitacao"], "seq_dispensa": emp["seq_dispensa"],
        "dotacao": emp["dsc_dotacao"],
    })
    saida["orgao"] = _orgao_nome(saida["cod_orgao"])
    saida = saida.merge(credores, on="seq_empenho", how="left").merge(exec_fonte, on="seq_empenho", how="left")
    saida = saida.rename(columns={"num_doc_credor": "credor_doc", "nom_credor": "credor"})
    saida["fonte"] = separar(saida["fonte"])[0]
    for c in ("liquidado", "pago"):
        saida[c] = saida[c].fillna(0.0)
    tem_fonte = saida["empenhado_fonte"].notna()
    saida.loc[tem_fonte, "empenhado"] = saida.loc[tem_fonte, "empenhado_fonte"]
    saida.loc[tem_fonte, "anulado"] = saida.loc[tem_fonte, "anulado_fonte"]
    saida = saida.drop(columns=["empenhado_fonte", "anulado_fonte"])
    saida["origem_contratacao"] = np.select(
        [saida["seq_licitacao"].fillna("-1").ne("-1") & saida["seq_licitacao"].fillna("").ne(""),
         saida["seq_dispensa"].fillna("-1").ne("-1") & saida["seq_dispensa"].fillna("").ne("")],
        ["Licitação", "Dispensa/inexigibilidade"], default="Sem vínculo informado")
    return saida


empenhos = _sem_cache(lambda ano: _empenhos(ano, _versao(ano, "empenho")))
empenhos.__doc__ = "Empenhos do exercício com credor, fonte e execução (liquidado/pago)."


@lru_cache(maxsize=8)
def _restos_a_pagar(ano: int, versao: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    estoque = tce_sicom.ler(ano, "empenho", "rsp")
    mov = tce_sicom.ler(ano, "empenho", "movimentacaoRsp")
    if not estoque.empty:
        estoque = estoque.assign(orgao=_orgao_nome(estoque["cod_orgao"]))
    if not mov.empty:
        mov = mov.assign(orgao=_orgao_nome(mov["cod_orgao"]),
                         tipo_rp=separar(mov["dsc_tipo_rsp"])[1], movimento=separar(mov["dsc_tipo_movimentacao"])[1])
    return estoque, mov


def restos_a_pagar(ano: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    estoque, mov = _restos_a_pagar(ano, _versao(ano, "empenho"))
    return estoque.copy(), mov.copy()


# ----------------------------------------------------------------------------- alterações orçamentárias

def decretos(ano: int) -> pd.DataFrame:
    dec = tce_sicom.ler(ano, "despesa", "decretos")
    if dec.empty:
        return dec
    leis = tce_sicom.ler(ano, "despesa", "leisDecretos")
    leis = leis.groupby("seq_decreto_alt").agg(
        leis=("num_lei", lambda s: ", ".join(sorted({x for x in s if x}))),
        data_lei=("dat_lei", "min"), valor_lei=("vlr_aberto_lei", "sum")).reset_index()
    saida = dec.merge(leis, on="seq_decreto_alt", how="left")
    saida["tipo"] = separar(saida["dsc_tipo_decreto"])[1].str.replace(r"\s+", " ", regex=True)
    saida["tipo_cod"] = separar(saida["dsc_tipo_decreto"])[0]
    saida["orgao"] = _orgao_nome(saida["cod_orgao"])
    return saida


def alteracoes(ano: int) -> pd.DataFrame:
    alt = tce_sicom.ler(ano, "despesa", "altOrcamentaria")
    if alt.empty:
        return alt
    partes = alt["dsc_dotacao"].str.split(".")
    alt["fonte"] = partes.str[-3].fillna("") + "." + partes.str[-2].fillna("") + "." + partes.str[-1].fillna("")
    alt["valor"] = np.where(alt["dsc_tipo_alteracao"].eq("R"), -alt["vlr_acres_red"], alt["vlr_acres_red"])
    return alt


# ----------------------------------------------------------------------------- pessoal, saúde e educação

def pessoal(ano: int) -> pd.DataFrame:
    df = tce_sicom.ler(ano, "desp_pessoal", "despPessoal")
    if df.empty:
        return df
    for c in ("vlr_executivo", "vlr_legislativo", "vlr_municipio"):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    df["orgao"] = _orgao_nome(df["cod_orgao"])
    df["elemento"] = df["cod_nat_despesa"].str[:9]
    return df.rename(columns={"vlr_executivo": "executivo", "vlr_legislativo": "legislativo", "vlr_municipio": "municipio",
                              "cod_nat_despesa": "natureza_cod", "dsc_nat_despesa": "natureza"})


def _funcao_execucao(ano: int, categoria: str) -> pd.DataFrame:
    df = tce_sicom.ler(ano, categoria, categoria)
    if df.empty:
        return df
    saida = pd.DataFrame({"ano": df["ano"].astype(int), "mes": df["mes"].astype(int), "cod_orgao": df["cod_orgao"],
                          "empenho": df["num_empenho"], "data_empenho": df["dat_empenho"]})
    for origem, destino in (("dsc_subfuncao", "subfuncao"), ("dsc_programa", "programa"), ("dsc_acao", "acao"),
                            ("dsc_nat_despesa", "natureza")):
        cod, desc = separar(df[origem])
        saida[f"{destino}_cod"] = cod
        saida[destino] = desc
    saida["grupo_cod"] = saida["natureza_cod"].str[:3]
    saida["grupo"] = saida["grupo_cod"].map(GRUPOS_DESPESA).fillna("Outros")
    saida = _fonte(saida.assign(_f=df["dsc_fonte_recurso"].values), "_f").drop(columns="_f")
    saida = _co(saida.assign(_c=df["dsc_cod_orcamentario"].values), "_c").drop(columns="_c")
    saida["empenhado"] = (df["vlr_empenho"] + df["vlr_ref_empenho"] - df["vlr_anu_empenho"]).values
    saida["liquidado"] = (df["vlr_liquidado"] - df["vlr_anu_liquidado"]).values
    saida["pago"] = (df["vlr_pagamento"] - df["vlr_anu_pagamento"]).values
    saida["orgao"] = _orgao_nome(saida["cod_orgao"])
    return saida


def saude(ano: int) -> pd.DataFrame:
    """Despesas com ASPS custeadas com recursos próprios (fonte 1.500 + CO 1002), por empenho e mês."""
    return _funcao_execucao(ano, "saude")


def educacao(ano: int) -> pd.DataFrame:
    """Despesas com MDE custeadas com impostos (fonte 1.500 + CO 1001), por empenho e mês."""
    return _funcao_execucao(ano, "educacao")


# ----------------------------------------------------------------------------- licitações, contratos, frota, órgãos

def licitacoes(ano: int) -> pd.DataFrame:
    df = tce_sicom.ler(ano, "licitacao", "licitacao")
    if df.empty or "dsc_modalidade" not in df.columns:
        return pd.DataFrame(columns=["modalidade", "objeto", "valor_homologado"]).assign(aviso=df.attrs.get("aviso"))
    homolog = tce_sicom.ler(ano, "licitacao", "homologLicitacao")
    if not homolog.empty:
        homolog["valor"] = pd.to_numeric(homolog["num_quant_item"], errors="coerce").fillna(0) * homolog["vlr_unitario"]
        homolog["valor"] = np.where(homolog["vlr_global"] > 0, homolog["vlr_global"], homolog["valor"])
        valores = homolog.groupby("seq_licitacao").agg(valor_homologado=("valor", "sum"),
                                                       vencedores=("nom_vencedor", "nunique")).reset_index()
        df = df.merge(valores, on="seq_licitacao", how="left")
    else:
        df["valor_homologado"] = 0.0
        df["vencedores"] = 0
    df["modalidade"] = separar(df["dsc_modalidade"])[1]
    df["natureza_objeto"] = separar(df["dsc_nat_objeto"])[1]
    df["orgao"] = _orgao_nome(df["cod_orgao"])
    df["valor_homologado"] = df["valor_homologado"].fillna(0.0)
    return df.rename(columns={"dsc_objeto_licitacao": "objeto"})


def dispensas(ano: int) -> pd.DataFrame:
    df = tce_sicom.ler(ano, "licitacao", "dispensa")
    if df.empty:
        return df
    forn = tce_sicom.ler(ano, "licitacao", "fornDispensa")
    if not forn.empty:
        forn["valor"] = pd.to_numeric(forn["num_quant_item"], errors="coerce").fillna(0) * forn["vlr_item"]
        valores = forn.groupby("seq_dispensa").agg(valor_estimado=("valor", "sum"),
                                                   fornecedores=("dsc_nom_fornecedor", lambda s: ", ".join(sorted(set(s))[:3])),
                                                   fornecedor_doc=("num_doc_fornecedor", "first")).reset_index()
        df = df.merge(valores, on="seq_dispensa", how="left")
    else:
        df["valor_estimado"] = 0.0
        df["fornecedores"] = ""
        df["fornecedor_doc"] = ""
    df["tipo"] = separar(df["dsc_tipo_processo"])[1]
    df["natureza_objeto"] = separar(df["dsc_nat_objeto"])[1]
    df["orgao"] = _orgao_nome(df["cod_orgao"])
    df["valor_estimado"] = df["valor_estimado"].fillna(0.0)
    texto = (df["dsc_justificativa"].fillna("") + " " + df["dsc_razao"].fillna("")).str.upper()
    df["fundamento_valor"] = texto.str.contains(r"75\s*,?\s*(?:INCISO\s*)?I{1,2}\b|DISPENSA POR VALOR|PEQUENO VALOR", regex=True)
    return df.rename(columns={"dsc_objeto": "objeto"})


def contratos(ano: int) -> pd.DataFrame:
    df = tce_sicom.ler(ano, "contrato", "contratos")
    if df.empty:
        return df
    contratados = tce_sicom.ler(ano, "contrato", "contContrato")[["seq_contrato", "num_doc_credor", "dsc_nome_credor"]]
    df = df.merge(contratados.drop_duplicates("seq_contrato"), on="seq_contrato", how="left")
    aditivos = tce_sicom.ler(ano, "contrato", "termoContrato")
    if not aditivos.empty:
        resumo = aditivos.groupby("seq_contrato").agg(aditivos=("seq_termo_aditivo", "count"),
                                                      valor_aditivos=("vlr_termo_aditivo", "sum")).reset_index()
        df = df.merge(resumo, on="seq_contrato", how="left")
    df["aditivos"] = df.get("aditivos", 0).fillna(0).astype(int) if "aditivos" in df else 0
    df["valor_aditivos"] = df.get("valor_aditivos", 0.0).fillna(0.0) if "valor_aditivos" in df else 0.0
    df["orgao"] = _orgao_nome(df["cod_orgao"])
    df["natureza_objeto"] = separar(df["dsc_naturezaobjeto"])[1]
    df["origem"] = separar(df["dsc_decorrentelicitacao"])[1]
    return df.rename(columns={"dsc_objetocontrato": "objeto", "dsc_nome_credor": "contratado", "num_doc_credor": "contratado_doc"})


def frota(ano: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    veiculos = tce_sicom.ler(ano, "frota", "frota")
    gastos = tce_sicom.ler(ano, "frota", "gastoFrota")
    if not veiculos.empty:
        veiculos = veiculos.sort_values("mes").drop_duplicates("seq_veiculo", keep="last")
        veiculos["orgao"] = _orgao_nome(veiculos["cod_orgao"])
        veiculos["tipo"] = separar(veiculos["dsc_tipo_veiculo"])[1]
        veiculos["subtipo"] = separar(veiculos["dsc_sub_tipo_veiculo"])[1]
        veiculos["situacao"] = separar(veiculos["dsc_situacaoveiculo"])[1]
    if not gastos.empty:
        gastos["orgao"] = _orgao_nome(gastos["cod_orgao"])
        gastos["tipo_gasto"] = separar(gastos["dsc_tipo_gasto"])[1]
        gastos["quantidade"] = pd.to_numeric(gastos["num_quant_utilizada"], errors="coerce")
    return veiculos, gastos


def orgaos(ano: int) -> dict[str, pd.DataFrame]:
    return {
        "orgaos": tce_sicom.ler(ano, "orgao", "orgao"),
        "unidades": tce_sicom.ler(ano, "orgao", "orgaoUnidade"),
        "responsaveis": tce_sicom.ler(ano, "orgao", "orgaoResp"),
        "remessas": tce_sicom.remessas(ano),
    }


# ----------------------------------------------------------------------------- resumos

def ultimo_mes(ano: int) -> int:
    return tce_sicom.ultimo_mes_enviado(ano)


def resumo_receita(ano: int, ate_mes: int | None = None, orgaos: list[str] | None = None,
                   incluir_intra: bool = False) -> dict:
    df = receitas(ano)
    if df.empty:
        return {}
    if not incluir_intra:
        df = df[~df["intra"]]
    if orgaos:
        df = df[df["cod_orgao"].isin(orgaos)]
    previsao_inicial = df["previsao_inicial"].sum()
    previsao_atualizada = df["previsao_atualizada"].sum()
    if ate_mes:
        df = df[df["mes"] <= ate_mes]
    return {
        "previsao_inicial": previsao_inicial,
        "previsao_atualizada": previsao_atualizada,
        "realizada": df["realizado"].sum(),
        "correntes": df.loc[df["categoria_cod"] == "1", "realizado"].sum(),
        "capital": df.loc[df["categoria_cod"] == "2", "realizado"].sum(),
        "deducoes": df.loc[df["deducao"], "realizado"].sum(),
    }


def resumo_despesa(ano: int, ate_mes: int | None = None, orgaos: list[str] | None = None,
                   incluir_intra: bool = False) -> dict:
    df = despesas(ano)
    if df.empty:
        return {}
    if not incluir_intra:
        df = df[~df["intra"]]
    if orgaos:
        df = df[df["cod_orgao"].isin(orgaos)]
    dotacao_inicial = df["dotacao_inicial"].sum()
    if ate_mes:
        df = df[df["mes"] <= ate_mes]
    return {
        "dotacao_inicial": dotacao_inicial,
        "dotacao_atualizada": df["dotacao_atualizada"].sum() + (dotacao_inicial - df["dotacao_inicial"].sum()),
        "empenhado": df["empenhado"].sum(),
        "liquidado": df["liquidado"].sum(),
        "pago": df["pago"].sum(),
        "correntes_empenhado": df.loc[df["categoria_cod"] == "3", "empenhado"].sum(),
        "capital_empenhado": df.loc[df["categoria_cod"] == "4", "empenhado"].sum(),
    }
