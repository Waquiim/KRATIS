"""Críticas: pontos dos dados de 2026 passíveis de apontamento pelo TCE-MG.

Fonte única: pacotes do SICOM publicados no portal de dados abertos do TCE-MG. Cada verificação
aplica a metodologia oficial (MDF/STN, LRF, CF/88, normas e consultas do TCE-MG) a esses dados e
devolve uma `Critica` com severidade, memória de cálculo e fundamentação.
"""
from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from datetime import date, timedelta

import pandas as pd

from . import consistencia, dados, indicadores
from .config import LIMITES, SEVERIDADES, carregar_parametros
from .fontes import tce_sicom
from .formatos import brl, mes_ano, numero, pct

GRUPOS = [
    "Limites constitucionais e legais",
    "Equilíbrio fiscal e execução orçamentária",
    "Créditos adicionais e alterações orçamentárias",
    "Prazos e remessas",
    "Consistência interna dos dados do SICOM",
    "Restos a pagar",
    "Contratações diretas",
    "Qualidade dos dados publicados",
]


@dataclass
class Critica:
    codigo: str
    grupo: str
    titulo: str
    severidade: str
    resultado: str
    referencia: str = ""
    fundamento: str = ""
    metodologia: str = ""
    fonte: str = ""
    recomendacao: str = ""
    detalhe: pd.DataFrame | None = field(default=None, repr=False)
    grafico: str | None = None

    @property
    def ordem(self) -> int:
        return SEVERIDADES.get(self.severidade, {}).get("ordem", 9)


_VERIFICACOES = []


def verificacao(funcao):
    _VERIFICACOES.append(funcao)
    return funcao


def _faixa(valor: float | None, limites: list[tuple[float, str]], padrao: str = "OK") -> str:
    if valor is None:
        return "Sem dados"
    for limite, severidade in limites:
        if valor >= limite:
            return severidade
    return padrao


def _pior(*severidades: str) -> str:
    validas = [s for s in severidades if s in SEVERIDADES]
    return min(validas, key=lambda s: SEVERIDADES[s]["ordem"]) if validas else "Sem dados"


# ============================================================================ limites

@verificacao
def _dc_rc(ano: int, ultimo: int) -> list[Critica]:
    serie = indicadores.dc_rc_serie()
    atual = serie[serie["per"] // 100 == ano] if not serie.empty else serie
    if atual.empty:
        return [Critica("LIM-01", GRUPOS[0], "Relação despesas correntes / receitas correntes (art. 167-A)", "Sem dados",
                        "Não há dados do SICOM suficientes para 12 meses.")]
    ult = atual.iloc[-1]
    maximo = atual.loc[atual["percentual"].idxmax()]
    severidade = _faixa(float(maximo["percentual"]), [(95, "Crítico"), (85, "Alto")])
    resultado = (f"{pct(ult['percentual'])} nos 12 meses até {mes_ano(int(ult['per']) // 100, int(ult['per']) % 100)} "
                 f"(metodologia TCE-MG); maior valor no exercício: {pct(maximo['percentual'])} em "
                 f"{mes_ano(int(maximo['per']) // 100, int(maximo['per']) % 100)}.")
    resultado += f" Sem a exclusão do superávit: {pct(ult['percentual_sem_exclusao'])}."
    anomalias = indicadores.anomalias_mensais(ano)
    if not anomalias.empty and int(ult["per"]) % 100 in set(anomalias["Mês"]):
        resultado += " Atenção: o último mês do SICOM tem indício de remessa incompleta, o que reduz o percentual."
    detalhe = atual.assign(Mês=[mes_ano(p // 100, p % 100) for p in atual["per"]])[
        ["Mês", "dc", "dc_superavit", "rc", "percentual", "percentual_sem_exclusao"]].rename(columns={
            "dc": "Despesas correntes empenhadas (12 meses)", "dc_superavit": "DC com recursos de superávit (excluídas)",
            "rc": "Receitas correntes (12 meses)", "percentual": "DC/RC – metodologia TCE-MG (%)",
            "percentual_sem_exclusao": "DC/RC sem exclusão (%)"})
    return [Critica(
        "LIM-01", GRUPOS[0], "Relação despesas correntes / receitas correntes (art. 167-A)", severidade, resultado,
        referencia="Alerta: 85% (§1º) · Limite: 95% (caput)",
        fundamento="CF/88, art. 167-A (EC nº 109/2021); TCE-MG, Consulta nº 1.160.617 (prejulgamento de tese, 11/12/2024).",
        metodologia=("12 meses móveis, apurados mês a mês com os dados do SICOM: despesas correntes empenhadas, excluídas as "
                     "custeadas por créditos abertos com superávit financeiro do exercício anterior (fontes iniciadas por 2), "
                     "divididas pelas receitas correntes realizadas, líquidas das deduções (FUNDEB). Intraorçamentárias "
                     "excluídas dos dois lados."),
        fonte="SICOM (TCE-MG) – Receitas e Despesas",
        recomendacao=("Acima de 95%: avaliar a adoção dos mecanismos de ajuste fiscal do art. 167-A (vedações a reajustes, "
                      "criação de cargos, admissões, concursos, novas despesas obrigatórias etc.). Enquanto as medidas não "
                      "forem adotadas por todos os Poderes, o Município não pode receber garantias nem contratar operações de "
                      "crédito com outro ente (§6º). Entre 85% e 95%, as medidas podem ser adotadas por ato do Executivo (§1º)."),
        detalhe=detalhe, grafico="dc_rc")]


@verificacao
def _pessoal(ano: int, ultimo: int) -> list[Critica]:
    saida = []
    est = indicadores.pessoal_12m(ano, ultimo)
    if not est.get("completo"):
        return [Critica("LIM-02", GRUPOS[0], "Despesa com pessoal", "Sem dados",
                        "São necessários 12 meses de dados do SICOM para apurar o percentual.")]
    periodo = f"12 meses até {mes_ano(ano, ultimo)}"
    metodologia = ("Despesa bruta do conjunto 'Despesa com Pessoal' do TCE-MG nos 12 meses, menos as exclusões do art. 19, §1º "
                   "(indenizações, sentenças, despesas de exercícios anteriores e inativos custeados com recursos do RPPS, "
                   "apuradas na execução do conjunto 'Despesas'), sobre a RCL ajustada (RCL − emendas individuais e de "
                   "bancada) apurada com as receitas do SICOM pela metodologia do MDF/STN.")
    lim = LIMITES["pessoal_executivo"]
    saida.append(Critica(
        "LIM-02", GRUPOS[0], "Despesa com pessoal do Poder Executivo",
        _faixa(est["percentual_executivo"], [(lim["maximo"], "Crítico"), (lim["prudencial"], "Alto"), (lim["alerta"], "Médio")]),
        (f"{pct(est['percentual_executivo'])} da RCL ajustada ({periodo}): despesa líquida {brl(est['liquida_executivo'])} "
         f"sobre RCL ajustada de {brl(est['rcl_ajustada'])}."),
        referencia=f"Alerta {pct(lim['alerta'], 1)} · Prudencial {pct(lim['prudencial'], 1)} · Máximo {pct(lim['maximo'], 1)} da RCL ajustada",
        fundamento="LRF, arts. 19, 20 (III, b), 22 e 59, §1º, II; MDF/STN – RGF Anexo 1.",
        metodologia=metodologia, fonte="SICOM (TCE-MG) – Despesa com Pessoal, Despesas e Receitas",
        recomendacao="Acima de 51,3% aplicam-se as vedações do art. 22 da LRF; acima de 54%, o prazo de recondução do art. 23.",
        detalhe=est["exclusoes"]))
    anterior = indicadores.pessoal_12m(ano - 1, ultimo)
    if anterior.get("completo") and est["percentual_executivo"] - anterior["percentual_executivo"] >= 3:
        saida.append(Critica(
            "LIM-03", GRUPOS[0], "Crescimento acelerado da despesa com pessoal", "Médio",
            (f"O percentual passou de {pct(anterior['percentual_executivo'])} ({mes_ano(ano - 1, ultimo)}) para "
             f"{pct(est['percentual_executivo'])} ({mes_ano(ano, ultimo)}), alta de "
             f"{numero(est['percentual_executivo'] - anterior['percentual_executivo'])} p.p. em 12 meses."),
            referencia="Monitoramento de tendência (LRF, art. 59)", fundamento="LRF, arts. 21, 22 e 59, §1º, II.",
            metodologia="Mesma apuração (12 meses) no mesmo mês de dois exercícios.",
            fonte="SICOM (TCE-MG)",
            recomendacao="Verificar a causa (reajustes, admissões, redução das exclusões com inativos) e projetar o fechamento."))
    lim_l = LIMITES["pessoal_legislativo"]
    saida.append(Critica(
        "LIM-04", GRUPOS[0], "Despesa com pessoal do Poder Legislativo",
        _faixa(est["percentual_legislativo"], [(lim_l["maximo"], "Crítico"), (lim_l["prudencial"], "Alto"), (lim_l["alerta"], "Médio")]),
        f"{pct(est['percentual_legislativo'])} da RCL ajustada ({periodo}); despesa líquida {brl(est['liquida_legislativo'])}.",
        referencia=f"Alerta {pct(lim_l['alerta'], 1)} · Prudencial {pct(lim_l['prudencial'], 1)} · Máximo {pct(lim_l['maximo'], 1)}",
        fundamento="LRF, art. 20, III, a.", metodologia=metodologia, fonte="SICOM (TCE-MG)"))
    lim_m = LIMITES["pessoal_municipio"]
    saida.append(Critica(
        "LIM-05", GRUPOS[0], "Despesa com pessoal consolidada do Município",
        _faixa(est["percentual_municipio"], [(lim_m["maximo"], "Crítico"), (lim_m["prudencial"], "Alto"), (lim_m["alerta"], "Médio")]),
        f"Executivo + Legislativo: {pct(est['percentual_municipio'])} da RCL ajustada ({periodo}).",
        referencia="Máximo de 60% da RCL", fundamento="LRF, art. 19, III.", metodologia=metodologia, fonte="SICOM (TCE-MG)"))
    return saida


def _minimo_constitucional(codigo, titulo, minimo, declarado, rotulo_declarado, estimativa, rotulo_estimativa, final,
                           fundamento, metodologia, fonte, recomendacao, detalhe=None) -> Critica:
    valores = [v for v in (declarado, estimativa) if v is not None]
    if not valores:
        sev = "Sem dados"
    elif final:
        sev = "Crítico" if min(valores) < minimo else "OK"
    elif all(v < minimo for v in valores):
        sev = "Médio"
    elif any(v < minimo for v in valores):
        sev = "Baixo"
    else:
        sev = "OK"
    partes = []
    if declarado is not None:
        partes.append(f"{rotulo_declarado}: {pct(declarado)}")
    if estimativa is not None:
        partes.append(f"{rotulo_estimativa}: {pct(estimativa)}")
    texto = "; ".join(partes) or "Sem dados."
    if valores and not final:
        texto += ". O mínimo é apurado no encerramento do exercício; durante o ano o indicador mostra a tendência."
    return Critica(codigo, GRUPOS[0], titulo, sev, texto, referencia=f"Mínimo de {pct(minimo, 0)}",
                   fundamento=fundamento, metodologia=metodologia, fonte=fonte, recomendacao=recomendacao, detalhe=detalhe)


@verificacao
def _educacao(ano: int, ultimo: int) -> list[Critica]:
    final = ultimo == 12
    base_despesa = "empenhado" if final else "liquidado"
    m = indicadores.mde(ano, ultimo)
    saida = [_minimo_constitucional(
        "LIM-06", "Aplicação em Manutenção e Desenvolvimento do Ensino (MDE)", LIMITES["mde_minimo"],
        None, "", m[f"percentual_{base_despesa}"],
        f"SICOM até {mes_ano(ano, ultimo)} (despesas {'empenhadas' if final else 'liquidadas'})", final,
        "CF/88, art. 212; Lei nº 14.113/2020; MDF/STN – RREO Anexo 8.",
        ("Base: impostos municipais (IPTU, ITBI, ISS, IRRF) e transferências constitucionais (FPM, inclusive cotas extras de 1%, "
         "ITR, ICMS, IPVA, IPI-Exportação), valores brutos. Aplicação: contribuição ao FUNDEB + despesas com recursos de "
         "impostos identificadas com CO 1001 (conjunto 'Educação' do TCE-MG)."),
        "SICOM (TCE-MG) – Educação e Receitas",
        "Projetar o fechamento: as despesas empenhadas e inscritas em restos a pagar sem disponibilidade de caixa não contam.",
        detalhe=m["itens_base"])]
    f = indicadores.fundeb(ano, ultimo)
    saida.append(_minimo_constitucional(
        "LIM-07", "FUNDEB na remuneração dos profissionais da educação básica", LIMITES["fundeb_remuneracao_minimo"],
        None, "", f.get("percentual_remuneracao"), f"SICOM até {mes_ano(ano, ultimo)}", final,
        "CF/88, art. 212-A, XI; Lei nº 14.113/2020, art. 26.",
        "Despesas liquidadas com recursos do FUNDEB identificadas com CO 1070 ÷ receitas do FUNDEB (fontes 540–546, inclusive rendimentos).",
        "SICOM (TCE-MG) – Despesas e Receitas",
        "Acompanhar mensalmente; o percentual tende a subir ao longo do ano (13º salário e abonos)."))
    saldo = indicadores.fundeb_saldo_anterior(ano)
    if saldo.get("saldo") and saldo["saldo"] > 0:
        prazo_vencido = ultimo >= 4 or date.today() > date(ano, 4, 30)
        aplicado = saldo["aplicado_1o_quadrimestre"]
        sev = "OK" if aplicado >= saldo["saldo"] else ("Alto" if prazo_vencido else "Médio")
        if (saldo.get("percentual_nao_aplicado") or 0) > LIMITES["fundeb_nao_aplicado_maximo"]:
            sev = "Crítico"
        saida.append(Critica(
            "LIM-08", GRUPOS[0], f"Saldo do FUNDEB de {ano - 1} e sua aplicação até o 1º quadrimestre", sev,
            (f"Receitas do FUNDEB de {ano - 1} não empenhadas no exercício: {brl(saldo['saldo'])} "
             f"({pct(saldo.get('percentual_nao_aplicado'))} das receitas; máximo permitido 10%). Empenhado com recursos do "
             f"FUNDEB de exercícios anteriores (fontes 2.540–2.546) até abril/{ano}: {brl(aplicado)}."),
            referencia="Até 10% das receitas do FUNDEB podem ficar para o 1º quadrimestre do exercício seguinte",
            fundamento="Lei nº 14.113/2020, art. 25, §3º.",
            metodologia="Receitas do FUNDEB do exercício anterior − despesas empenhadas nas mesmas fontes (SICOM) x empenhos de abril em diante em fontes de exercícios anteriores.",
            fonte="SICOM (TCE-MG) – Receitas e Despesas",
            recomendacao="Confirmar a abertura do crédito adicional e a aplicação do saldo; se aplicado em outra fonte, corrigir a classificação."))
    return saida


@verificacao
def _saude(ano: int, ultimo: int) -> list[Critica]:
    final = ultimo == 12
    base_despesa = "empenhado" if final else "liquidado"
    a = indicadores.asps(ano, ultimo)
    return [_minimo_constitucional(
        "LIM-09", "Aplicação em Ações e Serviços Públicos de Saúde (ASPS)", LIMITES["asps_minimo"],
        None, "", a[f"percentual_{base_despesa}"],
        f"SICOM até {mes_ano(ano, ultimo)} (despesas {'empenhadas' if final else 'liquidadas'})", final,
        "CF/88, art. 198, §2º, III; LC nº 141/2012, arts. 7º e 24; MDF/STN – RREO Anexo 12.",
        ("Base: impostos municipais e transferências constitucionais, excluídas as cotas extras de 1% do FPM (art. 159, I, d, e, f). "
         "Aplicação: despesas com recursos de impostos identificadas com CO 1002 (conjunto 'Saúde' do TCE-MG)."),
        "SICOM (TCE-MG) – Saúde e Receitas", "", detalhe=a["itens_base"])]


@verificacao
def _camara(ano: int, ultimo: int) -> list[Critica]:
    c = indicadores.camara(ano)
    if not c:
        return []
    sev_dot = "Alto" if c["dotacao_atualizada"] > c["limite"] else "OK"
    sev_proj = "Médio" if (c["projecao_anual"] or 0) > c["limite"] else "OK"
    sev_folha = "Médio" if (c["percentual_folha_dotacao"] or 0) > LIMITES["camara_folha_maximo"] else "OK"
    return [Critica(
        "LIM-10", GRUPOS[0], "Total da despesa do Poder Legislativo (art. 29-A)", _pior(sev_dot, sev_proj, sev_folha),
        (f"Limite de {pct(c['percentual_limite'], 0)} da receita tributária e transferências de {ano - 1} "
         f"({brl(c['base'])}): {brl(c['limite'])}. Dotação atualizada da Câmara: {brl(c['dotacao_atualizada'])} "
         f"({pct(c['percentual_dotacao'])}); projeção anual pela despesa liquidada: {brl(c['projecao_anual'])} "
         f"({pct(c['percentual_projecao'])}). Folha projetada sobre a dotação: {pct(c['percentual_folha_dotacao'])}."),
        referencia=f"{pct(c['percentual_limite'], 0)} (população {c['populacao']:,} hab.) · folha ≤ 70% da receita da Câmara".replace(",", "."),
        fundamento="CF/88, art. 29-A, I e §§1º e 2º.",
        metodologia=("Base: receita tributária e transferências dos arts. 153 §5º, 158 e 159 da CF efetivamente realizadas no "
                     "exercício anterior (SICOM), sem dedução do FUNDEB. Despesa da Câmara (órgão 01) excluídos inativos e "
                     "pensionistas. A folha (§1º) desconsidera obrigações patronais e é comparada à dotação, usada como "
                     "aproximação do duodécimo."),
        fonte="SICOM (TCE-MG) – Receitas e Despesas; população informada em Parâmetros",
        recomendacao="Repasse acima do limite ou inferior à proporção fixada na LOA configura crime de responsabilidade (art. 29-A, §2º).",
        detalhe=c["itens_base"])]


# ============================================================================ equilíbrio

@verificacao
def _receitas(ano: int, ultimo: int) -> list[Critica]:
    r = indicadores.realizacao_receita(ano, ultimo)
    if not r:
        return []
    saida = []
    cor = r["correntes"]
    saida.append(Critica(
        "EQU-01", GRUPOS[1], "Realização das receitas correntes", _faixa(100 - (cor["percentual"] or 100), [(10, "Alto"), (5, "Médio")]),
        (f"Arrecadado até {mes_ano(ano, ultimo)}: {brl(cor['realizado'])}, {pct(cor['percentual'])} do esperado pela sazonalidade "
         f"de {ano - 1} ({brl(cor['esperado'])}); {pct(cor['percentual_da_previsao'])} da previsão atualizada."),
        referencia="Frustração relevante exige limitação de empenho",
        fundamento="LRF, arts. 8º e 9º.",
        metodologia=("Esperado = previsão atualizada × proporção arrecadada até o mesmo mês no exercício anterior. "
                     "Receitas correntes líquidas das deduções, sem intraorçamentárias."),
        fonte="SICOM (TCE-MG) – Receitas"))
    cap = r["capital"]
    if cap["previsao_atualizada"]:
        sev = "Médio" if (cap["percentual_da_previsao"] or 0) < 25 and ultimo >= 6 else "OK"
        saida.append(Critica(
            "EQU-02", GRUPOS[1], "Realização das receitas de capital", sev,
            (f"Realizado até {mes_ano(ano, ultimo)}: {brl(cap['realizado'])} de {brl(cap['previsao_atualizada'])} previstos "
             f"({pct(cap['percentual_da_previsao'])})."),
            referencia="Receitas de capital previstas sustentam investimentos e operações de crédito autorizadas",
            fundamento="LRF, arts. 9º e 12; Lei nº 4.320/1964, art. 43, §1º, II (excesso de arrecadação).",
            metodologia="Receitas de capital realizadas (SICOM) x previsão atualizada.",
            fonte="SICOM (TCE-MG) – Receitas",
            recomendacao="Rever a programação de investimentos dependentes dessas receitas e evitar créditos adicionais lastreados nelas."))
    return saida


@verificacao
def _resultado(ano: int, ultimo: int) -> list[Critica]:
    rec = dados.resumo_receita(ano, ultimo)
    desp = dados.resumo_despesa(ano, ultimo)
    if not rec or not desp:
        return []
    saldo_liq = rec["realizada"] - desp["liquidado"]
    saldo_emp = rec["realizada"] - desp["empenhado"]
    return [Critica(
        "EQU-03", GRUPOS[1], "Resultado da execução orçamentária no exercício", "Médio" if saldo_liq < 0 else ("Baixo" if saldo_emp < 0 else "OK"),
        (f"Até {mes_ano(ano, ultimo)}: receita arrecadada {brl(rec['realizada'])}; despesa liquidada {brl(desp['liquidado'])} "
         f"(resultado {brl(saldo_liq)}); despesa empenhada {brl(desp['empenhado'])} (resultado {brl(saldo_emp)})."),
        referencia="Equilíbrio entre receitas e despesas",
        fundamento="LRF, art. 1º, §1º; Lei nº 4.320/1964, art. 48.",
        metodologia="Valores sem intraorçamentárias. Empenhos globais e estimativos concentram-se no início do ano, por isso o resultado pela despesa liquidada é a referência intermediária.",
        fonte="SICOM (TCE-MG) – Receitas e Despesas")]


@verificacao
def _fontes(ano: int, ultimo: int) -> list[Critica]:
    tabela = indicadores.execucao_por_fonte(ano, ultimo)
    if tabela.empty:
        return []
    tabela["resultado_liquidado"] = tabela["realizado"] - tabela["liquidado"]
    deficitarias = tabela[tabela["resultado_liquidado"] < -1000].sort_values("resultado_liquidado")
    return [Critica(
        "EQU-04", GRUPOS[1], "Fontes de recursos com despesa liquidada acima da receita do exercício",
        "Baixo" if not deficitarias.empty else "OK",
        (f"{len(deficitarias)} fonte(s) do exercício corrente com liquidação superior à arrecadação até {mes_ano(ano, ultimo)}; "
         f"maior diferença: {brl(deficitarias['resultado_liquidado'].min())} ({deficitarias.iloc[0]['fonte']})."
         if not deficitarias.empty else "Nenhuma fonte com liquidação acima da arrecadação."),
        referencia="Vinculação de recursos por fonte",
        fundamento="LRF, art. 8º, parágrafo único, e art. 50, I.",
        metodologia="Receita realizada x despesa liquidada por fonte de recursos do exercício corrente (prefixo 1). Não considera o saldo financeiro de exercícios anteriores.",
        fonte="SICOM (TCE-MG) – Receitas e Despesas",
        recomendacao="Confirmar a existência de saldo financeiro da fonte (superávit) que cubra a diferença.",
        detalhe=deficitarias[["fonte", "fonte_desc", "realizado", "liquidado", "resultado_liquidado"]].rename(columns={
            "fonte": "Fonte", "fonte_desc": "Descrição", "realizado": "Receita realizada", "liquidado": "Despesa liquidada",
            "resultado_liquidado": "Diferença"}))]


# ============================================================================ créditos

@verificacao
def _creditos(ano: int, ultimo: int) -> list[Critica]:
    c = indicadores.creditos_adicionais(ano)
    if not c:
        return []
    saida = []
    limite = c["limite_loa"]
    if limite:
        sev = "Alto" if (c["percentual_suplementado"] or 0) > float(limite) else "OK"
        referencia = f"Limite autorizado na LOA: {pct(float(limite))} da despesa fixada"
    else:
        sev = "Médio"
        referencia = "Informe o limite autorizado na LOA em Atualização de dados → Parâmetros"
    saida.append(Critica(
        "CRE-01", GRUPOS[2], "Créditos suplementares abertos por decreto", sev,
        (f"{brl(c['suplementares'])} em créditos suplementares até {mes_ano(ano, ultimo)}, "
         f"{pct(c['percentual_suplementado'])} da dotação inicial ({brl(c['dotacao_inicial'])}). Lei autorizativa mais citada: nº {c['lei_loa']}."),
        referencia=referencia,
        fundamento="CF/88, art. 167, V e VII; Lei nº 4.320/1964, arts. 7º, 42 e 43.",
        metodologia="Soma dos decretos do tipo 'crédito suplementar' publicados no conjunto Despesas do TCE-MG.",
        fonte="SICOM (TCE-MG) – Decretos e leis de alteração orçamentária",
        detalhe=c["resumo"]))
    especiais = c["especiais_sem_lei"]
    saida.append(Critica(
        "CRE-02", GRUPOS[2], "Créditos especiais sem lei específica", "Alto" if not especiais.empty else "OK",
        f"{len(especiais)} decreto(s) de crédito especial sem lei própria." if not especiais.empty
        else "Todos os créditos especiais citam lei específica.",
        referencia="Crédito especial depende de autorização legislativa específica",
        fundamento="CF/88, art. 167, V; Lei nº 4.320/1964, art. 42.",
        metodologia="Decretos do tipo 'crédito especial' cuja lei vinculada está ausente ou é a mesma lei da LOA.",
        fonte="SICOM (TCE-MG) – Decretos",
        detalhe=especiais[["num_decreto", "dat_ass_decreto", "vlr_aberto", "leis"]] if not especiais.empty else None))
    antes = c["decretos_antes_da_lei"]
    saida.append(Critica(
        "CRE-03", GRUPOS[2], "Decretos assinados antes da lei autorizativa", "Alto" if not antes.empty else "OK",
        f"{len(antes)} decreto(s) com data anterior à lei que os autoriza." if not antes.empty else "Nenhum decreto anterior à respectiva lei.",
        fundamento="CF/88, art. 167, V; Lei nº 4.320/1964, art. 42.",
        metodologia="Data de assinatura do decreto x data da lei vinculada.", fonte="SICOM (TCE-MG) – Decretos",
        detalhe=antes[["num_decreto", "dat_ass_decreto", "tipo", "leis", "data_lei", "vlr_aberto"]] if not antes.empty else None))
    mov = c["movimentacoes"]
    if not mov.empty:
        saida.append(Critica(
            "CRE-04", GRUPOS[2], "Remanejamentos, transposições e transferências de recursos", "Baixo",
            (f"{len(mov)} decreto(s), total {brl(mov['vlr_aberto'].sum())}, fundamentados na(s) lei(s) "
             f"{', '.join(sorted(set(', '.join(mov['leis'].fillna('')).split(', ')) - {''}))}."),
            referencia="Exigem prévia autorização legislativa",
            fundamento="CF/88, art. 167, VI.",
            metodologia="Decretos dos tipos remanejamento, transposição e transferência.",
            fonte="SICOM (TCE-MG) – Decretos",
            recomendacao="Confirmar que a lei citada autoriza expressamente essas movimentações e respeita seus limites.",
            detalhe=mov[["num_decreto", "dat_ass_decreto", "tipo", "vlr_aberto", "leis"]]))
    por_fonte = indicadores.dotacoes_excedidas(ano, ultimo, por_fonte=True)
    agregadas = indicadores.dotacoes_excedidas(ano, ultimo, por_fonte=False)
    colunas = ["orgao", "funcao", "acao", "natureza_cod", "natureza", "fonte", "dotacao", "empenhado", "excesso"]
    nomes = {"orgao": "Órgão", "funcao": "Função", "acao": "Ação", "natureza_cod": "Elemento", "natureza": "Descrição",
             "fonte": "Fonte(s)", "dotacao": "Crédito autorizado", "empenhado": "Empenhado", "excesso": "Excesso"}
    if not agregadas.empty:
        sev, texto = "Crítico", (f"{len(agregadas)} dotação(ões) com empenho acima do crédito mesmo somando todas as fontes; "
                                 f"excesso total {brl(agregadas['excesso'].sum())}.")
        detalhe = agregadas[colunas].rename(columns=nomes)
    elif not por_fonte.empty:
        sev, texto = "Alto", (f"{len(por_fonte)} dotação(ões) com empenho acima do crédito da fonte (o total da dotação comporta a "
                              f"despesa); excesso por fonte {brl(por_fonte['excesso'].sum())}. Possível erro de classificação da "
                              "fonte ou falta de decreto de alteração de fonte.")
        detalhe = por_fonte[colunas].rename(columns=nomes)
    else:
        sev, texto, detalhe = "OK", "Nenhuma dotação com empenho acima do crédito autorizado.", None
    saida.append(Critica(
        "CRE-05", GRUPOS[2], "Despesa empenhada acima do crédito orçamentário", sev, texto,
        fundamento="CF/88, art. 167, II; Lei nº 4.320/1964, art. 59.",
        metodologia=("Dotação atualizada (inicial + créditos − anulações, conforme o SICOM) x empenhado acumulado, por dotação: "
                     "órgão, unidade, funcional-programática e elemento, com e sem a fonte de recursos."),
        fonte="SICOM (TCE-MG) – Despesas e alterações orçamentárias",
        recomendacao="Confrontar com o razão das dotações no sistema contábil; se o crédito existe, retificar a remessa do SICOM.",
        detalhe=detalhe))
    return saida


# ============================================================================ prazos

@verificacao
def _remessas(ano: int, ultimo: int) -> list[Critica]:
    rem = indicadores.remessas_sicom(ano)
    if rem.empty:
        return []
    atrasadas = rem[rem["situacao_prazo"].eq("Não enviado após o prazo")]
    referencia_data = rem["referencia"].iloc[0]
    return [Critica(
        "PRA-01", GRUPOS[3], "Remessas do SICOM – Acompanhamento Mensal", "Alto" if not atrasadas.empty else "OK",
        (f"Na carga do TCE-MG de {referencia_data:%d/%m/%Y}: {int((rem['situacao_prazo'] == 'Enviado').sum())} mês(es) enviado(s); "
         f"{len(atrasadas)} não enviado(s) após o prazo; último mês disponível: {mes_ano(ano, ultimo)}."),
        referencia="Até o último dia do mês subsequente",
        fundamento="Instrução Normativa TCEMG nº 03/2015 (com alterações da IN nº 02/2017).",
        metodologia="Situação das remessas publicada no conjunto 'Órgão' do portal de dados abertos.",
        fonte="SICOM (TCE-MG) – Órgão (remessaMunicipio)",
        recomendacao="Para a posição atual, baixe novamente os pacotes do SICOM (aba Atualização de dados).",
        detalhe=rem[["mes", "dsc_situacao", "prazo", "situacao_prazo"]].rename(columns={
            "mes": "Mês", "dsc_situacao": "Situação no TCE", "prazo": "Prazo", "situacao_prazo": "Avaliação"}))]


@verificacao
def _consistencia(ano: int, ultimo: int) -> list[Critica]:
    todas = consistencia.todas(ano)
    if todas.empty:
        return []
    textos = {
        "Pessoal": ("CON-01", "Despesa com pessoal: conjunto 'Despesa com Pessoal' x grupo 3.1 de 'Despesas'",
                    "A folha informada nos dois conjuntos deve ser a mesma em cada mês."),
        "Execução": ("CON-02", "Execução da despesa: 'Despesas' x 'Empenho' (por fonte)",
                     "Empenhado, liquidado e pago do mês devem coincidir nos dois conjuntos."),
        "Educação (MDE)": ("CON-03", "Educação: conjunto 'Educação' x 'Despesas' (fonte 1.500, CO 1001)",
                           "O conjunto 'Educação' é o recorte da despesa com impostos identificada com CO 1001."),
        "Saúde (ASPS)": ("CON-04", "Saúde: conjunto 'Saúde' x 'Despesas' (fonte 1.500, CO 1002)",
                         "O conjunto 'Saúde' é o recorte da despesa com impostos identificada com CO 1002."),
        "Alterações orçamentárias": ("CON-05", "Decretos x detalhamento das alterações orçamentárias",
                                     "O valor aberto pelo decreto deve igualar os acréscimos por dotação; movimentações devem anular o mesmo valor."),
        "Remessas": ("CON-06", "Situação das remessas x meses com dados publicados",
                     "Meses enviados devem ter dados; meses não enviados não devem ter."),
    }
    saida = []
    for tema, (codigo, titulo, regra) in textos.items():
        parte = todas[todas["Tema"].eq(tema)]
        if parte.empty:
            continue
        ruins = parte[parte["Situação"].eq("Inconsistente")]
        pequenas = parte[parte["Situação"].eq("Diferença pequena")]
        if not ruins.empty:
            sev = "Alto"
            maior = ruins["Diferença (B − A)"].abs().max()
            texto = (f"{len(ruins)} de {len(parte)} confronto(s) inconsistente(s)"
                     + (f"; maior diferença {brl(maior)}" if pd.notna(maior) else "") + ".")
        elif not pequenas.empty:
            sev, texto = "Baixo", f"{len(pequenas)} confronto(s) com diferença inferior a 0,5%."
        else:
            sev, texto = "OK", f"Os {len(parte)} confrontos coincidem."
        saida.append(Critica(
            codigo, GRUPOS[4], titulo, sev, texto, referencia=regra,
            fundamento="IN TCEMG nº 03/2015 (integridade e fidedignidade das remessas do SICOM).",
            metodologia="Confronto mês a mês entre conjuntos do mesmo pacote do portal de dados abertos do TCE-MG.",
            fonte="SICOM (TCE-MG)",
            recomendacao="Verificar no sistema contábil qual remessa está incompleta ou desatualizada e retificá-la no SICOM.",
            detalhe=parte[parte["Situação"].ne("Consistente")] if sev != "OK" else None))
    return saida


@verificacao
def _anomalias(ano: int, ultimo: int) -> list[Critica]:
    a = indicadores.anomalias_mensais(ano)
    return [Critica(
        "QUA-01", GRUPOS[7], "Meses com valores atipicamente baixos no SICOM", "Médio" if not a.empty else "OK",
        "; ".join(f"{r['Série']} em {mes_ano(ano, int(r['Mês']))}: {pct(r['Proporção'], 0)} da mediana dos demais meses"
                  for _, r in a.iterrows()) or "Nenhuma série mensal com queda atípica.",
        referencia="Valor inferior a 50% da mediana dos demais meses",
        fundamento="IN TCEMG nº 03/2015 (integralidade das remessas).",
        metodologia="Comparação de cada mês com a mediana dos demais meses do exercício (pessoal, receitas correntes e despesa liquidada).",
        fonte="SICOM (TCE-MG)",
        recomendacao="Verificar se a remessa do mês foi completa (folha de pagamento, liquidações) e reenviar se necessário.",
        detalhe=a if not a.empty else None)]


@verificacao
def _qualidade_tce(ano: int, ultimo: int) -> list[Critica]:
    saida = []
    for a in (ano - 1, ano):
        lic = tce_sicom.ler(a, "licitacao", "licitacao")
        if lic.attrs.get("aviso"):
            saida.append(Critica(
                f"QUA-02-{a}", GRUPOS[7], f"Arquivo de licitações de {a} publicado com leiaute de dispensas", "Baixo",
                lic.attrs["aviso"], fundamento="Lei nº 12.527/2011 (qualidade da informação); IN TCEMG nº 03/2015.",
                metodologia="Validação do leiaute dos CSVs do portal.", fonte="Portal de dados abertos do TCE-MG",
                recomendacao="Conferir no SICOM se as licitações do exercício foram enviadas no módulo correto."))
    return saida


# ============================================================================ restos a pagar

@verificacao
def _restos(ano: int, ultimo: int) -> list[Critica]:
    canc = indicadores.rp_cancelamentos(ano)
    if canc.empty:
        return []
    proc = canc[canc["tipo_rp"].str.upper().str.startswith("RESTOS A PAGAR PROCESSADOS")]
    nproc = canc[~canc.index.isin(proc.index)]
    saida = [Critica(
        "RPG-01", GRUPOS[5], "Cancelamento de restos a pagar processados", "Alto" if not proc.empty else "OK",
        f"{len(proc)} cancelamento(s) de despesas já liquidadas, total {brl(proc['vlr_movimentacao'].sum())}."
        if not proc.empty else "Nenhum cancelamento de restos a pagar processados.",
        referencia="Despesa liquidada é obrigação reconhecida",
        fundamento="Lei nº 4.320/1964, arts. 36, 63 e 92; LRF, art. 42; entendimento reiterado do TCE-MG.",
        metodologia="Movimentações de restos a pagar do tipo 'cancelamento' sobre RP processados.",
        fonte="SICOM (TCE-MG) – Empenho (movimentações de RP)",
        recomendacao="Manter justificativa documentada (prescrição, erro de liquidação) e ato formal de cada cancelamento.",
        detalhe=proc[["num_emp_origem", "num_ano_emp_origem", "dsc_dotacao_origem", "vlr_movimentacao", "dsc_ato_cancelamento", "dsc_justificativa"]]
        if not proc.empty else None)]
    funcao = nproc["dsc_dotacao_origem"].str.split(".").str[2]
    vinculados = nproc[funcao.isin(["10", "12"])]
    saida.append(Critica(
        "RPG-02", GRUPOS[5], "Restos a pagar não processados cancelados em saúde e educação",
        "Médio" if not vinculados.empty else "OK",
        (f"Cancelados em {ano}: {brl(nproc['vlr_movimentacao'].sum())} em RP não processados, dos quais "
         f"{brl(vinculados['vlr_movimentacao'].sum())} nas funções Saúde e Educação."),
        referencia="RP computados no mínimo e depois cancelados devem ser reaplicados",
        fundamento="LC nº 141/2012, art. 24, §§1º e 2º; MDF/STN – Anexos 8 e 12.",
        metodologia="Movimentações de cancelamento de RP não processados com dotação de origem nas funções 10 e 12.",
        fonte="SICOM (TCE-MG) – Empenho (movimentações de RP)",
        recomendacao="Verificar se esses RP foram considerados no cumprimento dos mínimos de exercícios anteriores e compensar.",
        detalhe=vinculados[["num_emp_origem", "num_ano_emp_origem", "dsc_dotacao_origem", "vlr_movimentacao", "dsc_ato_cancelamento"]]
        if not vinculados.empty else None))
    return saida


# ============================================================================ contratações diretas

@verificacao
def _dispensas(ano: int, ultimo: int) -> list[Critica]:
    dv = indicadores.dispensas_por_valor(ano)
    if dv.empty:
        return []
    acima = dv[dv["acima_do_limite"]]
    limites = carregar_parametros().get("dispensa_limites", {}).get(str(ano), {})
    saida = [Critica(
        "CTR-01", GRUPOS[6], "Dispensa por valor acima do limite legal", "Médio" if not acima.empty else "OK",
        f"{len(acima)} dispensa(s) fundamentada(s) no art. 75, I ou II, com valor acima do limite."
        if not acima.empty else "Nenhuma dispensa por valor acima do limite.",
        referencia=(f"{brl(limites.get('obras'))} (obras e engenharia) · {brl(limites.get('outros'))} (demais) – "
                    f"{limites.get('norma', 'decreto de atualização')}"),
        fundamento="Lei nº 14.133/2021, art. 75, I e II, e §1º; decreto federal de atualização anual dos valores.",
        metodologia="Dispensas com fundamentação no art. 75, I/II (texto da justificativa) e valor dos fornecedores (quantidade × preço).",
        fonte="SICOM (TCE-MG) – Licitação (dispensa e fornecedores)",
        recomendacao="Verificar o enquadramento legal (consórcios públicos têm limites em dobro – art. 75, §2º) e a pesquisa de preços.",
        detalhe=acima[["num_processo", "objeto", "valor_estimado", "limite", "fornecedores"]] if not acima.empty else None)]
    frac = indicadores.possivel_fracionamento(ano)
    saida.append(Critica(
        "CTR-02", GRUPOS[6], "Possível fracionamento de despesa", "Médio" if not frac.empty else "OK",
        f"{len(frac)} fornecedor(es) com dispensas por valor que, somadas no exercício, superam o limite."
        if not frac.empty else "Não foram encontrados indícios de fracionamento nas dispensas por valor.",
        fundamento="Lei nº 14.133/2021, art. 75, §1º.",
        metodologia="Soma, por fornecedor e natureza do objeto, das dispensas por valor do exercício.",
        fonte="SICOM (TCE-MG) – Licitação",
        detalhe=frac if not frac.empty else None))
    return saida


# ============================================================================ execução

def gerar(ano: int) -> list[Critica]:
    ultimo = dados.ultimo_mes(ano)
    if not ultimo:
        return [Critica("GER-00", GRUPOS[7], "Dados do SICOM não importados", "Sem dados",
                        f"Não há pacotes do SICOM de {ano}. Use a aba Atualização de dados.")]
    saida: list[Critica] = []
    for funcao in _VERIFICACOES:
        try:
            saida.extend(funcao(ano, ultimo))
        except Exception as erro:  # uma verificação com falha não derruba as demais
            saida.append(Critica(f"ERR-{funcao.__name__}", GRUPOS[7], f"Falha ao executar a verificação {funcao.__name__}",
                                 "Sem dados", f"{erro}", metodologia=traceback.format_exc(limit=2)))
    return sorted(saida, key=lambda c: (c.ordem, GRUPOS.index(c.grupo) if c.grupo in GRUPOS else 99, c.codigo))
