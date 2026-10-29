"""Constantes do painel: município, caminhos, categorias do TCE-MG e parâmetros legais."""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
# Versão web (stlite): o Python roda dentro do navegador do aparelho (Mac, PC, iPad, iPhone, Android).
# Os dados ficam no armazenamento do próprio navegador (IndexedDB montado em /mnt; o painel usa /mnt/painel).
NAVEGADOR = sys.platform == "emscripten"
DADOS = Path("/mnt/painel/dados") if NAVEGADOR else RAIZ / "dados"
# Pacotes do SICOM embutidos na versão web no momento em que ela foi gerada (somente leitura).
PACOTE_EMBUTIDO = RAIZ / "pacote_sicom"
BRUTOS_TCE = DADOS / "brutos" / "tce_sicom"
CACHE = DADOS / "cache"
ENTRADA = DADOS / "entrada"
MANUAL = DADOS / "manual"
ESTADO = DADOS / "estado.json"
LOGS = DADOS / "logs"
ASSETS = RAIZ / "assets"
LOGO = ASSETS / "logo_vicosa.jpg"

for _p in (BRUTOS_TCE, CACHE, ENTRADA, MANUAL, LOGS):
    _p.mkdir(parents=True, exist_ok=True)

# Pasta onde o navegador salva os arquivos baixados do portal do TCE-MG.
PASTA_DOWNLOADS = Path.home() / "Downloads"

MUNICIPIO = "Viçosa"
UF = "MG"
COD_IBGE = 3171303
COD_IBGE6 = 317130
CNPJ = "18132449000179"

EXERCICIO_ATUAL = date.today().year
ANOS = [EXERCICIO_ATUAL - 2, EXERCICIO_ATUAL - 1, EXERCICIO_ATUAL]

# Única fonte de dados do painel: portal de dados abertos do TCE-MG (SICOM).
URL_PORTAL_TCE = "https://dadosabertos.tce.mg.gov.br/#/public/selecionar-item-assunto/jurisdicionado"

# Abas (categorias) do portal dadosabertos.tce.mg.gov.br, na ordem do portal.
CATEGORIAS_TCE = {
    "orgao": "Órgão",
    "receita": "Receitas",
    "despesa": "Despesas",
    "empenho": "Empenho",
    "desp_pessoal": "Despesa com Pessoal",
    "saude": "Saúde",
    "educacao": "Educação",
    "licitacao": "Licitação",
    "contrato": "Contratos",
    "frota": "Veículos",
}

ORGAOS = {
    "01": "Câmara Municipal",
    "02": "Prefeitura Municipal",
    "03": "SAAE",
    "04": "IMAS (assistência ao servidor)",
    "05": "RPPS (previdência)",
}

MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

# Cores da identidade visual (logo da Prefeitura). A paleta de séries foi validada
# para separação sob daltonismo e contraste mínimo de 3:1 sobre fundo claro.
CORES = {
    "vermelho": "#B11E25",
    "azul": "#1F5FAE",
    "dourado": "#A67C00",
    "amarelo": "#F8C80A",
    "grafite": "#262626",
    "cinza": "#6B6B6B",
    "fundo": "#F6F3EF",
    "borda": "#E4DED6",
}
COR_ANO = {EXERCICIO_ATUAL: CORES["vermelho"], EXERCICIO_ATUAL - 1: CORES["azul"], EXERCICIO_ATUAL - 2: CORES["dourado"]}

# Severidades das críticas (cor reservada + ícone + rótulo; nunca só a cor).
SEVERIDADES = {
    "Crítico": {"cor": "#8E1414", "fundo": "#FBE9E9", "icone": "⛔", "ordem": 0},
    "Alto": {"cor": "#B5470B", "fundo": "#FDEEE3", "icone": "🔺", "ordem": 1},
    "Médio": {"cor": "#7A5B00", "fundo": "#FFF6D6", "icone": "⚠️", "ordem": 2},
    "Baixo": {"cor": "#1F5FAE", "fundo": "#E9F0FA", "icone": "ℹ️", "ordem": 3},
    "OK": {"cor": "#2E6B30", "fundo": "#E8F3E8", "icone": "✅", "ordem": 4},
    "Sem dados": {"cor": "#6B6B6B", "fundo": "#F0F0F0", "icone": "⏳", "ordem": 5},
}

# Limites legais usados nas críticas.
LIMITES = {
    "pessoal_executivo": {"alerta": 48.6, "prudencial": 51.3, "maximo": 54.0},   # LRF arts. 20, III, b; 22; 59 §1º II
    "pessoal_legislativo": {"alerta": 5.4, "prudencial": 5.7, "maximo": 6.0},   # LRF art. 20, III, a
    "pessoal_municipio": {"alerta": 54.0, "prudencial": 57.0, "maximo": 60.0},  # LRF art. 19, III
    "dc_rc": {"alerta": 85.0, "limite": 95.0},                                 # CF art. 167-A
    "mde_minimo": 25.0,                                                          # CF art. 212
    "fundeb_remuneracao_minimo": 70.0,                                           # CF art. 212-A, XI; Lei 14.113/2020 art. 26
    "fundeb_nao_aplicado_maximo": 10.0,                                          # Lei 14.113/2020 art. 25 §3º
    "asps_minimo": 15.0,                                                         # LC 141/2012 art. 7º
    "camara_repasse_ate_100mil_hab": 7.0,                                        # CF art. 29-A, I
    "camara_folha_maximo": 70.0,                                                 # CF art. 29-A §1º
    "dcl_maximo": 120.0,                                                         # Res. Senado 40/2001 art. 3º II
    "operacoes_credito_maximo": 16.0,                                            # Res. Senado 43/2001 art. 7º I
    "garantias_maximo": 22.0,                                                    # Res. Senado 43/2001 art. 9º
}

# Parâmetros editáveis pela Contabilidade (salvos em dados/manual/parametros.json).
PARAMETROS_PADRAO = {
    "limite_suplementacao_loa_pct": None,
    "lei_loa_numero": "",
    "dispensa_limites": {
        "2024": {"obras": 119812.02, "outros": 59906.02, "norma": "Decreto nº 11.871/2023"},
        "2025": {"obras": 125451.15, "outros": 62725.59, "norma": "Decreto nº 12.343/2024"},
        "2026": {"obras": 130984.20, "outros": 65492.11, "norma": "Decreto nº 12.807/2025"},
    },
    "tolerancia_consistencia_valor": 1.0,
    "populacao": 79517,
    "verificar_pasta_downloads": True,
}

ARQ_PARAMETROS = MANUAL / "parametros.json"


def carregar_parametros() -> dict:
    dados = json.loads(json.dumps(PARAMETROS_PADRAO))
    # Versão web: enquanto o aparelho não salvar os seus, vale o que estava salvo quando ela foi gerada.
    arquivo = ARQ_PARAMETROS if ARQ_PARAMETROS.exists() else RAIZ / "parametros_padrao.json"
    if arquivo.exists():
        try:
            salvo = json.loads(arquivo.read_text(encoding="utf-8"))
            for chave, valor in salvo.items():
                if isinstance(valor, dict) and isinstance(dados.get(chave), dict):
                    dados[chave].update(valor)
                else:
                    dados[chave] = valor
        except (OSError, ValueError):
            pass
    return dados


def salvar_parametros(parametros: dict) -> None:
    ARQ_PARAMETROS.write_text(json.dumps(parametros, ensure_ascii=False, indent=2), encoding="utf-8")
