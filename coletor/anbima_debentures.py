"""Coletor diário das taxas de debêntures da ANBIMA (mercado secundário).

A ANBIMA publica um arquivo por dia útil e mantém de graça apenas os últimos
5 dias úteis. Este script baixa esses dias, guarda o arquivo bruto (para
auditoria) e uma versão normalizada em CSV.

Uso:
    python coletor/anbima_debentures.py              # dias úteis dos últimos 9 dias corridos
    python coletor/anbima_debentures.py 2026-10-01   # uma data específica
"""

import csv
import re
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

URL = "https://www.anbima.com.br/informacoes/merc-sec-debentures/arqs/db{:%y%m%d}.txt"
RAIZ = Path(__file__).resolve().parent.parent
DIR_BRUTOS = RAIZ / "dados" / "anbima" / "debentures" / "brutos"
DIR_CSV = RAIZ / "dados" / "anbima" / "debentures" / "normalizado"

DIAS_UTEIS_DU_POR_ANO = 252

COLUNAS = [
    "data_referencia",
    "codigo",
    "emissor",
    "marcadores",
    "vencimento",
    "indexador_texto",
    "indexador_tipo",
    "taxa_emissao",
    "taxa_compra",
    "taxa_venda",
    "taxa_indicativa",
    "desvio_padrao",
    "intervalo_min",
    "intervalo_max",
    "pu",
    "pct_pu_par",
    "duration_du",
    "duration_anos",
    "pct_reune",
    "ntnb_referencia",
]

CABECALHO_ESPERADO = (
    "Código@Nome@Repac./  Venc.@Índice/ Correção@Taxa de Compra@Taxa de Venda"
    "@Taxa Indicativa@Desvio Padrão@Intervalo Indicativo Minimo"
    "@Intervalo Indicativo Máximo@PU@% PU Par / % VNE@Duration@% Reune"
    "@Referência NTN-B"
)


def baixar(dia: date) -> bytes | None:
    """Devolve o conteúdo do arquivo do dia, ou None se não houver (feriado, fim de semana, fora da janela)."""
    req = urllib.request.Request(URL.format(dia), headers={"User-Agent": "grafo-credito/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def numero(texto: str) -> float | None:
    texto = texto.strip()
    if texto in ("", "--", "N/D"):
        return None
    return float(texto.replace(".", "").replace(",", "."))


def data_iso(texto: str) -> str:
    texto = texto.strip()
    if not texto:
        return ""
    return datetime.strptime(texto, "%d/%m/%Y").date().isoformat()


def classificar_indexador(texto: str) -> tuple[str, float | None]:
    """Separa o indexador em tipo e taxa de emissão. Ex.: 'IPCA + 7,415%' -> ('IPCA_MAIS', 7.415)."""
    t = texto.strip()
    m = re.fullmatch(r"([\d,]+)% do DI", t)
    if m:
        return "PCT_DI", numero(m.group(1))
    m = re.fullmatch(r"(DI|IPCA|IGP-M) \+ ([\d,]+)%", t)
    if m:
        tipo = {"DI": "DI_MAIS", "IPCA": "IPCA_MAIS", "IGP-M": "IGPM_MAIS"}[m.group(1)]
        return tipo, numero(m.group(2))
    m = re.fullmatch(r"PREFIXADO ([\d,]+)%", t)
    if m:
        return "PREFIXADO", numero(m.group(1))
    if t == "IGP-M":
        return "IGPM", None
    return "OUTRO", None


def separar_marcadores(nome: str) -> tuple[str, str]:
    """Separa as marcações '(*)' e '(**)' do nome do emissor, sem interpretá-las.

    O significado das marcações deve ser confirmado no manual da ANBIMA antes de uso analítico.
    """
    marcadores = re.findall(r"\((\*+)\)", nome)
    limpo = re.sub(r"\s*\(\*+\)", "", nome).strip()
    return limpo, ";".join(marcadores)


def normalizar(dia: date, bruto: bytes) -> list[dict]:
    linhas = bruto.decode("latin-1").splitlines()
    cabecalho = next((i for i, l in enumerate(linhas) if l.startswith("Código@")), None)
    if cabecalho is None or linhas[cabecalho].strip() != CABECALHO_ESPERADO:
        raise ValueError(f"{dia}: cabeçalho do arquivo mudou; revisar o parser antes de continuar")

    registros = []
    for linha in linhas[cabecalho + 1 :]:
        if not linha.strip():
            continue
        c = linha.split("@")
        if len(c) != 15:
            raise ValueError(f"{dia}: linha com {len(c)} campos: {linha!r}")
        emissor, marcadores = separar_marcadores(c[1])
        tipo, taxa_emissao = classificar_indexador(c[3])
        duration_du = numero(c[12])
        registros.append(
            {
                "data_referencia": dia.isoformat(),
                "codigo": c[0].strip(),
                "emissor": emissor,
                "marcadores": marcadores,
                "vencimento": data_iso(c[2]),
                "indexador_texto": c[3].strip(),
                "indexador_tipo": tipo,
                "taxa_emissao": taxa_emissao,
                "taxa_compra": numero(c[4]),
                "taxa_venda": numero(c[5]),
                "taxa_indicativa": numero(c[6]),
                "desvio_padrao": numero(c[7]),
                "intervalo_min": numero(c[8]),
                "intervalo_max": numero(c[9]),
                "pu": numero(c[10]),
                "pct_pu_par": numero(c[11]),
                "duration_du": duration_du,
                "duration_anos": round(duration_du / DIAS_UTEIS_DU_POR_ANO, 4) if duration_du else None,
                "pct_reune": numero(c[13]),
                "ntnb_referencia": data_iso(c[14]),
            }
        )
    return registros


def coletar(dia: date) -> str:
    destino_bruto = DIR_BRUTOS / str(dia.year) / f"db{dia:%y%m%d}.txt"
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
    return f"{len(registros)} séries"


def main(args: list[str]) -> None:
    if args:
        dias = [date.fromisoformat(a) for a in args]
    else:
        # Janela gratuita = 5 dias úteis; 9 dias corridos cobrem isso mesmo com feriado.
        hoje = date.today()
        dias = [hoje - timedelta(d) for d in range(9)]
        dias = [d for d in dias if d.weekday() < 5]

    for dia in sorted(dias):
        print(f"{dia}: {coletar(dia)}")


if __name__ == "__main__":
    main(sys.argv[1:])
