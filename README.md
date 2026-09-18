# 🔍 CPF Validador

> Valide CPFs, descubra a quem pertencem e encontre o CPF correto a partir de dígitos parciais ou ilegíveis — com resolução automática de CAPTCHA via rede neural treinada localmente.

Expõe as mesmas operações como **MCP tools** (para agentes AI) e **REST API** (para integrações diretas), com interface web incluída.

---

## 💡 O que este projeto faz

| | |
|--|--|
| ✅ | Valida se um CPF é matematicamente correto |
| 👤 | Confirma a quem um CPF pertence pelo nome |
| 🔎 | Descobre o CPF completo a partir de dígitos parciais ou ilegíveis |
| 👥 | Processa dezenas de CPFs em paralelo |
| 🤖 | Integra com qualquer agente AI via protocolo MCP |

Para confirmar a titularidade de um CPF, o sistema consulta o **TRT3** — que emite certidões públicas associando CPF e nome. A resolução de CAPTCHA é feita por uma **CRNN (Convolutional Recurrent Neural Network)** treinada especificamente para isso, atingindo **~99% de acurácia** sem depender de nenhum serviço externo.

---

## 🤖 MCP Tools

| Tool | Descrição |
| ---- | --------- |
| `validate_cpf` | Valida matematicamente um CPF pelo algoritmo módulo-11 |
| `generate_valid_variations` | Gera as variações válidas a um erro de digitação do CPF: verificadores recalculados, 1 dígito trocado ou par adjacente invertido |
| `check_cpf` | Confirma titularidade de um CPF consultando o TRT3 |
| `find_cpf_by_mask` | Descobre o CPF completo a partir de uma máscara com `*` nos dígitos desconhecidos |
| `find_cpf_by_variations` | Dado um CPF parcial ou errado, encontra o correto filtrando pelo nome |
| `check_multiple_cpfs` | Valida e confirma titularidade de uma lista de CPFs em paralelo |

---

## 🌐 REST API

| Método | Rota | Rate limit | Descrição |
| ------ | ---- | ---------- | --------- |
| `GET`  | `/` | — | Interface web |
| `POST` | `/cpf/validate` | — | Valida um CPF matematicamente |
| `POST` | `/cpf/variations` | — | Gera variações válidas de um CPF |
| `POST` | `/consulta/cpf` | 10/min por IP | Confirma a titularidade de um CPF na fonte ativa |
| `POST` | `/consulta/cpfs` | 5/min por IP | Confirma lista de CPFs em paralelo |
| `POST` | `/consulta/buscar-por-mascara` | 3/min por IP | Descobre CPF por máscara com curingas |
| `POST` | `/consulta/buscar-por-variacoes` | 3/min por IP | Descobre CPF correto a partir de variações |
| `GET`  | `/auth/check` | — | Valida o token — `401` se ausente/incorreto, `200` se válido |
| `GET`  | `/health` | — | Health check — retorna `{"status": "ok"}` |

Documentação interativa: `http://localhost:8000/docs` (disponível apenas em `ENV=development`).

### 📂 Histórico de consultas

O histórico é **local ao navegador** — fica no `localStorage` da interface web e nunca sai do cliente. O servidor não persiste CPFs consultados.

- **Interface web:** o toggle na aba Histórico ativa ou desativa o salvamento automático; a preferência também é salva no `localStorage`.
- **REST API / MCP:** não gravam histórico — cada cliente registra o que quiser do seu lado.
- **Por fonte:** a chave é `cpf::fonte`, então o mesmo CPF consultado no TRT3 e no TCU são duas
  entradas. Certidão é documento de quem emitiu; uma entrada só guardaria um número que não
  corresponde ao que está exibido.

---

## 🏗️ Arquitetura

FastAPI com FastMCP 3.0 montado em `/mcp` (streamable-http). A camada `services/` não tem dependência de framework — a mesma lógica é consumida pelos routers REST e pelo MCP server.

```
app/
├── main.py             # FastAPI — routers + mcp.http_app() em /mcp + rate limiter
├── config.py           # Lê todas as variáveis de ambiente com defaults
├── mcp_server.py       # FastMCP("cpf-validador") — 6 tools
├── auth.py             # TokenMiddleware — autenticação via API_TOKEN + controle prod/dev
├── rate_limit.py       # Limiter compartilhado por main.py e routers/consulta.py
├── metrics.py          # Métricas Prometheus
├── services/
│   ├── cpf.py          # Validação, variações e geração por máscara (zero deps de framework)
│   └── sources/        # Fontes de consulta — escolhidas por SOURCE no .env
│       ├── base.py       # Contrato: ABC Fonte + formato do retorno
│       ├── __init__.py   # Registro + busca em lote paralela (agnóstica de fonte)
│       ├── trt3.py       # TRT3: curl_cffi + CAPTCHA de imagem (CRNN) + pypdf
│       ├── tcu.py        # TCU: API JSON + CAPTCHA Altcha (proof-of-work)
│       └── exemplo.py    # Modelo para novas fontes (fictícia, sem rede)
├── routers/
│   ├── cpf.py          # POST /cpf/validate, POST /cpf/variations
│   ├── consulta.py     # POST /consulta/cpf, /cpfs, /buscar-por-mascara, /buscar-por-variacoes
│   └── ui.py           # GET / — interface web
└── captcha/
    ├── model.py        # Arquitetura CRNN (CNN + BiLSTM + CTC Loss)
    ├── predictor.py    # Inferência: carrega captcha_model.pt e prediz
    ├── dataset.py      # CaptchaDataset com data augmentation
    ├── train.py        # Loop de treino com early stopping + AMP + registry
    ├── collector.py    # Coleta amostras rotuladas direto do TRT3
    ├── registry.py     # Versionamento de modelos (models/vN/model.pt + meta.json)
    └── models/         # Histórico de versões treinadas
```

**Regras de camada:**
- `services/` — zero imports de FastAPI ou FastMCP
- `routers/` e `mcp_server.py` — importam apenas de `services/`, e nunca uma fonte concreta
- I/O bloqueante em `services/sources/` é sempre executado via `run_in_threadpool`

### 🔌 Fontes de consulta

A pergunta "a quem pertence este CPF?" é respondida por uma **fonte**. A fonte ativa vem de
`SOURCE` no `.env`:

| `SOURCE` | Fonte | Abrangência | CAPTCHA |
| -------- | ----- | ----------- | ------- |
| `trt3` *(padrão)* | TRT 3ª Região — feitos trabalhistas | Minas Gerais | imagem, resolvida por CRNN local |
| `tcu` | TCU — contas julgadas irregulares | Nacional | Altcha (proof-of-work, via [`altcha-solver`](https://github.com/opastorello/altcha-solver)) |
| `exemplo` | Dados fictícios, não consulta nada | — | nenhum |

As duas fontes reais não se parecem em nada por dentro, e é essa a prova de que a camada
funciona: o TRT3 é um formulário JSF com `ViewState`, CAPTCHA de imagem e resposta em PDF;
o TCU é uma API JSON cujo CAPTCHA é um **proof-of-work** — o cliente procura um contador
cujo `PBKDF2-HMAC-SHA256` comece com um prefixo dado, gastando CPU em vez de visão
computacional. Nenhum router, tool MCP ou a lógica de máscara precisou mudar para a
segunda entrar.

Cada fonte decide sozinha **como** consulta — cliente HTTP, autenticação, CAPTCHA ou a
ausência dele, parsing da resposta e limite de conexões simultâneas. A camada comum
padroniza apenas o formato do resultado.

A fonte também declara o que sabe fazer, e a interface se adapta: uma fonte com
`usa_captcha = False` mostra "Consulta concluída" no lugar de "CAPTCHA resolvido", em vez
de anunciar um trabalho que não aconteceu.

#### Imagem sem PyTorch

O PyTorch existe só para a CRNN que lê o CAPTCHA de imagem do TRT3 — são ~780 MB, 44% da
imagem. O CAPTCHA do TCU é proof-of-work, resolvido com a biblioteca padrão. Se você não
vai usar `SOURCE=trt3`:

```bash
docker build --build-arg COM_TRT3=false .   # 473 MB em vez de 1.76 GB
```

Subir essa imagem com `SOURCE=trt3` falha no boot com a instrução de como instalar, em vez
de subir e quebrar na primeira consulta.

#### Escrevendo uma fonte nova

Copie `app/services/sources/exemplo.py` — ele tem os cinco passos de uma consulta
comentados — implemente `consultar()` e registre a classe:

```python
class TRT2(Fonte):
    nome = "trt2"                       # o valor usado em SOURCE=
    rotulo = "TRT 2ª Região (SP)"       # texto legível, aparece no log e na UI
    usa_captcha = True                  # padrão é False

    def consultar(self, cpf_limpo: str) -> dict:
        ...
```

E registre:

```python
# app/services/sources/__init__.py
_REGISTRO = {
    "trt3":    ("app.services.sources.trt3",    "TRT3",    "TRT 3ª Região"),
    "trt2":    ("app.services.sources.trt2",    "TRT2",    "TRT 2ª Região (SP)"),  # nova
}
```

O contrato do retorno é este — só estas chaves são interpretadas:

```python
{
    "cpf": "151.879.820-95",       # obrigatório, formatado
    "encontrado": True,            # True achou | False não consta | None erro
    "nome_certidao": "FULANO",     # o filtro nome= das buscas em lote depende desta chave
    "tem_registro": False,         # a certidão é positiva? (há processo/conta irregular)
    "cpf_inexistente": False,      # a fonte não reconhece o CPF — acompanha encontrado=False
    "mensagem": "...",             # texto exibido ao usuário; use as constantes MSG_* de base.py
    "erro": "...",                 # só quando a consulta falhou
}
```

`consultar()` **não deve levantar exceção**: falha vira `encontrado: None` + `erro`. Quem
chama roda centenas em paralelo e trata ausência de resultado, não stack trace.

Nenhum router, tool MCP ou a lógica de máscara/variações precisa mudar — todos falam com a
fonte ativa através de `sources.consultar()` e `sources.consultar_multiplos()`.

---

## ⚙️ Configuração

Todas as opções são lidas de variáveis de ambiente ou do arquivo `.env` na raiz do projeto.

### Referência completa de variáveis

| Variável | Padrão | Descrição |
| -------- | ------ | --------- |
| `API_TOKEN` | *(vazio — sem auth)* | Token Bearer. Se vazio, todos os endpoints ficam abertos |
| `ENV` | `development` | `development` ou `production` — controla quais rotas ficam abertas sem token |
| `SOURCE` | `trt3` | Fonte consultada: `trt3`, `tcu` ou `exemplo` |
| `TCU_BASE_URL` | `https://certidoes.apps.tcu.gov.br` | Base da API do TCU |
| `TCU_POW_MAX_COUNTER` | `200000` | Teto da busca do proof-of-work (na prática o contador fica abaixo de 5.000) |
| `TCU_MAX_ATTEMPTS` | `3` | Tentativas por consulta ao TCU (o desafio vale ~90s e é de uso único) |
| `TRT3_BASE_URL` | `https://certidao.trt3.jus.br` | URL base do site do TRT3 |
| `TRT3_FORM_PATH` | `/certidao/feitosTrabalhistas/aba1.emissao.htm` | Path do formulário de consulta |
| `HTTP_TIMEOUT` | `30` | Timeout (segundos) para requisições HTTP ao TRT3 |
| `CAPTCHA_TIMEOUT` | `15` | Timeout (segundos) para download da imagem CAPTCHA |
| `MAX_CAPTCHA_ATTEMPTS` | `20` | Tentativas máximas de resolver o CAPTCHA antes de desistir |
| `RETRY_DELAY` | `1.0` | Segundos de espera entre tentativas de CAPTCHA |
| `DEFAULT_WORKERS` | `8` | Threads paralelas padrão nas consultas em lote |
| `MAX_WORKERS` | `20` | Limite máximo de `workers` que o cliente pode solicitar |
| `TASK_TIMEOUT` | `60` | Timeout (segundos) por CPF individual em consultas paralelas |
| `MAX_WILDCARDS_IN_MASK` | `5` | Máximo de curingas na parte base da máscara (evita explosão combinatória) |
| `RATE_LIMIT_CPF` | `10/minute` | Rate limit de `/consulta/cpf` por IP |
| `RATE_LIMIT_CPFS` | `5/minute` | Rate limit de `/consulta/cpfs` por IP |
| `RATE_LIMIT_MASK` | `3/minute` | Rate limit de `/consulta/buscar-por-mascara` por IP |
| `RATE_LIMIT_VARIACOES` | `3/minute` | Rate limit de `/consulta/buscar-por-variacoes` por IP |
| `CAPTCHA_MODEL_PATH` | *(vazio — usa `app/captcha/captcha_model.pt`)* | Path absoluto para o modelo `.pt` (útil para montar modelo externo) |
| `METRICS_PUBLIC` | `false` | `true` abre `/metrics` sem token também em `production` |
| `LOG_LEVEL` | `INFO` | Nível de log da consulta ao TRT3. `DEBUG` mostra cada tentativa de CAPTCHA |
| `FORWARDED_ALLOW_IPS` | `*` | Proxies em que confiar para ler `X-Forwarded-For`. Necessário para o rate limit contar por IP real atrás de proxy |

### 🔒 Rotas abertas por ambiente

| Rota | `development` | `production` |
| ---- | :-----------: | :----------: |
| `/` | ✅ aberta | ✅ aberta |
| `/health` | ✅ aberta | ✅ aberta |
| `/docs` | ✅ aberta | 🔒 token |
| `/redoc` | ✅ aberta | 🔒 token |
| `/openapi.json` | ✅ aberta | 🔒 token |
| `/metrics` | ✅ aberta | 🔒 token *(ou `METRICS_PUBLIC=true`)* |
| `/mcp` | 🔒 token | 🔒 token |
| demais | 🔒 token | 🔒 token |

> Se `API_TOKEN` estiver vazio, o middleware ignora autenticação em qualquer ambiente.

---

## 🔐 Autenticação

Com `API_TOKEN` configurado, todas as requisições protegidas precisam enviar:

```
Authorization: Bearer meu-token-secreto
```

**REST:**

```bash
curl -X POST http://localhost:8000/consulta/cpf \
  -H "Authorization: Bearer meu-token-secreto" \
  -H "Content-Type: application/json" \
  -d '{"cpf": "151.879.820-95"}'
```

**Claude Desktop / Claude Code (`claude_desktop_config.json`):**

```json
{
  "mcpServers": {
    "cpf-validador": {
      "command": "npx",
      "args": ["mcp-remote", "http://localhost:8000/mcp", "--allow-http"],
      "env": {
        "MCP_REMOTE_HEADER_AUTHORIZATION": "Bearer meu-token-secreto"
      }
    }
  }
}
```

A interface web (`/`) exibe um **gate de autenticação** quando `API_TOKEN` está definido — o token é validado contra o servidor e salvo no navegador.

---

## 📊 Métricas

`GET /metrics` expõe métricas Prometheus. Os nomes separam o que vale para qualquer fonte do
que é de uma só:

| Prefixo | Exemplos | O que mede |
| ------- | -------- | ---------- |
| `consulta_*` | `consulta_queries_total{fonte,result}`, `consulta_duration_seconds{fonte}`, `consulta_cpf_total`, `consulta_matches_total` | A consulta em si, com label `fonte`. Contadas num ponto só, então toda fonte é medida igual |
| `trt3_*` | `trt3_captcha_attempts_total`, `trt3_captcha_result_total`, `trt3_pdf_parsed_total`, `trt3_session_resets_total` | Específicas do scraping do TRT3 |
| `tcu_*` | `tcu_pow_duration_seconds`, `tcu_pow_counter`, `tcu_concurrent_queries`, `tcu_http_errors_total` | Específicas do proof-of-work do TCU |
| `cpf_*` | `cpf_validations_total`, `cpf_mask_searches_total`, `cpf_bulk_size` | Operações de CPF, sem rede |
| — | `mcp_calls_total{tool,result}`, `http_rate_limit_total{endpoint}` | Uso da aplicação |

O resultado de `consulta_queries_total` distingue `found`, `not_found`, `not_registered`
(o CPF não existe na base), `indeterminate` e `error`.

Em `production` a rota exige token; `METRICS_PUBLIC=true` abre. Configure `bearer_token` no
Prometheus se mantiver fechada.

---

## 🚀 Instalação

### Docker (recomendado)

```bash
git clone https://github.com/opastorello/cpf-validador.git
cd cpf-validador
cp .env.example .env   # edite se quiser definir API_TOKEN
docker compose up --build -d
```

### Local

```bash
pip install -r requirements-trt3.txt   # inclui o PyTorch da CRNN do TRT3
# sem usar SOURCE=trt3? `pip install -r requirements.txt` basta e evita ~780 MB
cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Após iniciar:
- Interface web: `http://localhost:8000/`
- REST docs: `http://localhost:8000/docs` *(apenas em `ENV=development`)*
- MCP endpoint: `http://localhost:8000/mcp`

---

## 📋 Exemplos de uso

### Validar um CPF

```bash
curl -X POST http://localhost:8000/cpf/validate \
  -H "Content-Type: application/json" \
  -d '{"cpf": "151.879.820-95"}'
```

### Confirmar titularidade

```bash
curl -X POST http://localhost:8000/consulta/cpf \
  -H "Content-Type: application/json" \
  -d '{"cpf": "151.879.820-95"}'
```

```json
{
  "cpf": "151.879.820-95",
  "encontrado": true,
  "nome_certidao": "JOAO DA SILVA",
  "valida_ate": "18/04/2026",
  "numero_certidao": "2026/123456"
}
```

### Descobrir CPF por máscara

Quando você conhece apenas parte dos dígitos — substitua os desconhecidos por `*`:

```bash
curl -X POST http://localhost:8000/consulta/buscar-por-mascara \
  -H "Content-Type: application/json" \
  -d '{"mascara": "***.123.456-**", "nome": "João Silva"}'
```

O servidor gera todas as combinações válidas para as posições curinga, consulta em paralelo e retorna apenas os matches com o nome informado.

**A busca para assim que confirma o nome.** Confirmar segue a mesma regra do selo `✓ Confirmado`
da interface: nomes iguais, ou toda palavra procurada aparecendo inteira no nome encontrado —
`MARIA SILVA` confirma `MARIA APARECIDA SILVA`, mas `SILVA` sozinho não confirma, senão pararia
no primeiro homônimo parcial. Numa máscara de 1.000 candidatos isso costuma cortar metade das
consultas ao serviço externo. A resposta traz `consultados` e `interrompido`, e
`parar_ao_confirmar: false` desliga quando você quiser listar homônimos.

**Formatos de máscara aceitos.** Os curingas `*`, `X`, `x`, `?`, `_` e `#` são equivalentes, os separadores `.`, `-`, `/` e espaços são ignorados (inclusive nenhum separador), e os dígitos verificadores podem ser omitidos. Todas estas máscaras são a mesma coisa:

```
***.879.820-**      ← mascaramento LGPD de documento público
***879820**         ← sem separador
*** 879 820 **      ← separado por espaço
XXX.879.820-XX      ← anotação manual
???.879.820-??
___.879.820-__      ← campo de formulário
###.879.820-##      ← planilha
***.879.820         ← dígitos verificadores omitidos
```

Um caractere que não seja dígito, curinga ou separador é rejeitado com `422` apontando qual é — em vez de ser descartado silenciosamente e virar erro de tamanho.

> Máximo de 5 wildcards na parte base (posições 0–8) = até 100.000 combinações. Configurável via `MAX_WILDCARDS_IN_MASK`.

### Recuperar CPF com erros ou dígito faltando

```bash
curl -X POST http://localhost:8000/consulta/buscar-por-variacoes \
  -H "Content-Type: application/json" \
  -d '{"cpf_parcial": "1518798209", "nome": "joao"}'
```

### Consulta em lote

```bash
curl -X POST http://localhost:8000/consulta/cpfs \
  -H "Content-Type: application/json" \
  -d '{"cpfs": ["151.879.820-95", "151.879.821-76"], "workers": 4}'
```

---

## 🧠 Modelo de CAPTCHA

### Arquitetura CRNN

```
Input (1×60×160)
    → Conv2D ×4 + BatchNorm + ReLU + MaxPool   (extração de features visuais)
    → BiLSTM ×2 (128 hidden, bidirectional)    (modelagem de sequência)
    → Linear → CTC Loss                         (decode sem segmentação)
Output: string de 5 caracteres [0-9a-z]
```

### Bootstrapping em 3 rodadas

| Rodada | Amostras | Rotulador | Acurácia dos labels | Acurácia do modelo |
| ------ | -------- | --------- | :-----------------: | :----------------: |
| 1 | 15.000 | ddddocr (OCR genérico) | ~43% | **98.70%** |
| 2 | 20.000 | Modelo R1 | ~96% | **98.80%** |
| 3 | 20.000 | Modelo R2 | ~99.3% | **98.55%** |

**Total: 55.000 amostras.** O modelo final (v1) convergiu na época 106/120 com `val_loss=0.0072`.

### Hiperparâmetros

- **Optimizer:** AdamW | **LR:** 1e-3 com CosineAnnealingLR
- **Epochs:** 120 com early stopping (patience: 20)
- **Batch size:** 128 | **Treino:** GPU com AMP float16 via `torch.amp.autocast`
- **Inferência:** CPU-only (Docker)
- **Augmentation:** rotação, shear, translate, color jitter, gaussian blur, random erasing

---

## Treinar o modelo

**1. Coletar amostras**

```bash
python -m app.captcha.collector --cpf 000.000.000-00 --target 15000 --workers 4
```

**2. Treinar**

```bash
python -m app.captcha.train --epochs 120 --batch 128 --lr 1e-3
```

O melhor modelo (menor `val_loss`) é salvo em `app/captcha/captcha_model.pt`.

**3. Bootstrap (melhora qualidade dos labels)**

```bash
rm -rf app/captcha/data/
python -m app.captcha.collector --cpf 000.000.000-00 --target 20000 --workers 4
python -m app.captcha.train --epochs 120 --batch 128 --lr 1e-3
```

Repita 2–3 rodadas até a acurácia estabilizar. Para consultar o histórico de versões:

```bash
python -m app.captcha.registry
```

---

## 📦 Dependências principais

| Pacote | Uso |
| ------ | --- |
| [FastMCP](https://github.com/jlowin/fastmcp) | Framework MCP server |
| [FastAPI](https://github.com/fastapi/fastapi) | REST API |
| [slowapi](https://github.com/laurentS/slowapi) | Rate limiting por IP |
| [curl-cffi](https://github.com/yifeikong/curl-cffi) | HTTP com impersonação TLS Chrome-124 |
| [altcha-solver](https://github.com/opastorello/altcha-solver) | Proof-of-work do CAPTCHA Altcha (fonte TCU) |
| [PyTorch](https://github.com/pytorch/pytorch) | Rede neural CRNN para o CAPTCHA de imagem (fonte TRT3, opcional) |
| [torchvision](https://github.com/pytorch/vision) | Transforms e augmentation de imagem (fonte TRT3, opcional) |
| [pypdf](https://github.com/py-pdf/pypdf) | Extração de dados do PDF de certidão |
| [Pillow](https://github.com/python-pillow/Pillow) | Processamento de imagem |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | Carregamento de variáveis do `.env` |

---

## 🗺️ Roadmap

Ideias e melhorias planejadas para versões futuras.

### Escalabilidade
- **Worker distribuído** — arquitetura de fila (Redis + worker nodes) onde cada nó é uma VPS com IP próprio contribuindo com slots de conexão ao TRT3. Escala horizontalmente: 1 worker = 20 slots, 5 workers = 100 slots, IPs diferentes reduzem risco de throttling.
- **Cache de resultados** — CPFs já consultados recentemente retornam resultado armazenado sem nova requisição ao TRT3. Reduz latência e carga no tribunal.

### Multi-usuário
- **Quota de consultas por token** — cada token teria um limite mensal/diário de consultas configurável independentemente do rate limit por IP. Ex: token A = 1.000 consultas/dia, token B = 10.000/dia.
- **Workers por token** — cada token teria um número máximo de workers simultâneos ao TRT3. Ex: token gratuito = 2 workers, token premium = 20 workers. Garante que um único cliente não monopoliza a capacidade do servidor enquanto outros aguardam.

### Cobertura
- **Suporte a outros tribunais** — expandir para TRT1 (RJ), TRT2 (SP) e demais regiões, consolidando resultados em uma única consulta.
- **Consulta à Receita Federal** — validar situação cadastral do CPF diretamente na base da RF.

### Observabilidade
- **Dashboard de uso** — visualizar volume de consultas, taxa de acerto do CAPTCHA e latência média por endpoint.
- **Alerta de bloqueio** — detectar automaticamente quando o TRT3 começa a retornar erros acima do normal e notificar.

---

## ⚖️ Responsabilidade de Uso

Este projeto consulta exclusivamente o sistema público do **TRT3** ([certidao.trt3.jus.br](https://certidao.trt3.jus.br)) — os mesmos dados acessíveis por qualquer pessoa pelo navegador, sem login ou cadastro. As certidões emitidas são documentos públicos por determinação legal.

**Usos adequados:**
- Due diligence em processos de contratação
- Verificação de titularidade em contextos jurídicos ou de compliance
- Integração com agentes AI para automação de processos legítimos

**O projeto não se destina a:**
- Varredura em massa sem finalidade específica
- Coleta de dados para fins não autorizados pela LGPD
- Qualquer uso que viole a legislação brasileira vigente

O código é aberto e auditável. A responsabilidade pelo uso é inteiramente do operador que implanta e utiliza o serviço. Rate limiting está configurado por padrão para desincentivar abuso.

---

## 📄 Licença

[MIT](LICENSE) © 2026 Nícolas Pastorello
