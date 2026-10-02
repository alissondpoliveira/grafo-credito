"""Fase 1: spread justo por comparáveis e desvio de cada papel.

Regressão cross-section (MQO, erros padrão robustos HC1) do spread comparável
das séries IPCA+ validadas na data mais recente. O desvio de cada papel é o
resíduo (observado menos ajustado), também em desvios-padrão dos resíduos.
Para as DI+ (amostra pequena), o desvio é contra a mediana das DI+.
Inclui a variação do spread no histórico disponível.

ESPECIFICAÇÃO PROVISÓRIA (a validar pelo Alisson; ver VARIAVEIS):
  spread_comparavel ~ duration_mod + garantia_real + controle_documentado
                      + ln(volume emitido) + dispersao_anbima

Uso: python analises/spread_justo.py
"""

import csv
import json
import math
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
PREC = RAIZ / "dados" / "derivados" / "precificacao"
SND = RAIZ / "dados" / "snd" / "caracteristicas.csv"
SAIDA = RAIZ / "dados" / "derivados" / "spread_justo"

VARIAVEIS = {
    "duration_mod": "Duration modificada (anos)",
    "garantia_real": "Garantia real (1 = sim)",
    "controle_documentado": "Controlador declarado na CVM (1 = sim)",
    "ln_volume": "ln(volume emitido, R$ milhões)",
    "liquidez": "Dias com negócio nos últimos 180 dias (%)",
    "tail": "Folga até o fim da concessão (anos)",
}
NEGOCIOS = RAIZ / "dados" / "snd" / "negocios.csv"
CONTRATOS = RAIZ / "dados" / "aneel" / "contratos_transmissao.csv"
UNIVERSO = RAIZ / "dados" / "referencia" / "universo_series.csv"


def liquidez_por_serie(data_ref: str) -> dict[str, dict]:
    """% de dias úteis com negócio e volume financeiro nos 180 dias corridos até a data de referência."""
    from datetime import date, timedelta
    fim = date.fromisoformat(data_ref)
    ini = (fim - timedelta(180)).isoformat()
    dias_uteis = sum(1 for k in range(180) if (fim - timedelta(k)).weekday() < 5)
    out: dict[str, dict] = {}
    if not NEGOCIOS.exists():
        return out
    for l in csv.DictReader(NEGOCIOS.open(encoding="utf-8")):
        if ini < l["data"] <= data_ref:
            d = out.setdefault(l["codigo"], {"dias": 0, "negocios": 0, "volume": 0.0})
            d["dias"] += 1
            d["negocios"] += int(l["negocios"])
            d["volume"] += int(l["quantidade"]) * float(l["pu_medio"])
    for d in out.values():
        d["pct_dias"] = 100 * d["dias"] / dias_uteis
    return out


def fim_concessao() -> dict[str, str]:
    fins: dict[str, str] = {}
    if CONTRATOS.exists():
        for l in csv.DictReader(CONTRATOS.open(encoding="utf-8")):
            if l["fim"] and l["fim"] > fins.get(l["cnpj"], ""):
                fins[l["cnpj"]] = l["fim"]
    return fins


def br(t: str) -> float:
    return float(t.replace(".", "").replace(",", "."))


def ols_hc1(X: np.ndarray, y: np.ndarray):
    n, k = X.shape
    xtx_inv = np.linalg.inv(X.T @ X)
    beta = xtx_inv @ X.T @ y
    e = y - X @ beta
    meat = X.T @ (X * (e ** 2)[:, None])
    cov = xtx_inv @ meat @ xtx_inv * n / (n - k)
    r2 = 1 - (e @ e) / ((y - y.mean()) @ (y - y.mean()))
    return beta, np.sqrt(np.diag(cov)), e, r2


def vif(X: np.ndarray) -> list[float]:
    out = []
    for j in range(1, X.shape[1]):
        outros = np.delete(X, j, axis=1)
        b = np.linalg.lstsq(outros, X[:, j], rcond=None)[0]
        res = X[:, j] - outros @ b
        r2 = 1 - (res @ res) / ((X[:, j] - X[:, j].mean()) @ (X[:, j] - X[:, j].mean()))
        out.append(1 / (1 - r2) if r2 < 1 else float("inf"))
    return out


def main() -> None:
    arquivos = sorted(p for p in PREC.glob("????-??-??.csv"))
    hoje = arquivos[-1]
    series = list(csv.DictReader(hoje.open(encoding="utf-8")))
    snd = {c["Codigo do Ativo"]: c for c in csv.DictReader(SND.open(encoding="utf-8"))}

    # histórico do spread (comparável para IPCA+, spread sobre CDI para DI+)
    hist: dict[str, list[tuple[str, float]]] = {}
    for a in arquivos:
        for s in csv.DictReader(a.open(encoding="utf-8")):
            v = s.get("zspread_comparavel_bps") if s["status"] == "ok" else s.get("spread_di_bps") if s["status"] == "ok DI+" else ""
            if v:
                hist.setdefault(s["codigo"], []).append((a.stem, float(v)))

    ipca = [s for s in series if s["status"] == "ok"]
    liq = liquidez_por_serie(hoje.stem)
    fins = fim_concessao()
    univ = {u["codigo"]: u for u in csv.DictReader(UNIVERSO.open(encoding="utf-8"))}
    seg = lambda cod: univ.get(cod, {}).get("segmento", "outro")

    # segmentos com poucas séries IPCA+ validadas entram como "outros" na regressão (evita coeficiente de 1 ou 2 pontos)
    from collections import Counter
    cont = Counter(seg(s["codigo"]) for s in ipca)
    seg_reg = lambda cod: seg(cod) if cont[seg(cod)] >= 4 else "outros"
    segmentos = sorted({seg_reg(s["codigo"]) for s in ipca} - {"transmissao"})

    extras = {}
    linhas_x, y, y_mercado, isenta = [], [], [], []
    for s in ipca:
        c = snd.get(s["codigo"], {})
        volume = br(c["Quantidade Emitida"]) * br(c["Valor Nominal na Emissao"]) / 1e6 if c.get("Quantidade Emitida") else None
        l = liq.get(s["codigo"], {"pct_dias": 0.0, "negocios": 0, "volume": 0.0})
        venc = c.get(" Data de Vencimento", c.get("Data de Vencimento", "")).strip()
        fim = fins.get(univ.get(s["codigo"], {}).get("cnpj", ""), "")
        tail = None
        if venc and fim:
            d, m, a = venc.split("/")
            tail = (int(fim[:4]) - int(a)) + (int(fim[5:7]) - int(m)) / 12
        extras[s["codigo"]] = {"segmento": seg(s["codigo"]), "liquidez_pct_dias": l["pct_dias"], "negocios_180d": l["negocios"],
                               "volume_negociado_180d_mi": l["volume"] / 1e6, "fim_concessao": fim, "tail_anos": tail}
        # tail só existe para transmissão (contratos ANEEL); nos demais segmentos entra 0 e o efeito fica no dummy do segmento
        tail_trans = (tail if tail is not None else 0.0) if seg(s["codigo"]) == "transmissao" else 0.0
        linhas_x.append([
            float(s["duration_mod_anos"]),
            1.0 if s["garantia"] == "Real" else 0.0,
            1.0 if s["fonte_grupo"] == "CVM FRE" else 0.0,
            math.log(volume) if volume else float("nan"),
            l["pct_dias"],
            tail_trans,
        ] + [1.0 if seg_reg(s["codigo"]) == g else 0.0 for g in segmentos])
        y.append(float(s["zspread_comparavel_bps"]))
        y_mercado.append(float(s["zspread_bps"]))
        isenta.append(1.0 if s["incentivada"] == "S" else 0.0)
    nomes = list(VARIAVEIS) + [f"seg_{g}" for g in segmentos]
    descricoes = dict(VARIAVEIS)
    descricoes["tail"] = "Folga até o fim da concessão (anos; só transmissão)"
    descricoes.update({f"seg_{g}": f"Segmento: {g.replace('_', ' ')} (vs transmissão)" for g in segmentos})
    X = np.array(linhas_x)
    y = np.array(y)
    usar = ~np.isnan(X).any(axis=1)
    Xc = np.column_stack([np.ones(usar.sum()), X[usar]])
    beta, se, e, r2 = ols_hc1(Xc, y[usar])
    vifs = vif(Xc)
    sd_e = float(np.std(e, ddof=Xc.shape[1]))
    ajustado = np.full(len(y), np.nan)
    ajustado[usar] = Xc @ beta

    # diagnóstico tributário: Z-spread de MERCADO (sem gross-up) com variável de isenção.
    # O coeficiente estima quanto o mercado desconta, em bps, por a debênture ser incentivada.
    Xt = np.column_stack([Xc, np.array(isenta)[usar]])
    bt, set_, _, r2t = ols_hc1(Xt, np.array(y_mercado)[usar])
    n_trib = int((1 - np.array(isenta)[usar]).sum())
    isencao = {"coef_bps": float(bt[-1]), "erro_padrao_hc1": float(set_[-1]), "r2": float(r2t),
               "n_tributadas": n_trib, "n_isentas": int(np.array(isenta)[usar].sum()),
               "leitura": "negativo = o mercado paga menos spread pela isenção; compare com o gross-up de 15% aplicado"}

    di = [s for s in series if s["status"] == "ok DI+"]
    # DI+: referência é a mediana do mesmo segmento (ou de todas as DI+ se o segmento tiver menos de 3)
    por_seg_di: dict[str, list[float]] = {}
    for s in di:
        por_seg_di.setdefault(seg(s["codigo"]), []).append(float(s["spread_di_bps"]))
    todas_di = [float(s["spread_di_bps"]) for s in di]
    ref_di = lambda cod: float(np.median(por_seg_di[seg(cod)])) if len(por_seg_di.get(seg(cod), [])) >= 3 else float(np.median(todas_di))
    sd_di = float(np.std(todas_di, ddof=1)) if len(todas_di) > 2 else None

    saida = []
    for i, s in enumerate(ipca):
        h = hist.get(s["codigo"], [])
        valores = [v for _, v in h]
        res = y[i] - ajustado[i] if not np.isnan(ajustado[i]) else None
        saida.append({
            "codigo": s["codigo"], "classe": "IPCA+", "spread_bps": y[i],
            "spread_justo_bps": None if np.isnan(ajustado[i]) else float(ajustado[i]),
            "desvio_bps": res, "desvio_em_dp": res / sd_e if res is not None else None,
            "variacao_hist_bps": valores[-1] - valores[0] if len(valores) > 1 else None,
            "dp_hist_bps": float(np.std(valores, ddof=1)) if len(valores) > 2 else None,
            "n_dias_hist": len(valores), "inicio_hist": h[0][0] if h else None,
            **extras.get(s["codigo"], {}),
        })
    for s in di:
        h = hist.get(s["codigo"], [])
        valores = [v for _, v in h]
        v = float(s["spread_di_bps"])
        r = ref_di(s["codigo"])
        saida.append({
            "codigo": s["codigo"], "classe": "DI+", "spread_bps": v, "spread_justo_bps": r,
            "desvio_bps": v - r, "desvio_em_dp": (v - r) / sd_di if sd_di else None,
            "variacao_hist_bps": valores[-1] - valores[0] if len(valores) > 1 else None,
            "dp_hist_bps": float(np.std(valores, ddof=1)) if len(valores) > 2 else None,
            "n_dias_hist": len(valores), "inicio_hist": h[0][0] if h else None,
            "segmento": seg(s["codigo"]),
        })

    SAIDA.mkdir(parents=True, exist_ok=True)
    campos = list(dict.fromkeys(k for l in saida for k in l))
    with (SAIDA / f"{hoje.stem}.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos, lineterminator="\n")
        w.writeheader()
        w.writerows(saida)
    modelo = {
        "data_referencia": hoje.stem, "n": int(usar.sum()), "r2": float(r2), "dp_residuos_bps": sd_e,
        "especificacao": "provisória, a validar",
        "coeficientes": [{"variavel": "constante", "descricao": "Constante (transmissão)", "coef": float(beta[0]), "erro_padrao_hc1": float(se[0]), "vif": None}]
        + [{"variavel": k, "descricao": descricoes[k], "coef": float(beta[j + 1]), "erro_padrao_hc1": float(se[j + 1]), "vif": float(vifs[j])}
           for j, k in enumerate(nomes)],
        "isencao": isencao,
        "di": {"n": len(di), "mediana_bps": float(np.median(todas_di)) if todas_di else None, "dp_bps": sd_di},
    }
    (SAIDA / f"{hoje.stem}_modelo.json").write_text(json.dumps(modelo, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"IPCA+: n={modelo['n']} R²={r2:.2f} dp resíduos={sd_e:.0f} bps")
    for c in modelo["coeficientes"]:
        t = c["coef"] / c["erro_padrao_hc1"] if c["erro_padrao_hc1"] else float("nan")
        print(f"  {c['descricao'][:46]:46} {c['coef']:9.2f}  t={t:6.2f}  VIF={c['vif'] if c['vif'] is None else round(c['vif'], 2)}")
    print(f"Isenção (Z de mercado): {isencao['coef_bps']:.1f} bps (t={isencao['coef_bps'] / isencao['erro_padrao_hc1']:.2f}); "
          f"{isencao['n_tributadas']} tributadas, {isencao['n_isentas']} isentas")
    print(f"DI+: n={len(di)}")


if __name__ == "__main__":
    main()
