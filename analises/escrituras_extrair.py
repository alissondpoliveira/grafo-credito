"""Extrai das escrituras os trechos que interessam ao grafo, com página e citação.

Para cada série: escolhe a escritura de emissão (e o aditamento mais recente),
converte para texto (pdftotext) e procura, por regras explícitas:
  fiadora / garantia fidejussória, garantias reais (alienação/cessão fiduciária,
  penhor), cross-default (vencimento antecipado por inadimplemento de outras
  dívidas, inclusive de controladora/fiadora), covenants financeiros
  (dívida líquida/EBITDA, ICSD) e resgate antecipado facultativo.

A saída é EVIDÊNCIA para revisão humana, não verdade: cada achado traz o trecho
e a página. Saídas:
  dados/referencia/escrituras_trechos.json   (todos os trechos)
  dados/referencia/clausulas_escrituras.csv  (resumo por série, status 'a revisar')

Uso: python analises/escrituras_extrair.py
"""

import csv
import json
import re
import subprocess
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
INDICE = RAIZ / "dados" / "referencia" / "escrituras_indice.csv"
TXT = RAIZ / "escrituras" / "txt"
SAIDA_JSON = RAIZ / "dados" / "referencia" / "escrituras_trechos.json"
SAIDA_CSV = RAIZ / "dados" / "referencia" / "clausulas_escrituras.csv"

REGRAS = {
    "fiadora": r"(?:na qualidade de fiador|[\"“]fiador[a]?[\"”]|garantia fidejuss[oó]ria|fian[cç]a)",
    "alienacao_fiduciaria_acoes": r"aliena[cç][aã]o fiduci[aá]ria de a[cç][oõ]es",
    "cessao_fiduciaria": r"cess[aã]o fiduci[aá]ria",
    "penhor": r"\bpenhor\b",
    "cross_default": r"(?:inadimplemento|vencimento antecipado)[\s\S]{0,220}?obriga[cç](?:[aã]o|[oõ]es)[\s\S]{0,60}?(?:natureza financeira|financeiras?|pecuni[aá]rias?)",
    "covenant_divida_ebitda": r"d[ií]vida l[ií]quida[^.]{0,80}ebitda",
    "covenant_icsd": r"(?:ICSD|[ií]ndice de cobertura do servi[cç]o da d[ií]vida)",
    "resgate_facultativo": r"resgate antecipado facultativo",
}
NOME_FIADORA = re.compile(
    r"([A-ZÀ-Ý][A-ZÀ-Ý0-9 .,&/\-]{6,140}?(?:S\.\s?A\.?|S/A|LTDA\.?))[^\"“”]{0,500}?[\"“]Fiador[a]?[\"”]"
)
GATILHO = re.compile(r"individual ou agregad[oa][^R]{0,60}R\$\s?([\d.]+,\d{2})", re.I)
ABRANGE = re.compile(r"(Controladas?|Controladora|Subsidi[aá]rias|Fiadora|Acionista|Coligadas)")
LIMITE_COVENANT = re.compile(r"(\d{1,2}[,.]\d{1,2})\s*(?:x|vezes)", re.I)


def texto_pdf(pdf: Path) -> list[str]:
    destino = TXT / pdf.parent.name / (pdf.stem + ".txt")
    if not destino.exists():
        destino.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["pdftotext", "-enc", "UTF-8", "-layout", str(pdf), str(destino)], check=False, capture_output=True)
    if not destino.exists():
        return []
    return destino.read_text(encoding="utf-8", errors="ignore").split("\f")


def sem_acento(t: str) -> str:
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()


def da_emissao(docs: list[dict], emissao: str) -> list[dict]:
    """Quando a fonte lista documentos de todas as emissões da companhia (CVM IPE), fica com os da emissão da série."""
    n = str(int(emissao)) if emissao and emissao.isdigit() else ""
    if not n:
        return docs
    alvo = re.compile(rf"(?<!\d){n}\s*(?:ª|a|º|o|_|\s)?\s*_?\s*(?:emiss|\(|$)", re.I)
    proprios = [d for d in docs if alvo.search(sem_acento(d["titulo"]).replace("_", " "))]
    return proprios


def escolher(docs: list[dict]) -> list[dict]:
    """Escritura original (preferindo a versão sem registro, que costuma ter texto) + aditamento mais recente."""
    esc = [d for d in docs if re.search(r"escritura", d["titulo"], re.I) and not re.search(r"aditamento", d["titulo"], re.I)]
    adit = [d for d in docs if re.search(r"aditamento", d["titulo"], re.I)]
    esc.sort(key=lambda d: (bool(re.search(r"registrad", d["titulo"], re.I)), d["data"]))
    adit.sort(key=lambda d: d["data"], reverse=True)
    return esc[:3] + adit[:1]


def main() -> None:
    docs_por_serie: dict[str, list[dict]] = {}
    if INDICE.exists():
        for l in csv.DictReader(INDICE.open(encoding="utf-8")):
            if l["status"] == "baixado":
                docs_por_serie.setdefault(l["codigo"], []).append(l)
    else:  # índice ainda não gravado: lê direto as pastas baixadas
        for pdf in sorted((RAIZ / "escrituras" / "pdf").glob("*/*.pdf")):
            docs_por_serie.setdefault(pdf.parent.name, []).append(
                {"titulo": pdf.stem, "data": pdf.stem[:10], "arquivo": str(pdf.relative_to(RAIZ))})

    emissao = {c["Codigo do Ativo"]: c["Emissao"] for c in csv.DictReader((RAIZ / "dados" / "snd" / "caracteristicas.csv").open(encoding="utf-8"))}
    trechos, resumo = {}, []
    for cod, docs in sorted(docs_por_serie.items()):
        if not any("Pentágono" == d.get("fonte") for d in docs):
            docs = da_emissao(docs, emissao.get(cod, ""))
        achados = {k: [] for k in REGRAS}
        fiadoras, limites, lidos, gatilhos, abrange = set(), [], [], set(), set()
        texto_ok = False
        for d in escolher(docs):
            paginas = texto_pdf(RAIZ / d["arquivo"])
            if sum(len(p.strip()) for p in paginas) < 2000:
                continue  # PDF escaneado (sem camada de texto)
            texto_ok = True
            lidos.append(d["titulo"])
            for i, pg in enumerate(paginas, 1):
                plano = re.sub(r"\s+", " ", pg)
                for k, padrao in REGRAS.items():
                    for m in re.finditer(padrao, plano, re.I):
                        if len(achados[k]) < 4:
                            ini = max(0, m.start() - 220)
                            achados[k].append({"documento": d["titulo"], "pagina": i, "trecho": plano[ini:m.end() + 260].strip()})
                for m in re.finditer(REGRAS["cross_default"], plano, re.I):
                    janela = plano[max(0, m.start() - 300): m.end() + 400]
                    gatilhos.update(GATILHO.findall(janela))
                    abrange.update(x.capitalize() for x in ABRANGE.findall(janela))
                for m in NOME_FIADORA.finditer(plano):
                    nome = re.sub(r"\s+", " ", m.group(1)).strip(" ,")
                    if 8 < len(nome) < 120:
                        fiadoras.add(nome)
                if re.search(REGRAS["covenant_divida_ebitda"], plano, re.I):
                    for m in re.finditer(REGRAS["covenant_divida_ebitda"], plano, re.I):
                        janela = plano[m.start(): m.end() + 200]
                        limites += LIMITE_COVENANT.findall(janela)
            if any(achados.values()):
                pass
        trechos[cod] = {"lidos": lidos, "achados": achados, "fiadoras_candidatas": sorted(fiadoras)}
        tem = {k: bool(v) for k, v in achados.items()}
        garantias = [n for n, k in (("alienação fiduciária de ações", "alienacao_fiduciaria_acoes"), ("cessão fiduciária", "cessao_fiduciaria"), ("penhor", "penhor")) if tem[k]]
        partes = []
        if fiadoras:
            partes.append("fiança: " + "; ".join(sorted(fiadoras))[:80])
        if garantias:
            partes.append(", ".join(garantias))
        if tem["cross_default"]:
            partes.append("cross-default" + (f" ≥ R$ {min(gatilhos, key=lambda v: float(v.replace('.', '').replace(',', '.')))}" if gatilhos else ""))
        if limites:
            partes.append("DL/EBITDA " + "/".join(sorted(set(limites))[:3]) + "x")
        resumo.append({
            "codigo": cod,
            "texto_legivel": "S" if texto_ok else "N",
            "documentos_lidos": len(lidos),
            "fiadora": sorted(fiadoras)[0] if len(fiadoras) == 1 else "",
            "fiadoras_candidatas": " | ".join(sorted(fiadoras)),
            "tem_fianca": "S" if tem["fiadora"] else "N",
            "alienacao_fiduciaria_acoes": "S" if tem["alienacao_fiduciaria_acoes"] else "N",
            "cessao_fiduciaria": "S" if tem["cessao_fiduciaria"] else "N",
            "penhor": "S" if tem["penhor"] else "N",
            "cross_default": "S" if tem["cross_default"] else "N",
            "cross_default_gatilho_brl": min(gatilhos, key=lambda v: float(v.replace(".", "").replace(",", "."))) if gatilhos else "",
            "cross_default_abrange": "; ".join(sorted(abrange)),
            "covenant_divida_ebitda": "/".join(sorted(set(limites))[:3]),
            "covenant_icsd": "S" if tem["covenant_icsd"] else "N",
            "resgate_facultativo": "S" if tem["resgate_facultativo"] else "N",
            "resumo": " · ".join(partes) if texto_ok else "escritura sem texto (escaneada)",
            "status_revisao": "a revisar",
        })

    SAIDA_JSON.write_text(json.dumps(trechos, ensure_ascii=False, indent=1), encoding="utf-8")
    with SAIDA_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(resumo[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(resumo)
    from collections import Counter
    print(f"{len(resumo)} séries; texto legível em {sum(r['texto_legivel'] == 'S' for r in resumo)}")
    for k in ("tem_fianca", "alienacao_fiduciaria_acoes", "cessao_fiduciaria", "cross_default", "resgate_facultativo"):
        print(k, Counter(r[k] for r in resumo))


if __name__ == "__main__":
    main()
