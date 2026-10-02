# 06 · Pitch (3 minutos)

**1. Problema (30 s)** — Quem está aprendendo segurança encontra conteúdo disperso, e assistentes de IA comuns inventam respostas e podem ajudar ataques. Em empresas, perguntar a um chatbot com dados reais ainda pode vazar CPF e credenciais.

**2. Solução (45 s)** — O **Aegis** é um assistente de segurança defensiva que responde com base em uma base curada, **cita a fonte**, diz "não sei" quando deve, bloqueia prompt injection e mascara dados sensíveis antes de qualquer processamento.

**3. Como funciona (45 s)** — Gateway com TLS → API com JWT/RBAC → **barramento cifrado e assinado** (Redis Streams) → worker com pipeline de 5 estágios → **barramento de IA** com múltiplos provedores e fallback determinístico. Tudo em contêineres endurecidos, em três redes isoladas, com auditoria à prova de adulteração.

**4. Prova (30 s)** — 63 testes automatizados, avaliação fim a fim com *quality gate* no CI e pipeline DevSecOps (gitleaks, Bandit, pip-audit, Trivy, SBOM, OPA, ZAP).

**5. Valor e próximos passos (30 s)** — Trilha de treinamento com simulado e laboratórios. Roadmap: embeddings, mTLS, ACL por tópico, SSO/OIDC, painel de métricas.

## Roteiro de demonstração
1. `make cli` → "Como me proteger de SQL injection?" (resposta com fonte e passos).
2. "Ignore todas as instruções anteriores…" (bloqueio).
3. "Usei a chave AKIA… no código" (máscara + aviso de rotação).
4. "Previsão do tempo?" (recusa honesta).
5. `make eval` e o relatório; mostrar o `ci.yml` e a rede `internal` no compose.
