"""
ZapDin PDV — Servidor local. WhatsApp conecta e envia pela máquina do cliente.
Credenciais e configuração vêm do ZapDin App remoto.

Fluxo:
  ERP → PDV (local:4600) → Evolution API local (local:8080) → WhatsApp
                         → ZapDin App remoto (credenciais/config)

Porta padrão: 4600
Auth ERP: header X-PDV-Key
"""
import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from .config import settings
from .evolution_local import local_evo
from .zapdin_client import zapdin_app
from .erp_router import router as erp_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ZapDin PDV iniciando na porta %s", settings.pdv_port)

    # Tenta autenticar no ZapDin App remoto (credenciais)
    r = await zapdin_app.verificar_conexao()
    if r["ok"]:
        logger.info("✅ Conectado ao ZapDin App remoto: %s", settings.zapdin_url)
    else:
        logger.warning("⚠️  ZapDin App remoto inacessível. Funcionando em modo offline.")

    yield

    # Encerra sessões locais
    await local_evo.stop()
    logger.info("ZapDin PDV encerrado")


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="ZapDin PDV",
    version="1.0.0",
    description="WhatsApp local via Evolution API. Credenciais via ZapDin App remoto.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(erp_router)


# ── Auth ERP ──────────────────────────────────────────────────────────────────

def _check_key(key: Optional[str]):
    if settings.pdv_api_key and key != settings.pdv_api_key:
        raise HTTPException(status_code=401, detail="X-PDV-Key inválida")


# ── Modelos ────────────────────────────────────────────────────────────────────

class CriarSessaoBody(BaseModel):
    nome: str = "PDV"

class EnviarTextoBody(BaseModel):
    phone: str
    message: str
    sessao_id: Optional[str] = None   # None = usa primeira sessão conectada

class EnviarArquivoBody(BaseModel):
    phone: str
    filename: str
    file_base64: str                   # base64 puro ou data URI
    caption: Optional[str] = ""
    sessao_id: Optional[str] = None

class EnviarArquivoUrlBody(BaseModel):
    phone: str
    url: str
    filename: str
    caption: Optional[str] = ""
    sessao_id: Optional[str] = None


# ── Endpoints gerais ───────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "app": "ZapDin PDV",
        "version": "1.0.0",
        "pdv": settings.pdv_nome,
        "evolution_local": settings.evolution_url,
        "zapdin_app": settings.zapdin_url,
        "docs": "/docs",
    }


@app.get("/status")
async def status(x_pdv_key: Optional[str] = Header(default=None)):
    """Status completo: sessões locais + conexão com ZapDin App remoto."""
    _check_key(x_pdv_key)
    sessoes = local_evo.get_status()
    conectadas = [s for s in sessoes if s["status"] == "connected"]
    app_remoto = await zapdin_app.verificar_conexao()
    return {
        "ok": True,
        "pdv": settings.pdv_nome,
        "evolution_local": settings.evolution_url,
        "sessoes_total": len(sessoes),
        "sessoes_conectadas": len(conectadas),
        "sessoes": sessoes,
        "zapdin_app": {
            "url": settings.zapdin_url,
            "conectado": app_remoto["ok"],
        },
    }


# ── WhatsApp LOCAL ─────────────────────────────────────────────────────────────

@app.get("/whatsapp/sessoes")
async def listar_sessoes(x_pdv_key: Optional[str] = Header(default=None)):
    """Lista as sessões WhatsApp gerenciadas localmente por este PDV."""
    _check_key(x_pdv_key)
    return local_evo.get_status()


@app.post("/whatsapp/sessoes")
async def criar_sessao(
    body: CriarSessaoBody,
    x_pdv_key: Optional[str] = Header(default=None),
):
    """
    Cria uma nova sessão WhatsApp no Evolution API LOCAL.
    O WhatsApp conecta nesta máquina — usa recursos locais.
    Acesse /whatsapp/sessoes/{id}/qr-page para escanear o QR.
    """
    _check_key(x_pdv_key)
    sessao_id = str(uuid.uuid4())[:8]
    sess = await local_evo.add_session(sessao_id, body.nome)
    return {
        "ok": True,
        "id": sessao_id,
        "nome": body.nome,
        "status": sess.status,
        "qr_page": f"http://localhost:{settings.pdv_port}/whatsapp/sessoes/{sessao_id}/qr-page",
    }


@app.delete("/whatsapp/sessoes/{sessao_id}")
async def remover_sessao(
    sessao_id: str,
    x_pdv_key: Optional[str] = Header(default=None),
):
    """Remove sessão local e desconecta do Evolution API local."""
    _check_key(x_pdv_key)
    await local_evo.remove_session(sessao_id)
    return {"ok": True}


@app.get("/whatsapp/sessoes/{sessao_id}/qr")
async def get_qr_json(
    sessao_id: str,
    x_pdv_key: Optional[str] = Header(default=None),
):
    """Retorna o QR code em base64 (para integração com ERP)."""
    _check_key(x_pdv_key)
    qr = local_evo.get_qr(sessao_id)
    if not qr:
        raise HTTPException(404, "QR não disponível. A sessão existe?")
    return {"ok": True, "qr": qr}


@app.get("/whatsapp/sessoes/{sessao_id}/qr-page", response_class=HTMLResponse)
async def qr_page(sessao_id: str):
    """
    Página HTML para escanear o QR code localmente.
    Não exige X-PDV-Key — é aberta no navegador da máquina local.
    Detecta automaticamente quando o WhatsApp conecta.
    """
    sess_data = next((s for s in local_evo.get_status() if s["id"] == sessao_id), None)
    nome = sess_data["nome"] if sess_data else sessao_id

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Conectar WhatsApp — {nome}</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
         background:#f0f2f5;display:flex;align-items:center;justify-content:center;
         min-height:100vh;padding:1rem}}
    .card{{background:#fff;border-radius:16px;box-shadow:0 4px 24px rgba(0,0,0,.12);
           padding:2rem;text-align:center;max-width:420px;width:100%}}
    .logo{{font-size:1.4rem;font-weight:800;color:#3d7f1f;margin-bottom:.2rem}}
    .sub{{color:#6b7280;font-size:.85rem;margin-bottom:1.25rem}}
    .badge{{display:inline-flex;align-items:center;gap:.5rem;padding:.35rem .9rem;
            border-radius:20px;font-size:.82rem;font-weight:600;margin-bottom:1rem}}
    .wait{{background:#fef9c3;color:#854d0e}}
    .scan{{background:#dbeafe;color:#1e40af}}
    .ok  {{background:#dcfce7;color:#15803d}}
    .err {{background:#fee2e2;color:#991b1b}}
    .dot{{width:8px;height:8px;border-radius:50%;background:currentColor;
          animation:pulse 1.4s infinite}}
    @keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.25}}}}
    .qr-wrap{{width:272px;height:272px;margin:0 auto 1.25rem;border:2px solid #e4e6ea;
              border-radius:12px;display:flex;align-items:center;justify-content:center;
              background:#fafafa;overflow:hidden;position:relative}}
    .qr-wrap img{{width:252px;height:252px}}
    .overlay{{position:absolute;inset:0;background:rgba(255,255,255,.93);
              display:flex;flex-direction:column;align-items:center;
              justify-content:center;border-radius:10px;gap:.5rem}}
    .steps{{text-align:left;background:#f8faf5;border-radius:10px;
            padding:.9rem 1.1rem;margin-bottom:1.1rem}}
    .steps li{{font-size:.83rem;color:#374151;margin-bottom:.35rem;line-height:1.5}}
    .btn{{background:#3d7f1f;color:#fff;border:none;border-radius:8px;
          padding:.55rem 1.25rem;font-size:.88rem;font-weight:600;cursor:pointer;
          width:100%;transition:background .2s}}
    .btn:hover{{background:#2d5f17}}
    .btn:disabled{{background:#9ca3af;cursor:not-allowed}}
    .footer{{font-size:.75rem;color:#9ca3af;margin-top:.85rem}}
    code{{background:#f4f6f9;padding:.1rem .35rem;border-radius:4px;font-size:.78rem}}
  </style>
</head>
<body>
<div class="card">
  <div class="logo">📱 ZapDin PDV</div>
  <div class="sub">
    Sessão <code>{nome}</code> · conexão local
  </div>

  <div id="badge" class="badge wait">
    <div class="dot"></div>
    <span id="badgeTxt">Aguardando QR…</span>
  </div>

  <div class="qr-wrap">
    <img id="qrImg" src="" alt="QR" style="display:none">
    <div class="overlay" id="overlay">
      <div style="font-size:2.2rem">⏳</div>
      <div style="font-size:.82rem;color:#6b7280">Gerando QR code…</div>
    </div>
  </div>

  <ol class="steps">
    <li>Abra o <strong>WhatsApp</strong> no celular</li>
    <li>Toque em <strong>⋮ Mais opções</strong> → <strong>Aparelhos conectados</strong></li>
    <li>Toque em <strong>Conectar um aparelho</strong></li>
    <li>Aponte a câmera para o QR acima</li>
  </ol>

  <button class="btn" id="btnAtualizar" onclick="atualizarQR()">🔄 Atualizar QR</button>
  <div class="footer" id="footerMsg">Atualizando automaticamente…</div>
</div>

<script>
const SESSAO = '{sessao_id}';
const BASE   = 'http://localhost:{settings.pdv_port}';
const KEY    = '{settings.pdv_api_key}';
let _running = true, _timer = null;

function setBadge(tipo, txt) {{
  const b = document.getElementById('badge');
  b.className = 'badge ' + tipo;
  document.getElementById('badgeTxt').textContent = txt;
}}

async function carregarQR() {{
  try {{
    const r = await fetch(`${{BASE}}/whatsapp/sessoes/${{SESSAO}}/qr`,
      {{headers:{{'X-PDV-Key':KEY}}}});
    if (r.ok) {{
      const d = await r.json();
      if (d.qr) {{
        const img = document.getElementById('qrImg');
        img.src = d.qr.startsWith('data:') ? d.qr : 'data:image/png;base64,' + d.qr;
        img.style.display = '';
        document.getElementById('overlay').style.display = 'none';
        setBadge('scan', 'Escaneie com o celular');
        return true;
      }}
    }}
  }} catch(e) {{}}
  return false;
}}

async function checarStatus() {{
  try {{
    const r = await fetch(`${{BASE}}/status`, {{headers:{{'X-PDV-Key':KEY}}}});
    if (!r.ok) return 'error';
    const d = await r.json();
    const s = (d.sessoes||[]).find(x => x.id === SESSAO);
    return s ? s.status : 'unknown';
  }} catch(e) {{ return 'error'; }}
}}

async function poll() {{
  if (!_running) return;
  const st = await checarStatus();

  if (st === 'connected') {{
    _running = false;
    clearTimeout(_timer);
    setBadge('ok', '✅ WhatsApp Conectado!');
    document.getElementById('overlay').style.display = 'flex';
    document.getElementById('overlay').innerHTML =
      '<div style="font-size:3rem">✅</div>' +
      '<div style="font-size:.95rem;font-weight:700;color:#15803d;margin-top:.4rem">Conectado com sucesso!</div>' +
      '<div style="font-size:.8rem;color:#6b7280;margin-top:.25rem">Pode fechar esta janela.</div>';
    document.getElementById('btnAtualizar').disabled = true;
    document.getElementById('footerMsg').textContent = 'Conectado! Pronto para enviar.';
    return;
  }}

  if (st === 'connecting') {{
    setBadge('scan', 'Conectando…');
    document.getElementById('footerMsg').textContent = 'QR escaneado, aguardando confirmação…';
  }} else {{
    await carregarQR();
    document.getElementById('footerMsg').textContent = 'Próxima atualização em 15s…';
  }}
  _timer = setTimeout(poll, 15000);
}}

async function atualizarQR() {{
  document.getElementById('footerMsg').textContent = 'Atualizando…';
  clearTimeout(_timer);
  await carregarQR();
  _timer = setTimeout(poll, 15000);
}}

poll();
</script>
</body>
</html>"""


# ── Envio via Evolution API LOCAL ─────────────────────────────────────────────

@app.post("/enviar/texto")
async def enviar_texto(
    body: EnviarTextoBody,
    x_pdv_key: Optional[str] = Header(default=None),
):
    """Envia texto via WhatsApp LOCAL (usa recursos desta máquina)."""
    _check_key(x_pdv_key)
    sessao_id = body.sessao_id or local_evo.pick_connected()
    if not sessao_id:
        raise HTTPException(503, "Nenhuma sessão WhatsApp conectada localmente")
    ok, err = await local_evo.send_text(sessao_id, body.phone, body.message)
    if not ok:
        raise HTTPException(400, err or "Erro ao enviar mensagem")
    return {"ok": True, "sessao_id": sessao_id, "phone": body.phone}


@app.post("/enviar/arquivo")
async def enviar_arquivo(
    body: EnviarArquivoBody,
    x_pdv_key: Optional[str] = Header(default=None),
):
    """Envia arquivo (base64) via WhatsApp LOCAL."""
    _check_key(x_pdv_key)
    sessao_id = body.sessao_id or local_evo.pick_connected()
    if not sessao_id:
        raise HTTPException(503, "Nenhuma sessão WhatsApp conectada localmente")
    ok, err = await local_evo.send_file_b64(
        sessao_id, body.phone, body.filename, body.file_base64, body.caption or ""
    )
    if not ok:
        raise HTTPException(400, err or "Erro ao enviar arquivo")
    return {"ok": True, "sessao_id": sessao_id, "phone": body.phone, "filename": body.filename}


@app.post("/enviar/arquivo-url")
async def enviar_arquivo_url(
    body: EnviarArquivoUrlBody,
    x_pdv_key: Optional[str] = Header(default=None),
):
    """Baixa arquivo de uma URL e envia via WhatsApp LOCAL."""
    _check_key(x_pdv_key)
    import base64
    import httpx as _httpx

    sessao_id = body.sessao_id or local_evo.pick_connected()
    if not sessao_id:
        raise HTTPException(503, "Nenhuma sessão WhatsApp conectada localmente")
    try:
        async with _httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(body.url)
        r.raise_for_status()
        file_b64 = base64.b64encode(r.content).decode()
    except Exception as exc:
        raise HTTPException(400, f"Erro ao baixar arquivo: {exc}")

    ok, err = await local_evo.send_file_b64(
        sessao_id, body.phone, body.filename, file_b64, body.caption or ""
    )
    if not ok:
        raise HTTPException(400, err or "Erro ao enviar arquivo")
    return {"ok": True, "sessao_id": sessao_id, "phone": body.phone}


# ── Webhook do Evolution API LOCAL ────────────────────────────────────────────

@app.post("/evo-webhook")
async def evo_webhook(request: Request):
    """Recebe eventos do Evolution API LOCAL (QR, conexão)."""
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"ok": False}, status_code=400)
    local_evo.handle_webhook(payload)
    return {"ok": True}


# ── Configurações via ZapDin App remoto ───────────────────────────────────────

@app.get("/remoto/config")
async def config_remota(x_pdv_key: Optional[str] = Header(default=None)):
    """Busca configurações do ZapDin App remoto (mensagem padrão, etc.)."""
    _check_key(x_pdv_key)
    data = await zapdin_app.get_config()
    return {"ok": True, "config": data}


@app.get("/remoto/status")
async def status_remoto(x_pdv_key: Optional[str] = Header(default=None)):
    """Verifica conexão com o ZapDin App remoto."""
    _check_key(x_pdv_key)
    return await zapdin_app.verificar_conexao()


@app.get("/remoto/me")
async def me_remoto(x_pdv_key: Optional[str] = Header(default=None)):
    """Retorna dados do usuário autenticado no ZapDin App remoto."""
    _check_key(x_pdv_key)
    return await zapdin_app.get_me()


# ── Setup QR (configuração do PDV para o ERP) ─────────────────────────────────

@app.get("/setup/qr", response_class=HTMLResponse)
async def setup_qr():
    """Gera QR code de configuração para o ERP escanear e se conectar ao PDV."""
    import json, io, base64
    try:
        import qrcode
        from PIL import Image
        config_data = json.dumps({
            "pdv_url": f"http://localhost:{settings.pdv_port}",
            "pdv_key": settings.pdv_api_key,
            "pdv_nome": settings.pdv_nome,
        })
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(config_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        img_b64 = base64.b64encode(buf.getvalue()).decode()
        qr_html = f'<img src="data:image/png;base64,{img_b64}" width="260" height="260" />'
    except ImportError:
        qr_html = f'<p style="color:#854d0e">Instale: pip install qrcode[pil]</p>'

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>ZapDin PDV — Setup</title>
<style>
  body{{font-family:sans-serif;display:flex;align-items:center;justify-content:center;
        min-height:100vh;background:#f4f6f9;padding:1rem}}
  .card{{background:#fff;border-radius:12px;padding:2rem;text-align:center;
         max-width:380px;box-shadow:0 2px 12px rgba(0,0,0,.1)}}
  h2{{color:#3d7f1f;margin-bottom:.3rem}}
  p{{color:#6b7280;font-size:.88rem;margin:.4rem 0}}
  code{{background:#f4f6f9;padding:.15rem .4rem;border-radius:4px;font-size:.82rem}}
</style>
</head>
<body><div class="card">
  <h2>📱 ZapDin PDV</h2>
  <p>Escaneie no ERP para configurar a integração.</p>
  {qr_html}
  <p>PDV: <code>{settings.pdv_nome}</code></p>
  <p>URL: <code>http://localhost:{settings.pdv_port}</code></p>
  <p>ZapDin App: <code>{settings.zapdin_url}</code></p>
</div></body></html>"""


# ── Entrada ────────────────────────────────────────────────────────────────────

def main():
    uvicorn.run(app, host="127.0.0.1", port=settings.pdv_port, log_level="info")


if __name__ == "__main__":
    main()
