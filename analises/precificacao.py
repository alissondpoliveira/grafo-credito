"""Motor de precificação das debêntures IPCA+ do universo.

Para cada série: monta o fluxo real remanescente (agenda SND), reprecifica pela
taxa indicativa ANBIMA (validação contra o PU e a duration ANBIMA), calcula o
Z-spread sobre a curva real ETTJ IPCA, o Z-spread após gross-up tributário das
incentivadas, sensibilidade a choques de spread e break-even de carry.

Convenções (fato = documentado pela ANBIMA/SND; escolha = decisão do projeto):
- dias úteis/252, capitalização exponencial (fato: critério SND das séries)
- calendário: feriados nacionais (fato: ANBIMA usa feriados nacionais)
- juros de cada evento sobre o saldo antes da amortização do mesmo dia
- Z-spread somado à taxa spot da curva real, curva Svensson ANBIMA (escolha, CFA L2)
- gross-up: alíquota ALIQUOTA_GROSS_UP (15%, decisão do Alisson em 02/10/2026) sobre a taxa nominal das incentivadas,
  com inflação implícita da ETTJ; 'zspread_comparavel_bps' = gross-up nas isentas, Z-spread puro nas demais
- break-even: quanto o spread pode abrir no horizonte até a perda de preço igualar o carry do spread (escolha)

Uso: python analises/precificacao.py [AAAA-MM-DD]
"""

import csv
import math
import sys
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DEB = RAIZ / "dados" / "anbima" / "debentures" / "normalizado"
ETTJ = RAIZ / "dados" / "anbima" / "ettj" / "normalizado"
SND = RAIZ / "dados" / "snd"
UNIVERSO = RAIZ / "dados" / "referencia" / "universo_series.csv"
SAIDA = RAIZ / "dados" / "derivados" / "precificacao"

ALIQUOTA_GROSS_UP = 0.15
CHOQUES_BPS = [-100, -50, 50, 100, 200]
HORIZONTES_MESES = [6, 12]
TOLERANCIA_PU = 0.005  # 0,5%: acima disso o fluxo da série é tratado como não confiável


# ---------- calendário ----------

def pascoa(ano: int) -> date:
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return date(ano, mes, dia)


@lru_cache(maxsize=None)
def feriados(ano: int) -> frozenset:
    fixos = [(1, 1), (4, 21), (5, 1), (9, 7), (10, 12), (11, 2), (11, 15), (12, 25)]
    if ano >= 2024:
        fixos.append((11, 20))
    p = pascoa(ano)
    moveis = [p - timedelta(48), p - timedelta(47), p - timedelta(2), p + timedelta(60)]
    return frozenset([date(ano, m, d) for m, d in fixos] + moveis)


def util(d: date) -> bool:
    return d.weekday() < 5 and d not in feriados(d.year)


def du(d0: date, d1: date) -> int:
    """Dias úteis em [d0, d1)."""
    if d1 <= d0:
        return 0
    n, d = 0, d0
    while d < d1:
        if util(d):
            n += 1
        d += timedelta(1)
    return n


def menos_meses(d: date, meses: int) -> date:
    m = d.month - meses
    a = d.year + (m - 1) // 12
    m = (m - 1) % 12 + 1
    for dia in (d.day, 30, 29, 28):
        try:
            return date(a, m, dia)
        except ValueError:
            continue
    raise ValueError(d)


# ---------- curva ----------

def svensson(p: dict, t: float) -> float:
    b1, b2, b3, b4, l1, l2 = (p[k] for k in ("beta1", "beta2", "beta3", "beta4", "lambda1", "lambda2"))
    t = max(t, 1e-6)
    x1, x2 = l1 * t, l2 * t  # forma ANBIMA: (1 - e^(-λt)) / (λt); confere com os vértices publicados
    f1 = (1 - math.exp(-x1)) / x1
    f2 = f1 - math.exp(-x1)
    f3 = (1 - math.exp(-x2)) / x2 - math.exp(-x2)
    return b1 + b2 * f1 + b3 * f2 + b4 * f3


def ler_curvas(data_ref: str) -> dict:
    arq = ETTJ / data_ref[:4] / f"{data_ref}_parametros.csv"
    return {r["curva"]: {k: float(v) for k, v in r.items() if k not in ("data_referencia", "curva")}
            for r in csv.DictReader(arq.open(encoding="utf-8"))}


# ---------- fluxo ----------

def br(texto: str) -> float:
    return float(texto.replace(".", "").replace(",", "."))


def dt(texto: str) -> date:
    return datetime.strptime(texto.strip(), "%d/%m/%Y").date()


@lru_cache(maxsize=None)
def ipca_mensal() -> dict:
    arq = RAIZ / "dados" / "bcb" / "ipca_mensal.csv"
    return {r["mes"]: float(r["variacao_pct"]) for r in csv.DictReader(arq.open(encoding="utf-8"))}


def fator_ipca(inicio: date, fim: date) -> float:
    """Fator acumulado do IPCA mensal entre o mês de início e o mês anterior ao fim (aproximação sem pró-rata)."""
    serie, fator = ipca_mensal(), 1.0
    a, m = inicio.year, inicio.month
    while (a, m) < (fim.year, fim.month):
        fator *= 1 + serie.get(f"{a}-{m:02d}", 0.0) / 100
        m += 1
        if m == 13:
            a, m = a + 1, 1
    return fator


def montar_fluxo(carac: dict, eventos: list[dict], data_ref: date, vna_corrigido: bool = True) -> tuple[list[tuple[date, float]], str]:
    """Fluxo real por unidade de saldo atual (saldo = 1 na data de referência)."""
    taxa = br(carac["Juros Criterio Novo - Taxa"]) / 100
    cada = int(carac["Juros Criterio Novo - Cada"] or 0)
    tipo_amort = carac.get("Tipo de Amortizacao", "")
    sobre_emissao = "de emiss" in tipo_amort

    evs = sorted(
        (e for e in eventos if e["Evento"] in ("Juros", "Amortização", "Vencimento") and dt(e["Data do Evento"]) > data_ref),
        key=lambda e: (dt(e["Data do Evento"]), e["Evento"] != "Juros"),
    )
    if not evs:
        return [], "sem eventos futuros"

    inicio = dt(carac["Data do Inicio da Rentabilidade"]) if carac.get("Data do Inicio da Rentabilidade") else None

    # amortização sobre valor de emissão: percentuais são do VNE original, então é preciso saber
    # que fração do VNE ainda está em aberto (R). Sem amortização passada, R = 1; com amortização
    # passada, R sai do VNA do SND descontada a correção pelo IPCA desde o início da rentabilidade.
    fracao_vne = 1.0
    carencia_amort = carac.get("Amortizacao - Carencia", "")
    if sobre_emissao and carencia_amort and dt(carencia_amort) <= data_ref:
        try:
            vna = br(carac["Valor Nominal Atual"])
            vne = br(carac["Valor Nominal na Emissao"])
        except (KeyError, ValueError):
            return [], "amortização sobre emissão sem VNA"
        # o SND publica o VNA ora corrigido pelo IPCA, ora só pelo saldo; quem chama testa as duas leituras
        estimado = vna / (vne * (fator_ipca(inicio, data_ref) if vna_corrigido else 1.0))
        arredondado = round(estimado / 0.005) * 0.005
        fracao_vne = arredondado if abs(arredondado - estimado) < 0.004 else estimado

    primeiro_juros = next((dt(e["Data do Evento"]) for e in evs if e["Evento"] == "Juros"), None)
    if primeiro_juros is None:
        return [], "sem juros futuros"
    carencia_juros = carac.get("Juros Criterio Novo - Carencia", "")
    if carencia_juros and dt(carencia_juros) >= primeiro_juros:
        ultimo = inicio  # ainda não houve pagamento de juros: acumula desde o início da rentabilidade
    else:
        ultimo = menos_meses(primeiro_juros, cada) if cada else inicio
        if inicio and (ultimo is None or inicio > ultimo):
            ultimo = inicio

    saldo, fluxo = 1.0, {}
    for e in evs:
        d_ev, d_pg = dt(e["Data do Evento"]), dt(e["Data do Pagamento"] or e["Data do Evento"])
        if e["Evento"] == "Juros":
            valor = saldo * ((1 + taxa) ** (du(ultimo, d_ev) / 252) - 1)
            ultimo = d_ev
        elif e["Evento"] == "Amortização":
            pct = br(e["Taxa/Percentual"]) / 100
            valor = pct / fracao_vne if sobre_emissao else saldo * pct
            valor = min(valor, saldo)
            saldo -= valor
        else:  # vencimento: paga o saldo remanescente
            valor, saldo = saldo, 0.0
        if valor > 0:
            fluxo[d_pg] = fluxo.get(d_pg, 0.0) + valor
    if saldo > 1e-6:
        d_final = max(fluxo)
        fluxo[d_final] += saldo
    return sorted(fluxo.items()), ""


# ---------- métricas ----------

def em_anos(fluxo, data_ref) -> list[tuple[float, float]]:
    """Converte (data, valor) em (prazo em anos úteis, valor) uma única vez por série."""
    return [(du(data_ref, d) / 252, cf) for d, cf in fluxo]


def preco(fluxo_t, taxa: float, curva=None, z: float = 0.0) -> float:
    total = 0.0
    for t, cf in fluxo_t:
        r = (svensson(curva, t) if curva else 0.0) + taxa + z
        total += cf / (1 + r) ** t
    return total


def resolver(f, alvo: float, lo: float = -0.2, hi: float = 0.5) -> float:
    for _ in range(80):
        meio = (lo + hi) / 2
        if f(meio) > alvo:
            lo = meio
        else:
            hi = meio
    return (lo + hi) / 2


def duration_mac(fluxo_t, y: float) -> float:
    return sum(t * cf / (1 + y) ** t for t, cf in fluxo_t) / preco(fluxo_t, y)


def grossup_real(y_real: float, infl: float, aliquota: float) -> float:
    nominal = (1 + y_real) * (1 + infl) - 1
    return (1 + nominal / (1 - aliquota)) / (1 + infl) - 1


def main(data_ref_txt: str | None) -> None:
    if data_ref_txt:
        arq_deb = DEB / data_ref_txt[:4] / f"{data_ref_txt}.csv"
    else:  # data mais recente que tenha debêntures e curva
        arq_deb = [a for a in sorted(DEB.rglob("*.csv")) if (ETTJ / a.stem[:4] / f"{a.stem}_parametros.csv").exists()][-1]
    data_ref = date.fromisoformat(arq_deb.stem)
    curvas = ler_curvas(arq_deb.stem)
    universo = {u["codigo"]: u for u in csv.DictReader(UNIVERSO.open(encoding="utf-8"))}
    caracs = {c["Codigo do Ativo"]: c for c in csv.DictReader((SND / "caracteristicas.csv").open(encoding="utf-8"))}
    agenda = {}
    for e in csv.DictReader((SND / "agenda.csv").open(encoding="utf-8")):
        agenda.setdefault(e["Ativo"], []).append(e)

    linhas, fluxos_json = [], {}
    for s in csv.DictReader(arq_deb.open(encoding="utf-8")):
        u = universo.get(s["codigo"])
        if not u or u["no_piloto"] != "S":
            continue
        c = caracs.get(s["codigo"], {})
        base = {
            "data_referencia": data_ref.isoformat(),
            "codigo": s["codigo"],
            "emissor": s["emissor"],
            "emissor_atual": u["emissor_atual_snd"],
            "grupo_risco": u["grupo_risco"],
            "fonte_grupo": u["fonte_grupo"],
            "indexador_tipo": s["indexador_tipo"],
            "incentivada": c.get("Deb. Incent. (Lei 12.431)", ""),
            "garantia": c.get("Garantia/Especie", ""),
            "resgate_antecipado_snd": c.get("Resgate Antecipado", ""),
            "emissor_snd": c.get("Empresa", ""),
            "cnpj_snd": c.get("CNPJ", ""),
            "taxa_indicativa": s["taxa_indicativa"],
            "pu_anbima": s["pu"],
            "duration_anbima_anos": s["duration_anos"],
        }
        status = ""
        if s["indexador_tipo"] != "IPCA_MAIS":
            status = "fora do escopo (não IPCA+)"
        elif not s["taxa_indicativa"]:
            status = "sem taxa indicativa"
        elif not c:
            status = "sem características SND"
        if status:
            linhas.append({**base, "status": status})
            continue

        y = float(s["taxa_indicativa"]) / 100
        dur_anbima = float(s["duration_anos"]) if s["duration_anos"] else None
        candidatos = []
        for leitura in (True, False):
            f, erro = montar_fluxo(c, agenda.get(s["codigo"], []), data_ref, vna_corrigido=leitura)
            if erro:
                continue
            f = em_anos(f, data_ref)
            e = abs(duration_mac(f, y) - dur_anbima) if dur_anbima else 0.0
            candidatos.append((e, leitura, f))
        if not candidatos:
            linhas.append({**base, "status": erro})
            continue
        _, leitura_vna, fluxo = min(candidatos, key=lambda x: x[0])
        base["leitura_vna_snd"] = "corrigido IPCA" if leitura_vna else "sem correção"
        p_real = preco(fluxo, y)
        dmac = duration_mac(fluxo, y)
        dmod = dmac / (1 + y)
        erro_dur = (dmac - dur_anbima) / dur_anbima if dur_anbima else None

        # validação: duration ANBIMA (independe do VNA); PU só se o VNA do SND estiver na data
        status = "ok" if erro_dur is not None and abs(erro_dur) <= 0.02 else "fluxo divergente da ANBIMA"

        z = resolver(lambda zz: preco(fluxo, 0.0, curvas["IPCA"], zz), p_real)
        t_dur = dmac
        infl = (1 + svensson(curvas["PREFIXADOS"], t_dur)) / (1 + svensson(curvas["IPCA"], t_dur)) - 1
        z_gu = ""
        if base["incentivada"] == "S":
            y_gu = grossup_real(y, infl, ALIQUOTA_GROSS_UP)
            p_gu = preco(fluxo, y_gu)
            z_gu = resolver(lambda zz: preco(fluxo, 0.0, curvas["IPCA"], zz), p_gu) * 1e4

        h = 1e-4
        p_up, p_dn = preco(fluxo, y + h), preco(fluxo, y - h)
        convex = (p_up + p_dn - 2 * p_real) / (h * h * p_real)

        choques = {}
        for bps in CHOQUES_BPS:
            ds = bps / 1e4
            choques[f"choque_{bps}_pct"] = (preco(fluxo, y + ds) / p_real - 1) * 100
            choques[f"choque_{bps}_aprox_pct"] = (-dmod * ds + 0.5 * convex * ds * ds) * 100

        breakeven = {}
        for meses in HORIZONTES_MESES:
            carry = z * meses / 12
            breakeven[f"breakeven_{meses}m_bps"] = carry / dmod * 1e4 if dmod else ""

        if status == "ok":
            fluxos_json[s["codigo"]] = {"y": y, "t": [round(t, 6) for t, _ in fluxo], "cf": [round(cf, 8) for _, cf in fluxo]}
        linhas.append({
            **base,
            "status": status,
            "n_fluxos": len(fluxo),
            "preco_real_por_saldo": p_real,
            "duration_mac_modelo_anos": dmac,
            "erro_duration_pct": erro_dur * 100 if erro_dur is not None else "",
            "duration_mod_anos": dmod,
            "convexidade": convex,
            "zspread_bps": z * 1e4,
            "inflacao_implicita_na_duration_pct": infl * 100,
            "zspread_grossup_bps": z_gu,
            "zspread_comparavel_bps": z_gu if z_gu != "" else z * 1e4,
            **choques,
            **breakeven,
        })

    SAIDA.mkdir(parents=True, exist_ok=True)
    destino = SAIDA / f"{data_ref.isoformat()}.csv"
    campos = list(dict.fromkeys(k for l in linhas for k in l))
    with destino.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos, lineterminator="\n")
        w.writeheader()
        w.writerows(linhas)

    import json
    (SAIDA / f"{data_ref.isoformat()}_fluxos.json").write_text(json.dumps(fluxos_json), encoding="utf-8")

    from collections import Counter
    print(f"{destino.relative_to(RAIZ)}: {len(linhas)} séries")
    print(Counter(l["status"] for l in linhas))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
