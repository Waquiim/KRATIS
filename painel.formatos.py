"""Formatação numérica no padrão brasileiro."""
from __future__ import annotations

import math

MESES_EXTENSO = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
                 "outubro", "novembro", "dezembro"]


def _vazio(valor) -> bool:
    return valor is None or (isinstance(valor, float) and math.isnan(valor))


def numero(valor, casas: int = 2) -> str:
    if _vazio(valor):
        return "–"
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


def brl(valor, casas: int = 2) -> str:
    return "–" if _vazio(valor) else f"R$ {numero(valor, casas)}"


def brl_compacto(valor) -> str:
    if _vazio(valor):
        return "–"
    absoluto = abs(valor)
    if absoluto >= 1e9:
        return f"R$ {numero(valor / 1e9, 2)} bi"
    if absoluto >= 1e6:
        return f"R$ {numero(valor / 1e6, 2)} mi"
    if absoluto >= 1e3:
        return f"R$ {numero(valor / 1e3, 1)} mil"
    return brl(valor)


def pct(valor, casas: int = 2) -> str:
    return "–" if _vazio(valor) else f"{numero(valor, casas)}%"


def periodo(aaaamm: int) -> str:
    return f"{MESES_EXTENSO[aaaamm % 100 - 1]}/{aaaamm // 100}"


def mes_ano(ano: int, mes: int) -> str:
    return f"{MESES_EXTENSO[mes - 1]}/{ano}"
