"""Série mensal do IPCA (variação %, BCB SGS 433), usada para separar correção monetária de amortização.

Uso: python coletor/bcb_ipca.py
"""

import csv
import json
import urllib.request
from pathlib import Path

URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?formato=json&dataInicial=01/01/2005"
DESTINO = Path(__file__).resolve().parent.parent / "dados" / "bcb" / "ipca_mensal.csv"


def main() -> None:
    with urllib.request.urlopen(urllib.request.Request(URL, headers={"User-Agent": "grafo-credito/0.1"}), timeout=60) as r:
        serie = json.load(r)
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    with DESTINO.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["mes", "variacao_pct"])
        for p in serie:
            d, m, a = p["data"].split("/")
            w.writerow([f"{a}-{m}", p["valor"]])
    print(f"{len(serie)} meses até {serie[-1]['data']}")


if __name__ == "__main__":
    main()
