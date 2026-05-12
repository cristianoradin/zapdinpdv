"""
config.py — Configurações do ZapDin PDV.
Lidas do arquivo .env na mesma pasta do executável.
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


def _env_path() -> Path:
    import sys
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).parent
    return base / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_env_path()),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Evolution API LOCAL (WhatsApp roda na máquina do cliente) ─────────────
    # O PDV conecta o WhatsApp localmente, usando recursos da máquina local.
    evolution_url: str = "http://localhost:8080"
    evolution_api_key: str = "zapdin-pdv-local"

    # ── ZapDin App REMOTO (autenticação, credenciais, histórico) ──────────────
    # O PDV fala APENAS com o ZapDin App. Quem fala com o Monitor é o App.
    zapdin_url: str = "https://app.seuservidor.com.br"
    zapdin_username: str = ""
    zapdin_password: str = ""

    # ── PDV Local ─────────────────────────────────────────────────────────────
    pdv_port: int = 4600
    pdv_api_key: str = "pdv-local-key"     # Chave que o ERP usa no header X-PDV-Key
    pdv_nome: str = "PDV"
    pdv_empresa_id: int = 1                 # empresa_id local para nomear instâncias

    # ── Comportamento ─────────────────────────────────────────────────────────
    request_timeout: float = 30.0
    session_refresh_minutes: int = 60       # re-autentica no ZapDin App a cada N min


settings = Settings()
