#!/bin/bash
# Abre a versão web do Painel Contábil de Viçosa neste computador (duplo clique no Finder).
cd "$(dirname "$0")"
PORTA=8502
if ! curl -s -o /dev/null "http://localhost:$PORTA/"; then
  python3 servidor_local.py "$PORTA" >/dev/null 2>&1 &
  sleep 1
fi
open "http://localhost:$PORTA/"
