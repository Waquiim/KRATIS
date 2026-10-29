"""Pacotes do SICOM publicados no portal de dados abertos do TCE-MG.

O portal (dadosabertos.tce.mg.gov.br) só libera a API depois de uma verificação
reCAPTCHA feita no navegador. Por isso o programa não baixa esses arquivos sozinho:
o usuário usa o favorito "Baixar SICOM Viçosa" (ferramentas/) no próprio navegador
e este módulo importa os ZIPs que aparecem em dados/entrada ou na pasta Downloads.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import shutil
import zipfile
from collections import Counter
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import pandas as pd

from .. import estado
from ..config import (
    ANOS,
    BRUTOS_TCE,
    CATEGORIAS_TCE,
    COD_IBGE,
    ENTRADA,
    NAVEGADOR,
    PACOTE_EMBUTIDO,
    PASTA_DOWNLOADS,
    carregar_parametros,
)

PADRAO_ZIP = re.compile(rf"^SICOM\.(\d{{4}})\.{COD_IBGE}\.([a-z_]+)(?: ?\(\d+\))?\.zip$", re.IGNORECASE)
PADRAO_MANIFESTO = re.compile(rf"^SICOM\.{COD_IBGE}\.manifesto.*\.json$", re.IGNORECASE)
PADRAO_CSV = re.compile(rf"(?:^|/)(\d{{4}})\.{COD_IBGE}\.([a-z_]+)\.([A-Za-z]+)\.csv$")
ARQ_MANIFESTO = BRUTOS_TCE / "manifesto.json"
HISTORICO = BRUTOS_TCE / "historico"
PROCESSADOS = ENTRADA / "processados"
TAMANHO_MAXIMO = 400 * 1024 * 1024

# O arquivo movimentacaoRsp é publicado com o cabeçalho de movFonteRsp; as linhas
# seguem o leiaute MOVIMENTORSP do dicionário de dados do TCE-MG.
CABECALHOS_CORRIGIDOS = {
    "movimentacaoRsp": [
        "seq_mov_rsp", "seq_rsp", "seq_orgao", "cod_orgao", "num_ano_referencia", "num_mes_referencia",
        "cod_unid_origem", "cod_sub_unid_origem", "num_emp_origem", "dat_emp_origem", "num_ano_emp_origem",
        "dsc_dotacao_origem", "dsc_tipo_rsp", "dsc_tipo_movimentacao", "dat_movimentacao", "vlr_movimentacao",
        "dsc_ato_cancelamento", "dat_ato_cancelamento", "dsc_justificativa",
    ],
    "remessaMunicipio": ["cod_municipio", "nom_municipio", "tpo_remessa", "num_ano_referencia", "num_mes_referencia", "dsc_situacao"],
}


def caminho_zip(ano: int, categoria: str) -> Path:
    return BRUTOS_TCE / f"SICOM.{ano}.{COD_IBGE}.{categoria}.zip"


# ----------------------------------------------------------------------------- leitura

def _ajustar_linha(linha: list[str], n: int) -> list[str]:
    if len(linha) == n:
        return linha
    if len(linha) < n:
        return linha + [""] * (n - len(linha))
    excedente = linha[n:]
    if all(c.strip() in ("", "-") for c in excedente):
        return linha[:n]
    # Campo vazio a mais no meio da linha (ex.: respLicitacao): remove vazios até alinhar.
    nova = list(linha)
    i = 6
    while len(nova) > n and i < len(nova):
        if nova[i].strip() == "":
            del nova[i]
        else:
            i += 1
    if len(nova) > n:
        nova = nova[: n - 1] + [";".join(nova[n - 1:])]
    return nova


def _tipar(df: pd.DataFrame) -> pd.DataFrame:
    for coluna in df.columns:
        if coluna.startswith("vlr_"):
            df[coluna] = pd.to_numeric(df[coluna].str.replace(",", ".", regex=False), errors="coerce").fillna(0.0)
        elif coluna.startswith("dat_"):
            df[coluna] = pd.to_datetime(df[coluna].str.strip(), format="%Y%m%d", errors="coerce")
        elif df[coluna].dtype == object:
            df[coluna] = df[coluna].str.strip()
    for origem, destino in (("num_anoexercicio", "ano"), ("num_ano_referencia", "ano"),
                            ("num_mesexercicio", "mes"), ("num_mes_referencia", "mes")):
        if origem in df.columns and destino not in df.columns:
            df[destino] = pd.to_numeric(df[origem], errors="coerce").astype("Int64")
    return df


def _ler_csv(texto: str, tabela: str, cabecalhos_do_zip: dict[str, list[str]]) -> pd.DataFrame:
    linhas = [l for l in texto.splitlines() if l.strip()]
    if not linhas:
        return pd.DataFrame()
    leitor = list(csv.reader(linhas, delimiter=";", quoting=csv.QUOTE_NONE))
    cabecalho = [c.strip() for c in leitor[0]]
    corpo = leitor[1:]
    aviso = ""
    if corpo:
        tamanho_modal = Counter(len(l) for l in corpo).most_common(1)[0][0]
        corrigido = CABECALHOS_CORRIGIDOS.get(tabela)
        if corrigido and tamanho_modal == len(corrigido):
            cabecalho = corrigido
        elif abs(tamanho_modal - len(cabecalho)) > 2:
            # Arquivo publicado com o conteúdo de outra tabela (ex.: licitacao de 2025 com leiaute de dispensa).
            for outra, cab in cabecalhos_do_zip.items():
                if outra != tabela and len(cab) == tamanho_modal:
                    aviso = (f"O arquivo '{tabela}' publicado pelo TCE-MG contém registros no leiaute de '{outra}' "
                             "(inconsistência da publicação). Os registros foram lidos com esse leiaute.")
                    cabecalho = cab
                    break
    n = len(cabecalho)
    df = pd.DataFrame([_ajustar_linha(l, n) for l in corpo], columns=cabecalho, dtype=str)
    df = _tipar(df)
    if aviso:
        df.attrs["aviso"] = aviso
    return df


@lru_cache(maxsize=512)
def _ler_zip(caminho: str, mtime: float, tabela: str) -> pd.DataFrame:
    with zipfile.ZipFile(caminho) as zf:
        nomes = {PADRAO_CSV.search(n).group(3): n for n in zf.namelist() if PADRAO_CSV.search(n)}
        if tabela not in nomes:
            return pd.DataFrame()
        cabecalhos = {}
        for t, nome in nomes.items():
            with zf.open(nome) as f:
                primeira = f.readline().decode("utf-8", errors="replace").strip()
            cabecalhos[t] = [c.strip() for c in primeira.split(";")]
        bruto = zf.read(nomes[tabela])
    try:
        texto = bruto.decode("utf-8")
    except UnicodeDecodeError:
        texto = bruto.decode("latin-1")
    return _ler_csv(texto, tabela, cabecalhos)


def ler(ano: int, categoria: str, tabela: str) -> pd.DataFrame:
    """Lê uma tabela (CSV) de um pacote do SICOM. Ex.: ler(2026, 'receita', 'receita')."""
    caminho = caminho_zip(ano, categoria)
    if not caminho.exists():
        return pd.DataFrame()
    df = _ler_zip(str(caminho), caminho.stat().st_mtime, tabela)
    copia = df.copy()
    copia.attrs = dict(df.attrs)
    return copia


def ler_anos(anos, categoria: str, tabela: str) -> pd.DataFrame:
    partes = [ler(a, categoria, tabela) for a in anos]
    partes = [p for p in partes if not p.empty]
    if not partes:
        return pd.DataFrame()
    avisos = [p.attrs.get("aviso") for p in partes if p.attrs.get("aviso")]
    df = pd.concat(partes, ignore_index=True)
    if avisos:
        df.attrs["aviso"] = " ".join(avisos)
    return df


def tabelas(ano: int, categoria: str) -> list[str]:
    caminho = caminho_zip(ano, categoria)
    if not caminho.exists():
        return []
    with zipfile.ZipFile(caminho) as zf:
        return [PADRAO_CSV.search(n).group(3) for n in zf.namelist() if PADRAO_CSV.search(n)]


# ----------------------------------------------------------------------------- manifesto e inventário

def manifesto() -> dict:
    try:
        return json.loads(ARQ_MANIFESTO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"arquivos": {}}


def _salvar_manifesto(dados: dict) -> None:
    ARQ_MANIFESTO.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def data_publicacao_tce(ano: int, categoria: str | None = None) -> datetime | None:
    """Data em que o TCE-MG atualizou o pacote no portal (informada pelo favorito de download)."""
    arquivos = manifesto().get("arquivos", {})
    datas = []
    for chave, info in arquivos.items():
        a, c = chave.split("/")
        if int(a) == ano and (categoria is None or c == categoria) and info.get("dataAtualizacao"):
            datas.append(datetime.fromisoformat(info["dataAtualizacao"]))
    return max(datas) if datas else None


def inventario() -> pd.DataFrame:
    info = manifesto().get("arquivos", {})
    linhas = []
    for ano in ANOS:
        for categoria, rotulo in CATEGORIAS_TCE.items():
            caminho = caminho_zip(ano, categoria)
            item = info.get(f"{ano}/{categoria}", {})
            linhas.append({
                "Exercício": ano,
                "Aba do portal": rotulo,
                "Arquivo": caminho.name,
                "Disponível": caminho.exists(),
                "Tamanho (KB)": round(caminho.stat().st_size / 1024, 1) if caminho.exists() else None,
                "Publicado pelo TCE em": item.get("dataAtualizacao"),
                "Importado em": datetime.fromtimestamp(caminho.stat().st_mtime).isoformat(timespec="minutes") if caminho.exists() else None,
            })
    return pd.DataFrame(linhas)


def remessas(ano: int) -> pd.DataFrame:
    """Situação das remessas do Acompanhamento Mensal (AM) segundo o pacote 'orgao'."""
    df = ler(ano, "orgao", "remessaMunicipio")
    if df.empty:
        return df
    df = df.sort_values("mes")
    return df[["ano", "mes", "tpo_remessa", "dsc_situacao"]].reset_index(drop=True)


def ultimo_mes_enviado(ano: int) -> int:
    df = remessas(ano)
    if not df.empty and "dsc_situacao" in df.columns:
        enviados = df[df["dsc_situacao"].str.upper().str.startswith("ENVIADO")]
        if not enviados.empty:
            return int(enviados["mes"].max())
    receita = ler(ano, "receita", "receita")
    return int(receita["mes"].max()) if not receita.empty else 0


# ----------------------------------------------------------------------------- importação

def _sha256(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def _valida_pacote(dados: bytes, ano: int, categoria: str) -> None:
    with zipfile.ZipFile(io.BytesIO(dados)) as zf:
        total = sum(i.file_size for i in zf.infolist())
        if total > TAMANHO_MAXIMO:
            raise ValueError("pacote grande demais")
        esperados = [n for n in zf.namelist() if n.startswith(f"{ano}.{COD_IBGE}.{categoria}.") and n.endswith(".csv")]
        if not esperados:
            raise ValueError("o ZIP não contém os CSVs esperados do SICOM")


def _extrair_de_pacote_geral(caminho: Path) -> dict[tuple[int, str], bytes]:
    """Extrai de um pacote 'todos os municípios' (aba Downloads do portal) apenas os dados de Viçosa."""
    achados: dict[tuple[int, str], bytes] = {}
    with zipfile.ZipFile(caminho) as zf:
        if sum(i.file_size for i in zf.infolist()) > 20 * TAMANHO_MAXIMO:
            raise ValueError("pacote grande demais")
        csvs: dict[tuple[int, str], dict[str, bytes]] = {}
        for nome in zf.namelist():
            base = nome.rsplit("/", 1)[-1]
            m = PADRAO_ZIP.match(base)
            if m:
                achados[(int(m.group(1)), m.group(2).lower())] = zf.read(nome)
                continue
            m = PADRAO_CSV.search(nome)
            if m:
                csvs.setdefault((int(m.group(1)), m.group(2).lower()), {})[base] = zf.read(nome)
        for chave, membros in csvs.items():
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as novo:
                for base, conteudo in membros.items():
                    novo.writestr(base, conteudo)
            achados.setdefault(chave, buffer.getvalue())
    return achados


def _mover_para_processados(arquivo: Path) -> None:
    PROCESSADOS.mkdir(parents=True, exist_ok=True)
    destino = PROCESSADOS / f"{datetime.now():%Y%m%d-%H%M%S}_{arquivo.name}"
    shutil.move(str(arquivo), destino)


def importar_novos(verificar_downloads: bool | None = None) -> dict:
    """Importa pacotes do SICOM encontrados em dados/entrada e (opcionalmente) em ~/Downloads."""
    if verificar_downloads is None:
        verificar_downloads = bool(carregar_parametros().get("verificar_pasta_downloads", True))
    pastas = [ENTRADA]
    if verificar_downloads and not NAVEGADOR and PASTA_DOWNLOADS.exists():
        pastas.append(PASTA_DOWNLOADS)

    candidatos: dict[tuple[int, str], tuple[float, Path | None, bytes | None]] = {}
    manifestos: list[Path] = []
    origens: list[Path] = []
    resultado = {"importados": [], "sem_alteracao": [], "erros": []}

    for pasta in pastas:
        try:
            conteudo_pasta = sorted(pasta.iterdir())
        except PermissionError:
            # O macOS protege a pasta Downloads de processos em segundo plano (serviço do painel).
            resultado["erros"].append(
                f"sem permissão para ler {pasta}. Conceda 'Acesso Total ao Disco' ao Python em Ajustes do Sistema → "
                "Privacidade e Segurança, ou envie os arquivos pela aba Atualização de dados")
            continue
        for arquivo in conteudo_pasta:
            if not arquivo.is_file():
                continue
            m = PADRAO_ZIP.match(arquivo.name)
            if m:
                chave = (int(m.group(1)), m.group(2).lower())
                mtime = arquivo.stat().st_mtime
                if chave not in candidatos or mtime > candidatos[chave][0]:
                    candidatos[chave] = (mtime, arquivo, None)
                origens.append(arquivo)
            elif PADRAO_MANIFESTO.match(arquivo.name):
                manifestos.append(arquivo)
            elif pasta == ENTRADA and arquivo.suffix.lower() == ".zip":
                try:
                    for chave, conteudo in _extrair_de_pacote_geral(arquivo).items():
                        candidatos[chave] = (arquivo.stat().st_mtime, None, conteudo)
                    origens.append(arquivo)
                except (zipfile.BadZipFile, ValueError) as erro:
                    resultado["erros"].append(f"{arquivo.name}: {erro}")

    for (ano, categoria), (_, arquivo, conteudo) in sorted(candidatos.items()):
        rotulo = f"{ano}/{categoria}"
        if categoria not in CATEGORIAS_TCE:
            continue
        try:
            dados = conteudo if conteudo is not None else arquivo.read_bytes()
            _valida_pacote(dados, ano, categoria)
            destino = caminho_zip(ano, categoria)
            if destino.exists() and _sha256(destino.read_bytes()) == _sha256(dados):
                resultado["sem_alteracao"].append(rotulo)
                continue
            if destino.exists():
                HISTORICO.mkdir(parents=True, exist_ok=True)
                shutil.copy2(destino, HISTORICO / f"{datetime.now():%Y%m%d-%H%M%S}_{destino.name}")
            destino.write_bytes(dados)
            resultado["importados"].append(rotulo)
        except (OSError, zipfile.BadZipFile, ValueError) as erro:
            resultado["erros"].append(f"{rotulo}: {erro}")

    dados_manifesto = manifesto()
    for arquivo in manifestos:
        try:
            novo = json.loads(arquivo.read_text(encoding="utf-8"))
            for item in novo.get("arquivos", []):
                chave = f"{item['ano']}/{item['categoria']}"
                dados_manifesto.setdefault("arquivos", {})[chave] = {
                    "seqArquivo": item.get("seqArquivo"),
                    "dataAtualizacao": item.get("dataAtualizacao"),
                    "baixado_em": novo.get("gerado_em"),
                }
            origens.append(arquivo)
        except (OSError, ValueError, KeyError) as erro:
            resultado["erros"].append(f"{arquivo.name}: {erro}")
    _salvar_manifesto(dados_manifesto)

    for arquivo in origens:
        if arquivo.exists():
            try:
                _mover_para_processados(arquivo)
            except OSError as erro:
                resultado["erros"].append(f"{arquivo.name}: {erro}")

    _ler_zip.cache_clear()
    if candidatos or manifestos or resultado["erros"]:
        mensagem = (f"{len(resultado['importados'])} pacote(s) importado(s), "
                    f"{len(resultado['sem_alteracao'])} sem alteração")
        if resultado["erros"]:
            mensagem += f", {len(resultado['erros'])} erro(s): " + "; ".join(resultado["erros"][:3])
        estado.registrar("tce_sicom", ok=not resultado["erros"], mensagem=mensagem)
    return resultado


_embutido_verificado = False


def instalar_pacote_embutido() -> list[str]:
    """Versão web: copia para o armazenamento do aparelho os pacotes embutidos que forem mais novos.

    Pacotes importados pelo usuário com data de publicação do TCE mais recente são mantidos.
    """
    global _embutido_verificado
    if _embutido_verificado or not PACOTE_EMBUTIDO.exists():
        return []
    _embutido_verificado = True
    try:
        embutido = json.loads((PACOTE_EMBUTIDO / "manifesto.json").read_text(encoding="utf-8")).get("arquivos", {})
    except (OSError, ValueError):
        embutido = {}
    local = manifesto()
    copiados = []
    for arquivo in sorted(PACOTE_EMBUTIDO.glob("SICOM.*.zip")):
        m = PADRAO_ZIP.match(arquivo.name)
        if not m:
            continue
        ano, categoria = int(m.group(1)), m.group(2).lower()
        chave = f"{ano}/{categoria}"
        data_embutida = (embutido.get(chave) or {}).get("dataAtualizacao") or ""
        data_local = (local.get("arquivos", {}).get(chave) or {}).get("dataAtualizacao") or ""
        destino = caminho_zip(ano, categoria)
        if destino.exists() and data_embutida <= data_local:
            continue
        destino.write_bytes(arquivo.read_bytes())
        if chave in embutido:
            local.setdefault("arquivos", {})[chave] = embutido[chave]
        copiados.append(chave)
    if copiados:
        _salvar_manifesto(local)
        _ler_zip.cache_clear()
        estado.registrar("tce_sicom", ok=True, mensagem=f"{len(copiados)} pacote(s) instalado(s) com a versão web")
    return copiados
