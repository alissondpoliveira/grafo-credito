"""Gera o site estático (alissonprata.io) a partir dos dados do repositório.

Saída em site/public/: index.html (página pessoal) e grafo-credito/index.html
(página do projeto, com a tabela do universo de transmissão na data mais recente).

Uso: python site/gerar.py
"""

import csv
import html
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PUBLICO = RAIZ / "site" / "public"
DEB = RAIZ / "dados" / "anbima" / "debentures" / "normalizado"
TIT = RAIZ / "dados" / "anbima" / "titulos_publicos" / "normalizado"
UNIVERSO = RAIZ / "dados" / "referencia" / "universo_transmissao.csv"

CSS = """
:root{--bg:#fbfaf8;--fg:#1d1d1f;--muted:#6b6b70;--line:#e4e2dd;--accent:#1f4e79;--chip:#eef2f6}
@media (prefers-color-scheme:dark){:root{--bg:#141416;--fg:#ececee;--muted:#9a9aa0;--line:#2b2b2f;--accent:#8fb8e0;--chip:#1f2630}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 "Inter",system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:980px;margin:0 auto;padding:56px 16px 80px}
.estreito{max-width:640px}
h1{font-size:2rem;line-height:1.2;margin:0 0 .5rem;letter-spacing:-.01em}
h2{font-size:1.15rem;margin:2.5rem 0 .75rem}
p{margin:.5rem 0 1rem}
a{color:var(--accent)}
.muted{color:var(--muted)}
nav{font-size:.9rem;margin-bottom:2.5rem}
nav a{margin-right:1rem;text-decoration:none}
.links a{margin-right:1.25rem}
.tabela{overflow-x:auto;border:1px solid var(--line);border-radius:8px}
table{border-collapse:collapse;width:100%;font-size:.86rem;font-variant-numeric:tabular-nums}
th,td{padding:.5rem .65rem;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
th{font-weight:600;color:var(--muted);background:var(--chip);position:sticky;top:0}
td.t,th.t{text-align:left}
tr:last-child td{border-bottom:0}
.chip{display:inline-block;padding:.05rem .5rem;border-radius:99px;background:var(--chip);font-size:.78rem}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:1.25rem 0}
.card{border:1px solid var(--line);border-radius:8px;padding:.75rem 1rem}
.card b{display:block;font-size:1.4rem}
ol li{margin-bottom:.35rem}
footer{margin-top:3rem;font-size:.82rem;color:var(--muted);border-top:1px solid var(--line);padding-top:1rem}
"""


def pagina(titulo: str, descricao: str, corpo: str) -> str:
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(titulo)}</title>
<meta name="description" content="{html.escape(descricao)}">
<style>{CSS}</style>
</head>
<body>
{corpo}
</body>
</html>
"""


def ultimo_csv(pasta: Path) -> Path:
    return sorted(pasta.rglob("*.csv"))[-1]


def fmt(v: str, casas: int = 2) -> str:
    if v in ("", None):
        return "–"
    return f"{float(v):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gerar_home() -> str:
    corpo = """<main class="estreito">
<h1>Alisson Prata Oliveira</h1>
<p class="muted">Planejador financeiro CFP®, candidato ao CFA Level II e engenheiro de produção (UFTM). No mercado financeiro desde 2019.</p>

<h2>Financial Syntax</h2>
<p>Financial Syntax é onde publico análises de mercado escritas para o investidor que quer o mecanismo, não a manchete. Cada texto cita fonte e data, mostra a memória de cálculo e declara o que o modelo usado não mede.</p>

<h2>Projetos</h2>
<p><a href="/grafo-credito">Grafo de Crédito</a>: memória viva dos emissores de debêntures do crédito privado brasileiro, começando pelas transmissoras de energia.</p>

<p class="links" style="margin-top:2rem">
<a href="https://www.linkedin.com/in/alissonpoliveira">LinkedIn</a>
<a href="https://github.com/alissondpoliveira">GitHub</a>
</p>
</main>"""
    return pagina("Alisson Prata Oliveira", "Alisson Prata Oliveira: análise de mercado e crédito privado.", corpo)


def gerar_projeto() -> str:
    arq_deb = ultimo_csv(DEB)
    data_ref = arq_deb.stem
    arq_tit = TIT / data_ref[:4] / f"{data_ref}.csv"

    ntnb = {}
    if arq_tit.exists():
        for t in csv.DictReader(arq_tit.open(encoding="utf-8")):
            if t["titulo"] == "NTN-B" and t["taxa_indicativa"]:
                ntnb[t["vencimento"]] = float(t["taxa_indicativa"])

    grupos = {u["emissor"]: u["grupo_risco"] for u in csv.DictReader(UNIVERSO.open(encoding="utf-8"))}
    linhas = []
    for s in csv.DictReader(arq_deb.open(encoding="utf-8")):
        if s["emissor"] not in grupos:
            continue
        ref = ntnb.get(s["ntnb_referencia"])
        spread = ""
        if s["indexador_tipo"] == "IPCA_MAIS" and s["taxa_indicativa"] and ref is not None:
            spread = str((float(s["taxa_indicativa"]) - ref) * 100)
        linhas.append({**s, "grupo": grupos[s["emissor"]], "ntnb_taxa": ref, "spread_bps": spread})

    linhas.sort(key=lambda x: (x["grupo"].startswith("Isolada"), x["grupo"], x["emissor"], x["vencimento"]))
    n_emissores = len({l["emissor"] for l in linhas})
    n_grupos = len({l["grupo"] for l in linhas if not l["grupo"].startswith("Isolada")})
    n_isoladas = len({l["emissor"] for l in linhas if l["grupo"].startswith("Isolada")})
    spreads = sorted(float(l["spread_bps"]) for l in linhas if l["spread_bps"])
    mediana = spreads[len(spreads) // 2] if spreads else None

    trs = []
    for l in linhas:
        trs.append(
            "<tr>"
            f'<td class="t">{html.escape(l["codigo"])}</td>'
            f'<td class="t">{html.escape(l["emissor"].title())}</td>'
            f'<td class="t"><span class="chip">{html.escape(l["grupo"])}</span></td>'
            f'<td class="t">{html.escape(l["indexador_texto"])}</td>'
            f'<td>{l["vencimento"][8:10]}/{l["vencimento"][5:7]}/{l["vencimento"][:4]}</td>'
            f'<td>{fmt(l["taxa_indicativa"], 4)}</td>'
            f'<td>{fmt(l["ntnb_taxa"] if l["ntnb_taxa"] is not None else "", 4)}</td>'
            f'<td>{fmt(l["spread_bps"], 0)}</td>'
            f'<td>{fmt(l["duration_anos"], 2)}</td>'
            f'<td>{fmt(l["pu"], 2)}</td>'
            "</tr>"
        )

    dia = date.fromisoformat(data_ref).strftime("%d/%m/%Y")
    corpo = f"""<main>
<nav><a href="/">Alisson Prata Oliveira</a><a href="https://github.com/alissondpoliveira/grafo-credito">Código e dados</a></nav>
<h1>Grafo de Crédito</h1>
<p class="muted" style="max-width:680px">Memória viva dos emissores de debêntures do crédito privado brasileiro, organizada como grafo: emissões, garantias, covenants, grupo econômico, demonstrações financeiras e preços de mercado. Piloto: transmissoras de energia elétrica.</p>

<div class="cards">
<div class="card"><span class="muted">Data de referência</span><b>{dia}</b></div>
<div class="card"><span class="muted">Séries no universo</span><b>{len(linhas)}</b></div>
<div class="card"><span class="muted">Emissores</span><b>{n_emissores}</b></div>
<div class="card"><span class="muted">Grupos / isoladas</span><b>{n_grupos} / {n_isoladas}</b></div>
<div class="card"><span class="muted">Spread mediano IPCA+</span><b>{fmt(str(mediana), 0) if mediana is not None else "–"} bps</b></div>
</div>

<h2>Universo de transmissão</h2>
<p class="muted">Taxas indicativas ANBIMA. Spread = taxa indicativa menos a taxa indicativa da NTN-B de referência apontada pela própria ANBIMA, em pontos-base (método provisório, ainda sem interpolação por duration). O grupo de risco foi inferido pelo nome do emissor e ainda será confirmado nos documentos de cada emissão.</p>
<div class="tabela"><table>
<thead><tr><th class="t">Código</th><th class="t">Emissor</th><th class="t">Grupo de risco</th><th class="t">Remuneração</th><th>Vencimento</th><th>Taxa indicativa (%)</th><th>NTN-B ref. (%)</th><th>Spread (bps)</th><th>Duration (anos)</th><th>PU (R$)</th></tr></thead>
<tbody>
{chr(10).join(trs)}
</tbody></table></div>

<h2>Como o projeto avança</h2>
<ol>
<li>Coleta diária das taxas ANBIMA de debêntures e títulos públicos, guardando histórico próprio. <span class="chip">em produção</span></li>
<li>Universo piloto de transmissoras e grupos de risco. <span class="chip">em andamento</span></li>
<li>Grafo de emissores, grupos, garantias e cláusulas de cross-default.</li>
<li>Spread justo por comparáveis e resíduo de cada emissão.</li>
<li>Simulador de abertura e fechamento de spread (impacto no PU e break-even de carry).</li>
<li>Probabilidade de default implícita no spread versus fundamentos.</li>
</ol>

<footer>
Fonte: ANBIMA, mercado secundário de debêntures e de títulos públicos ({dia}). A taxa indicativa é referência de preço justo, não necessariamente negócio fechado.
Conteúdo de pesquisa e educacional. Não constitui recomendação de investimento.
</footer>
</main>"""
    return pagina("Grafo de Crédito", "Grafo de Crédito: debêntures de transmissão de energia, taxas ANBIMA e spread sobre NTN-B.", corpo)


def main() -> None:
    (PUBLICO / "grafo-credito").mkdir(parents=True, exist_ok=True)
    (PUBLICO / "index.html").write_text(gerar_home(), encoding="utf-8")
    (PUBLICO / "grafo-credito" / "index.html").write_text(gerar_projeto(), encoding="utf-8")
    print("site/public gerado")


if __name__ == "__main__":
    main()
