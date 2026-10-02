"""Spread justo por pares comparáveis e ajuste por eventos.

PARES. Filtros duros: mesmo segmento e mesma classe (IPCA+ com IPCA+, DI+ com DI+).
Entre os candidatos, distância ponderada (pesos em PESOS, todos explícitos):
  estrutura, fase, patrocinador, garantia, incentivada (diferença = 1 ponto x peso)
  duration (|dif| / 2 anos, teto 2), tail (|dif| / 8 anos, teto 1,5), tamanho (|dif ln|, teto 1)
Os K mais próximos de OUTROS emissores formam os pares; o spread justo é a mediana deles.
Séries do mesmo emissor ficam de fora dos pares (comparar o papel com ele mesmo infla a semelhança).

AJUSTE POR EVENTOS (camada separada, parâmetros provisórios conservadores, a calibrar com estudo de evento):
  evento de crédito negativo (JEV, confiança >= 0,8)   +25 bps
  outro evento de impacto negativo (confiança >= 0,8)   +8 bps
  avanço operacional (energização, operação, licença; JEV operacional positivo) -5 bps
  tetos por tipo e emissor: operacional -10, impacto negativo +20, crédito negativo +40
  decaimento exponencial com meia-vida de 60 dias; janela de 180 dias; teto de +/-40 bps por emissor
O ajuste nunca altera o spread observado: muda o "justo ajustado" e o desvio contra ele.

Uso: python analises/pares.py
"""

import csv
import json
import math
from datetime import date
from pathlib import Path
from statistics import median, pstdev

RAIZ = Path(__file__).resolve().parent.parent
PREC = RAIZ / "dados" / "derivados" / "precificacao"
JUSTO = RAIZ / "dados" / "derivados" / "spread_justo"
ATRIB = RAIZ / "dados" / "derivados" / "atributos_emissor.csv"
UNIVERSO = RAIZ / "dados" / "referencia" / "universo_series.csv"
SND = RAIZ / "dados" / "snd" / "caracteristicas.csv"
JEV = RAIZ / "dados" / "derivados" / "jev" / "classificacao.json"
SAIDA = RAIZ / "dados" / "derivados" / "pares"

K = 8
PESOS = {"estrutura": 3.0, "fase": 3.0, "patrocinador": 2.0, "garantia": 1.0, "incentivada": 1.0,
         "duration": 1.0, "tail": 1.0, "tamanho": 0.5}
EVENTOS = {"credito_negativo": 25.0, "negativo": 8.0, "operacional_positivo": -5.0}
TETO_TIPO = {"credito_negativo": 40.0, "negativo": 20.0, "operacional_positivo": -10.0}
MEIA_VIDA, JANELA, TETO = 60, 180, 40.0
CONFIANCA_MINIMA = 0.8


def br(t: str) -> float:
    return float(t.replace(".", "").replace(",", "."))


def ajuste_eventos(data_ref: date) -> dict[str, tuple[float, list[str]]]:
    if not JEV.exists():
        return {}
    por_emissor: dict[str, list] = {}
    for chave, r in json.loads(JEV.read_text(encoding="utf-8")).items():
        if r.get("status") != "automatico" or r.get("evento_confianca", 0) < CONFIANCA_MINIMA:
            continue
        cnpj, tipo, d, titulo = chave.split("|", 3)
        try:
            dias = (data_ref - date.fromisoformat(d)).days
        except ValueError:
            continue
        if not 0 <= dias <= JANELA:
            continue
        if r["evento"] == "credito_negativo":
            tipo_aj, rot = "credito_negativo", "crédito negativo"
        elif r["impacto"] == "negativo":
            tipo_aj, rot = "negativo", "impacto negativo"
        elif r["evento"] == "operacional" and r["impacto"] == "positivo":
            tipo_aj, rot = "operacional_positivo", "avanço operacional"
        else:
            continue
        valor = EVENTOS[tipo_aj] * 0.5 ** (dias / MEIA_VIDA)
        por_emissor.setdefault(cnpj, []).append((tipo_aj, valor, f"{rot} ({d}): {titulo[:60]} → {valor:+.1f} bps"))
    saida = {}
    for c, ls in por_emissor.items():
        total = 0.0
        for t, teto in TETO_TIPO.items():
            soma = sum(v for tt, v, _ in ls if tt == t)
            total += max(soma, teto) if teto < 0 else min(soma, teto)
        saida[c] = (max(-TETO, min(TETO, total)), [m for _, _, m in ls])
    return saida


def main() -> None:
    arq = sorted(PREC.glob("????-??-??.csv"))[-1]
    data_ref = date.fromisoformat(arq.stem)
    series = list(csv.DictReader(arq.open(encoding="utf-8")))
    justos = {j["codigo"]: j for j in csv.DictReader((JUSTO / f"{arq.stem}.csv").open(encoding="utf-8"))}
    atrib = {a["cnpj"]: a for a in csv.DictReader(ATRIB.open(encoding="utf-8"))}
    cnpj = {u["codigo"]: u["cnpj"] for u in csv.DictReader(UNIVERSO.open(encoding="utf-8"))}
    snd = {c["Codigo do Ativo"]: c for c in csv.DictReader(SND.open(encoding="utf-8"))}
    ajustes = ajuste_eventos(data_ref)

    base = []
    for s in series:
        j = justos.get(s["codigo"])
        if not j or j["spread_bps"] in ("", None):
            continue
        c = snd.get(s["codigo"], {})
        a = atrib.get(cnpj.get(s["codigo"], ""), {})
        vol = br(c["Quantidade Emitida"]) * br(c["Valor Nominal na Emissao"]) / 1e6 if c.get("Quantidade Emitida") else None
        base.append({
            "codigo": s["codigo"], "cnpj": cnpj.get(s["codigo"]), "classe": j["classe"], "segmento": a.get("segmento", "transmissao"),
            "faixa": j.get("faixa", "principal"),
            "spread": float(j["spread_bps"]), "estrutura": a.get("estrutura"), "fase": a.get("fase"), "patrocinador": a.get("patrocinador"),
            "garantia": s["garantia"], "incentivada": s["incentivada"], "duration": float(s["duration_mod_anos"]),
            "tail": float(j["tail_anos"]) if j.get("tail_anos") not in ("", None) else None, "tamanho": math.log(vol) if vol else None,
        })

    def distancia(a: dict, b: dict) -> float:
        d = sum(PESOS[k] for k in ("estrutura", "fase", "patrocinador", "garantia", "incentivada") if a[k] != b[k])
        d += PESOS["duration"] * min(2.0, abs(a["duration"] - b["duration"]) / 2)
        if a["tail"] is not None and b["tail"] is not None:
            d += PESOS["tail"] * min(1.5, abs(a["tail"] - b["tail"]) / 8)
        if a["tamanho"] is not None and b["tamanho"] is not None:
            d += PESOS["tamanho"] * min(1.0, abs(a["tamanho"] - b["tamanho"]))
        return d

    linhas = []
    for a in base:
        # filtros obrigatórios: classe, faixa (principal / high yield) e segmento
        mesma = lambda b: b["cnpj"] != a["cnpj"] and b["classe"] == a["classe"] and b["faixa"] == a["faixa"]
        candidatos = [b for b in base if mesma(b) and b["segmento"] == a["segmento"]]
        entre_segmentos = False
        if len(candidatos) < 3 and a["faixa"] == "high_yield":
            candidatos, entre_segmentos = [b for b in base if mesma(b)], True  # poucos high yield no segmento
        candidatos.sort(key=lambda b: distancia(a, b))
        pares = candidatos[:K]
        if len(pares) < 3:
            continue
        justo = median(p["spread"] for p in pares)
        aj, motivos = ajustes.get(a["cnpj"], (0.0, []))
        linhas.append({
            "codigo": a["codigo"], "classe": a["classe"], "spread_bps": a["spread"],
            "justo_pares_bps": justo, "dispersao_pares_bps": pstdev(p["spread"] for p in pares),
            "distancia_media": sum(distancia(a, p) for p in pares) / len(pares), "n_pares": len(pares),
            "pares": " ".join(p["codigo"] for p in pares),
            "ajuste_eventos_bps": aj, "motivos_ajuste": " | ".join(motivos),
            "justo_ajustado_bps": justo + aj, "desvio_bps": a["spread"] - (justo + aj),
            "estrutura": a["estrutura"], "fase": a["fase"], "patrocinador": a["patrocinador"],
            "faixa": a["faixa"], "pares_entre_segmentos": "S" if entre_segmentos else "",
        })
    # desvio em desvios-padrão, por classe e faixa
    for grupo in {(l["classe"], l["faixa"]) for l in linhas}:
        ds = [l["desvio_bps"] for l in linhas if (l["classe"], l["faixa"]) == grupo]
        dp = pstdev(ds) if len(ds) > 2 else None
        for l in linhas:
            if (l["classe"], l["faixa"]) == grupo:
                l["desvio_em_dp"] = l["desvio_bps"] / dp if dp else None

    SAIDA.mkdir(parents=True, exist_ok=True)
    with (SAIDA / f"{arq.stem}.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(linhas)
    (SAIDA / "parametros.json").write_text(json.dumps({"K": K, "pesos": PESOS, "eventos_bps": EVENTOS, "tetos_por_tipo_bps": TETO_TIPO, "meia_vida_dias": MEIA_VIDA,
                                                        "janela_dias": JANELA, "teto_bps": TETO, "confianca_minima": CONFIANCA_MINIMA},
                                                       ensure_ascii=False, indent=1), encoding="utf-8")
    com_aj = [l for l in linhas if l["ajuste_eventos_bps"]]
    print(f"{len(linhas)} séries com pares | com ajuste por evento: {len(com_aj)}")
    for l in com_aj:
        print(f"  {l['codigo']}: {l['ajuste_eventos_bps']:+.1f} bps — {l['motivos_ajuste'][:140]}")


if __name__ == "__main__":
    main()
