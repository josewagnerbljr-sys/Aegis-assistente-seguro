# 07 · Blueprint da Interface Web

Implementação base já incluída em `src/aegis/ui/` (HTML + CSS + JS puros, sem build e sem dependências), servida pela própria API em `/ui/`. Este documento descreve o que existe e como evoluir.

## Objetivo
Mostrar em 30 segundos o diferencial do projeto: **respostas com fonte, recusa honesta e segurança visível**, não só um chat.

## Wireframe
```
┌──────────────────────────────────────────────────────────────┐
│ 🛡️ Aegis  assistente de segurança defensiva        👤 maria [Sair] │
├───────────────────────────────────────┬──────────────────────┤
│  Conversa                             │ Caminho da pergunta  │
│  ┌ usuário ─────────────────────┐     │  ✔ Guarda de entrada │
│  └──────────────────────────────┘     │  ✔ DLP               │
│  ┌ Aegis ───────────────────────┐     │  ✔ NLU               │
│  │ resposta com chips [S1] [S2] │     │  ✔ RAG               │
│  │ Fontes: S1 · kb-002 · …      │     │  ✔ Geração+citações  │
│  │ Próximos passos: 1. 2. 3.    │     │  ✔ Guarda de saída   │
│  │ ⚠ aviso de credencial        │     ├──────────────────────┤
│  │ intenção · confiança ▓▓▓░ ·  │     │ Camadas ativas       │
│  │ provedor · ms · trace        │     │  🔒 🪪 🧠 🔐 🧾 📦      │
│  └──────────────────────────────┘     │                      │
│  [exemplos clicáveis]                 │                      │
│  [ Pergunte sobre segurança…  ][Enviar]│                     │
└───────────────────────────────────────┴──────────────────────┘
```

## Mapeamento API → interface
| Campo de `/v1/chat` | Elemento |
|---------------------|----------|
| `answer` | bolha do bot; `[S#]` vira chip azul |
| `sources[]` | lista "S1 · kb-002 · título — fontes" |
| `next_steps[]` | lista numerada |
| `warnings[]` | faixa amarela (credencial/PII mascarada) |
| `blocked` | borda vermelha + estágio "Guarda de entrada" em vermelho |
| `intent == fora_de_escopo` | borda amarela + estágio "RAG" em vermelho (recusa honesta) |
| `confidence` | barra de confiança |
| `provider`, `latency_ms`, `trace_id` | selos no rodapé da bolha |

## Estados tratados
Login inválido, limite de tentativas (429), sessão expirada (401 volta ao login), pergunta inválida (413/422), erro temporário, bloqueio, recusa e resposta normal.

## Regras de segurança da UI (já aplicadas e testadas)
- CSP estrita para `/ui`: `script-src 'self'`, sem `unsafe-inline`, `frame-ancestors 'none'`.
- Todo texto vem por `textContent`/nós de texto; **nunca HTML bruto** (o teste `test_ui_served_with_strict_csp` falha se isso mudar).
- Token JWT **só em memória** (nada em `localStorage`/cookies); a senha é limpa do campo após o login.
- Sem CDN, fontes ou scripts externos.

## Acessibilidade
Rótulos nos campos, `role="log"` com `aria-live` no histórico, foco visível, contraste alto, `prefers-reduced-motion` respeitado, layout responsivo (painel lateral sobe em telas estreitas).

## Roadmap sugerido (em ordem de impacto visual)
1. **Painel de métricas**: tela `/ui/metrics.html` lendo o `eval/report.json` (endpoint admin `GET /v1/eval/report`), com barras por métrica e lista de falhas.
2. **Streaming (SSE)** da resposta com estágios aparecendo em tempo real no "Caminho da pergunta".
3. **Histórico de sessão** local (apenas em memória) e botão "copiar resposta com fontes".
4. **Modo claro/escuro** e seletor de idioma PT/EN.
5. **Feedback 👍/👎** por resposta, gravando na auditoria (sem texto) para medir resolução.
6. **Visualização do barramento**: linha do tempo `req.received → … → res.<id>` com latência por estágio (usar `trace_id`).

## Checklist de capturas para o README
1. Tela de login. 2. Resposta com fontes e passos. 3. Bloqueio de prompt injection (borda vermelha). 4. Aviso de credencial mascarada. 5. Recusa "não encontrei na base". 6. Relatório da avaliação. Grave um GIF de 20 s seguindo o roteiro de `docs/06-pitch.md`.
