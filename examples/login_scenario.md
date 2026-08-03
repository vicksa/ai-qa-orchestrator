# Exemplo de cenário

Um cenário é só linguagem natural — o próprio agente planeja as tool calls
(`navigate`, `click`, `fill`, `assert_text`, `get_dom`).

```json
{
  "target_url": "https://example.com/login",
  "scenario": "Vá até a página de login. Preencha o campo de e-mail com 'demo@example.com' e o campo de senha com 'demo-password-123'. Clique no botão de Entrar. Depois que a página carregar, confirme que o título do dashboard contém a palavra 'Bem-vindo'."
}
```

Enviando:

```bash
curl -X POST http://localhost:8000/runs \
  -H "Content-Type: application/json" \
  -d @- <<'JSON'
{
  "target_url": "https://example.com/login",
  "scenario": "Vá até a página de login. Preencha o campo de e-mail com 'demo@example.com' e o campo de senha com 'demo-password-123'. Clique no botão de Entrar. Depois que a página carregar, confirme que o título do dashboard contém a palavra 'Bem-vindo'."
}
JSON
```

A resposta traz o `id` da execução. Acompanhe com:

```bash
curl http://localhost:8000/runs/<id>
```

Ou abra `http://localhost:8000/runs/<id>/report` para o relatório legível, incluindo
qualquer seletor que o agente precisou corrigir sozinho pelo caminho.

## Como o "self-healing" funciona na prática

Se o botão de submit do formulário de login for renomeado de `#login-btn` para
`data-testid="submit-login"` entre o momento em que o cenário foi escrito e o
momento em que ele roda, um teste ingênuo baseado em seletor quebra. Este agente,
em vez disso:

1. Tenta `#login-btn`, recebe um timeout de localização.
2. Tira um snapshot novo do DOM da página como ela está agora.
3. Pede ao modelo um novo seletor, dado a descrição do elemento em linguagem
   natural ("o botão de Entrar") e o HTML ao vivo.
4. Tenta o clique de novo com o novo seletor.
5. Registra a substituição como um `HealingEvent` — visível na página de
   relatório — em vez de falhar a execução silenciosamente.

Se o seletor corrigido também falhar, o passo é reportado como uma falha normal;
a correção tem exatamente uma tentativa, não um loop sem limite.
