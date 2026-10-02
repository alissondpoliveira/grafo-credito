"""Coletor diário das taxas de títulos públicos da ANBIMA (mercado secundário).

Serve de referência para o spread das debêntures: NTN-B para IPCA+, LTN/NTN-F
para prefixados. Mesmo padrão do coletor de debêntures: arquivo bruto + CSV.

Uso:
    python coletor/anbima_titulos_publicos.py              # dias úteis dos últimos 9 dias corridos
    python coletor/anbima_titulos_publicos.py 2026-10-01   # uma data específica
"""

import csv
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

from anbima_debentures import numero

URL = "https://www.anbima.com.br/informacoes/merc-sec/arqs/ms{:%y%m%d}.txt"
RAIZ = Path(__file__).resolve().parent.parent
DIR_BRUTOS = RAIZ / "dados" / "anbima" / "titulos_publicos" / "brutos"
DIR_CSV = RAIZ / "dados" / "anbima" / "titulos_publicos" / "normalizado"

CABECALHO_ESPERADO = (
    "Titulo@Data Referencia@Codigo SELIC@Data Base/Emissao@Data Vencimento@Tx. Compra"
    "@Tx. Venda@Tx. Indicativas@PU@Desvio padrao@Interv. Ind. Inf. (D0)"
    "@Interv. Ind. Sup. (D0)@Interv. Ind. Inf. (D+1)@Interv. Ind. Sup. (D+1)@Criterio"
)

COLUNAS = [
    "data_referencia",
    "titulo",
    "codigo_selic",
    "data_base",
    "vencimento",
    "taxa_compra",
    "taxa_venda",
    "taxa_indicativa",
    "pu",
    "desvio_padrao",
    "intervalo_min_d0",
    "intervalo_max_d0",
    "intervalo_min_d1",
    "intervalo_max_d1",
    "criterio",
]


def baixar(dia: date) -> bytes | None:
    req = urllib.request.Request(URL.format(dia), headers={"User-Agent": "grafo-credito/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def data_iso(texto: str) -> str:
    return datetime.strptime(texto.strip(), "%Y%m%d").date().isoformat()


def normalizar(dia: date, bruto: bytes) -> list[dict]:
    linhas = bruto.decode("latin-1").splitlines()
    cabecalho = next((i for i, l in enumerate(linhas) if l.startswith("Titulo@")), None)
    if cabecalho is None or linhas[cabecalho].strip() != CABECALHO_ESPERADO:
        raise ValueError(f"{dia}: cabeçalho do arquivo mudou; revisar o parser antes de continuar")

    registros = []
    for linha in linhas[cabecalho + 1 :]:
        if not linha.strip():
            continue
        c = linha.split("@")
        if len(c) != 15:
            raise ValueError(f"{dia}: linha com {len(c)} campos: {linha!r}")
        if data_iso(c[1]) != dia.isoformat():
            raise ValueError(f"{dia}: data de referência {c[1]} diferente da esperada")
        registros.append(
            {
                "data_referencia": dia.isoformat(),
                "titulo": c[0].strip(),
                "codigo_selic": c[2].strip(),
                "data_base": data_iso(c[3]),
                "vencimento": data_iso(c[4]),
                "taxa_compra": numero(c[5]),
                "taxa_venda": numero(c[6]),
                "taxa_indicativa": numero(c[7]),
                "pu": numero(c[8]),
                "desvio_padrao": numero(c[9]),
                "intervalo_min_d0": numero(c[10]),
                "intervalo_max_d0": numero(c[11]),
                "intervalo_min_d1": numero(c[12]),
                "intervalo_max_d1": numero(c[13]),
                "criterio": c[14].strip(),
            }
        )
    return registros


def coletar(dia: date) -> str:
    destino_bruto = DIR_BRUTOS / str(dia.year) / f"ms{dia:%y%m%d}.txt"
    destino_csv = DIR_CSV / str(dia.year) / f"{dia.isoformat()}.csv"
    if destino_bruto.exists() and destino_csv.exists():
        return "já existe"

    bruto = baixar(dia)
    if bruto is None:
        return "sem arquivo"

    registros = normalizar(dia, bruto)
    destino_bruto.parent.mkdir(parents=True, exist_ok=True)
    destino_bruto.write_bytes(bruto)
    destino_csv.parent.mkdir(parents=True, exist_ok=True)
    with destino_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS, lineterminator="\n")
        w.writeheader()
        w.writerows(registros)
    return f"{len(registros)} títulos"


def main(args: list[str]) -> None:
    if args:
        dias = [date.fromisoformat(a) for a in args]
    else:
        hoje = date.today()
        dias = [hoje - timedelta(d) for d in range(9)]
        dias = [d for d in dias if d.weekday() < 5]

    for dia in sorted(dias):
        print(f"{dia}: {coletar(dia)}")


if __name__ == "__main__":
    main(sys.argv[1:])
