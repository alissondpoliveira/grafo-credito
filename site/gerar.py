"""Gera o site estático (alissonprata.io) a partir dos dados do repositório.

Saída em site/public/: index.html (página pessoal) e grafo-credito/index.html
(mapa de controle e risco, desvio em relação aos pares, simulador, tabela e modelo).

Uso: python site/gerar.py
"""

import csv
import html
import re
import unicodedata
import json
import statistics
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PUBLICO = RAIZ / "site" / "public"
PREC = RAIZ / "dados" / "derivados" / "precificacao"
JUSTO = RAIZ / "dados" / "derivados" / "spread_justo"
UNIVERSO = RAIZ / "dados" / "referencia" / "universo_series.csv"
CONTROLADORES = RAIZ / "dados" / "referencia" / "controladores_cvm.csv"
CLAUSULAS = RAIZ / "dados" / "referencia" / "clausulas_escrituras.csv"

FONTES = '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Newsreader:opsz,wght@6..72,500;6..72,600&display=swap" rel="stylesheet">'

# Tokens: superfícies e tintas neutras + par divergente azul/vermelho da paleta de referência (dataviz)
CSS = """
:root{color-scheme:light;
 --bg:#f7f6f3;--surface:#fcfcfb;--surface-2:#f0efec;--ink:#0b0b0b;--ink-2:#52514e;--ink-3:#8a8984;--line:#e2e0da;--line-2:#d3d1ca;
 --accent:#1c5cab;--hull:rgba(82,81,78,.06);--hull-line:rgba(82,81,78,.28);--edge:#b5b3ab;
 --div-neg-2:#1c5cab;--div-neg-1:#86b6ef;--div-0:#d9d7d1;--div-pos-1:#f0a3a2;--div-pos-2:#c7302f;--doc-oficial:#4a3aa7;--doc-noticia:#eda100;--doc-analise:#e87ba4;}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){color-scheme:dark;
 --bg:#121211;--surface:#1a1a19;--surface-2:#232321;--ink:#ffffff;--ink-2:#c3c2b7;--ink-3:#8a8984;--line:#2c2c2a;--line-2:#3a3a37;
 --accent:#6da7ec;--hull:rgba(195,194,183,.06);--hull-line:rgba(195,194,183,.25);--edge:#4d4c48;
 --div-neg-2:#3987e5;--div-neg-1:#1c4f8f;--div-0:#4a4a46;--div-pos-1:#8f3534;--div-pos-2:#e66767;--doc-oficial:#9085e9;--doc-noticia:#c98500;--doc-analise:#d55181;}}
:root[data-theme="dark"]{color-scheme:dark;
 --bg:#121211;--surface:#1a1a19;--surface-2:#232321;--ink:#ffffff;--ink-2:#c3c2b7;--ink-3:#8a8984;--line:#2c2c2a;--line-2:#3a3a37;
 --accent:#6da7ec;--hull:rgba(195,194,183,.06);--hull-line:rgba(195,194,183,.25);--edge:#4d4c48;
 --div-neg-2:#3987e5;--div-neg-1:#1c4f8f;--div-0:#4a4a46;--div-pos-1:#8f3534;--div-pos-2:#e66767;--doc-oficial:#9085e9;--doc-noticia:#c98500;--doc-analise:#d55181;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 Inter,system-ui,-apple-system,"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased}
main{max-width:1120px;margin:0 auto;padding:40px 16px 80px}
.estreito{max-width:640px;padding-top:72px}
h1,h2,.serif{font-family:Newsreader,Georgia,serif;font-weight:600;letter-spacing:-.01em}
h1{font-size:2.6rem;line-height:1.1;margin:.25rem 0 .75rem}
h2{font-size:1.45rem;margin:0 0 .35rem}
h3{font-size:.95rem;margin:1.25rem 0 .4rem}
p{margin:.4rem 0 .9rem}
a{color:var(--accent)}
.kicker{font-size:.75rem;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-3)}
.dek{color:var(--ink-2);font-size:1.05rem;max-width:720px}
.muted{color:var(--ink-2)}.fraco{color:var(--ink-3)}.pequeno{font-size:.82rem}
nav{display:flex;justify-content:space-between;align-items:center;font-size:.85rem;padding-bottom:28px;border-bottom:1px solid var(--line);margin-bottom:28px}
nav a{color:var(--ink-2);text-decoration:none;margin-left:1.1rem}nav a:first-child{margin-left:0;color:var(--ink);font-weight:600}
section{margin-top:48px}
.cab{display:flex;justify-content:space-between;align-items:end;gap:16px;flex-wrap:wrap;margin-bottom:12px}
.cab p{margin:0;max-width:640px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:1px;background:var(--line);border:1px solid var(--line);border-radius:10px;overflow:hidden;margin-top:28px}
.tile{background:var(--surface);padding:14px 16px}
.tile span{display:block;font-size:.76rem;color:var(--ink-2)}
.tile b{display:block;font-size:1.55rem;font-weight:600;font-variant-numeric:tabular-nums;margin-top:2px}
.tile small{color:var(--ink-3);font-size:.74rem}
.painel{background:var(--surface);border:1px solid var(--line);border-radius:10px}
#grafo{width:100%;height:auto;aspect-ratio:16/10;display:block;touch-action:none;border-radius:10px}
.controles{display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:10px 12px;border-bottom:1px solid var(--line)}
.controles label{font-size:.8rem;color:var(--ink-2);display:inline-flex;gap:6px;align-items:center}
select,input,button{font:inherit;font-size:.85rem;color:var(--ink);background:var(--surface);border:1px solid var(--line-2);border-radius:6px;padding:.35rem .55rem}
button{cursor:pointer;background:var(--surface-2)}
button.ativo{background:var(--ink);color:var(--surface);border-color:var(--ink)}
.legenda{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:.78rem;color:var(--ink-2);padding:10px 12px;border-top:1px solid var(--line)}
.legenda i{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px;vertical-align:-1px}
.escala{display:inline-flex;align-items:center;gap:6px}.escala b{display:inline-flex}.escala b i{width:18px;height:10px;border-radius:2px;margin:0 1px 0 0}
.tip{position:fixed;pointer-events:none;background:var(--surface);color:var(--ink);border:1px solid var(--line-2);border-radius:8px;padding:8px 10px;font-size:.8rem;line-height:1.45;max-width:300px;display:none;z-index:20;box-shadow:0 6px 24px rgba(0,0,0,.14)}
.tip b{font-weight:600}.tip .l{display:flex;justify-content:space-between;gap:14px;font-variant-numeric:tabular-nums}.tip .l span:first-child{color:var(--ink-2)}
#desvio{width:100%;display:block}
.sim{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.35fr);gap:0}
.sim>div{padding:16px}.sim>div:first-child{border-right:1px solid var(--line)}
@media (max-width:760px){.sim{grid-template-columns:1fr}.sim>div:first-child{border-right:0;border-bottom:1px solid var(--line)}}
.sim label{display:block;font-size:.78rem;color:var(--ink-2);margin:.7rem 0 .25rem}.sim label:first-child{margin-top:0}
.sim select,.sim input{width:100%}
.botoes{display:flex;flex-wrap:wrap;gap:6px;margin-top:.6rem}
.res{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1px;background:var(--line);border:1px solid var(--line);border-radius:8px;overflow:hidden}
.res div{background:var(--surface);padding:10px 12px}
.res small{color:var(--ink-2);display:block;font-size:.74rem}
.res b{font-size:1.15rem;font-weight:600;font-variant-numeric:tabular-nums}
.tabela{overflow:auto;max-height:640px}
table{border-collapse:collapse;width:100%;font-size:.8rem;font-variant-numeric:tabular-nums}
th,td{padding:.42rem .6rem;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
th{font-weight:600;color:var(--ink-2);background:var(--surface-2);position:sticky;top:0;cursor:pointer;user-select:none;z-index:1}
th:hover{color:var(--ink)}
td.t,th.t{text-align:left}
tbody tr[data-codigo]{cursor:pointer}tbody tr:hover{background:var(--surface-2)}
.marca{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;vertical-align:0}
.selo{display:inline-block;padding:0 .4rem;border-radius:4px;font-size:.7rem;border:1px solid var(--line-2);color:var(--ink-2)}
.coef td:first-child{text-align:left}
ul.metodo li{margin-bottom:.45rem;color:var(--ink-2)}ul.metodo b{color:var(--ink)}
input[type=range]{-webkit-appearance:none;appearance:none;width:100%;height:28px;background:transparent;padding:0;border:0;cursor:pointer}
input[type=range]::-webkit-slider-runnable-track{height:6px;border-radius:3px;background:linear-gradient(90deg,var(--div-neg-2),var(--div-0) 50%,var(--div-pos-2))}
input[type=range]::-moz-range-track{height:6px;border-radius:3px;background:linear-gradient(90deg,var(--div-neg-2),var(--div-0) 50%,var(--div-pos-2))}
input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:18px;height:18px;border-radius:50%;background:var(--surface);border:2px solid var(--ink);margin-top:-6px;box-shadow:0 1px 4px rgba(0,0,0,.2)}
input[type=range]::-moz-range-thumb{width:16px;height:16px;border-radius:50%;background:var(--surface);border:2px solid var(--ink)}
.regua-marcas{display:flex;justify-content:space-between;font-size:.7rem;color:var(--ink-3);margin-top:-4px;font-variant-numeric:tabular-nums}
#curva{width:100%;height:auto;aspect-ratio:2.2/1;display:block;margin-top:10px;touch-action:none}
#ficha{margin-top:12px;padding:16px;display:none}
#ficha h3{margin:0 0 .2rem;font-family:Newsreader,Georgia,serif;font-size:1.2rem}
.ficha-grade{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;margin-top:12px}
.ficha-grade h4{margin:0 0 .35rem;font-size:.76rem;text-transform:uppercase;letter-spacing:.06em;color:var(--ink-3)}
.ficha-grade ul{list-style:none;margin:0;padding:0}.ficha-grade li{font-size:.8rem;padding:.25rem 0;border-bottom:1px solid var(--line)}
.ficha-grade li span{color:var(--ink-3);font-variant-numeric:tabular-nums;margin-right:6px}
.ficha-grade a{color:var(--ink);text-decoration:none}.ficha-grade a:hover{color:var(--accent);text-decoration:underline}
footer{margin-top:56px;font-size:.78rem;color:var(--ink-3);border-top:1px solid var(--line);padding-top:16px}
.links a{margin-right:1.25rem}
"""


def pagina(titulo: str, descricao: str, corpo: str) -> str:
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(titulo)}</title>
<meta name="description" content="{html.escape(descricao)}">
{FONTES}
<style>{CSS}</style>
</head>
<body>
{corpo}
</body>
</html>
"""


def num(v, casas=2):
    if v in ("", None):
        return "–"
    return f"{float(v):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gerar_home() -> str:
    corpo = """<main class="estreito">
<div class="kicker">Pesquisa em crédito e mercado</div>
<h1>Alisson Prata Oliveira</h1>
<p class="dek">Planejador financeiro CFP®, candidato ao CFA Level II e engenheiro de produção (UFTM). No mercado financeiro desde 2019.</p>

<section>
<h2>Financial Syntax</h2>
<p class="muted">Financial Syntax é onde publico análises de mercado escritas para o investidor que quer o mecanismo, não a manchete. Cada texto cita fonte e data, mostra a memória de cálculo e declara o que o modelo usado não mede.</p>
</section>

<section>
<h2>Projetos</h2>
<p class="muted"><a href="/grafo-credito">Grafo de Crédito</a>: memória viva dos emissores de debêntures do crédito privado brasileiro, começando pelas transmissoras de energia.</p>
</section>

<p class="links" style="margin-top:2.5rem">
<a href="https://www.linkedin.com/in/alissonpoliveira">LinkedIn</a>
<a href="https://github.com/alissondpoliveira">GitHub</a>
</p>
</main>"""
    return pagina("Alisson Prata Oliveira", "Alisson Prata Oliveira: análise de mercado e crédito privado.", corpo)


def sem_acento(t: str) -> str:
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()


def ler_csv(p: Path) -> list[dict]:
    return list(csv.DictReader(p.open(encoding="utf-8"))) if p.exists() else []


CATEGORIA_DOC = {"fato_relevante": "oficial", "comunicado": "oficial", "aviso_debenturistas": "oficial",
                 "escritura": "escritura", "noticia": "noticia", "analise": "analise"}


def montar_grafo(series: list[dict], universo: dict, desvios: dict, clausulas: dict, documentos: dict, jev: dict) -> dict:
    revisao = {}
    for r in ler_csv(RAIZ / "dados" / "referencia" / "revisao_escrituras.csv"):
        revisao.setdefault(r["codigo"], []).append(r)
    controladores = {}
    for c in ler_csv(CONTROLADORES):
        controladores.setdefault(c["cnpj_companhia"], []).append(c)

    nos, links, vistos, pendentes_escritura = [], [], set(), []

    def no(i, **kw):
        if i not in vistos:
            vistos.add(i)
            nos.append({"id": i, **kw})

    for s in series:
        u = universo[s["codigo"]]
        g = u["grupo_risco"]
        em_id = "e:" + u["cnpj"]
        if em_id not in vistos:
            # documentos do emissor (até 4 mais recentes por categoria) entram como nós filhos
            por_cat: dict[str, int] = {}
            for i, d in enumerate(documentos.get(u["cnpj"], [])):
                cat = CATEGORIA_DOC[d["tipo"]]
                if por_cat.get(cat, 0) >= 4:
                    continue
                por_cat[cat] = por_cat.get(cat, 0) + 1
                d_id = f"d:{u['cnpj']}:{i}"
                cl = jev.get(f"{u['cnpj']}|{d['tipo']}|{d.get('data', '')}|{d['titulo'][:60]}", {})
                no(d_id, tipo="doc", categoria=cat, subtipo=d["tipo"], rotulo=d["titulo"][:90], data=d.get("data", ""),
                   fonte=d.get("fonte", ""), url=d.get("url", ""), grupo=g,
                   evento=cl.get("evento"), impacto=cl.get("impacto"), confianca=cl.get("evento_confianca"), status_jev=cl.get("status"))
                links.append({"source": em_id, "target": d_id, "tipo": "doc"})
        no(em_id, tipo="emissor", rotulo=u["emissor_atual_snd"].title(), grupo=g, cnpj=u["cnpj"],
           detalhe=f"CNPJ {u['cnpj']}" + (f" · nome ANBIMA: {u['emissor_anbima'].title()}" if u["emissor_anbima"] != u["emissor_atual_snd"] else ""))
        d = desvios.get(s["codigo"], {})
        no("s:" + s["codigo"], tipo="serie", rotulo=s["codigo"], grupo=g,
           spread=d.get("spread"), justo=d.get("justo"), desvio=d.get("desvio"), dp=d.get("dp"), classe=d.get("classe"),
           status=s["status"])
        links.append({"source": em_id, "target": "s:" + s["codigo"], "tipo": "emitiu"})

        if u["fonte_grupo"] == "CVM FRE":
            for c in controladores.get(u["cnpj"], []):
                c_id = "c:" + (c["cnpj_controlador"] or c["controlador"])
                no(c_id, tipo="controlador", rotulo=c["controlador"], grupo=g, detalhe="controlador declarado na CVM")
                alvo = em_id
                if c["socio_de"]:
                    alvo = "c:" + (c["cnpj_socio_de"] or c["socio_de"])
                    no(alvo, tipo="controlador", rotulo=c["socio_de"], grupo=g, detalhe="controlador declarado na CVM")
                links.append({"source": c_id, "target": alvo, "tipo": "controla"})
        elif u["fonte_grupo"] == "escritura":
            pendentes_escritura.append((s, u, em_id, g))
        elif u["fonte_grupo"] == "inferido":
            g_id = "g:" + g
            no(g_id, tipo="grupo", rotulo=g, grupo=g, detalhe="grupo inferido, a confirmar na escritura")
            links.append({"source": g_id, "target": em_id, "tipo": "inferido"})

        # ligações de risco lidas nas escrituras (status 'a revisar' até revisão humana)
        cl = clausulas.get(s["codigo"])
        if cl and cl.get("fiadora"):
            alvo_nome = sem_acento(cl["fiadora"]).upper()[:18]
            existente = next((n for n in nos if n["tipo"] in ("controlador", "emissor") and sem_acento(n["rotulo"]).upper().startswith(alvo_nome)), None)
            f_id = existente["id"] if existente else "f:" + cl["fiadora"].upper()
            if not existente:
                no(f_id, tipo="garantidor", rotulo=cl["fiadora"], grupo=g, detalhe="fiadora citada na escritura (a revisar)")
            links.append({"source": f_id, "target": "s:" + s["codigo"], "tipo": "garante"})
        if cl and cl.get("cross_default") == "S" and any(x in cl.get("cross_default_abrange", "") for x in ("Controladora", "Fiadora", "Acionista")):
            for c in controladores.get(u["cnpj"], []):
                if not c["socio_de"]:
                    links.append({"source": "c:" + (c["cnpj_controlador"] or c["controlador"]), "target": "s:" + s["codigo"], "tipo": "cross"})

    # partes citadas nas escrituras: reaproveita o nó do controlador da CVM quando é a mesma empresa
    chave = lambda t: re.sub(r"[^A-Z]", "", sem_acento(t).upper().replace("IEB-", "").replace(" S/A", "").replace(" S.A.", ""))[:22]
    for s, u, em_id, g in pendentes_escritura:
        for r in revisao.get(s["codigo"], []):
            existente = next((n for n in nos if n["tipo"] == "controlador" and chave(n["rotulo"]) == chave(r["parte"])), None)
            p_id = existente["id"] if existente else "c:" + sem_acento(r["parte"]).upper()
            if not existente:
                no(p_id, tipo="controlador" if "acionista" in r["papel"] or "interveniente" in r["papel"] else "garantidor",
                   rotulo=r["parte"].title(), grupo=g, detalhe=f'{r["papel"]} na escritura (a revisar)')
            links.append({"source": p_id, "target": em_id, "tipo": "escritura"})
            if "fiador" in r["papel"] or "garantidor" in r["papel"]:
                links.append({"source": p_id, "target": "s:" + s["codigo"], "tipo": "garante"})

    for n in [n for n in nos if n["tipo"] == "grupo"]:
        for c in [c for c in nos if c["tipo"] == "controlador" and c["grupo"] == n["grupo"]]:
            links.append({"source": n["id"], "target": c["id"], "tipo": "inferido"})
    unicos = {(l["source"], l["target"], l["tipo"]): l for l in links}
    return {"nodes": nos, "links": list(unicos.values())}


JS = r"""
const D = window.DADOS;
const fmt = (v, c=2) => v==null||isNaN(v) ? '–' : Number(v).toLocaleString('pt-BR',{minimumFractionDigits:c,maximumFractionDigits:c});
const sinal = (v, c=0) => v==null||isNaN(v) ? '–' : (v>0?'+':'')+fmt(v,c);
const tip = document.getElementById('tip');
const mostrar = (e, h) => { tip.innerHTML = h; tip.style.display = 'block'; mover(e); };
const mover = e => { const x = Math.min(e.clientX+14, innerWidth-tip.offsetWidth-8); tip.style.left = x+'px'; tip.style.top = (e.clientY+14)+'px'; };
const esconder = () => tip.style.display = 'none';
const linha = (a, b) => '<div class="l"><span>'+a+'</span><span>'+b+'</span></div>';
// desvio em desvios-padrão -> cinco degraus do par divergente (neutro no meio)
const corDesvio = dp => dp==null||isNaN(dp) ? 'var(--surface)' : dp<=-1.5?'var(--div-neg-2)': dp<=-.5?'var(--div-neg-1)': dp<.5?'var(--div-0)': dp<1.5?'var(--div-pos-1)':'var(--div-pos-2)';
const textoSerie = n => '<b>'+n.rotulo+'</b> <span class="fraco">'+(n.classe||'')+'</span><br><span class="fraco">'+n.grupo+'</span>'
  + (n.spread!=null ? linha(n.classe==='DI+'?'Spread sobre CDI':'Spread comparável', fmt(n.spread,0)+' bps') + linha(n.classe==='DI+'?'Mediana DI+':'Spread justo (pares)', fmt(n.justo,0)+' bps') + linha('Desvio', sinal(n.desvio)+' bps ('+sinal(n.dp,1)+' dp)') : '<br>'+n.status);

// ---------- mapa de controle e risco: grupo -> empresas -> emissões ----------
(function(){
  const svg = d3.select('#grafo'); const W = 1120, H = 700;
  svg.attr('viewBox', `0 0 ${W} ${H}`).attr('preserveAspectRatio','xMidYMid meet');
  const g = svg.append('g');
  const zoom = d3.zoom().scaleExtent([.4, 5]).on('zoom', e => g.attr('transform', e.transform));
  svg.call(zoom).on('dblclick.zoom', null);
  const camHull = g.append('g'), camLink = g.append('g'), camNo = g.append('g'), camRot = g.append('g');

  const todos = D.grafo.nodes, porId = new Map(todos.map(n => [n.id, n]));
  const ISOL = 'Isolada (a identificar)';
  const nomeGrupo = x => x===ISOL ? 'Isoladas' : x;
  // emissor de cada série
  const paiSerie = new Map(); D.grafo.links.forEach(l => { if (l.tipo==='emitiu' || l.tipo==='doc') paiSerie.set(l.target, l.source); });
  const filho = n => n.tipo==='serie' || n.tipo==='doc';
  const grupos = [...new Set(todos.map(n => n.grupo))];
  const resumo = Object.fromEntries(grupos.map(x => { const ss = todos.filter(n => n.grupo===x && n.tipo==='serie');
    const ds = ss.map(n=>n.desvio).filter(v=>v!=null).sort((a,b)=>a-b);
    return [x, {series: ss.length, emissores: todos.filter(n=>n.grupo===x && n.tipo==='emissor').length, mediana: ds.length ? ds[Math.floor(ds.length/2)] : null}]; }));
  grupos.sort((a,b) => (a===ISOL) - (b===ISOL) || resumo[b].series - resumo[a].series);
  const ancora = {};
  // grupos abertos dividem o centro; bolas fechadas ficam num anel em volta (anel mais largo quando há algo aberto)
  function posicionarAncoras(){
    const abertos = grupos.filter(x => abertosG.has(x)), fechados = grupos.filter(x => !abertosG.has(x));
    const anel = abertos.length ? fechados : fechados.filter(x => x!==ISOL);
    const rx = abertos.length ? 420 : 320, ry = abertos.length ? 285 : 240;
    anel.forEach((x,i) => { const a = -Math.PI/2 + 2*Math.PI*i/Math.max(anel.length,1); ancora[x] = [W/2+rx*Math.cos(a), H/2+ry*Math.sin(a)]; });
    if (!abertos.length) ancora[ISOL] = [W/2, H/2];
    abertos.forEach((x,i) => { const a = 2*Math.PI*i/abertos.length; const d = abertos.length>1 ? 150 : 0; ancora[x] = [W/2+d*Math.cos(a), H/2+d*.7*Math.sin(a)]; });
  }
  const abertosG = new Set(), abertosE = new Set();
  posicionarAncoras();
  const raioBolha = x => 14 + 5.5*Math.sqrt(resumo[x].series);
  const raio = n => n.tipo==='bolha' ? raioBolha(n.grupo) : ({controlador:6, grupo:7, garantidor:6, emissor:6.5, serie:4.4, doc:5})[n.tipo];
  const corDoc = c => ({oficial:'var(--doc-oficial)', escritura:'var(--doc-oficial)', noticia:'var(--doc-noticia)', analise:'var(--doc-analise)'})[c];
  const formaDoc = c => ({oficial:d3.symbolTriangle, escritura:d3.symbolSquare, noticia:d3.symbolDiamond, analise:d3.symbolStar})[c];
  const nomeDoc = {fato_relevante:'Fato relevante', comunicado:'Comunicado ao mercado', aviso_debenturistas:'Aviso aos debenturistas', escritura:'Escritura', noticia:'Notícia', analise:'Análise'};

  const pos = new Map(); grupos.forEach(x => pos.set('G:'+x, {x: ancora[x][0], y: ancora[x][1]}));

  // representante visível de qualquer nó: bolha do grupo fechado, emissor fechado ou o próprio nó
  const rep = id => { const n = porId.get(id); if (!n) return id;
    if (!abertosG.has(n.grupo)) return 'G:'+n.grupo;
    if (filho(n) && !abertosE.has(paiSerie.get(id))) return paiSerie.get(id);
    return id; };

  function visiveis(){
    const nos = [];
    grupos.forEach(x => { if (!abertosG.has(x)) nos.push({id:'G:'+x, tipo:'bolha', grupo:x, rotulo:nomeGrupo(x)}); });
    todos.forEach(n => { if (!abertosG.has(n.grupo)) return; if (filho(n) && !abertosE.has(paiSerie.get(n.id))) return; nos.push(n); });
    const ids = new Set(nos.map(n=>n.id)), vistos = new Map();
    D.grafo.links.forEach(l => { const s = rep(l.source.id||l.source), t = rep(l.target.id||l.target);
      if (s===t || !ids.has(s) || !ids.has(t)) return;
      const ponte = s.startsWith('G:') && t.startsWith('G:'), k = s<t ? s+'|'+t : t+'|'+s;
      if (!vistos.has(k)) vistos.set(k, {source:s, target:t, tipo: ponte ? 'ponte' : (s.startsWith('G:')||t.startsWith('G:')) ? 'ponte' : l.tipo}); });
    return {nos, links:[...vistos.values()]};
  }

  const sim = d3.forceSimulation().alphaDecay(.03).velocityDecay(.35)
    .force('link', d3.forceLink().id(d=>d.id).distance(l => l.tipo==='ponte'?160 : l.tipo==='emitiu'?30 : l.tipo==='doc'?44 : 46).strength(l => l.tipo==='ponte'?.02 : l.tipo==='emitiu'?.9 : .35))
    .force('charge', d3.forceManyBody().strength(n => n.tipo==='bolha'?-300 : n.tipo==='serie'?-40 : -110).distanceMax(280))
    .force('x', d3.forceX(n => ancora[n.grupo][0]).strength(n => n.tipo==='bolha'?.3:.2))
    .force('y', d3.forceY(n => ancora[n.grupo][1]).strength(n => n.tipo==='bolha'?.3:.2))
    .force('colide', d3.forceCollide().radius(n => raio(n)+(n.tipo==='bolha'?8:2.5)));

  let no = camNo.selectAll('g'), link = camLink.selectAll('line'), rot = camRot.selectAll('text'), hull = camHull.selectAll('path'), hullRot = camHull.selectAll('text');
  let rotulos = 'controle';
  const visRot = n => n.tipo==='bolha' || n.tipo==='serie' ? false : rotulos==='todos' || (rotulos==='controle' && n.tipo!=='emissor') || (n.tipo==='emissor' && abertosE.has(n.id));

  function desenhar(){
    hull.attr('d', x => { const pts = sim.nodes().filter(n=>n.grupo===x && n.tipo!=='bolha').flatMap(n => { const r=raio(n)+12; return [[n.x-r,n.y],[n.x+r,n.y],[n.x,n.y-r],[n.x,n.y+r]]; }); const h = d3.polygonHull(pts); return h ? 'M'+h.join('L')+'Z' : null; });
    hullRot.each(function(x){ const ns = sim.nodes().filter(n=>n.grupo===x && n.tipo!=='bolha'); if (!ns.length) return; d3.select(this).attr('x', d3.mean(ns,n=>n.x)).attr('y', d3.min(ns,n=>n.y)-16); });
    link.attr('x1',l=>l.source.x).attr('y1',l=>l.source.y).attr('x2',l=>l.target.x).attr('y2',l=>l.target.y);
    no.attr('transform', n => `translate(${n.x},${n.y})`);
    rot.attr('x', n => n.x).attr('y', n => n.y);
  }

  function atualizar(origem){
    posicionarAncoras();
    const {nos, links} = visiveis();
    // nós novos nascem na posição de quem foi aberto
    nos.forEach(n => { if (n.x==null || !pos.has(n.id)) { const p = pos.get(origem) || pos.get('G:'+n.grupo) || {x:ancora[n.grupo][0], y:ancora[n.grupo][1]};
      n.x = p.x + (Math.random()-.5)*20; n.y = p.y + (Math.random()-.5)*20; } });
    sim.nodes(nos); sim.force('link').links(links);

    const abertos = [...abertosG];
    hull = camHull.selectAll('path').data(abertos, x=>x).join('path').attr('fill','var(--hull)').attr('stroke','var(--hull-line)').attr('stroke-linejoin','round')
      .attr('stroke-dasharray', x => x===ISOL?'3 3':null).style('cursor','pointer').on('click', (e,x) => { e.stopPropagation(); fecharGrupo(x); });
    hullRot = camHull.selectAll('text').data(abertos, x=>x).join('text').text(x => (x===ISOL?'ISOLADAS · GRUPO A IDENTIFICAR':x.toUpperCase())+'  ×')
      .attr('font-size',10.5).attr('font-weight',700).attr('letter-spacing','.08em').attr('fill','var(--ink-2)').attr('text-anchor','middle').style('cursor','pointer')
      .on('click', (e,x) => { e.stopPropagation(); fecharGrupo(x); });

    link = camLink.selectAll('line').data(links, l => (l.source.id||l.source)+'|'+(l.target.id||l.target)).join('line')
      .attr('stroke', l => l.tipo==='cross'?'var(--div-pos-2)':'var(--edge)')
      .attr('stroke-width', l => l.tipo==='ponte'?2 : l.tipo==='emitiu'?.8 : 1.3)
      .attr('stroke-dasharray', l => l.tipo==='inferido'?'4 3' : l.tipo==='garante'?'1 2.5' : l.tipo==='escritura'?'8 2 2 2' : l.tipo==='ponte'?'2 4' : null);

    no = camNo.selectAll('g.no').data(nos, n=>n.id).join(enter => {
      const ge = enter.append('g').attr('class','no').style('cursor','pointer');
      ge.filter(n=>n.tipo==='bolha').append('circle').attr('r', 0).attr('fill','var(--surface-2)').attr('stroke','var(--line-2)').attr('stroke-width',1.5)
        .transition().duration(350).attr('r', n => raio(n));
      ge.filter(n=>n.tipo==='bolha').append('text').attr('class','rb').attr('text-anchor','middle').attr('dy', n => raio(n)+15).attr('font-size',11).attr('font-weight',600).attr('fill','var(--ink)').text(n=>n.rotulo);
      ge.filter(n=>n.tipo==='bolha').append('text').attr('text-anchor','middle').attr('dy', n => raio(n)+28).attr('font-size',9.5).attr('fill','var(--ink-3)')
        .text(n => resumo[n.grupo].emissores+' emissores · '+resumo[n.grupo].series+' séries');
      ge.filter(n=>n.tipo==='controlador'||n.tipo==='grupo').append('rect').attr('x',n=>-raio(n)).attr('y',n=>-raio(n)).attr('width',n=>2*raio(n)).attr('height',n=>2*raio(n)).attr('rx',2)
        .attr('fill', n => n.tipo==='grupo'?'var(--surface)':'var(--ink-2)').attr('stroke','var(--ink-2)').attr('stroke-width',1.2).attr('stroke-dasharray', n=>n.tipo==='grupo'?'2 2':null);
      ge.filter(n=>n.tipo==='garantidor').append('path').attr('d', d3.symbol(d3.symbolDiamond, 90)()).attr('fill','var(--ink-2)');
      ge.filter(n=>n.tipo==='emissor').append('circle').attr('r',raio).attr('fill','var(--surface)').attr('stroke','var(--ink)').attr('stroke-width',1.5);
      ge.filter(n=>n.tipo==='emissor').append('text').attr('class','mais').attr('text-anchor','middle').attr('dy',3).attr('font-size',8).attr('font-weight',700).attr('fill','var(--ink)').text('+');
      ge.filter(n=>n.tipo==='doc').append('path').attr('d', n => d3.symbol(formaDoc(n.categoria), n.categoria==='analise'?70:58)()).attr('fill', n => corDoc(n.categoria))
        .attr('stroke', n => n.status_jev==='automatico' && n.impacto==='negativo' ? 'var(--div-pos-2)' : n.status_jev==='automatico' && n.impacto==='positivo' ? 'var(--div-neg-2)' : 'var(--surface)')
        .attr('stroke-width', n => n.status_jev==='automatico' && n.impacto!=='neutro' ? 2.2 : 1);
      ge.filter(n=>n.tipo==='serie').append('circle').attr('r',0).attr('fill', n => corDesvio(n.dp)).attr('stroke','var(--surface)').attr('stroke-width',1.2).transition().duration(300).attr('r', raio);
      return ge;
    });
    no.select('text.mais').text(n => abertosE.has(n.id) ? '−' : '+');

    rot = camRot.selectAll('text').data(nos.filter(n => n.tipo!=='bolha' && n.tipo!=='serie' && n.tipo!=='doc'), n=>n.id).join('text')
      .text(n => n.rotulo.length>30 ? n.rotulo.slice(0,29)+'…' : n.rotulo).attr('font-size',8.5).attr('fill','var(--ink-2)')
      .attr('dx', n=>raio(n)+3).attr('dy',3).style('pointer-events','none').attr('paint-order','stroke').attr('stroke','var(--surface)').attr('stroke-width',3);
    aplicarRot();
    ligarEventos();
    sim.alpha(1).restart();
    clearTimeout(enquadrar.t); enquadrar.t = setTimeout(enquadrar, 900);
  }
  // zoom automático: aproxima o que está aberto; tudo recolhido volta à vista inteira
  function enquadrar(){
    const foco = sim.nodes().filter(n => n.tipo!=='bolha');
    if (!foco.length) { svg.transition().duration(600).call(zoom.transform, d3.zoomIdentity); return; }
    const x0 = d3.min(foco,n=>n.x)-60, x1 = d3.max(foco,n=>n.x)+160, y0 = d3.min(foco,n=>n.y)-50, y1 = d3.max(foco,n=>n.y)+40;
    const k = Math.max(1, Math.min(2.2, .9*Math.min(W/(x1-x0), H/(y1-y0))));
    svg.transition().duration(700).call(zoom.transform, d3.zoomIdentity.translate(W/2 - k*(x0+x1)/2, H/2 - k*(y0+y1)/2).scale(k));
  }
  const aplicarRot = () => rot.attr('display', n => visRot(n)?null:'none');
  sim.on('tick', () => { sim.nodes().forEach(n => pos.set(n.id, {x:n.x, y:n.y})); desenhar(); });

  function abrirGrupo(x){ abertosG.add(x); atualizar('G:'+x); }
  function fecharGrupo(x){ abertosG.delete(x); todos.filter(n=>n.grupo===x && n.tipo==='emissor').forEach(n=>abertosE.delete(n.id)); pos.set('G:'+x, centro(x)); atualizar(); }
  const centro = x => { const ns = sim.nodes().filter(n=>n.grupo===x); return ns.length ? {x:d3.mean(ns,n=>n.x), y:d3.mean(ns,n=>n.y)} : {x:ancora[x][0], y:ancora[x][1]}; };
  function alternarEmissor(id){ abertosE.has(id) ? abertosE.delete(id) : abertosE.add(id); atualizar(id); }

  const viz = () => { const m = new Map(); sim.force('link').links().forEach(l => [[l.source.id,l.target.id],[l.target.id,l.source.id]].forEach(([a,b]) => { if(!m.has(a)) m.set(a,new Set()); m.get(a).add(b); })); return m; };
  function realcar(ids){ no.attr('opacity', n => !ids||ids.has(n.id)?1:.15); rot.attr('opacity', n => !ids||ids.has(n.id)?1:.15); link.attr('opacity', l => !ids||(ids.has(l.source.id)&&ids.has(l.target.id))?1:.08); }
  function ligarEventos(){
    no.on('mouseenter', (e,n) => { const v = viz(); realcar(new Set([n.id, ...(v.get(n.id)||[])]));
        if (n.tipo==='bolha') { const r = resumo[n.grupo]; mostrar(e, '<b>'+nomeGrupo(n.grupo)+'</b>'+linha('Emissores', r.emissores)+linha('Séries', r.series)+linha('Desvio mediano', r.mediana==null?'–':sinal(r.mediana)+' bps')+'<span class="fraco">clique para abrir</span>'); }
        else if (n.tipo==='serie') mostrar(e, textoSerie(n));
        else if (n.tipo==='doc') mostrar(e, '<b>'+nomeDoc[n.subtipo]+'</b> <span class="fraco">'+(n.data||'')+' · '+n.fonte+'</span><br>'+n.rotulo
          + (n.evento ? linha('Evento (JEV)', n.evento.replace(/_/g,' ')) + linha('Impacto para o credor', n.impacto) + linha('Confiança', fmt(n.confianca,2) + (n.status_jev==='a_revisar'?' · a revisar':'')) : '')
          + '<br><span class="fraco">clique para abrir o original</span>');
        else mostrar(e, '<b>'+n.rotulo+'</b><br><span class="fraco">'+nomeGrupo(n.grupo)+'</span><br>'+(n.detalhe||'')+(n.tipo==='emissor'?'<br><span class="fraco">clique para '+(abertosE.has(n.id)?'recolher':'ver as emissões')+'</span>':'')); })
      .on('mousemove', mover).on('mouseleave', () => { realcar(null); esconder(); })
      .on('click', (e,n) => { e.stopPropagation(); esconder();
        if (n.tipo==='bolha') abrirGrupo(n.grupo);
        else if (n.tipo==='emissor') { alternarEmissor(n.id); mostrarFicha(n); }
        else if (n.tipo==='doc') { if (n.url) window.open(n.url, '_blank', 'noopener'); }
        else if (n.tipo==='serie') { selecionar(n.rotulo); document.getElementById('simulador').scrollIntoView({behavior:'smooth'}); } })
      .call(d3.drag().on('start',(e,d)=>{if(!e.active)sim.alphaTarget(.2).restart();d.fx=d.x;d.fy=d.y}).on('drag',(e,d)=>{d.fx=e.x;d.fy=e.y}).on('end',(e,d)=>{if(!e.active)sim.alphaTarget(0);d.fx=null;d.fy=null}));
  }

  // controles
  const selG = document.getElementById('filtroGrupo');
  ['Todos os grupos', ...grupos].forEach(x => { const o=document.createElement('option'); o.value=x; o.textContent=nomeGrupo(x); selG.appendChild(o); });
  selG.addEventListener('change', () => { const x = selG.value; if (x==='Todos os grupos') { realcar(null); return; } if (!abertosG.has(x)) abrirGrupo(x); setTimeout(() => realcar(new Set(sim.nodes().filter(n=>n.grupo===x).map(n=>n.id))), 400); });
  document.querySelectorAll('[data-rot]').forEach(b => b.addEventListener('click', () => { rotulos = b.dataset.rot; document.querySelectorAll('[data-rot]').forEach(x=>x.classList.toggle('ativo', x===b)); aplicarRot(); }));
  document.getElementById('abrirTudo').addEventListener('click', () => { grupos.forEach(x => abertosG.add(x)); atualizar(); });
  document.getElementById('abrirEmissoes').addEventListener('click', () => { grupos.forEach(x => abertosG.add(x)); todos.filter(n=>n.tipo==='emissor').forEach(n=>abertosE.add(n.id)); atualizar(); });
  document.getElementById('fecharTudo').addEventListener('click', () => { abertosG.clear(); abertosE.clear(); grupos.forEach(x => pos.set('G:'+x, {x:ancora[x][0], y:ancora[x][1]})); atualizar(); svg.transition().duration(400).call(zoom.transform, d3.zoomIdentity); });

  // ficha do emissor: tudo que o sistema sabe dele, com link para a fonte original
  function mostrarFicha(n){
    const f = document.getElementById('ficha'), docs = (D.docs[n.cnpj] || []);
    const series = todos.filter(m => m.tipo==='serie' && paiSerie.get(m.id)===n.id);
    const esc = t => String(t||'').replace(/&/g,'&amp;').replace(/</g,'&lt;');
    const bloco = (titulo, itens) => itens.length ? '<div><h4>'+titulo+'</h4><ul>'+itens.join('')+'</ul></div>' : '';
    const selo = j => !j ? '' : ' <span class="selo" title="classificação JEV, confiança '+j.confianca+'">'+(j.impacto==='negativo'?'▼ ':j.impacto==='positivo'?'▲ ':'')+j.evento.replace(/_/g,' ')+(j.status==='a_revisar'?' · a revisar':'')+'</span>';
    const item = d => '<li><span>'+(d.data||'')+'</span><a href="'+esc(d.url)+'" target="_blank" rel="noopener">'+esc(d.titulo)+'</a> <span class="fraco">'+esc(d.fonte)+'</span>'+selo(d.jev)+'</li>';
    const lista = t => docs.filter(d => t.includes(d.tipo)).map(item);
    f.innerHTML = '<div class="kicker">'+esc(nomeGrupo(n.grupo))+' · CNPJ '+n.cnpj+'</div><h3>'+esc(n.rotulo)+'</h3><p class="muted pequeno" style="margin:0">'+esc(n.detalhe)+'</p>'
      + '<div class="ficha-grade">'
      + bloco('Emissões', series.map(m => '<li><span>'+m.rotulo+'</span>'+(m.spread!=null ? fmt(m.spread,0)+' bps · desvio '+sinal(m.desvio)+' bps' : esc(m.status))+'</li>'))
      + bloco('Fatos relevantes', lista(['fato_relevante'])) + bloco('Comunicados e avisos', lista(['comunicado','aviso_debenturistas']))
      + bloco('Escrituras', lista(['escritura'])) + bloco('Notícias', lista(['noticia'])) + bloco('Análises', lista(['analise']))
      + '</div>' + (docs.length ? '' : '<p class="fraco pequeno">Sem documentos públicos indexados ainda para este emissor.</p>');
    f.style.display = 'block';
  }

  atualizar();
})();

// ---------- desvio em relação aos pares (barras divergentes) ----------
function desenharDesvio(classe){
  const dados = D.desvios.filter(d => d.classe===classe && d.desvio!=null).sort((a,b)=>b.desvio-a.desvio);
  const svg = d3.select('#desvio'); svg.selectAll('*').remove();
  const W = 1080, lin = 15, M = {t:24, r:70, b:8, l:150}, H = M.t + dados.length*lin + M.b;
  svg.attr('viewBox', `0 0 ${W} ${H}`);
  const lim = Math.max(30, d3.max(dados, d => Math.abs(d.desvio)));
  const x = d3.scaleLinear().domain([-lim, lim]).range([M.l, W-M.r]).nice();
  x.ticks(6).forEach(t => { svg.append('line').attr('x1',x(t)).attr('x2',x(t)).attr('y1',M.t-6).attr('y2',H-M.b).attr('stroke','var(--line)').attr('stroke-width', t===0?1.2:1);
    svg.append('text').attr('x',x(t)).attr('y',M.t-10).attr('text-anchor','middle').attr('font-size',10).attr('fill','var(--ink-3)').text(sinal(t)); });
  const gr = svg.append('g').selectAll('g').data(dados).join('g').attr('transform',(d,i)=>`translate(0,${M.t+i*lin})`);
  gr.append('rect').attr('x', d => Math.min(x(0), x(d.desvio))).attr('y', 2).attr('height', lin-4).attr('width', d => Math.max(1, Math.abs(x(d.desvio)-x(0)))).attr('rx', 2).attr('fill', d => corDesvio(d.dp));
  gr.append('text').attr('x', M.l-8).attr('y', lin/2+3.5).attr('text-anchor','end').attr('font-size',10.5).attr('fill','var(--ink)').text(d => d.codigo);
  gr.append('text').attr('x', M.l-62).attr('y', lin/2+3.5).attr('text-anchor','end').attr('font-size',9.5).attr('fill','var(--ink-3)').text(d => d.grupo.startsWith('Isolada')?'isolada':d.grupo.split(' ')[0]);
  gr.append('text').attr('x', d => d.desvio>=0 ? x(d.desvio)+5 : x(d.desvio)-5).attr('y', lin/2+3.5).attr('text-anchor', d=>d.desvio>=0?'start':'end').attr('font-size',9.5).attr('fill','var(--ink-2)').text(d => sinal(d.desvio));
  gr.append('rect').attr('x',0).attr('width',W).attr('height',lin).attr('fill','transparent').style('cursor','pointer')
    .on('mouseenter', (e,d) => mostrar(e, '<b>'+d.codigo+'</b> · '+d.emissor+'<br><span class="fraco">'+d.grupo+'</span>' + linha(classe==='DI+'?'Spread sobre CDI':'Spread comparável', fmt(d.spread,0)+' bps') + linha(classe==='DI+'?'Mediana DI+':'Spread justo', fmt(d.justo,0)+' bps') + linha('Desvio', sinal(d.desvio)+' bps ('+sinal(d.dp,1)+' dp)') + linha('Variação no histórico', d.var_hist==null?'–':sinal(d.var_hist)+' bps ('+d.n_hist+' dias)')))
    .on('mousemove', mover).on('mouseleave', esconder).on('click', (e,d) => { if (D.fluxos[d.codigo]||D.di[d.codigo]) { selecionar(d.codigo); document.getElementById('simulador').scrollIntoView({behavior:'smooth'}); } });
}
document.querySelectorAll('[data-classe]').forEach(b => b.addEventListener('click', () => { document.querySelectorAll('[data-classe]').forEach(x=>x.classList.toggle('ativo', x===b)); desenharDesvio(b.dataset.classe); }));
desenharDesvio('IPCA+');

// ---------- simulador ----------
const sel = document.getElementById('serie'), choque = document.getElementById('choque');
D.series.forEach(s => { const o=document.createElement('option'); o.value=s.codigo; o.textContent=s.codigo+' · '+s.emissor+(s.classe==='DI+'?' (DI+)':''); sel.appendChild(o); });
const preco = (f, y) => f.t.reduce((p,t,i) => p + f.cf[i]/Math.pow(1+y, t), 0);
function calcular(){
  const s = D.series.find(x => x.codigo===sel.value); if(!s) return;
  const f = D.fluxos[s.codigo], ds = (parseFloat(choque.value)||0)/1e4;
  const aprox = (-s.dmod*ds + (s.convex? .5*s.convex*ds*ds : 0))*100;
  const cheio = f ? (preco(f, f.y+ds)/preco(f, f.y)-1)*100 : null;
  const v = cheio!=null ? cheio : aprox;
  document.getElementById('r_pu').textContent = s.pu ? 'R$ '+fmt(s.pu,2) : '–';
  document.getElementById('r_pu_novo').textContent = s.pu ? 'R$ '+fmt(s.pu*(1+v/100),2) : '–';
  document.getElementById('r_var').textContent = cheio!=null ? fmt(cheio,2)+'%' : 'n/d (DI+)';
  document.getElementById('r_aprox').textContent = fmt(aprox,2)+'%';
  document.getElementById('r_dur').textContent = fmt(s.dmod,2)+' anos';
  document.getElementById('r_z').textContent = fmt(s.spread,0)+' bps' + (s.classe==='DI+'?' sobre CDI':'');
  document.getElementById('r_desvio').textContent = s.desvio==null?'–':sinal(s.desvio)+' bps ('+sinal(s.dp,1)+' dp)';
  document.getElementById('r_be12').textContent = s.be12==null?'–':fmt(s.be12,1)+' bps';
}
// régua e curva preço x choque: os três controles (régua, ponto arrastável, campo) ficam sincronizados
const regua = document.getElementById('regua'), reguaValor = document.getElementById('regua_valor');
const variacao = (s, bps) => { const f = D.fluxos[s.codigo], ds = bps/1e4;
  return f ? (preco(f, f.y+ds)/preco(f, f.y)-1)*100 : (-s.dmod*ds)*100; };
function definir(bps, origem){
  bps = Math.max(-300, Math.min(300, Math.round(bps/5)*5));
  if (origem!=='campo') choque.value = bps; if (origem!=='regua') regua.value = bps;
  reguaValor.textContent = (bps>0?'+':'')+bps+' bps'; calcular(); desenharCurva();
}
function desenharCurva(){
  const s = D.series.find(x => x.codigo===sel.value); if(!s) return;
  const svg = d3.select('#curva'); svg.selectAll('*').remove();
  const W = 440, H = 200, M = {t:12, r:12, b:22, l:40}; svg.attr('viewBox', `0 0 ${W} ${H}`);
  const pts = d3.range(-300, 301, 10).map(b => [b, variacao(s, b)]);
  const x = d3.scaleLinear().domain([-300, 300]).range([M.l, W-M.r]);
  const y = d3.scaleLinear().domain(d3.extent(pts, p=>p[1])).nice().range([H-M.b, M.t]);
  y.ticks(4).forEach(t => { svg.append('line').attr('x1',M.l).attr('x2',W-M.r).attr('y1',y(t)).attr('y2',y(t)).attr('stroke','var(--line)');
    svg.append('text').attr('x',M.l-6).attr('y',y(t)+3).attr('text-anchor','end').attr('font-size',9.5).attr('fill','var(--ink-3)').text(fmt(t,0)+'%'); });
  [-300,-150,0,150,300].forEach(t => svg.append('text').attr('x',x(t)).attr('y',H-6).attr('text-anchor','middle').attr('font-size',9.5).attr('fill','var(--ink-3)').text((t>0?'+':'')+t));
  svg.append('line').attr('x1',x(0)).attr('x2',x(0)).attr('y1',M.t).attr('y2',H-M.b).attr('stroke','var(--line-2)');
  svg.append('path').attr('d', d3.line().x(p=>x(p[0])).y(p=>y(p[1]))(pts)).attr('fill','none').attr('stroke','var(--ink)').attr('stroke-width',2);
  const b = +choque.value || 0, v = variacao(s, b);
  svg.append('line').attr('x1',x(b)).attr('x2',x(b)).attr('y1',y(v)).attr('y2',H-M.b).attr('stroke','var(--ink-3)').attr('stroke-dasharray','3 3');
  svg.append('circle').attr('cx',x(b)).attr('cy',y(v)).attr('r',7).attr('fill', b<0?'var(--div-neg-2)':b>0?'var(--div-pos-2)':'var(--div-0)').attr('stroke','var(--surface)').attr('stroke-width',2);
  svg.append('text').attr('x', x(b) + (b>150?-10:10)).attr('y', y(v)-10).attr('text-anchor', b>150?'end':'start').attr('font-size',11).attr('font-weight',600).attr('fill','var(--ink)').text(fmt(v,2)+'%');
  // arrastar em qualquer ponto do gráfico move o choque
  svg.append('rect').attr('x',M.l).attr('y',0).attr('width',W-M.l-M.r).attr('height',H).attr('fill','transparent').style('cursor','ew-resize')
    .call(d3.drag().on('start drag', e => definir(x.invert(e.x), 'curva')))
    .on('click', e => definir(x.invert(d3.pointer(e)[0]), 'curva'));
}
function selecionar(c){ sel.value=c; calcular(); desenharCurva(); }
sel.addEventListener('change', () => { calcular(); desenharCurva(); });
regua.addEventListener('input', () => definir(+regua.value, 'regua'));
choque.addEventListener('input', () => definir(+choque.value || 0, 'campo'));
document.querySelectorAll('.botoes button').forEach(b => b.addEventListener('click', () => definir(+b.dataset.v, 'botao')));
if (sel.options.length) { sel.value = sel.options[0].value; definir(100, 'inicio'); }

// ---------- tabela: ordenar e abrir no simulador ----------
document.querySelectorAll('tbody tr[data-codigo]').forEach(tr => tr.addEventListener('click', () => { selecionar(tr.dataset.codigo); document.getElementById('simulador').scrollIntoView({behavior:'smooth'}); }));
document.querySelectorAll('#tab th').forEach((th, i) => th.addEventListener('click', () => {
  const corpo = document.querySelector('#tab tbody'), linhas = [...corpo.rows], asc = th.dataset.asc !== '1'; th.dataset.asc = asc?'1':'0';
  const val = r => { const t = r.cells[i].dataset.v ?? r.cells[i].textContent; const n = parseFloat(t); return isNaN(n) ? t : n; };
  linhas.sort((a,b) => { const x=val(a), y=val(b); return (x>y?1:x<y?-1:0)*(asc?1:-1); }).forEach(r => corpo.appendChild(r));
}));
"""


def gerar_projeto() -> str:
    arq = sorted(PREC.glob("????-??-??.csv"))[-1]
    data_ref = arq.stem
    series = ler_csv(arq)
    fluxos = json.loads((PREC / f"{data_ref}_fluxos.json").read_text(encoding="utf-8"))
    universo = {u["codigo"]: u for u in ler_csv(UNIVERSO)}
    justos = {j["codigo"]: j for j in ler_csv(JUSTO / f"{data_ref}.csv")}
    modelo = json.loads((JUSTO / f"{data_ref}_modelo.json").read_text(encoding="utf-8")) if (JUSTO / f"{data_ref}_modelo.json").exists() else None
    clausulas = {c["codigo"]: c for c in ler_csv(CLAUSULAS)}

    f = lambda v: float(v) if v not in ("", None) else None
    desvios = {}
    for s in series:
        j = justos.get(s["codigo"])
        if j:
            desvios[s["codigo"]] = {"classe": j["classe"], "spread": f(j["spread_bps"]), "justo": f(j["spread_justo_bps"]),
                                    "desvio": f(j["desvio_bps"]), "dp": f(j["desvio_em_dp"]), "var_hist": f(j["variacao_hist_bps"]),
                                    "n_hist": int(j["n_dias_hist"] or 0)}
    arq_docs = RAIZ / "dados" / "derivados" / "documentos.json"
    documentos = json.loads(arq_docs.read_text(encoding="utf-8"))["emissores"] if arq_docs.exists() else {}
    arq_jev = RAIZ / "dados" / "derivados" / "jev" / "classificacao.json"
    jev = json.loads(arq_jev.read_text(encoding="utf-8")) if arq_jev.exists() else {}
    # a ficha também mostra a classificação: anexa ao próprio documento
    for cnpj, ls in documentos.items():
        for d in ls:
            cl = jev.get(f"{cnpj}|{d['tipo']}|{d.get('data', '')}|{d['titulo'][:60]}")
            if cl and cl.get("evento"):
                d["jev"] = {"evento": cl["evento"], "impacto": cl["impacto"], "confianca": round(cl["evento_confianca"], 2), "status": cl["status"]}
    grafo = montar_grafo(series, universo, desvios, clausulas, documentos, jev)

    validas = [s for s in series if s["status"] in ("ok", "ok DI+")]
    dados_series, di = [], {}
    for s in validas:
        d = desvios.get(s["codigo"], {})
        dados_series.append({
            "codigo": s["codigo"], "emissor": s["emissor_atual"].title(), "classe": d.get("classe"),
            "pu": f(s["pu_anbima"]), "dmod": f(s["duration_mod_anos"]), "convex": f(s.get("convexidade")),
            "spread": d.get("spread"), "desvio": d.get("desvio"), "dp": d.get("dp"), "be12": f(s.get("breakeven_12m_bps")),
        })
        if s["status"] == "ok DI+":
            di[s["codigo"]] = True
    lista_desvios = [{"codigo": c, "emissor": universo[c]["emissor_atual_snd"].title(), "grupo": universo[c]["grupo_risco"], **v}
                     for c, v in desvios.items()]

    ipca = [d for d in desvios.values() if d["classe"] == "IPCA+"]
    n_emissores = len({universo[s["codigo"]]["cnpj"] for s in series})
    n_cvm = len({universo[s["codigo"]]["cnpj"] for s in series if universo[s["codigo"]]["fonte_grupo"] == "CVM FRE"})
    n_grupos = len({universo[s["codigo"]]["grupo_risco"] for s in series} - {"Isolada (a identificar)"})
    mediana = statistics.median(d["spread"] for d in ipca) if ipca else None
    fora = sum(1 for d in ipca if d["dp"] is not None and abs(d["dp"]) >= 1.5)

    trs = []
    ordem = sorted(series, key=lambda s: (desvios.get(s["codigo"], {}).get("desvio") is None, -(desvios.get(s["codigo"], {}).get("desvio") or 0)))
    for s in ordem:
        u, d = universo[s["codigo"]], desvios.get(s["codigo"], {})
        valida = s["status"] in ("ok", "ok DI+")
        cl = clausulas.get(s["codigo"], {})
        fonte = {"CVM FRE": "CVM", "inferido": "inferido", "escritura": "escritura"}.get(u["fonte_grupo"], "")
        dp = d.get("dp")
        cor = "var(--surface)" if dp is None else "var(--div-neg-2)" if dp <= -1.5 else "var(--div-neg-1)" if dp <= -.5 else "var(--div-0)" if dp < .5 else "var(--div-pos-1)" if dp < 1.5 else "var(--div-pos-2)"
        abre = f'<tr data-codigo="{html.escape(s["codigo"])}">' if valida else "<tr>"
        celula = lambda v, c=0, sinal=False: f'<td data-v="{"" if v is None else v}">{("+" if sinal and v is not None and v > 0 else "") + num(v, c)}</td>'
        trs.append(
            abre
            + f'<td class="t"><span class="marca" style="background:{cor}"></span>{html.escape(s["codigo"])}</td>'
            + f'<td class="t">{html.escape(u["emissor_atual_snd"].title())}</td>'
            + f'<td class="t">{html.escape(u["grupo_risco"])} <span class="selo">{fonte}</span></td>' if fonte else
            abre
            + f'<td class="t"><span class="marca" style="background:{cor}"></span>{html.escape(s["codigo"])}</td>'
            + f'<td class="t">{html.escape(u["emissor_atual_snd"].title())}</td>'
            + f'<td class="t">{html.escape(u["grupo_risco"])}</td>'
        )
        trs[-1] += (
            f'<td class="t">{d.get("classe") or s["indexador_tipo"]}</td>'
            f'<td class="t">{ {"S": "sim", "N": "não"}.get(s["incentivada"], "–") }</td>'
            f'<td class="t">{html.escape(s["garantia"] or "–")}</td>'
            + celula(d.get("spread"))
            + celula(d.get("justo"))
            + celula(d.get("desvio"), 0, True)
            + celula(dp, 1, True)
            + celula(d.get("var_hist"), 0, True)
            + celula(f(s.get("duration_mod_anos")), 2)
            + celula(f(s.get("choque_100_pct")), 2)
            + f'<td class="t pequeno fraco">{html.escape(cl.get("resumo", "")) if cl else ""}{"" if valida else html.escape(s["status"])}</td>'
            + "</tr>"
        )

    coef_html = ""
    if modelo:
        linhas = "".join(
            f'<tr><td>{html.escape(c["descricao"])}</td><td>{num(c["coef"], 2)}</td><td>{num(c["erro_padrao_hc1"], 2)}</td>'
            f'<td>{num(c["coef"] / c["erro_padrao_hc1"], 2) if c["erro_padrao_hc1"] else "–"}</td><td>{num(c["vif"], 2) if c["vif"] else "–"}</td></tr>'
            for c in modelo["coeficientes"]
        )
        coef_html = f"""<div class="painel tabela" style="max-height:none"><table class="coef">
<thead><tr><th class="t">Variável</th><th>Coeficiente (bps)</th><th>Erro padrão (HC1)</th><th>t</th><th>VIF</th></tr></thead>
<tbody>{linhas}</tbody></table></div>
<p class="fraco pequeno">IPCA+: n = {modelo["n"]}, R² = {num(modelo["r2"], 2)}, desvio padrão dos resíduos = {num(modelo["dp_residuos_bps"], 0)} bps. DI+: desvio medido contra a mediana das {modelo["di"]["n"]} séries ({num(modelo["di"]["mediana_bps"], 0)} bps). Especificação provisória.</p>"""

    dia = date.fromisoformat(data_ref).strftime("%d/%m/%Y")
    dados_js = json.dumps({"grafo": grafo, "series": dados_series, "fluxos": fluxos, "di": di, "desvios": lista_desvios, "docs": documentos},
                          ensure_ascii=False, separators=(",", ":"))
    escala = '<span class="escala">abaixo dos pares <b><i style="background:var(--div-neg-2)"></i><i style="background:var(--div-neg-1)"></i><i style="background:var(--div-0)"></i><i style="background:var(--div-pos-1)"></i><i style="background:var(--div-pos-2)"></i></b> acima dos pares</span>'

    corpo = f"""<main>
<nav><a href="/">Alisson Prata Oliveira</a><span><a href="#mapa">Mapa</a><a href="#desvios">Desvios</a><a href="#simulador">Simulador</a><a href="#tabela">Tabela</a><a href="https://github.com/alissondpoliveira/grafo-credito">Código e dados</a></span></nav>

<div class="kicker">Crédito privado · Transmissão de energia · {dia}</div>
<h1>Grafo de Crédito</h1>
<p class="dek">Quem controla quem, quem emitiu o quê e quanto cada debênture paga acima ou abaixo do que seus pares sugerem. Piloto com as transmissoras de energia elétrica, atualizado todo dia útil com dados da ANBIMA, do SND e da CVM.</p>

<div class="tiles">
<div class="tile"><span>Séries no piloto</span><b>{len(series)}</b><small>{len(validas)} precificadas</small></div>
<div class="tile"><span>Emissores</span><b>{n_emissores}</b><small>{n_cvm} com controle na CVM</small></div>
<div class="tile"><span>Grupos de risco</span><b>{n_grupos}</b><small>mais as isoladas</small></div>
<div class="tile"><span>Spread comparável mediano</span><b>{num(mediana, 0)} bps</b><small>IPCA+, gross-up 15% nas isentas</small></div>
<div class="tile"><span>Fora da faixa dos pares</span><b>{fora}</b><small>séries com |desvio| ≥ 1,5 dp</small></div>
</div>

<section id="mapa">
<div class="cab"><div><h2>Mapa de controle e risco</h2><p class="muted pequeno">Cada bola é um grupo de risco, do tamanho do número de séries. Clique numa bola para abrir as empresas do grupo; clique num emissor para abrir as emissões (coloridas pelo desvio em relação aos pares) e os documentos dele (fatos relevantes, escrituras, notícias e análises), com a ficha completa abaixo do mapa. Clique num documento para abrir o original e no nome do grupo para recolher. Linhas pontilhadas entre bolas são empresas compartilhadas entre grupos.</p></div></div>
<div class="painel">
<div class="controles"><label>Abrir grupo <select id="filtroGrupo"></select></label>
<button id="abrirTudo">abrir todos os grupos</button><button id="abrirEmissoes">abrir tudo até as emissões</button><button id="fecharTudo">recolher</button>
<label style="margin-left:auto">Rótulos <button data-rot="controle" class="ativo">controladores</button><button data-rot="todos">todos</button><button data-rot="nenhum">nenhum</button></label></div>
<svg id="grafo" role="img" aria-label="Grafo de controladores, emissores e séries de debêntures agrupados por grupo de risco"></svg>
<div class="legenda"><span><i style="background:var(--doc-oficial);border-radius:0;clip-path:polygon(50% 0,100% 100%,0 100%)"></i>fato relevante, comunicado, aviso (CVM)</span><span><i style="background:var(--doc-oficial);border-radius:1px"></i>escritura</span><span><i style="background:var(--doc-noticia);transform:rotate(45deg);border-radius:1px"></i>notícia</span><span><i style="background:var(--surface);border:2px solid var(--div-pos-2)"></i>impacto negativo (JEV)</span><span><i style="background:var(--surface);border:2px solid var(--div-neg-2)"></i>impacto positivo (JEV)</span><span><i style="background:var(--doc-analise);clip-path:polygon(50% 0,61% 35%,98% 35%,68% 57%,79% 91%,50% 70%,21% 91%,32% 57%,2% 35%,39% 35%)"></i>análise (casas de research)</span></div>
<div class="legenda" style="border-top:0;padding-top:0">{escala}<span>■ controlador (CVM)</span><span>⬚ grupo inferido</span><span>○ emissor</span><span>· · ponte entre grupos</span><span>── controle declarado (CVM)</span><span>—·— parte citada na escritura</span><span>- - grupo inferido</span><span>··· fiança (escritura)</span><span style="color:var(--div-pos-2)">— — cross-default alcança a controladora (escritura)</span></div>
</div>
<div id="ficha" class="painel"></div>
</section>

<section id="desvios">
<div class="cab"><div><h2>Desvio em relação aos pares</h2><p class="muted pequeno">Spread observado menos spread justo estimado pelos pares, em bps. À direita, a série paga mais que o perfil dela sugere; à esquerda, menos. A cor marca o tamanho do desvio em desvios-padrão dos resíduos.</p></div>
<div><button data-classe="IPCA+" class="ativo">IPCA+</button> <button data-classe="DI+">DI+</button></div></div>
<div class="painel" style="padding:8px 4px"><svg id="desvio" role="img" aria-label="Barras divergentes do desvio de spread de cada série"></svg></div>
</section>

<section id="simulador">
<div class="cab"><div><h2>Simulador de abertura e fechamento de spread</h2><p class="muted pequeno">IPCA+: reprecificação completa do fluxo remanescente (agenda SND) pela taxa indicativa mais o choque. DI+: aproximação pela duration.</p></div></div>
<div class="painel sim">
<div>
<label for="serie">Série</label><select id="serie"></select>
<label for="regua">Choque no spread: <b id="regua_valor" class="serif" style="font-size:1.05rem">+100 bps</b></label>
<input id="regua" type="range" min="-300" max="300" step="5" value="100" aria-label="Choque no spread em bps">
<div class="regua-marcas"><span>−300</span><span>−150</span><span>0</span><span>+150</span><span>+300</span></div>
<svg id="curva" role="img" aria-label="Variação do PU em função do choque de spread; arraste o ponto para ajustar"></svg>
<label for="choque">Valor exato (bps)</label><input id="choque" type="number" step="5" value="100">
<div class="botoes"><button data-v="-100">−100</button><button data-v="-50">−50</button><button data-v="50">+50</button><button data-v="100">+100</button><button data-v="200">+200</button></div>
</div>
<div><div class="res">
<div><small>PU ANBIMA</small><b id="r_pu">–</b></div>
<div><small>PU após o choque</small><b id="r_pu_novo">–</b></div>
<div><small>Variação, reprecificação completa</small><b id="r_var">–</b></div>
<div><small>Variação, duration + convexidade</small><b id="r_aprox">–</b></div>
<div><small>Duration modificada</small><b id="r_dur">–</b></div>
<div><small>Spread (comparável ou sobre CDI)</small><b id="r_z">–</b></div>
<div><small>Desvio em relação aos pares</small><b id="r_desvio">–</b></div>
<div><small>Break-even de abertura em 12 meses</small><b id="r_be12">–</b></div>
</div></div>
</div>
</section>

<section id="tabela">
<div class="cab"><div><h2>Tabela</h2><p class="muted pequeno">Clique no cabeçalho para ordenar; clique numa linha para simular.</p></div></div>
<div class="painel tabela"><table id="tab">
<thead><tr><th class="t">Série</th><th class="t">Emissor atual (SND)</th><th class="t">Grupo de risco</th><th class="t">Classe</th><th class="t">Isenta</th><th class="t">Garantia</th><th>Spread (bps)</th><th>Justo (bps)</th><th>Desvio (bps)</th><th>Desvio (dp)</th><th>Variação hist. (bps)</th><th>Duration</th><th>Choque +100 (%)</th><th class="t">Escritura / status</th></tr></thead>
<tbody>
{chr(10).join(trs)}
</tbody></table></div>
</section>

<section>
<div class="cab"><div><h2>Modelo de spread justo</h2><p class="muted pequeno">Regressão cross-section do spread comparável das séries IPCA+ validadas, com erros padrão robustos. O spread justo de cada série é o valor ajustado; o desvio é o resíduo.</p></div></div>
{coef_html}
</section>

<section>
<h2>Método e limites</h2>
<ul class="metodo pequeno">
<li><b>Fluxo de pagamentos</b> da agenda de eventos do SND; validação contra a duration ANBIMA. Séries que não batem ficam fora e aparecem marcadas.</li>
<li><b>Spread comparável</b>: Z-spread sobre a curva zero-cupom real (ETTJ IPCA, ANBIMA), com gross-up de 15% na taxa nominal das debêntures incentivadas (isentas para pessoa física), usando a inflação implícita na duration de cada série.</li>
<li><b>Spread justo</b>: modelo provisório com duration, garantia real, controle declarado na CVM, tamanho da emissão e dispersão das contribuições ANBIMA. Desvio não é recomendação: parte dele é prêmio de liquidez que o modelo não mede.</li>
<li><b>DI+</b>: a taxa indicativa ANBIMA já é o spread sobre o CDI; desvio contra a mediana das DI+ do piloto (amostra pequena).</li>
<li><b>Variação histórica</b>: diferença entre o spread de hoje e o do primeiro dia do histórico coletado (desde 24/09/2026). Ganha significado com o tempo.</li>
<li><b>Grupo de risco</b>: "CVM" = controlador pessoa jurídica declarado no Formulário de Referência; "escritura" = acionista, fiadora ou interveniente citada no preâmbulo da escritura (lida e a revisar); "inferido" = regra explícita, a confirmar. Emissor identificado pelo CNPJ do SND.</li>
<li><b>Documentos</b>: só título, data, fonte e link, de fontes públicas (CVM IPE, agentes fiduciários, Google Notícias e páginas públicas de casas de análise). O conteúdo fica na fonte original. Análises filtradas por termos de crédito (debênture, rating, dívida, resultado).</li>
<li><b>Classificação de eventos (JEV)</b>: o modelo System One da TypeSafe lê o título de cada fato relevante, comunicado, aviso, notícia e análise e devolve tipo de evento, impacto para o credor e relevância, com confiança. Validação em 50 documentos (02/10/2026): 89% de acerto no tipo de evento quando a confiança é ≥ 0,8 e 36% abaixo disso; só o primeiro grupo é exibido como classificação, o resto aparece "a revisar". Títulos sem conteúdo não são enviados. O critério de impacto segue o do JEV (pagamento em dia, captação e leilão vencido tendem a positivo) e está em calibração.</li>
<li><b>Cláusulas</b> (coluna "Escritura"): presença de fiança, cessão fiduciária, cross-default e covenant de dívida líquida/EBITDA, localizada por regras de texto nas escrituras públicas (Pentágono e CVM IPE). Evidência a revisar, não leitura jurídica.</li>
</ul>
</section>

<footer>Fontes: ANBIMA (taxas de debêntures e títulos públicos, ETTJ), SND/debentures.com.br (características e agenda), CVM (Formulário de Referência e IPE), agentes fiduciários (escrituras). Data de referência {dia}. A taxa indicativa é referência de preço justo, não necessariamente negócio fechado. Conteúdo de pesquisa e educacional. Não constitui recomendação de investimento.</footer>
</main>
<div id="tip" class="tip"></div>
<script>window.DADOS = {dados_js};</script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
<script>{JS}</script>"""
    return pagina("Grafo de Crédito", "Grafo de Crédito: controle, grupos de risco e desvio de spread das debêntures de transmissão de energia.", corpo)


def main() -> None:
    (PUBLICO / "grafo-credito").mkdir(parents=True, exist_ok=True)
    (PUBLICO / "index.html").write_text(gerar_home(), encoding="utf-8")
    (PUBLICO / "grafo-credito" / "index.html").write_text(gerar_projeto(), encoding="utf-8")
    print("site/public gerado")


if __name__ == "__main__":
    main()
