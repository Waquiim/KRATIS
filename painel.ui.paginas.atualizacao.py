"""Aba Atualização de dados: importação dos pacotes do SICOM (portal do TCE-MG) e parâmetros das críticas."""
from __future__ import annotations

import html
from datetime import datetime
from urllib.parse import quote

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from ... import estado
from ...atualizar import em_andamento, executar
from ...config import (ENTRADA, EXERCICIO_ATUAL, NAVEGADOR, RAIZ, URL_PORTAL_TCE, carregar_parametros,
                        salvar_parametros)
from ...fontes import tce_sicom
from .. import comum

ROTULOS = {"tce_sicom": "SICOM (portal de dados abertos do TCE-MG)"}


def _favorito() -> str:
    linhas = (RAIZ / "ferramentas" / "favorito_sicom_vicosa.js").read_text(encoding="utf-8").splitlines()
    codigo = " ".join(l.strip() for l in linhas if l.strip() and not l.strip().startswith("//"))
    return "javascript:" + quote(codigo, safe="(){}[];,.=>'+-*/!?&|:$`")


def _situacao() -> None:
    est = estado.ler()
    linhas = []
    for fonte, rotulo in ROTULOS.items():
        item = est.get(fonte, {})
        quando = item.get("ultima_tentativa")
        carga = tce_sicom.data_publicacao_tce(EXERCICIO_ATUAL)
        linhas.append({"Fonte": rotulo,
                       "Publicação do TCE (exercício atual)": carga.strftime("%d/%m/%Y") if carga else "—",
                       "Última verificação": datetime.fromisoformat(quando).strftime("%d/%m/%Y %H:%M") if quando else "—",
                       "Situação": "OK" if item.get("ok", False) else ("Falha" if item else "—"),
                       "Mensagem": item.get("mensagem", "")})
    st.dataframe(pd.DataFrame(linhas), width="stretch", hide_index=True, key="atu-situacao")


def pagina() -> None:
    comum.cabecalho("Atualização de dados", "Importação dos pacotes do SICOM publicados no portal do TCE-MG e parâmetros das críticas")

    if NAVEGADOR:
        comum.secao("Situação dos dados", "Fonte única: portal de dados abertos do TCE-MG. Nesta versão o painel roda inteiro "
                                          "dentro do navegador e os dados ficam guardados neste aparelho.")
    else:
        comum.secao("Situação dos dados", "Fonte única: portal de dados abertos do TCE-MG. A pasta Downloads e a pasta "
                                          "dados/entrada são verificadas automaticamente uma vez por dia em busca de pacotes novos.")
    _situacao()
    if NAVEGADOR:
        pass
    elif em_andamento():
        st.info("Há uma atualização em andamento.", icon="🔄")
    elif st.button("🔄 Verificar pacotes novos agora", type="primary", key="atu-agora"):
        with st.status("Procurando pacotes do SICOM…", expanded=True) as caixa:
            executar(log=lambda mensagem: caixa.write(mensagem))
            caixa.update(label="Atualização concluída", state="complete")
        st.cache_data.clear()
        st.rerun()

    comum.secao("Pacotes do SICOM (portal de dados abertos do TCE-MG)")
    st.markdown(
        "O portal do TCE-MG libera os arquivos somente depois de uma verificação de acesso feita no navegador (reCAPTCHA). "
        "Por isso o download é feito por você, na sua própria sessão do portal, com um clique no favorito abaixo; "
        + ("depois envie os arquivos baixados no campo **Enviar arquivos** desta aba (no iPhone e no iPad eles ficam no app "
           "Arquivos, pasta Downloads)." if NAVEGADOR else "o painel importa os arquivos automaticamente da pasta **Downloads**."))
    passos = st.columns([2, 3])
    with passos[0]:
        st.markdown("**1. Instale o favorito** (uma vez): arraste o botão para a barra de favoritos do navegador.")
        alvo = html.escape(_favorito(), quote=True)
        components.html(
            f"""<div style="font-family:sans-serif;padding:6px 2px">
<a href="{alvo}" title="Arraste para a barra de favoritos"
   onclick="alert('Arraste este botão para a barra de favoritos e use-o na página do portal do TCE-MG.');return false;"
   style="display:inline-block;padding:10px 18px;background:#B11E25;color:#fff;border-radius:8px;text-decoration:none;font-weight:600;cursor:grab">
⬇ SICOM Viçosa</a></div>""", height=58)
        with st.expander("Não consegue arrastar? Crie o favorito manualmente"):
            st.markdown("Crie um favorito novo com o nome **SICOM Viçosa** e cole o texto abaixo no campo de endereço (URL). "
                        "No iPhone e no iPad: copie o texto, adicione qualquer página aos favoritos do Safari, toque em "
                        "**Editar** no favorito e substitua o endereço pelo texto copiado.")
            st.code(_favorito(), language=None, wrap_lines=True)
    with passos[1]:
        st.markdown(f"**2.** Abra o [portal de dados abertos do TCE-MG]({URL_PORTAL_TCE}) e aguarde carregar.  \n"
                    "**3.** Clique no favorito **⬇ SICOM Viçosa**: ele baixa os 10 pacotes (abas) de Viçosa dos três últimos "
                    "exercícios e um manifesto com a data de publicação (o navegador pode pedir para permitir vários downloads).  \n"
                    + ("**4.** Volte aqui e envie os arquivos baixados no campo abaixo (pode selecionar todos de uma vez)."
                       if NAVEGADOR else
                       "**4.** Volte aqui e clique em **Importar arquivos baixados**. A importação também roda na atualização diária."))
        if not NAVEGADOR and st.button("📥 Importar arquivos baixados", key="atu-importar"):
            resultado = tce_sicom.importar_novos()
            if resultado["importados"]:
                st.success(f"{len(resultado['importados'])} pacote(s) novo(s) ou atualizado(s): {', '.join(resultado['importados'])}.")
            if resultado["sem_alteracao"]:
                st.info(f"{len(resultado['sem_alteracao'])} pacote(s) iguais aos já importados.")
            if resultado["erros"]:
                st.error("Erros: " + "; ".join(resultado["erros"]))
            if not any(resultado.values()):
                st.warning("Nenhum pacote do SICOM de Viçosa encontrado em Downloads ou em dados/entrada.")
            st.cache_data.clear()
    enviados = st.file_uploader(("Enviar arquivos: " if NAVEGADOR else "Ou envie aqui os arquivos baixados")
                                + " (ZIPs do SICOM, pacotes completos da aba Downloads do "
                                "portal ou o manifesto)", type=["zip", "json"], accept_multiple_files=True, key="atu-upload")
    if enviados and st.button("Importar arquivos enviados", key="atu-importar-upload"):
        for arquivo in enviados:
            (ENTRADA / arquivo.name).write_bytes(arquivo.getvalue())
        resultado = tce_sicom.importar_novos(verificar_downloads=False)
        st.success(f"Importados: {', '.join(resultado['importados']) or 'nenhum novo'}; sem alteração: "
                   f"{len(resultado['sem_alteracao'])}; erros: {'; '.join(resultado['erros']) or 'nenhum'}.")
        st.cache_data.clear()
    with st.expander("Pacotes disponíveis no painel"):
        comum.tabela(tce_sicom.inventario(), chave="atu-inventario")

    comum.secao("Parâmetros das críticas")
    parametros = carregar_parametros()
    with st.form("atu-parametros"):
        c = st.columns(3)
        limite = c[0].number_input("Limite de suplementação autorizado na LOA (% da despesa fixada)", min_value=0.0, max_value=100.0,
                                   value=float(parametros.get("limite_suplementacao_loa_pct") or 0.0), step=0.5,
                                   help="Deixe 0 se não quiser avaliar o limite.")
        lei = c[1].text_input("Número da lei da LOA", value=parametros.get("lei_loa_numero", ""),
                              help="Se vazio, o painel usa a lei mais citada nos decretos de suplementação.")
        downloads = bool(parametros.get("verificar_pasta_downloads", True))
        if not NAVEGADOR:
            downloads = c[2].toggle("Procurar pacotes do SICOM na pasta Downloads", value=downloads)
        c = st.columns(2)
        populacao = c[0].number_input("População do Município (faixa do art. 29-A da CF)", min_value=0,
                                      value=int(parametros.get("populacao") or 0), step=1,
                                      help="Estimativa populacional oficial (IBGE) usada apenas para o limite da Câmara.")
        tolerancia = c[1].number_input("Tolerância nos confrontos de consistência (R$)", min_value=0.0,
                                       value=float(parametros.get("tolerancia_consistencia_valor", 1.0)), step=1.0)
        limites = parametros["dispensa_limites"].get(str(EXERCICIO_ATUAL), {"obras": 0.0, "outros": 0.0, "norma": ""})
        c = st.columns(3)
        obras = c[0].number_input(f"Dispensa {EXERCICIO_ATUAL} – obras e engenharia (R$)", value=float(limites.get("obras", 0.0)), step=100.0)
        outros = c[1].number_input(f"Dispensa {EXERCICIO_ATUAL} – demais compras e serviços (R$)", value=float(limites.get("outros", 0.0)), step=100.0)
        norma = c[2].text_input("Norma de atualização dos valores", value=limites.get("norma", ""))
        if st.form_submit_button("Salvar parâmetros"):
            parametros.update({"limite_suplementacao_loa_pct": limite or None, "lei_loa_numero": lei.strip(),
                               "verificar_pasta_downloads": downloads, "populacao": int(populacao),
                               "tolerancia_consistencia_valor": tolerancia})
            parametros["dispensa_limites"][str(EXERCICIO_ATUAL)] = {"obras": obras, "outros": outros, "norma": norma}
            salvar_parametros(parametros)
            st.cache_data.clear()
            st.success("Parâmetros salvos.")

    if NAVEGADOR:
        comum.rodape()
        return
    comum.secao("Atualização automática diária")
    st.markdown(
        "Com o painel aberto, a verificação de pacotes novos roda sozinha uma vez por dia. Para verificar também com o painel "
        "fechado, instale o agendamento diário do macOS (06h30) executando no Terminal, dentro da pasta do projeto:")
    st.code("bash ferramentas/agendar_atualizacao_macos.sh", language="bash")
    st.markdown("Para remover o agendamento: `bash ferramentas/agendar_atualizacao_macos.sh --remover`. "
                "Registros de execução: pasta `dados/logs`.")
    comum.rodape()
