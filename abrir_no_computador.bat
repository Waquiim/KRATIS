@echo off
rem Abre a versao web do Painel Contabil de Vicosa neste computador (duplo clique).
cd /d "%~dp0"
start "" /min python servidor_local.py 8502
timeout /t 2 >nul
start "" http://localhost:8502/
