# CLAUDE.md

Guia para o Claude Code ao trabalhar neste repositório.

## Comandos

```bash
# Instalar dependências (requirements-trt3.txt inclui o PyTorch da CRNN)
pip install -r requirements-trt3.txt

# Rodar localmente (FastAPI + FastMCP na porta 8000)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Docker (porta 8002 conforme docker-compose.yaml)
docker compose up --build -d
docker compose down
```

Testes automatizados (mockam o TRT3, rodam no CI):

```bash
pip install -r requirements-dev.txt
ruff check app/
pytest tests/ -v
```

Testes manuais via:
- Interface web: `http://localhost:8000/`
- FastAPI docs (apenas `ENV=development`): `http://localhost:8000/docs`
- MCP transport: `http://localhost:8000/mcp` (streamable-http)

## Arquitetura

FastAPI (`app/main.py`) com routers REST + FastMCP 3.0 montado em `/mcp`. A camada `services/` não tem dependência de framework.

```
app/
├── main.py           # FastAPI — routers + rate limiter + mcp.http_app() em /mcp
├── config.py         # Lê todas as variáveis de ambiente com defaults
├── mcp_server.py     # FastMCP("cpf-validador") — 6 tools wrapping services
├── auth.py           # TokenMiddleware — autenticação via API_TOKEN + controle prod/dev via ENV
├── rate_limit.py     # Limiter compartilhado — main.py e routers/consulta.py precisam do mesmo objeto
├── services/
│   ├── cpf.py        # Lógica pura de CPF (zero deps de framework)
│   └── sources/      # Fontes de consulta — a fonte ativa vem de SOURCE no .env
│       ├── base.py     # ABC Fonte + contrato do retorno + mascarar_cpf (log)
│       ├── __init__.py # Registro preguiçoso + busca em lote (agnóstica de fonte)
│       ├── trt3.py     # TRT3: curl_cffi + CAPTCHA CRNN + pypdf
│       ├── tcu.py      # TCU: API JSON + Altcha (PoW PBKDF2), sem pypdf
│       └── exemplo.py  # Modelo para novas fontes — fictícia, sem rede e sem CAPTCHA
├── routers/
│   ├── cpf.py        # POST /cpf/validate, POST /cpf/variations
│   ├── consulta.py   # POST /consulta/cpf, /cpfs, /buscar-por-mascara, /buscar-por-variacoes
│   └── ui.py         # GET / — interface web com gate de autenticação
└── captcha/
    ├── model.py       # Arquitetura CRNN (CNN + BiLSTM + CTC Loss)
    ├── predictor.py   # Inferência — carrega captcha_model.pt
    ├── dataset.py     # CaptchaDataset com data augmentation
    ├── train.py       # Loop de treino com early stopping + AMP + registry
    ├── collector.py   # Coleta amostras rotuladas do TRT3 (--workers N)
    ├── registry.py    # Versionamento de modelos (models/vN/model.pt + meta.json)
    └── models/        # Histórico de versões treinadas
```

### Regras de camada
- `services/` — zero imports de FastAPI ou FastMCP; puro Python
- `routers/` e `mcp_server.py` importam apenas de `services/` — mesma lógica de negócio, duas interfaces
- `routers/` e `mcp_server.py` **nunca** importam uma fonte concreta: só `services.sources.consultar`
  e `consultar_multiplos`, que despacham para a fonte ativa
- I/O bloqueante em `services/sources/` sempre executado via `run_in_threadpool`
- Consultas paralelas usam `ThreadPoolExecutor` em `services/sources/__init__.py` (não nos routers)

### MCP tools (6)
| Tool | Descrição |
|------|-----------|
| `validate_cpf` | Validação matemática via algoritmo módulo-11 |
| `generate_valid_variations` | Gera variações válidas: recalcula dígitos, troca 1 dígito (mantendo os outros 10), transpõe pares adjacentes |
| `check_cpf` | Consulta TRT3 — valida CPF, resolve CAPTCHA (CRNN), retorna resultado estruturado |
| `find_cpf_by_mask` | Descobre CPF completo a partir de máscara com curingas — consulta TRT3 em paralelo |
| `find_cpf_by_variations` | Gera candidatos de CPF parcial/errado e consulta TRT3 em paralelo, filtra por nome |
| `check_multiple_cpfs` | Consulta lista de CPFs em paralelo, agrupa erros de validação separadamente |

### REST endpoints
| Método | Rota | Rate limit | Descrição |
|--------|------|------------|-----------|
| GET | `/` | — | Interface web |
| POST | `/cpf/validate` | — | Valida um CPF |
| POST | `/cpf/variations` | — | Gera variações válidas |
| POST | `/consulta/cpf` | 10/min por IP | Consulta um CPF na fonte ativa |
| POST | `/consulta/cpfs` | 5/min por IP | Consulta lista de CPFs em paralelo |
| POST | `/consulta/buscar-por-mascara` | 3/min por IP | Consulta CPFs por máscara com curingas |
| POST | `/consulta/buscar-por-variacoes` | 3/min por IP | Consulta variações de CPF parcial |
| GET | `/auth/check` | — | Valida o token (401 se inválido) — usado pelo gate da UI |
| GET | `/health` | — | Health check (sempre aberto — healthcheck do Docker) |
| GET | `/metrics` | — | Métricas Prometheus (token em `production`) |

Campos do retorno de consulta: `cpf`, `encontrado`, `nome_certidao`, `tem_registro`,
`cpf_inexistente`, `mensagem`, `erro` — descritos em `base.Fonte.consultar`.

### Autenticação
- `API_TOKEN` vazio → servidor sem autenticação
- `API_TOKEN` definido → todas as rotas exigem `Authorization: Bearer <token>`, exceto `/` e `/health`
- `ENV=development` → `/docs`, `/redoc`, `/openapi.json`, `/metrics` também ficam abertos
- `ENV=production` → apenas `/` e `/health` ficam abertos sem token (`/health` é o healthcheck do Docker)
- `METRICS_PUBLIC=true` → abre `/metrics` sem token também em `production`
- Interface web (`/`) tem gate: exige token no browser quando `API_TOKEN` está configurado. O gate valida contra `/auth/check` — **nunca** contra uma rota aberta como `/health`, senão qualquer token passa
- O histórico da UI vive no `localStorage` do navegador; o servidor não persiste consultas

### Máscaras de CPF
`services/cpf.py::_normalizar_mascara` reduz qualquer formato a 11 posições antes de gerar candidatos:
- Curingas equivalentes: `*` `X` `x` `?` `_` `#`
- Separadores ignorados: `.` `-` `/` `\`, espaço, tab e espaço não-quebrável (colagem de PDF/web)
- Máscaras de 9 ou 10 posições completam os dígitos verificadores com curinga
- Caractere desconhecido → `ValueError` apontando o caractere (nunca descarte silencioso)

### Fontes de consulta
`SOURCE` no .env escolhe quem responde "a quem pertence este CPF?". Registradas em
`services/sources/__init__.py::_REGISTRO`:

| `SOURCE` | Fonte | Como consulta |
|----------|-------|---------------|
| `trt3` (padrão) | TRT 3ª Região (MG) | formulário JSF + CAPTCHA de imagem (CRNN) + PDF |
| `tcu` | TCU, nacional | API JSON + CAPTCHA Altcha (proof-of-work via `altcha-solver`) |
| `exemplo` | Fictícia | nada — modelo para novas fontes |

Cada fonte é dona do *como*: cliente HTTP, autenticação, CAPTCHA (ou nenhum), parsing e
limite de conexões. A camada comum padroniza só o retorno — `cpf`, `encontrado`
(`True`/`False`/`None`), `nome_certidao`, `cpf_inexistente`, `mensagem` e `erro`,
documentado em `base.Fonte.consultar`. `nome_certidao` é obrigatório para que o filtro
`nome=` das buscas em lote funcione, e `mensagem` é exibida pela UI como veio — nada de
texto específico de uma fonte dentro da interface.

A fonte declara também `usa_captcha` (padrão `False`), que a UI recebe via
`__USA_CAPTCHA__` para escolher os rótulos dos passos.

As frases exibidas ao usuário são padronizadas em `base.py` — `MSG_CPF_INEXISTENTE`,
`MSG_SEM_REGISTRO` e `MSG_INDETERMINADO`. Toda fonte usa as mesmas: o usuário não deve
descobrir qual respondeu pelo texto da mensagem. Texto próprio só quando a fonte tem algo
que nenhuma outra teria.

O registro é **preguiçoso**: a classe só é importada quando a fonte é usada, para que uma
fonte sem CAPTCHA não carregue o PyTorch do TRT3. `tests/test_sources.py` trava isso.

Para adicionar uma fonte: copie `sources/exemplo.py`, implemente `consultar()` e acrescente
uma linha em `_REGISTRO`. Nenhum router ou tool MCP precisa mudar.

### Métricas
Dois grupos, separados pelo que é conceito de consulta e o que é do scraping:
- `consulta_*` — valem para qualquer fonte e levam o label `fonte`
  (`consulta_queries_total`, `consulta_duration_seconds`, `consulta_cpf_total`,
  `consulta_matches_total`). São incrementadas num ponto só, em
  `sources/__init__.py::_consultar_medindo`, para toda fonte ser medida igual
- `trt3_*` — CAPTCHA de imagem, PDF, resets de sessão e erros HTTP
- `tcu_*` — duração e contador do proof-of-work, concorrência e erros HTTP
- `cpf_*`, `mcp_calls_total`, `http_rate_limit_total` — da aplicação

### Logs da consulta
Dois loggers, configurados pelo root logger em `main.py` via `LOG_LEVEL`:
- `consulta` (`sources/__init__.py`) — o que vale para qualquer fonte: início, progresso, fim de
  lote e `MATCH`. Toda linha traz `fonte=<nome>`
- `trt3` (`sources/trt3.py`) — o que é específico do scraping: CAPTCHA, PDF, sessão

- `INFO` — certidão obtida (com tipo, tentativas, duração), `MATCH`, início/progresso/fim de lote
- `DEBUG` — cada tentativa de CAPTCHA, o texto lido pela CRNN e o nome da certidão
- `WARNING` — captcha esgotado numa tentativa, PDF ilegível, timeout, resposta não reconhecida
- `ERROR` — página sem CAPTCHA (layout do TRT3 mudou) e desistência após todas as tentativas

**CPF nunca sai inteiro no log** — `sources/base.py::mascarar_cpf()` reduz para `111.***.***-35`. O nome da certidão
só aparece em `DEBUG`. `tests/test_logging.py` trava as duas garantias.

### Busca em lote
`sources/__init__.py::consultar_multiplos` é agnóstico de fonte e cuida de paralelismo,
filtro por nome e progresso. Com `nome` informado e `parar_ao_confirmar=True` (padrão), a
busca é interrompida assim que `nome_confirmado()` casar — as futures pendentes são
canceladas. A resposta traz `consultados` e `interrompido` além de `total`.

`nome_confirmado()` exige nomes iguais ou toda palavra procurada presente inteira no nome
encontrado, e recusa filtro de uma palavra só — a mesma regra do selo `✓ Confirmado` da
interface, que tem a versão em JS.

### Fluxo de scraping TRT3
1. GET página do formulário → extrai JSF `ViewState` e URL do CAPTCHA
2. Download da imagem CAPTCHA → resolve com **modelo CRNN local** (PyTorch, ~99% acurácia)
3. POST do formulário com impersonação Chrome-124 via **curl_cffi** (bypass TLS fingerprint)
4. Retry até 20× em falha de CAPTCHA
5. Parse da resposta: se PDF retornado, extrai nome/CPF/validade via **pypdf** + regex

### Modelo CAPTCHA
- Arquitetura: CRNN (4× Conv2D + BatchNorm + BiLSTM × 2 + CTC Loss)
- Treinamento: 3 rodadas bootstrapping, 55k amostras, val_accuracy 98.55%
- Modelo ativo: `app/captcha/captcha_model.pt` (registry v1)
- Para retreinar: `python -m app.captcha.train --epochs 120 --batch 128 --lr 1e-3`
