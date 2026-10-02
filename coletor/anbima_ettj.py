"""Coletor diário da estrutura a termo (ETTJ) da ANBIMA: parâmetros Svensson e vértices.

A curva real (IPCA) é a base do Z-spread das debêntures IPCA+; a prefixada e a
inflação implícita entram no gross-up das incentivadas.

Uso:
    python coletor/anbima_ettj.py              # dias úteis dos últimos 9 dias corridos
    python coletor/anbima_ettj.py 2026-10-01
"""

import csv
import sys
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from anbima_debentures import numero

URL = "https://www.anbima.com.br/informacoes/est-termo/CZ-down.asp"
RAIZ = Path(__file__).resolve().parent.parent
DIR_BRUTOS = RAIZ / "dados" / "anbima" / "ettj" / "brutos"
DIR_CSV = RAIZ / "dados" / "anbima" / "ettj" / "normalizado"


def baixar(dia: date) -> bytes | None:
    corpo = urllib.parse.urlencode({"Idioma": "PT", "Dt_Ref": f"{dia:%d/%m/%Y}", "saida": "csv"}).encode()
    req = urllib.request.Request(URL, data=corpo, headers={"User-Agent": "grafo-credito/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        bruto = r.read()
    # sem curva para a data, a ANBIMA devolve outra data no cabeçalho ou página vazia
    if not bruto.decode("latin-1").startswith(f"{dia:%d/%m/%Y};"):
        return None
    return bruto


def normalizar(dia: date, bruto: bytes) -> tuple[list[dict], list[dict]]:
    linhas = [l for l in bruto.decode("latin-1").splitlines()]
    parametros = []
    for l in linhas[1:3]:
        c = l.split(";")
        parametros.append(
            {"data_referencia": dia.isoformat(), "curva": c[0], "beta1": numero(c[1]), "beta2": numero(c[2]),
             "beta3": numero(c[3]), "beta4": numero(c[4]), "lambda1": numero(c[5]), "lambda2": numero(c[6])}
        )
    i = next(k for k, l in enumerate(linhas) if l.startswith("Vertices;"))
    vertices = []
    for l in linhas[i + 1 :]:
        c = l.split(";")
        if len(c) < 4 or not c[0].strip().replace(".", "").isdigit():
            break
        vertices.append(
            {"data_referencia": dia.isoformat(), "du": int(c[0].replace(".", "")), "ettj_ipca": numero(c[1]),
             "ettj_pre": numero(c[2]), "inflacao_implicita": numero(c[3])}
        )
    return parametros, vertices


def gravar(caminho: Path, linhas: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(linhas)


def coletar(dia: date) -> str:
    destino_bruto = DIR_BRUTOS / str(dia.year) / f"ettj_{dia.isoformat()}.csv"
    destino_par = DIR_CSV / str(dia.year) / f"{dia.isoformat()}_parametros.csv"
    destino_ver = DIR_CSV / str(dia.year) / f"{dia.isoformat()}_vertices.csv"
    if destino_bruto.exists() and destino_par.exists():
        return "já existe"
    bruto = baixar(dia)
    if bruto is None:
        return "sem curva"
    parametros, vertices = normalizar(dia, bruto)
    destino_bruto.parent.mkdir(parents=True, exist_ok=True)
    destino_bruto.write_bytes(bruto)
    gravar(destino_par, parametros)
    gravar(destino_ver, vertices)
    return f"{len(vertices)} vértices"


def main(args: list[str]) -> None:
    if args:
        dias = [date.fromisoformat(a) for a in args]
    else:
        hoje = date.today()
        dias = [d for d in (hoje - timedelta(k) for k in range(9)) if d.weekday() < 5]
    for dia in sorted(dias):
        print(f"{dia}: {coletar(dia)}")


if __name__ == "__main__":
    main(sys.argv[1:])
