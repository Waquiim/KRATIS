"""Atualização do painel: importa os pacotes do SICOM baixados do portal de dados abertos do TCE-MG.

Uso (terminal, na pasta do projeto):
    .venv/bin/python -m painel.atualizar                  # importa de dados/entrada e da pasta Downloads
    .venv/bin/python -m painel.atualizar --sem-downloads  # importa só de dados/entrada

O agendamento diário no macOS é instalado por ferramentas/agendar_atualizacao_macos.sh.
"""
from __future__ import annotations

import argparse
import sys
import traceback
from datetime import datetime

from . import estado
from .config import LOGS, NAVEGADOR
from .fontes import tce_sicom

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None
if NAVEGADOR:  # versão web: um único processo, sem travas de arquivo
    fcntl = None

TRAVA = LOGS / "atualizacao.lock"


def precisa_atualizar(horas: float = 20) -> bool:
    item = estado.ler().get("tce_sicom", {})
    quando = item.get("ultima_tentativa")
    if not quando:
        return True
    return (datetime.now() - datetime.fromisoformat(quando)).total_seconds() / 3600 >= horas


def em_andamento() -> bool:
    if fcntl is None or not TRAVA.exists():
        return False
    with open(TRAVA, "a") as arquivo:
        try:
            fcntl.flock(arquivo, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(arquivo, fcntl.LOCK_UN)
            return False
        except BlockingIOError:
            return True


def executar(verificar_downloads: bool | None = None, log=print, **_) -> dict:
    TRAVA.parent.mkdir(parents=True, exist_ok=True)
    with open(TRAVA, "a") as arquivo_trava:
        if fcntl is not None:
            try:
                fcntl.flock(arquivo_trava, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                log("Já existe uma atualização em andamento.")
                return {"em_andamento": True}
        try:
            resultado = tce_sicom.importar_novos(verificar_downloads)
            mensagem = (f"{len(resultado['importados'])} pacote(s) importado(s), "
                        f"{len(resultado['sem_alteracao'])} sem alteração, {len(resultado['erros'])} erro(s)")
            if not (resultado["importados"] or resultado["sem_alteracao"] or resultado["erros"]):
                mensagem = "Nenhum pacote novo do SICOM encontrado"
            estado.registrar("tce_sicom", ok=not resultado["erros"],
                             mensagem=mensagem + ("; " + "; ".join(resultado["erros"][:2]) if resultado["erros"] else ""))
            log(f"[{datetime.now():%H:%M:%S}] {mensagem}")
            return resultado
        except Exception as erro:
            estado.registrar("tce_sicom", ok=False, mensagem=f"Erro inesperado: {str(erro)[:200]}")
            log(f"[{datetime.now():%H:%M:%S}] ERRO {erro}\n{traceback.format_exc()}")
            return {"erro": str(erro)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Importa os pacotes do SICOM do Painel Contábil de Viçosa/MG.")
    parser.add_argument("--sem-downloads", action="store_true", help="não procura pacotes na pasta Downloads")
    args = parser.parse_args()
    arquivo_log = LOGS / f"atualizacao_{datetime.now():%Y-%m}.log"

    def log(mensagem: str) -> None:
        print(mensagem, flush=True)
        with open(arquivo_log, "a", encoding="utf-8") as f:
            f.write(mensagem + "\n")

    log(f"=== Atualização iniciada em {datetime.now():%d/%m/%Y %H:%M:%S} ===")
    resumo = executar(verificar_downloads=False if args.sem_downloads else None, log=log)
    return 0 if not resumo.get("em_andamento") else 1


if __name__ == "__main__":
    sys.exit(main())
