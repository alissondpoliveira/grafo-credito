"""Fundamentos de balanço dos emissores registrados na CVM (DFP anual, consolidado; individual se não houver).

Métricas por CNPJ, último exercício entregue:
  receita            3.01
  ebit               3.05  (resultado antes do resultado financeiro e dos tributos)
  depreciacao        DFC 6.01.01.xx com "deprecia" ou "amortiza" na descrição
  ebitda             ebit + depreciação
  divida_bruta       2.01.04 + 2.02.01 (empréstimos e financiamentos, inclui debêntures)
  caixa              1.01.01 + 1.01.02 (caixa e aplicações financeiras de curto prazo)
  divida_liquida     dívida bruta - caixa
  dl_ebitda          dívida líquida / ebitda
  cobertura_juros    ebitda / |despesas financeiras (3.06.02)|

Saída: dados/cvm/fundamentos.csv

Uso: python coletor/cvm_dfp.py
"""

import csv
import io
import urllib.request
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_{}.zip"
DESTINO = RAIZ / "dados" / "cvm" / "fundamentos.csv"


def ler(z: zipfile.ZipFile, demo: str, ano: int, tipo: str) -> list[dict]:
    nome = f"dfp_cia_aberta_{demo}_{tipo}_{ano}.csv"
    if nome not in z.namelist():
        return []
    return [l for l in csv.DictReader(io.TextIOWrapper(z.open(nome), encoding="latin-1"), delimiter=";") if l["ORDEM_EXERC"].startswith("ÚLTIMO") or l["ORDEM_EXERC"].startswith("Ã\x9aLTIMO") or "LTIMO" in l["ORDEM_EXERC"] and not l["ORDEM_EXERC"].startswith("PEN")]


def valor(l: dict) -> float:
    v = float(l["VL_CONTA"] or 0)
    return v * 1000 if l.get("ESCALA_MOEDA", "").upper().startswith("MIL") else v


def main() -> None:
    hoje = date.today().year
    por_cnpj: dict[str, dict] = {}
    for ano in (hoje - 1, hoje - 2):  # exercício mais recente primeiro; o anterior cobre quem ainda não entregou
        try:
            with urllib.request.urlopen(urllib.request.Request(URL.format(ano), headers={"User-Agent": "grafo-credito"}), timeout=600) as r:
                z = zipfile.ZipFile(io.BytesIO(r.read()))
        except Exception as e:
            print(f"{ano}: sem DFP ({e})")
            continue
        for tipo in ("con", "ind"):
            linhas = defaultdict(list)
            for demo in ("BPA", "BPP", "DRE", "DFC_MI", "DFC_MD"):
                for l in ler(z, demo, ano, tipo):
                    linhas[l["CNPJ_CIA"]].append(l)
            for cnpj_fmt, ls in linhas.items():
                cnpj = "".join(ch for ch in cnpj_fmt if ch.isdigit())
                if cnpj in por_cnpj:
                    continue  # já tem dado mais recente ou consolidado
                versao = max(int(l["VERSAO"]) for l in ls)
                ls = [l for l in ls if int(l["VERSAO"]) == versao]
                conta = {l["CD_CONTA"]: valor(l) for l in ls}
                g = lambda c: conta.get(c, 0.0)
                deprec = sum(abs(valor(l)) for l in ls if l["CD_CONTA"].startswith("6.01.01.")
                             and any(k in l["DS_CONTA"].lower() for k in ("deprecia", "amortiza")) and "custo" not in l["DS_CONTA"].lower())
                ebit = g("3.05")
                ebitda = ebit + deprec
                divida = g("2.01.04") + g("2.02.01")
                caixa = g("1.01.01") + g("1.01.02")
                desp_fin = abs(g("3.06.02"))
                if not (g("3.01") or divida):
                    continue
                por_cnpj[cnpj] = {
                    "cnpj": cnpj, "nome": ls[0]["DENOM_CIA"], "exercicio": ls[0]["DT_REFER"], "demonstracao": tipo,
                    "receita": g("3.01"), "ebit": ebit, "depreciacao": deprec, "ebitda": ebitda,
                    "divida_bruta": divida, "caixa": caixa, "divida_liquida": divida - caixa,
                    "despesa_financeira": desp_fin, "lucro_liquido": g("3.11"),
                    "dl_ebitda": (divida - caixa) / ebitda if ebitda > 0 else None,
                    "cobertura_juros": ebitda / desp_fin if desp_fin > 0 else None,
                }
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    with DESTINO.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(next(iter(por_cnpj.values())).keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(por_cnpj.values())
    print(f"{len(por_cnpj)} companhias com fundamentos")


if __name__ == "__main__":
    main()
