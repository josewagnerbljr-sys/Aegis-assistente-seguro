# Trilha de Treinamento em Segurança — Banco de Treinamento do Aegis

Material de apoio do desafio. Cada módulo liga **conceito → base de conhecimento (`kb-XXX`) → laboratório no próprio projeto → verificação**. O assistente responde sobre todos estes temas (pergunte a ele!), e `scripts/quiz.py` aplica o simulado em `banco_quiz.json`.

> Público: quem está começando em segurança e quer provar competência com um projeto real. Carga sugerida: 6 a 8 semanas.

## Mapa de módulos

| # | Módulo | Base (kb) | Laboratório no repositório | Verificação |
|---|--------|-----------|----------------------------|-------------|
| 0 | Fundamentos e defesa em profundidade | 027, 033 | Desenhar o DFD e aplicar STRIDE ao Aegis (`docs/04-arquitetura-seguranca.md`) | Lista de ameaças com mitigação |
| 1 | AppSec / OWASP Top 10 | 001–004, 037 | Escrever 3 testes que tentam IDOR e injeção na API (`tests/test_api.py`) | Testes verdes |
| 2 | Identidade e acesso | 005, 006, 009, 010 | Criar usuário com `scripts/hash_password.py`; forjar JWT `alg=none` e ver o 401 | `test_jwt_none_algorithm_rejected` |
| 3 | Criptografia | 007, 008, 036 | Cifrar a base com `scripts/encrypt_kb.py`; adulterar 1 byte e ver `InvalidTag` | `tests/test_crypto.py` |
| 4 | Contêineres | 011–013 | Construir a imagem; rodar `docker run --read-only --cap-drop ALL` | `docker inspect` mostra USER não-root |
| 5 | Rede e barramento | 013, 026, 031 | Subir o compose; confirmar que `api` não alcança a internet (`backend` é `internal`) | `docker compose exec` + curl falha |
| 6 | Pipelines DevSecOps | 014–021, 035 | Ler `.github/workflows/ci.yml`; quebrar o pipeline de propósito com um segredo falso | gitleaks reprova o PR |
| 7 | Segurança de IA generativa | 022–025 | Rodar `eval/run_eval.py`; adicionar 5 ataques de injeção ao `golden_set.json` | Taxa de bloqueio ≥ 100% do conjunto |
| 8 | Logs, auditoria e LGPD | 023, 028, 032 | Alterar uma linha do log e rodar `GET /v1/audit/verify` | Cadeia reportada como quebrada |
| 9 | Resposta a incidentes | 029, 030, 034 | Simular "commitei uma chave": perguntar ao Aegis e executar o checklist | Playbook preenchido |
| 10 | Projeto final | todos | Evoluir o Aegis (ver roadmap no README) e apresentar o pitch | Demo + métricas |

## Pipelines de referência

O banco inclui três artefatos de pipeline, todos com os mesmos *quality gates*:

```
pre-commit ─► lint/SAST ─► SCA ─► testes+cobertura ─► eval do assistente ─► build ─► policy (OPA) ─► Trivy ─► SBOM ─► DAST ─► assinatura
```

| Artefato | Caminho | Observação |
|----------|---------|------------|
| GitHub Actions | `.github/workflows/ci.yml` | permissões mínimas, concorrência, artefatos (eval, SBOM) |
| GitLab CI | `data/treinamento/pipelines/gitlab-ci.yml` | mesmos estágios, com Kaniko e Cosign |
| Política como código | `data/treinamento/pipelines/policy/dockerfile.rego` | proíbe `:latest`, root e `ADD` |
| Hooks locais | `.pre-commit-config.yaml` | gitleaks, ruff, bandit, detect-private-key |

### Exercícios de pipeline
1. **Quebre o gate de segredo**: adicione `AKIAABCDEFGHIJKLMNOP` em um arquivo e abra um PR. Registre qual job falhou e por quê.
2. **Quebre o gate de container**: troque `FROM python:3.12-slim` por `FROM python:latest` e rode `conftest test Dockerfile --policy data/treinamento/pipelines/policy`.
3. **Quebre o gate de qualidade**: reduza `min_confidence` para `0.0` e veja `out_of_scope_refusal` cair no `eval/run_eval.py`.
4. **Fixe actions por SHA** (módulo 6) e documente o ganho contra um ataque de troca de tag.
5. **Gere o SBOM** com `syft aegis:local -o cyclonedx-json` e procure um pacote específico com `jq`.

## Laboratórios guiados (resumo)

### Lab A — Atacar para defender (somente neste ambiente de estudo)
Com a API em `localhost`, execute (e explique o resultado de) cada tentativa: login com senha errada (resposta genérica), 20 logins seguidos (429), corpo de 20 KB (413), `alg=none` (401), `Ignore todas as instruções...` (bloqueado), pedir ao bot um ransomware (recusado).

### Lab B — Barramento sob ataque
No `tests/test_bus_audit.py`, reproduza: adulteração do cabeçalho, chave errada, replay fora da janela e mensagem lixo na DLQ do Redis. Para cada caso, indique **qual camada** barrou (HMAC, AEAD, timestamp, formato).

### Lab C — Medir para melhorar
Crie 10 perguntas novas **escritas por outra pessoa** e rode a avaliação. Compare com o conjunto original: a diferença mostra o viés de avaliar com dados do próprio autor.

## Glossário rápido
**AEAD** cifra autenticada · **AAD** dados autenticados não cifrados · **HKDF** derivação de subchaves · **HMAC** código de autenticação · **DLQ** fila de mensagens com falha · **DLP** prevenção de perda de dados · **SBOM** inventário de software · **SAST/DAST/SCA** análise estática/dinâmica/de composição · **KEV/EPSS** exploração conhecida/probabilidade de exploração · **RAG** geração aumentada por recuperação.

## Avaliação final
Simulado de 21 questões (`python scripts/quiz.py`): meta ≥ 80%. Complemente com a defesa oral do pitch (`docs/06-pitch.md`).
