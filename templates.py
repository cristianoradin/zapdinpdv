"""
templates.py — Templates de mensagem para eventos do ERP.

Os templates ficam em templates.json (editável pelo usuário).
Variáveis: {nome_cliente}, {numero_venda}, {valor_total}, etc.
"""
import json
import logging
import re
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def _templates_path() -> Path:
    import sys
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).parent
    return base / "templates.json"


# Templates padrão — usados quando templates.json não existe
DEFAULT_TEMPLATES: Dict[str, dict] = {
    "venda_realizada": {
        "descricao": "Comprovante de venda",
        "mensagem": (
            "✅ *Venda Confirmada!*\n\n"
            "👤 Cliente: {nome_cliente}\n"
            "🧾 Venda Nº: {numero_venda}\n"
            "💰 Valor Total: R$ {valor_total}\n"
            "💳 Pagamento: {forma_pagamento}\n"
            "📅 Data: {data}\n\n"
            "Obrigado pela preferência! 🙏"
        ),
        "ativo": True,
    },
    "nota_fiscal": {
        "descricao": "Nota Fiscal Eletrônica",
        "mensagem": (
            "📄 *Nota Fiscal Emitida*\n\n"
            "👤 {nome_cliente}\n"
            "🔢 NF-e Nº: {numero_nf}\n"
            "💰 Valor: R$ {valor_total}\n"
            "📅 Emissão: {data}\n\n"
            "Segue em anexo o documento fiscal."
        ),
        "ativo": True,
    },
    "boleto": {
        "descricao": "Boleto bancário",
        "mensagem": (
            "🏦 *Boleto Gerado*\n\n"
            "👤 {nome_cliente}\n"
            "💰 Valor: R$ {valor_total}\n"
            "📅 Vencimento: {data_vencimento}\n\n"
            "📋 Linha digitável:\n`{linha_digitavel}`\n\n"
            "Ou acesse: {link_boleto}"
        ),
        "ativo": True,
    },
    "pedido_confirmado": {
        "descricao": "Confirmação de pedido",
        "mensagem": (
            "🛒 *Pedido Confirmado!*\n\n"
            "👤 {nome_cliente}\n"
            "📦 Pedido Nº: {numero_pedido}\n"
            "💰 Valor: R$ {valor_total}\n"
            "🚚 Previsão: {previsao_entrega}\n\n"
            "Acompanhe pelo nosso sistema."
        ),
        "ativo": True,
    },
    "entrega_realizada": {
        "descricao": "Confirmação de entrega",
        "mensagem": (
            "📦 *Entrega Realizada!*\n\n"
            "👤 {nome_cliente}\n"
            "📋 Pedido Nº: {numero_pedido}\n"
            "✅ Entregue em: {data}\n\n"
            "Obrigado pela compra! Avalie nosso atendimento. ⭐"
        ),
        "ativo": True,
    },
    "cobranca": {
        "descricao": "Lembrete de cobrança",
        "mensagem": (
            "⚠️ *Lembrete de Pagamento*\n\n"
            "Olá, {nome_cliente}!\n\n"
            "Identificamos um débito em aberto:\n"
            "💰 Valor: R$ {valor_total}\n"
            "📅 Vencimento: {data_vencimento}\n\n"
            "Regularize para evitar juros. Entre em contato conosco."
        ),
        "ativo": True,
    },
    "custom": {
        "descricao": "Mensagem personalizada (ERP envia o texto completo)",
        "mensagem": "{mensagem}",
        "ativo": True,
    },
}


class TemplateManager:
    def __init__(self):
        self._templates: Dict[str, dict] = {}
        self._load()

    def _load(self):
        path = _templates_path()
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    self._templates = json.load(f)
                logger.info("Templates carregados de %s", path)
                return
            except Exception as exc:
                logger.warning("Erro ao ler templates.json: %s", exc)
        # Cria o arquivo com os defaults
        self._templates = dict(DEFAULT_TEMPLATES)
        self._save()

    def _save(self):
        path = _templates_path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._templates, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.warning("Erro ao salvar templates.json: %s", exc)

    def get_all(self) -> dict:
        return dict(self._templates)

    def get(self, evento: str) -> Optional[dict]:
        return self._templates.get(evento)

    def render(self, evento: str, vars: dict) -> Optional[str]:
        """Renderiza o template do evento com as variáveis fornecidas."""
        tmpl = self._templates.get(evento)
        if not tmpl or not tmpl.get("ativo", True):
            return None
        msg = tmpl.get("mensagem", "")
        # Substitui {variavel} pelas vars do ERP
        try:
            msg = msg.format_map(_SafeDict(vars))
        except Exception as exc:
            logger.warning("Erro ao renderizar template '%s': %s", evento, exc)
        return msg.strip()

    def save_template(self, evento: str, mensagem: str, descricao: str = "",
                      ativo: bool = True):
        self._templates[evento] = {
            "descricao": descricao,
            "mensagem": mensagem,
            "ativo": ativo,
        }
        self._save()

    def delete_template(self, evento: str) -> bool:
        if evento in self._templates:
            del self._templates[evento]
            self._save()
            return True
        return False


class _SafeDict(dict):
    """Retorna '{chave}' quando a chave não existe, evitando KeyError."""
    def __missing__(self, key):
        return "{" + key + "}"


# Instância global
templates = TemplateManager()
