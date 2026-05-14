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

    # ── Modo de envio ─────────────────────────────────────────────────────────
    # "app"   → roteia via ZapDin App local (porta 4000) — RECOMENDADO para testes
    # "local" → usa Evolution API própria nesta máquina (requer Evolution rodando)
    modo_envio: str = "app"

    # ── ZapDin App LOCAL (porta 4000 na mesma máquina) ────────────────────────
    # Em modo "app", todos os envios passam pelo App que já gerencia sessões WA.
    zapdin_url: str = "http://localhost:4000"
    zapdin_erp_token: str = ""    # token ERP gerado no painel: Configurações → ERP Token
    zapdin_pdv_token: str = ""    # token PDV (legado — não obrigatório no modo app)

    # ── Evolution API LOCAL (só para modo "local") ────────────────────────────
    evolution_url: str = "http://localhost:8080"
    evolution_api_key: str = "zapdin-pdv-local"

    # ── PDV Local ─────────────────────────────────────────────────────────────
    pdv_port: int = 4600
    pdv_api_key: str = "pdv-local-key"   # chave que o ERP usa no header X-PDV-Key
    pdv_nome: str = "PDV Teste"
    pdv_empresa_id: int = 1              # empresa_id no ZapDin App (para instâncias locais)
    empresa_nome: str = ""               # Nome da empresa (aparece no topo das mensagens)

    # ── Comportamento ─────────────────────────────────────────────────────────
    request_timeout: float = 30.0


settings = Settings()
