"""
zapdin_client.py — Cliente HTTP para o ZapDin App REMOTO.

Autenticação: token de máquina (X-PDV-Token).
Sem usuário/senha — o admin gera o token uma vez no App.

Responsabilidade: config, status, reportar sessão local.
NÃO envia mensagens — isso é feito pelo evolution_local.py.
"""
import logging
from typing import Optional, Tuple

import httpx

from .config import settings

logger = logging.getLogger(__name__)


class ZapDinAppClient:
    """
    Fala com o ZapDin App remoto usando X-PDV-Token.
    """

    def _headers(self) -> dict:
        return {"X-PDV-Token": settings.zapdin_pdv_token} if settings.zapdin_pdv_token else {}

    @property
    def configurado(self) -> bool:
        return bool(settings.zapdin_pdv_token)

    # ── Requisições ───────────────────────────────────────────────────────────

    async def _get(self, path: str) -> Tuple[int, dict]:
        if not self.configurado:
            return 503, {"error": "ZAPDIN_PDV_TOKEN não configurado"}
        url = f"{settings.zapdin_url.rstrip('/')}{path}"
        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
                r = await client.get(url, headers=self._headers())
            try:
                return r.status_code, r.json()
            except Exception:
                return r.status_code, {}
        except Exception as exc:
            logger.warning("ZapDinAppClient GET %s: %s", path, exc)
            return 503, {"error": str(exc)}

    async def _post(self, path: str, **kwargs) -> Tuple[int, dict]:
        if not self.configurado:
            return 503, {"error": "ZAPDIN_PDV_TOKEN não configurado"}
        url = f"{settings.zapdin_url.rstrip('/')}{path}"
        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
                r = await client.post(url, headers=self._headers(), **kwargs)
            try:
                return r.status_code, r.json()
            except Exception:
                return r.status_code, {}
        except Exception as exc:
            logger.warning("ZapDinAppClient POST %s: %s", path, exc)
            return 503, {"error": str(exc)}

    # ── Métodos públicos ──────────────────────────────────────────────────────

    async def verificar_conexao(self) -> dict:
        """Verifica se o token é válido e o App está acessível."""
        if not self.configurado:
            return {"ok": False, "zapdin_url": settings.zapdin_url,
                    "erro": "ZAPDIN_PDV_TOKEN não configurado no .env"}
        code, data = await self._get("/api/pdv/config")
        ok = code == 200
        if not ok:
            logger.warning("ZapDin App retornou HTTP %s ao verificar token", code)
        return {"ok": ok, "zapdin_url": settings.zapdin_url, "empresa": data.get("empresa", "")}

    async def get_pdv_config(self) -> dict:
        """
        Busca configurações do PDV no App:
          - evolution_api_key
          - mensagem_padrao
          - pdv_ativo
        """
        code, data = await self._get("/api/pdv/config")
        return data if code == 200 else {}

    async def registrar_sessao_local(self, sessao_id: str,
                                      phone: Optional[str], status: str) -> bool:
        """Notifica o App que esta sessão WhatsApp está rodando localmente."""
        code, _ = await self._post("/api/pdv/sessao-local", json={
            "sessao_id": sessao_id,
            "pdv_nome":  settings.pdv_nome,
            "phone":     phone,
            "status":    status,
        })
        return code in (200, 201, 204)


# Instância global
zapdin_app = ZapDinAppClient()
