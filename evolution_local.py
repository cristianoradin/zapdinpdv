"""
evolution_local.py — Cliente para a Evolution API rodando LOCALMENTE na máquina do cliente.

O WhatsApp conecta aqui, usando CPU/memória da máquina local.
Tudo que é credencial, token, histórico vai para o ZapDin App remoto via zapdin_client.py.
"""
import asyncio
import logging
from typing import Optional, Dict

import httpx

from .config import settings

logger = logging.getLogger(__name__)

_TIMEOUT = 30.0


def _url(path: str) -> str:
    return f"{settings.evolution_url.rstrip('/')}/{path.lstrip('/')}"


def _h() -> dict:
    return {"apikey": settings.evolution_api_key, "Content-Type": "application/json"}


def _inst_name(sessao_id: str) -> str:
    """Nome da instância no Evolution API local."""
    return f"pdv{settings.pdv_empresa_id}_{sessao_id}"


def _webhook_url() -> str:
    """Webhook local — o PDV recebe eventos do Evolution API local."""
    return f"http://127.0.0.1:{settings.pdv_port}/evo-webhook"


# ── Sessão local ──────────────────────────────────────────────────────────────

class LocalSession:
    def __init__(self, sessao_id: str, nome: str):
        self.sessao_id = sessao_id
        self.nome = nome
        self.status = "disconnected"
        self.qr_data: Optional[str] = None
        self.phone: Optional[str] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._polling = False

    def on_qr_updated(self, qr_b64: str):
        if not qr_b64.startswith("data:"):
            qr_b64 = "data:image/png;base64," + qr_b64
        self.qr_data = qr_b64
        self.status = "disconnected"
        logger.info("LocalSession [%s] QR atualizado", self.sessao_id)

    def on_connection_update(self, state: str, phone: Optional[str] = None):
        prev = self.status
        if state == "open":
            self.status = "connected"
            self.qr_data = None
            if phone:
                self.phone = phone
        elif state in ("connecting", "pairingCode"):
            self.status = "connecting"
            asyncio.create_task(self._poll_until_open())
        elif state == "close":
            if self.status == "connecting":
                return  # ignora close enquanto está conectando
            self.status = "disconnected"
        else:
            self.status = "disconnected"
        if prev != self.status:
            logger.info("LocalSession [%s] %s → %s", self.sessao_id, prev, self.status)

    async def _poll_until_open(self):
        if self._polling:
            return
        self._polling = True
        try:
            for _ in range(15):
                await asyncio.sleep(3)
                if self.status == "connected":
                    return
                try:
                    await self._check_state()
                except Exception:
                    pass
        finally:
            self._polling = False

    async def _check_state(self):
        inst = _inst_name(self.sessao_id)
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.get(_url(f"instance/connectionState/{inst}"), headers=_h())
            if r.status_code != 200:
                return
            data = r.json()
            state = (
                data.get("instance", {}).get("state")
                or data.get("state")
                or "close"
            )
            if not (self.status == "connecting" and state == "close"):
                self.on_connection_update(state)
        except Exception as exc:
            logger.debug("LocalSession._check_state [%s]: %s", self.sessao_id, exc)

    async def fetch_qr(self):
        """Solicita QR code ao Evolution API local."""
        inst = _inst_name(self.sessao_id)
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                rs = await client.get(_url(f"instance/connectionState/{inst}"), headers=_h())
            if rs.status_code == 200:
                state = (
                    rs.json().get("instance", {}).get("state")
                    or rs.json().get("state")
                    or "close"
                )
                if state == "open":
                    self.on_connection_update("open")
                    return
            if self.status == "connected":
                return
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.get(_url(f"instance/connect/{inst}"), headers=_h())
            if r.status_code == 200:
                d = r.json()
                qr = d.get("base64") or d.get("qrcode", {}).get("base64") or d.get("qr", "")
                if qr:
                    self.on_qr_updated(qr)
        except Exception as exc:
            logger.debug("LocalSession.fetch_qr [%s]: %s", self.sessao_id, exc)

    def start_heartbeat(self):
        if not self._heartbeat_task or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    def stop_heartbeat(self):
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None

    async def _heartbeat_loop(self):
        await asyncio.sleep(5)
        while True:
            try:
                await self._check_state()
            except Exception as exc:
                logger.debug("LocalSession heartbeat [%s]: %s", self.sessao_id, exc)
            await asyncio.sleep(60 if self.status == "connected" else 15)

    async def stop(self):
        self.stop_heartbeat()


# ── Manager local ─────────────────────────────────────────────────────────────

class LocalEvoManager:
    """Gerencia sessões WhatsApp na Evolution API local do PDV."""

    def __init__(self):
        self._sessions: Dict[str, LocalSession] = {}
        self._inst_index: Dict[str, LocalSession] = {}

    async def _ensure_instance(self, inst: str) -> bool:
        wh_cfg = {
            "url": _webhook_url(),
            "byEvents": False,
            "base64": False,
            "events": ["QRCODE_UPDATED", "CONNECTION_UPDATE"],
        }
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.get(_url("instance/fetchInstances"), headers=_h())
                if r.status_code == 200:
                    existing = {
                        i.get("instance", {}).get("instanceName")
                        for i in r.json()
                    }
                    if inst in existing:
                        await client.post(_url(f"webhook/set/{inst}"), json=wh_cfg, headers=_h())
                        return True
                r2 = await client.post(
                    _url("instance/create"),
                    json={
                        "instanceName": inst,
                        "qrcode": True,
                        "integration": "WHATSAPP-BAILEYS",
                        "webhook": wh_cfg,
                    },
                    headers=_h(),
                )
                if r2.status_code in (200, 201):
                    await client.post(_url(f"webhook/set/{inst}"), json=wh_cfg, headers=_h())
                    return True
                return False
        except Exception as exc:
            logger.error("LocalEvoManager._ensure_instance [%s]: %s", inst, exc)
            return False

    async def add_session(self, sessao_id: str, nome: str) -> LocalSession:
        if sessao_id in self._sessions:
            return self._sessions[sessao_id]
        inst = _inst_name(sessao_id)
        await self._ensure_instance(inst)
        sess = LocalSession(sessao_id, nome)
        self._sessions[sessao_id] = sess
        self._inst_index[inst] = sess
        sess.start_heartbeat()
        asyncio.create_task(sess.fetch_qr())
        logger.info("LocalEvoManager: sessão %s criada", sessao_id)
        return sess

    async def remove_session(self, sessao_id: str) -> None:
        sess = self._sessions.pop(sessao_id, None)
        if not sess:
            return
        sess.stop_heartbeat()
        inst = _inst_name(sessao_id)
        self._inst_index.pop(inst, None)
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                await client.delete(_url(f"instance/delete/{inst}"), headers=_h())
        except Exception as exc:
            logger.debug("LocalEvoManager.remove_session: %s", exc)

    def handle_webhook(self, payload: dict) -> None:
        event = (payload.get("event") or "").upper()
        inst = payload.get("instance") or payload.get("instanceName") or ""
        data = payload.get("data") or {}
        sess = self._inst_index.get(inst)
        if not sess:
            return
        if event in ("QRCODE_UPDATED", "QRCODE.UPDATED"):
            qr = data.get("base64") or data.get("qrcode", {}).get("base64") or ""
            if qr:
                sess.on_qr_updated(qr)
        elif event in ("CONNECTION_UPDATE", "CONNECTION.UPDATE"):
            state = data.get("state") or data.get("instance", {}).get("state") or ""
            phone = data.get("wuid") or data.get("phone") or data.get("number") or None
            if state:
                sess.on_connection_update(state, phone)

    def get_status(self) -> list:
        return [
            {"id": s.sessao_id, "nome": s.nome, "status": s.status, "phone": s.phone}
            for s in self._sessions.values()
        ]

    def get_qr(self, sessao_id: str) -> Optional[str]:
        sess = self._sessions.get(sessao_id)
        if not sess:
            return None
        if not sess.qr_data and sess.status != "connected":
            asyncio.create_task(sess.fetch_qr())
        return sess.qr_data

    def pick_connected(self) -> Optional[str]:
        for s in self._sessions.values():
            if s.status == "connected":
                return s.sessao_id
        return None

    async def send_text(self, sessao_id: str, phone: str, message: str):
        inst = _inst_name(sessao_id)
        number = phone.strip().lstrip("+").replace(" ", "")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.post(
                    _url(f"message/sendText/{inst}"),
                    json={"number": number, "text": message},
                    headers=_h(),
                )
            if r.status_code in (200, 201):
                return True, None
            return False, f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as exc:
            return False, str(exc)

    async def send_file_b64(self, sessao_id: str, phone: str, filename: str,
                             file_b64: str, caption: str = ""):
        import os, base64 as _b64
        inst = _inst_name(sessao_id)
        number = phone.strip().lstrip("+").replace(" ", "")
        ext = os.path.splitext(filename)[1].lower()

        mime_map = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
            ".gif": "image/gif", ".webp": "image/webp", ".mp4": "video/mp4",
            ".mp3": "audio/mpeg", ".ogg": "audio/ogg", ".wav": "audio/wav",
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }
        type_map = {
            ".jpg": "image", ".jpeg": "image", ".png": "image",
            ".gif": "image", ".webp": "image",
            ".mp4": "video", ".mov": "video",
            ".mp3": "audio", ".ogg": "audio", ".wav": "audio",
        }
        mime = mime_map.get(ext, "application/octet-stream")
        mtype = type_map.get(ext, "document")

        # Evolution API v2: base64 puro, sem prefixo data URI
        raw_b64 = file_b64
        if "," in file_b64:
            raw_b64 = file_b64.split(",", 1)[1]

        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                r = await client.post(
                    _url(f"message/sendMedia/{inst}"),
                    json={
                        "number": number,
                        "mediatype": mtype,
                        "mimetype": mime,
                        "caption": caption or "",
                        "media": raw_b64,
                        "fileName": filename,
                    },
                    headers=_h(),
                )
            if r.status_code in (200, 201):
                return True, None
            return False, f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as exc:
            return False, str(exc)

    async def stop(self):
        for sess in list(self._sessions.values()):
            await sess.stop()


# Instância global do manager local
local_evo = LocalEvoManager()
