# 01 · Documentação do Agente

## Caso de uso
**Aegis** é um assistente virtual de **segurança da informação defensiva**. Ele ajuda estudantes e profissionais iniciantes a entender e aplicar boas práticas (AppSec, contêineres, pipelines DevSecOps, criptografia, segurança de IA generativa e resposta a incidentes).

**Problema:** material de segurança é disperso, técnico e, em um assistente de IA comum, pode vir com respostas inventadas ou até com instruções ofensivas.
**Solução:** respostas curtas, **ancoradas em uma base curada, com fonte citada**, que dizem "não sei" quando não há base e que recusam pedidos ofensivos.

## Público-alvo
Estudantes de tecnologia, devs que querem incorporar segurança ao dia a dia e times pequenos sem especialista dedicado.

## Comportamento esperado
| Situação | Comportamento |
|----------|---------------|
| Dúvida coberta pela base | Resposta objetiva + `[S#]` + fontes + próximos passos |
| Dúvida fora da base/escopo | Recusa educada ("não encontrei na base"), lista temas disponíveis |
| Tentativa de prompt injection | Bloqueio e orientação para reformular |
| Pedido ofensivo (malware, invasão) | Recusa; oferece o ângulo defensivo |
| Incidente relatado ("commitei uma senha") | Prioriza o checklist de resposta a incidentes |
| Credencial/CPF/cartão na pergunta | Mascara antes de processar e avisa a pessoa usuária |
| Saudação/ajuda/agradecimento | Resposta curta, sem chamar o LLM |

## Fora de escopo
Segurança ofensiva operacional, aconselhamento jurídico definitivo (LGPD é orientação geral), diagnóstico de sistemas reais e qualquer assunto não relacionado a segurança.

## Princípios
1. **Não inventar**: sem base suficiente, o assistente se recusa.
2. **Citar sempre**: toda resposta de LLM precisa de `[S#]` válido, senão é descartada e substituída pela resposta extrativa.
3. **Minimizar dados**: mascarar antes de processar; não registrar o texto da pergunta.
4. **Falhar fechado**: erro interno devolve mensagem genérica, nunca stack trace.

## Fluxo de uma pergunta
```
Cliente ─TLS─► Gateway(nginx) ─► API(JWT,RBAC,rate limit) ─► [barramento cifrado]
   guarda de entrada ─► NLU ─► RAG(BM25) ─► geração(LLM ou extrativa) ─► guarda de saída ─► resposta
```
