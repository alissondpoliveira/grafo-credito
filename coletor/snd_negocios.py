"""Negócios do mercado secundário (SND) por série: quantidade, número de negócios e PU.

Base da medida de liquidez: dias com negócio, número de negócios e volume
financeiro numa janela recente. Guarda o histórico completo baixado.

Uso: python coletor/snd_negocios.py [dias=180]
"""

import csv
import io
import sys
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path

URL = ("https://www.debentures.com.br/exploreosnd/consultaadados/mercadosecundario/"
       "precosdenegociacao_e.asp?ativo={}&dt_ini={:%Y%m%d}&dt_fim={:%Y%m%d}")
RAIZ = Path(__file__).resolve().parent.parent
UNIVERSO = RAIZ / "dados" / "referencia" / "universo_series.csv"
DESTINO = RAIZ / "dados" / "snd" / "negocios.csv"


def br(t: str) -> float:
    return float(t.replace(".", "").replace(",", "."))


def baixar(codigo: str, ini: date, fim: date) -> list[dict]:
    req = urllib.request.Request(URL.format(codigo, ini, fim), headers={"User-Agent": "grafo-credito/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        texto = r.read().decode("latin-1")
    linhas = texto.splitlines()
    i = next((k for k, l in enumerate(linhas) if l.startswith("Data\t")), None)
    if i is None:
        return []
    saida = []
    for l in csv.DictReader(io.StringIO("\n".join(linhas[i:])), delimiter="\t"):
        if not l.get("Data") or "/" not in l["Data"]:
            continue
        d, m, a = l["Data"].split("/")
        saida.append({
            "data": f"{a}-{int(m):02d}-{int(d):02d}", "codigo": codigo,
            "quantidade": int(br(l["Quantidade"])), "negocios": int(br(l["Número de Negócios"])),
            "pu_min": br(l["PU Mínimo"]), "pu_medio": br(l["PU Médio"]), "pu_max": br(l["PU Máximo"]),
            "pct_pu_curva": br(l["% PU da Curva"]) if l.get("% PU da Curva", "").strip() else "",
        })
    return saida


def main(dias: int) -> None:
    fim = date.today()
    ini = fim - timedelta(dias)
    codigos = [u["codigo"] for u in csv.DictReader(UNIVERSO.open(encoding="utf-8")) if u["no_piloto"] == "S"]
    existentes = {}
    if DESTINO.exists():
        for l in csv.DictReader(DESTINO.open(encoding="utf-8")):
            existentes[(l["data"], l["codigo"])] = l
    falhas = 0
    for cod in codigos:
        try:
            for l in baixar(cod, ini, fim):
                existentes[(l["data"], l["codigo"])] = l
        except Exception as e:
            falhas += 1
            print(f"{cod}: falha ({e})")
        time.sleep(0.4)
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    campos = ["data", "codigo", "quantidade", "negocios", "pu_min", "pu_medio", "pu_max", "pct_pu_curva"]
    with DESTINO.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos, lineterminator="\n")
        w.writeheader()
        w.writerows(sorted(existentes.values(), key=lambda l: (l["codigo"], l["data"])))
    print(f"{len(existentes)} dias-série com negócio; {falhas} falhas")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 180)
