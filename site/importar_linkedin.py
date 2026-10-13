"""Importa artigos do export de dados do LinkedIn para site/artigos/ (fonte) e site/public/artigos/ (imagens).

O LinkedIn entrega cada artigo em HTML (Configurações > Privacidade de dados > Obter uma cópia dos seus dados >
Artigos). Este script limpa o HTML (só tags de texto), baixa as imagens do corpo para o próprio site (o CSP do
site só aceita imagem do mesmo domínio) e grava um JSON por artigo. O site é montado depois por site/gerar.py.

Uso: python site/importar_linkedin.py <pasta Articles/Articles do export> [--todos]
Sem --todos, importa só os artigos da série Financial Syntax.
"""

import html
import json
import re
import sys
import unicodedata
from html.parser import HTMLParser
from pathlib import Path

from urllib.request import Request, urlopen

RAIZ = Path(__file__).resolve().parent.parent
FONTE = RAIZ / "site" / "artigos"
PUBLICO = RAIZ / "site" / "public" / "artigos"

PERMITIDAS = {"p", "strong", "em", "h2", "h3", "ul", "ol", "li", "blockquote", "a", "hr", "br", "figure", "figcaption", "img"}
EXT = {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif", "image/webp": "webp"}


def slug(titulo: str) -> str:
    t = unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t if len(t) <= 60 else t[:61].rsplit("-", 1)[0]


class Limpador(HTMLParser):
    """Refaz o corpo só com as tags permitidas; imagens viram marcadores {IMG:n} e as URLs ficam em self.imagens."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.saida, self.imagens, self.pilha = [], [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "iframe" and a.get("src"):
            src = a["src"] if a["src"].startswith("http") else "https:" + a["src"]
            yt = re.search(r"youtube\.com/embed/([\w-]+)", src)
            src = f"https://www.youtube.com/watch?v={yt.group(1)}" if yt else src
            self.saida.append(f'<p><a href="{html.escape(src)}" rel="noopener">Assistir ao vídeo</a></p>')
            return
        if tag not in PERMITIDAS:
            return
        if tag == "img":
            if a.get("src", "").startswith("http"):
                self.imagens.append(a["src"])
                self.saida.append("{IMG:%d}" % (len(self.imagens) - 1))
            return
        if tag == "a":
            href = a.get("href", "")
            if not href.startswith(("http://", "https://")):
                self.pilha.append(None)
                return
            self.saida.append(f'<a href="{html.escape(href)}" rel="noopener">')
        elif tag in ("hr", "br"):
            self.saida.append(f"<{tag}>")
            return
        else:
            self.saida.append(f"<{tag}>")
        self.pilha.append(tag)

    def handle_endtag(self, tag):
        if tag not in PERMITIDAS or tag in ("img", "hr", "br"):
            return
        while self.pilha:
            t = self.pilha.pop()
            if t is not None:
                self.saida.append(f"</{t}>")
            if t == tag or (t is None and tag == "a"):
                break

    def handle_data(self, data):
        self.saida.append(html.escape(data.replace("\xa0", " "), quote=False))


def _subtitulos(corpo: str) -> str:
    """Parágrafo curto todo em negrito, sem ponto final nem dois-pontos, é subtítulo no LinkedIn: vira <h2>. <h3> também vira <h2>.
    Linha de sublinhados vira <hr>."""
    corpo = re.sub(r"(?<!<li>)<p><strong>([^<]{2,110})</strong></p>", lambda m: m.group(0) if m.group(1).rstrip().endswith((".", ":")) else f"<h2>{m.group(1).strip()}</h2>", corpo)
    corpo = re.sub(r"<h3>(.*?)</h3>", r"<h2>\1</h2>", corpo, flags=re.S)
    corpo = re.sub(r"<(p|h2)>(?:<strong>)?_{5,}(?:</strong>)?</\1>", "<hr>", corpo)
    corpo = re.sub(r"<figcaption></figcaption>", "", corpo)
    return re.sub(r"<p>\s*</p>", "", corpo)


def _texto(trecho: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", trecho))).strip()


def importar(arquivo: Path, todos: bool) -> dict | None:
    bruto = arquivo.read_text(encoding="utf-8")
    serie = re.search(r'<span class="series-title">([^<]*)', bruto)
    serie = serie.group(1).strip() if serie else None
    if serie != "Financial Syntax" and not todos:
        return None
    titulo = _texto(re.search(r"<h1>(.*?)</h1>", bruto, re.S).group(1))
    url = re.search(r'<h1><a href="([^"]+)"', bruto).group(1)
    criado = re.search(r'class="created">Created on (\S+)', bruto).group(1)
    publicado = re.search(r'class="published">Published on (\S+)', bruto).group(1)
    corpo_bruto = bruto.split('class="published">', 1)[1].split("</p>", 1)[1].rsplit("</body>", 1)[0]

    lim = Limpador()
    lim.feed(corpo_bruto)
    corpo = _subtitulos("".join(lim.saida))
    s = slug(titulo)

    pasta = PUBLICO / s
    pasta.mkdir(parents=True, exist_ok=True)
    for i, src in enumerate(lim.imagens):
        with urlopen(Request(html.unescape(src), headers={"User-Agent": "Mozilla/5.0"}), timeout=30) as r:
            tipo, dados = r.headers.get_content_type(), r.read()
        nome = f"img-{i + 1}.{EXT.get(tipo, 'jpg')}"
        (pasta / nome).write_bytes(dados)
        corpo = corpo.replace("{IMG:%d}" % i, f'<img src="/artigos/{s}/{nome}" alt="Figura {i + 1} do artigo" loading="lazy">')

    primeiro = re.search(r"<p>(.*?)</p>", corpo, re.S)
    resumo = _texto(primeiro.group(1)) if primeiro else titulo
    if len(resumo) > 200:
        resumo = resumo[:197].rsplit(" ", 1)[0] + "…"
    return {"titulo": titulo, "slug": s, "serie": serie, "publicado": publicado, "criado": criado,
            "url_linkedin": url, "resumo": resumo, "corpo": corpo}


def main() -> None:
    pasta = Path(sys.argv[1])
    todos = "--todos" in sys.argv
    FONTE.mkdir(parents=True, exist_ok=True)
    for arq in sorted(pasta.glob("*.html")):
        art = importar(arq, todos)
        if art:
            (FONTE / f"{art['slug']}.json").write_text(json.dumps(art, ensure_ascii=False, indent=1), encoding="utf-8")
            print(art["publicado"], art["slug"], art["corpo"].count("<img"), "imagens")


if __name__ == "__main__":
    main()
