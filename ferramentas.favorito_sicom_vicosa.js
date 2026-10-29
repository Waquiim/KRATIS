// Favorito "⬇ SICOM Viçosa" – baixa os pacotes do SICOM de Viçosa no portal de dados abertos do TCE-MG.
// Uso: abra https://dadosabertos.tce.mg.gov.br no seu navegador, aguarde a página carregar
// (a verificação de acesso do TCE-MG acontece normalmente) e clique no favorito.
// O favorito usa a sua própria sessão do portal: baixa os 10 pacotes (abas) de Viçosa dos três
// últimos exercícios e um manifesto com a data de publicação de cada pacote. O painel importa
// esses arquivos da pasta Downloads.
(async () => {
  const PORTAL = 'dadosabertos.tce.mg.gov.br';
  if (location.hostname !== PORTAL) {
    alert('Abra https://' + PORTAL + ', aguarde a página carregar e clique novamente no favorito.');
    return;
  }
  const API = 'https://arabiasaudita.tce.mg.gov.br:8443/TCEMG-proxy-web/publico/apimoci/dados-abertos/dadosAbertos/';
  const token = () => localStorage.getItem('tokenRequestAuthorizationProxy') || localStorage.getItem('tokenAuthorizationProxy');
  if (!token()) {
    alert('O portal ainda não concluiu a verificação de acesso. Aguarde alguns segundos (ou entre em "Jurisdicionado") e tente de novo.');
    return;
  }
  const obter = async (caminho) => {
    const resposta = await fetch(API + caminho, { headers: { AuthorizationProxy: 'token ' + token() } });
    const novo = resposta.headers.get('AuthorizationProxy');
    if (novo) localStorage.setItem('tokenRequestAuthorizationProxy', novo);
    if (!resposta.ok) throw new Error('HTTP ' + resposta.status);
    return resposta.json();
  };
  const salvar = (blob, nome) => {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = nome;
    document.body.appendChild(a);
    a.click();
    a.remove();
  };
  const caixa = document.createElement('div');
  caixa.style.cssText = 'position:fixed;z-index:99999;top:16px;right:16px;background:#fff;border:3px solid #B11E25;' +
    'padding:14px 18px;font:14px sans-serif;color:#262626;border-radius:8px;box-shadow:0 4px 18px rgba(0,0,0,.25);max-width:380px';
  document.body.appendChild(caixa);
  const aviso = (texto) => { caixa.textContent = 'Painel Viçosa – ' + texto; };
  const atual = new Date().getFullYear();
  const anos = [atual, atual - 1, atual - 2];
  const categorias = ['orgao', 'receita', 'despesa', 'empenho', 'desp_pessoal', 'saude', 'educacao', 'licitacao', 'contrato', 'frota'];
  const manifesto = { municipio: 'Viçosa', cod_ibge: 3171303, gerado_em: new Date().toISOString(), arquivos: [] };
  const erros = [];
  let n = 0;
  for (const ano of anos) {
    for (const categoria of categorias) {
      n += 1;
      aviso(`baixando ${categoria} de ${ano} (${n}/${anos.length * categorias.length})…`);
      try {
        const detalhe = await obter(`buscarDetalhesCategorias?municipio=${encodeURIComponent('Viçosa')}&categoria=${categoria}&origem=SICOM&exercicio=${ano}`);
        for (const arquivo of detalhe.arquivoList || []) {
          const conteudo = await obter('baixarArquivo/' + arquivo.seqArquivo);
          const bytes = Uint8Array.from(atob(conteudo.bytesConteudo), (c) => c.charCodeAt(0));
          salvar(new Blob([bytes], { type: 'application/zip' }), conteudo.nomeArquivo);
          manifesto.arquivos.push({ ano, categoria, seqArquivo: arquivo.seqArquivo, dataAtualizacao: detalhe.dataAtualizacao,
            arquivo: conteudo.nomeArquivo });
          await new Promise((r) => setTimeout(r, 2500));
        }
      } catch (erro) {
        erros.push(`${categoria}/${ano}: ${erro.message}`);
      }
    }
  }
  salvar(new Blob([JSON.stringify(manifesto, null, 1)], { type: 'application/json' }), 'SICOM.3171303.manifesto.json');
  aviso(`concluído: ${manifesto.arquivos.length} pacote(s) salvo(s) na pasta Downloads` +
    (erros.length ? ` · ${erros.length} erro(s): ${erros.join('; ')}` : '') +
    '. Volte ao painel e clique em "Importar arquivos baixados".');
  setTimeout(() => caixa.remove(), 60000);
})();
