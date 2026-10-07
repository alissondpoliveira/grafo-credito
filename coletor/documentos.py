"""Camada de documentos e informações por emissor: o "cérebro" de cada nó do grafo.

Para cada emissor do piloto (por CNPJ), reúne só METADADOS (tipo, data, título,
fonte, link) de fontes públicas. Nenhum conteúdo é copiado: o site mostra o
título e leva ao documento original.

  fato_relevante / comunicado / aviso_debenturistas : CVM IPE (emissores registrados)
  escritura                                          : índice de escrituras (Pentágono, CVM IPE)
  noticia                                            : Google News RSS ("<emissor>" debêntures)
  analise                                            : Google News RSS restrito a sites de casas de análise

Saída: dados/derivados/documentos.json  {cnpj: [ {tipo, data, titulo, fonte, url}, ... ]}

Uso: python coletor/documentos.py
"""

import csv
import io
import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
UNIVERSO = RAIZ / "dados" / "referencia" / "universo_series.csv"
ESCRITURAS = RAIZ / "dados" / "referencia" / "escrituras_indice.csv"
DESTINO = RAIZ / "dados" / "derivados" / "documentos.json"
IPE = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE/DADOS/ipe_cia_aberta_{}.zip"
RSS = "https://news.google.com/rss/search?q={}&hl=pt-BR&gl=BR&ceid=BR:pt-419"

CATEGORIAS_IPE = {"Fato Relevante": "fato_relevante", "Comunicado ao Mercado": "comunicado",
                  "Aviso aos Debenturistas": "aviso_debenturistas"}
# casas de análise com conteúdo público indexado (título e link apenas)
CASAS = {
    "BTG Pactual": "content.btgpactual.com",
    "Itaú": "itau.com.br",
    "Inter": "inter.co",
    "Suno": "suno.com.br",
    "Levante": "levanteideias.com.br",
}
# nome de busca para emissores cujo nome legal não é como o mercado os chama
APELIDOS = {
    "TRANSMISSORA ALIANCA DE ENERGIA ELETRICA": "Taesa",
    "ISA ENERGIA BRASIL": "ISA Energia",
    "CPFL TRANSMISSAO": "CPFL Transmissão",
    "ENERGISA TRANSMISSAO": "Energisa Transmissão",
    "ALUPAR": "Alupar",
    "VERENE TRANSMISSAO": "Verene",
    "NEOENERGIA MORRO DO CHAPEU": "Neoenergia Morro do Chapéu",
    "HORIZON TRANSMISSAO": "Horizon Transmissão",
}
POR_TIPO = {"fato_relevante": 12, "comunicado": 8, "aviso_debenturistas": 6, "escritura": 6, "noticia": 10, "analise": 10}


def sem_acento(t: str) -> str:
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()


def nome_busca(razao: str) -> str:
    up = sem_acento(razao).upper()
    for k, v in APELIDOS.items():
        if k in up:
            return v
    t = re.sub(r"^[A-Z]{2,5}\s*-\s*", "", razao.strip())
    t = re.sub(r"\b(S\.?\s?/?A\.?|SPE|LTDA\.?)\b", " ", t, flags=re.I)
    t = re.sub(r"\bDE ENERGIA( ELETRICA| ELÉTRICA)?\b", " ", t, flags=re.I)
    return re.sub(r"\s+", " ", t).strip(" -.").title()


def get(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (grafo-credito; pesquisa)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def rss(consulta: str) -> list[dict]:
    try:
        raiz = ET.fromstring(get(RSS.format(urllib.parse.quote(consulta)), timeout=40))
    except Exception:
        return []
    itens = []
    for i in raiz.iter("item"):
        try:
            d = parsedate_to_datetime(i.findtext("pubDate")).date().isoformat()
        except Exception:
            d = ""
        titulo = re.sub(r"\s+-\s+[^-]+$", "", i.findtext("title") or "").strip()
        itens.append({"data": d, "titulo": titulo, "fonte": i.findtext("source") or "", "url": i.findtext("link") or ""})
    return itens


CREDITO = re.compile(r"deb[eê]nt|cr[eé]dit|rating|renda fixa|d[ií]vida|alavanc|resultado|emiss|incentivad|covenant|capta|juros|amortiza", re.I)


def consertar(t: str) -> str:
    """Títulos da Pentágono chegam em UTF-8 lido como latin-1 ('EmissÃ£o')."""
    try:
        return t.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return t


def menciona(titulo: str, nome: str) -> bool:
    """O título cita o emissor? Usa a primeira palavra distintiva do nome (evita notícia de outra empresa)."""
    palavras = [p for p in sem_acento(nome).upper().split() if len(p) > 3 and p not in {"TRANSMISSORA", "TRANSMISSAO", "ENERGIA", "EMPRESA", "COMPANHIA"}]
    alvo = palavras[0] if palavras else sem_acento(nome).upper()
    return alvo in sem_acento(titulo).upper()


def documentos_ipe(cnpjs: set[str]) -> dict[str, list[dict]]:
    fmt = lambda c: f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"
    alvo = {fmt(c): c for c in cnpjs}
    out: dict[str, list[dict]] = {}
    ano = date.today().year
    for a in (ano - 2, ano - 1, ano):
        try:
            z = zipfile.ZipFile(io.BytesIO(get(IPE.format(a), timeout=300)))
        except Exception:
            continue
        nome = next(n for n in z.namelist() if n.endswith(".csv"))
        for l in csv.DictReader(io.TextIOWrapper(z.open(nome), encoding="latin-1"), delimiter=";"):
            tipo = CATEGORIAS_IPE.get(l["Categoria"])
            if tipo and l["CNPJ_Companhia"] in alvo:
                out.setdefault(alvo[l["CNPJ_Companhia"]], []).append(
                    {"tipo": tipo, "data": l["Data_Entrega"][:10], "titulo": (l["Assunto"] or l["Categoria"]).strip(),
                     "fonte": "CVM", "url": l["Link_Download"]})
    return out


def main() -> None:
    universo = [u for u in csv.DictReader(UNIVERSO.open(encoding="utf-8")) if u["no_piloto"] == "S"]
    emissores = {u["cnpj"]: u["emissor_atual_snd"] for u in universo}
    docs: dict[str, list[dict]] = {c: [] for c in emissores}

    for c, ls in documentos_ipe(set(emissores)).items():
        docs[c] += ls

    if ESCRITURAS.exists():
        vistos = set()
        for l in csv.DictReader(ESCRITURAS.open(encoding="utf-8")):
            if l["status"] == "baixado" and l["url"] not in vistos:
                vistos.add(l["url"])
                titulo = consertar(l["titulo"])
                m = re.search(r"(\d{4})[.-](\d{2})[.-](\d{2})", titulo + " " + l["data"])
                docs[l["cnpj"]].append({"tipo": "escritura", "data": "-".join(m.groups()) if m else "", "titulo": titulo,
                                        "fonte": l["fonte"], "url": l["url"], "serie": l["codigo"]})

    for c, razao in emissores.items():
        nome = nome_busca(razao)
        for item in rss(f'"{nome}" debêntures'):
            if menciona(item["titulo"], nome):
                docs[c].append({"tipo": "noticia", **item})
        time.sleep(0.8)
        sites = " OR ".join(f"site:{s}" for s in CASAS.values())
        for item in rss(f'"{nome}" ({sites})'):
            if menciona(item["titulo"], nome) and CREDITO.search(item["titulo"]):
                casa = next((k for k, s in CASAS.items() if s.split(".")[0] in (item["fonte"] + item["url"]).lower() or k.lower() in item["fonte"].lower()), item["fonte"])
                docs[c].append({"tipo": "analise", **item, "fonte": casa})
        time.sleep(0.8)

    # ordena por data, remove duplicados e limita por tipo
    final = {}
    for c, ls in docs.items():
        unicos = {}
        for d in sorted(ls, key=lambda d: d.get("data", ""), reverse=True):
            unicos.setdefault((d["tipo"], d["titulo"].lower()[:80]), d)
        por_tipo: dict[str, list] = {}
        for d in unicos.values():
            if len(por_tipo.setdefault(d["tipo"], [])) < POR_TIPO[d["tipo"]]:
                por_tipo[d["tipo"]].append(d)
        final[c] = [d for t in POR_TIPO for d in por_tipo.get(t, [])]

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(json.dumps({"gerado_em": datetime.now().isoformat(timespec="minutes"), "emissores": final},
                                  ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    cont = Counter(d["tipo"] for ls in final.values() for d in ls)
    print(f"{sum(cont.values())} documentos para {sum(1 for v in final.values() if v)} de {len(final)} emissores: {dict(cont)}")


if __name__ == "__main__":
    main()
