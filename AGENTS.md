# AGENTS.md

Guia para qualquer agente de código (Codex, Cursor, Claude Code, Copilot…) que for
trabalhar neste repositório. Explica o que o projeto faz, como cada parte funciona e as
regras que não podem ser quebradas. O `CLAUDE.md` tem o mesmo conteúdo em formato de
referência rápida; se os dois divergirem, o código manda e os dois devem ser corrigidos.

## O que é

Serviço que responde **"a quem pertence este CPF?"** consultando bases públicas, e que
**recupera um CPF incompleto ou digitado errado**. Expõe a mesma lógica por três portas:

- **REST** (FastAPI) — `app/routers/`
- **MCP** (FastMCP 3.0, streamable-http em `/mcp`) — `app/mcp_server.py`, 6 tools
- **Interface web** em `/` — uma página única servida por `app/routers/ui.py`

Nada é persistido no servidor: o histórico da interface vive no `localStorage` do navegador.

## Regras que não se quebram

1. **Dado real nunca entra no repositório.** Ele é público. CPF, nome ou certidão de pessoa
   real não vão para teste, fixture, exemplo de API, README, CHANGELOG nem mensagem de
   commit — inclusive o CPF que alguém informou para reproduzir um bug e a versão
   "corrigida" dele. Use o CPF de exemplo do projeto, `151.879.820-95`, e derive dele os
   casos inválidos (`151.879.820-98`, `151.979.820-95`). Nome de exemplo: `FULANO DE TAL`.
   Antes de commitar, `git grep` pelo dado usado na reprodução.
2. **CPF nunca sai inteiro no log.** Use `sources/base.py::mascarar_cpf()`
   (`111.***.***-35`). Nome de certidão só em `DEBUG`. `tests/test_logging.py` trava as duas.
3. **`services/` não importa FastAPI nem FastMCP.** É Python puro.
4. **Routers e tools MCP nunca importam uma fonte concreta** — só
   `services.sources.consultar` e `consultar_multiplos`.
5. **Uma fonte nunca levanta exceção para quem chama**: falha vira
   `{"cpf": ..., "encontrado": None, "erro": "..."}`.
6. **Um commit por mudança**, em português (`fix:`, `fix(ui):`, `build:`, `ci:`, `chore:`),
   sem `Co-Authored-By` nem assinatura de ferramenta.
7. **Toda mudança é documentada** no README (no padrão existente) e no `CHANGELOG.md`.
8. **Subir a versão e dar push no `master` publica uma release** (ver "CI e release").

## Comandos

```bash
pip install -r requirements-trt3.txt     # app + PyTorch da CRNN
pip install -r requirements-dev.txt      # + ruff e pytest

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
docker compose up --build -d             # porta 8002

ruff check app/                          # config fixada no pyproject.toml
pytest tests/ -v                         # não toca em rede; ~5s
```

`requirements.txt` é o app sem PyTorch — serve para `SOURCE=tcu` ou `exemplo`. A imagem
Docker sem TRT3 sai com `--build-arg COM_TRT3=false` (473 MB em vez de 1.76 GB).

## Mapa do código

```
app/
├── main.py           # monta FastAPI: routers, rate limiter, TokenMiddleware, MCP em /mcp,
│                     # /health, /auth/check, /metrics; configura o root logger (LOG_LEVEL)
├── config.py         # TODA variável de ambiente é lida aqui, com default
├── auth.py           # TokenMiddleware — Bearer token, comparação em bytes e tempo constante
├── rate_limit.py     # Limiter único do slowapi — main.py e routers usam o MESMO objeto
├── metrics.py        # métricas Prometheus
├── mcp_server.py     # FastMCP("cpf-validador") — 6 tools
├── services/
│   ├── cpf.py        # módulo-11, máscaras e variações — lógica pura
│   └── sources/
│       ├── base.py     # ABC Fonte, contrato do retorno, MSG_*, mascarar_cpf
│       ├── __init__.py # registro preguiçoso, consultar, consultar_multiplos, nome_confirmado
│       ├── trt3.py     # TRT 3ª Região: curl_cffi + CAPTCHA de imagem (CRNN) + pypdf
│       ├── tcu.py      # TCU: API JSON + Altcha (proof-of-work)
│       └── exemplo.py  # fonte fictícia — modelo para fontes novas
├── routers/
│   ├── cpf.py        # /cpf/validate, /cpf/variations
│   ├── consulta.py   # /consulta/cpf, /cpfs, /buscar-por-mascara, /buscar-por-variacoes (+ /stream)
│   └── ui.py         # GET / — HTML+CSS+JS numa string Python
└── captcha/          # CRNN do TRT3: model, predictor, dataset, train, collector, registry
tests/                # pytest; fixtures/ tem respostas reais do TRT3 com dados fictícios
```

## Como funciona

### 1. Lógica de CPF (`services/cpf.py`)

- `calcular_digitos(base9)` — os dois verificadores pelo módulo-11.
- `is_valido(cpf11)` — 11 dígitos, não todos iguais, verificadores batendo.
- **Máscara** (`gerar_cpfs_de_mascara`): `_normalizar_mascara` reduz qualquer formato a 11
  posições. Curingas equivalentes `* X x ? _ #`; separadores ignorados `. - / \`, espaço,
  tab e espaço não-quebrável; máscara de 9 ou 10 posições completa os verificadores com
  curinga; caractere desconhecido levanta `ValueError` apontando qual (nunca descarte
  silencioso). Só os curingas da **base** (posições 0–8) são enumerados — os verificadores
  são sempre recalculados e, se informados, funcionam como filtro. Limite:
  `MAX_WILDCARDS_IN_MASK` (5 → até 100.000 combinações).
- **Variações** (`generate_valid_variations`): modela **um** erro de digitação. Candidatos,
  nesta ordem: o próprio CPF se válido; verificadores recalculados; troca de 1 dígito em
  qualquer das 11 posições; transposição de par adjacente. Só entram os que passam no
  módulo-11. A troca **mantém os outros 10 dígitos como digitados** — recalcular os
  verificadores depois de trocar um dígito da base faz as 81 trocas passarem sempre (toda
  base tem verificadores válidos) e o resultado vira 82 candidatos. O normal é 1 a 8
  candidatos, média ~2.
- CPF com menos de 11 dígitos é tratado em `routers/consulta.py::_gerar_candidatos_variacoes`:
  insere um dígito em cada posição, com e sem um dígito trocado.

### 2. Fontes de consulta (`services/sources/`)

`SOURCE` no `.env` escolhe a fonte ativa; valor inválido derruba o boot.

| `SOURCE` | Fonte | Como consulta |
|----------|-------|---------------|
| `trt3` (padrão) | TRT 3ª Região (MG) | formulário JSF + CAPTCHA de imagem lido pela CRNN + PDF |
| `tcu` | TCU, nacional | API JSON + CAPTCHA Altcha (proof-of-work via `altcha-solver`) |
| `exemplo` | fictícia | nada — sem rede e sem CAPTCHA |

Cada fonte é dona do *como* (cliente HTTP, CAPTCHA, parsing, limite de conexões). A camada
comum padroniza só o **retorno** de `Fonte.consultar(cpf_limpo)`:

| chave | significado |
|-------|-------------|
| `cpf` | CPF formatado — obrigatório |
| `encontrado` | `True` achou titular · `False` sem registro · `None` indeterminado/erro |
| `nome_certidao` | nome do titular — é por ele que o filtro `nome=` decide o match |
| `tem_registro` | há registro na base consultada |
| `cpf_inexistente` | a fonte disse que o CPF não existe (acompanha `encontrado=False`) |
| `mensagem` | texto exibido ao usuário **como veio** — use `MSG_CPF_INEXISTENTE`, `MSG_SEM_REGISTRO`, `MSG_INDETERMINADO` |
| `erro` | só quando a consulta falhou |

Chaves extras (`pdf_url`, `numero_certidao`, `valida_ate`…) são repassadas sem
interpretação. As mensagens são as mesmas em toda fonte: o usuário não deve descobrir qual
respondeu pelo texto. `usa_captcha` (padrão `False`) chega à interface como
`__USA_CAPTCHA__` e escolhe os rótulos dos passos.

O registro (`_REGISTRO`) é **preguiçoso**: a classe só é importada quando usada, para uma
fonte sem CAPTCHA não pagar o import do PyTorch. `tests/test_sources.py` trava isso.

**Adicionar uma fonte:** copie `exemplo.py`, implemente `consultar()`, acrescente uma linha
em `_REGISTRO`. Nenhum router, tool MCP ou parte da interface muda.

#### Fluxo TRT3
1. `GET` do formulário → extrai o `ViewState` do JSF e a URL do CAPTCHA
2. baixa a imagem → resolve com a CRNN local (`app/captcha/`, ~99% de acerto)
3. `POST` com `curl_cffi` impersonando Chrome 124 (o TLS fingerprint importa)
4. CAPTCHA errado → tenta de novo, até `MAX_CAPTCHA_ATTEMPTS` (20)
5. resposta é PDF → `pypdf` + regex extraem nome, CPF e validade
6. CPF não cadastrado e "Falha na Transação" devolvem o formulário — são reconhecidos à
   parte para **não** serem confundidos com CAPTCHA errado (queimariam 20 tentativas)

#### Fluxo TCU
1. `GET /api/publico/captcha` → desafio Altcha (nonce, salt, cost, keyPrefix)
2. resolve o proof-of-work localmente — custa CPU, não visão computacional
3. `POST .../pessoa-fisica` com `{cpf, nome, captcha}`

O desafio vale ~90s e é de uso único: não dá para pré-computar em lote.

### 3. Busca em lote (`sources/__init__.py::consultar_multiplos`)

Agnóstica de fonte. Roda os candidatos num `ThreadPoolExecutor` (o paralelismo vive aqui,
não nos routers), com `workers` limitado a `MAX_WORKERS` e `TASK_TIMEOUT` por consulta.

- Sem `nome`: match é todo resultado com `encontrado is True`.
- Com `nome`: match é o nome contido em `nome_certidao`; e com `parar_ao_confirmar=True`
  (padrão) a busca **para** assim que `nome_confirmado()` casar — as futures pendentes são
  canceladas.
- `nome_confirmado()` exige nomes iguais ou **toda** palavra procurada presente inteira no
  nome encontrado, e recusa filtro de uma palavra só. É a mesma regra do selo
  `✓ Confirmado` da interface, que tem a versão em JS — mude as duas juntas.
- A resposta traz `total`, `consultados`, `interrompido`, `matches` e `resultados`.
- Callbacks de progresso e de match alimentam os endpoints `/stream` (SSE), que a interface
  usa para mostrar resultado ao vivo. Eles ficam fora do schema OpenAPI.

I/O bloqueante das fontes é sempre chamado via `run_in_threadpool` a partir dos handlers
assíncronos.

### 4. Portas de entrada

**REST**

| Método | Rota | Rate limit | Descrição |
|--------|------|------------|-----------|
| GET | `/` | — | interface web |
| POST | `/cpf/validate` | — | valida um CPF (422 se inválido) |
| POST | `/cpf/variations` | — | gera variações válidas |
| POST | `/consulta/cpf` | 10/min por IP | consulta um CPF |
| POST | `/consulta/cpfs` | 5/min por IP | consulta lista em paralelo |
| POST | `/consulta/buscar-por-mascara` | 3/min por IP | candidatos de máscara |
| POST | `/consulta/buscar-por-variacoes` | 3/min por IP | candidatos de CPF errado/parcial |
| GET | `/auth/check` | — | valida o token (401 se inválido) |
| GET | `/health` | — | healthcheck do Docker, sempre aberto |
| GET | `/metrics` | — | Prometheus |

Os limites vêm de `RATE_LIMIT_*`. Atrás de proxy o uvicorn precisa de `--proxy-headers`
(já está no `Dockerfile`), senão todo mundo divide o balde do IP do proxy.

**MCP** — `validate_cpf`, `generate_valid_variations`, `check_cpf`, `find_cpf_by_mask`,
`find_cpf_by_variations`, `check_multiple_cpfs`. Mesma lógica dos routers, mas **erro vira
dicionário** (`{"erro": ...}`) em vez de `HTTPException`, e cada chamada conta em
`mcp_calls_total`. `tests/test_mcp.py` cobre as seis.

**Interface** (`routers/ui.py`) — fluxo de uma busca:
1. tem curinga → máscara; senão valida em `/cpf/validate`
2. CPF inválido → pede `/cpf/variations` e consulta **todas** pelo stream de
   `/consulta/buscar-por-variacoes`. Não há atalho que confirme o primeiro candidato com
   certidão: sem nome informado, isso devolvia o CPF de outra pessoa
3. CPF válido → `/consulta/cpf`
4. mostra `mensagem` como veio da fonte; nada de texto específico de fonte no JS

O JavaScript da interface é testado rodando no Node (`tests/test_ui_js.py`).

### 5. Autenticação (`auth.py`)

- `API_TOKEN` vazio → sem autenticação
- `API_TOKEN` definido → toda rota exige `Authorization: Bearer <token>`, exceto `/` e `/health`
- `ENV=development` → `/docs`, `/redoc`, `/openapi.json` e `/metrics` também abrem
- `ENV=production` → só `/` e `/health` abertos; `METRICS_PUBLIC=true` abre `/metrics`
- O gate da interface valida o token em `/auth/check` — **nunca** numa rota aberta como
  `/health`, senão qualquer token passa
- A comparação é em bytes (`hmac.compare_digest`): com `str`, um caractere não-ASCII
  levantava `TypeError` e virava 500

### 6. Observabilidade

**Métricas** — `consulta_*` valem para qualquer fonte, levam o label `fonte` e são
incrementadas num ponto só (`_consultar_medindo`); `trt3_*` e `tcu_*` são do scraping de
cada uma; `cpf_*`, `mcp_calls_total` e `http_rate_limit_total` são da aplicação.

**Logs** — logger `consulta` (agnóstico, toda linha traz `fonte=`), `trt3` e `tcu`.
`INFO` resultado e lote · `DEBUG` cada tentativa de CAPTCHA e o nome · `WARNING` captcha
esgotado, PDF ilegível, timeout · `ERROR` layout mudou ou desistência.

### 7. Configuração

Tudo em `app/config.py`, com default; `.env.example` lista as variáveis. As que mais
importam: `ENV`, `API_TOKEN`, `SOURCE`, `MAX_CAPTCHA_ATTEMPTS`, `DEFAULT_WORKERS`,
`MAX_WORKERS`, `TASK_TIMEOUT`, `MAX_WILDCARDS_IN_MASK`, `RATE_LIMIT_*`, `LOG_LEVEL`,
`METRICS_PUBLIC`. Variável nova entra em `config.py`, `.env.example`,
`docker-compose.yaml` e na tabela do README.

### 8. Modelo CAPTCHA (`app/captcha/`)

CRNN (4× Conv2D + BatchNorm + 2× BiLSTM + CTC). Modelo ativo em
`app/captcha/captcha_model.pt` (Git LFS); versões em `models/vN/` com `meta.json`.
Retreinar: `python -m app.captcha.train --epochs 120 --batch 128 --lr 1e-3`. Coletar
amostras: `python -m app.captcha.collector --workers N`.

## Testes

`pytest tests/` não toca em rede. `conftest.py` troca o predictor da CRNN por um stub
antes de qualquer import (economia de ~3s de PyTorch). Os parsers do TRT3 são testados
contra `tests/fixtures/`, que são respostas reais com dados fictícios.

| Arquivo | Cobre |
|---------|-------|
| `test_api.py` | rotas REST, autenticação, rate limit |
| `test_mcp.py` | as 6 tools e as variações de CPF |
| `test_cpf_mask.py` | parser de máscaras |
| `test_sources.py` | registro preguiçoso, contrato das fontes, lote |
| `test_tcu.py` | proof-of-work e respostas do TCU |
| `test_trt3_parsers.py`, `test_trt3_falhas.py` | parsing e caminhos de falha do TRT3 |
| `test_logging.py` | CPF mascarado e nome só em DEBUG |
| `test_metrics.py` | `/metrics` de verdade, sem mock |
| `test_ui_js.py` | JavaScript da interface, no Node |

Bug corrigido ganha teste que falharia antes da correção.

## CI e release

- **CI** (`.github/workflows/ci.yml`) — push ou PR no `master`: `ruff check app/` + `pytest`.
- **Release** (`release.yml`) — roda quando o CI do `master` passa. Lê a versão de
  `app/main.py` (`version="X.Y.Z"`); se a tag `vX.Y.Z` **não** existe, publica a imagem em
  `ghcr.io/opastorello/cpf-validador` (`:X.Y.Z` e `:latest`) e cria a release com a seção
  `## vX.Y.Z` recortada do `CHANGELOG.md`.
- Portanto: correção que deve ir ao ar = subir a versão em `main.py` + entrada no
  CHANGELOG, no mesmo commit da correção. O texto do CHANGELOG **vira nota pública de
  release** — vale a regra de não conter dado real.
- Se algo indevido foi publicado: cancele o CI em andamento (para o release não rodar),
  reescreva o commit e use `git push --force-with-lease`. O commit antigo continua
  acessível pelo SHA no GitHub até o suporte purgar.
