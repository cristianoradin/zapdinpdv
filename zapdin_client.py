"""
zapdin_client.py — Cliente HTTP autenticado para o ZapDin App REMOTO.

Responsabilidade: credenciais, tokens, histórico, usuários.
NÃO envia mensagens — isso é feito localmente pelo evolution_local.py.
"""
import asyncio
import logging
import time
from typing import Optional, Tuple

import httpx

from .config import settings

logger = logging.getLogger(__name__)

_COOKIE_NAME = "session"


class ZapDinAppClient:
    """
    Fala com o ZapDin App remoto para:
    - Autenticar o usuário (login/senha)
    - Validar token do cliente
    - Registrar sessão WA local no app remoto (para rastreamento)
    - Buscar configurações e credenciais
    """

    def __init__(self):
        self._cookie: Optional[str] = None
        self._cookie_ts: float = 0.0
        self._lock = asyncio.Lock()

    # ── Autenticação ──────────────────────────────────────────────────────────

    async def _login(self) -> bool:
        if not settings.zapdin_username or not settings.zapdin_password:
            logger.warning("ZapDinAppClient: ZAPDIN_USERNAME/PASSWORD não configurados")
            return False
        url = f"{settings.zapdin_url.rstrip('/')}/api/auth/login"
        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
                r = await client.post(url, json={
                    "username": settings.zapdin_username,
                    "password": settings.zapdin_password,
                })
            if r.status_code == 200:
                # Extrai cookie de sessão
                cookie = r.cookies.get(_COOKIE_NAME)
                if not cookie:
                    for v in r.headers.get_list("set-cookie"):
                        if "=" in v:
                            name, val = v.split("=", 1)
                            val = val.split(";")[0]
                            if name.strip().lower() == _COOKIE_NAME:
                                cookie = val.strip()
                                break
                if cookie:
                    self._cookie = cookie
                    self._cookie_ts = time.time()
                    logger.info("ZapDinAppClient: autenticado no ZapDin App remoto")
                    return True
            logger.warning("ZapDinAppClient: login falhou — HTTP %s", r.status_code)
            return False
        except Exception as exc:
            logger.warning("ZapDinAppClient: erro ao conectar no ZapDin App: %s", exc)
            return False

    async def _ensure_auth(self) -> bool:
        async with self._lock:
            age = time.time() - self._cookie_ts
            if self._cookie and age < settings.session_refresh_minutes * 60:
                return True
            return await self._login()

    def _headers(self) -> dict:
        return {"Cookie": f"session={self._cookie}"} if self._cookie else {}

    @property
    def conectado(self) -> bool:
        return self._cookie is not None

    # ── Requisições ───────────────────────────────────────────────────────────

    async def _get(self, path: str) -> Tuple[int, dict]:
        if not await self._ensure_auth():
            return 503, {"error": "Sem conexão com o ZapDin App remoto"}
        url = f"{settings.zapdin_url.rstrip('/')}{path}"
        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
                r = await client.get(url, headers=self._headers())
            if r.status_code == 401:
                self._cookie = None
            try:
                return r.status_code, r.json()
            except Exception:
                return r.status_code, {}
        except Exception as exc:
            return 503, {"error": str(exc)}

    async def _post(self, path: str, **kwargs) -> Tuple[int, dict]:
        if not await self._ensure_auth():
            return 503, {"error": "Sem conexão com o ZapDin App remoto"}
        url = f"{settings.zapdin_url.rstrip('/')}{path}"
        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
                r = await client.post(url, headers=self._headers(), **kwargs)
            if r.status_code == 401:
                self._cookie = None
            try:
                return r.status_code, r.json()
            except Exception:
                return r.status_code, {}
        except Exception as exc:
            return 503, {"error": str(exc)}

    # ── Métodos públicos ──────────────────────────────────────────────────────

    async def verificar_conexao(self) -> dict:
        """Verifica se o ZapDin App remoto está acessível e o usuário autenticado."""
        ok = await self._ensure_auth()
        return {"ok": ok, "zapdin_url": settings.zapdin_url, "autenticado": ok}

    async def get_config(self) -> dict:
        """Busca configurações gerais do app remoto."""
        code, data = await self._get("/api/config")
        return data if code == 200 else {}

    async def get_pdv_config(self) -> dict:
        """
        Busca configurações específicas do PDV:
          - evolution_api_key: chave para o Evolution API local
          - mensagem_padrao: fallback se nenhum template bater
          - pdv_ativo: se o PDV está habilitado para esta empresa
        """
        code, data = await self._get("/api/pdv/config")
        return data if code == 200 else {}

    async def get_me(self) -> dict:
        """Retorna dados do usuário autenticado no ZapDin App."""
        code, data = await self._get("/api/auth/me")
        return data if code == 200 else {}

    async def registrar_sessao_local(self, sessao_id: str, phone: Optional[str],
                                      status: str) -> bool:
        """
        Notifica o ZapDin App que esta sessão WA está rodando localmente no PDV.
        O App registra para rastreamento — não usa a sessão para envio.
        """
        code, _ = await self._post("/api/pdv/sessao-local", json={
            "sessao_id": sessao_id,
            "pdv_nome": settings.pdv_nome,
            "phone": phone,
            "status": status,
        })
        return code in (200, 201, 204)


# Instância global
zapdin_app = ZapDinAppClient()
