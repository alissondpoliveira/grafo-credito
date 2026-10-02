"""Exploratório: em qual setor estão as debêntures da ANBIMA?

O arquivo da ANBIMA não traz setor nem CNPJ. Este script cruza o nome do
emissor com o cadastro de companhias da CVM (campo SETOR_ATIV) e, para quem
não casa, aplica palavras-chave no nome. As duas origens ficam separadas na
saída: `fonte_setor` = 'cvm' (fato documentado) ou 'palavra_chave' (inferência).

Uso: python analises/setores_universo.py [AAAA-MM-DD]
"""

import csv
import io
import re
import sys
import unicodedata
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
URL_CVM = "https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"

SUFIXOS = r"\b(S\s?/?\s?A|SA|LTDA|EM RECUPERACAO JUDICIAL|EM RECUPERACAO EXTRAJUDICIAL|EM LIQUIDACAO)\b"

# Ordem importa: a primeira regra que casar define o grupo.
PALAVRAS_CHAVE = [
    ("Energia - Transmissão", r"TRANSMISS|\bTRANSM\b|\bLT\b|LINHAS DE TRANSMISSAO"),
    ("Energia - Geração/Eólica/Solar", r"EOLIC|SOLAR|FOTOVOLT|HIDRELETR|\bUHE\b|\bPCH\b|GERACAO|GERADORA|ENERGIA RENOVAVEL|VENTOS|PARQUE"),
    ("Energia - Distribuição", r"DISTRIBUI.*ENERGIA|ENERGIA.*DISTRIBUI"),
    ("Energia - Outros", r"ENERGI|ELETRIC|POWER|COMERCIALIZADORA"),
    ("Saneamento", r"SANEAMENTO|AGUAS|\bAGUA\b|ESGOTO"),
    ("Rodovias/Concessões", r"RODOVI|CONCESSION|AUTOPISTA|VIA\b|\bVIAS\b|ROTA"),
    ("Logística/Transporte", r"LOGISTIC|PORTO|PORTUAR|FERROV|AEROPORTO|TRANSPORT|MULTIMODAL|LOCALIZA|LOCACAO|LOCADORA|MOVIDA"),
    ("Telecom", r"TELECOM|TELEFON|FIBRA|\bNET\b|INTERNET|TORRES"),
    ("Saúde", r"HOSPITAL|SAUDE|DIAGNOST|LABORAT|FARMA|DROGARIA"),
    ("Imobiliário/Shopping", r"SHOPPING|IMOBILI|INCORPORA|CONSTRU|EMPREEND|REALTY|PROPERT"),
    ("Óleo e Gás", r"PETRO|\bGAS\b|OLEO|COMBUSTIV|RAIZEN|COSAN|ULTRAPAR"),
    ("Agro/Alimentos", r"AGRO|ALIMENT|ACUCAR|ETANOL|BIOENERG|FRIGORIF|GRAOS|SEMENTE"),
    ("Mineração/Siderurgia", r"MINERA|SIDERUR|\bACO\b|METALUR"),
    ("Varejo", r"VAREJ|LOJAS|MAGAZINE|SUPERMERC|ATACAD|COMERCIO"),
    ("Financeiro/Holding", r"PARTICIPAC|HOLDING|FINANC|BANCO|CAPITAL|INVEST|SECURITIZ"),
]


def normalizar_nome(nome: str) -> str:
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().upper()
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"[.,\-/&]", " ", s)
    s = re.sub(SUFIXOS, " ", s)
    return re.sub(r"\s+", " ", s).strip()


def carregar_cvm() -> dict[str, str]:
    with urllib.request.urlopen(URL_CVM, timeout=120) as r:
        texto = r.read().decode("latin-1")
    por_nome: dict[str, tuple[bool, str]] = {}
    for linha in csv.DictReader(io.StringIO(texto), delimiter=";"):
        setor = linha["SETOR_ATIV"].strip()
        if not setor:
            continue
        ativo = linha["SIT"].strip() == "ATIVO"
        for campo in ("DENOM_SOCIAL", "DENOM_COMERC"):
            chave = normalizar_nome(linha[campo])
            # registro ativo tem prioridade sobre cancelado
            if chave and (chave not in por_nome or (ativo and not por_nome[chave][0])):
                por_nome[chave] = (ativo, setor)
    return {k: v[1] for k, v in por_nome.items()}


def setor_por_palavra(nome_normalizado: str) -> str:
    for grupo, padrao in PALAVRAS_CHAVE:
        if re.search(padrao, nome_normalizado):
            return grupo
    return "Não classificado"


def main(data_ref: str | None) -> None:
    pasta = RAIZ / "dados" / "anbima" / "debentures" / "normalizado"
    arquivo = pasta / data_ref[:4] / f"{data_ref}.csv" if data_ref else sorted(pasta.rglob("*.csv"))[-1]
    series = list(csv.DictReader(arquivo.open(encoding="utf-8")))
    cvm = carregar_cvm()

    saida = []
    for s in series:
        n = normalizar_nome(s["emissor"])
        if n in cvm:
            setor, fonte = cvm[n], "cvm"
        else:
            setor, fonte = setor_por_palavra(n), "palavra_chave"
        saida.append({**s, "setor": setor, "fonte_setor": fonte, "com_indicativa": bool(s["taxa_indicativa"])})

    destino = RAIZ / "analises" / "saidas" / f"setores_{arquivo.stem}.csv"
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(saida[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(saida)

    print(f"Base: {arquivo.name} | {len(saida)} séries | {len({s['emissor'] for s in saida})} emissores")
    print(f"Setor via CVM: {sum(s['fonte_setor'] == 'cvm' for s in saida)} séries; via palavra-chave: "
          f"{sum(s['fonte_setor'] == 'palavra_chave' for s in saida)}\n")

    agg = defaultdict(lambda: Counter())
    for s in saida:
        a = agg[s["setor"]]
        a["series"] += 1
        a["com_indicativa"] += s["com_indicativa"]
        a["ipca"] += s["indexador_tipo"] == "IPCA_MAIS"
        a["di"] += s["indexador_tipo"] in ("DI_MAIS", "PCT_DI")
        a["incent?"] += "**" in s["marcadores"].split(";")
        a[f"fonte_{s['fonte_setor']}"] += 1
    emissores = defaultdict(set)
    for s in saida:
        emissores[s["setor"]].add(s["emissor"])

    print(f"{'Setor':45} {'séries':>6} {'c/ taxa':>7} {'emiss.':>6} {'IPCA+':>6} {'DI':>5} {'(**)':>5} {'via CVM':>7}")
    for setor, a in sorted(agg.items(), key=lambda x: -x[1]["com_indicativa"]):
        print(f"{setor[:45]:45} {a['series']:6} {a['com_indicativa']:7} {len(emissores[setor]):6} "
              f"{a['ipca']:6} {a['di']:5} {a['incent?']:5} {a['fonte_cvm']:7}")
    print(f"\nDetalhe por série: {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
