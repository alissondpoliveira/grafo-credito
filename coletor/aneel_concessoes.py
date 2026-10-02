"""Contratos de concessão de transmissão (ANEEL, SIGET - Contrato Agente).

Cada contrato tem CNPJ da concessionária, data de assinatura e data de fim.
Base para o "tail": folga entre o vencimento da debênture e o fim da concessão.

Uso: python coletor/aneel_concessoes.py
"""

import csv
import io
import urllib.request
from pathlib import Path

URL = ("https://dadosabertos.aneel.gov.br/dataset/beefe870-7452-4830-a7b0-6611e3d5eff6/resource/"
       "60e111c3-6ee1-412e-abe3-bc15af897537/download/siget-contrato-agente.csv")
DESTINO = Path(__file__).resolve().parent.parent / "dados" / "aneel" / "contratos_transmissao.csv"


def iso(d: str) -> str:
    d = d.strip()
    if not d:
        return ""
    dia, mes, ano = d.split("/")
    return f"{ano}-{mes}-{dia}"


def main() -> None:
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 (grafo-credito)"})
    with urllib.request.urlopen(req, timeout=180) as r:
        bruto = r.read()
    try:
        texto = bruto.decode("utf-8")
    except UnicodeDecodeError:
        texto = bruto.decode("latin-1")
    linhas = list(csv.DictReader(io.StringIO(texto), delimiter=";"))
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    with DESTINO.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["cnpj", "razao_social", "contrato", "tipo", "assinatura", "fim", "uf"])
        for l in linhas:
            w.writerow([l["NumCNPJ"].zfill(14), l["DscRazaoSocial"].strip(), l["NumCnaCcd"], l["IdcTipoCcd"],
                        iso(l["DatAsnCcd"]), iso(l["DatFimCcd"]), l["SigUF"]])
    print(f"{len(linhas)} contratos de transmissão")


if __name__ == "__main__":
    main()
