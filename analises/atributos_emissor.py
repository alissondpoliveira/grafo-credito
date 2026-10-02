"""Atributos de comparabilidade por emissor (critérios para definir pares).

  segmento     : do universo ampliado (filtro duro dos pares)
  estrutura    : transmissão: project_finance (SPE com 1 ou 2 contratos ANEEL) | corporativa (3+ contratos ou holding sem contrato)
                 demais segmentos: corporativa (companhia aberta categoria A na CVM) | project_finance (demais)
  fase         : construcao | transicao | operacional
                 regra: ano da concessão mais recente (ANEEL) >= 2022 construção; 2019-2021 transição; <= 2018 operacional;
                 corporativas = operacional (carteira dominada por ativos em operação).
                 refino pelo JEV quando há comunicados/notícias do emissor e a confiança é >= 0,8.
  patrocinador : grande_grupo (controle documentado na CVM ou na escritura) | grupo_inferido | nao_identificado

Uso: python analises/atributos_emissor.py   (com TYPESAFE_API_KEY definida, roda também o refino pelo JEV)
"""

import csv
import json
import os
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
UNIVERSO = RAIZ / "dados" / "referencia" / "universo_series.csv"
CONTRATOS = RAIZ / "dados" / "aneel" / "contratos_transmissao.csv"
DOCS = RAIZ / "dados" / "derivados" / "documentos.json"
DESTINO = RAIZ / "dados" / "derivados" / "atributos_emissor.csv"
URL_CVM = "https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"
ATIVO = {"transmissao": "ativos de transmissão", "geracao": "usinas de geração", "distribuicao": "rede de distribuição",
         "saneamento": "sistemas de água e esgoto", "rodovias": "rodovias concedidas", "ferrovias": "malha ferroviária",
         "portos": "terminais portuários", "aeroportos": "aeroportos", "mobilidade_urbana": "linhas de transporte urbano"}
CACHE_JEV = RAIZ / "dados" / "derivados" / "jev" / "fase_emissor.json"

def fases(ativo: str) -> dict:
    return {
        "construcao": f"A maior parte dos {ativo} do emissor ainda está em obra ou licenciamento; receita ainda não começou ou é parcial",
        "transicao": f"Parte dos {ativo} já entrou em operação e parte ainda está em obra ou em investimento pesado",
        "operacional": f"Os {ativo} já estão em operação comercial e geram receita recorrente",
    }


def fase_por_regra(estrutura: str, anos: list[int]) -> str:
    if estrutura == "corporativa" or not anos:
        return "operacional"
    ultimo = max(anos)
    return "construcao" if ultimo >= 2022 else "transicao" if ultimo >= 2019 else "operacional"


def main() -> None:
    contratos = defaultdict(list)
    for c in csv.DictReader(CONTRATOS.open(encoding="utf-8")):
        if c["assinatura"]:
            contratos[c["cnpj"]].append(int(c["assinatura"][:4]))
    emissores = {}
    for u in csv.DictReader(UNIVERSO.open(encoding="utf-8")):
        if u["no_piloto"] == "S":
            emissores[u["cnpj"]] = u
    import io, re, urllib.request
    with urllib.request.urlopen(urllib.request.Request(URL_CVM, headers={"User-Agent": "grafo-credito"}), timeout=120) as r:
        cad = csv.DictReader(io.StringIO(r.read().decode("latin-1")), delimiter=";")
        categoria = {re.sub(r"\D", "", c["CNPJ_CIA"]): c["CATEG_REG"] for c in cad if c["SIT"].strip() == "ATIVO"}
    docs = json.loads(DOCS.read_text(encoding="utf-8"))["emissores"] if DOCS.exists() else {}
    cache = json.loads(CACHE_JEV.read_text(encoding="utf-8")) if CACHE_JEV.exists() else {}
    tem_chave = bool(os.environ.get("TYPESAFE_API_KEY"))
    if tem_chave:
        import sys
        sys.path.insert(0, str(RAIZ / "analises"))
        from jev_classificar import chamar, MODELO

    linhas = []
    for cnpj, u in emissores.items():
        anos = contratos.get(cnpj, [])
        segmento = u.get("segmento", "transmissao")
        if segmento == "transmissao":
            estrutura = "corporativa" if len(anos) >= 3 or not anos else "project_finance"
            fase_regra = fase_por_regra(estrutura, anos)
        else:
            estrutura = "corporativa" if categoria.get(cnpj) == "Categoria A" else "project_finance"
            fase_regra = "operacional"
        fase, fonte_fase, conf = fase_regra, "regra (ANEEL)", None

        titulos = [d["titulo"] for d in docs.get(cnpj, []) if d["tipo"] in ("comunicado", "fato_relevante", "noticia")][:15]
        if titulos:
            chave = f"{cnpj}|{len(titulos)}|{titulos[0][:40]}"
            if chave not in cache and tem_chave:
                estado = (f"Emissor: {u['emissor_atual_snd'].title()}, segmento {segmento.replace('_', ' ')} no Brasil. "
                          + (f"Contratos de concessão assinados em: {', '.join(map(str, sorted(anos)))}. " if anos else "")
                          + 
                          f"Títulos recentes de comunicados e notícias: " + " | ".join(titulos))
                r = chamar("systemone", {"model": MODELO, "state": estado, "questions": {
                    "fase": {"type": "choice", "instructions": f"Em que fase estão os {ATIVO.get(segmento, 'ativos')} deste emissor hoje?",
                             "criteria": fases(ATIVO.get(segmento, "ativos"))}}})
                cache[chave] = {"fase": r["answers"]["fase"]["choice"], "confianca": r["answers"]["fase"]["confidence"]}
            if chave in cache and cache[chave]["confianca"] >= 0.8:
                fase, fonte_fase, conf = cache[chave]["fase"], "JEV (comunicados e notícias)", cache[chave]["confianca"]

        fonte = u["fonte_grupo"]
        patrocinador = "grande_grupo" if fonte in ("CVM FRE", "escritura") else "grupo_inferido" if fonte == "inferido" else "nao_identificado"
        linhas.append({
            "cnpj": cnpj, "emissor": u["emissor_atual_snd"], "grupo_risco": u["grupo_risco"], "segmento": segmento,
            "estrutura": estrutura, "n_contratos_aneel": len(anos), "fase": fase, "fonte_fase": fonte_fase,
            "fase_regra": fase_regra, "confianca_fase_jev": conf, "patrocinador": patrocinador,
        })

    if cache:
        CACHE_JEV.parent.mkdir(parents=True, exist_ok=True)
        CACHE_JEV.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    with DESTINO.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(linhas)
    from collections import Counter
    print(f"{len(linhas)} emissores | estrutura {dict(Counter(l['estrutura'] for l in linhas))} | "
          f"fase {dict(Counter(l['fase'] for l in linhas))} | fase pelo JEV: {sum(1 for l in linhas if l['fonte_fase'].startswith('JEV'))}")


if __name__ == "__main__":
    main()
