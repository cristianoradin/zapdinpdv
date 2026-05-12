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
    evolution_url: str = "http://localhost:8080"
    evolution_api_key: str = "zapdin-pdv-local"

    # ── ZapDin App REMOTO ─────────────────────────────────────────────────────
    # Autenticação por TOKEN DE MÁQUINA — sem usuário/senha.
    # O admin gera o token no App (POST /api/pdv/tokens) e cola aqui.
    zapdin_url: str = "https://app.seuservidor.com.br"
    zapdin_pdv_token: str = ""   # ZAPDIN_PDV_TOKEN no .env

    # ── PDV Local ─────────────────────────────────────────────────────────────
    pdv_port: int = 4600
    pdv_api_key: str = "pdv-local-key"   # chave que o ERP usa no header X-PDV-Key
    pdv_nome: str = "PDV"

    # ── Comportamento ─────────────────────────────────────────────────────────
    request_timeout: float = 30.0


settings = Settings()
