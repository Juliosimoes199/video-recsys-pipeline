import os
import sys
import webbrowser
import http.server
import functools
import socketserver

from youtube_api import buscar_shorts, salvar_no_banco, DB_PATH


def gerar_pagina_html(videos, caminho="feed.html"):
    cards = "\n".join(f"""
        <div class="video-card">
            <h3>{v['titulo']}</h3>
            <p>{v['duracao']}s</p>
            <iframe width="360" height="640"
                src="https://www.youtube.com/embed/{v['id']}"
                frameborder="0" allow="autoplay; encrypted-media" allowfullscreen>
            </iframe>
        </div>
    """ for v in videos)

    html = f"""<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<title>Feed de Shorts</title>
<style>
  body {{ background:#000; color:#fff; font-family:sans-serif; display:flex; flex-direction:column; align-items:center; gap:40px; padding:20px; }}
  .video-card {{ text-align:center; }}
</style>
</head>
<body>
{cards}
</body>
</html>"""

    with open(caminho, "w", encoding="utf-8") as f:
        f.write(html)
    return os.path.abspath(caminho)


def servir_pagina(caminho, porta=8000):
    """Sobe um servidor HTTP local servindo o diretório do arquivo e abre no navegador.

    O YouTube recusa o embed (erro 153) quando a página é aberta via file://,
    então precisa vir de um http:// de verdade, mesmo que local.
    """
    diretorio = os.path.dirname(caminho)
    nome_arquivo = os.path.basename(caminho)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=diretorio)

    with socketserver.TCPServer(("", porta), handler) as httpd:
        webbrowser.open(f"http://localhost:{porta}/{nome_arquivo}")
        print(f"Servindo em http://localhost:{porta}/{nome_arquivo} — Ctrl+C para encerrar")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    # Passe o termo de busca como argumento: python novo.py gatos engraçados
    termo_busca = " ".join(sys.argv[1:]) or "funny fails shorts"

    try:
        videos = buscar_shorts(query=termo_busca, max_resultados=10)

        if not videos:
            print("Nenhum vídeo encontrado para essa busca.")
        else:
            print(f"--- Encontrados {len(videos)} shorts para '{termo_busca}' ---\n")
            for i, v in enumerate(videos, 1):
                print(f"Vídeo #{i}: {v['titulo']} ({v['duracao']}s) [id={v['id']}]")

            salvar_no_banco(videos, termo_busca)
            print(f"\n{len(videos)} vídeos salvos em {os.path.abspath(DB_PATH)}")

            caminho = gerar_pagina_html(videos)
            servir_pagina(caminho)

    except Exception as erro:
        print(f"Erro ao conectar na API: {erro}")
