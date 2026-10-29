"""Visão geral do exercício."""
from __future__ import annotations

import streamlit as st

from ... import criticas, dados, indicadores
from ...config import CORES, LIMITES, SEVERIDADES
from ...formatos import brl, brl_compacto, mes_ano, pct
from .. import comum, navegacao


# cache_resource: guarda o objeto sem serializar (o pandas da versão web não desserializa datas)
@st.cache_resource(ttl=3600, show_spinner="Aplicando as verificações…")
def _criticas(ano: int, versao: str) -> list[dict]:
    return [c.__dict__ | {"ordem": c.ordem} for c in criticas.gerar(ano)]


def versao_dados() -> str:
    """Chave de cache que muda quando qualquer fonte é atualizada."""
    from ... import estado
    from ...fontes import tce_sicom
    from ...config import ARQ_PARAMETROS
    marcas = [str(p.stat().st_mtime) for p in sorted(tce_sicom.BRUTOS_TCE.glob("SICOM.*.zip"))]
    marcas.append(str(ARQ_PARAMETROS.stat().st_mtime) if ARQ_PARAMETROS.exists() else "")
    est = estado.ler()
    marcas += [str(v.get("ultima_atualizacao")) for v in est.values() if isinstance(v, dict)]
    return "|".join(marcas)


def pagina() -> None:
    ano, mes = comum.ano_selecionado(), comum.mes_selecionado()
    comum.cabecalho("Visão geral", f"Execução orçamentária e indicadores fiscais até {mes_ano(ano, mes)} – {comum.legenda_orgaos()}")
    orgaos = comum.orgaos_selecionados() or None
    # Execução total do orçamento: os indicadores desta linha incluem as intraorçamentárias.
    rec = dados.resumo_receita(ano, mes, orgaos, incluir_intra=True)
    desp = dados.resumo_despesa(ano, mes, orgaos, incluir_intra=True)
    if not rec or not desp:
        comum.aviso_sem_dados()
        return

    c = comum.colunas_kpi(5, "visao_geral-1")
    comum.kpi(c[0], "Receita arrecadada", brl_compacto(rec["realizada"]),
              f"Receita realizada líquida das deduções, incluindo intraorçamentárias. Previsão atualizada: {brl(rec['previsao_atualizada'])}.",
              delta=f"{pct(rec['realizada'] / rec['previsao_atualizada'] * 100 if rec['previsao_atualizada'] else None, 1)} da previsão",
              cor_delta="off")
    comum.kpi(c[1], "Despesa empenhada", brl_compacto(desp["empenhado"]),
              f"Inclui intraorçamentárias. Dotação atualizada: {brl(desp['dotacao_atualizada'])}.",
              delta=f"{pct(desp['empenhado'] / desp['dotacao_atualizada'] * 100 if desp['dotacao_atualizada'] else None, 1)} da dotação",
              cor_delta="off")
    comum.kpi(c[2], "Despesa liquidada", brl_compacto(desp["liquidado"]), "Inclui intraorçamentárias.")
    comum.kpi(c[3], "Despesa paga", brl_compacto(desp["pago"]), "Inclui intraorçamentárias.")
    saldo = rec["realizada"] - desp["liquidado"]
    comum.kpi(c[4], "Resultado (rec. − liquid.)", brl_compacto(saldo),
              "Receita arrecadada − despesa liquidada, ambas com intraorçamentárias. Resultado intermediário: a despesa "
              "empenhada inclui empenhos globais e estimativos do ano inteiro.",
              delta="superávit" if saldo >= 0 else "déficit", cor_delta="normal" if saldo >= 0 else "inverse")

    comum.secao("Indicadores fiscais", "Percentuais do exercício (metodologia oficial). Detalhes e memória de cálculo na aba Críticas.")
    c = comum.colunas_kpi(5, "visao_geral-2")
    serie = indicadores.dc_rc_serie()
    atual = serie[serie["per"] // 100 == ano] if not serie.empty else serie
    if not atual.empty:
        ult = atual.iloc[-1]
        bimestres = atual[atual["bimestre"]]
        maximo = bimestres["percentual"].max() if not bimestres.empty else ult["percentual"]
        comum.kpi(c[0], "DC/RC (art. 167-A)", pct(ult["percentual"]),
                  "Art. 167-A da CF, 12 meses, metodologia TCE-MG (Consulta nº 1.160.617 e IN nº 07/2025): despesas "
                  "correntes liquidadas + RPNP de dezembro, sem as custeadas com superávit, ÷ receitas correntes "
                  "líquidas; com intraorçamentárias. Alerta 85%; limite 95%. Máximo entre os bimestres do ano.",
                  delta=f"máx. {pct(maximo, 1)} no ano", cor_delta="off")
    est = indicadores.pessoal_12m(ano, mes)
    comum.kpi(c[1], "Pessoal – Executivo", pct(est.get("percentual_executivo")),
              "Despesa líquida com pessoal em 12 meses ÷ RCL ajustada, apuradas com o SICOM. Limite 54%, prudencial 51,3%.")
    m = indicadores.mde(ano, mes)
    comum.kpi(c[2], "Educação (MDE)", pct(m["percentual_liquidado"]), "Despesas liquidadas, dados do SICOM. Mínimo 25% no ano.")
    a = indicadores.asps(ano, mes)
    comum.kpi(c[3], "Saúde (ASPS)", pct(a["percentual_liquidado"]), "Estimativa com dados do SICOM (despesas liquidadas). Mínimo 15% no ano.")
    f = indicadores.fundeb(ano, mes)
    comum.kpi(c[4], "FUNDEB 70%", pct(f.get("percentual_remuneracao")),
              "Despesas com profissionais da educação (CO 1070) ÷ receitas do FUNDEB. Mínimo 70% no ano.")

    esquerda, direita = st.columns([3, 2])
    with esquerda:
        comum.secao("Receita arrecadada e despesa liquidada por mês")
        r = comum.filtrar_orgaos(comum.ate_mes(dados.receitas(ano)))
        d = comum.filtrar_orgaos(comum.ate_mes(dados.despesas(ano)))
        comum.colunas_mensais(
            {"Receita arrecadada": r[~r["intra"]].groupby("mes")["realizado"].sum(),
             "Despesa liquidada": d[~d["intra"]].groupby("mes")["liquidado"].sum()},
            {"Receita arrecadada": CORES["azul"], "Despesa liquidada": CORES["vermelho"]}, chave="vg-mensal")
    with direita:
        comum.secao(f"Críticas {ano} por severidade")
        lista = _criticas(ano, versao_dados())
        contagem = {s: sum(1 for x in lista if x["severidade"] == s) for s in SEVERIDADES}
        cols = st.columns(3)
        for i, sev in enumerate(["Crítico", "Alto", "Médio"]):
            s = SEVERIDADES[sev]
            cols[i].markdown(f"<div class='pv-cartao-sev' style='border-color:{s['cor']}55;background:{s['fundo']}'>"
                             f"<div class='n' style='color:{s['cor']}'>{contagem[sev]}</div>"
                             f"<div class='r' style='color:{s['cor']}'>{s['icone']} {sev}</div></div>", unsafe_allow_html=True)
        principais = [x for x in lista if x["severidade"] in ("Crítico", "Alto")][:6]
        for x in principais:
            st.markdown(f"{comum.selo_severidade(x['severidade'])} **{x['titulo']}**  \n<span class='pv-nota'>{x['resultado'][:220]}"
                        f"{'…' if len(x['resultado']) > 220 else ''}</span>", unsafe_allow_html=True)
        if "criticas" in navegacao.PAGINAS:
            st.page_link(navegacao.PAGINAS["criticas"], label="Ver todas as críticas e a memória de cálculo →")

    comum.secao("Despesa por função de governo", "Empenhado no período, consolidado ou órgãos selecionados.")
    d = comum.filtrar_orgaos(comum.ate_mes(dados.despesas(ano)))
    comum.barras_horizontais(d[~d["intra"]], "funcao", "empenhado", cor=CORES["vermelho"], n=12, chave="vg-funcao")
    comum.rodape()
