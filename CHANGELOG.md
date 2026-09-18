# Changelog

## v2.0.2

- **CPF com um dígito errado gerava 82 variações** em vez de uma ou duas. A
  estratégia "troca 1 dígito" trocava um dígito da base e *recalculava* os
  verificadores — e como toda base de 9 dígitos tem verificadores válidos, as
  81 trocas possíveis passavam, produzindo candidatos a até 3 dígitos do CPF
  informado. A troca agora vale para qualquer das 11 posições e mantém os
  outros 10 dígitos como digitados: `151.879.820-98` gera só `151.879.820-95`.
  A busca por variações consulta a fonte muito menos vezes para chegar ao
  mesmo resultado.

## v2.0.1

- **Token com caractere não-ASCII derrubava a rota com 500** em vez de devolver
  401. `hmac.compare_digest` com `str` exige ASCII dos dois lados e levanta
  `TypeError` fora disso; como o cabeçalho HTTP é latin-1, bastava um acento no
  token guardado no navegador para o middleware estourar — e qualquer cliente
  podia provocar erro no servidor de propósito. A comparação passa a ser em
  bytes, que vale para qualquer entrada e continua sendo de tempo constante.

## v2.0.0

Consultar CPF deixou de ser "consultar o TRT3". A aplicação passa a ter uma
camada de fontes, e o TRT3 virou uma delas.

### ⚠️ Quebras de compatibilidade

| O que | Antes | Agora |
| ----- | ----- | ----- |
| Rotas | `POST /trt3/feitos`, `/trt3/feitos-multiplos` | `POST /consulta/cpf`, `/consulta/cpfs` |
| Tool MCP | `check_feitos_trabalhistas` | `check_cpf` |
| Campo da resposta | `tem_feitos` | `tem_registro` |
| Rate limit | `RATE_LIMIT_FEITOS`, `RATE_LIMIT_MULTIPLOS` | `RATE_LIMIT_CPF`, `RATE_LIMIT_CPFS` |
| Métricas | `trt3_queries_total`, `trt3_feitos_total`, `trt3_matches_total`, `trt3_rate_limit_total`, `trt3_mcp_calls_total` | `consulta_queries_total{fonte}`, `consulta_cpf_total{fonte}`, `consulta_matches_total{fonte}`, `http_rate_limit_total`, `mcp_calls_total` |
| Histórico | `/history/*` server-side | `localStorage` do navegador |

Dashboards que usem os nomes antigos de métrica precisam ser atualizados, e
clientes que chamem `/trt3/*` recebem `404`.

### Fontes de consulta

- Camada `services/sources/` com contrato explícito (`base.Fonte`): cada fonte é
  dona do próprio jeito de consultar — cliente HTTP, autenticação, CAPTCHA ou a
  ausência dele, parsing e limite de conexões
- **TCU** (`SOURCE=tcu`) — certidão de contas julgadas irregulares, cobertura
  nacional, CAPTCHA Altcha resolvido por proof-of-work
- **TRT3** (`SOURCE=trt3`, padrão) — feitos trabalhistas em Minas, CAPTCHA de
  imagem lido pela CRNN local
- **exemplo** (`SOURCE=exemplo`) — dados fictícios, sem rede, modelo para novas
  fontes
- Registro preguiçoso: uma fonte sem CAPTCHA não carrega o PyTorch de quem tem
- `SOURCE` inválido derruba o boot em vez de falhar na primeira consulta

### Correções

- **Gate de autenticação aceitava qualquer token** — validava contra `/health`,
  que é rota aberta. Agora usa `/auth/check`
- **`/metrics` estava aberto em produção**, expondo volume de consultas e taxa
  de acerto do CAPTCHA
- **Rate limit era global atrás de proxy** — sem `--proxy-headers`, todo mundo
  chegava com o IP do proxy e dividia o mesmo balde
- **CPF não cadastrado queimava 20 CAPTCHAs** — o TRT3 devolve o formulário, que
  era lido como captcha errado. Numa máscara de 1.000 candidatos isso
  multiplicava por 20 as requisições ao tribunal
- **"Falha na Transação" do TRT3** tinha o mesmo problema: 47s e uma mensagem
  que apontava para a causa errada
- **`cpf_certidao` nunca era retornado** — o padrão exigia o número colado em
  "CPF", mas o texto real é "no CPF sob o nº ..."
- **Histórico misturava fontes** — a chave era só o CPF, então o número de
  certidão de uma fonte sobrescrevia o da outra
- `total` no lote mudava de significado conforme houvesse ou não algum CPF
  válido; agora há `total` e `total_consultados`

### Melhorias

- **Máscaras aceitam qualquer formato**: curingas `* X x ? _ #`, separadores
  `. - / espaço` ou nenhum, e dígitos verificadores omitidos
- **A busca para ao confirmar o nome** — numa máscara de 1.000 candidatos,
  costuma cortar metade das consultas ao serviço externo
- **Logs do processo de consulta**, com CPF mascarado (`111.***.***-35`) e nome
  só em `DEBUG`
- Métricas separadas entre o que vale para qualquer fonte (`consulta_*{fonte}`)
  e o que é de uma só (`trt3_*`, `tcu_*`)
- Interface mostra qual fonte respondeu e adapta os rótulos à capacidade dela —
  uma fonte sem CAPTCHA não anuncia "CAPTCHA resolvido"
- Mensagens padronizadas entre fontes: o usuário não descobre qual respondeu
  pelo texto
- Imagem Docker sem PyTorch com `--build-arg COM_TRT3=false`: **473 MB** em vez
  de 1.76 GB

### Testes

De 11 para 116, cobrindo parsers do TRT3 com fixtures da resposta real, o
proof-of-work do TCU, as 6 tools MCP, `/metrics` sem mock, os caminhos de falha
e o JavaScript da interface rodando no Node.

---

## v1.0.0

Primeira versão: validação de CPF, geração de variações, busca por máscara e
consulta ao TRT3 com CAPTCHA resolvido por CRNN local, expostas via REST e MCP.
