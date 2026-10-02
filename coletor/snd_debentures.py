"""Coletor de características e agenda de eventos das debêntures no SND (debentures.com.br).

Para cada série do universo: características (incentivada, garantia, taxa,
juros, amortização, resgate) e agenda de eventos futuros (juros, amortização,
vencimento). Dados mudam pouco; rodar sob demanda ou semanalmente.

Uso:
    python coletor/snd_debentures.py              # séries do universo de transmissão
    python coletor/snd_debentures.py CPFGA2 TAEE17
"""

import csv
import io
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

BASE = "https://www.debentures.com.br/exploreosnd/consultaadados"
URL_CARAC = BASE + "/emissoesdedebentures/caracteristicas_e.asp?Ativo={}"
URL_AGENDA = BASE + "/eventosfinanceiros/agenda_e.asp?Ativo={}"
RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "dados" / "snd"
UNIVERSO = RAIZ / "dados" / "referencia" / "universo_transmissao.csv"
DEB = RAIZ / "dados" / "anbima" / "debentures" / "normalizado"


def baixar(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "grafo-credito/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("latin-1")


def tabela(texto: str, inicio_cabecalho: str) -> list[dict]:
    """Lê o bloco tab-delimitado que começa na linha de cabeçalho indicada."""
    linhas = texto.splitlines()
    i = next((k for k, l in enumerate(linhas) if l.startswith(inicio_cabecalho)), None)
    if i is None:
        return []
    corpo = "\n".join(l for l in linhas[i:] if l.strip())
    leitor = csv.DictReader(io.StringIO(corpo), delimiter="\t", restkey="_excedente")
    # linhas do SND às vezes têm colunas a mais que o cabeçalho; o excedente é descartado
    return [
        {k.strip(): (v or "").strip() for k, v in linha.items() if k and k != "_excedente"}
        for linha in leitor
    ]


CANDIDATOS = RAIZ / "dados" / "referencia" / "universo_candidatos.csv"


def series_do_universo() -> list[str]:
    """Séries do universo ampliado (energia, saneamento e infraestrutura de transporte)."""
    return sorted({c["codigo"] for c in csv.DictReader(CANDIDATOS.open(encoding="utf-8"))})


def main(codigos: list[str]) -> None:
    codigos = codigos or series_do_universo()
    caracs, agendas, falhas = [], [], []
    for cod in codigos:
        try:
            c = tabela(baixar(URL_CARAC.format(cod)), "Codigo do Ativo")
            a = tabela(baixar(URL_AGENDA.format(cod)), "Data do Evento")
        except Exception as e:  # rede instável: registra e segue
            falhas.append(f"{cod}: {e}")
            continue
        if not c:
            falhas.append(f"{cod}: sem características no SND")
            continue
        caracs.extend(c)
        agendas.extend({**ev, "Ativo": ev.get("Ativo", "").strip() or cod} for ev in a)
        time.sleep(0.5)

    DESTINO.mkdir(parents=True, exist_ok=True)
    hoje = date.today().isoformat()
    for nome, linhas in (("caracteristicas", caracs), ("agenda", agendas)):
        if not linhas:
            continue
        campos = list(dict.fromkeys(k for l in linhas for k in l if k))
        with (DESTINO / f"{nome}.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["data_coleta"] + campos, extrasaction="ignore", lineterminator="\n")
            w.writeheader()
            w.writerows({"data_coleta": hoje, **l} for l in linhas)
    print(f"{len(caracs)} séries com características, {len(agendas)} eventos de agenda")
    for f in falhas:
        print("FALHA", f)


if __name__ == "__main__":
    main(sys.argv[1:])
