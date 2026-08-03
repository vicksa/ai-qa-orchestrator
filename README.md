# ai-qa-orchestrator

Um agente de IA que transforma um cenário de teste escrito em linguagem natural em uma
execução real num navegador — planeja os passos, controla o Playwright através de tool calls,
**se auto-corrige quando um seletor quebra** e reporta a execução inteira (incluindo o que foi
corrigido e por quê) num dashboard em FastAPI.

## Por que isso importa

Suítes de teste E2E apodrecem no momento em que um `data-testid` é renomeado ou um botão muda
de lugar dentro de uma nova `<div>`. Suítes tradicionais quebram nesse tipo de mudança mesmo
quando o fluxo de usuário continua funcionando perfeitamente — alguém precisa notar o build
vermelho, abrir o diff e atualizar o seletor manualmente. Este projeto trata isso como algo que
um agente pode resolver em tempo real: quando o seletor de um passo não resolve, o agente tira
um novo snapshot do DOM, pede ao modelo um seletor substituto baseado na página real, tenta de
novo uma vez e — se funcionar — registra o evento de correção em vez de derrubar a execução.
O resultado é uma suíte de testes que sobrevive a mudanças incidentais de UI, com um histórico
completo de cada vez que precisou se adaptar.

Também é um exemplo pequeno e completo de um sistema agente construído diretamente sobre a
API da Claude (sem framework): um loop manual de tool-use, uma chamada de structured output
restrita para o passo de correção, uma camada de execução assíncrona (FastAPI + Celery + Redis)
para que execuções lentas de navegador não travem a API, e uma camada de persistência que
transforma cada execução em um relatório revisável.

## Arquitetura

```
                    ┌─────────────────────────┐
   POST /runs  ───▶ │   FastAPI (aiqa.api)     │ ───▶ Postgres/SQLite
                    │   dashboard + REST API   │        (runs, steps,
                    └───────────┬─────────────┘         healing events)
                                │ enfileira
                                ▼
                    ┌─────────────────────────┐
                    │  Celery worker + Redis   │
                    │  aiqa.worker.tasks       │
                    └───────────┬─────────────┘
                                │ conduz
                                ▼
                    ┌─────────────────────────┐        ┌───────────────────┐
                    │  Agent orchestrator      │ ─────▶ │  Claude (Opus 5)   │
                    │  aiqa.agent.orchestrator │ ◀───── │  loop de tool-use  │
                    └───────────┬─────────────┘        └───────────────────┘
                                │ tool calls (navigate/click/fill/assert/get_dom)
                                ▼
                    ┌─────────────────────────┐
                    │  Playwright (Chromium)   │
                    └─────────────────────────┘
                                │ ao encontrar um seletor quebrado
                                ▼
                    ┌─────────────────────────┐        ┌───────────────────┐
                    │  Self-healing             │ ─────▶ │  Claude (output    │
                    │  aiqa.agent.healing       │ ◀───── │  estruturado: novo │
                    │                           │        │  seletor + porquê) │
                    └─────────────────────────┘        └───────────────────┘
```

**Por que um agente em vez de um gerador de script fixo:** uma abordagem de codegen (transformar
linguagem natural num script Playwright uma vez e rodar esse script para sempre) não tem
caminho de recuperação quando a página muda por baixo dele. Rodar o modelo ao vivo durante a
execução — com tools em vez de código gerado — significa que o mesmo agente que planejou o
fluxo pode replanejar só o passo que quebrou, sem precisar reconstruir o teste inteiro.

## Instalação

```bash
pip install -e ".[dev]"
playwright install --with-deps chromium
cp .env.example .env   # depois defina ANTHROPIC_API_KEY
```

## Rodando localmente

Tudo que é necessário para executar uma run: Redis (broker), o worker do Celery e a API.

```bash
docker compose up -d redis postgres   # ou aponte DATABASE_URL para seu próprio Postgres/SQLite
celery -A aiqa.worker.celery_app worker --loglevel=info &
uvicorn aiqa.api.main:app --reload
```

Depois abra `http://localhost:8000` para o dashboard, ou envie uma execução diretamente:

```bash
curl -X POST http://localhost:8000/runs \
  -H "Content-Type: application/json" \
  -d '{
        "scenario": "Vá até a página de login, entre com a conta demo e confirme que a saudação do dashboard mostra o nome do usuário.",
        "target_url": "https://example.com/login"
      }'
```

`GET /runs/{id}` retorna o status da execução em JSON; `GET /runs/{id}/report` renderiza um
relatório em HTML com cada passo e qualquer evento de self-healing.

Veja `examples/login_scenario.md` para um exemplo de cenário mais completo.

## Docker

```bash
docker compose up --build
```

Sobe Postgres, Redis, a aplicação FastAPI e um worker do Celery juntos. Veja `docker-compose.yml`
para a ligação entre os serviços e `.env.example` para as variáveis que cada um lê.

## Testes

```bash
pytest
ruff check .
```

Os testes mockam o LLM e a `Page` do Playwright — não é preciso navegador real, acesso à rede
nem API key para rodar a suíte.

## Estrutura do projeto

```
src/aiqa/
  agent/         schemas das tools, loop de tool-use com a Anthropic, self-healing
  api/           app FastAPI, routers, templates Jinja2 do dashboard/relatório
  worker/        task do Celery que roda um cenário e persiste o resultado
  models.py      tabelas SQLModel (TestRun, TestStep, HealingEvent)
tests/           suíte pytest (tools, healing, orchestrator, API, worker)
```

## Licença

MIT — veja [LICENSE](./LICENSE).
