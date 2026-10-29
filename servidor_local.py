"""Servidor local da versão web: entrega os arquivos desta pasta só para este computador.

Endereços das abas (ex.: /atualizacao) recebem a página principal, como no GitHub Pages.
Uso: python3 servidor_local.py [porta]
"""
import functools
import http.server
import os
import sys

PASTA = os.path.dirname(os.path.abspath(__file__))


class Pagina(http.server.SimpleHTTPRequestHandler):
    def send_head(self):
        caminho = self.translate_path(self.path)
        if not os.path.exists(caminho) and "." not in os.path.basename(self.path.split("?")[0]):
            self.path = "/index.html"
        return super().send_head()

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, *args):
        pass


porta = int(sys.argv[1]) if len(sys.argv) > 1 else 8502
servidor = http.server.ThreadingHTTPServer(("127.0.0.1", porta), functools.partial(Pagina, directory=PASTA))
print(f"Painel em http://localhost:{porta}/ (feche esta janela para encerrar)")
servidor.serve_forever()
