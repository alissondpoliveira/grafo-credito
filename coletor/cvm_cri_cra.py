"""CRI e CRA: Informe Mensal das securitizadoras (CVM, dados abertos). Opção B, versão 1.

Não há preço de mercado diário aberto para CRI/CRA (ANBIMA Data exige reCAPTCHA; ANBIMA Feed é pago).
Este módulo traz QUALIDADE DE CRÉDITO e EXPOSIÇÃO por certificado, no informe mais recente:
  securitizadora, segmento do lastro, tipo de lastro, garantias, LTV, rating, classe (sênior/subordinada),
  código CETIP e ISIN, vencimento, remuneração, situação (adimplente...), inadimplência dos créditos vinculados
  e devedores/cedentes com CNPJ e percentual (que ligam o CRI/CRA ao grafo de emissores).

Saídas: dados/cri_cra/certificados.csv e dados/cri_cra/devedores.csv

Uso: python coletor/cvm_cri_cra.py
"""

import csv
import io
import urllib.request
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
URL = "https://dados.cvm.gov.br/dados/SECURIT/DOC/INF_MENSAL_{t}/DADOS/inf_mensal_{tl}_{a}.zip"
DESTINO = RAIZ / "dados" / "cri_cra"


def num(v: str) -> float | None:
    try:
        return float(v) if v not in ("", None) else None
    except ValueError:
        return None


def carregar(tipo: str) -> tuple[list[dict], list[dict]]:
    ano = date.today().year
    for a in (ano, ano - 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(URL.format(t=tipo, tl=tipo.lower(), a=a), headers={"User-Agent": "grafo-credito"}), timeout=600) as r:
                z = zipfile.ZipFile(io.BytesIO(r.read()))
            break
        except Exception:
            continue
    else:
        return [], []

    def tab(parte: str) -> list[dict]:
        nome = next((n for n in z.namelist() if f"_{parte}_" in n), None)
        return list(csv.DictReader(io.TextIOWrapper(z.open(nome), encoding="latin-1"), delimiter=";")) if nome else []

    # último informe (data de referência e versão) de cada certificado
    geral = tab("geral")
    ult: dict[str, tuple] = {}
    for g in geral:
        k = g["Codigo_Identificacao_Certificado"]
        chave = (g["Data_Referencia"], int(g["Versao"] or 0))
        if k not in ult or chave > ult[k]:
            ult[k] = chave
    atual = lambda l: ult.get(l["Codigo_Identificacao_Certificado"]) == (l["Data_Referencia"], int(l["Versao"] or 0))
    geral = {g["Codigo_Identificacao_Certificado"]: g for g in geral if atual(g)}
    carteira = {c["Codigo_Identificacao_Certificado"]: c for c in tab("carteira") if atual(c)}

    certificados = []
    for c in tab("classe"):
        if not atual(c):
            continue
        g = geral.get(c.get("Codigo_Identificacao_Certificado", ""), {})
        ca = carteira.get(c.get("Codigo_Identificacao_Certificado", ""), {})
        vinc, inad = num(ca.get("Creditos_Vinculados", "")), num(ca.get("Creditos_Vinculados_Inadimplentes", ""))
        certificados.append({
            "tipo": tipo, "codigo_cetip": c.get("Codigo_CETIP", ""), "isin": c.get("Codigo_ISIN", ""), "certificado": c.get("Codigo_Identificacao_Certificado", ""),
            "data_referencia": c.get("Data_Referencia", ""), "securitizadora": g.get("Companhia_Emissora", ""), "cnpj_securitizadora": c.get("CNPJ_Emissora", ""),
            "emissao": g.get("Numero_Emissao", ""), "serie": c.get("Numero_Serie", ""), "classe": c.get("Classe", ""), "situacao": c.get("Situacao", ""),
            "vencimento": c.get("Data_Vencimento", ""), "remuneracao": c.get("Taxa_Juros", "") or c.get("Taxas_Indexadores", ""),
            "valor_certificados": num(c.get("Valor_Certificados", "")), "rating": c.get("Classificacao_Risco_Atual", ""), "agencia": g.get("Agencia_Classificadora", ""),
            "subordinacao": c.get("Nivel_Subordinacao", ""), "segmento_lastro": g.get("Segmento_Creditos_Vinculados", ""),
            "tipo_lastro": g.get("Tipo_Lastro", ""), "detalhe_lastro": g.get("Detalhamento_Lastro", ""),
            "garantias": g.get("Sobrecolateralizacao", "") or g.get("Tipos_Garantias_Coobrigacao_Terceiros", ""),
            "ltv": num(g.get("Indice_LTV", "")), "inadimplencia_pct": 100 * inad / vinc if vinc and inad is not None else None,
            "agente_fiduciario": g.get("Agente_Fiduciario", ""),
        })
    devedores = [{"tipo": tipo, "certificado": d["Codigo_Identificacao_Certificado"], "papel": d.get("Tipo", ""),
                  "cnpj": "".join(ch for ch in d.get("CNPJ", d.get("CPF_CNPJ", "")) if ch.isdigit()).zfill(14), "percentual": num(d.get("Percentual", ""))}
                 for d in tab("cedente_devedor") if atual(d)]
    return certificados, devedores


def gravar(nome: str, linhas: list[dict]) -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    with (DESTINO / nome).open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(linhas)


def main() -> None:
    certs, devs = [], []
    for t in ("CRI", "CRA"):
        c, d = carregar(t)
        certs += c
        devs += d
        print(f"{t}: {len(c)} séries/classes, {len({x['certificado'] for x in c})} certificados, {len(d)} vínculos de devedor/cedente")
    gravar("certificados.csv", certs)
    gravar("devedores.csv", devs)


if __name__ == "__main__":
    main()
