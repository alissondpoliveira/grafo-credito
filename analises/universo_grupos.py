"""Reconstrói o universo de transmissão por série, com emissor atual (SND/CNPJ) e grupo de risco.

Hierarquia de evidência do grupo de risco:
  1. 'CVM FRE'   : acionista controlador PJ declarado no Formulário de Referência (fato documentado)
  2. 'inferido'  : regra explícita abaixo (cadeia societária ou nome), a confirmar na escritura
Pessoas físicas listadas como controladoras não são gravadas.

Uso: python analises/universo_grupos.py   (requer dados/snd/caracteristicas.csv e o FRE da CVM)
"""

import csv
import io
import urllib.request
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SND = RAIZ / "dados" / "snd" / "caracteristicas.csv"
DEB = RAIZ / "dados" / "anbima" / "debentures" / "normalizado"
ANTIGO = RAIZ / "dados" / "referencia" / "universo_transmissao.csv"
DESTINO = RAIZ / "dados" / "referencia" / "universo_series.csv"
CONTROLADORES = RAIZ / "dados" / "referencia" / "controladores_cvm.csv"
URL_FRE = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FRE/DADOS/fre_cia_aberta_{}.zip"

# Grupo de risco atribuído a partir do controlador PJ declarado na CVM (nome normalizado -> grupo)
GRUPO_POR_CONTROLADOR = {
    "INTERCONEXI": "ISA",
    "ISA CAPITAL": "ISA",
    "COMPANHIA ENERGÉTICA DE MINAS GERAIS": "Taesa (Cemig + ISA)",
    "CAMBESA": "Alupar",
    "ARGO ENERGIA": "Argo",
    "ARGEB": "Argo",
    "VERENE": "Verene/IEB",
    "IEB-INFRAESTRUTURA": "Verene/IEB",
    "ENERGISA S/A": "Energisa",
    "CPFL ENERGIA": "CPFL",
    "AXIA ENERGIA": "Axia (ex-Eletrobras)",
}

# Inferências explícitas para emissores sem FRE (fonte = 'inferido'); cada uma diz o porquê
INFERIDOS = {
    "VERENE TRANSMISSAO SUBHOLDING": ("Verene/IEB", "mesmo nome do controlador de Belém e Tapajós (CVM)"),
    "BARREIRAS TRANSMISSORA": ("Verene/IEB", "ex-Equatorial Transmissora SPE; holding hoje é a Verene Subholding"),
    "BURITIRAMA TRANSMISSORA": ("Verene/IEB", "ex-Equatorial Transmissora SPE; holding hoje é a Verene Subholding"),
    "ALTO SERTAO TRANSMISSORA": ("Verene/IEB", "ex-Equatorial Transmissora SPE; holding hoje é a Verene Subholding"),
    "VALE DO SERTAO TRANSMISSORA": ("Verene/IEB", "ex-Equatorial Transmissora SPE; holding hoje é a Verene Subholding"),
    "INTERLIGACAO ELETRICA": ("ISA", "nome padrão das SPEs da ISA"),
    "NEOENERGIA": ("Neoenergia", "nome do emissor"),
    "EDP TRANSMISSAO": ("EDP", "nome do emissor"),
}

# Emissor atual não é transmissora pura: fora do piloto pela decisão de 02/10/2026
FORA_DO_PILOTO = {
    "COMPANHIA HIDRO ELETRICA DO SAO FRANCISCO": "emissor atual é a CHESF (integrada geração + transmissão)",
    "CPFL COMERCIALIZACAO": "emissor atual é comercializadora de energia, não transmissora",
}


def baixar_controladores(cnpjs: set[str]) -> dict[str, list[tuple[str, str]]]:
    """Controladores PJ da versão mais recente do FRE de cada companhia."""
    ano = date.today().year
    for a in (ano, ano - 1):
        try:
            with urllib.request.urlopen(URL_FRE.format(a), timeout=300) as r:
                z = zipfile.ZipFile(io.BytesIO(r.read()))
            break
        except Exception:
            continue
    nome = next(n for n in z.namelist() if n.endswith(f"posicao_acionaria_{a}.csv"))
    linhas = csv.DictReader(io.TextIOWrapper(z.open(nome), encoding="latin-1"), delimiter=";")
    por_cia = defaultdict(list)
    for l in linhas:
        cnpj = "".join(ch for ch in l["CNPJ_Companhia"] if ch.isdigit())
        if cnpj in cnpjs:
            por_cia[cnpj].append(l)
    saida = {}
    for cnpj, ls in por_cia.items():
        versao = max(int(l["Versao"]) for l in ls)
        # (controlador, cnpj, de quem ele é sócio: vazio = da própria companhia)
        saida[cnpj] = list(dict.fromkeys(
            (l["Acionista"].strip(), l["CPF_CNPJ_Acionista"], l["Acionista_Relacionado"].strip(), l["CPF_CNPJ_Acionista_Relacionado"])
            for l in ls
            if int(l["Versao"]) == versao and l["Acionista_Controlador"] == "S" and l["Tipo_Pessoa_Acionista"] == "PJ"
        ))
    return saida


def main() -> None:
    antigos = {u["emissor"] for u in csv.DictReader(ANTIGO.open(encoding="utf-8"))}
    ultimo = sorted(DEB.rglob("*.csv"))[-1]
    series = [s for s in csv.DictReader(ultimo.open(encoding="utf-8")) if s["emissor"] in antigos]
    snd = {c["Codigo do Ativo"]: c for c in csv.DictReader(SND.open(encoding="utf-8"))}

    cnpjs = {snd[s["codigo"]]["CNPJ"].zfill(14) for s in series if s["codigo"] in snd}
    ctrl = baixar_controladores(cnpjs)

    revisao: dict[str, list[dict]] = {}
    arq_rev = RAIZ / "dados" / "referencia" / "revisao_escrituras.csv"
    if arq_rev.exists():
        for r in csv.DictReader(arq_rev.open(encoding="utf-8")):
            revisao.setdefault(r["codigo"], []).append(r)

    linhas, controladores = [], []
    for cnpj, cs in sorted(ctrl.items()):
        for nome, doc, rel, doc_rel in cs:
            controladores.append({"cnpj_companhia": cnpj, "controlador": nome, "cnpj_controlador": doc,
                                  "socio_de": rel, "cnpj_socio_de": doc_rel, "fonte": "CVM FRE"})

    for s in series:
        c = snd.get(s["codigo"], {})
        emissor_atual = c.get("Empresa", s["emissor"])
        cnpj = c.get("CNPJ", "").zfill(14) if c else ""
        up = emissor_atual.upper()

        grupo, fonte, motivo = "Isolada (a identificar)", "", ""
        nomes_ctrl = [c[0].upper() for c in ctrl.get(cnpj, [])]
        for chave, g in GRUPO_POR_CONTROLADOR.items():
            if any(chave.upper() in n for n in nomes_ctrl):
                grupo, fonte, motivo = g, "CVM FRE", "controlador PJ declarado"
                break
        rev = revisao.get(s["codigo"])
        if not fonte and rev:
            grupo, fonte = rev[0]["grupo_risco"], "escritura"
            motivo = "; ".join(f'{r["parte"].title()} ({r["papel"]})' for r in rev)
        if not fonte:
            for chave, (g, porque) in INFERIDOS.items():
                if chave in up:
                    grupo, fonte, motivo = g, "inferido", porque
                    break

        fora = next((m for k, m in FORA_DO_PILOTO.items() if k in up), "")
        linhas.append({
            "codigo": s["codigo"],
            "emissor_anbima": s["emissor"],
            "emissor_atual_snd": emissor_atual,
            "cnpj": cnpj,
            "grupo_risco": grupo,
            "fonte_grupo": fonte,
            "motivo_grupo": motivo,
            "no_piloto": "N" if fora else "S",
            "motivo_exclusao": fora,
        })

    with DESTINO.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(linhas)
    with CONTROLADORES.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["cnpj_companhia", "controlador", "cnpj_controlador", "socio_de", "cnpj_socio_de", "fonte"], lineterminator="\n")
        w.writeheader()
        w.writerows(controladores)

    from collections import Counter
    print(f"{len(linhas)} séries; fora do piloto: {sum(l['no_piloto'] == 'N' for l in linhas)}")
    print(Counter((l["grupo_risco"], l["fonte_grupo"]) for l in linhas if l["no_piloto"] == "S").most_common())


if __name__ == "__main__":
    main()
