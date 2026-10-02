# 02 · Base de Conhecimento

Arquivo: `data/kb/base_conhecimento.json` — **37 itens** curados, em 8 categorias (`appsec`, `iam`, `cripto`, `container`, `rede`, `pipeline`, `llm`, `incidente`).

## Esquema de cada item
| Campo | Descrição |
|-------|-----------|
| `id` | `kb-001`… único (validado no carregamento) |
| `titulo`, `categoria`, `nivel` | classificação (`basico`/`intermediario`/`avancado`) |
| `tags` | sinônimos e termos de busca (peso 2 no índice) |
| `conteudo` | resposta curta e verificável (2–4 frases) |
| `passos` | ações práticas, usadas como "próximos passos" |
| `fontes` | referências (OWASP, NIST, CIS…) pelo **nome**, para a pessoa pesquisar na versão atual |

## Recuperação
BM25 próprio (sem dependências) sobre `titulo×3 + tags×2 + conteudo + passos`, com normalização de acentos, stopwords PT/EN e stemming mínimo de plural. A **confiança** combina cobertura dos termos da pergunta e score BM25; abaixo de `0.35` (ajustável) o assistente se recusa. Casar apenas 1 termo de uma pergunta com 2+ termos reduz a confiança (evidência fraca).

## Como evoluir
1. Adicione um item seguindo o esquema (o carregamento valida campos e IDs duplicados).
2. Adicione 1–2 perguntas ao `eval/golden_set.json`.
3. Rode `make eval`. O CI bloqueia regressões.

## Proteção em repouso e integridade
`python scripts/encrypt_kb.py data/kb/base_conhecimento.json data/kb/base.enc` cifra a base com AES-256-GCM (chave derivada por HKDF da chave-mestra). Aponte `AEGIS_KB_PATH` para o `.enc`. Como o GCM é autenticado, **qualquer alteração no arquivo impede o carregamento** (defesa contra envenenamento da base — ver `kb-024`).

## Limitações
Base pequena e em português; perguntas em inglês só funcionam quando usam termos técnicos em comum. Não há embeddings semânticos: sinônimos fora das `tags` podem falhar (próximo passo no roadmap).
