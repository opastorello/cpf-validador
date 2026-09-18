import logging

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app import config as _cfg
from app import metrics as _m
from app.auth import TokenMiddleware
from app.mcp_server import mcp
from app.rate_limit import limiter
from app.routers import consulta, cpf, ui
from app.services import sources

logging.basicConfig(
    level=getattr(logging, _cfg.LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)

# Falha no boot, não na primeira consulta: um SOURCE errado no .env não pode
# subir um container "healthy" que só devolve 500 quando alguém consulta.
# Só valida o nome — não importa a fonte, para o registro seguir preguiçoso.
_fontes = sources.fontes_disponiveis()
if _cfg.SOURCE not in _fontes:
    raise RuntimeError(
        f"SOURCE={_cfg.SOURCE!r} não existe. Disponíveis: {', '.join(sorted(_fontes))}"
    )
# Carrega a fonte ativa agora, não na primeira consulta: se as dependências
# dela não estiverem na imagem (COM_TRT3=false com SOURCE=trt3), é melhor não
# subir do que subir "healthy" e falhar quando alguém consultar.
sources.get_fonte()

# FastMCP — endpoint will live at /mcp (no sub-mount, avoids 307 redirect)
_mcp_app = mcp.http_app(path="/mcp")

app = FastAPI(
    title="CPF Validador",
    description=(
        "Valida CPFs, confirma titularidade e descobre CPFs parciais ou ilegíveis "
        "consultando o TRT3 com resolução automática de CAPTCHA via rede neural local.\n\n"
        "**Autenticação:** quando `API_TOKEN` está configurado, todos os endpoints (exceto `/`) "
        "exigem `Authorization: Bearer <token>`. Use o botão **Authorize** acima para informar o token."
    ),
    version="2.0.2",
    lifespan=_mcp_app.lifespan,
    swagger_ui_parameters={"persistAuthorization": True},
)


def _custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    schema.setdefault("components", {})["securitySchemes"] = {
        "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "Token"}
    }
    for path in schema.get("paths", {}).values():
        for operation in path.values():
            if isinstance(operation, dict):
                operation["security"] = [{"BearerAuth": []}, {}]
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = _custom_openapi

def _rate_limit_handler(request, exc: RateLimitExceeded):
    _m.http_rate_limit_total.labels(endpoint=request.url.path).inc()
    return _rate_limit_exceeded_handler(request, exc)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
app.add_middleware(TokenMiddleware)

# REST routers — all defined before mount so they aren't swallowed by the "/" catch-all
@app.get(
    "/health",
    tags=["health"],
    summary="Health check",
    description="Verifica se o servidor está no ar. Sempre aberto — é consumido pelo healthcheck do Docker.",
    responses={200: {"content": {"application/json": {"example": {"status": "ok"}}}}},
)
async def health():
    return {"status": "ok"}


@app.get(
    "/auth/check",
    tags=["auth"],
    summary="Valida o token de acesso",
    description=(
        "Rota protegida usada pela interface web para validar o token informado no gate. "
        "Retorna 401 quando o token está ausente ou incorreto, e 200 quando é válido "
        "(ou quando `API_TOKEN` não está configurado)."
    ),
    responses={
        200: {"content": {"application/json": {"example": {"ok": True}}}},
        401: {"content": {"application/json": {"example": {"detail": "Unauthorized"}}}},
    },
)
async def auth_check():
    return {"ok": True}

app.include_router(ui.router)
app.include_router(cpf.router)
app.include_router(consulta.router, prefix="/consulta", tags=["consulta"])

Instrumentator().instrument(app).expose(app, include_in_schema=False)

# Mount FastMCP last — catch-all at "/"
app.mount("/", _mcp_app)
