"""Gera o site estático (alissonprata.io) a partir dos dados do repositório.

Saída em site/public/: index.html (página pessoal) e grafo-credito/index.html
(grafo do universo, simulador de choque de spread e tabela de precificação).

Uso: python site/gerar.py
"""

import csv
import html
import json
import statistics
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PUBLICO = RAIZ / "site" / "public"
PREC = RAIZ / "dados" / "derivados" / "precificacao"
UNIVERSO = RAIZ / "dados" / "referencia" / "universo_series.csv"
CONTROLADORES = RAIZ / "dados" / "referencia" / "controladores_cvm.csv"

CSS = """
:root{--bg:#fbfaf8;--fg:#1d1d1f;--muted:#6b6b70;--line:#e4e2dd;--accent:#1f4e79;--chip:#eef2f6;--panel:#ffffff;--edge:#b9b6ae}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#141416;--fg:#ececee;--muted:#9a9aa0;--line:#2b2b2f;--accent:#8fb8e0;--chip:#1f2630;--panel:#1b1b1e;--edge:#4a4a50}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 "Inter",system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1080px;margin:0 auto;padding:56px 16px 80px}
.estreito{max-width:640px}
h1{font-size:2rem;line-height:1.2;margin:0 0 .5rem;letter-spacing:-.01em}
h2{font-size:1.15rem;margin:2.75rem 0 .75rem}
p{margin:.5rem 0 1rem}
a{color:var(--accent)}
.muted{color:var(--muted)}
.pequeno{font-size:.86rem}
nav{font-size:.9rem;margin-bottom:2.5rem}
nav a{margin-right:1rem;text-decoration:none}
.links a{margin-right:1.25rem}
.tabela{overflow-x:auto;border:1px solid var(--line);border-radius:8px}
table{border-collapse:collapse;width:100%;font-size:.84rem;font-variant-numeric:tabular-nums}
th,td{padding:.45rem .6rem;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
th{font-weight:600;color:var(--muted);background:var(--chip);position:sticky;top:0}
td.t,th.t{text-align:left}
tr:last-child td{border-bottom:0}
tbody tr{cursor:pointer}
tbody tr:hover{background:var(--chip)}
.chip{display:inline-block;padding:.05rem .5rem;border-radius:99px;background:var(--chip);font-size:.76rem}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:1.25rem 0}
.card{border:1px solid var(--line);border-radius:8px;padding:.75rem 1rem;background:var(--panel)}
.card b{display:block;font-size:1.35rem}
#grafo{width:100%;height:auto;aspect-ratio:5/3;max-height:640px;border:1px solid var(--line);border-radius:8px;background:var(--panel);display:block;touch-action:none}
.legenda{display:flex;flex-wrap:wrap;gap:.4rem 1rem;font-size:.8rem;color:var(--muted);margin:.5rem 0}
.legenda span{display:inline-flex;align-items:center;gap:.35rem}
.bolinha{width:10px;height:10px;border-radius:50%;display:inline-block}
.tip{position:fixed;pointer-events:none;background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:.4rem .6rem;font-size:.8rem;max-width:280px;display:none;z-index:10;box-shadow:0 2px 10px rgba(0,0,0,.12)}
.sim{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.3fr);gap:16px;border:1px solid var(--line);border-radius:8px;padding:16px;background:var(--panel)}
@media (max-width:760px){.sim{grid-template-columns:1fr}}
.sim label{display:block;font-size:.82rem;color:var(--muted);margin:.6rem 0 .2rem}
.sim select,.sim input{width:100%;padding:.45rem .5rem;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg);font:inherit}
.botoes{display:flex;flex-wrap:wrap;gap:6px;margin-top:.5rem}
.botoes button{padding:.3rem .6rem;border:1px solid var(--line);border-radius:6px;background:var(--chip);color:var(--fg);font:inherit;font-size:.82rem;cursor:pointer}
.res{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.res div{border:1px solid var(--line);border-radius:6px;padding:.5rem .7rem}
.res small{color:var(--muted);display:block;font-size:.76rem}
.res b{font-size:1.1rem;font-variant-numeric:tabular-nums}
ol li,ul li{margin-bottom:.35rem}
footer{margin-top:3rem;font-size:.82rem;color:var(--muted);border-top:1px solid var(--line);padding-top:1rem}
"""

CORES = ["#4e79a7", "#f28e2b", "#59a14f", "#e15759", "#76b7b2", "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#2f8f9d"]
COR_ISOLADA = "#9a9aa0"


def pagina(titulo: str, descricao: str, corpo: str, extra_head: str = "") -> str:
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(titulo)}</title>
<meta name="description" content="{html.escape(descricao)}">
<style>{CSS}</style>
{extra_head}
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


def montar_grafo(series: list[dict], universo: dict, cores: dict) -> dict:
    controladores = {}
    for c in csv.DictReader(CONTROLADORES.open(encoding="utf-8")):
        controladores.setdefault(c["cnpj_companhia"], []).append(c)

    nos, links, vistos = [], [], set()

    def no(i, **kw):
        if i not in vistos:
            vistos.add(i)
            nos.append({"id": i, **kw})

    for s in series:
        u = universo[s["codigo"]]
        g = u["grupo_risco"]
        cor = cores.get(g, COR_ISOLADA)
        em_id = "e:" + u["cnpj"]
        no(em_id, tipo="emissor", rotulo=u["emissor_atual_snd"].title(), grupo=g, cor=cor,
           detalhe=f"CNPJ {u['cnpj']} · nome ANBIMA: {u['emissor_anbima'].title()}")
        z = s.get("zspread_bps")
        no("s:" + s["codigo"], tipo="serie", rotulo=s["codigo"], grupo=g, cor=cor,
           detalhe=(f"Z-spread {num(z, 0)} bps · duration {num(s.get('duration_mod_anos'), 2)}" if z else s["status"]),
           z=float(z) if z else None)
        links.append({"source": em_id, "target": "s:" + s["codigo"], "tipo": "emitiu"})

        if u["fonte_grupo"] == "CVM FRE":
            # cadeia declarada: cada controlador aponta para quem ele controla (outra holding ou o emissor)
            for c in controladores.get(u["cnpj"], []):
                c_id = "c:" + (c["cnpj_controlador"] or c["controlador"])
                no(c_id, tipo="controlador", rotulo=c["controlador"], grupo=g, cor=cor, detalhe="controlador declarado no Formulário de Referência (CVM)")
                if c["socio_de"]:
                    alvo = "c:" + (c["cnpj_socio_de"] or c["socio_de"])
                    no(alvo, tipo="controlador", rotulo=c["socio_de"], grupo=g, cor=cor, detalhe="controlador declarado no Formulário de Referência (CVM)")
                else:
                    alvo = em_id
                links.append({"source": c_id, "target": alvo, "tipo": "controla"})
        elif u["fonte_grupo"] == "inferido":
            g_id = "g:" + g
            no(g_id, tipo="grupo", rotulo=g, grupo=g, cor=cor, detalhe="grupo inferido, a confirmar na escritura")
            links.append({"source": g_id, "target": em_id, "tipo": "inferido", "motivo": u["motivo_grupo"]})

    # liga grupos inferidos aos controladores documentados do mesmo grupo
    for n in [n for n in nos if n["tipo"] == "grupo"]:
        for c in [c for c in nos if c["tipo"] == "controlador" and c["grupo"] == n["grupo"]]:
            links.append({"source": n["id"], "target": c["id"], "tipo": "inferido", "motivo": "mesmo grupo de risco"})
    unicos = {(l["source"], l["target"], l["tipo"]): l for l in links}
    return {"nodes": nos, "links": list(unicos.values())}


JS = r"""
const D = window.DADOS;
const fmt = (v, c=2) => v==null||isNaN(v) ? '–' : v.toLocaleString('pt-BR',{minimumFractionDigits:c,maximumFractionDigits:c});

// ---------- grafo ----------
(function(){
  const svg = d3.select('#grafo'), tip = document.getElementById('tip');
  const W = () => 1000, H = 600;
  svg.attr('viewBox', '0 0 1000 600').attr('preserveAspectRatio', 'xMidYMid meet');
  const g = svg.append('g');
  svg.call(d3.zoom().scaleExtent([0.2, 4]).on('zoom', e => g.attr('transform', e.transform)));
  const raio = n => n.tipo==='controlador'?8 : n.tipo==='grupo'?10 : n.tipo==='emissor'?6 : 3.2;
  // cada grupo de risco ganha uma região própria num círculo; isoladas ficam num anel externo
  const grupos = [...new Set(D.grafo.nodes.map(n=>n.grupo).filter(g=>g && !g.startsWith('Isolada')))];
  const ancora = {}; grupos.forEach((g,i) => { const a = 2*Math.PI*i/grupos.length; ancora[g] = [500+250*Math.cos(a), 300+190*Math.sin(a)]; });
  const ax = n => ancora[n.grupo] ? ancora[n.grupo][0] : 500, ay = n => ancora[n.grupo] ? ancora[n.grupo][1] : 300;
  const forca = n => ancora[n.grupo] ? .14 : .07;
  D.grafo.nodes.forEach(n => { n.x = ax(n) + (Math.random()-.5)*60; n.y = ay(n) + (Math.random()-.5)*60; });
  const sim = d3.forceSimulation(D.grafo.nodes)
    .force('link', d3.forceLink(D.grafo.links).id(d=>d.id).distance(l => l.tipo==='emitiu'?14:34).strength(l => l.tipo==='emitiu'?1:.35))
    .force('charge', d3.forceManyBody().strength(n => n.tipo==='serie'?-14 : n.tipo==='emissor'?-60 : -110).distanceMax(220))
    .force('x', d3.forceX(ax).strength(forca)).force('y', d3.forceY(ay).strength(forca))
    .force('colide', d3.forceCollide().radius(n => raio(n)+1.5));
  const link = g.append('g').selectAll('line').data(D.grafo.links).join('line')
    .attr('stroke', 'var(--edge)').attr('stroke-opacity', l => l.tipo==='emitiu'?.55:.9)
    .attr('stroke-width', l => l.tipo==='emitiu'?.7:1.3).attr('stroke-dasharray', l => l.tipo==='inferido'?'4 3':null);
  const node = g.append('g').selectAll('circle').data(D.grafo.nodes).join('circle')
    .attr('r', raio).attr('fill', n => n.tipo==='serie'?'var(--panel)':n.cor)
    .attr('stroke', n => n.cor).attr('stroke-width', n => n.tipo==='serie'?1.6:0)
    .style('cursor','pointer')
    .call(d3.drag().on('start',(e,d)=>{if(!e.active)sim.alphaTarget(.3).restart();d.fx=d.x;d.fy=d.y})
                   .on('drag',(e,d)=>{d.fx=e.x;d.fy=e.y})
                   .on('end',(e,d)=>{if(!e.active)sim.alphaTarget(0);d.fx=null;d.fy=null}));
  const rot = g.append('g').selectAll('text').data(D.grafo.nodes.filter(n=>n.tipo!=='serie')).join('text')
    .attr('display', n => n.tipo==='emissor' ? 'none' : null)
    .text(n => n.rotulo.length>28 ? n.rotulo.slice(0,27)+'…' : n.rotulo)
    .attr('font-size', n => n.tipo==='emissor'?8:9.5).attr('fill','var(--muted)').attr('dx', n=>raio(n)+3).attr('dy', 3)
    .style('pointer-events','none');
  const viz = new Map(); D.grafo.links.forEach(l => {[[l.source,l.target],[l.target,l.source]].forEach(([a,b]) => {const k=a.id||a; if(!viz.has(k))viz.set(k,new Set()); viz.get(k).add(b.id||b);});});
  node.on('mouseenter', (e, n) => {
      const v = viz.get(n.id)||new Set();
      node.attr('opacity', m => m.id===n.id||v.has(m.id)?1:.15);
      rot.attr('opacity', m => m.id===n.id||v.has(m.id)?1:.15).attr('display', m => m.tipo!=='emissor'||m.id===n.id||v.has(m.id)?null:'none');
      link.attr('opacity', l => l.source.id===n.id||l.target.id===n.id?1:.08);
      tip.style.display='block'; tip.innerHTML = '<b>'+n.rotulo+'</b><br><span class="muted">'+(n.grupo||'')+'</span><br>'+(n.detalhe||'');
    })
    .on('mousemove', e => {tip.style.left=(e.clientX+12)+'px'; tip.style.top=(e.clientY+12)+'px';})
    .on('mouseleave', () => {node.attr('opacity',1); rot.attr('opacity',1).attr('display', m => m.tipo==='emissor'?'none':null); link.attr('opacity',1); tip.style.display='none';})
    .on('click', (e, n) => { if(n.tipo==='serie'){ selecionar(n.rotulo); document.getElementById('simulador').scrollIntoView({behavior:'smooth'}); }});
  const desenhar = () => {
    link.attr('x1',l=>l.source.x).attr('y1',l=>l.source.y).attr('x2',l=>l.target.x).attr('y2',l=>l.target.y);
    node.attr('cx',n=>n.x).attr('cy',n=>n.y); rot.attr('x',n=>n.x).attr('y',n=>n.y);
  };
  sim.stop(); for (let i=0; i<400; i++) sim.tick(); desenhar();  // layout pronto antes de aparecer
  sim.on('tick', desenhar);
})();

// ---------- simulador ----------
const sel = document.getElementById('serie'), choque = document.getElementById('choque');
D.series.filter(s => D.fluxos[s.codigo]).forEach(s => { const o=document.createElement('option'); o.value=s.codigo; o.textContent=s.codigo+' · '+s.emissor; sel.appendChild(o); });
function preco(f, y){ let p=0; for(let i=0;i<f.t.length;i++) p += f.cf[i]/Math.pow(1+y, f.t[i]); return p; }
function calcular(){
  const s = D.series.find(x => x.codigo===sel.value), f = D.fluxos[sel.value]; if(!s||!f) return;
  const ds = (parseFloat(choque.value)||0)/1e4, p0 = preco(f, f.y), p1 = preco(f, f.y+ds);
  const cheio = (p1/p0-1)*100, aprox = (-s.dmod*ds + .5*s.convex*ds*ds)*100;
  document.getElementById('r_pu').textContent = 'R$ '+fmt(s.pu,2);
  document.getElementById('r_pu_novo').textContent = 'R$ '+fmt(s.pu*p1/p0,2);
  document.getElementById('r_var').textContent = fmt(cheio,2)+'%';
  document.getElementById('r_aprox').textContent = fmt(aprox,2)+'%';
  document.getElementById('r_dur').textContent = fmt(s.dmod,2)+' anos';
  document.getElementById('r_z').textContent = fmt(s.z,0)+' bps' + (s.zgu!=null ? ' (gross-up '+fmt(s.zgu,0)+')' : '');
  document.getElementById('r_be6').textContent = fmt(s.be6,1)+' bps';
  document.getElementById('r_be12').textContent = fmt(s.be12,1)+' bps';
}
function selecionar(c){ sel.value=c; calcular(); }
sel.addEventListener('change', calcular); choque.addEventListener('input', calcular);
document.querySelectorAll('.botoes button').forEach(b => b.addEventListener('click', () => { choque.value=b.dataset.v; calcular(); }));
document.querySelectorAll('tbody tr[data-codigo]').forEach(tr => tr.addEventListener('click', () => { selecionar(tr.dataset.codigo); document.getElementById('simulador').scrollIntoView({behavior:'smooth'}); }));
if (sel.options.length) { sel.value = sel.options[0].value; calcular(); }
"""


def gerar_projeto() -> str:
    arq = sorted(p for p in PREC.glob("*.csv"))[-1]
    data_ref = arq.stem
    series = list(csv.DictReader(arq.open(encoding="utf-8")))
    fluxos = json.loads((PREC / f"{data_ref}_fluxos.json").read_text(encoding="utf-8"))
    universo = {u["codigo"]: u for u in csv.DictReader(UNIVERSO.open(encoding="utf-8"))}

    grupos = sorted({universo[s["codigo"]]["grupo_risco"] for s in series} - {"Isolada (a identificar)"})
    cores = {g: CORES[i % len(CORES)] for i, g in enumerate(grupos)}
    grafo = montar_grafo(series, universo, cores)

    ok = [s for s in series if s["status"] == "ok"]
    zs = [float(s["zspread_bps"]) for s in ok]
    zgu = [float(s["zspread_grossup_bps"]) for s in ok if s["zspread_grossup_bps"]]
    n_emissores = len({universo[s["codigo"]]["cnpj"] for s in series})
    n_cvm = len({universo[s["codigo"]]["cnpj"] for s in series if universo[s["codigo"]]["fonte_grupo"] == "CVM FRE"})

    dados_series = [{
        "codigo": s["codigo"], "emissor": s["emissor_atual"].title(), "pu": float(s["pu_anbima"]) if s["pu_anbima"] else None,
        "dmod": float(s["duration_mod_anos"]), "convex": float(s["convexidade"]), "z": float(s["zspread_bps"]),
        "zgu": float(s["zspread_grossup_bps"]) if s["zspread_grossup_bps"] else None,
        "be6": float(s["breakeven_6m_bps"]), "be12": float(s["breakeven_12m_bps"]),
    } for s in ok]

    ordenadas = sorted(series, key=lambda s: (universo[s["codigo"]]["grupo_risco"].startswith("Isolada"), universo[s["codigo"]]["grupo_risco"], s["emissor_atual"], s["codigo"]))
    trs = []
    for s in ordenadas:
        u = universo[s["codigo"]]
        cor = cores.get(u["grupo_risco"], COR_ISOLADA)
        fonte = {"CVM FRE": "CVM", "inferido": "inferido"}.get(u["fonte_grupo"], "")
        incent = {"S": "sim", "N": "não"}.get(s["incentivada"], "–")
        ok_s = s["status"] == "ok"
        abre = f'<tr data-codigo="{html.escape(s["codigo"])}">' if ok_s else "<tr>"
        trs.append(
            abre +
            f'<td class="t">{html.escape(s["codigo"])}</td>'
            f'<td class="t">{html.escape(s["emissor_atual"].title())}</td>'
            f'<td class="t"><span class="bolinha" style="background:{cor}"></span> {html.escape(u["grupo_risco"])} <span class="muted pequeno">{fonte}</span></td>'
            f'<td class="t">{incent}</td>'
            f'<td class="t">{html.escape(s["garantia"] or "–")}</td>'
            f'<td>{num(s["taxa_indicativa"], 4)}</td>'
            f'<td>{num(s.get("zspread_bps"), 0)}</td>'
            f'<td>{num(s.get("zspread_grossup_bps"), 0)}</td>'
            f'<td>{num(s.get("duration_mod_anos"), 2)}</td>'
            f'<td>{num(s.get("choque_100_pct"), 2)}</td>'
            f'<td>{num(s["pu_anbima"], 2)}</td>'
            f'<td class="t pequeno muted">{"" if ok_s else html.escape(s["status"])}</td>'
            "</tr>"
        )

    legenda = "".join(f'<span><i class="bolinha" style="background:{c}"></i>{html.escape(g)}</span>' for g, c in cores.items())
    legenda += f'<span><i class="bolinha" style="background:{COR_ISOLADA}"></i>Isolada (a identificar)</span>'
    dia = date.fromisoformat(data_ref).strftime("%d/%m/%Y")
    dados_js = json.dumps({"grafo": grafo, "series": dados_series, "fluxos": fluxos}, ensure_ascii=False, separators=(",", ":"))

    corpo = f"""<main>
<nav><a href="/">Alisson Prata Oliveira</a><a href="https://github.com/alissondpoliveira/grafo-credito">Código e dados</a></nav>
<h1>Grafo de Crédito</h1>
<p class="muted" style="max-width:700px">Memória viva dos emissores de debêntures do crédito privado brasileiro, organizada como grafo: quem controla quem, quem emitiu o quê e quanto cada emissão paga sobre a curva real. Piloto: transmissoras de energia elétrica.</p>

<div class="cards">
<div class="card"><span class="muted">Data de referência</span><b>{dia}</b></div>
<div class="card"><span class="muted">Séries no piloto</span><b>{len(series)}</b></div>
<div class="card"><span class="muted">Emissores</span><b>{n_emissores}</b></div>
<div class="card"><span class="muted">Controle confirmado na CVM</span><b>{n_cvm} emissores</b></div>
<div class="card"><span class="muted">Z-spread mediano IPCA+</span><b>{num(statistics.median(zs), 0)} bps</b></div>
<div class="card"><span class="muted">Mediano com gross-up 15%</span><b>{num(statistics.median(zgu), 0) if zgu else "–"} bps</b></div>
</div>

<h2>Grafo do universo</h2>
<p class="muted pequeno">Passe o mouse para ver as ligações de um nó; arraste para reorganizar; role para dar zoom; clique numa série para levá-la ao simulador. Nós cheios grandes são controladores (CVM) ou grupos inferidos, nós cheios médios são emissores, círculos vazados são séries.</p>
<div class="legenda">{legenda}<span>── controle declarado na CVM</span><span>- - grupo inferido</span></div>
<svg id="grafo" role="img" aria-label="Grafo de controladores, emissores e séries de debêntures"></svg>
<div id="tip" class="tip"></div>

<h2 id="simulador">Simulador de abertura e fechamento de spread</h2>
<div class="sim">
<div>
<label for="serie">Série</label><select id="serie"></select>
<label for="choque">Choque no spread (bps)</label><input id="choque" type="number" step="5" value="100">
<div class="botoes"><button data-v="-100">−100</button><button data-v="-50">−50</button><button data-v="50">+50</button><button data-v="100">+100</button><button data-v="200">+200</button></div>
<p class="muted pequeno" style="margin-top:1rem">Reprecificação completa: desconta o fluxo remanescente (juros e amortizações da agenda SND) pela taxa indicativa mais o choque. A aproximação usa duration modificada e convexidade.</p>
</div>
<div class="res">
<div><small>PU ANBIMA</small><b id="r_pu">–</b></div>
<div><small>PU após o choque</small><b id="r_pu_novo">–</b></div>
<div><small>Variação (reprecificação completa)</small><b id="r_var">–</b></div>
<div><small>Variação (duration + convexidade)</small><b id="r_aprox">–</b></div>
<div><small>Duration modificada</small><b id="r_dur">–</b></div>
<div><small>Z-spread sobre a curva real</small><b id="r_z">–</b></div>
<div><small>Break-even de abertura em 6 meses</small><b id="r_be6">–</b></div>
<div><small>Break-even de abertura em 12 meses</small><b id="r_be12">–</b></div>
</div>
</div>

<h2>Tabela de precificação</h2>
<p class="muted pequeno">Z-spread: spread constante somado à curva zero-cupom real (ETTJ IPCA, ANBIMA) que reproduz o preço da série. Choque +100: variação do PU com reprecificação completa. Clique numa linha para simular.</p>
<div class="tabela"><table>
<thead><tr><th class="t">Código</th><th class="t">Emissor atual (SND)</th><th class="t">Grupo de risco</th><th class="t">Incentivada</th><th class="t">Garantia</th><th>Taxa indicativa (%)</th><th>Z-spread (bps)</th><th>Z gross-up (bps)</th><th>Duration mod.</th><th>Choque +100 (%)</th><th>PU (R$)</th><th class="t"></th></tr></thead>
<tbody>
{chr(10).join(trs)}
</tbody></table></div>

<h2>Método e limites</h2>
<ul class="pequeno">
<li><b>Fluxo de pagamentos</b> montado da agenda de eventos do SND. Validação: a duration recalculada bate com a da ANBIMA (mediana de erro perto de zero); séries que não batem ficam fora do Z-spread e aparecem marcadas.</li>
<li><b>Emissor atual</b> é o do SND (por CNPJ). Os nomes da ANBIMA estão desatualizados em várias séries após trocas de controle.</li>
<li><b>Grupo de risco</b>: "CVM" = controlador pessoa jurídica declarado no Formulário de Referência; "inferido" = regra explícita (cadeia societária ou nome), a confirmar na escritura.</li>
<li><b>Gross-up</b> provisório: alíquota de 15% sobre a taxa nominal, com inflação implícita da ETTJ na duration de cada série. É o efeito tributário máximo para pessoa física; o desconto que o mercado de fato aplica às incentivadas ainda será estimado.</li>
<li><b>Break-even</b>: quanto o spread pode abrir no horizonte até a perda de preço igualar o carry do Z-spread no período. Z-spread negativo gera break-even negativo.</li>
<li>Debêntures DI+ do universo ainda não entram no Z-spread nem no simulador.</li>
</ul>

<footer>
Fontes: ANBIMA (taxas de debêntures e títulos públicos, ETTJ), SND/debentures.com.br (características e agenda), CVM (Formulário de Referência). Data de referência {dia}. A taxa indicativa é referência de preço justo, não necessariamente negócio fechado.
Conteúdo de pesquisa e educacional. Não constitui recomendação de investimento.
</footer>
</main>
<script>window.DADOS = {dados_js};</script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
<script>{JS}</script>"""
    return pagina("Grafo de Crédito", "Grafo de Crédito: transmissoras de energia, Z-spread sobre a curva real e simulador de choque de spread.", corpo)


def main() -> None:
    (PUBLICO / "grafo-credito").mkdir(parents=True, exist_ok=True)
    (PUBLICO / "index.html").write_text(gerar_home(), encoding="utf-8")
    (PUBLICO / "grafo-credito" / "index.html").write_text(gerar_projeto(), encoding="utf-8")
    print("site/public gerado")


if __name__ == "__main__":
    main()
