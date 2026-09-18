"""
As 6 tools MCP.

Eram a maior superfície sem teste do projeto: mesma lógica de negócio dos
routers, mas com validação, contagem de métricas e formato de erro próprios —
e nada disso passava pelo CI. As tools devolvem erro em dicionário em vez de
levantar HTTPException, então é justamente aí que os dois caminhos divergem.
"""
from unittest.mock import patch

import pytest

from app.mcp_server import (
    check_cpf,
    check_multiple_cpfs,
    find_cpf_by_mask,
    find_cpf_by_variations,
    generate_valid_variations,
    validate_cpf,
)

CPF = "151.879.820-95"
CPF_LIMPO = "15187982095"
ENCONTRADO = {"cpf": CPF, "encontrado": True, "nome_certidao": "FULANO DE TAL"}


def _lote(cpfs, nome=None, workers=None, **kw):
    """Substitui a consulta em lote sem tocar em rede."""
    return {"total": len(cpfs), "consultados": len(cpfs), "interrompido": False,
            "matches": {}, "resultados": {c: ENCONTRADO for c in cpfs}}


# ── tools puras ────────────────────────────────────────────────────────────

def test_validate_cpf():
    assert validate_cpf(CPF)["valido"] is True
    assert validate_cpf("111.111.111-11")["valido"] is False


def test_generate_valid_variations():
    r = generate_valid_variations(CPF)
    assert r["total_variacoes"] > 0
    assert all(v["cpf_numeros"] for v in r["variations"])


def test_variacoes_ficam_a_um_digito_do_informado():
    # 151.879.820-98 tem só o último dígito errado. Recalcular os verificadores
    # a cada troca na base aceitava as 81 trocas possíveis — 82 "variações".
    r = generate_valid_variations("151.879.820-98")
    assert [v["cpf_numeros"] for v in r["variations"]] == [CPF_LIMPO]


def test_variacoes_recuperam_digito_errado_na_base():
    # 151.979.820-95: o 4º dígito deveria ser 8
    r = generate_valid_variations("151.979.820-95")
    assert CPF_LIMPO in [v["cpf_numeros"] for v in r["variations"]]
    assert r["total_variacoes"] < 10


def test_generate_valid_variations_com_cpf_curto():
    assert "error" in generate_valid_variations("123")


# ── tools que consultam ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_check_cpf():
    with patch("app.mcp_server.consultar_fonte", return_value=ENCONTRADO):
        r = await check_cpf(CPF)
    assert r["encontrado"] is True


@pytest.mark.asyncio
async def test_check_cpf_invalido_nao_consulta():
    """Erro vira dicionário, não exceção: quem chama é um cliente MCP."""
    with patch("app.mcp_server.consultar_fonte") as consulta:
        r = await check_cpf("111.111.111-11")
    assert "erro" in r
    consulta.assert_not_called()


@pytest.mark.asyncio
async def test_check_cpf_com_digitos_faltando():
    r = await check_cpf("123")
    assert "11 dígitos" in r["erro"]


@pytest.mark.asyncio
async def test_find_cpf_by_mask():
    with patch("app.mcp_server.consultar_multiplos", side_effect=_lote):
        r = await find_cpf_by_mask("151.879.82*-**")
    assert r["candidatos_gerados"] == 10


@pytest.mark.asyncio
async def test_find_cpf_by_mask_com_mascara_invalida():
    r = await find_cpf_by_mask("151.879.82A-**")
    assert "Caractere inválido" in r["erro"]


@pytest.mark.asyncio
async def test_find_cpf_by_mask_repassa_parar_ao_confirmar():
    with patch("app.mcp_server.consultar_multiplos", side_effect=_lote) as lote:
        await find_cpf_by_mask("151.879.82*-**", nome="fulano", parar_ao_confirmar=False)
    assert lote.call_args.kwargs["parar_ao_confirmar"] is False


@pytest.mark.asyncio
async def test_find_cpf_by_variations():
    with patch("app.mcp_server.consultar_multiplos", side_effect=_lote):
        r = await find_cpf_by_variations(CPF_LIMPO)
    assert r["candidatos_gerados"] > 0


@pytest.mark.asyncio
async def test_check_multiple_cpfs_separa_invalidos():
    with patch("app.mcp_server.consultar_multiplos", side_effect=_lote):
        r = await check_multiple_cpfs([CPF, "111.111.111-11"])
    assert r["total"] == 2              # recebidos
    assert r["total_consultados"] == 1  # só o válido
    assert len(r["erros"]) == 1


@pytest.mark.asyncio
async def test_check_multiple_cpfs_sem_nenhum_valido():
    with patch("app.mcp_server.consultar_multiplos") as lote:
        r = await check_multiple_cpfs(["111.111.111-11"])
    assert r["total"] == 1
    assert r["total_consultados"] == 0
    lote.assert_not_called()


@pytest.mark.asyncio
async def test_workers_sao_limitados():
    """Cliente MCP pode pedir qualquer número; o teto é do servidor."""
    with patch("app.mcp_server.consultar_multiplos", side_effect=_lote) as lote:
        await find_cpf_by_mask("151.879.82*-**", workers=9999)
    assert lote.call_args.args[2] <= 20   # (candidatos, nome, workers)
