"""Localiza e baixa as escrituras de emissão das séries do piloto, a partir de fontes públicas.

Fontes, em ordem: site do agente fiduciário Pentágono (documentos por ativo) e
sistema IPE da CVM (categoria "Escrituras e aditamentos de debêntures").
Os PDFs ficam em escrituras/pdf/ (fora do Git); o índice vai para
dados/referencia/escrituras_indice.csv.

Uso: python coletor/escrituras.py [CODIGO ...]
"""

import csv
import html
import io
import re
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
UNIVERSO = RAIZ / "dados" / "referencia" / "universo_series.csv"
SND = RAIZ / "dados" / "snd" / "caracteristicas.csv"
PDFS = RAIZ / "escrituras" / "pdf"
INDICE = RAIZ / "dados" / "referencia" / "escrituras_indice.csv"

PENTAGONO_LISTA = "https://www.pentagonotrustee.com.br/Site/DetalhesEmissor?ativo={}&aba=tab-2"
PENTAGONO_ARQ = "https://www.pentagonotrustee.com.br/Site/DownloadBinario?id={}"
IPE = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE/DADOS/ipe_cia_aberta_{}.zip"
ANOS_IPE = range(2017, 2027)


def get(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (grafo-credito; pesquisa)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def docs_pentagono(codigo: str) -> list[dict]:
    pagina = get(PENTAGONO_LISTA.format(codigo)).decode("latin-1", errors="ignore")
    achados = re.findall(r"title='([^']+)'[^>]*onclick=\"DownloadBinario\((\d+)\)", pagina)
    docs = []
    for titulo, ident in achados:
        titulo = html.unescape(titulo)
        if re.search(r"escritura|aditamento", titulo, re.I):
            docs.append({"fonte": "Pentágono", "titulo": titulo, "url": PENTAGONO_ARQ.format(ident), "data": titulo[:10]})
    # várias cópias registradas do mesmo documento: fica com a escritura sem registro (tem texto) e o aditamento mais recente
    esc = sorted([d for d in docs if not re.search(r"aditamento", d["titulo"], re.I)],
                 key=lambda d: (bool(re.search(r"registrad", d["titulo"], re.I)), d["data"]))
    adit = sorted([d for d in docs if re.search(r"aditamento", d["titulo"], re.I)], key=lambda d: d["data"], reverse=True)
    return esc[:2] + adit[:1]


def indice_ipe(cnpjs: set[str]) -> dict[str, list[dict]]:
    fmt = lambda c: f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"
    alvo = {fmt(c): c for c in cnpjs}
    saida: dict[str, list[dict]] = {}
    for ano in ANOS_IPE:
        try:
            z = zipfile.ZipFile(io.BytesIO(get(IPE.format(ano), timeout=300)))
        except Exception:
            continue
        nome = next(n for n in z.namelist() if n.endswith(".csv"))
        for l in csv.DictReader(io.TextIOWrapper(z.open(nome), encoding="latin-1"), delimiter=";"):
            if l["CNPJ_Companhia"] in alvo and l["Categoria"].startswith("Escrituras"):
                saida.setdefault(alvo[l["CNPJ_Companhia"]], []).append(
                    {"fonte": "CVM IPE", "titulo": l["Assunto"], "url": l["Link_Download"], "data": l["Data_Entrega"]}
                )
    return saida


def da_emissao(docs: list[dict], emissao: str) -> list[dict]:
    """Documentos do IPE cobrem todas as emissões da companhia; fica só com os da emissão da série."""
    import unicodedata
    n = str(int(emissao)) if emissao and emissao.isdigit() else ""
    if not n:
        return []
    alvo = re.compile(rf"(?<!\d){n}\s*(?:ª|a|º|o|_|\s)?\s*_?\s*(?:emiss|\(|$)", re.I)
    sem = lambda t: unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().replace("_", " ")
    return [d for d in docs if alvo.search(sem(d["titulo"]))]


def nome_arquivo(doc: dict) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", f"{doc['data']}_{doc['titulo']}")[:110]
    return base if base.lower().endswith(".pdf") else base + ".pdf"


def main(codigos: list[str]) -> None:
    universo = [u for u in csv.DictReader(UNIVERSO.open(encoding="utf-8")) if u["no_piloto"] == "S"]
    if codigos:
        universo = [u for u in universo if u["codigo"] in codigos]
    snd = list(csv.DictReader(SND.open(encoding="utf-8")))
    agentes = {c["Codigo do Ativo"]: c.get("Agente Fiduciario", "") for c in snd}
    emissoes = {c["Codigo do Ativo"]: c.get("Emissao", "") for c in snd}
    ipe = indice_ipe({u["cnpj"] for u in universo})

    linhas = []
    for u in universo:
        cod = u["codigo"]
        docs = []
        if agentes.get(cod, "").startswith("PENT"):
            try:
                docs = docs_pentagono(cod)
            except Exception as e:
                print(f"{cod}: falha Pentágono ({e})")
            time.sleep(0.5)
        if not docs:
            docs = da_emissao(ipe.get(u["cnpj"], []), emissoes.get(cod, ""))
        if not docs:
            linhas.append({"codigo": cod, "cnpj": u["cnpj"], "agente_fiduciario": agentes.get(cod, ""), "fonte": "", "titulo": "",
                           "url": "", "arquivo": "", "status": "não localizado"})
            continue
        for d in docs:
            destino = PDFS / cod / nome_arquivo(d)
            status = "baixado"
            if not destino.exists():
                try:
                    conteudo = get(d["url"], timeout=300)
                    if not conteudo.startswith(b"%PDF"):
                        status = "não é PDF"
                    else:
                        destino.parent.mkdir(parents=True, exist_ok=True)
                        destino.write_bytes(conteudo)
                except Exception as e:
                    status = f"falha download ({e})"
                time.sleep(0.5)
            linhas.append({"codigo": cod, "cnpj": u["cnpj"], "agente_fiduciario": agentes.get(cod, ""), **d,
                           "arquivo": str(destino.relative_to(RAIZ)) if status == "baixado" else "", "status": status})

    INDICE.parent.mkdir(parents=True, exist_ok=True)
    with INDICE.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["codigo", "cnpj", "agente_fiduciario", "fonte", "titulo", "data", "url", "arquivo", "status"],
                           lineterminator="\n")
        w.writeheader()
        w.writerows(linhas)
    from collections import Counter
    por_serie = {l["codigo"] for l in linhas if l["status"] == "baixado"}
    print(f"séries com documento: {len(por_serie)} de {len(universo)}")
    print(Counter(l["status"] for l in linhas))


if __name__ == "__main__":
    main(sys.argv[1:])
