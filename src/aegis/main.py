"""API HTTP (FastAPI). Camada de aplicação: autenticação, autorização, limites e cabeçalhos."""

from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from . import __version__
from .bootstrap import Runtime, build_runtime
from .config import Settings
from .security.auth import AuthError, Principal
from .security.crypto import hash_password

log = logging.getLogger("aegis.api")
MAX_BODY = 16 * 1024
AUTH_SCHEME = "bearer"
UI_DIR = Path(__file__).parent / "ui"
UI_CSP = "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"

SEC_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}


class ChatIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=2, max_length=2000)


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


def create_app(settings: Settings | None = None) -> FastAPI:
    s = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        users = dict(s.users)
        if not users and not s.is_prod:
            pw = secrets.token_urlsafe(12)
            users = {"demo": {"hash": hash_password(pw), "role": "analista"}}
            log.warning("Usuário de DEV criado -> demo / %s (nunca use em produção)", pw)
        rt = build_runtime(dataclasses.replace(s, users=users))
        await rt.bus.start()
        app.state.rt = rt
        yield
        await rt.bus.stop()

    app = FastAPI(
        title="Aegis",
        version=__version__,
        lifespan=lifespan,
        docs_url=None if s.is_prod else "/docs",
        redoc_url=None,
        openapi_url=None if s.is_prod else "/openapi.json",
    )

    @app.middleware("http")
    async def hardening(request: Request, call_next):
        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > MAX_BODY:
            resp: JSONResponse = JSONResponse({"detail": "payload_too_large"}, status_code=413)
        else:
            try:
                resp = await call_next(request)
            except Exception:
                log.exception("erro não tratado")
                resp = JSONResponse({"detail": "internal_error"}, status_code=500)
        for k, v in SEC_HEADERS.items():
            resp.headers[k] = v
        if request.url.path.startswith("/ui"):
            resp.headers["Content-Security-Policy"] = UI_CSP
        return resp

    def rt_of(request: Request) -> Runtime:
        return request.app.state.rt

    async def current_user(request: Request) -> Principal:
        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(401, "não autenticado", headers={"WWW-Authenticate": "Bearer"})
        try:
            return rt_of(request).auth.decode(token)
        except AuthError:
            raise HTTPException(401, "token inválido", headers={"WWW-Authenticate": "Bearer"}) from None

    def throttle(limiter, key: str) -> None:
        ok, retry = limiter.allow(key)
        if not ok:
            raise HTTPException(429, "limite excedido", headers={"Retry-After": str(int(retry) + 1)})

    app.mount("/ui", StaticFiles(directory=UI_DIR, html=True), name="ui")

    @app.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse("/ui/")

    @app.get("/v1/health")
    async def health():
        return {"status": "ok", "version": __version__}

    @app.post("/v1/auth/token")
    async def token(body: LoginIn, request: Request):
        rt = rt_of(request)
        ip = hashlib.sha256((request.client.host if request.client else "?").encode()).hexdigest()[:12]
        throttle(rt.login_limiter, f"{ip}:{body.username}")
        tok = await asyncio.to_thread(rt.auth.login, body.username, body.password)
        if not tok:
            rt.audit.write("login_fail", "-", body.username[:64], {"ip": ip})
            raise HTTPException(401, "credenciais inválidas")
        rt.audit.write("login_ok", "-", body.username, {"ip": ip})
        return {"access_token": tok, "token_type": AUTH_SCHEME, "expires_in": rt.settings.jwt_ttl_seconds}

    @app.post("/v1/chat")
    async def chat(body: ChatIn, request: Request, user: Principal = Depends(current_user)):
        rt = rt_of(request)
        throttle(rt.limiter, user.sub)
        try:
            return await rt.pipeline.ask(body.question, user.sub, user.role)
        except TimeoutError:
            raise HTTPException(504, "tempo esgotado") from None

    @app.get("/v1/kb/topics")
    async def topics(request: Request, user: Principal = Depends(current_user)):
        kb = rt_of(request).pipeline.kb
        if kb is None:
            raise HTTPException(501, "base não disponível neste papel (api)")
        return {"topics": [{"categoria": c, "itens": n} for c, n in kb.topics()]}

    @app.get("/v1/audit/verify")
    async def audit_verify(request: Request, user: Principal = Depends(current_user)):
        if not user.has("admin"):
            raise HTTPException(403, "permissão insuficiente")
        rt = rt_of(request)
        from .security.audit import AuditLog
        from .security.crypto import KeyRing

        key = KeyRing.from_master(rt.settings.master_key).audit
        report = {}
        for f in sorted(rt.settings.audit_dir.glob("audit-*.jsonl")):
            ok, n, bad = AuditLog(f, key).verify()
            report[f.name] = {"integro": ok, "registros": n, "linha_invalida": bad}
        return report

    return app
