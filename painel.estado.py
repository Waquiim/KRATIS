"""Registro da última atualização de cada fonte (dados/estado.json)."""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime

from .config import ESTADO

_trava = threading.Lock()


def ler() -> dict:
    try:
        return json.loads(ESTADO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def registrar(fonte: str, ok: bool, mensagem: str = "", **extra) -> None:
    with _trava:
        estado = ler()
        item = estado.get(fonte, {})
        agora = datetime.now().isoformat(timespec="seconds")
        item.update({"ultima_tentativa": agora, "ok": ok, "mensagem": mensagem})
        if ok:
            item["ultima_atualizacao"] = agora
        item.update(extra)
        estado[fonte] = item
        temporario = ESTADO.with_suffix(".tmp")
        temporario.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporario, ESTADO)


def horas_desde_atualizacao(fonte: str) -> float | None:
    item = ler().get(fonte, {})
    quando = item.get("ultima_atualizacao")
    if not quando:
        return None
    return (datetime.now() - datetime.fromisoformat(quando)).total_seconds() / 3600
