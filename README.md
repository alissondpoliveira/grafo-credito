# grafo-credito

Memória viva de emissores de dívida do crédito privado brasileiro, organizada como grafo de conhecimento: emissões, garantias, covenants, grupo econômico, demonstrações financeiras e preços de mercado.

- **Fase 1:** spread justo por comparáveis e simulador de abertura/fechamento de spread.
- **Fase 2:** probabilidade de default implícita no spread vs. sugerida pelos fundamentos.

## Estado atual

Coletor diário das taxas de debêntures da ANBIMA rodando no GitHub Actions. A ANBIMA só mantém os últimos dias úteis gratuitamente, então o histórico deste repositório é construído dia a dia a partir de setembro/2026.

| Pasta | Conteúdo |
|---|---|
| `coletor/` | Scripts de coleta (Python, só biblioteca padrão) |
| `dados/anbima/debentures/brutos/` | Arquivo original da ANBIMA, sem alteração (auditoria) |
| `dados/anbima/debentures/normalizado/` | Um CSV por dia, números em ponto decimal e datas ISO |

### Campos do CSV normalizado

| Campo | Descrição |
|---|---|
| `data_referencia` | Data do arquivo ANBIMA |
| `codigo`, `emissor` | Código da série e nome do emissor |
| `marcadores` | Marcações `(*)`/`(**)` do nome, preservadas sem interpretação |
| `vencimento` | Data de repactuação ou vencimento |
| `indexador_tipo`, `taxa_emissao` | `DI_MAIS`, `PCT_DI`, `IPCA_MAIS`, `IGPM_MAIS`, `IGPM`, `PREFIXADO` e a taxa de emissão |
| `taxa_compra`, `taxa_venda`, `taxa_indicativa` | Taxas ANBIMA (% a.a.; para DI+ é o spread sobre o CDI) |
| `desvio_padrao`, `intervalo_min`, `intervalo_max` | Dispersão das contribuições |
| `pu`, `pct_pu_par` | Preço unitário e % do PU par |
| `duration_du`, `duration_anos` | Duration em dias úteis (como divulgada) e em anos (÷252) |
| `pct_reune` | % Reune |
| `ntnb_referencia` | Vencimento da NTN-B de referência (papéis IPCA+) |

## Rodar localmente

```bash
python coletor/anbima_debentures.py              # dias úteis recentes
python coletor/anbima_debentures.py 2026-10-01   # data específica
```

## Fonte e limitações

Dados: [ANBIMA, mercado secundário de debêntures](https://www.anbima.com.br/pt_br/informar/precos-e-indices/precos/taxas-debentures.htm). A taxa indicativa é uma referência de preço justo, não necessariamente negócio fechado.
