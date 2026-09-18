import re

from fastmcp import FastMCP
from starlette.concurrency import run_in_threadpool

from app import config as _cfg
from app import metrics as _m
from app.services.cpf import formatar, gerar_cpfs_de_mascara, is_valido
from app.services.cpf import generate_valid_variations as _generate_valid_variations
from app.services.cpf import validate_cpf as _validate_cpf
from app.services.sources import consultar as consultar_fonte
from app.services.sources import consultar_multiplos

mcp = FastMCP("cpf-validador")


@mcp.tool
def validate_cpf(cpf: str) -> dict:
    """Valida se um CPF é matematicamente válido (dígitos verificadores corretos)."""
    result = _validate_cpf(cpf)
    label = "valid" if result.get("valido") else "invalid"
    _m.mcp_calls_total.labels(tool="validate_cpf", result=label).inc()
    return result


@mcp.tool
def generate_valid_variations(cpf: str) -> dict:
    """Gera variações matematicamente válidas de um CPF possivelmente errado.
    Estratégias: original, recalcula dígitos verificadores, troca 1 dígito (qualquer das 11 posições, mantendo os demais), transpõe pares adjacentes."""
    result = _generate_valid_variations(cpf)
    if "error" in result:
        _m.mcp_calls_total.labels(tool="generate_valid_variations", result="invalid").inc()
    else:
        _m.mcp_calls_total.labels(tool="generate_valid_variations", result="success").inc()
        _m.cpf_variations_generated_total.inc(result.get("total_variacoes", 0))
    return result


@mcp.tool
async def check_cpf(cpf: str) -> dict:
    """Consulta um CPF na fonte configurada (SOURCE) e devolve a certidão.
    Valida o CPF, resolve o captcha da fonte automaticamente e retorna o resultado."""
    cpf_limpo = re.sub(r"\D", "", cpf)
    if len(cpf_limpo) != 11:
        _m.mcp_calls_total.labels(tool="check_cpf", result="invalid").inc()
        return {"erro": f"CPF deve ter 11 dígitos, recebido {len(cpf_limpo)}"}
    if not is_valido(cpf_limpo):
        _m.mcp_calls_total.labels(tool="check_cpf", result="invalid").inc()
        return {"erro": "CPF matematicamente inválido", "cpf": formatar(cpf_limpo)}
    result = await run_in_threadpool(consultar_fonte, cpf_limpo)
    if result.get("encontrado"):
        _m.mcp_calls_total.labels(tool="check_cpf", result="found").inc()
        _m.consulta_matches_total.labels(fonte=_cfg.SOURCE, type="mcp_cpf").inc()
    elif result.get("erro"):
        _m.mcp_calls_total.labels(tool="check_cpf", result="error").inc()
    else:
        _m.mcp_calls_total.labels(tool="check_cpf", result="not_found").inc()
    return result


@mcp.tool
async def find_cpf_by_mask(mascara: str, nome: str | None = None, workers: int = 8,
                           parar_ao_confirmar: bool = True) -> dict:
    """Descobre o CPF completo a partir de uma máscara com curingas nos dígitos desconhecidos.
    Gera todas as combinações matematicamente válidas e consulta o TRT3 em paralelo.
    Se 'nome' for informado, filtra somente os resultados que contenham o nome na certidão.

    Args:
        mascara: CPF com curingas nos dígitos desconhecidos. Curingas equivalentes: * X x ? _ #
            Separadores (. - / espaço) são ignorados e os dígitos verificadores podem ser omitidos,
            então '***.879.820-**', '***879820**', '___.879.820-__' e '***.879.820' são a mesma máscara.
            Ex: '15X.879.82X-95', '***.879.820-**', '151.879.820'
        nome: nome ou parte do nome para filtrar (ex: 'Italvino Rebelatto')
        workers: número de threads paralelas (padrão 8)
        parar_ao_confirmar: interrompe assim que um resultado confirmar o 'nome'
            informado, em vez de varrer todos os candidatos. Sem 'nome' não tem efeito
    """
    workers = max(1, min(workers, 20))
    try:
        candidates = gerar_cpfs_de_mascara(mascara)
    except ValueError as e:
        _m.mcp_calls_total.labels(tool="find_cpf_by_mask", result="invalid").inc()
        return {"erro": str(e)}

    if not candidates:
        _m.mcp_calls_total.labels(tool="find_cpf_by_mask", result="invalid").inc()
        return {"erro": "Nenhum CPF válido gerado pela máscara", "mascara": mascara}

    _m.cpf_mask_searches_total.inc()
    _m.cpf_mask_candidates_total.inc(len(candidates))
    resultado = await run_in_threadpool(consultar_multiplos, candidates, nome, workers,
                                        parar_ao_confirmar=parar_ao_confirmar)
    resultado["candidatos_gerados"] = len(candidates)
    matches = len(resultado.get("matches", {}))
    _m.mcp_calls_total.labels(tool="find_cpf_by_mask", result="success" if matches else "not_found").inc()
    if matches:
        _m.consulta_matches_total.labels(fonte=_cfg.SOURCE, type="mcp_mascara").inc(matches)
    return resultado


@mcp.tool
async def find_cpf_by_variations(cpf_parcial: str, nome: str | None = None, workers: int = 8,
                                 parar_ao_confirmar: bool = True) -> dict:
    """Dado um CPF parcial ou com erros, encontra o CPF correto filtrando pelo nome.
    Gera todas as variações matematicamente válidas e consulta o TRT3 em paralelo.
    Ideal para recuperar um CPF com um dígito faltando ou digitado errado.

    Args:
        cpf_parcial: CPF com dígitos faltando ou errados (9 a 11 dígitos)
        nome: nome ou parte do nome para filtrar (ex: 'nicolas', 'pastorello')
        workers: número de threads paralelas (padrão 8)
        parar_ao_confirmar: interrompe assim que um resultado confirmar o 'nome'
            informado, em vez de varrer todos os candidatos. Sem 'nome' não tem efeito
    """
    workers = max(1, min(workers, 20))
    from app.services.cpf import generate_valid_variations

    cpf_limpo = re.sub(r"\D", "", cpf_parcial)

    candidates = set()

    if len(cpf_limpo) == 11:
        result = generate_valid_variations(cpf_limpo)
        candidates = {v["cpf_numeros"] for v in result.get("variations", [])}
    else:
        base = cpf_limpo
        for pos in range(11):
            for digit in "0123456789":
                c = base[:pos] + digit + base[pos:]
                if is_valido(c):
                    candidates.add(c)
        for wrong_pos in range(len(base)):
            for wrong_digit in "0123456789":
                if wrong_digit == base[wrong_pos]:
                    continue
                modified = base[:wrong_pos] + wrong_digit + base[wrong_pos + 1:]
                for pos in range(11):
                    for digit in "0123456789":
                        c = modified[:pos] + digit + modified[pos:]
                        if is_valido(c):
                            candidates.add(c)

    if not candidates:
        _m.mcp_calls_total.labels(tool="find_cpf_by_variations", result="invalid").inc()
        return {"erro": "Nenhum candidato válido gerado", "cpf_parcial": cpf_parcial}

    _m.cpf_variation_searches_total.inc()
    _m.cpf_variation_candidates_total.inc(len(candidates))
    resultado = await run_in_threadpool(
        consultar_multiplos, list(candidates), nome, workers,
        parar_ao_confirmar=parar_ao_confirmar,
    )
    resultado["candidatos_gerados"] = len(candidates)
    matches = len(resultado.get("matches", {}))
    _m.mcp_calls_total.labels(tool="find_cpf_by_variations", result="success" if matches else "not_found").inc()
    if matches:
        _m.consulta_matches_total.labels(fonte=_cfg.SOURCE, type="mcp_variacoes").inc(matches)
    return resultado


@mcp.tool
async def check_multiple_cpfs(cpfs: list[str], workers: int = 8) -> dict:
    """Valida e confirma titularidade de uma lista de CPFs em paralelo consultando o TRT3.
    CPFs inválidos são agrupados no campo 'erros' sem interromper os demais.
    'total' conta os CPFs recebidos; 'total_consultados', os que foram consultados.

    Args:
        cpfs: lista de CPFs (aceita com ou sem formatação)
        workers: número de threads paralelas (padrão 8)
        parar_ao_confirmar: interrompe assim que um resultado confirmar o 'nome'
            informado, em vez de varrer todos os candidatos. Sem 'nome' não tem efeito
    """
    workers = max(1, min(workers, 20))
    cpfs_validos = []
    erros = {}

    for cpf in cpfs:
        cpf_limpo = re.sub(r"\D", "", cpf)
        if len(cpf_limpo) != 11:
            erros[cpf] = {"erro": f"CPF deve ter 11 dígitos, recebido {len(cpf_limpo)}"}
        elif not is_valido(cpf_limpo):
            erros[cpf] = {"erro": "CPF matematicamente inválido", "cpf": formatar(cpf_limpo)}
        else:
            cpfs_validos.append(cpf_limpo)

    if erros:
        _m.cpf_bulk_invalid_total.inc(len(erros))

    if not cpfs_validos:
        _m.mcp_calls_total.labels(tool="check_multiple_cpfs", result="invalid").inc()
        return {"total": len(cpfs), "total_consultados": 0, "erros": erros,
                "resultados": {}, "matches": {}}

    _m.cpf_bulk_queries_total.inc()
    _m.cpf_bulk_size.observe(len(cpfs_validos))
    resultado = await run_in_threadpool(consultar_multiplos, cpfs_validos, None, workers)
    # "total" = recebidos, "total_consultados" = os válidos que foram consultados
    resultado["total_consultados"] = resultado["total"]
    resultado["total"] = len(cpfs)
    resultado["erros"] = erros
    matches = len(resultado.get("matches", {}))
    _m.mcp_calls_total.labels(tool="check_multiple_cpfs", result="success" if matches else "not_found").inc()
    if matches:
        _m.consulta_matches_total.labels(fonte=_cfg.SOURCE, type="mcp_multiplos").inc(matches)
    return resultado
