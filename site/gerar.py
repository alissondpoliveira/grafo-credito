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
from datetime import date, timedelta
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
 --div-neg-2:#1c5cab;--div-neg-1:#86b6ef;--div-0:#d9d7d1;--div-pos-1:#f0a3a2;--div-pos-2:#c7302f;--doc-oficial:#4a3aa7;--doc-noticia:#eda100;--m-energia:#eda100;--m-infra:#4a3aa7;--m-commod:#008300;--m-consumo:#e87ba4;}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){color-scheme:dark;
 --bg:#121211;--surface:#1a1a19;--surface-2:#232321;--ink:#ffffff;--ink-2:#c3c2b7;--ink-3:#8a8984;--line:#2c2c2a;--line-2:#3a3a37;
 --accent:#6da7ec;--hull:rgba(195,194,183,.06);--hull-line:rgba(195,194,183,.25);--edge:#4d4c48;
 --div-neg-2:#3987e5;--div-neg-1:#1c4f8f;--div-0:#4a4a46;--div-pos-1:#8f3534;--div-pos-2:#e66767;--doc-oficial:#9085e9;--doc-noticia:#c98500;--m-energia:#c98500;--m-infra:#9085e9;--m-commod:#008300;--m-consumo:#d55181;}}
:root[data-theme="dark"]{color-scheme:dark;
 --bg:#121211;--surface:#1a1a19;--surface-2:#232321;--ink:#ffffff;--ink-2:#c3c2b7;--ink-3:#8a8984;--line:#2c2c2a;--line-2:#3a3a37;
 --accent:#6da7ec;--hull:rgba(195,194,183,.06);--hull-line:rgba(195,194,183,.25);--edge:#4d4c48;
 --div-neg-2:#3987e5;--div-neg-1:#1c4f8f;--div-0:#4a4a46;--div-pos-1:#8f3534;--div-pos-2:#e66767;--doc-oficial:#9085e9;--doc-noticia:#c98500;--m-energia:#c98500;--m-infra:#9085e9;--m-commod:#008300;--m-consumo:#d55181;}
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
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:0;background:var(--surface);border:1px solid var(--line);border-radius:10px;overflow:hidden;margin-top:28px}
.tile{background:var(--surface);padding:14px 16px;box-shadow:inset -1px -1px 0 var(--line)}
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
.selo.hy{border-color:var(--div-pos-2);color:var(--div-pos-2);font-weight:600}
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
#trilha a{color:var(--accent);text-decoration:none}#trilha a:hover{text-decoration:underline}#trilha span{color:var(--ink)}
.busca-caixa{position:relative;margin-top:22px;max-width:720px}
#busca{width:100%;padding:.7rem .9rem;font-size:1rem;border-radius:8px;border:1px solid var(--line-2);background:var(--surface)}
#resultados{position:absolute;z-index:15;left:0;right:0;top:100%;margin:4px 0 0;padding:4px;list-style:none;background:var(--surface);border:1px solid var(--line-2);border-radius:8px;box-shadow:0 8px 24px rgba(0,0,0,.12);display:none;max-height:380px;overflow:auto}
#resultados li{padding:.45rem .6rem;border-radius:6px;cursor:pointer;font-size:.86rem}
#resultados li:hover,#resultados li.foco{background:var(--surface-2)}
#ativo{margin-top:28px}
.ativo-grade{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:0;border:1px solid var(--line);border-radius:8px;overflow:hidden;margin-top:14px}
.ativo-grade div{padding:10px 12px;box-shadow:inset -1px -1px 0 var(--line)}
.ativo-grade small{display:block;color:var(--ink-2);font-size:.74rem}.ativo-grade b{font-size:1.1rem;font-variant-numeric:tabular-nums}
.ativo-grade em{display:block;font-style:normal;font-size:.72rem;color:var(--ink-3)}
.aviso-sel{position:absolute;left:12px;bottom:12px;background:var(--surface);border:1px solid var(--line-2);border-radius:8px;padding:.45rem .7rem;font-size:.82rem;box-shadow:0 4px 14px rgba(0,0,0,.1)}
.aviso-sel a{color:var(--accent)}
#tab tbody tr.sel{background:var(--surface-2);box-shadow:inset 3px 0 0 var(--ink)}
.res span{display:block;margin-top:2px}
.boleta{border:1px solid var(--line-2);border-radius:10px;padding:14px 16px;margin:14px 0 6px;background:var(--surface)}
.boleta .linha{font-size:1.02rem;line-height:1.55}
.boleta .linha b{font-variant-numeric:tabular-nums}
.boleta .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px 18px;margin-top:12px}
.boleta .kpi .r{font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;color:var(--ink-3)}
.boleta .kpi .v{font-size:1.25rem;font-weight:650;font-variant-numeric:tabular-nums}
.boleta .kpi .s{font-size:.76rem;color:var(--ink-2)}
.carac{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:0 22px;margin-top:6px}
.carac div{display:flex;justify-content:space-between;gap:10px;font-size:.82rem;padding:.3rem 0;border-bottom:1px solid var(--line)}
.carac div span:first-child{color:var(--ink-3)}.carac div span:last-child{text-align:right;font-variant-numeric:tabular-nums}
.legenda-macro i{width:12px;height:12px}
#ficha{margin-top:12px;padding:16px;display:none}
#ficha h3{margin:0 0 .2rem;font-family:Newsreader,Georgia,serif;font-size:1.2rem}
.ficha-grade{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;margin-top:12px}
.ficha-grade h4{margin:0 0 .35rem;font-size:.76rem;text-transform:uppercase;letter-spacing:.06em;color:var(--ink-3)}
.ficha-grade ul{list-style:none;margin:0;padding:0}.ficha-grade li{font-size:.8rem;padding:.25rem 0;border-bottom:1px solid var(--line)}
.ficha-grade li span{color:var(--ink-3);font-variant-numeric:tabular-nums;margin-right:6px}
.ficha-grade a{color:var(--ink);text-decoration:none}.ficha-grade a:hover{color:var(--accent);text-decoration:underline}
footer{margin-top:56px;font-size:.78rem;color:var(--ink-3);border-top:1px solid var(--line);padding-top:16px}
.links a{margin-right:1.25rem}
/* ---------- aplicativo: barra fixa, abas, telas e ficha lateral ---------- */
.pular{position:absolute;left:-999px;top:8px;z-index:60;background:var(--ink);color:var(--surface);padding:.4rem .7rem;border-radius:6px}.pular:focus{left:8px}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.barra{position:sticky;top:0;z-index:30;background:color-mix(in srgb,var(--bg) 90%,transparent);-webkit-backdrop-filter:saturate(1.4) blur(10px);backdrop-filter:saturate(1.4) blur(10px);border-bottom:1px solid var(--line)}
.barra-in{max-width:1240px;margin:0 auto;padding:10px 16px 2px;display:flex;align-items:center;gap:18px}
.marca-site{display:flex;flex-direction:column;text-decoration:none;color:var(--ink);line-height:1.15;flex:none}
.marca-site b{font-family:Newsreader,Georgia,serif;font-size:1.3rem;font-weight:600;letter-spacing:-.01em}
.marca-site span{font-size:.72rem;color:var(--ink-3)}
.barra .busca-caixa{flex:1;max-width:560px;margin:0;position:relative}
.barra #busca{padding:.5rem 2.2rem .5rem 2.2rem;font-size:.92rem;border-radius:9px;background:var(--surface) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='none' stroke='%238a8984' stroke-width='2'%3E%3Ccircle cx='7' cy='7' r='5'/%3E%3Cpath d='m11 11 3.5 3.5'/%3E%3C/svg%3E") no-repeat 10px 50%}
.atalho,kbd{font:600 .7rem Inter,system-ui,sans-serif;border:1px solid var(--line-2);border-bottom-width:2px;border-radius:4px;padding:0 .35rem;color:var(--ink-3);background:var(--surface)}
.atalho{position:absolute;right:9px;top:50%;transform:translateY(-50%)}
.barra-acoes{margin-left:auto;display:flex;gap:10px;align-items:center;flex:none}
.link-sobre{font-size:.85rem;color:var(--ink-2);text-decoration:none}.link-sobre:hover{color:var(--ink)}
.icone{width:34px;height:34px;display:inline-grid;place-items:center;border-radius:8px;border:1px solid var(--line-2);background:var(--surface);padding:0;font-size:.95rem;color:var(--ink-2);text-decoration:none;flex:none}
.icone:hover{color:var(--ink);border-color:var(--ink-3)}
.abas{max-width:1240px;margin:0 auto;padding:0 10px;display:flex;gap:2px;overflow-x:auto;scrollbar-width:none}
nav.abas,nav#trilha{justify-content:flex-start;padding-bottom:0;margin-bottom:0;border-bottom:0}nav.abas a,nav#trilha a{margin-left:0}
.recentes[hidden]{display:none}
.abas::-webkit-scrollbar{display:none}
.abas a{flex:none;padding:.6rem .7rem .55rem;font-size:.86rem;color:var(--ink-2);text-decoration:none;border-bottom:2px solid transparent;white-space:nowrap}
.abas a:hover{color:var(--ink)}
.abas a[aria-current=page]{color:var(--ink);border-bottom-color:var(--ink);font-weight:600}
main.app{max-width:1240px;margin:0 auto;padding:26px 16px 64px}
.vista{margin-top:0}.vista[hidden]{display:none}
.vista-cab{display:flex;justify-content:space-between;align-items:flex-start;gap:10px 24px;flex-wrap:wrap;margin-bottom:14px}
.vista-cab h2{font-size:1.65rem;margin:0}
.vista-cab p{margin:.25rem 0 0;max-width:720px;color:var(--ink-2);font-size:.92rem}
details.ajuda{font-size:.85rem;color:var(--ink-2);max-width:460px;padding-top:.4rem}
details.ajuda summary,details.legenda-det summary{cursor:pointer;color:var(--accent);font-size:.85rem;list-style:none}
details.ajuda summary::before,details.legenda-det summary::before{content:'▸ ';display:inline-block;transition:transform .15s}
details[open].ajuda summary::before,details[open].legenda-det summary::before{transform:rotate(90deg)}
details.ajuda p{margin:.4rem 0 0;background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:10px 12px}
details.legenda-det{border-top:1px solid var(--line);padding:8px 12px}
details.legenda-det .legenda{border-top:0;padding:8px 0 0}
.barra-filtros,.controles{display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:10px 12px;border-bottom:1px solid var(--line)}
.espaco{flex:1}
.barra-filtros input[type=search]{min-width:220px;flex:1;max-width:340px}
.chk{display:inline-flex;gap:6px;align-items:center;font-size:.82rem;color:var(--ink-2);cursor:pointer}
.seg{display:inline-flex;border:1px solid var(--line-2);border-radius:7px;overflow:hidden;flex:none}
.seg button{border:0;border-radius:0;background:var(--surface);padding:.35rem .6rem}
.seg button+button{border-left:1px solid var(--line-2)}
.seg button.ativo{background:var(--ink);color:var(--surface)}
.rotulo-ctrl{margin-left:4px}
#trilha{display:flex;flex-wrap:wrap;gap:4px;align-items:center}
.proximo{margin-top:14px;font-size:.86rem;color:var(--ink-2)}
.heroi{max-width:780px}
.heroi h1{font-size:2.7rem}
h2.sec{font-size:1.25rem;margin:2.2rem 0 .7rem}
.jornada{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:12px;counter-reset:passo}
.jornada a{position:relative;display:flex;flex-direction:column;gap:.25rem;height:100%;text-decoration:none;color:var(--ink);background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:16px 16px 14px;transition:border-color .15s,transform .15s,box-shadow .15s}
.jornada a:hover{border-color:var(--ink-3);transform:translateY(-2px);box-shadow:0 6px 18px rgba(0,0,0,.06)}
.jornada li{counter-increment:passo}
.jornada .passo{font-size:.76rem;color:var(--ink-3);font-weight:600;letter-spacing:.02em}
.jornada .passo::before{content:counter(passo) '. '}
.jornada b{font-family:Newsreader,Georgia,serif;font-size:1.25rem;font-weight:600}
.jornada span:not(.passo){font-size:.86rem;color:var(--ink-2)}
.jornada em{font-style:normal;font-size:.84rem;color:var(--accent);margin-top:auto;padding-top:.4rem}
.ranking{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px}
.ranking .painel{padding:12px 14px}
.ranking h3{margin:0 0 .4rem;font-size:.92rem}.ranking h3 span{font-weight:400;font-size:.78rem;margin-left:4px}
.lista-clicavel{list-style:none;margin:0;padding:0}
.lista-clicavel li{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:.5rem .4rem;border-top:1px solid var(--line);cursor:pointer;font-size:.86rem;border-radius:6px}
.lista-clicavel li:hover,.lista-clicavel li:focus-visible{background:var(--surface-2)}
.lista-clicavel li>span:first-child{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.lista-clicavel li b{font-variant-numeric:tabular-nums;white-space:nowrap}
.recentes{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:14px 0 0}
.chip{display:inline-flex;gap:6px;align-items:center;border:1px solid var(--line-2);background:var(--surface);border-radius:999px;padding:.2rem .65rem;font-size:.8rem;cursor:pointer;color:var(--ink)}
.chip:hover{border-color:var(--ink-3)}
.tabela{max-height:calc(100vh - 230px)}
#tab td:first-child,#tab th:first-child{position:sticky;left:0;z-index:2;background:var(--surface)}
#tab th:first-child{z-index:3;background:var(--surface-2)}
#tab tbody tr:hover td:first-child{background:var(--surface-2)}
#tab .extra{display:none}#tab.mostrar-extra .extra{display:table-cell}
.grafico-desvio{padding:8px 4px}
/* ficha lateral */
.fundo{position:fixed;inset:0;background:rgba(0,0,0,.32);z-index:40;opacity:0;pointer-events:none;transition:opacity .2s}
body.gaveta-aberta .fundo{opacity:1;pointer-events:auto}
.gaveta{position:fixed;top:0;right:0;bottom:0;width:min(540px,100vw);background:var(--surface);border-left:1px solid var(--line-2);z-index:41;display:flex;flex-direction:column;transform:translateX(102%);transition:transform .25s ease;box-shadow:-14px 0 36px rgba(0,0,0,.14)}
body.gaveta-aberta .gaveta{transform:none}
.gaveta[hidden]{display:none}
.gav-topo{display:flex;gap:10px;align-items:flex-start;padding:14px 16px 8px 18px}
.gav-cab{flex:1;min-width:0}
.gav-cab h2{font-size:1.55rem;margin:.1rem 0 0;line-height:1.15}
.gav-cab h2 small{font-family:Inter,system-ui,sans-serif;font-size:.9rem;font-weight:400;color:var(--ink-2);display:block;margin-top:2px}
.gav-cab .linha-info{font-size:.8rem;color:var(--ink-2);margin:.35rem 0 0}
.gav-acoes{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}
.gav-acoes button{font-size:.8rem}
.gav-abas{display:flex;gap:0;overflow-x:auto;padding:0 10px;border-bottom:1px solid var(--line);flex:none;scrollbar-width:none}
.gav-abas::-webkit-scrollbar{display:none}
.gav-abas button{border:0;background:none;border-bottom:2px solid transparent;border-radius:0;padding:.55rem .65rem;color:var(--ink-2);white-space:nowrap;font-size:.84rem}
.gav-abas button[aria-selected=true]{color:var(--ink);border-bottom-color:var(--ink);font-weight:600}
.gav-corpo{overflow-y:auto;padding:12px 18px 40px;flex:1;overscroll-behavior:contain}
.gav-corpo .boleta{margin-top:4px}
.gav-corpo .boleta .kpis{grid-template-columns:repeat(2,minmax(0,1fr))}
.gav-corpo .boleta .kpi .v{font-size:1.1rem}
.gav-corpo h3:first-child{margin-top:.2rem}
.gav-corpo .tabela{max-height:300px;border:1px solid var(--line);border-radius:8px}
.passos{margin-top:22px;border-top:1px solid var(--line);padding-top:12px}
.passos h3{margin:0 0 .5rem}
.passos .lista-clicavel li{border-top:0;border-bottom:1px solid var(--line)}
.passos .lista-clicavel li>span:last-child{color:var(--accent)}
.mini-sim label{display:block;font-size:.8rem;color:var(--ink-2);margin-bottom:.2rem}
@media (min-width:1280px){
 body.gaveta-aberta .fundo{opacity:0;pointer-events:none}
 body{transition:padding-right .25s ease}
 body.gaveta-aberta{padding-right:540px}
 .gaveta{box-shadow:none}
}
@media (max-width:760px){
 .barra-in{flex-wrap:wrap;gap:8px 12px;padding-top:8px}
 .barra .busca-caixa{order:3;flex-basis:100%;max-width:none}
 .atalho{display:none}
 .marca-site b{font-size:1.15rem}
 main.app{padding-top:18px}
 .heroi h1{font-size:2.1rem}
 .vista-cab h2{font-size:1.35rem}
 .tiles{grid-template-columns:repeat(2,minmax(0,1fr))}
 .barra-filtros input[type=search]{min-width:0;max-width:none;flex-basis:100%}
 .barra-filtros select{flex:1}
 .rotulo-ctrl{display:none}
 .so-largo{display:none}
 .controles .espaco{display:none}
 .controles select{flex:1 1 100%}
 .gaveta{width:100vw;border-left:0}
 .gav-cab h2{font-size:1.35rem}
 .tabela{max-height:none}
}
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


SEGMENTOS_NOMES = {
    "transmissao": "Transmissão", "geracao": "Geração", "distribuicao": "Distribuição", "integrada_gt": "Integradas G+T",
    "energia_diversificada": "Holdings de energia", "comercializacao": "Comercialização", "saneamento": "Saneamento",
    "distribuicao_gas": "Distribuição de gás", "rodovias": "Rodovias", "ferrovias": "Ferrovias", "portos": "Portos",
    "aeroportos": "Aeroportos", "mobilidade_urbana": "Mobilidade urbana", "logistica": "Logística", "locacao": "Locação de veículos",
    "saude": "Saúde", "telecom": "Telecomunicações", "varejo": "Varejo", "agro_acucar_etanol": "Agro, açúcar e etanol",
    "oleo_gas": "Óleo, gás e combustíveis", "mineracao_siderurgia": "Mineração e siderurgia", "educacao": "Educação",
    "industria": "Indústria", "financeiro": "Financeiro", "servicos_lazer": "Serviços e lazer",
    "imobiliario_construcao": "Imobiliário e construção", "quimica": "Química", "papel_celulose": "Papel e celulose",
    "alimentos_bebidas": "Alimentos e bebidas", "tecnologia_midia": "Tecnologia e mídia", "servicos_ambientais": "Serviços ambientais",
    "outros_corporativo": "Outros corporativos",
}


PERIODO = {1: "mensal", 3: "trimestral", 6: "semestral", 12: "anual"}


def montar_ponta(snd_c: dict) -> dict:
    """Visão de mesa por série: taxa ANBIMA do dia (compra, venda, indicativa), negócios do SND com taxa
    implícita aproximada, agenda de juros e amortização e características da emissão (SND)."""
    dias = sorted((RAIZ / "dados" / "anbima" / "debentures" / "normalizado").glob("*/*.csv"))
    anbima: dict[str, dict] = {}  # codigo -> {data: linha}
    for arq in dias:
        for l in ler_csv(arq):
            if l["taxa_indicativa"]:
                anbima.setdefault(l["codigo"], {})[l["data_referencia"]] = l
    hoje = dias[-1].stem if dias else ""
    agenda: dict[str, list] = {}
    for l in ler_csv(RAIZ / "dados" / "snd" / "agenda.csv"):
        pg = l["Data do Pagamento"] or l["Data do Evento"]
        if len(pg) == 10:
            iso = pg[6:] + "-" + pg[3:5] + "-" + pg[:2]
            if iso >= hoje:
                ev_nome = "Amortização" if l["Evento"].startswith("Amortiza") else l["Evento"]
                agenda.setdefault(l["Ativo"], []).append([iso, ev_nome, l["Taxa/Percentual"].replace(".", "").replace(",", ".")])
    negocios: dict[str, list] = {}
    for l in ler_csv(RAIZ / "dados" / "snd" / "negocios.csv"):
        negocios.setdefault(l["codigo"], []).append(l)

    def num(v):
        try:
            return float(str(v).replace(",", ".")) if v not in ("", None, "-") else None
        except ValueError:
            return None

    def dmy(v):
        return v[6:] + "-" + v[3:5] + "-" + v[:2] if v and len(v) == 10 and v[2] == "/" else ""

    out = {}
    for cod, c in snd_c.items():
        hist = anbima.get(cod, {})
        ult = hist[max(hist)] if hist else None
        tipo = ult["indexador_tipo"] if ult else ""
        tx_em = num(ult["taxa_emissao"]) if ult else num(c.get("Juros Criterio Novo - Taxa"))
        dmod = num(ult["duration_anos"]) if ult else None
        # taxa implícita do negócio: âncora na ANBIMA do mesmo dia quando houver; senão na taxa de emissão (PU par)
        negs = []
        for n in sorted(negocios.get(cod, []), key=lambda x: x["data"])[-8:][::-1]:
            pct, tx = num(n["pct_pu_curva"]), None
            if pct and dmod and tipo in ("IPCA_MAIS", "DI_MAIS", "PREFIXADO"):
                a = hist.get(n["data"])
                if a and num(a["pct_pu_par"]):
                    tx = num(a["taxa_indicativa"]) - (pct / num(a["pct_pu_par"]) - 1) / dmod * 100
                elif tx_em is not None:
                    tx = tx_em - (pct / 100 - 1) / dmod * 100
            negs.append([n["data"], int(n["quantidade"]), int(n["negocios"]), num(n["pu_medio"]), pct, None if tx is None else round(tx, 4)])
        corte = (date.fromisoformat(hoje) - timedelta(days=180)).isoformat() if hoje else ""
        ult180 = [n for n in negocios.get(cod, []) if n["data"] >= corte]
        ev = sorted(agenda.get(cod, []))
        amort = [e for e in ev if e[1].startswith("Amortiza")]
        cada = num(c.get("Juros Criterio Novo - Cada"))
        un = c.get("Juros Criterio Novo - Unidade", "")
        per = (PERIODO.get(int(cada), f"a cada {int(cada)} meses") if un == "MES" else f"a cada {int(cada)} {un.lower()}") if cada else ""
        qtd_em, vne = num(c.get("Quantidade Emitida")), num(c.get("Valor Nominal na Emissao"))
        qtd_mer = num(c.get("Quantidade em Mercado"))
        out[cod] = {
            "data": max(hist) if hist else "", "tipo": tipo, "texto_emissao": ult["indexador_texto"] if ult else "",
            "tx_em": tx_em, "compra": num(ult["taxa_compra"]) if ult else None, "venda": num(ult["taxa_venda"]) if ult else None,
            "ind": num(ult["taxa_indicativa"]) if ult else None, "int_min": num(ult["intervalo_min"]) if ult else None,
            "int_max": num(ult["intervalo_max"]) if ult else None, "pct_par": num(ult["pct_pu_par"]) if ult else None,
            "dur": dmod, "ntnb": ult["ntnb_referencia"] if ult else "",
            "emissao": c.get("Emissao", "").lstrip("0"), "serie": c.get("Serie", ""), "dt_emissao": dmy(c.get("Data de Emissao", "")),
            "inicio_rent": dmy(c.get("Data do Inicio da Rentabilidade", "")), "venc": dmy(c.get("Data de Vencimento", "")),
            "juros_per": per, "carencia_juros": dmy(c.get("Juros Criterio Novo - Carencia", "")),
            "prox_juros": next((e[0] for e in ev if e[1] == "Juros"), ""),
            "amort": [[e[0], num(e[2])] for e in amort][:1], "n_amort": len(amort),
            "volume_emitido": qtd_em * vne if qtd_em and vne else None, "qtd_mercado": qtd_mer, "vne": vne,
            "vna": num(c.get("Valor Nominal Atual")), "incentivada": c.get("Deb. Incent. (Lei 12.431)", ""),
            "resgate": c.get("Resgate Antecipado", ""), "fiduciario": c.get("Agente Fiduciario", ""),
            "coordenador": c.get("Coordenador Lider", ""),
            "negocios": negs, "dias180": len({n["data"] for n in ult180}),
            "vol180": sum(int(n["quantidade"]) * (num(n["pu_medio"]) or 0) for n in ult180),
            "agenda": ev[:10],
        }
    return out


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
        seg = u.get("segmento", "transmissao")
        g = f"{seg}|{u['grupo_risco']}"
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
                   fonte=d.get("fonte", ""), url=d.get("url", ""), grupo=g, segmento=seg,
                   evento=cl.get("evento"), impacto=cl.get("impacto"), confianca=cl.get("evento_confianca"), status_jev=cl.get("status"))
                links.append({"source": em_id, "target": d_id, "tipo": "doc"})
        no(em_id, tipo="emissor", rotulo=u["emissor_atual_snd"].title(), grupo=g, segmento=seg, cnpj=u["cnpj"],
           detalhe=f"CNPJ {u['cnpj']}" + (f" · nome ANBIMA: {u['emissor_anbima'].title()}" if u["emissor_anbima"] != u["emissor_atual_snd"] else ""))
        d = desvios.get(s["codigo"], {})
        no("s:" + s["codigo"], tipo="serie", rotulo=s["codigo"], grupo=g, segmento=seg,
           spread=d.get("spread"), justo=d.get("justo"), desvio=d.get("desvio"), dp=d.get("dp"), classe=d.get("classe"),
           justo_pares=d.get("justo_pares"), ajuste=d.get("ajuste"), pares=d.get("pares"), justo_reg=d.get("justo_reg"),
           faixa=d.get("faixa"), motivo_faixa=d.get("motivo_faixa"),
           status=s["status"])
        links.append({"source": em_id, "target": "s:" + s["codigo"], "tipo": "emitiu"})

        if u["fonte_grupo"] == "CVM FRE":
            for c in controladores.get(u["cnpj"], []):
                c_id = "c:" + (c["cnpj_controlador"] or c["controlador"])
                no(c_id, tipo="controlador", rotulo=c["controlador"], grupo=g, segmento=seg, detalhe="controlador declarado na CVM")
                alvo = em_id
                if c["socio_de"]:
                    alvo = "c:" + (c["cnpj_socio_de"] or c["socio_de"])
                    no(alvo, tipo="controlador", rotulo=c["socio_de"], grupo=g, segmento=seg, detalhe="controlador declarado na CVM")
                links.append({"source": c_id, "target": alvo, "tipo": "controla"})
        elif u["fonte_grupo"] == "escritura":
            pendentes_escritura.append((s, u, em_id, g))
        elif u["fonte_grupo"] == "inferido":
            g_id = "g:" + g
            no(g_id, tipo="grupo", rotulo=u["grupo_risco"], grupo=g, segmento=seg, detalhe="grupo inferido, a confirmar na escritura")
            links.append({"source": g_id, "target": em_id, "tipo": "inferido"})

        # ligações de risco lidas nas escrituras (status 'a revisar' até revisão humana)
        cl = clausulas.get(s["codigo"])
        if cl and cl.get("fiadora"):
            alvo_nome = sem_acento(cl["fiadora"]).upper()[:18]
            existente = next((n for n in nos if n["tipo"] in ("controlador", "emissor") and sem_acento(n["rotulo"]).upper().startswith(alvo_nome)), None)
            f_id = existente["id"] if existente else "f:" + cl["fiadora"].upper()
            if not existente:
                no(f_id, tipo="garantidor", rotulo=cl["fiadora"], grupo=g, segmento=seg, detalhe="fiadora citada na escritura (a revisar)")
            links.append({"source": f_id, "target": "s:" + s["codigo"], "tipo": "garante"})
        if cl and cl.get("cross_default") == "S" and any(x in cl.get("cross_default_abrange", "") for x in ("Controladora", "Fiadora", "Acionista")):
            for c in controladores.get(u["cnpj"], []):
                if not c["socio_de"]:
                    links.append({"source": "c:" + (c["cnpj_controlador"] or c["controlador"]), "target": "s:" + s["codigo"], "tipo": "cross"})

    # partes citadas nas escrituras: reaproveita o nó do controlador da CVM quando é a mesma empresa
    chave = lambda t: re.sub(r"[^A-Z]", "", sem_acento(t).upper().replace("IEB-", "").replace(" S/A", "").replace(" S.A.", ""))[:22]
    for s, u, em_id, g in pendentes_escritura:
        seg = u.get("segmento", "transmissao")
        for r in revisao.get(s["codigo"], []):
            existente = next((n for n in nos if n["tipo"] == "controlador" and chave(n["rotulo"]) == chave(r["parte"])), None)
            p_id = existente["id"] if existente else "c:" + sem_acento(r["parte"]).upper()
            if not existente:
                no(p_id, tipo="controlador" if "acionista" in r["papel"] or "interveniente" in r["papel"] else "garantidor",
                   rotulo=r["parte"].title(), grupo=g, segmento=seg, detalhe=f'{r["papel"]} na escritura (a revisar)')
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
const textoSerie = n => '<b>'+n.rotulo+'</b> <span class="fraco">'+(n.classe||'')+'</span>'+(n.faixa==='high_yield'?' <span class="selo hy">high yield</span><br><span class="fraco">'+n.motivo_faixa+'</span>':'')+'<br><span class="fraco">'+String(n.grupo||'').split('|').pop()+'</span>'
  + (n.spread!=null ? linha(n.classe==='DI+'?'Spread sobre CDI':'Spread comparável', fmt(n.spread,0)+' bps')
     + linha('Justo pelos pares', fmt(n.justo_pares,0)+' bps') + (n.ajuste ? linha('Ajuste por eventos', sinal(n.ajuste,1)+' bps') : '')
     + linha('Desvio', sinal(n.desvio)+' bps ('+sinal(n.dp,1)+' dp)') + linha('Justo pela regressão', fmt(n.justo_reg,0)+' bps')
     + (n.pares ? '<br><span class="fraco">pares: '+n.pares+'</span>' : '') : '<br>'+n.status);

// ---------- mapa: segmento -> grupos -> empresas -> emissões e documentos ----------
(function(){
  const svg = d3.select('#grafo'); const estreito = innerWidth < 700;
  // em tela estreita o mapa fica em retrato e as fontes crescem, para continuarem legíveis depois da escala
  const W = estreito ? 820 : 1120, H = estreito ? 1040 : 700, FS = estreito ? 1.5 : 1;
  svg.style('aspect-ratio', W+' / '+H);
  svg.attr('viewBox', `0 0 ${W} ${H}`).attr('preserveAspectRatio','xMidYMid meet');
  const g = svg.append('g');
  const zoom = d3.zoom().scaleExtent([.4, 5]).on('zoom', e => g.attr('transform', e.transform));
  svg.call(zoom).on('dblclick.zoom', null);
  const camHull = g.append('g'), camLink = g.append('g'), camNo = g.append('g'), camRot = g.append('g');

  const todos = D.grafo.nodes, porId = new Map(todos.map(n => [n.id, n]));
  const ISOL = 'Isolada (a identificar)';
  const nomeSeg = s => (D.segmentos[s] || s.replace(/_/g,' '));
  const nomeGrupo = k => { const x = k.split('|')[1] || k; return x===ISOL ? 'Isoladas' : x; };
  const segDe = k => k.split('|')[0];
  const paiSerie = new Map(); D.grafo.links.forEach(l => { if (l.tipo==='emitiu' || l.tipo==='doc') paiSerie.set(l.target, l.source); });
  const filho = n => n.tipo==='serie' || n.tipo==='doc';
  const segmentos = [...new Set(todos.map(n => n.segmento))];
  const gruposDe = s => [...new Set(todos.filter(n => n.segmento===s).map(n => n.grupo))];
  const resumoDe = filtro => { const ss = todos.filter(n => n.tipo==='serie' && filtro(n)); const ds = ss.map(n=>n.desvio).filter(v=>v!=null).sort((a,b)=>a-b);
    return {series: ss.length, emissores: todos.filter(n => n.tipo==='emissor' && filtro(n)).length, grupos: new Set(ss.map(n=>n.grupo)).size, mediana: ds.length ? ds[Math.floor(ds.length/2)] : null}; };
  const resumo = {}; segmentos.forEach(s => resumo['S:'+s] = resumoDe(n => n.segmento===s));
  [...new Set(todos.map(n=>n.grupo))].forEach(k => resumo['G:'+k] = resumoDe(n => n.grupo===k));
  segmentos.sort((a,b) => resumo['S:'+b].series - resumo['S:'+a].series);

  // macrossetor de cada segmento: só cor de contexto (bolhas, contornos de grupo, emissores); séries seguem o desvio
  const MACRO = {energia:['transmissao','geracao','distribuicao','integrada_gt','energia_diversificada','comercializacao'],
    infra:['saneamento','distribuicao_gas','servicos_ambientais','rodovias','ferrovias','portos','aeroportos','mobilidade_urbana','logistica','locacao'],
    commod:['agro_acucar_etanol','oleo_gas','mineracao_siderurgia','industria','quimica','papel_celulose']};
  const macroDe = seg => Object.keys(MACRO).find(k => MACRO[k].includes(seg)) || 'consumo';
  const corM = seg => 'var(--m-'+macroDe(seg)+')';
  const tinta = (seg, p) => 'color-mix(in srgb, '+corM(seg)+' '+p+'%, var(--surface))';
  const corDoc = c => ({oficial:'var(--doc-oficial)', escritura:'var(--doc-oficial)', noticia:'var(--doc-noticia)', analise:'var(--doc-analise)'})[c];
  const formaDoc = c => ({oficial:d3.symbolTriangle, escritura:d3.symbolSquare, noticia:d3.symbolDiamond, analise:d3.symbolStar})[c];
  const nomeDoc = {fato_relevante:'Fato relevante', comunicado:'Comunicado ao mercado', aviso_debenturistas:'Aviso aos debenturistas', escritura:'Escritura', noticia:'Notícia', analise:'Análise'};
  const raioBolha = id => (id.startsWith('S:') ? 16 : 11) + (id.startsWith('S:') ? 3.2 : 4.5) * Math.sqrt(resumo[id].series);
  const raio = n => n.tipo==='bolha' ? raioBolha(n.id) : ({controlador:6, grupo:7, garantidor:6, emissor:6.5, serie:4.4, doc:5})[n.tipo];

  const abertosS = new Set(), abertosG = new Set(), abertosE = new Set();
  const rep = id => { const n = porId.get(id); if (!n) return id;
    if (!abertosS.has(n.segmento)) return 'S:'+n.segmento;
    if (!abertosG.has(n.grupo)) return 'G:'+n.grupo;
    if (filho(n) && !abertosE.has(paiSerie.get(id))) return paiSerie.get(id);
    return id; };

  function visiveis(){
    const nos = [];
    if (!abertosS.size) segmentos.forEach(s => nos.push({id:'S:'+s, tipo:'bolha', nivel:'segmento', segmento:s, grupo:'', rotulo:nomeSeg(s)}));
    else { const s = [...abertosS][0]; gruposDe(s).forEach(k => { if (!abertosG.has(k)) nos.push({id:'G:'+k, tipo:'bolha', nivel:'grupo', segmento:s, grupo:k, rotulo:nomeGrupo(k)}); }); }
    todos.forEach(n => { if (!abertosS.has(n.segmento) || !abertosG.has(n.grupo)) return; if (filho(n) && !abertosE.has(paiSerie.get(n.id))) return; nos.push(n); });
    const ids = new Set(nos.map(n=>n.id)), vistos = new Map();
    D.grafo.links.forEach(l => { const s = rep(l.source.id||l.source), t = rep(l.target.id||l.target);
      if (s===t || !ids.has(s) || !ids.has(t)) return;
      const k = s<t ? s+'|'+t : t+'|'+s, bolha = s.startsWith('S:')||s.startsWith('G:')||t.startsWith('S:')||t.startsWith('G:');
      if (!vistos.has(k)) vistos.set(k, {source:s, target:t, tipo: bolha ? 'ponte' : l.tipo}); });
    return {nos, links:[...vistos.values()]};
  }

  // âncoras: grupos abertos no centro; bolhas de grupo dos segmentos abertos num anel interno; segmentos fechados no anel externo
  const ancora = {};
  function posicionarAncoras(nos){
    const abertos = [...abertosG], bolhasG = nos.filter(n => n.nivel==='grupo'), bolhasS = nos.filter(n => n.nivel==='segmento');
    abertos.forEach((k,i) => { const a = 2*Math.PI*i/abertos.length, d = abertos.length>1 ? W*.125 : 0; ancora[k] = [W/2+d*Math.cos(a), H/2+d*.7*Math.sin(a)]; });
    const anel = (lista, rx, ry, desloc) => lista.forEach((n,i) => { const a = -Math.PI/2 + desloc + 2*Math.PI*i/Math.max(lista.length,1); ancora[n.id] = [W/2+rx*Math.cos(a), H/2+ry*Math.sin(a)]; });
    // segmentos do mesmo macrossetor ficam vizinhos no anel (arcos de cor contínua)
    const ordemM = ['energia','infra','commod','consumo'];
    if (!abertosS.size) anel([...bolhasS].sort((x,y) => ordemM.indexOf(macroDe(x.segmento)) - ordemM.indexOf(macroDe(y.segmento)) || resumo['S:'+y.segmento].series - resumo['S:'+x.segmento].series), W*.35, H*.365, 0);
    else anel(bolhasG, abertos.length ? W*.357 : W*.268, abertos.length ? H*.379 : H*.307, 0);
  }
  const alvo = n => n.tipo==='bolha' ? (ancora[n.id] || [W/2,H/2]) : (ancora[n.grupo] || ancora['G:'+n.grupo] || [W/2,H/2]);

  const sim = d3.forceSimulation().alphaDecay(.03).velocityDecay(.35)
    .force('link', d3.forceLink().id(d=>d.id).distance(l => l.tipo==='ponte'?170 : l.tipo==='emitiu'?30 : l.tipo==='doc'?44 : 46).strength(l => l.tipo==='ponte'?.015 : l.tipo==='emitiu'?.9 : .35))
    .force('charge', d3.forceManyBody().strength(n => n.tipo==='bolha'?-260 : n.tipo==='serie'?-40 : -110).distanceMax(280))
    .force('x', d3.forceX(n => alvo(n)[0]).strength(n => n.tipo==='bolha'?.35:.2))
    .force('y', d3.forceY(n => alvo(n)[1]).strength(n => n.tipo==='bolha'?.35:.2))
    .force('colide', d3.forceCollide().radius(n => raio(n)+(n.tipo==='bolha'?24:2.5)));

  let no = camNo.selectAll('g'), link = camLink.selectAll('line'), rot = camRot.selectAll('text'), hull = camHull.selectAll('path'), hullRot = camHull.selectAll('text');
  let rotulos = 'controle';
  const visRot = n => n.tipo==='bolha' || n.tipo==='serie' || n.tipo==='doc' ? false : rotulos==='todos' || (rotulos==='controle' && n.tipo!=='emissor') || (n.tipo==='emissor' && abertosE.has(n.id));
  const pos = new Map();

  function desenhar(){
    hull.attr('d', k => { const pts = sim.nodes().filter(n=>n.grupo===k && n.tipo!=='bolha').flatMap(n => { const r=raio(n)+12; return [[n.x-r,n.y],[n.x+r,n.y],[n.x,n.y-r],[n.x,n.y+r]]; }); const h = d3.polygonHull(pts); return h ? 'M'+h.join('L')+'Z' : null; });
    hullRot.each(function(k){ const ns = sim.nodes().filter(n=>n.grupo===k && n.tipo!=='bolha'); if (!ns.length) return; d3.select(this).attr('x', d3.mean(ns,n=>n.x)).attr('y', d3.min(ns,n=>n.y)-16); });
    link.attr('x1',l=>l.source.x).attr('y1',l=>l.source.y).attr('x2',l=>l.target.x).attr('y2',l=>l.target.y);
    no.attr('transform', n => `translate(${n.x},${n.y})`);
    rot.attr('x', n => n.x).attr('y', n => n.y);
  }

  function atualizar(origem){
    const {nos, links} = visiveis();
    posicionarAncoras(nos);
    nos.forEach(n => { if (n.x==null || !pos.has(n.id)) { const p = pos.get(origem) || {x:alvo(n)[0], y:alvo(n)[1]};
      n.x = p.x + (Math.random()-.5)*24; n.y = p.y + (Math.random()-.5)*24; } });
    sim.nodes(nos); sim.force('link').links(links);
    sim.force('x').x(n => alvo(n)[0]); sim.force('y').y(n => alvo(n)[1]);

    const abertos = [...abertosG];
    hull = camHull.selectAll('path').data(abertos, k=>k).join('path').attr('fill', k => tinta(segDe(k), 9)).attr('stroke', k => tinta(segDe(k), 70)).attr('stroke-width',1.4).attr('stroke-linejoin','round')
      .attr('stroke-dasharray', k => k.endsWith(ISOL)?'3 3':null).style('cursor','pointer').on('click', (e,k) => { e.stopPropagation(); fecharGrupo(k); });
    hullRot = camHull.selectAll('text').data(abertos, k=>k).join('text').text(k => (nomeGrupo(k)+' · '+nomeSeg(segDe(k))).toUpperCase()+'  ×')
      .attr('font-size',10.5*FS).attr('font-weight',700).attr('letter-spacing','.06em').attr('fill','var(--ink-2)').attr('text-anchor','middle').style('cursor','pointer')
      .on('click', (e,k) => { e.stopPropagation(); fecharGrupo(k); });

    link = camLink.selectAll('line').data(links, l => (l.source.id||l.source)+'|'+(l.target.id||l.target)).join('line')
      .attr('stroke', l => l.tipo==='cross'?'var(--div-pos-2)':'var(--edge)')
      .attr('stroke-width', l => l.tipo==='ponte'?1.8 : l.tipo==='emitiu'?.8 : 1.3)
      .attr('stroke-dasharray', l => l.tipo==='inferido'?'4 3' : l.tipo==='garante'?'1 2.5' : l.tipo==='escritura'?'8 2 2 2' : l.tipo==='ponte'?'2 4' : null);

    no = camNo.selectAll('g.no').data(nos, n=>n.id).join(enter => {
      const ge = enter.append('g').attr('class','no').style('cursor','pointer');
      const b = ge.filter(n=>n.tipo==='bolha');
      b.append('circle').attr('r', 0).attr('fill', n => tinta(n.segmento, n.nivel==='segmento' ? 30 : 16))
        .attr('stroke', n => corM(n.segmento)).attr('stroke-width', n => n.nivel==='segmento' ? 2 : 1.4)
        .transition().duration(350).attr('r', n => raio(n));
      b.append('text').attr('text-anchor','middle').attr('dy', n => raio(n)+15*FS).attr('font-size', n => (n.nivel==='segmento'?12:10.5)*FS).attr('font-weight',600).attr('fill','var(--ink)').text(n=>n.rotulo);
      b.append('text').attr('text-anchor','middle').attr('dy', n => raio(n)+28*FS).attr('font-size',9.5*FS).attr('fill','var(--ink-3)')
        .text(n => { const r = resumo[n.id]; return n.nivel==='segmento' ? r.grupos+' grupos · '+r.series+' séries' : r.emissores+' emissores · '+r.series+' séries'; });
      ge.filter(n=>n.tipo==='controlador'||n.tipo==='grupo').append('rect').attr('x',n=>-raio(n)).attr('y',n=>-raio(n)).attr('width',n=>2*raio(n)).attr('height',n=>2*raio(n)).attr('rx',2)
        .attr('fill', n => n.tipo==='grupo'?'var(--surface)':'var(--ink-2)').attr('stroke','var(--ink-2)').attr('stroke-width',1.2).attr('stroke-dasharray', n=>n.tipo==='grupo'?'2 2':null);
      ge.filter(n=>n.tipo==='garantidor').append('path').attr('d', d3.symbol(d3.symbolDiamond, 90)()).attr('fill','var(--ink-2)');
      ge.filter(n=>n.tipo==='emissor').append('circle').attr('r',raio).attr('fill', n => tinta(n.segmento, 25)).attr('stroke', n => corM(n.segmento)).attr('stroke-width',2);
      ge.filter(n=>n.tipo==='emissor').append('text').attr('class','mais').attr('text-anchor','middle').attr('dy',3).attr('font-size',8).attr('font-weight',700).attr('fill','var(--ink)').text('+');
      ge.filter(n=>n.tipo==='doc').append('path').attr('d', n => d3.symbol(formaDoc(n.categoria), n.categoria==='analise'?70:58)()).attr('fill', n => corDoc(n.categoria))
        .attr('stroke', n => n.status_jev==='automatico' && n.impacto==='negativo' ? 'var(--div-pos-2)' : n.status_jev==='automatico' && n.impacto==='positivo' ? 'var(--div-neg-2)' : 'var(--surface)')
        .attr('stroke-width', n => n.status_jev==='automatico' && n.impacto!=='neutro' ? 2.2 : 1);
      ge.filter(n=>n.tipo==='serie').append('circle').attr('class','pt').attr('r',0).attr('fill', n => corDesvio(n.dp)).attr('stroke','var(--surface)').attr('stroke-width',1.2).transition().duration(300).attr('r', raio);
      return ge;
    });
    no.select('text.mais').text(n => abertosE.has(n.id) ? '−' : '+');
    rot = camRot.selectAll('text').data(nos.filter(n => n.tipo!=='bolha' && n.tipo!=='serie' && n.tipo!=='doc'), n=>n.id).join('text')
      .text(n => n.rotulo.length>30 ? n.rotulo.slice(0,29)+'…' : n.rotulo).attr('font-size',8.5*FS).attr('fill','var(--ink-2)')
      .attr('dx', n=>raio(n)+3).attr('dy',3).style('pointer-events','none').attr('paint-order','stroke').attr('stroke','var(--surface)').attr('stroke-width',3);
    aplicarRot(); ligarEventos(); sim.alpha(1).restart();
    precisaEnquadrar = true; clearTimeout(enquadrar.t); enquadrar.t = setTimeout(enquadrar, 2500);
  }
  const aplicarRot = () => rot.attr('display', n => visRot(n)?null:'none');
  let precisaEnquadrar = false;
  sim.on('tick', () => { sim.nodes().forEach(n => pos.set(n.id, {x:n.x, y:n.y})); desenhar(); if (precisaEnquadrar && sim.alpha() < .08) enquadrar(); });

  function enquadrar(){
    if (!precisaEnquadrar) return; precisaEnquadrar = false; clearTimeout(enquadrar.t);
    // com grupo aberto aproxima nas empresas; na visão geral encaixa todas as bolhas sem ampliar
    const aberto = abertosG.size > 0, foco = sim.nodes().filter(n => !aberto || n.tipo!=='bolha');
    if (!foco.length) { svg.transition().duration(600).call(zoom.transform, d3.zoomIdentity); return; }
    let x0, x1, y0, y1;
    if (aberto) { x0 = d3.min(foco,n=>n.x)-70; x1 = d3.max(foco,n=>n.x)+170; y0 = d3.min(foco,n=>n.y)-50; y1 = d3.max(foco,n=>n.y)+50; }
    else { x0 = d3.min(foco,n=>n.x-raio(n))-60*FS; x1 = d3.max(foco,n=>n.x+raio(n))+60*FS; y0 = d3.min(foco,n=>n.y-raio(n))-12; y1 = d3.max(foco,n=>n.y+raio(n))+36*FS; }
    const kk = .94*Math.min(W/(x1-x0), H/(y1-y0)), k = aberto ? Math.max(1, Math.min(2.2, kk)) : Math.min(1, kk);
    svg.transition().duration(700).call(zoom.transform, d3.zoomIdentity.translate(W/2 - k*(x0+x1)/2, H/2 - k*(y0+y1)/2).scale(k));
  }
  function recentrar(){ precisaEnquadrar = true; enquadrar(); }
  document.getElementById('mapaCentro').onclick = recentrar;
  function abrirSegmento(s){ abertosS.clear(); abertosS.add(s); [...abertosG].filter(k=>segDe(k)!==s).forEach(k=>abertosG.delete(k)); pos.clear(); atualizar(); trilha(); }
  function abrirGrupo(k){ if (!abertosS.has(segDe(k))) abrirSegmento(segDe(k)); abertosG.add(k); atualizar('G:'+k); trilha(); }
  function voltarGeral(){ abertosS.clear(); abertosG.clear(); abertosE.clear(); pos.clear(); atualizar(); trilha(); svg.transition().duration(400).call(zoom.transform, d3.zoomIdentity); }
  function trilha(){
    const el = document.getElementById('trilha'), s = [...abertosS][0], gs = [...abertosG];
    let h = '<a href="#" data-nav="geral">Todos os segmentos</a>';
    if (s) h += ' › <a href="#" data-nav="seg">'+nomeSeg(s)+'</a>';
    gs.forEach(k => h += ' › <span>'+nomeGrupo(k)+'</span>');
    el.innerHTML = h;
    el.querySelector('[data-nav="geral"]').onclick = e => { e.preventDefault(); voltarGeral(); };
    const a = el.querySelector('[data-nav="seg"]'); if (a) a.onclick = e => { e.preventDefault(); abertosG.clear(); abertosE.clear(); pos.clear(); atualizar(); trilha(); };
  }
  function fecharGrupo(k){ abertosG.delete(k); todos.filter(n=>n.grupo===k && n.tipo==='emissor').forEach(n=>abertosE.delete(n.id)); atualizar(); trilha(); }
  function fecharSegmento(s){ abertosS.delete(s); [...abertosG].filter(k=>segDe(k)===s).forEach(fecharGrupo); atualizar(); }
  function alternarEmissor(id){ abertosE.has(id) ? abertosE.delete(id) : abertosE.add(id); atualizar(id); }

  const viz = () => { const m = new Map(); sim.force('link').links().forEach(l => [[l.source.id,l.target.id],[l.target.id,l.source.id]].forEach(([a,b]) => { if(!m.has(a)) m.set(a,new Set()); m.get(a).add(b); })); return m; };
  function realcar(ids){ no.attr('opacity', n => !ids||ids.has(n.id)?1:.15); rot.attr('opacity', n => !ids||ids.has(n.id)?1:.15); link.attr('opacity', l => !ids||(ids.has(l.source.id)&&ids.has(l.target.id))?1:.08); }
  function ligarEventos(){
    no.on('mouseenter', (e,n) => { const v = viz(); realcar(new Set([n.id, ...(v.get(n.id)||[])]));
        if (n.tipo==='bolha') { const r = resumo[n.id]; mostrar(e, '<b>'+(n.nivel==='segmento'?nomeSeg(n.segmento):nomeGrupo(n.grupo)+' · '+nomeSeg(n.segmento))+'</b>'
          + (n.nivel==='segmento'?linha('Grupos', r.grupos):'') + linha('Emissores', r.emissores)+linha('Séries', r.series)+linha('Desvio mediano', r.mediana==null?'–':sinal(r.mediana)+' bps')
          + (n.nivel==='grupo' && !n.grupo.endsWith(ISOL) ? (() => { const outros = segmentos.filter(x => x!==n.segmento && gruposDe(x).includes(x+'|'+n.grupo.split('|')[1])).map(nomeSeg); return outros.length ? '<br><span class="fraco">também atua em: '+outros.join(', ')+'</span><br>' : ''; })() : '')
          + '<span class="fraco">clique para abrir'+(n.nivel==='segmento' && abertosS.has(n.segmento)?'':'')+'</span>'); }
        else if (n.tipo==='serie') mostrar(e, textoSerie(n));
        else if (n.tipo==='doc') mostrar(e, '<b>'+nomeDoc[n.subtipo]+'</b> <span class="fraco">'+(n.data||'')+' · '+n.fonte+'</span><br>'+n.rotulo
          + (n.evento ? linha('Evento (JEV)', n.evento.replace(/_/g,' ')) + linha('Impacto para o credor', n.impacto) + linha('Confiança', fmt(n.confianca,2) + (n.status_jev==='a_revisar'?' · a revisar':'')) : '')
          + '<br><span class="fraco">clique para abrir o original</span>');
        else mostrar(e, '<b>'+n.rotulo+'</b><br><span class="fraco">'+nomeGrupo(n.grupo)+' · '+nomeSeg(n.segmento)+'</span><br>'+(n.detalhe||'')+(n.tipo==='emissor'?'<br><span class="fraco">clique para '+(abertosE.has(n.id)?'recolher':'ver emissões e documentos')+'</span>':'')); })
      .on('mousemove', mover).on('mouseleave', () => { realcar(null); esconder(); })
      .on('click', (e,n) => { e.stopPropagation(); esconder();
        if (n.tipo==='bolha') n.nivel==='segmento' ? abrirSegmento(n.segmento) : abrirGrupo(n.grupo);
        else if (n.tipo==='emissor') { const abre = !abertosE.has(n.id); alternarEmissor(n.id); if (abre && window.abrirEmissor) window.abrirEmissor(n.cnpj, 'mapa'); }
        else if (n.tipo==='doc') { if (n.url) window.open(n.url, '_blank', 'noopener'); }
        else if (n.tipo==='serie') { abrirAtivo(n.rotulo, 'mapa'); } })
      .call(d3.drag().on('start',(e,d)=>{if(!e.active)sim.alphaTarget(.2).restart();d.fx=d.x;d.fy=d.y}).on('drag',(e,d)=>{d.fx=e.x;d.fy=e.y}).on('end',(e,d)=>{if(!e.active)sim.alphaTarget(0);d.fx=null;d.fy=null}));
  }


  // controles
  const selG = document.getElementById('filtroGrupo');
  const op = (v, t) => { const o = document.createElement('option'); o.value = v; o.textContent = t; selG.appendChild(o); };
  op('', 'Abrir segmento ou grupo…');
  segmentos.forEach(s => { op('S:'+s, nomeSeg(s)); gruposDe(s).filter(k => !k.endsWith(ISOL)).sort((a,b)=>resumo['G:'+b].series-resumo['G:'+a].series).forEach(k => op('G:'+k, '   '+nomeGrupo(k))); });
  selG.addEventListener('change', () => { const v = selG.value; if (!v) return; v.startsWith('S:') ? abrirSegmento(v.slice(2)) : abrirGrupo(v.slice(2)); });
  document.querySelectorAll('[data-rot]').forEach(b => b.addEventListener('click', () => { rotulos = b.dataset.rot; document.querySelectorAll('[data-rot]').forEach(x=>x.classList.toggle('ativo', x===b)); aplicarRot(); }));
  // seleção vinda de qualquer lugar: abre segmento, grupo e emissor da série e destaca o ponto
  function marcar(){ no.select('circle.pt').attr('stroke', n => n.rotulo===window.ativoSel ? 'var(--ink)' : 'var(--surface)').attr('stroke-width', n => n.rotulo===window.ativoSel ? 3 : 1.2)
    .attr('r', n => n.rotulo===window.ativoSel ? raio(n)+2.5 : raio(n)); }
  function focar(cod){
    const n = porId.get('s:'+cod); if (!n) return;
    const pai = paiSerie.get(n.id); let mudou = false;
    if (!abertosS.has(n.segmento)) { abertosS.clear(); abertosS.add(n.segmento); [...abertosG].filter(k=>segDe(k)!==n.segmento).forEach(k=>abertosG.delete(k)); pos.clear(); mudou = true; }
    if (!abertosG.has(n.grupo)) { abertosG.add(n.grupo); mudou = true; }
    if (pai && !abertosE.has(pai)) { abertosE.add(pai); mudou = true; }
    if (mudou) { atualizar(pai); trilha(); }
    marcar();
  }
  sim.on('end.marcar', marcar);
  window.mapa = { abrirGrupo, abrirSegmento, emissor: cnpj => porId.get('e:'+cnpj), focar, marcar, recentrar };
  atualizar(); trilha();
})();

// ---------- desvio em relação aos pares (barras divergentes) ----------
let classeAtual = 'IPCA+', modoDesvio = 'extremos';
function desenharDesvio(classe){
  classeAtual = classe;
  const svgEl = document.getElementById('desvio'), larg = svgEl.parentNode.clientWidth;
  if (!larg) return;  // aba escondida: redesenha ao abrir
  const segSel = document.getElementById('segDesvio').value;
  const dados = D.desvios.filter(d => d.classe===classe && d.desvio!=null && (!segSel || d.segmento===segSel)).sort((a,b)=>b.desvio-a.desvio);
  const total = dados.length;
  let linhas = dados.map((d,i) => ({...d, _i:i}));
  if (modoDesvio==='extremos' && total > 40) {
    linhas = linhas.filter(d => d._i < 20 || d._i >= total-20 || d.codigo===window.ativoSel);
    const comVao = []; linhas.forEach((d,j) => { if (j && d._i - linhas[j-1]._i > 1) comVao.push({vao:true, n: d._i - linhas[j-1]._i - 1}); comVao.push(d); });
    linhas = comVao;
  }
  document.getElementById('desvioInfo').textContent = total + ' séries' + (linhas.length < total ? ', mostrando os extremos' : '');
  const svg = d3.select(svgEl); svg.selectAll('*').remove();
  const W = Math.max(320, larg - 8), estreito = W < 640, lin = estreito ? 20 : 16, M = {t:24, r: estreito?46:70, b:8, l: estreito?82:150}, H = M.t + linhas.length*lin + M.b;
  svg.attr('viewBox', `0 0 ${W} ${H}`);
  const lim = Math.max(30, d3.max(dados, d => Math.abs(d.desvio)) || 30);
  const x = d3.scaleLinear().domain([-lim, lim]).range([M.l, W-M.r]).nice();
  x.ticks(estreito ? 4 : 6).forEach(t => { svg.append('line').attr('x1',x(t)).attr('x2',x(t)).attr('y1',M.t-6).attr('y2',H-M.b).attr('stroke','var(--line)').attr('stroke-width', t===0?1.2:1);
    svg.append('text').attr('x',x(t)).attr('y',M.t-10).attr('text-anchor','middle').attr('font-size',10).attr('fill','var(--ink-3)').text(sinal(t)); });
  const gr = svg.append('g').selectAll('g').data(linhas).join('g').attr('transform',(d,i)=>`translate(0,${M.t+i*lin})`);
  gr.filter(d => d.vao).append('text').attr('x', (M.l+W-M.r)/2).attr('y', lin/2+3.5).attr('text-anchor','middle').attr('font-size',10).attr('fill','var(--ink-3)').text(d => '⋯ '+d.n+' séries no meio ⋯');
  const gs = gr.filter(d => !d.vao);
  gs.append('rect').attr('class','barra').attr('x', d => Math.min(x(0), x(d.desvio))).attr('y', 2).attr('height', lin-4).attr('width', d => Math.max(1, Math.abs(x(d.desvio)-x(0)))).attr('rx', 2).attr('fill', d => corDesvio(d.dp))
    .attr('stroke', d => d.codigo===window.ativoSel ? 'var(--ink)' : 'none').attr('stroke-width', 2);
  gs.filter(d => d.codigo===window.ativoSel).append('text').attr('x', 2).attr('y', lin/2+3.5).attr('font-size',10).attr('font-weight',700).attr('fill','var(--ink)').text('▶');
  gs.append('text').attr('x', M.l-8).attr('y', lin/2+3.5).attr('text-anchor','end').attr('font-size',10.5).attr('font-weight', d => d.codigo===window.ativoSel ? 700 : 400).attr('fill','var(--ink)').text(d => d.codigo);
  if (!estreito) gs.append('text').attr('x', M.l-62).attr('y', lin/2+3.5).attr('text-anchor','end').attr('font-size',9.5).attr('fill','var(--ink-3)').text(d => d.grupo.startsWith('Isolada')?'isolada':d.grupo.split(' ')[0]);
  gs.append('text').attr('x', d => d.desvio>=0 ? x(d.desvio)+5 : x(d.desvio)-5).attr('y', lin/2+3.5).attr('text-anchor', d=>d.desvio>=0?'start':'end').attr('font-size',9.5).attr('fill','var(--ink-2)').text(d => sinal(d.desvio));
  gs.append('rect').attr('x',0).attr('width',W).attr('height',lin).attr('fill','transparent').style('cursor','pointer')
    .on('mouseenter', (e,d) => mostrar(e, '<b>'+d.codigo+'</b> · '+d.emissor+'<br><span class="fraco">'+d.grupo+'</span>' + linha(classe==='DI+'?'Spread sobre CDI':'Spread comparável', fmt(d.spread,0)+' bps') + linha(classe==='DI+'?'Mediana DI+':'Spread justo', fmt(d.justo,0)+' bps') + linha('Desvio', sinal(d.desvio)+' bps ('+sinal(d.dp,1)+' dp)') + linha('Variação no histórico', d.var_hist==null?'–':sinal(d.var_hist)+' bps ('+d.n_hist+' dias)') + '<br><span class="fraco">clique para abrir a ficha</span>'))
    .on('mousemove', mover).on('mouseleave', esconder).on('click', (e,d) => { esconder(); abrirAtivo(d.codigo); });
}
document.querySelectorAll('[data-ndesvio]').forEach(b => b.addEventListener('click', () => { modoDesvio = b.dataset.ndesvio; document.querySelectorAll('[data-ndesvio]').forEach(x=>x.classList.toggle('ativo', x===b)); desenharDesvio(classeAtual); }));
let _redim; addEventListener('resize', () => { clearTimeout(_redim); _redim = setTimeout(() => desenharDesvio(classeAtual), 150); });
document.querySelectorAll('[data-classe]').forEach(b => b.addEventListener('click', () => { document.querySelectorAll('[data-classe]').forEach(x=>x.classList.toggle('ativo', x===b)); desenharDesvio(b.dataset.classe); }));
(function(){ const sd = document.getElementById('segDesvio'), st = document.getElementById('segTabela');
  const segs = [...new Set(D.desvios.map(d => d.segmento))].sort((a,b) => D.desvios.filter(d=>d.segmento===b).length - D.desvios.filter(d=>d.segmento===a).length);
  [sd, st].forEach(sel => { const o = document.createElement('option'); o.value=''; o.textContent='Todos os segmentos'; sel.appendChild(o);
    segs.forEach(x => { const o = document.createElement('option'); o.value = x; o.textContent = D.segmentos[x] || x; sel.appendChild(o); }); });
  sd.addEventListener('change', () => desenharDesvio(classeAtual));
})();

// ---------- simulador ----------
const sel = document.getElementById('serie'), choque = document.getElementById('choque');
D.series.forEach(s => { const o=document.createElement('option'); o.value=s.codigo; o.textContent=s.codigo+' · '+s.emissor+(s.classe==='DI+'?' (DI+)':''); sel.appendChild(o); });
const preco = (f, y) => f.t.reduce((p,t,i) => p + f.cf[i]/Math.pow(1+y, t), 0);
const txtTaxa = (s, v) => v==null ? '' : (s.classe==='DI+' ? 'DI + ' : 'IPCA + ')+fmt(v,2)+'%';
function calcular(){
  const s = D.series.find(x => x.codigo===sel.value); if(!s) return;
  const f = D.fluxos[s.codigo], bps = parseFloat(choque.value)||0, ds = bps/1e4;
  const soDur = -s.dmod*ds*100, conv = s.convex ? .5*s.convex*ds*ds*100 : null;
  const aprox = soDur + (conv||0);
  const cheio = f ? (preco(f, f.y+ds)/preco(f, f.y)-1)*100 : null;
  const v = cheio!=null ? cheio : aprox;
  const $ = id => document.getElementById(id);
  $('r_pu').textContent = s.pu ? 'R$ '+fmt(s.pu,2) : '–';
  $('r_taxa').textContent = s.taxa!=null ? 'a '+txtTaxa(s, s.taxa) : '';
  $('r_pu_novo').textContent = s.pu ? 'R$ '+fmt(s.pu*(1+v/100),2) : '–';
  $('r_taxa_nova').textContent = s.taxa!=null ? 'a '+txtTaxa(s, s.taxa+bps/100) : '';
  $('r_var').textContent = cheio!=null ? sinal(cheio,2)+'%' : 'sem fluxo validado';
  $('r_var_rs').textContent = s.pu ? (v<0?'− ':'+ ')+'R$ '+fmt(Math.abs(s.pu*v/100),2)+' por título'+(cheio==null?' (pela aproximação)':'') : '';
  $('r_so_dur').textContent = sinal(soDur,2)+'%';
  $('r_conv').textContent = conv==null ? '–' : sinal(conv,2)+'%';
  $('r_conv_info').textContent = s.convex ? 'convexidade '+fmt(s.convex,1)+'; sempre a favor do investidor' : '';
  $('r_aprox').textContent = sinal(aprox,2)+'%';
  $('r_resid').textContent = cheio!=null ? 'diferença para o fluxo: '+fmt(Math.abs(cheio-aprox)*100,1)+' bps de preço' : '';
  // modificada = Macaulay / (1 + taxa): lê-se como % do preço por 1 ponto (100 bps) de taxa
  $('r_dur').textContent = fmt(s.dmod,2);
  $('r_dur_info').textContent = '≈ '+fmt(s.dmod,2)+'% do preço a cada 100 bps' + (s.taxa!=null ? ' · Macaulay '+fmt(s.dmod*(1+s.taxa/100),2)+' anos' : '');
  $('r_z').textContent = s.classe==='DI+' ? fmt(s.spread,0)+' bps sobre o CDI' : fmt(s.z,0)+' bps (Z de mercado)';
  $('r_z_info').textContent = s.classe==='DI+' ? '' : 'comparável '+fmt(s.spread,0)+' bps'+(s.isenta==='S'?' com gross-up de 15% (isenta)':'');
  document.getElementById('r_desvio').textContent = s.desvio==null?'–':sinal(s.desvio)+' bps ('+sinal(s.dp,1)+' dp)';
  document.getElementById('r_be12').textContent = s.be12==null?'–':fmt(s.be12,1)+' bps';
}
// régua e curva preço x choque: os três controles (régua, ponto arrastável, campo) ficam sincronizados
const regua = document.getElementById('regua'), reguaValor = document.getElementById('regua_valor');
const variacao = (s, bps) => { const f = D.fluxos[s.codigo], ds = bps/1e4;
  return f ? (preco(f, f.y+ds)/preco(f, f.y)-1)*100 : (-s.dmod*ds + (s.convex? .5*s.convex*ds*ds : 0))*100; };
function definir(bps, origem){
  bps = Math.max(-300, Math.min(300, Math.round(bps/5)*5));
  if (origem!=='campo') choque.value = bps; if (origem!=='regua') regua.value = bps;
  reguaValor.textContent = (bps>0?'+':'')+bps+' bps'; calcular(); desenharCurva();
}
function desenharCurva(){
  const s = D.series.find(x => x.codigo===sel.value); if(!s) return;
  const svg = d3.select('#curva'); svg.selectAll('*').remove();
  const W = 440, H = 210, M = {t:14, r:12, b:22, l:58}; svg.attr('viewBox', `0 0 ${W} ${H}`);
  const pu0 = s.pu || 100, puDe = v => pu0*(1+v/100);
  const pts = d3.range(-300, 301, 10).map(b => [b, puDe(variacao(s, b))]);
  const reta = [[-300, puDe(s.dmod*3)], [300, puDe(-s.dmod*3)]];
  const x = d3.scaleLinear().domain([-300, 300]).range([M.l, W-M.r]);
  const y = d3.scaleLinear().domain(d3.extent([...pts, ...reta], p=>p[1])).nice().range([H-M.b, M.t]);
  y.ticks(4).forEach(t => { svg.append('line').attr('x1',M.l).attr('x2',W-M.r).attr('y1',y(t)).attr('y2',y(t)).attr('stroke','var(--line)');
    svg.append('text').attr('x',M.l-6).attr('y',y(t)+3).attr('text-anchor','end').attr('font-size',9.5).attr('fill','var(--ink-3)').text('R$ '+fmt(t,0)); });
  svg.append('path').attr('d', d3.line().x(p=>x(p[0])).y(p=>y(p[1]))(reta)).attr('fill','none').attr('stroke','var(--ink-3)').attr('stroke-width',1.2).attr('stroke-dasharray','4 3');
  svg.append('text').attr('x', W-M.r).attr('y', y(reta[1][1])+12).attr('text-anchor','end').attr('font-size',9).attr('fill','var(--ink-3)').text('só duration');
  [-300,-150,0,150,300].forEach(t => svg.append('text').attr('x',x(t)).attr('y',H-6).attr('text-anchor','middle').attr('font-size',9.5).attr('fill','var(--ink-3)').text((t>0?'+':'')+t));
  svg.append('line').attr('x1',x(0)).attr('x2',x(0)).attr('y1',M.t).attr('y2',H-M.b).attr('stroke','var(--line-2)');
  svg.append('path').attr('d', d3.line().x(p=>x(p[0])).y(p=>y(p[1]))(pts)).attr('fill','none').attr('stroke','var(--ink)').attr('stroke-width',2);
  const b = +choque.value || 0, vp = variacao(s, b), v = puDe(vp);
  svg.append('line').attr('x1',x(b)).attr('x2',x(b)).attr('y1',y(v)).attr('y2',H-M.b).attr('stroke','var(--ink-3)').attr('stroke-dasharray','3 3');
  svg.append('line').attr('x1',M.l).attr('x2',x(b)).attr('y1',y(v)).attr('y2',y(v)).attr('stroke','var(--ink-3)').attr('stroke-dasharray','3 3');
  svg.append('circle').attr('cx',x(b)).attr('cy',y(v)).attr('r',7).attr('fill', b<0?'var(--div-neg-2)':b>0?'var(--div-pos-2)':'var(--div-0)').attr('stroke','var(--surface)').attr('stroke-width',2);
  svg.append('text').attr('x', x(b) + (b>150?-10:10)).attr('y', y(v)-10).attr('text-anchor', b>150?'end':'start').attr('font-size',11).attr('font-weight',600).attr('fill','var(--ink)').text('R$ '+fmt(v,2)+' ('+sinal(vp,2)+'%)');
  // arrastar em qualquer ponto do gráfico move o choque
  svg.append('rect').attr('x',M.l).attr('y',0).attr('width',W-M.l-M.r).attr('height',H).attr('fill','transparent').style('cursor','ew-resize')
    .call(d3.drag().on('start drag', e => definir(x.invert(e.x), 'curva')))
    .on('click', e => definir(x.invert(d3.pointer(e)[0]), 'curva'));
}
function selecionar(c){ if (![...sel.options].some(o => o.value===c)) return false; sel.value=c; calcular(); desenharCurva(); return true; }
sel.addEventListener('change', () => { calcular(); desenharCurva(); if (window.abrirAtivo) abrirAtivo(sel.value, 'simulador'); });
document.getElementById('simFicha').onclick = () => abrirAtivo(sel.value);
regua.addEventListener('input', () => definir(+regua.value, 'regua'));
choque.addEventListener('input', () => definir(+choque.value || 0, 'campo'));
document.querySelectorAll('.botoes button').forEach(b => b.addEventListener('click', () => definir(+b.dataset.v, 'botao')));
if (sel.options.length) { sel.value = sel.options[0].value; definir(100, 'inicio'); }

// ---------- tabela: ordenar e abrir no simulador ----------
(function(){
  const tab = document.getElementById('tab'), linhas = [...tab.tBodies[0].rows];
  const fq = document.getElementById('fBusca'), fs = document.getElementById('segTabela'), fc = document.getElementById('fClasse'), ff = document.getElementById('fFaixa'), fx = document.getElementById('fFora'), info = document.getElementById('fInfo');
  const semA = t => String(t||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  function filtrar(){
    const q = semA(fq.value).trim(); let n = 0;
    linhas.forEach(tr => { const dp = tr.dataset.dp;
      const ok = (!fs.value || tr.dataset.segmento===fs.value) && (!fc.value || tr.dataset.cls===fc.value) && (!ff.value || tr.dataset.faixa===ff.value)
        && (!fx.checked || (dp!=='' && Math.abs(+dp) >= 1.5)) && (!q || semA(tr.dataset.busca).includes(q));
      tr.hidden = !ok; if (ok) n++; });
    info.textContent = n===linhas.length ? n+' séries' : n+' de '+linhas.length+' séries';
  }
  [fs, fc, ff, fx].forEach(e => e.addEventListener('change', filtrar)); fq.addEventListener('input', filtrar); filtrar();
  const bc = document.getElementById('fColunas');
  bc.onclick = () => { const on = tab.classList.toggle('mostrar-extra'); bc.textContent = on ? 'Menos colunas' : 'Mais colunas'; bc.setAttribute('aria-pressed', on); };
})();
document.querySelectorAll('#tab th').forEach((th, i) => th.addEventListener('click', () => {
  const corpo = document.querySelector('#tab tbody'), linhas = [...corpo.rows], asc = th.dataset.asc !== '1'; th.dataset.asc = asc?'1':'0';
  const val = r => { const t = r.cells[i].dataset.v ?? r.cells[i].textContent; const n = parseFloat(t); return isNaN(n) ? t : n; };
  linhas.sort((a,b) => { const x=val(a), y=val(b); return (x>y?1:x<y?-1:0)*(asc?1:-1); }).forEach(r => corpo.appendChild(r));
}));

// ---------- CRI e CRA (carregados sob demanda) ----------
let _cri = null;
window.carregarCri = () => _cri || (_cri = fetch('/grafo-credito/cri_cra.json', {cache:'no-cache'}).then(r => r.json()));
(function(){
  const sec = document.getElementById('crisec'); if (!sec) return;
  const fT = document.getElementById('criTipo'), fS = document.getElementById('criSit'), fL = document.getElementById('criLastro'), fQ = document.getElementById('criBusca'), corpo = document.getElementById('criCorpo'), info = document.getElementById('criInfo');
  let dados = [];
  const semA = t => String(t||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  function render(){
    const q = semA(fQ.value);
    const r = dados.filter(x => (!fT.value || x.t===fT.value) && (!fS.value || x.st===fS.value) && (!fL.value || x.lg===fL.value)
      && (!q || semA([x.c,x.i,x.s,x.lg,x.tl,x.dv.map(d=>(D.nomes_cnpj[d[0]]||d[0])).join(' ')].join(' ')).includes(q)));
    info.textContent = r.length+' séries/classes · '+r.filter(x=>x.st==='Em atraso').length+' em atraso';
    corpo.innerHTML = r.slice(0, 300).map(x => '<tr><td class="t">'+x.t+'</td><td class="t">'+x.c+'</td><td class="t">'+x.s+'</td><td class="t">'+x.cl+'</td><td class="t">'+(x.st==='Em atraso'?'<span class="selo hy">em atraso</span>':x.st)+'</td><td class="t">'+(x.r||'–')+'</td><td class="t">'+(x.v||'')+'</td><td class="t">'+(x.lg||'–')+'</td><td>'+(x.ltv==null?'–':fmt(x.ltv,0)+'%')+'</td><td>'+(x.in==null?'–':fmt(x.in,1)+'%')+'</td><td class="t">'+(x.rt||'–')+'</td><td class="t pequeno">'+x.dv.map(d => (D.nomes_cnpj[d[0]] ? '<b>'+D.nomes_cnpj[d[0]]+'</b>' : d[0])+' ('+d[1]+')').join('; ')+'</td></tr>').join('');
  }
  carregarCri().then(cc => { dados = cc;
    [...new Set(cc.map(x=>x.lg).filter(Boolean))].sort().forEach(v => { const o = document.createElement('option'); o.value=v; o.textContent=v; fL.appendChild(o); });
    [fT,fS,fL].forEach(e => e.onchange = render); fQ.oninput = render; render(); });
})();

// ---------- navegação: abas, ficha lateral, tema, atalhos e vistos recentemente ----------
const VISTAS = ['inicio','mapa','valor','ativos','simulador','cri','metodo'];
const ALIAS = {desvios:'valor', tabela:'ativos', crisec:'cri', busca:'inicio', ativo:'inicio'};
let vistaAtual = null;
function irPara(v, o={}){
  v = ALIAS[v] || v; if (!VISTAS.includes(v)) v = 'inicio';
  const mudou = v !== vistaAtual; vistaAtual = v;
  document.querySelectorAll('.vista').forEach(sec => sec.hidden = sec.id !== 'v-'+v);
  document.querySelectorAll('.abas a').forEach(a => a.setAttribute('aria-current', a.dataset.vista===v ? 'page' : 'false'));
  if (location.hash !== '#'+v) history[o.substituir ? 'replaceState' : 'pushState'](o.substituir ? history.state : null, '', location.pathname + location.search + '#' + v);
  if (v==='valor') desenharDesvio(classeAtual);
  if (mudou && !o.manterRolagem) window.scrollTo({top:0});
  const ab = document.querySelector('.abas a[data-vista="'+v+'"]'); if (ab && ab.scrollIntoView) ab.scrollIntoView({block:'nearest', inline:'nearest'});
}
window.irPara = irPara;
document.addEventListener('click', e => { const a = e.target.closest('[data-vista]'); if (!a) return; e.preventDefault(); irPara(a.dataset.vista); });

// ficha lateral: abre por cima em telas estreitas e encaixada ao lado a partir de 1280 px; Voltar do navegador fecha
const gav = document.getElementById('gaveta'), gavCab = document.getElementById('gavCab'), gavAbas = document.getElementById('gavAbas'), gavCorpo = document.getElementById('gavCorpo');
const preferida = {ativo:'resumo', emissor:'series'};
let gavFoco = null, gavEmpilhou = false;
const gavAberta = () => document.body.classList.contains('gaveta-aberta');
function definirParam(k, v, origem){
  const u = new URL(location.href), tinha = u.searchParams.has('ativo') || u.searchParams.has('emissor');
  u.searchParams.delete('ativo'); u.searchParams.delete('emissor'); u.searchParams.set(k, v);
  const url = u.pathname + u.search + u.hash;
  if (tinha || origem==='url') history.replaceState(history.state, '', url);
  else { history.pushState({gaveta:1}, '', url); gavEmpilhou = true; }
}
function abrirGaveta(tipo, cab, abas){
  if (!gavAberta()) gavFoco = document.activeElement;
  gavCab.innerHTML = cab;
  gavAbas.innerHTML = abas.map(a => '<button role="tab" data-aba="'+a.id+'">'+a.rotulo+'</button>').join('');
  gavCorpo.innerHTML = abas.map(a => '<div role="tabpanel" data-painel="'+a.id+'">'+a.html+'</div>').join('');
  const mostrarAba = id => { preferida[tipo] = id;
    gavAbas.querySelectorAll('button').forEach(b => b.setAttribute('aria-selected', b.dataset.aba===id));
    gavCorpo.querySelectorAll('[data-painel]').forEach(pn => pn.hidden = pn.dataset.painel!==id); gavCorpo.scrollTop = 0;
    const b = gavAbas.querySelector('[data-aba="'+id+'"]'); if (b) b.scrollIntoView({block:'nearest', inline:'nearest'}); };
  gavAbas.querySelectorAll('button').forEach(b => b.onclick = () => mostrarAba(b.dataset.aba));
  mostrarAba(abas.some(a => a.id===preferida[tipo]) ? preferida[tipo] : abas[0].id);
  gav.hidden = false; gav.setAttribute('aria-modal', innerWidth < 1280 ? 'true' : 'false');
  requestAnimationFrame(() => document.body.classList.add('gaveta-aberta'));
  document.getElementById('gavFechar').focus({preventScroll:true});
  return mostrarAba;
}
function fecharGaveta(viaHistorico){
  if (!gavAberta()) return;
  if (!viaHistorico && gavEmpilhou && history.state && history.state.gaveta) { gavEmpilhou = false; history.back(); return; }
  document.body.classList.remove('gaveta-aberta'); gavEmpilhou = false;
  setTimeout(() => { if (!gavAberta()) gav.hidden = true; }, 280);
  const u = new URL(location.href);
  if (u.searchParams.has('ativo') || u.searchParams.has('emissor')) { u.searchParams.delete('ativo'); u.searchParams.delete('emissor'); history.replaceState(null, '', u.pathname + u.search + u.hash); }
  if (gavFoco && gavFoco.focus && document.contains(gavFoco)) gavFoco.focus({preventScroll:true});
}
window.fecharGaveta = fecharGaveta;
document.getElementById('gavFechar').onclick = () => fecharGaveta();
document.getElementById('fundo').onclick = () => fecharGaveta();
function sincronizarUrl(){
  const q = new URLSearchParams(location.search);
  if (q.get('ativo') && D.ativos[q.get('ativo')]) abrirAtivo(q.get('ativo'), 'url');
  else if (q.get('emissor')) abrirEmissor(q.get('emissor'), 'url');
  else fecharGaveta(true);
}
addEventListener('popstate', () => { irPara(location.hash.slice(1), {substituir:true}); sincronizarUrl(); });
document.addEventListener('keydown', e => {
  const digitando = /INPUT|TEXTAREA|SELECT/.test((document.activeElement||{}).tagName||'');
  if (e.key==='Escape' && gavAberta() && !(digitando && document.activeElement.id==='busca' && document.getElementById('resultados').style.display==='block')) fecharGaveta();
  else if (e.key==='/' && !digitando) { e.preventDefault(); document.getElementById('busca').focus(); }
});

// tema claro ou escuro escolhido pela pessoa (o padrão segue o sistema)
document.getElementById('tema').onclick = () => {
  const r = document.documentElement, escuro = r.dataset.theme ? r.dataset.theme==='dark' : matchMedia('(prefers-color-scheme: dark)').matches;
  r.dataset.theme = escuro ? 'light' : 'dark'; try { localStorage.setItem('tema', r.dataset.theme); } catch(e) {}
};

// vistos recentemente: ponto de retorno na visão geral
const CHAVE_RECENTES = 'gc_recentes';
function lerRecentes(){ try { return JSON.parse(localStorage.getItem(CHAVE_RECENTES) || '[]').filter(c => D.ativos[c]); } catch(e) { return []; } }
function lembrar(cod){ try { localStorage.setItem(CHAVE_RECENTES, JSON.stringify([cod, ...lerRecentes().filter(c => c!==cod)].slice(0, 6))); } catch(e) {} mostrarRecentes(); }
function mostrarRecentes(){
  const r = lerRecentes(), box = document.getElementById('recentes'); if (!box) return;
  box.hidden = !r.length;
  document.getElementById('recentesLista').innerHTML = r.map(c => '<button class="chip" data-cod="'+c+'"><b>'+c+'</b> <span class="fraco">'+D.ativos[c].emissor.split(' ').slice(0,2).join(' ')+'</span></button>').join(' ');
  box.querySelectorAll('[data-cod]').forEach(b => b.onclick = () => abrirAtivo(b.dataset.cod));
}

// ---------- busca e ficha do ativo ----------
(function(){
  const sem = t => String(t||'').normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase();
  const A = D.ativos;
  // índice: séries, emissores e grupos, com texto normalizado para busca tolerante (código, nome, grupo, segmento, ISIN)
  const idx = [];
  Object.values(A).forEach(a => idx.push({tipo:'serie', chave:a.codigo, rotulo:a.codigo, sub:a.emissor+' · '+(D.segmentos[a.segmento]||a.segmento), texto:sem([a.codigo,a.isin,a.emissor,a.grupo,a.segmento,a.indexador].join(' '))}));
  const emis = {}; Object.values(A).forEach(a => { (emis[a.cnpj] = emis[a.cnpj] || {cnpj:a.cnpj, nome:a.emissor, grupo:a.grupo, segmento:a.segmento, n:0}).n++; });
  Object.values(emis).forEach(e => idx.push({tipo:'emissor', chave:e.cnpj, rotulo:e.nome, sub:e.n+' séries · '+e.grupo, texto:sem([e.nome,e.cnpj,e.grupo].join(' '))}));
  const grs = {}; Object.values(A).forEach(a => { const k = a.segmento+'|'+a.grupo; (grs[k] = grs[k] || {k, grupo:a.grupo, segmento:a.segmento, n:0}).n++; });
  Object.values(grs).filter(g => !g.grupo.startsWith('Isolada')).forEach(g => idx.push({tipo:'grupo', chave:g.k, rotulo:g.grupo, sub:(D.segmentos[g.segmento]||g.segmento)+' · '+g.n+' séries', texto:sem([g.grupo,g.segmento].join(' '))}));

  const caixa = document.getElementById('busca'), lista = document.getElementById('resultados');
  let atual = [], foco = -1;
  function buscar(q){
    const toks = sem(q).split(/\s+/).filter(Boolean); if (!toks.length) return [];
    const peso = {serie:0, emissor:1, grupo:2, cri:3};
    return idx.filter(i => toks.every(t => i.texto.includes(t)))
      .map(i => ({...i, s: (sem(i.rotulo).startsWith(toks[0]) ? 0 : 1)*10 + peso[i.tipo] + (sem(i.chave)===toks.join('') ? -20 : 0)}))
      .sort((a,b) => a.s-b.s || a.rotulo.localeCompare(b.rotulo)).slice(0, 12);
  }
  function mostrarLista(){
    lista.innerHTML = atual.map((r,i) => '<li class="'+(i===foco?'foco':'')+'" data-i="'+i+'"><span class="selo">'+({serie:'série',emissor:'emissor',grupo:'grupo',cri:'CRI/CRA'})[r.tipo]+'</span> <b>'+r.rotulo+'</b> <span class="fraco">'+r.sub+'</span></li>').join('');
    lista.style.display = atual.length ? 'block' : 'none';
    lista.querySelectorAll('li').forEach(li => li.onmousedown = e => { e.preventDefault(); escolher(atual[+li.dataset.i]); });
  }
  function escolher(r){
    lista.style.display = 'none'; caixa.value = ''; caixa.blur();
    if (r.tipo==='serie') abrirAtivo(r.chave);
    else if (r.tipo==='emissor') abrirEmissor(r.chave);
    else if (r.tipo==='cri') { irPara('cri'); const q = document.getElementById('criBusca'); q.value = r.chave; q.dispatchEvent(new Event('input')); }
    else { irPara('mapa'); window.mapa && window.mapa.abrirGrupo(r.chave); }
  }
  carregarCri().then(cc => cc.forEach(x => idx.push({tipo:'cri', chave:x.c, rotulo:x.c, sub:x.t+' · '+x.s+' · '+(x.lg||''), texto:sem([x.c,x.i,x.s,x.t,x.lg].join(' '))})));
  caixa.addEventListener('input', () => { atual = buscar(caixa.value); foco = -1; mostrarLista(); });
  caixa.addEventListener('keydown', e => {
    if (e.key==='ArrowDown') { foco = Math.min(foco+1, atual.length-1); mostrarLista(); e.preventDefault(); }
    else if (e.key==='ArrowUp') { foco = Math.max(foco-1, 0); mostrarLista(); e.preventDefault(); }
    else if (e.key==='Enter' && atual.length) { escolher(atual[Math.max(foco,0)]); }
    else if (e.key==='Escape') { lista.style.display='none'; }
  });
  caixa.addEventListener('blur', () => setTimeout(() => lista.style.display='none', 150));

  // ficha do ativo
  const fmtv = (v,c=0,suf='') => v==null||isNaN(v) ? '–' : fmt(v,c)+suf;
  const cel = (rot, val, nota) => '<div><small>'+rot+'</small><b>'+val+'</b>'+(nota?'<em>'+nota+'</em>':'')+'</div>';
  const dtBR = v => v ? v.slice(8,10)+'/'+v.slice(5,7)+'/'+v.slice(0,4) : '–';
  const esc = t => String(t ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');
  const nomeSegA = x => D.segmentos[x] || x;
  const liSerie = x => '<li tabindex="0" data-cod="'+x.codigo+'"><span><span class="marca" style="background:'+corDesvio(x.dp)+'"></span><b>'+x.codigo+'</b> <span class="fraco">'+esc(x.indexador||'')+' · vence '+dtBR(x.vencimento)+'</span></span><b>'+(x.desvio==null?'–':sinal(x.desvio)+' bps')+'</b></li>';
  function htmlDocs(docs){
    const selo = j => !j ? '' : ' <span class="selo" title="classificação JEV, confiança '+j.confianca+'">'+(j.impacto==='negativo'?'▼ ':j.impacto==='positivo'?'▲ ':'')+j.evento.replace(/_/g,' ')+(j.status==='a_revisar'?' · a revisar':'')+'</span>';
    const item = d => '<li><span>'+(d.data||'')+'</span><a href="'+esc(d.url)+'" target="_blank" rel="noopener">'+esc(d.titulo)+'</a> <span class="fraco">'+esc(d.fonte)+'</span>'+selo(d.jev)+'</li>';
    const bloco = (titulo, tipos) => { const it = docs.filter(d => tipos.includes(d.tipo)).map(item); return it.length ? '<div><h4>'+titulo+'</h4><ul>'+it.join('')+'</ul></div>' : ''; };
    return docs.length ? '<div class="ficha-grade">'+bloco('Fatos relevantes',['fato_relevante'])+bloco('Comunicados e avisos',['comunicado','aviso_debenturistas'])+bloco('Escrituras',['escritura'])+bloco('Notícias',['noticia'])+bloco('Análises',['analise'])+'</div>'
      : '<p class="fraco pequeno">Sem documentos públicos indexados ainda para este emissor.</p>';
  }
  function htmlFund(cnpj){
    const fu = D.fundamentos[cnpj]; if (!fu) return '<p class="fraco pequeno">Emissor sem demonstrações na CVM (não registrado ou sem DFP recente).</p>';
    const bi = v => v==null ? '–' : 'R$ '+fmt(v/1e9,2)+' bi';
    return '<p class="pequeno muted" style="margin:0">CVM, exercício '+fu.exercicio.slice(0,4)+'</p><div class="ativo-grade">'
      + cel('Dívida líquida / EBITDA', fu.dl_ebitda==null?'–':fmt(fu.dl_ebitda,2)+'x') + cel('EBITDA / despesa financeira', fu.cobertura_juros==null?'–':fmt(fu.cobertura_juros,2)+'x')
      + cel('Receita', bi(fu.receita)) + cel('EBITDA', bi(fu.ebitda)) + cel('Dívida líquida', bi(fu.divida_liquida)) + cel('Lucro líquido', bi(fu.lucro_liquido)) + '</div>';
  }
  function preencherCri(cnpj){
    carregarCri().then(cc => { const meus = cc.filter(x => x.dv.some(d => d[0]===cnpj)); const box = gavCorpo.querySelector('.criBox'); if (!box || !meus.length) return;
      box.innerHTML = '<h3>Exposição em CRI e CRA (devedor ou cedente)</h3><div class="tabela"><table><thead><tr><th class="t">Tipo</th><th class="t">Código</th><th class="t">Securitizadora</th><th class="t">Situação</th><th class="t">Remuneração</th><th class="t">Vencimento</th><th>Inadimplência</th></tr></thead><tbody>'
        + meus.map(x => '<tr><td class="t">'+x.t+'</td><td class="t">'+x.c+'</td><td class="t">'+x.s+'</td><td class="t">'+x.st+'</td><td class="t">'+(x.r||'–')+'</td><td class="t">'+(x.v||'')+'</td><td>'+(x.in==null?'–':fmt(x.in,1)+'%')+'</td></tr>').join('') + '</tbody></table></div>'; });
  }
  const ligarCods = () => gavCorpo.querySelectorAll('[data-cod]').forEach(el => { el.onclick = () => abrirAtivo(el.dataset.cod); el.onkeydown = e => { if (e.key==='Enter') abrirAtivo(el.dataset.cod); }; });
  const estreita = () => innerWidth < 1280;

  // a seleção de uma série vale para o site inteiro: simulador, tabela, desvios e mapa
  function sincronizar(cod, origem){
    const a = A[cod]; window.ativoSel = cod;
    if (origem !== 'simulador') selecionar(cod);
    document.querySelectorAll('#tab tbody tr').forEach(tr => tr.classList.toggle('sel', tr.dataset.codigo===cod));
    const cls = a.classe==='DI+' ? 'DI+' : 'IPCA+';
    if (cls !== classeAtual) document.querySelectorAll('[data-classe]').forEach(b => b.classList.toggle('ativo', b.dataset.classe===cls));
    desenharDesvio(cls);
    if (window.mapa) { if (origem !== 'mapa') window.mapa.focar(cod); else window.mapa.marcar(); }
  }

  window.abrirAtivo = function(cod, origem){
    const a = A[cod]; if (!a) return;
    sincronizar(cod, origem);
    if (origem === 'simulador') return;
    definirParam('ativo', cod, origem); lembrar(cod);
    const mesmos = Object.values(A).filter(x => x.segmento===a.segmento && x.classe===a.classe && x.spread!=null);
    const ord = mesmos.map(x=>x.spread).sort((x,y)=>x-y);
    const med = ord.length ? ord[Math.floor(ord.length/2)] : null;
    const pct = ord.length && a.spread!=null ? Math.round(100*ord.filter(v=>v<=a.spread).length/ord.length) : null;
    const pares = (a.pares||'').split(' ').filter(Boolean).map(c => A[c]).filter(Boolean);
    const rotSpread = a.classe==='DI+' ? 'Spread sobre o CDI' : 'Spread comparável (Z, gross-up 15% se isenta)';
    const docs = (D.docs[a.cnpj]||[]).slice(0, 8);
    const hist = a.hist || [];
    const P = a.ponta || {};
    const dt = v => v ? v.slice(8,10)+'/'+v.slice(5,7)+'/'+v.slice(0,4) : '–';
    const txt = v => { if (v==null) return '–'; const k = P.tipo || ''; return k==='IPCA_MAIS' ? 'IPCA + '+fmt(v,2)+'%' : k==='DI_MAIS' ? 'DI + '+fmt(v,2)+'%' : k==='PCT_DI' ? fmt(v,2)+'% do DI' : fmt(v,2)+'%'; };
    const anosAte = v => v ? (new Date(v) - new Date(P.data||Date.now()))/(365.25*864e5) : null;
    const mi = v => v==null ? '–' : v>=1e9 ? 'R$ '+fmt(v/1e9,2)+' bi' : 'R$ '+fmt(v/1e6,1)+' mi';
    const ultNeg = (P.negocios||[])[0];
    const tit = v => !v ? '–' : v.toLowerCase().replace(/(^|[\s(])([a-zà-ú])/g, (m,p1,p2) => p1+p2.toUpperCase()).replace(/(S\/A|S\.A\.?|Dtvm|Ltda\.?|Cv|Btg)/gi, m => m.toUpperCase());
    const amortTxt = !P.n_amort ? 'no vencimento (bullet)' : P.n_amort===1 ? 'parcela única em '+dt(P.amort[0][0]) : P.n_amort+' parcelas, a próxima em '+dt(P.amort[0][0])+(P.amort[0][1]!=null?' ('+fmt(P.amort[0][1],2)+'%)':'');
    const boleta = !P.data && !P.venc ? '' : '<div class="boleta">'
      + '<div class="linha"><b>'+a.codigo+'</b> '+(P.ind!=null?'a <b>'+txt(P.ind)+'</b> na indicativa ANBIMA de '+dt(P.data):'sem taxa indicativa ANBIMA')
      + (ultNeg ? ', último negócio em '+dt(ultNeg[0])+(ultNeg[5]!=null?' a ~<b>'+txt(ultNeg[5])+'</b>':'') : ', sem negócio registrado no SND')
      + '. Emitida a '+(P.texto_emissao||a.indexador||'–')+', vence em <b>'+dt(P.venc)+'</b>'+(anosAte(P.venc)!=null?' ('+fmt(anosAte(P.venc),1)+' anos)':'')
      + ', juros '+(P.juros_per ? P.juros_per.replace(/al$/,'ais') : '–')+(P.prox_juros?' (próximo em '+dt(P.prox_juros)+')':'')+', amortização '+amortTxt+'. '
      + (P.incentivada==='S'?'Incentivada (Lei 12.431, isenta para PF).':'Tributada.')+'</div>'
      + '<div class="kpis">'
      + '<div class="kpi"><div class="r">Indicativa ANBIMA</div><div class="v">'+txt(P.ind)+'</div><div class="s">'+(P.int_min!=null?'intervalo '+fmt(P.int_min,2)+' a '+fmt(P.int_max,2):'')+'</div></div>'
      + '<div class="kpi"><div class="r">Compra / venda ANBIMA</div><div class="v">'+(P.compra!=null?fmt(P.compra,2)+' / '+fmt(P.venda,2):'–')+'</div><div class="s">média das taxas informadas</div></div>'
      + '<div class="kpi"><div class="r">Último negócio (SND)</div><div class="v">'+(ultNeg&&ultNeg[5]!=null?'~'+txt(ultNeg[5]):ultNeg?'R$ '+fmt(ultNeg[3],2):'–')+'</div><div class="s">'+(ultNeg?dt(ultNeg[0])+' · '+ultNeg[2]+' negócios · '+fmt(ultNeg[1],0)+' títulos':'')+'</div></div>'
      + '<div class="kpi"><div class="r">PU indicativo</div><div class="v">'+(a.pu==null?'–':'R$ '+fmt(a.pu,2))+'</div><div class="s">'+(P.pct_par!=null?fmt(P.pct_par,2)+'% do PU par':'')+'</div></div>'
      + '<div class="kpi"><div class="r">Duration modificada</div><div class="v">'+fmtv(a.dmod,2)+'</div><div class="s">'+(a.dmod!=null?'≈ '+fmt(a.dmod,2)+'% do preço por 100 bps':'')+(P.dur!=null?' · Macaulay '+fmt(P.dur,2)+' anos':'')+(P.ntnb?' · NTN-B '+P.ntnb:'')+'</div></div>'
      + '<div class="kpi"><div class="r">Liquidez 180 dias</div><div class="v">'+(P.dias180||0)+' dias</div><div class="s">'+(P.vol180?'volume '+mi(P.vol180):'sem negócios')+'</div></div>'
      + '</div></div>';
    const carac = !P.venc ? '' : '<h3>Características</h3><div class="carac">'
      + [['Emissão / série', (P.emissao||'–')+'ª / '+(P.serie||'–')], ['Data de emissão', dt(P.dt_emissao)], ['Início da rentabilidade', dt(P.inicio_rent)], ['Vencimento', dt(P.venc)],
         ['Remuneração de emissão', P.texto_emissao||a.indexador||'–'], ['Pagamento de juros', (P.juros_per||'–')+(P.carencia_juros?', desde '+dt(P.carencia_juros):'')], ['Próximo juros', dt(P.prox_juros)],
         ['Amortização', amortTxt], ['Volume emitido', mi(P.volume_emitido)], ['Saldo em mercado (aprox.)', P.qtd_mercado&&a.pu?mi(P.qtd_mercado*a.pu):'–'],
         ['Valor nominal (emissão / atual)', P.vne?'R$ '+fmt(P.vne,2)+' / R$ '+fmt(P.vna,2):'–'], ['Garantia', a.garantia||'–'], ['Lei 12.431', P.incentivada==='S'?'sim':'não'],
         ['Resgate antecipado', P.resgate==='S'?'previsto':P.resgate==='N'?'não previsto':'–'], ['Agente fiduciário', tit(P.fiduciario)], ['Coordenador líder', tit(P.coordenador)], ['ISIN', a.isin||'–']]
        .map(x => '<div><span>'+x[0]+'</span><span>'+x[1]+'</span></div>').join('') + '</div>';
    const negs = ((P.negocios||[]).length ? '<h3>Negócios recentes (SND)</h3><div class="tabela" style="max-height:260px"><table><thead><tr><th class="t">Data</th><th>Negócios</th><th>Títulos</th><th>PU médio (R$)</th><th>% do PU par</th><th>Taxa implícita aprox.</th></tr></thead><tbody>'
          + P.negocios.map(n => '<tr><td class="t">'+dt(n[0])+'</td><td>'+n[2]+'</td><td>'+fmt(n[1],0)+'</td><td>'+fmtv(n[3],2)+'</td><td>'+fmtv(n[4],2)+'</td><td>'+(n[5]==null?'–':txt(n[5]))+'</td></tr>').join('')
          + '</tbody></table></div><p class="fraco pequeno">Taxa implícita: aproximação pela duration a partir do % do PU par do negócio, ancorada na taxa ANBIMA do mesmo dia quando disponível, senão na taxa de emissão. Inferência, não taxa registrada.</p>' : '');
    const agenda = ((P.agenda||[]).length ? '<h3>Próximos eventos (agenda SND)</h3><div class="tabela" style="max-height:220px"><table><thead><tr><th class="t">Pagamento</th><th class="t">Evento</th><th>Taxa / percentual</th></tr></thead><tbody>'
          + P.agenda.map(e => '<tr><td class="t">'+dt(e[0])+'</td><td class="t">'+e[1]+'</td><td>'+(e[2]&&e[2]!=='-'?fmt(+e[2],4):'–')+'</td></tr>').join('') + '</tbody></table></div>' : '');
    const s = D.series.find(x => x.codigo===cod);
    const outras = Object.values(A).filter(x => x.cnpj===a.cnpj && x.codigo!==cod);
    const valor = '<div class="ativo-grade" style="margin-top:4px">'
      + cel(rotSpread, fmtv(a.spread,0,' bps'))
      + (a.classe==='IPCA+' ? cel('Z-spread de mercado', fmtv(a.z_mercado,0,' bps'), 'sem gross-up') + cel('Spread sobre a NTN-B', fmtv(a.spread_ntnb,0,' bps'), a.ntnb_ref ? 'NTN-B '+a.ntnb_ref : '') : '')
      + cel('Justo pelos pares', fmtv(a.justo_pares,0,' bps'), pares.length+' pares')
      + cel('Ajuste por eventos', a.ajuste ? (a.ajuste>0?'+':'')+fmt(a.ajuste,1)+' bps' : '–')
      + cel('Desvio em relação aos pares', a.desvio==null?'–':sinal(a.desvio)+' bps', a.dp==null?'':sinal(a.dp,1)+' dp')
      + cel('Mediana do segmento', fmtv(med,0,' bps'), pct==null?'':'esta série está no percentil '+pct)
      + cel('Justo pela regressão', fmtv(a.justo_reg,0,' bps'))
      + '</div>'
      + (hist.length > 1 ? '<h3>Histórico do spread</h3><svg id="ativoHist" style="width:100%;height:auto;aspect-ratio:4/1"></svg>' : '')
      + '<h3>Pares comparáveis</h3>'
      + (pares.length ? '<ol class="lista-clicavel">'+pares.map(liSerie).join('')+'</ol><p class="fraco pequeno">Mesmo segmento, classe e faixa; à direita, o desvio de cada par. Clique para abrir.</p>' : '<p class="fraco pequeno">Sem pares suficientes no mesmo segmento, classe e faixa.</p>')
      + (a.motivos ? '<h3>Eventos que ajustam o justo</h3><p class="pequeno muted">'+a.motivos.split(' | ').join('<br>')+'</p>' : '');
    const mini = !s ? '<p class="fraco pequeno">Série sem preço validado; simulação indisponível.</p>'
      : '<div class="mini-sim"><label for="msR">Choque no spread: <b id="msV"></b></label><input id="msR" type="range" min="-300" max="300" step="5" value="'+(+choque.value||100)+'" aria-label="Choque no spread em bps"><div class="regua-marcas"><span>−300</span><span>0</span><span>+300</span></div>'
        + '<div class="ativo-grade" id="msRes"></div>'
        + '<h3>Choques padrão</h3><div class="tabela"><table><thead><tr><th class="t">Choque</th><th>PU (R$)</th><th>Variação</th><th>R$ por título</th></tr></thead><tbody>'
        + [-200,-100,-50,50,100,200].map(b => { const vp = variacao(s,b); return '<tr><td class="t">'+(b>0?'+':'')+b+' bps</td><td>'+fmt(s.pu*(1+vp/100),2)+'</td><td>'+sinal(vp,2)+'%</td><td>'+sinal(s.pu*vp/100,2)+'</td></tr>'; }).join('')
        + '</tbody></table></div><p class="fraco pequeno">Fluxo remanescente reprecificado com a taxa indicativa mais o choque. Duration modificada '+fmt(s.dmod,2)+' (≈ '+fmt(s.dmod,2)+'% do preço por 100 bps)'+(s.convex?', convexidade '+fmt(s.convex,1):'')+'.</p></div>';
    const passos = '<div class="passos"><h3>Próximos passos</h3><ol class="lista-clicavel">'
      + (s ? '<li tabindex="0" data-passo="simular"><span>Simular abertura ou fechamento do spread</span><span>→</span></li>' : '')
      + (pares.length ? '<li tabindex="0" data-passo="par"><span>Comparar com o par mais próximo: '+pares[0].codigo+' ('+esc(pares[0].emissor)+')</span><span>→</span></li>' : '')
      + '<li tabindex="0" data-passo="emissor"><span>Ver o emissor: '+(outras.length ? outras.length+' outras séries, ' : '')+'documentos e fundamentos</span><span>→</span></li>'
      + '<li tabindex="0" data-passo="segmento"><span>Comparar com o segmento '+esc(nomeSegA(a.segmento))+' em Valor relativo</span><span>→</span></li>'
      + '<li tabindex="0" data-passo="mapa"><span>Ver no mapa, dentro do grupo de risco</span><span>→</span></li>'
      + '</ol></div>';
    const emissorHtml = '<h3>'+esc(a.emissor)+'</h3>'+htmlFund(a.cnpj)+'<div class="criBox"></div>'
      + (a.clausulas ? '<h3>Escritura</h3><p class="pequeno muted">'+a.clausulas+'</p>' : '')
      + (outras.length ? '<h3>Outras séries do emissor</h3><ol class="lista-clicavel">'+outras.map(liSerie).join('')+'</ol>' : '')
      + '<h3>Documentos do emissor</h3>'+htmlDocs(D.docs[a.cnpj]||[]);
    const cab = '<div class="kicker">'+esc(nomeSegA(a.segmento))+' · '+esc(a.grupo)+'</div>'
      + '<h2 id="gavTitulo">'+a.codigo+(a.faixa==='high_yield'?' <span class="selo hy">high yield</span>':'')+'<small>'+esc(a.emissor)+'</small></h2>'
      + '<p class="linha-info">'+[a.indexador, 'vence '+dtBR(a.vencimento), a.isenta==='S'?'incentivada (isenta)':'tributada', 'garantia '+(a.garantia||'–')].filter(Boolean).join(' · ')+(a.motivo_faixa?'<br>'+esc(a.motivo_faixa):'')+'</p>'
      + '<div class="gav-acoes">'+(s?'<button data-acao="sim">Simular no painel</button>':'')+'<button data-acao="mapa">Ver no mapa</button><button data-acao="link">Copiar link</button></div>';
    const mostrarAba = abrirGaveta('ativo', cab, [
      {id:'resumo', rotulo:'Resumo', html: (boleta || '<p class="fraco pequeno">Sem dados de mercado para esta série.</p>') + carac + passos},
      {id:'valor', rotulo:'Valor relativo', html: valor + passos},
      {id:'simular', rotulo:'Simulação', html: mini + passos},
      {id:'mercado', rotulo:'Negócios e agenda', html: (negs + agenda) || '<p class="fraco pequeno">Sem negócios nem eventos futuros registrados no SND.</p>'},
      {id:'emissor', rotulo:'Emissor', html: emissorHtml}]);
    ligarCods(); preencherCri(a.cnpj);
    const acoes = {
      simular: () => mostrarAba('simular'),
      par: () => abrirAtivo(pares[0].codigo),
      emissor: () => mostrarAba('emissor'),
      segmento: () => { const sd = document.getElementById('segDesvio'); if ([...sd.options].some(o => o.value===a.segmento)) sd.value = a.segmento; if (estreita()) fecharGaveta(); irPara('valor'); },
      mapa: () => { if (estreita()) fecharGaveta(); irPara('mapa'); window.mapa && window.mapa.focar(cod); },
      sim: () => { if (estreita()) fecharGaveta(); irPara('simulador'); selecionar(cod); },
      link: b => { if (navigator.clipboard) navigator.clipboard.writeText(location.href).then(() => { b.textContent = 'Link copiado'; setTimeout(() => b.textContent = 'Copiar link', 1600); }); }
    };
    gavCorpo.querySelectorAll('[data-passo]').forEach(li => { const f = () => acoes[li.dataset.passo](li); li.onclick = f; li.onkeydown = e => { if (e.key==='Enter') f(); }; });
    gavCab.querySelectorAll('[data-acao]').forEach(b => b.onclick = () => acoes[b.dataset.acao](b));
    if (s) { const r = document.getElementById('msR'), v = document.getElementById('msV'), res = document.getElementById('msRes');
      const upd = () => { const b = +r.value, vp = variacao(s, b); v.textContent = (b>0?'+':'')+b+' bps';
        res.innerHTML = cel('PU hoje', 'R$ '+fmt(s.pu,2), 'a '+txtTaxa(s, s.taxa)) + cel('PU após o choque', 'R$ '+fmt(s.pu*(1+vp/100),2), 'a '+txtTaxa(s, s.taxa+b/100))
          + cel('Variação do preço', sinal(vp,2)+'%', (vp<0?'− ':'+ ')+'R$ '+fmt(Math.abs(s.pu*vp/100),2)+' por título') + cel('Só duration', sinal(-s.dmod*b/100,2)+'%', 'a diferença é a convexidade'); };
      r.oninput = upd; upd(); }
    if (hist.length > 1) {
      const sv = d3.select('#ativoHist'), W = 480, H = 120, M = {t:10,r:14,b:22,l:40}; sv.attr('viewBox', `0 0 ${W} ${H}`);
      const x = d3.scalePoint().domain(hist.map(h=>h[0])).range([M.l, W-M.r]), y = d3.scaleLinear().domain(d3.extent(hist, h=>h[1])).nice().range([H-M.b, M.t]);
      y.ticks(3).forEach(t => { sv.append('line').attr('x1',M.l).attr('x2',W-M.r).attr('y1',y(t)).attr('y2',y(t)).attr('stroke','var(--line)'); sv.append('text').attr('x',M.l-6).attr('y',y(t)+3).attr('text-anchor','end').attr('font-size',10).attr('fill','var(--ink-3)').text(fmt(t,0)); });
      const passo = Math.ceil(hist.length/6);
      hist.forEach((h,i) => { if (i % passo === 0 || i===hist.length-1) sv.append('text').attr('x',x(h[0])).attr('y',H-6).attr('text-anchor','middle').attr('font-size',10).attr('fill','var(--ink-3)').text(h[0].slice(8,10)+'/'+h[0].slice(5,7)); });
      sv.append('path').attr('d', d3.line().x(h=>x(h[0])).y(h=>y(h[1]))(hist)).attr('fill','none').attr('stroke','var(--ink)').attr('stroke-width',2);
      sv.selectAll('circle').data(hist).join('circle').attr('cx',h=>x(h[0])).attr('cy',h=>y(h[1])).attr('r',3.5).attr('fill','var(--ink)')
        .on('mouseenter',(e,h)=>mostrar(e,'<b>'+dtBR(h[0])+'</b>'+linha('Spread',fmt(h[1],0)+' bps'))).on('mousemove',mover).on('mouseleave',esconder);
    }
  };

  window.abrirEmissor = function(cnpj, origem){
    const minhas = Object.values(A).filter(a => a.cnpj===cnpj); if (!minhas.length) return;
    const e0 = minhas[0], n = window.mapa && window.mapa.emissor(cnpj);
    if (origem !== 'mapa' && origem !== 'url' && n) window.mapa.abrirGrupo(n.grupo);
    definirParam('emissor', cnpj, origem);
    const cab = '<div class="kicker">'+esc(nomeSegA(e0.segmento))+' · '+esc(e0.grupo)+'</div>'
      + '<h2 id="gavTitulo">'+esc(e0.emissor)+'<small>CNPJ '+cnpj.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/,'$1.$2.$3/$4-$5')+'</small></h2>'
      + (n && n.detalhe ? '<p class="linha-info">'+esc(n.detalhe)+'</p>' : '')
      + '<div class="gav-acoes"><button data-acao="mapa">Ver no mapa</button></div>';
    const ordem = [...minhas].sort((x,y) => (y.dp ?? -99) - (x.dp ?? -99));
    abrirGaveta('emissor', cab, [
      {id:'series', rotulo:'Emissões ('+minhas.length+')', html: '<p class="pequeno muted" style="margin-top:0">Ordenadas pelo desvio em relação aos pares. Clique numa série para abrir a ficha.</p><ol class="lista-clicavel">'+ordem.map(liSerie).join('')+'</ol>'},
      {id:'docs', rotulo:'Documentos', html: htmlDocs(D.docs[cnpj]||[])},
      {id:'fund', rotulo:'Fundamentos', html: htmlFund(cnpj)+'<div class="criBox"></div>'}]);
    ligarCods(); preencherCri(cnpj);
    gavCab.querySelector('[data-acao="mapa"]').onclick = () => { if (estreita()) fecharGaveta(); irPara('mapa'); if (n) window.mapa.abrirGrupo(n.grupo); };
  };
  // cliques nas linhas da tabela abrem a ficha
  document.querySelectorAll('tbody tr[data-codigo]').forEach(tr => tr.onclick = () => abrirAtivo(tr.dataset.codigo));
})();

// ---------- visão geral: maiores desvios (faixa principal) ----------
(function(){
  const base = D.desvios.filter(d => d.dp!=null && (D.ativos[d.codigo]||{}).faixa!=='high_yield');
  const li = d => '<li tabindex="0" data-cod="'+d.codigo+'"><span><span class="marca" style="background:'+corDesvio(d.dp)+'"></span><b>'+d.codigo+'</b> <span class="fraco">'+d.emissor+' · '+d.classe+'</span></span><b>'+sinal(d.desvio)+' bps · '+sinal(d.dp,1)+' dp</b></li>';
  document.getElementById('rkAcima').innerHTML = [...base].sort((a,b) => b.dp-a.dp).slice(0,6).map(li).join('');
  document.getElementById('rkAbaixo').innerHTML = [...base].sort((a,b) => a.dp-b.dp).slice(0,6).map(li).join('');
  document.querySelectorAll('#rkAcima, #rkAbaixo').forEach(ol => { ol.className = 'lista-clicavel'; ol.querySelectorAll('li').forEach(x => { x.onclick = () => abrirAtivo(x.dataset.cod); x.onkeydown = e => { if (e.key==='Enter') abrirAtivo(x.dataset.cod); }; }); });
})();
mostrarRecentes();
irPara(location.hash.slice(1) || 'inicio', {substituir:true});
sincronizarUrl();
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
    pasta_pares = RAIZ / "dados" / "derivados" / "pares"
    pares = {x["codigo"]: x for x in ler_csv(pasta_pares / f"{data_ref}.csv")}
    param_pares = json.loads((pasta_pares / "parametros.json").read_text(encoding="utf-8")) if (pasta_pares / "parametros.json").exists() else None
    desvios = {}
    for s in series:
        j = justos.get(s["codigo"])
        if j:
            pr = pares.get(s["codigo"])
            desvios[s["codigo"]] = {"classe": j["classe"], "spread": f(j["spread_bps"]),
                                    "justo": f(pr["justo_ajustado_bps"]) if pr else f(j["spread_justo_bps"]),
                                    "justo_pares": f(pr["justo_pares_bps"]) if pr else None,
                                    "ajuste": f(pr["ajuste_eventos_bps"]) if pr else 0.0,
                                    "motivos": pr["motivos_ajuste"] if pr else "",
                                    "pares": pr["pares"] if pr else "",
                                    "justo_reg": f(j["spread_justo_bps"]),
                                    "desvio": f(pr["desvio_bps"]) if pr else f(j["desvio_bps"]),
                                    "dp": f(pr["desvio_em_dp"]) if pr else f(j["desvio_em_dp"]),
                                    "var_hist": f(j["variacao_hist_bps"]), "n_hist": int(j["n_dias_hist"] or 0),
                                    "faixa": j.get("faixa", "principal"), "motivo_faixa": j.get("motivo_faixa", "")}
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
            "taxa": f(s["taxa_indicativa"]), "z": f(s.get("zspread_bps")), "isenta": s.get("incentivada", ""),
        })
        if s["status"] == "ok DI+":
            di[s["codigo"]] = True
    historico: dict[str, list] = {}
    for a_csv in sorted(PREC.glob("????-??-??.csv")):
        for h in ler_csv(a_csv):
            v = h.get("zspread_comparavel_bps") if h["status"] == "ok" else h.get("spread_di_bps") if h["status"] == "ok DI+" else ""
            if v:
                historico.setdefault(h["codigo"], []).append([a_csv.stem, round(float(v), 1)])
    snd_c = {c["Codigo do Ativo"]: c for c in ler_csv(RAIZ / "dados" / "snd" / "caracteristicas.csv")}
    ponta = montar_ponta(snd_c)
    ativos = {}
    for s_ in series:
        c, u, d = s_["codigo"], universo[s_["codigo"]], desvios.get(s_["codigo"], {})
        cl = clausulas.get(c, {})
        ativos[c] = {
            "codigo": c, "isin": snd_c.get(c, {}).get("ISIN", ""), "emissor": u["emissor_atual_snd"].title(), "cnpj": u["cnpj"],
            "grupo": u["grupo_risco"], "segmento": u.get("segmento", ""), "faixa": d.get("faixa", "principal"), "motivo_faixa": d.get("motivo_faixa", ""),
            "classe": d.get("classe") or s_["indexador_tipo"], "indexador": snd_c.get(c, {}).get("indice", "") + (" + " + snd_c.get(c, {}).get("Juros Criterio Novo - Taxa", "") + "%" if snd_c.get(c, {}).get("Juros Criterio Novo - Taxa") else ""),
            "isenta": s_["incentivada"], "garantia": s_["garantia"], "vencimento": s_.get("vencimento", ""),
            "taxa": f(s_["taxa_indicativa"]), "pu": f(s_["pu_anbima"]), "dmod": f(s_.get("duration_mod_anos")),
            "z_mercado": f(s_.get("zspread_bps")), "spread_ntnb": f(s_.get("spread_ntnb_bps")), "ntnb_ref": s_.get("ntnb_referencia", ""),
            "spread": d.get("spread"), "justo_pares": d.get("justo_pares"), "ajuste": d.get("ajuste"), "motivos": d.get("motivos", ""),
            "justo_reg": d.get("justo_reg"), "desvio": d.get("desvio"), "dp": d.get("dp"), "pares": d.get("pares", ""),
            "choque100": f(s_.get("choque_100_pct")), "clausulas": cl.get("resumo", ""), "hist": historico.get(c, []),
            "ponta": ponta.get(c),
        }
    # fundamentos (CVM DFP) por emissor e exposição como devedor/cedente em CRI e CRA
    fundamentos = {}
    for x in ler_csv(RAIZ / "dados" / "cvm" / "fundamentos.csv"):
        fundamentos[x["cnpj"]] = {k: (f(x[k]) if k not in ("cnpj", "nome", "exercicio", "demonstracao") else x[k])
                                  for k in ("exercicio", "receita", "ebitda", "divida_liquida", "dl_ebitda", "cobertura_juros", "lucro_liquido")}
    certs = ler_csv(RAIZ / "dados" / "cri_cra" / "certificados.csv")
    devs = ler_csv(RAIZ / "dados" / "cri_cra" / "devedores.csv")
    por_cert = {}
    for d_ in devs:
        por_cert.setdefault(d_["certificado"], []).append(d_)
    cri_cra = []
    for c_ in certs:
        cri_cra.append({"t": c_["tipo"], "c": c_["codigo_cetip"], "i": c_["isin"], "s": c_["securitizadora"].title()[:40], "cl": c_["classe"],
                        "st": c_["situacao"], "v": c_["vencimento"], "r": c_["remuneracao"], "vl": f(c_["valor_certificados"]),
                        "rt": c_["rating"], "lg": c_["segmento_lastro"], "tl": c_["tipo_lastro"][:60], "ltv": f(c_["ltv"]),
                        "in": f(c_["inadimplencia_pct"]), "dv": [[x["cnpj"], x["papel"], f(x["percentual"])] for x in por_cert.get(c_["certificado"], [])][:6],
                        "ref": c_["data_referencia"]})
    nomes_cnpj = {u["cnpj"]: u["emissor_atual_snd"].title() for u in universo.values()}
    lista_desvios = [{"codigo": c, "emissor": universo[c]["emissor_atual_snd"].title(), "grupo": universo[c]["grupo_risco"],
                      "segmento": universo[c].get("segmento", ""), **v}
                     for c, v in desvios.items()]

    ipca = [d for d in desvios.values() if d["classe"] == "IPCA+"]
    n_emissores = len({universo[s["codigo"]]["cnpj"] for s in series})
    n_cvm = len({universo[s["codigo"]]["cnpj"] for s in series if universo[s["codigo"]]["fonte_grupo"] == "CVM FRE"})
    n_grupos = len({universo[s["codigo"]]["grupo_risco"] for s in series} - {"Isolada (a identificar)"})
    mediana = statistics.median(d["spread"] for d in ipca) if ipca else None
    fora = sum(1 for d in ipca if d["dp"] is not None and abs(d["dp"]) >= 1.5)

    trs = []
    ordem = sorted(series, key=lambda s: (desvios.get(s["codigo"], {}).get("desvio") is None, -(desvios.get(s["codigo"], {}).get("desvio") or 0)))
    EX = ' class="extra"'
    for s in ordem:
        u, d = universo[s["codigo"]], desvios.get(s["codigo"], {})
        valida = s["status"] in ("ok", "ok DI+")
        cl = clausulas.get(s["codigo"], {})
        fonte = {"CVM FRE": "CVM", "inferido": "inferido", "escritura": "escritura"}.get(u["fonte_grupo"], "")
        dp = d.get("dp")
        cor = "var(--surface)" if dp is None else "var(--div-neg-2)" if dp <= -1.5 else "var(--div-neg-1)" if dp <= -.5 else "var(--div-0)" if dp < .5 else "var(--div-pos-1)" if dp < 1.5 else "var(--div-pos-2)"
        segm = u.get("segmento", "")
        classe = d.get("classe") or s["indexador_tipo"]
        selo_hy = (' <span class="selo hy" title="' + html.escape(d.get("motivo_faixa", "")) + '">HY</span>') if d.get("faixa") == "high_yield" else ""
        busca_txt = html.escape(" ".join([s["codigo"], u["emissor_atual_snd"], u["grupo_risco"]]).lower())
        attrs = (f' data-segmento="{segm}" data-cls="{html.escape(classe)}" data-faixa="{d.get("faixa", "principal")}"'
                 f' data-dp="{"" if dp is None else dp}" data-busca="{busca_txt}"')
        abre = f'<tr data-codigo="{html.escape(s["codigo"])}"{attrs}>' if valida else f'<tr{attrs}>'

        def celula(v, c=0, sinal=False, extra=False):
            txt = ("+" if sinal and v is not None and v > 0 else "") + num(v, c)
            return f'<td{EX if extra else ""} data-v="{"" if v is None else v}">{txt}</td>'
        selo_fonte = f' <span class="selo">{fonte}</span>' if fonte else ""
        trs.append(
            abre
            + f'<td class="t"><span class="marca" style="background:{cor}"></span>{html.escape(s["codigo"])}{selo_hy}</td>'
            + f'<td class="t">{html.escape(u["emissor_atual_snd"].title())}</td>'
            + f'<td class="t extra">{html.escape(u["grupo_risco"])}{selo_fonte}</td>'
            + f'<td class="t">{SEGMENTOS_NOMES.get(segm, segm)}</td>'
            + f'<td class="t">{classe}</td>'
            + f'<td class="t extra">{ {"S": "sim", "N": "não"}.get(s["incentivada"], "–") }</td>'
            + f'<td class="t extra">{html.escape(s["garantia"] or "–")}</td>'
            + celula(d.get("spread"))
            + celula(d.get("justo_pares"))
            + celula(d.get("ajuste"), 1, True, True)
            + celula(d.get("desvio"), 0, True)
            + celula(dp, 1, True)
            + celula(d.get("var_hist"), 0, True, True)
            + celula(f(s.get("duration_mod_anos")), 2)
            + celula(f(s.get("choque_100_pct")), 2)
            + f'<td class="t pequeno fraco extra">{html.escape(cl.get("resumo", "")) if cl else ""}{"" if valida else html.escape(s["status"])}</td>'
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
<p class="pequeno" style="margin-top:.75rem"><b>Efeito da isenção medido no mercado:</b> no Z-spread sem ajuste, as debêntures incentivadas pagam {num(modelo.get("isencao", {}).get("coef_bps"), 0)} bps em relação às tributadas com o mesmo perfil (erro padrão {num(modelo.get("isencao", {}).get("erro_padrao_hc1"), 0)} bps; {modelo.get("isencao", {}).get("n_tributadas", "–")} tributadas e {modelo.get("isencao", {}).get("n_isentas", "–")} isentas). O gross-up de 15% aplicado no spread comparável equivale a cerca de 240 bps.</p>
<p class="fraco pequeno">IPCA+: n = {modelo["n"]}, R² = {num(modelo["r2"], 2)}, desvio padrão dos resíduos = {num(modelo["dp_residuos_bps"], 0)} bps. DI+: desvio medido contra a mediana das {modelo["di"]["n"]} séries ({num(modelo["di"]["mediana_bps"], 0)} bps). Especificação provisória.</p>"""

    dia = date.fromisoformat(data_ref).strftime("%d/%m/%Y")
    dados_js = json.dumps({"grafo": grafo, "series": dados_series, "fluxos": fluxos, "di": di, "desvios": lista_desvios, "docs": documentos,
                           "segmentos": SEGMENTOS_NOMES, "ativos": ativos, "fundamentos": fundamentos, "nomes_cnpj": nomes_cnpj},
                          ensure_ascii=False, separators=(",", ":"))
    (PUBLICO / "grafo-credito" / "cri_cra.json").write_text(json.dumps(cri_cra, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (PUBLICO / "grafo-credito").mkdir(parents=True, exist_ok=True)
    (PUBLICO / "grafo-credito" / "dados.json").write_text(dados_js, encoding="utf-8")
    escala = '<span class="escala">abaixo dos pares <b><i style="background:var(--div-neg-2)"></i><i style="background:var(--div-neg-1)"></i><i style="background:var(--div-0)"></i><i style="background:var(--div-pos-1)"></i><i style="background:var(--div-pos-2)"></i></b> acima dos pares</span>'

    n_seg = len({u.get("segmento") for u in universo.values()})
    n_hy = sum(1 for d in desvios.values() if d.get("faixa") == "high_yield")
    corpo = f"""<script>try{{var t=localStorage.getItem('tema');if(t)document.documentElement.dataset.theme=t}}catch(e){{}}</script>
<a class="pular" href="#conteudo">Pular para o conteúdo</a>
<header class="barra">
<div class="barra-in">
<a class="marca-site" href="#inicio" data-vista="inicio"><b>Grafo de Crédito</b><span>dados de {dia}</span></a>
<div class="busca-caixa"><input id="busca" type="search" autocomplete="off" placeholder="Buscar código, ISIN, empresa ou grupo" aria-label="Buscar ativo, emissor ou grupo"><kbd class="atalho" aria-hidden="true">/</kbd>
<ul id="resultados" role="listbox"></ul></div>
<div class="barra-acoes"><button id="tema" class="icone" aria-label="Alternar tema claro ou escuro" title="Tema claro ou escuro">◐</button><a class="link-sobre" href="/">Sobre</a></div>
</div>
<nav class="abas" aria-label="Seções">
<a href="#inicio" data-vista="inicio">Visão geral</a><a href="#mapa" data-vista="mapa">Mapa</a><a href="#valor" data-vista="valor">Valor relativo</a><a href="#ativos" data-vista="ativos">Ativos</a><a href="#simulador" data-vista="simulador">Simulador</a><a href="#cri" data-vista="cri">CRI e CRA</a><a href="#metodo" data-vista="metodo">Método</a>
</nav>
</header>

<main class="app" id="conteudo">

<section class="vista" id="v-inicio">
<div class="heroi">
<div class="kicker">Crédito privado · debêntures, CRI e CRA</div>
<h1>Grafo de Crédito</h1>
<p class="dek">Quem controla quem, quem emitiu o quê e quanto cada debênture paga acima ou abaixo dos pares. {num(len(series), 0)} séries de {n_emissores} emissores em {n_seg} segmentos, atualizado todo dia útil com dados públicos da ANBIMA, do SND, da CVM e da ANEEL.</p>
</div>

<div id="recentes" class="recentes" hidden><span class="fraco pequeno">Continuar de onde parou:</span> <span id="recentesLista"></span></div>

<h2 class="sec">Por onde começar</h2>
<ol class="jornada">
<li><a href="#mapa" data-vista="mapa"><span class="passo">Onde está o risco?</span><b>Mapa de controle</b><span>Do segmento ao grupo de risco, à empresa e a cada emissão, com fatos relevantes e escrituras.</span><em>Abrir o mapa →</em></a></li>
<li><a href="#valor" data-vista="valor"><span class="passo">Quem paga mais ou menos que os pares?</span><b>Valor relativo</b><span>Desvio de cada série em relação aos pares comparáveis, em bps e em desvios-padrão.</span><em>Ver os desvios →</em></a></li>
<li><a href="#simulador" data-vista="simulador"><span class="passo">E se o spread mudar?</span><b>Simulador</b><span>Quanto o preço muda numa abertura ou num fechamento, com o fluxo reprecificado.</span><em>Simular →</em></a></li>
</ol>
<p class="pequeno muted">Já sabe o que procura? Use a busca no topo (atalho <kbd>/</kbd>) ou a <a href="#ativos" data-vista="ativos">tabela de ativos</a>. Todo caminho termina na ficha do papel: preço de hoje, características, pares, simulação e documentos do emissor.</p>

<h2 class="sec">Maiores desvios hoje</h2>
<p class="pequeno muted" style="margin-top:-.4rem">Faixa principal, sem high yield, ordenados em desvios-padrão dos resíduos. Clique para abrir a ficha.</p>
<div class="ranking">
<div class="painel"><h3>Acima dos pares <span class="fraco">pagam mais que o perfil sugere</span></h3><ol id="rkAcima"></ol></div>
<div class="painel"><h3>Abaixo dos pares <span class="fraco">pagam menos que o perfil sugere</span></h3><ol id="rkAbaixo"></ol></div>
</div>

<h2 class="sec">O universo</h2>
<div class="tiles">
<div class="tile"><span>Séries no universo</span><b>{num(len(series), 0)}</b><small>{num(len(validas), 0)} precificadas</small></div>
<div class="tile"><span>Emissores</span><b>{n_emissores}</b><small>{n_cvm} com controle na CVM</small></div>
<div class="tile"><span>Grupos de risco</span><b>{n_grupos}</b><small>mais as isoladas</small></div>
<div class="tile"><span>Segmentos</span><b>{n_seg}</b><small>pares só dentro do segmento</small></div>
<div class="tile"><span>Spread comparável mediano</span><b>{num(mediana, 0)} bps</b><small>IPCA+, gross-up 15% nas isentas</small></div>
<div class="tile"><span>Faixa high yield</span><b>{n_hy}</b><small>Z ≥ 300 bps ou evento de crédito</small></div>
<div class="tile"><span>Fora da faixa dos pares</span><b>{fora}</b><small>|desvio| ≥ 1,5 dp</small></div>
</div>
</section>

<section class="vista" id="v-mapa" hidden>
<div class="vista-cab"><div><h2>Mapa de controle e risco</h2><p>Clique num segmento, depois num grupo de risco e numa empresa. A ficha abre ao lado; clique numa emissão para ver o papel.</p></div>
<details class="ajuda"><summary>Como ler o mapa</summary><p>Cada bola grande é um segmento; dentro dele, cada bola é um grupo de risco, do tamanho do número de séries. A cor das bolhas, grupos e emissores é o macrossetor; a cor de cada emissão é o desvio de spread em relação aos pares. Ao abrir uma empresa aparecem as emissões e os documentos (fatos relevantes, escrituras, notícias e análises); clique num documento para abrir o original. Clique no nome do grupo para recolher. Linhas pontilhadas entre bolas são empresas compartilhadas entre grupos. Arraste para mover e use a roda do mouse ou dois dedos para aproximar.</p></details></div>
<div class="painel">
<div class="controles"><nav id="trilha" class="pequeno" aria-label="Caminho no mapa"></nav><span class="espaco"></span>
<select id="filtroGrupo" aria-label="Abrir segmento ou grupo"></select>
<span class="pequeno muted rotulo-ctrl">Rótulos</span><span class="seg" role="group" aria-label="Rótulos"><button data-rot="controle" class="ativo">controladores</button><button data-rot="todos">todos</button><button data-rot="nenhum">nenhum</button></span>
<button id="mapaCentro" aria-label="Recentrar o mapa" title="Recentrar o mapa"><span aria-hidden="true">⟲</span><span class="so-largo"> Recentrar</span></button></div>
<svg id="grafo" role="img" aria-label="Grafo de controladores, emissores e séries de debêntures agrupados por grupo de risco"></svg>
<div class="legenda legenda-macro"><span><i style="background:var(--m-energia)"></i>energia</span><span><i style="background:var(--m-infra)"></i>saneamento, transporte e logística</span><span><i style="background:var(--m-commod)"></i>commodities e indústria</span><span><i style="background:var(--m-consumo)"></i>consumo, serviços, telecom e financeiro</span>{escala}</div>
<details class="legenda-det"><summary>Legenda completa: documentos e ligações</summary>
<div class="legenda"><span><i style="background:var(--doc-oficial);border-radius:0;clip-path:polygon(50% 0,100% 100%,0 100%)"></i>fato relevante, comunicado, aviso (CVM)</span><span><i style="background:var(--doc-oficial);border-radius:1px"></i>escritura</span><span><i style="background:var(--doc-noticia);transform:rotate(45deg);border-radius:1px"></i>notícia</span><span><i style="background:var(--doc-analise);clip-path:polygon(50% 0,61% 35%,98% 35%,68% 57%,79% 91%,50% 70%,21% 91%,32% 57%,2% 35%,39% 35%)"></i>análise (casas de research)</span><span><i style="background:var(--surface);border:2px solid var(--div-pos-2)"></i>impacto negativo (JEV)</span><span><i style="background:var(--surface);border:2px solid var(--div-neg-2)"></i>impacto positivo (JEV)</span></div>
<div class="legenda" style="border-top:0;padding-top:0"><span>■ controlador (CVM)</span><span>⬚ grupo inferido</span><span>○ emissor</span><span>· · ponte entre grupos</span><span>── controle declarado (CVM)</span><span>—·— parte citada na escritura</span><span>- - grupo inferido</span><span>··· fiança (escritura)</span><span style="color:var(--div-pos-2)">— — cross-default alcança a controladora (escritura)</span></div>
</details>
</div>
<p class="proximo">Encontrou um papel? A ficha ao lado leva à simulação e aos pares. Para comparar o segmento inteiro, vá para <a href="#valor" data-vista="valor">Valor relativo →</a></p>
</section>

<section class="vista" id="v-valor" hidden>
<div class="vista-cab"><div><h2>Valor relativo</h2><p>Spread observado menos o spread justo dos pares, já com o ajuste por eventos. À direita, a série paga mais do que o perfil dela sugere; à esquerda, menos. Clique numa barra para abrir a ficha.</p></div>
<details class="ajuda"><summary>Como é calculado</summary><p>Spread justo = mediana das 8 séries mais comparáveis de outros emissores, no mesmo segmento, na mesma classe (IPCA+ ou DI+) e na mesma faixa (principal ou high yield). A cor marca o tamanho do desvio em desvios-padrão dos resíduos. Desvio não é recomendação: parte dele é prêmio de liquidez que o modelo não mede.</p></details></div>
<div class="painel">
<div class="barra-filtros"><select id="segDesvio" aria-label="Segmento"></select>
<span class="seg" role="group" aria-label="Indexador"><button data-classe="IPCA+" class="ativo">IPCA+</button><button data-classe="DI+">DI+</button></span>
<span class="seg" role="group" aria-label="Quantidade"><button data-ndesvio="extremos" class="ativo">20 maiores de cada lado</button><button data-ndesvio="todos">todas</button></span>
<span class="espaco"></span><span id="desvioInfo" class="pequeno fraco"></span></div>
<div class="grafico-desvio"><svg id="desvio" role="img" aria-label="Barras divergentes do desvio de spread de cada série"></svg></div>
<div class="legenda">{escala}</div>
</div>
<p class="proximo">Escolheu uma série? Na ficha, a aba Simulação mostra o efeito de uma abertura ou de um fechamento. Para filtrar e ordenar com mais critérios, use <a href="#ativos" data-vista="ativos">Ativos →</a></p>
</section>

<section class="vista" id="v-ativos" hidden>
<div class="vista-cab"><div><h2>Ativos</h2><p>Todas as séries do universo. Clique numa linha para abrir a ficha; clique no cabeçalho para ordenar.</p></div></div>
<div class="painel">
<div class="barra-filtros">
<input id="fBusca" type="search" placeholder="Filtrar por código, emissor ou grupo" aria-label="Filtrar a tabela">
<select id="segTabela" aria-label="Segmento"></select>
<select id="fClasse" aria-label="Indexador"><option value="">IPCA+ e DI+</option><option>IPCA+</option><option>DI+</option></select>
<select id="fFaixa" aria-label="Faixa"><option value="">Todas as faixas</option><option value="principal">Principal</option><option value="high_yield">High yield</option></select>
<label class="chk"><input type="checkbox" id="fFora"> só fora da faixa dos pares</label>
<span class="espaco"></span><span id="fInfo" class="pequeno fraco" aria-live="polite"></span><button id="fColunas" aria-pressed="false">Mais colunas</button>
</div>
<div class="tabela"><table id="tab">
<thead><tr><th class="t">Série</th><th class="t">Emissor atual (SND)</th><th class="t extra">Grupo de risco</th><th class="t">Segmento</th><th class="t">Classe</th><th class="t extra">Isenta</th><th class="t extra">Garantia</th><th>Spread (bps)</th><th>Justo pares (bps)</th><th class="extra">Ajuste eventos</th><th>Desvio (bps)</th><th>Desvio (dp)</th><th class="extra">Variação hist. (bps)</th><th title="Duration modificada: % do preço por 100 bps de taxa">Duration mod.</th><th>Choque +100 (%)</th><th class="t extra">Escritura / status</th></tr></thead>
<tbody>
{chr(10).join(trs)}
</tbody></table></div>
</div>
</section>

<section class="vista" id="v-simulador" hidden>
<div class="vista-cab"><div><h2>Simulador de abertura e fechamento de spread</h2><p>Escolha a série e arraste a régua ou o ponto do gráfico. O fluxo remanescente é descontado de novo com a taxa indicativa mais o choque.</p></div>
<details class="ajuda"><summary>Como é calculado</summary><p>IPCA+: fluxo real da agenda SND descontado à taxa real. DI+: fluxo projetado pela curva prefixada ANBIMA e descontado a (1 + DI) × (1 + spread). A linha tracejada é o que daria só a duration; a diferença para a curva cheia é a convexidade.</p></details></div>
<div class="painel sim">
<div>
<label for="serie">Série</label><select id="serie"></select>
<label for="regua">Choque no spread: <b id="regua_valor" class="serif" style="font-size:1.05rem">+100 bps</b></label>
<input id="regua" type="range" min="-300" max="300" step="5" value="100" aria-label="Choque no spread em bps">
<div class="regua-marcas"><span>−300</span><span>−150</span><span>0</span><span>+150</span><span>+300</span></div>
<svg id="curva" role="img" aria-label="PU em função do choque de spread; arraste para ajustar"></svg>
<label for="choque">Valor exato (bps)</label><input id="choque" type="number" step="5" value="100">
<div class="botoes"><button data-v="-100">−100</button><button data-v="-50">−50</button><button data-v="50">+50</button><button data-v="100">+100</button><button data-v="200">+200</button></div>
</div>
<div><div class="res">
<div><small>PU ANBIMA (hoje)</small><b id="r_pu">–</b><span class="pequeno muted" id="r_taxa"></span></div>
<div><small>PU após o choque</small><b id="r_pu_novo">–</b><span class="pequeno muted" id="r_taxa_nova"></span></div>
<div><small>Variação do preço (fluxo reprecificado)</small><b id="r_var">–</b><span class="pequeno muted" id="r_var_rs"></span></div>
<div><small>Só duration: − duration × choque</small><b id="r_so_dur">–</b><span class="pequeno muted">erra porque trata a curva preço × taxa como reta</span></div>
<div><small>Ajuste de convexidade: + ½ × convexidade × choque²</small><b id="r_conv">–</b><span class="pequeno muted" id="r_conv_info"></span></div>
<div><small>Duration + convexidade (aproximação)</small><b id="r_aprox">–</b><span class="pequeno muted" id="r_resid"></span></div>
<div><small>Duration modificada</small><b id="r_dur">–</b><span class="pequeno muted" id="r_dur_info"></span></div>
<div><small>Spread</small><b id="r_z">–</b><span class="pequeno muted" id="r_z_info"></span></div>
<div><small>Desvio em relação aos pares</small><b id="r_desvio">–</b></div>
<div><small>Break-even de abertura em 12 meses</small><b id="r_be12">–</b></div>
</div>
<p class="pequeno" style="margin:.8rem 0 0"><button id="simFicha">Abrir a ficha desta série</button></p></div>
</div>
</section>

<section class="vista" id="v-cri" hidden>
<div id="crisec">
<div class="vista-cab"><div><h2>CRI e CRA</h2><p>Certificados de recebíveis imobiliários e do agronegócio, pelo Informe Mensal das securitizadoras à CVM. Devedores que também emitem debêntures aparecem em negrito e na ficha do emissor.</p></div>
<details class="ajuda"><summary>Limites</summary><p>Sem preço diário de mercado: a ANBIMA não publica taxas de CRI e CRA em arquivo aberto. A tabela traz situação, remuneração, lastro, LTV, inadimplência dos créditos, rating e devedores.</p></details></div>
<div class="painel">
<div class="barra-filtros"><input id="criBusca" type="search" placeholder="Filtrar por código, ISIN, securitizadora ou devedor" aria-label="Filtrar CRI e CRA">
<select id="criTipo" aria-label="Tipo"><option value="">CRI e CRA</option><option>CRI</option><option>CRA</option></select> <select id="criSit" aria-label="Situação"><option value="">Toda situação</option><option>Adimplente</option><option>Em atraso</option></select> <select id="criLastro" aria-label="Lastro"><option value="">Todo lastro</option></select>
<span class="espaco"></span><span id="criInfo" class="pequeno fraco" aria-live="polite"></span></div>
<div class="tabela"><table><thead><tr><th class="t">Tipo</th><th class="t">Código</th><th class="t">Securitizadora</th><th class="t">Classe</th><th class="t">Situação</th><th class="t">Remuneração</th><th class="t">Vencimento</th><th class="t">Lastro</th><th>LTV</th><th>Inadimplência</th><th class="t">Rating</th><th class="t">Devedores / cedentes</th></tr></thead><tbody id="criCorpo"></tbody></table></div>
</div>
</div>
</section>

<section class="vista" id="v-metodo" hidden>
<div class="vista-cab"><div><h2>Método e limites</h2><p>Como cada número é calculado e o que o modelo não mede. Código e dados em <a href="https://github.com/alissondpoliveira/grafo-credito">github.com/alissondpoliveira/grafo-credito</a>.</p></div></div>
<h3>Modelo de spread justo</h3>
<p class="muted pequeno">Regressão cross-section do spread comparável das séries IPCA+ validadas, com erros padrão robustos. O spread justo de cada série é o valor ajustado; o desvio é o resíduo.</p>
{coef_html}
<h3>Regras</h3>
<ul class="metodo pequeno">
<li><b>Fluxo de pagamentos</b> da agenda de eventos do SND; validação contra a duration ANBIMA. Séries que não batem ficam fora e aparecem marcadas.</li>
<li><b>Spread comparável</b>: Z-spread sobre a curva zero-cupom real (ETTJ IPCA, ANBIMA), com gross-up de 15% na taxa nominal das debêntures incentivadas (isentas para pessoa física), usando a inflação implícita na duration de cada série.</li>
<li><b>Faixa high yield</b>: séries IPCA+ com Z-spread de mercado ≥ 300 bps, DI+ com spread ≥ 300 bps sobre o CDI, ou emissor com evento de crédito negativo (JEV, confiança ≥ 0,8) nos últimos 12 meses. Ficam fora da regressão e só se comparam com outras high yield.</li>
<li><b>Pares comparáveis</b>: filtros obrigatórios de mesmo segmento, mesma classe (IPCA+ ou DI+) e mesma faixa (principal ou high yield; high yield com menos de 3 pares no segmento compara entre segmentos); entre os candidatos de outros emissores, os 8 mais próximos por estrutura (project finance ou corporativa), fase do ativo (construção, transição, operacional; regra pela idade da concessão na ANEEL, refinada pelo JEV), patrocinador, garantia, isenção, duration, folga até o fim da concessão e tamanho. Pesos explícitos em <code>analises/pares.py</code>. O spread justo é a mediana dos pares.</li>
<li><b>Ajuste por eventos</b> (provisório, conservador): crédito negativo +25 bps, outro impacto negativo +8, avanço operacional −5, só com classificação JEV de confiança ≥ 0,8; meia-vida de 60 dias, janela de 180, tetos por tipo (−10 / +20 / +40) e de ±40 por emissor. Será recalibrado por estudo de evento quando houver histórico.</li>
<li><b>Spread justo pela regressão</b> (segunda leitura): modelo provisório com duration, garantia real, controle declarado na CVM, tamanho da emissão e dispersão das contribuições ANBIMA. Desvio não é recomendação: parte dele é prêmio de liquidez que o modelo não mede.</li>
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
<div id="fundo" class="fundo"></div>
<aside id="gaveta" class="gaveta" role="dialog" aria-labelledby="gavTitulo" hidden>
<div class="gav-topo"><div id="gavCab" class="gav-cab"></div><button id="gavFechar" class="icone" aria-label="Fechar a ficha" title="Fechar (Esc)">✕</button></div>
<div id="gavAbas" class="gav-abas" role="tablist"></div>
<div id="gavCorpo" class="gav-corpo"></div>
</aside>
<div id="tip" class="tip"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
<script>function iniciar(){{""" + JS + """}
fetch('/grafo-credito/dados.json', {cache: 'no-cache'}).then(r => r.json()).then(d => { window.DADOS = d; iniciar(); });</script>"""
    return pagina("Grafo de Crédito", "Grafo de Crédito: controle, grupos de risco e desvio de spread das debêntures de transmissão de energia.", corpo)


def main() -> None:
    (PUBLICO / "grafo-credito").mkdir(parents=True, exist_ok=True)
    (PUBLICO / "index.html").write_text(gerar_home(), encoding="utf-8")
    (PUBLICO / "grafo-credito" / "index.html").write_text(gerar_projeto(), encoding="utf-8")
    print("site/public gerado")


if __name__ == "__main__":
    main()
