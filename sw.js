// Service worker do Painel Contábil de Viçosa: guarda o painel no aparelho para abrir sem internet.
const VERSAO = "20261028-2115-e5d556ae";
const CACHE = "painel-vicosa-" + VERSAO;
const LOCAIS = ["./", "index.html", "manifest.webmanifest", "icone-512.png", "icone-192.png", "apple-touch-icon.png", "app/app.py?v=20261028-2115-e5d556ae", "app/assets/logo_vicosa.jpg?v=20261028-2115-e5d556ae", "app/ferramentas/favorito_sicom_vicosa.js?v=20261028-2115-e5d556ae", "app/pacote_sicom/SICOM.2024.3171303.contrato.zip?v=20261028-2115-e5d556ae", "app/pacote_sicom/SICOM.2024.3171303.desp_pessoal.zip?v=20261028-2115-e5d556ae", "app/pacote_sicom/SICOM.2024.3171303.despesa.zip?v=20261028-2115-e5d556ae", "app/pacote_sicom/SICOM.2024.3171303.educacao.zip?v=20261028-2115-e5d556ae", "app/pacote_sicom/SICOM.2024.3171303.empenho.zip?v=20261028-2115-e5d556ae", "app/pacote_sicom/SICOM.2024.3171303.frota.zip?v=20261028-2115-e5d556ae", "app/pacote_sicom/SICOM.2024.3171303.licitacao.zip?v=20261028-2115-e5d556ae", "app/pacote_sicom/SICOM.2024.3171303.orgao.zip?v=20261028-2115-e5d556ae", "app/pacote_sicom/SICOM.2024.3171303.receita.zip?v=20261028-2115-e5d556ae", "app/pacote_sicom/SICOM.2024.3171303.saude.zip?v=20261028-2115-e5d556ae", "app/pacote_sicom/SICOM.2025.3171303.contrato.zip?v=20261028-2115-e5d556ae", "app/pacote_sicom/SICOM.2025.3171303.desp_pessoal.zip?v=20261028-2115-e5d556ae", "app/pacote_sicom/SICOM.2025.3171303.despesa.zip?v=20261028-2115-e5d556ae", "app/pacote_sicom/SICOM.2025.3171303.educacao.zip?v=20261028-2115-e5d556ae", "app/pacote_sicom/SICOM.2025.3171303.empenho.zip?v=20261028-2115-e5d556ae", "app/pacote_sicom/SICOM.2025.3171303.frota.zip?v=20261028-2115-e5d556ae", "app/pacote_sicom/SICOM.2025.3171303.licitacao.zip?v=20261028-2115-e5d556ae", "app/pacote_sicom/SICOM.2025.3171303.orgao.zip?v=20261028-2115-e5d556ae", "app/pacote_sicom/SICOM.2025.3171303.receita.zip?v=20261028-2115-e5d556ae", "app/pacote_sicom/SICOM.2025.3171303.saude.zip?v=20261028-2115-e5d556ae", "app/pacote_sicom/SICOM.2026.3171303.contrato.zip?v=20261028-2115-e5d556ae", "app/pacote_sicom/SICOM.2026.3171303.desp_pessoal.zip?v=20261028-2115-e5d556ae", "app/pacote_sicom/SICOM.2026.3171303.despesa.zip?v=20261028-2115-e5d556ae", "app/pacote_sicom/SICOM.2026.3171303.educacao.zip?v=20261028-2115-e5d556ae", "app/pacote_sicom/SICOM.2026.3171303.empenho.zip?v=20261028-2115-e5d556ae", "app/pacote_sicom/SICOM.2026.3171303.frota.zip?v=20261028-2115-e5d556ae", "app/pacote_sicom/SICOM.2026.3171303.licitacao.zip?v=20261028-2115-e5d556ae", "app/pacote_sicom/SICOM.2026.3171303.orgao.zip?v=20261028-2115-e5d556ae", "app/pacote_sicom/SICOM.2026.3171303.receita.zip?v=20261028-2115-e5d556ae", "app/pacote_sicom/SICOM.2026.3171303.saude.zip?v=20261028-2115-e5d556ae", "app/pacote_sicom/manifesto.json?v=20261028-2115-e5d556ae", "app/painel/atualizar.py?v=20261028-2115-e5d556ae", "app/painel/config.py?v=20261028-2115-e5d556ae", "app/painel/consistencia.py?v=20261028-2115-e5d556ae", "app/painel/criticas.py?v=20261028-2115-e5d556ae", "app/painel/dados.py?v=20261028-2115-e5d556ae", "app/painel/estado.py?v=20261028-2115-e5d556ae", "app/painel/fontes/init__.py?v=20261028-2115-e5d556ae", "app/painel/fontes/tce_sicom.py?v=20261028-2115-e5d556ae", "app/painel/formatos.py?v=20261028-2115-e5d556ae", "app/painel/indicadores.py?v=20261028-2115-e5d556ae", "app/painel/init__.py?v=20261028-2115-e5d556ae", "app/painel/ui/comum.py?v=20261028-2115-e5d556ae", "app/painel/ui/init__.py?v=20261028-2115-e5d556ae", "app/painel/ui/navegacao.py?v=20261028-2115-e5d556ae", "app/painel/ui/paginas/atualizacao.py?v=20261028-2115-e5d556ae", "app/painel/ui/paginas/comparativo.py?v=20261028-2115-e5d556ae", "app/painel/ui/paginas/consistencia.py?v=20261028-2115-e5d556ae", "app/painel/ui/paginas/contratos.py?v=20261028-2115-e5d556ae", "app/painel/ui/paginas/criticas.py?v=20261028-2115-e5d556ae", "app/painel/ui/paginas/despesas.py?v=20261028-2115-e5d556ae", "app/painel/ui/paginas/educacao.py?v=20261028-2115-e5d556ae", "app/painel/ui/paginas/empenhos.py?v=20261028-2115-e5d556ae", "app/painel/ui/paginas/init__.py?v=20261028-2115-e5d556ae", "app/painel/ui/paginas/licitacoes.py?v=20261028-2115-e5d556ae", "app/painel/ui/paginas/orgaos.py?v=20261028-2115-e5d556ae", "app/painel/ui/paginas/pessoal.py?v=20261028-2115-e5d556ae", "app/painel/ui/paginas/receitas.py?v=20261028-2115-e5d556ae", "app/painel/ui/paginas/saude.py?v=20261028-2115-e5d556ae", "app/painel/ui/paginas/veiculos.py?v=20261028-2115-e5d556ae", "app/painel/ui/paginas/visao_geral.py?v=20261028-2115-e5d556ae", "app/parametros_padrao.json?v=20261028-2115-e5d556ae", "app/streamlit/config.toml?v=20261028-2115-e5d556ae"];
// Arquivos de versão fixa (stlite, Pyodide, pacotes Python): guardados no primeiro uso.
const IMUTAVEIS = ["cdn.jsdelivr.net", "files.pythonhosted.org"];

self.addEventListener("install", (evento) => {
  evento.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(LOCAIS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (evento) => {
  evento.waitUntil(
    caches.keys()
      .then((nomes) => Promise.all(nomes.filter((n) => n.startsWith("painel-vicosa-") && n !== CACHE).map((n) => caches.delete(n))))
      .then(() => self.clients.claim())
  );
});

async function primeiroCache(pedido) {
  const guardado = await caches.match(pedido);
  if (guardado) return guardado;
  const resposta = await fetch(pedido);
  if (resposta.ok) (await caches.open(CACHE)).put(pedido, resposta.clone());
  return resposta;
}

async function primeiroRede(pedido) {
  try {
    const resposta = await fetch(pedido);
    if (resposta.ok) (await caches.open(CACHE)).put(pedido, resposta.clone());
    return resposta;
  } catch (erro) {
    const guardado = await caches.match(pedido);
    if (guardado) return guardado;
    throw erro;
  }
}

// O painel põe o nome da aba no endereço (ex.: /atualizacao): toda navegação abre a mesma página.
async function paginaPrincipal(pedido) {
  try {
    const resposta = await fetch(pedido);
    if (resposta.ok) {
      (await caches.open(CACHE)).put("index.html", resposta.clone());
      return resposta;
    }
  } catch (erro) { /* sem internet */ }
  return (await caches.match("index.html")) || fetch("index.html");
}

self.addEventListener("fetch", (evento) => {
  const pedido = evento.request;
  if (pedido.method !== "GET") return;
  const url = new URL(pedido.url);
  if (url.protocol !== "https:" && url.origin !== self.location.origin) return;
  if (pedido.mode === "navigate") {
    // A página principal vem da rede quando há internet (pega versões novas) e do aparelho quando não há.
    evento.respondWith(paginaPrincipal(pedido));
  } else if (url.origin === self.location.origin || IMUTAVEIS.includes(url.hostname)) {
    evento.respondWith(primeiroCache(pedido));
  } else {
    evento.respondWith(primeiroRede(pedido));
  }
});
