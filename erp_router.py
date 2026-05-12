"""
erp_router.py — Endpoints de integração com o ERP do cliente.

O ERP chama estes endpoints para disparar notificações via WhatsApp.
Todas as rotas ficam em /erp/*

Fluxo:
  ERP → POST /erp/notificar → PDV formata mensagem → Evolution API local → WhatsApp
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .config import settings
from .evolution_local import local_evo
from .templates import templates

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/erp", tags=["ERP"])


def _check_key(key: Optional[str]):
    if settings.pdv_api_key and key != settings.pdv_api_key:
        raise HTTPException(status_code=401, detail="X-PDV-Key inválida")


# ── Modelos ────────────────────────────────────────────────────────────────────

class NotificarRequest(BaseModel):
    """
    Payload principal que o ERP envia para disparar uma notificação.

    Exemplos de uso:
      - Comprovante de venda: evento="venda_realizada", vars={...}
      - NF-e com PDF:         evento="nota_fiscal",     arquivo_base64="...", arquivo_nome="nf.pdf"
      - Mensagem livre:       evento="custom",          vars={"mensagem": "Texto livre aqui"}
    """
    phone: str                              # Número destino (44999990000 ou +5544999990000)
    evento: str = "venda_realizada"         # Qual template usar

    # Variáveis para preencher o template
    vars: Dict[str, Any] = {}

    # Arquivo opcional (NF-e, boleto PDF, imagem, etc.)
    arquivo_base64: Optional[str] = None   # base64 puro ou data URI
    arquivo_nome: Optional[str] = None     # nome com extensão: "nf_001.pdf"
    arquivo_caption: Optional[str] = None  # legenda do arquivo (substitui template se informada)

    # Controle
    sessao_id: Optional[str] = None        # None = usa primeira sessão conectada
    apenas_arquivo: bool = False           # True = não envia texto, só o arquivo


class VendaRequest(BaseModel):
    """Atalho específico para evento de venda — campos nomeados para facilitar integração."""
    phone: str
    numero_venda: str
    nome_cliente: str
    valor_total: str                        # "150,00" ou "150.00"
    forma_pagamento: str = ""
    data: str = ""
    itens: Optional[List[Dict]] = None     # lista de produtos (exibida se template usar {itens})
    observacao: Optional[str] = ""
    arquivo_base64: Optional[str] = None   # PDF comprovante/NF-e
    arquivo_nome: Optional[str] = None
    sessao_id: Optional[str] = None


class NotaFiscalRequest(BaseModel):
    """Atalho específico para envio de NF-e."""
    phone: str
    numero_nf: str
    nome_cliente: str
    valor_total: str
    data: str = ""
    chave_acesso: Optional[str] = ""
    link_danfe: Optional[str] = ""         # link para download da DANFE
    arquivo_base64: Optional[str] = None   # PDF da NF-e
    arquivo_nome: Optional[str] = None
    sessao_id: Optional[str] = None


class BoletoRequest(BaseModel):
    """Atalho para envio de boleto."""
    phone: str
    nome_cliente: str
    valor_total: str
    data_vencimento: str
    linha_digitavel: Optional[str] = ""
    link_boleto: Optional[str] = ""
    arquivo_base64: Optional[str] = None   # PDF do boleto
    arquivo_nome: Optional[str] = None
    sessao_id: Optional[str] = None


class TemplateUpsert(BaseModel):
    evento: str
    descricao: str = ""
    mensagem: str
    ativo: bool = True


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_phone(phone: str) -> str:
    """Normaliza número: remove +, espaços, traços. Adiciona 55 se necessário."""
    p = phone.strip().replace("+", "").replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if len(p) <= 11 and not p.startswith("55"):
        p = "55" + p
    return p


def _fmt_itens(itens: Optional[List[Dict]]) -> str:
    if not itens:
        return ""
    linhas = []
    for item in itens:
        desc = item.get("descricao") or item.get("nome") or item.get("produto") or "Item"
        qtd  = item.get("quantidade") or item.get("qtd") or 1
        val  = item.get("valor_unitario") or item.get("valor") or ""
        linhas.append(f"  • {desc} x{qtd}" + (f" — R$ {val}" if val else ""))
    return "\n".join(linhas)


async def _enviar(
    phone: str,
    mensagem: Optional[str],
    arquivo_base64: Optional[str],
    arquivo_nome: Optional[str],
    caption: Optional[str],
    sessao_id: Optional[str],
    apenas_arquivo: bool = False,
) -> dict:
    """Envia mensagem e/ou arquivo via Evolution API local."""
    sessao = sessao_id or local_evo.pick_connected()
    if not sessao:
        raise HTTPException(503, "Nenhuma sessão WhatsApp conectada. Conecte o WhatsApp em /whatsapp/sessoes")

    phone_fmt = _fmt_phone(phone)
    resultados = []

    # 1. Envia texto (se não for apenas_arquivo)
    if mensagem and not apenas_arquivo:
        ok, err = await local_evo.send_text(sessao, phone_fmt, mensagem)
        if not ok:
            raise HTTPException(400, f"Erro ao enviar mensagem: {err}")
        resultados.append("texto")

    # 2. Envia arquivo (se fornecido)
    if arquivo_base64 and arquivo_nome:
        leg = caption or mensagem or ""
        ok, err = await local_evo.send_file_b64(sessao, phone_fmt, arquivo_nome, arquivo_base64, leg)
        if not ok:
            raise HTTPException(400, f"Erro ao enviar arquivo: {err}")
        resultados.append(f"arquivo:{arquivo_nome}")

    return {
        "ok": True,
        "phone": phone_fmt,
        "sessao_id": sessao,
        "enviados": resultados,
    }


# ── Endpoint genérico (principal) ─────────────────────────────────────────────

@router.post("/notificar", summary="Enviar notificação via template")
async def notificar(
    body: NotificarRequest,
    x_pdv_key: Optional[str] = Header(default=None),
):
    """
    Endpoint principal de integração ERP → WhatsApp.

    O ERP informa o evento e as variáveis.
    O PDV busca o template, renderiza a mensagem e envia via WhatsApp local.

    **Exemplos de evento:**
    - `venda_realizada` — comprovante de venda
    - `nota_fiscal`     — NF-e (pode incluir arquivo_base64)
    - `boleto`          — boleto bancário
    - `pedido_confirmado`
    - `entrega_realizada`
    - `cobranca`
    - `custom`          — vars={"mensagem": "texto livre"}
    """
    _check_key(x_pdv_key)

    mensagem = templates.render(body.evento, body.vars)
    if mensagem is None:
        raise HTTPException(400, f"Template '{body.evento}' não encontrado ou inativo")

    return await _enviar(
        phone=body.phone,
        mensagem=mensagem,
        arquivo_base64=body.arquivo_base64,
        arquivo_nome=body.arquivo_nome,
        caption=body.arquivo_caption,
        sessao_id=body.sessao_id,
        apenas_arquivo=body.apenas_arquivo,
    )


# ── Atalhos específicos ────────────────────────────────────────────────────────

@router.post("/venda", summary="Comprovante de venda")
async def venda(
    body: VendaRequest,
    x_pdv_key: Optional[str] = Header(default=None),
):
    """Atalho para enviar comprovante de venda. Campos nomeados para facilitar integração."""
    _check_key(x_pdv_key)

    vars_dict = {
        "numero_venda": body.numero_venda,
        "nome_cliente": body.nome_cliente,
        "valor_total": body.valor_total,
        "forma_pagamento": body.forma_pagamento,
        "data": body.data,
        "observacao": body.observacao or "",
        "itens": _fmt_itens(body.itens),
    }
    mensagem = templates.render("venda_realizada", vars_dict)

    return await _enviar(
        phone=body.phone,
        mensagem=mensagem,
        arquivo_base64=body.arquivo_base64,
        arquivo_nome=body.arquivo_nome or (f"comprovante_{body.numero_venda}.pdf" if body.arquivo_base64 else None),
        caption=f"Comprovante #{body.numero_venda}",
        sessao_id=body.sessao_id,
    )


@router.post("/nota-fiscal", summary="Enviar NF-e")
async def nota_fiscal(
    body: NotaFiscalRequest,
    x_pdv_key: Optional[str] = Header(default=None),
):
    """Atalho para envio de Nota Fiscal Eletrônica."""
    _check_key(x_pdv_key)

    vars_dict = {
        "numero_nf": body.numero_nf,
        "nome_cliente": body.nome_cliente,
        "valor_total": body.valor_total,
        "data": body.data,
        "chave_acesso": body.chave_acesso or "",
        "link_danfe": body.link_danfe or "",
    }
    mensagem = templates.render("nota_fiscal", vars_dict)

    return await _enviar(
        phone=body.phone,
        mensagem=mensagem,
        arquivo_base64=body.arquivo_base64,
        arquivo_nome=body.arquivo_nome or (f"nfe_{body.numero_nf}.pdf" if body.arquivo_base64 else None),
        caption=f"NF-e Nº {body.numero_nf}",
        sessao_id=body.sessao_id,
    )


@router.post("/boleto", summary="Enviar boleto")
async def boleto(
    body: BoletoRequest,
    x_pdv_key: Optional[str] = Header(default=None),
):
    """Atalho para envio de boleto bancário."""
    _check_key(x_pdv_key)

    vars_dict = {
        "nome_cliente": body.nome_cliente,
        "valor_total": body.valor_total,
        "data_vencimento": body.data_vencimento,
        "linha_digitavel": body.linha_digitavel or "",
        "link_boleto": body.link_boleto or "",
    }
    mensagem = templates.render("boleto", vars_dict)

    return await _enviar(
        phone=body.phone,
        mensagem=mensagem,
        arquivo_base64=body.arquivo_base64,
        arquivo_nome=body.arquivo_nome or ("boleto.pdf" if body.arquivo_base64 else None),
        caption="Boleto bancário",
        sessao_id=body.sessao_id,
    )


# ── Templates CRUD ─────────────────────────────────────────────────────────────

@router.get("/templates", summary="Listar templates")
async def listar_templates(x_pdv_key: Optional[str] = Header(default=None)):
    """Lista todos os templates de mensagem configurados."""
    _check_key(x_pdv_key)
    return templates.get_all()


@router.put("/templates", summary="Criar/editar template")
async def salvar_template(
    body: TemplateUpsert,
    x_pdv_key: Optional[str] = Header(default=None),
):
    """Cria ou edita um template de mensagem."""
    _check_key(x_pdv_key)
    templates.save_template(body.evento, body.mensagem, body.descricao, body.ativo)
    return {"ok": True, "evento": body.evento}


@router.delete("/templates/{evento}", summary="Remover template")
async def deletar_template(
    evento: str,
    x_pdv_key: Optional[str] = Header(default=None),
):
    """Remove um template personalizado."""
    _check_key(x_pdv_key)
    ok = templates.delete_template(evento)
    if not ok:
        raise HTTPException(404, f"Template '{evento}' não encontrado")
    return {"ok": True}


# ── Painel de templates (UI web) ───────────────────────────────────────────────

@router.get("/templates/painel", response_class=HTMLResponse, include_in_schema=False)
async def painel_templates():
    """Painel web para visualizar e editar templates de mensagem."""
    all_tmpl = templates.get_all()
    rows = ""
    for evento, t in all_tmpl.items():
        ativo_badge = (
            '<span style="background:#dcfce7;color:#15803d;padding:.1rem .5rem;'
            'border-radius:10px;font-size:.72rem;font-weight:700">Ativo</span>'
            if t.get("ativo", True) else
            '<span style="background:#f1f5f9;color:#475569;padding:.1rem .5rem;'
            'border-radius:10px;font-size:.72rem;font-weight:700">Inativo</span>'
        )
        msg_escaped = t.get("mensagem", "").replace("<", "&lt;").replace(">", "&gt;")
        rows += f"""
        <tr>
          <td><code style="font-size:.85rem">{evento}</code></td>
          <td style="font-size:.83rem;color:#6b7280">{t.get('descricao','')}</td>
          <td>{ativo_badge}</td>
          <td>
            <button onclick="editarTemplate('{evento}')"
              style="padding:.25rem .6rem;border:1px solid #e4e6ea;border-radius:6px;
                     background:#fff;cursor:pointer;font-size:.78rem">Editar</button>
          </td>
        </tr>"""

    tmpl_json = __import__('json').dumps(all_tmpl, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <title>Templates — ZapDin PDV</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
         background:#f4f6f9;padding:1.5rem;color:#1a1d23}}
    h1{{font-size:1.25rem;font-weight:800;color:#3d7f1f;margin-bottom:.25rem}}
    .sub{{color:#6b7280;font-size:.85rem;margin-bottom:1.5rem}}
    table{{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;
           overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
    th{{background:#f8faf5;font-size:.75rem;font-weight:700;color:#6b7280;
        text-transform:uppercase;letter-spacing:.05em;padding:.65rem 1rem;text-align:left}}
    td{{padding:.7rem 1rem;font-size:.85rem;border-top:1px solid #f1f5f9}}
    .modal-bg{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.4);
               align-items:center;justify-content:center;z-index:100}}
    .modal-bg.open{{display:flex}}
    .modal{{background:#fff;border-radius:12px;padding:1.5rem;width:100%;max-width:540px;
            box-shadow:0 8px 32px rgba(0,0,0,.18)}}
    .modal h2{{font-size:1rem;font-weight:700;margin-bottom:1rem}}
    label{{font-size:.8rem;font-weight:600;color:#374151;display:block;margin-bottom:.3rem}}
    textarea,input{{width:100%;border:1px solid #e4e6ea;border-radius:8px;
                    padding:.55rem .75rem;font-size:.875rem;font-family:inherit;
                    outline:none;resize:vertical}}
    textarea:focus,input:focus{{border-color:#3d7f1f}}
    .btn{{background:#3d7f1f;color:#fff;border:none;border-radius:8px;
          padding:.55rem 1.25rem;font-size:.875rem;font-weight:600;cursor:pointer}}
    .btn-ghost{{background:transparent;border:1px solid #e4e6ea;color:#374151}}
    .vars-hint{{background:#f8faf5;border-radius:8px;padding:.75rem;margin:.75rem 0;
                font-size:.78rem;color:#374151;line-height:1.7}}
    code{{background:#e8f5e9;color:#2d6a0a;padding:.05rem .3rem;border-radius:4px}}
  </style>
</head>
<body>
  <h1>📝 Templates de Mensagem</h1>
  <p class="sub">Configure as mensagens enviadas para cada evento do ERP. As variáveis entre {{chaves}} são substituídas pelos dados enviados.</p>

  <table>
    <thead>
      <tr><th>Evento</th><th>Descrição</th><th>Status</th><th>Ação</th></tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>

  <!-- Modal edição -->
  <div class="modal-bg" id="modalBg">
    <div class="modal">
      <h2>✏️ Editar Template: <span id="modalEvento" style="color:#3d7f1f"></span></h2>
      <div style="margin-bottom:.75rem">
        <label>Descrição</label>
        <input type="text" id="inpDesc" placeholder="Descrição do template" />
      </div>
      <div>
        <label>Mensagem</label>
        <div class="vars-hint" id="varsHint">Variáveis disponíveis para este evento.</div>
        <textarea id="inpMsg" rows="8" placeholder="Digite a mensagem..."></textarea>
      </div>
      <div style="display:flex;align-items:center;gap:.75rem;margin-top:.75rem">
        <label style="display:flex;align-items:center;gap:.4rem;cursor:pointer;font-size:.85rem;margin:0">
          <input type="checkbox" id="chkAtivo" style="width:auto;accent-color:#3d7f1f"> Ativo
        </label>
      </div>
      <div style="display:flex;gap:.5rem;justify-content:flex-end;margin-top:1rem">
        <button class="btn btn-ghost" onclick="fecharModal()">Cancelar</button>
        <button class="btn" onclick="salvarTemplate()">💾 Salvar</button>
      </div>
      <div id="modalMsg" style="margin-top:.5rem;font-size:.82rem;color:#15803d"></div>
    </div>
  </div>

<script>
const TEMPLATES = {tmpl_json};
const KEY = '{settings.pdv_api_key}';
const BASE = 'http://localhost:{settings.pdv_port}';

const VARS_POR_EVENTO = {{
  venda_realizada: ['nome_cliente','numero_venda','valor_total','forma_pagamento','data','itens','observacao'],
  nota_fiscal:     ['nome_cliente','numero_nf','valor_total','data','chave_acesso','link_danfe'],
  boleto:          ['nome_cliente','valor_total','data_vencimento','linha_digitavel','link_boleto'],
  pedido_confirmado: ['nome_cliente','numero_pedido','valor_total','previsao_entrega'],
  entrega_realizada: ['nome_cliente','numero_pedido','data'],
  cobranca:        ['nome_cliente','valor_total','data_vencimento'],
  custom:          ['mensagem'],
}};

let _eventoAtual = '';

function editarTemplate(evento) {{
  _eventoAtual = evento;
  const t = TEMPLATES[evento] || {{}};
  document.getElementById('modalEvento').textContent = evento;
  document.getElementById('inpDesc').value = t.descricao || '';
  document.getElementById('inpMsg').value = t.mensagem || '';
  document.getElementById('chkAtivo').checked = t.ativo !== false;
  document.getElementById('modalMsg').textContent = '';

  const vars = VARS_POR_EVENTO[evento] || [];
  document.getElementById('varsHint').innerHTML = vars.length
    ? 'Variáveis: ' + vars.map(v => `<code>{{${v}}}</code>`).join(' ')
    : 'Use <code>{{nome_var}}</code> para variáveis customizadas.';

  document.getElementById('modalBg').classList.add('open');
}}

function fecharModal() {{
  document.getElementById('modalBg').classList.remove('open');
}}

async function salvarTemplate() {{
  const body = {{
    evento: _eventoAtual,
    descricao: document.getElementById('inpDesc').value,
    mensagem: document.getElementById('inpMsg').value,
    ativo: document.getElementById('chkAtivo').checked,
  }};
  try {{
    const r = await fetch(`${{BASE}}/erp/templates`, {{
      method:'PUT', headers:{{'Content-Type':'application/json','X-PDV-Key':KEY}},
      body: JSON.stringify(body)
    }});
    if (r.ok) {{
      document.getElementById('modalMsg').textContent = '✅ Salvo!';
      TEMPLATES[_eventoAtual] = {{descricao:body.descricao,mensagem:body.mensagem,ativo:body.ativo}};
      setTimeout(() => {{ fecharModal(); location.reload(); }}, 800);
    }} else {{
      document.getElementById('modalMsg').textContent = '❌ Erro ao salvar.';
    }}
  }} catch(e) {{
    document.getElementById('modalMsg').textContent = '❌ ' + e.message;
  }}
}}

document.getElementById('modalBg').addEventListener('click', e => {{
  if (e.target === document.getElementById('modalBg')) fecharModal();
}});
</script>
</body>
</html>"""
