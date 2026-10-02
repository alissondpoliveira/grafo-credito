"""Universo ampliado: energia (todos os subsegmentos), saneamento e infraestrutura de transporte.

Classifica cada série da ANBIMA num SEGMENTO, que é filtro obrigatório dos pares.
Ordem de evidência: setor declarado na CVM (por CNPJ do SND, quando já coletado; senão
por nome no cadastro CVM) e palavras-chave no nome do emissor para o subsegmento.

Saída: dados/referencia/universo_candidatos.csv (codigo, emissor_anbima, segmento, fonte_segmento)

Uso: python analises/universo_amplo.py
"""

import csv
import io
import re
import unicodedata
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DEB = RAIZ / "dados" / "anbima" / "debentures" / "normalizado"
SND = RAIZ / "dados" / "snd" / "caracteristicas.csv"
DESTINO = RAIZ / "dados" / "referencia" / "universo_candidatos.csv"
URL_CVM = "https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"

MACRO_CVM = {
    "Energia Elétrica": "energia",
    "Emp. Adm. Part. - Energia Elétrica": "energia",
    "Saneamento, Serv. Água e Gás": "saneamento_gas",
    "Emp. Adm. Part. - Saneamento, Serv. Água e Gás": "saneamento_gas",
    "Serviços Transporte e Logística": "transporte",
    "Emp. Adm. Part. - Serviços Transporte e Logística": "transporte",
}
# subsegmentos por palavra-chave (primeira regra que casa vence, dentro do macro)
SUB = {
    "energia": [
        ("integrada_gt", r"ELETROBRAS|\bAXIA\b|CHESF|SAO FRANCISCO|FURNAS|ELETRONORTE|ELETROSUL|GERACAO E TRANSMISSAO"),
        ("geracao", r"GERACAO DISTRIBUIDA"),
        ("transmissao", r"TRANSMISS|\bTRANS\b|INTERLIGACAO ELETRICA|\bLT\b|ISA ENERGIA|LINHAS DE TAUBATE|ALUPAR"),
        ("distribuicao", r"DISTRIBUI|\bCELPE\b|\bCOELBA\b|\bCOSERN\b|\bCEMIG D\b|\bCOPEL DIS|\bLIGHT\b|\bENEL\b|ELEKTRO|\bRGE\b|PAULISTA DE FORCA|PIRATININGA|EQUATORIAL (PARA|MARANHAO|PIAUI|ALAGOAS|GOIAS)|ENERGISA (MATO|MINAS|PARAIBA|SERGIPE|SUL|TOCANTINS|ACRE|RONDONIA|BORBOREMA|NOVA)|ELETRICIDADE|ELETRICAS DE RONDONIA|ELETROPAULO"),
        ("comercializacao", r"COMERCIALIZ"),
        ("geracao", r"ENEVA|ENGIE|AES TIETE|\bAES\b|CESP|AUREN|ECHOENERGIA|ESSENTIA|THREE GORGES|CELSE|CONFLUENCIA|JAGUARI|JAGUARA|SINOP|MIRANDA|SAO MANOEL|FERREIRA GOMES|NORTE ENERGIA|OMEGA|RIO PARANA|SERENA|TIBAGI|ASSURUA|EOLIC|SOLAR|FOTOVOLT|HIDRELETR|\bUHE\b|\bPCH\b|\bCGH\b|GERACAO|GERADORA|RENOVAV|BIOENERG|TERMELETR|TERMOELETR|VENTOS|PARQUE|ENERGIAS? DO|\bUTE\b|\bSPE\b.*ENERGIA"),
        ("energia_diversificada", r"."),
    ],
    "saneamento_gas": [
        ("distribuicao_gas", r"\bGAS\b|COMGAS|COMPAGAS|NATURGY|SULGAS|GASMIG|BAHIAGAS"),
        ("saneamento", r"."),
    ],
    "transporte": [
        ("locacao", r"LOCADORA|LOCALIZA|MOVIDA|UNIDAS|LOCACAO|VAMOS|RENT"),
        ("mobilidade_urbana", r"TRENS|METRO|\bVLT\b|LINHAS? \d|MOBILIDADE|BARCAS"),
        ("aeroportos", r"AEROPORTO|AIRPORT|GALEAO|VIRACOPOS|GUARULHOS"),
        ("ferrovias", r"FERROV|\bRUMO\b|\bMRS\b|\bVLI\b|MALHA"),
        ("portos", r"PORTO|PORTUAR|TERMINAL|SANTOS BRASIL|WILSON|\bCLI\b"),
        ("rodovias", r"\bEPR\b|VIAPAULISTA|ARAGUAIA|LITORAL PIONEIRO|RODOVI|AUTOPISTA|\bVIA\b|\bVIAS\b|ROTA|ECO\d|\bECO\b|ARTERIS|CONCESSIONARIA|TRIANGULO DO SOL|ENTREVIAS|ECOVIAS|MOTIVA|CCR"),
        ("logistica", r"."),
    ],
}
# emissores fora dos três macros mas cujo nome indica o segmento
MACRO_POR_NOME = [
    ("energia", r"TRANSMISS|EOLIC|SOLAR|FOTOVOLT|HIDRELETR|ENERGIA|ELETRIC|GERACAO|\bPCH\b|\bUHE\b"),
    ("saneamento_gas", r"SANEAMENTO|\bAGUAS?\b|ESGOTO|AMBIENTAL|\bGAS\b"),
    ("transporte", r"RODOVI|AUTOPISTA|CONCESSIONARIA DE RODOVIAS|PORTO|PORTUAR|FERROV|AEROPORTO|LOGISTIC|TRENS|METRO|MOBILIDADE"),
]
SEGMENTOS = [s for v in SUB.values() for s, _ in v]
# nomes com "energia" que não são do setor elétrico (combustíveis, GLP, açúcar e etanol)
FORA = re.compile(r"VIBRA|RAIZEN|COPA ENERGIA|ULTRAPAR|COSAN|PETROBRAS|PETRO|AMBIPAR")  # Ambipar: serviços ambientais, não saneamento


def sem_acento(t: str) -> str:
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().upper()


def norm(t: str) -> str:
    s = sem_acento(t)
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"[.,\-/&]", " ", s)
    s = re.sub(r"\b(S\s?/?\s?A|SA|LTDA|EM RECUPERACAO JUDICIAL)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def main() -> None:
    with urllib.request.urlopen(urllib.request.Request(URL_CVM, headers={"User-Agent": "grafo-credito"}), timeout=120) as r:
        cad = list(csv.DictReader(io.StringIO(r.read().decode("latin-1")), delimiter=";"))
    setor_por_cnpj = {re.sub(r"\D", "", c["CNPJ_CIA"]): c["SETOR_ATIV"].strip() for c in cad if c["SETOR_ATIV"].strip()}
    setor_por_nome = {}
    for c in cad:
        if c["SETOR_ATIV"].strip():
            for campo in ("DENOM_SOCIAL", "DENOM_COMERC"):
                setor_por_nome.setdefault(norm(c[campo]), c["SETOR_ATIV"].strip())
    snd = {}
    if SND.exists():
        snd = {c["Codigo do Ativo"]: c for c in csv.DictReader(SND.open(encoding="utf-8"))}

    ultimo = sorted(DEB.rglob("*.csv"))[-1]
    saida = []
    for s in csv.DictReader(ultimo.open(encoding="utf-8")):
        if s["indexador_tipo"] not in ("IPCA_MAIS", "DI_MAIS", "PCT_DI"):
            continue
        c = snd.get(s["codigo"], {})
        nome = c.get("Empresa") or s["emissor"]
        cnpj = c.get("CNPJ", "").zfill(14) if c.get("CNPJ") else ""
        setor, fonte = "", ""
        if cnpj and cnpj in setor_por_cnpj:
            setor, fonte = setor_por_cnpj[cnpj], "CVM (CNPJ)"
        elif norm(nome) in setor_por_nome:
            setor, fonte = setor_por_nome[norm(nome)], "CVM (nome)"
        macro = MACRO_CVM.get(setor)
        if not macro:
            for m, padrao in MACRO_POR_NOME:
                if re.search(padrao, sem_acento(nome)):
                    macro, fonte = m, "nome do emissor"
                    break
        if not macro or FORA.search(sem_acento(nome)):
            continue
        seg = next(sub for sub, padrao in SUB[macro] if re.search(padrao, sem_acento(nome)))
        saida.append({"codigo": s["codigo"], "emissor_anbima": s["emissor"], "emissor_snd": c.get("Empresa", ""),
                      "macro": macro, "segmento": seg, "fonte_segmento": fonte, "setor_cvm": setor})

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    with DESTINO.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(saida[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(saida)
    from collections import Counter
    print(f"{len(saida)} séries no universo ampliado")
    for k, v in sorted(Counter(l["segmento"] for l in saida).items(), key=lambda x: -x[1]):
        print(f"  {k:24} {v}")


if __name__ == "__main__":
    main()
