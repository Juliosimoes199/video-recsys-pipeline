from flask import Flask, request, render_template_string

from youtube_api import buscar_shorts, salvar_no_banco

app = Flask(__name__)

TEMPLATE = """<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<title>Feed de Shorts</title>
<style>
  body { background:#000; color:#fff; font-family:sans-serif; display:flex; flex-direction:column; align-items:center; gap:24px; padding:20px; }
  form { display:flex; gap:8px; width:100%; max-width:360px; }
  input { flex:1; padding:10px; border-radius:6px; border:none; font-size:16px; }
  button { padding:10px 16px; border-radius:6px; border:none; background:#f00; color:#fff; font-size:16px; cursor:pointer; }
  .video-card { text-align:center; }
  .erro { color:#f66; }
</style>
</head>
<body>

<form method="get" action="/buscar">
  <input type="text" name="q" placeholder="Buscar shorts..." value="{{ termo }}" autofocus>
  <button type="submit">Buscar</button>
</form>

{% if erro %}
  <p class="erro">{{ erro }}</p>
{% elif termo and not videos %}
  <p>Nenhum vídeo encontrado para "{{ termo }}".</p>
{% endif %}

{% for v in videos %}
<div class="video-card">
    <h3>{{ v.titulo }}</h3>
    <p>{{ v.duracao }}s</p>
    <iframe width="360" height="640"
        src="https://www.youtube.com/embed/{{ v.id }}"
        frameborder="0" allow="autoplay; encrypted-media" allowfullscreen>
    </iframe>
</div>
{% endfor %}

</body>
</html>"""


@app.route("/")
def index():
    return render_template_string(TEMPLATE, videos=[], termo="", erro=None)


@app.route("/buscar")
def buscar():
    termo = request.args.get("q", "").strip()
    if not termo:
        return render_template_string(TEMPLATE, videos=[], termo="", erro=None)

    try:
        videos = buscar_shorts(query=termo, max_resultados=30)
        if videos:
            salvar_no_banco(videos, termo)
        return render_template_string(TEMPLATE, videos=videos, termo=termo, erro=None)
    except Exception as erro:
        return render_template_string(TEMPLATE, videos=[], termo=termo, erro=f"Erro ao conectar na API: {erro}")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
