# Política de Segurança

## Reportando vulnerabilidades
Não abra issue pública. Envie os detalhes por canal privado ao mantenedor (ou use *Security Advisories* do GitHub), com passos de reprodução e impacto. Meta de resposta: 5 dias úteis.

## Versões suportadas
Somente a versão em `main`.

## Regras do projeto
- Nenhum segredo no repositório (gitleaks no pre-commit e no CI). Use `.env` local ou cofre.
- Toda mudança passa por lint, SAST, SCA, testes e pela avaliação do assistente.
- Dependências fixas em `requirements.txt`; atualize com revisão.
- Uso exclusivamente **defensivo e educacional**.
