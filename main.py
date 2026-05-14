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
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from pydantic import BaseModel

from .config import settings
from .evolution_local import local_evo
from .zapdin_client import zapdin_app
from .erp_router import router as erp_router
from .docs_router import router as docs_router

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
app.include_router(docs_router)

# Arquivos estáticos (pdv.html, etc.)
_static_path = Path(__file__).parent / "static"
if _static_path.exists():
    app.mount("/static", StaticFiles(directory=str(_static_path)), name="static")


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

@app.get("/info")
async def info():
    """Status JSON para integrações programáticas."""
    return {
        "app": "ZapDin PDV",
        "version": "1.0.0",
        "pdv": settings.pdv_nome,
        "modo_envio": settings.modo_envio,
        "zapdin_url": settings.zapdin_url,
        "zapdin_erp_token": settings.zapdin_erp_token,
        "docs": "/docs",
    }


_STATIC_DIR = Path(__file__).parent / "static"

@app.get("/", response_class=FileResponse)
async def terminal_pdv():
    """Tela principal de PDV."""
    return FileResponse(_STATIC_DIR / "pdv.html")


# ROTA ANTIGA — mantida para compatibilidade (não remova)
@app.get("/_legacy_pdv", response_class=HTMLResponse)
async def terminal_pdv_legacy():
    """Legado."""
    from . import produtos as cat
    import json as _json

    prods = cat.listar()
    cats  = cat.categorias()
    prods_json = _json.dumps(prods, ensure_ascii=False)
    cats_json  = _json.dumps(cats,  ensure_ascii=False)
    modo_label = "ZapDin App" if settings.modo_envio == "app" else "Evolution Local"
    token_ok   = bool(settings.zapdin_erp_token) if settings.modo_envio == "app" else True

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>ZapDin PDV</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    :root{{
      --green:#3d7f1f;--green-d:#2d5f17;--green-l:#7cdc44;
      --bg:#f0f2f5;--surface:#fff;--border:#e4e6ea;
      --text:#1a1d23;--muted:#6b7280;--red:#dc2626;--yellow:#d97706;
    }}
    body{{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);
         height:100vh;display:flex;flex-direction:column;overflow:hidden}}

    /* ── Header ── */
    .hdr{{background:var(--green);color:#fff;padding:.6rem 1.25rem;
          display:flex;align-items:center;justify-content:space-between;
          flex-shrink:0;box-shadow:0 2px 6px rgba(0,0,0,.2)}}
    .hdr-left{{display:flex;align-items:center;gap:.75rem}}
    .hdr h1{{font-size:1.05rem;font-weight:800;letter-spacing:-.01em}}
    .hdr .sub{{font-size:.72rem;opacity:.8;margin-top:.05rem}}
    .hdr-right{{display:flex;align-items:center;gap:.6rem}}
    .badge{{padding:.2rem .6rem;border-radius:10px;font-size:.7rem;font-weight:700}}
    .badge-ok{{background:rgba(255,255,255,.2);color:#fff}}
    .badge-warn{{background:#fef3c7;color:#92400e}}
    .hdr-btn{{background:rgba(255,255,255,.15);border:none;color:#fff;
              border-radius:8px;padding:.35rem .75rem;font-size:.78rem;
              font-weight:600;cursor:pointer;display:flex;align-items:center;gap:.35rem}}
    .hdr-btn:hover{{background:rgba(255,255,255,.25)}}
    #wa-badge{{padding:.2rem .7rem;border-radius:10px;font-size:.72rem;font-weight:700;
               background:rgba(255,255,255,.15);color:#fff;cursor:pointer}}
    #wa-badge.connected{{background:#dcfce7;color:#15803d}}
    #wa-badge.disconnected{{background:#fee2e2;color:#991b1b}}

    /* ── Body layout ── */
    .body{{display:flex;flex:1;overflow:hidden;gap:0}}

    /* ── LEFT — Catálogo ── */
    .catalog{{display:flex;flex-direction:column;flex:1;min-width:0;
              border-right:1px solid var(--border);background:var(--bg)}}
    .cat-toolbar{{background:var(--surface);padding:.75rem 1rem;border-bottom:1px solid var(--border);
                  display:flex;align-items:center;gap:.6rem;flex-shrink:0;flex-wrap:wrap}}
    .search-wrap{{position:relative;flex:1;min-width:140px}}
    .search-wrap input{{width:100%;padding:.45rem .75rem .45rem 2rem;border:1px solid var(--border);
                         border-radius:8px;font-size:.85rem;font-family:inherit;outline:none;background:#f8fafc}}
    .search-wrap input:focus{{border-color:var(--green);background:#fff}}
    .search-ico{{position:absolute;left:.6rem;top:50%;transform:translateY(-50%);
                 font-size:.85rem;opacity:.4;pointer-events:none}}
    .cat-tabs{{display:flex;gap:.4rem;flex-wrap:wrap}}
    .cat-tab{{border:1px solid var(--border);background:var(--surface);border-radius:20px;
              padding:.3rem .75rem;font-size:.75rem;font-weight:600;cursor:pointer;
              color:var(--muted);white-space:nowrap;transition:all .15s}}
    .cat-tab:hover{{border-color:var(--green);color:var(--green)}}
    .cat-tab.active{{background:var(--green);border-color:var(--green);color:#fff}}
    .prod-grid{{flex:1;overflow-y:auto;padding:.75rem 1rem;
                display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:.6rem}}
    .prod-card{{background:var(--surface);border:1.5px solid var(--border);border-radius:12px;
                padding:.85rem .75rem;cursor:pointer;transition:all .15s;
                display:flex;flex-direction:column;gap:.35rem;user-select:none}}
    .prod-card:hover{{border-color:var(--green);box-shadow:0 2px 12px rgba(61,127,31,.12);
                      transform:translateY(-1px)}}
    .prod-card:active{{transform:translateY(0);box-shadow:none}}
    .prod-card.hidden{{display:none}}
    .prod-emoji{{font-size:1.6rem;line-height:1}}
    .prod-nome{{font-size:.8rem;font-weight:600;line-height:1.3;color:var(--text)}}
    .prod-preco{{font-size:.95rem;font-weight:800;color:var(--green);margin-top:auto}}
    .prod-un{{font-size:.65rem;color:var(--muted);font-weight:500}}

    /* ── RIGHT — Carrinho ── */
    .cart-panel{{width:340px;flex-shrink:0;display:flex;flex-direction:column;
                 background:var(--surface)}}
    .cart-head{{padding:.9rem 1.1rem .7rem;border-bottom:1px solid var(--border);flex-shrink:0}}
    .cart-head h2{{font-size:.9rem;font-weight:700;display:flex;align-items:center;
                   justify-content:space-between}}
    .cart-items{{flex:1;overflow-y:auto;padding:.5rem .9rem}}
    .cart-empty{{text-align:center;padding:2rem 1rem;color:var(--muted);font-size:.85rem}}
    .cart-item{{display:grid;grid-template-columns:1fr auto;align-items:center;
                gap:.4rem;padding:.5rem 0;border-bottom:1px solid #f1f5f9}}
    .cart-item:last-child{{border-bottom:none}}
    .ci-nome{{font-size:.8rem;font-weight:600;line-height:1.3}}
    .ci-sub{{font-size:.72rem;color:var(--muted)}}
    .ci-ctrl{{display:flex;align-items:center;gap:.3rem}}
    .ci-btn{{width:26px;height:26px;border-radius:6px;border:1px solid var(--border);
             background:var(--bg);cursor:pointer;font-size:.85rem;font-weight:700;
             display:flex;align-items:center;justify-content:center;flex-shrink:0;
             transition:background .1s}}
    .ci-btn:hover{{background:#e8f5e9;border-color:var(--green);color:var(--green)}}
    .ci-btn.del{{color:var(--red);border-color:#fecaca}}
    .ci-btn.del:hover{{background:#fee2e2}}
    .ci-qty{{font-size:.85rem;font-weight:700;min-width:24px;text-align:center}}
    .ci-val{{font-size:.83rem;font-weight:700;color:var(--green);white-space:nowrap;
             min-width:64px;text-align:right}}

    /* ── Totais ── */
    .cart-totals{{padding:.75rem 1.1rem;border-top:1px solid var(--border);
                  border-bottom:1px solid var(--border);flex-shrink:0}}
    .tot-row{{display:flex;justify-content:space-between;font-size:.82rem;
              padding:.2rem 0;color:var(--muted)}}
    .tot-row.total{{font-size:1.15rem;font-weight:800;color:var(--text);
                    margin-top:.4rem;padding-top:.4rem;border-top:1px solid var(--border)}}

    /* ── Formulário cliente ── */
    .cart-form{{padding:.75rem 1.1rem;border-bottom:1px solid var(--border);flex-shrink:0}}
    .cart-form h3{{font-size:.78rem;font-weight:700;color:var(--muted);
                   text-transform:uppercase;letter-spacing:.06em;margin-bottom:.6rem}}
    .f-field{{margin-bottom:.5rem}}
    .f-field label{{font-size:.72rem;font-weight:600;color:var(--muted);display:block;margin-bottom:.2rem}}
    .f-field input{{width:100%;border:1px solid var(--border);border-radius:8px;
                    padding:.45rem .65rem;font-size:.85rem;font-family:inherit;outline:none}}
    .f-field input:focus{{border-color:var(--green)}}
    .pgto-grid{{display:grid;grid-template-columns:1fr 1fr;gap:.4rem;margin-top:.5rem}}
    .pgto-btn{{border:1.5px solid var(--border);background:var(--surface);border-radius:8px;
               padding:.4rem .5rem;font-size:.75rem;font-weight:600;cursor:pointer;
               color:var(--muted);text-align:center;transition:all .15s}}
    .pgto-btn.active{{background:var(--green);border-color:var(--green);color:#fff}}
    .pgto-btn:hover:not(.active){{border-color:var(--green);color:var(--green)}}

    /* ── Botão finalizar ── */
    .cart-actions{{padding:.85rem 1.1rem;flex-shrink:0}}
    .btn-finalizar{{width:100%;background:var(--green);color:#fff;border:none;
                    border-radius:12px;padding:.85rem;font-size:1rem;font-weight:800;
                    cursor:pointer;display:flex;align-items:center;justify-content:center;
                    gap:.5rem;transition:all .2s;letter-spacing:.01em}}
    .btn-finalizar:hover:not(:disabled){{background:var(--green-d);
                                          box-shadow:0 4px 16px rgba(61,127,31,.35)}}
    .btn-finalizar:disabled{{background:#9ca3af;cursor:not-allowed}}
    .btn-limpar{{width:100%;margin-top:.4rem;background:transparent;border:1px solid var(--border);
                 border-radius:8px;padding:.5rem;font-size:.8rem;font-weight:600;
                 cursor:pointer;color:var(--muted)}}
    .btn-limpar:hover{{border-color:var(--red);color:var(--red)}}

    /* ── Modal ── */
    .modal-bg{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);
               align-items:center;justify-content:center;z-index:200;padding:1rem}}
    .modal-bg.open{{display:flex}}
    .modal{{background:var(--surface);border-radius:16px;padding:2rem;
            width:100%;max-width:440px;box-shadow:0 20px 60px rgba(0,0,0,.25);
            animation:popIn .2s ease}}
    @keyframes popIn{{from{{transform:scale(.9);opacity:0}}to{{transform:scale(1);opacity:1}}}}
    .modal h2{{font-size:1.2rem;font-weight:800;margin-bottom:.25rem}}
    .modal .sub{{color:var(--muted);font-size:.83rem;margin-bottom:1.25rem}}
    .recibo{{background:#f8fafc;border-radius:10px;padding:.9rem 1rem;font-size:.8rem;
             border:1px solid var(--border);margin-bottom:1.25rem;font-family:monospace;
             white-space:pre-wrap;line-height:1.7}}
    .modal-actions{{display:flex;gap:.6rem}}
    .btn-novo{{flex:1;background:var(--green);color:#fff;border:none;border-radius:10px;
               padding:.7rem;font-size:.9rem;font-weight:700;cursor:pointer}}
    .btn-wpp{{flex:1;background:#25D366;color:#fff;border:none;border-radius:10px;
              padding:.7rem;font-size:.9rem;font-weight:700;cursor:pointer;
              display:flex;align-items:center;justify-content:center;gap:.4rem}}

    /* Modal gerenciar produtos */
    .mprod-item{{display:flex;align-items:center;gap:.5rem;padding:.5rem 0;
                 border-bottom:1px solid var(--border);font-size:.82rem}}
    .mprod-nome{{flex:1;font-weight:600}}
    .mprod-cat{{color:var(--muted);font-size:.72rem;min-width:80px}}
    .mprod-preco{{font-weight:700;color:var(--green);min-width:60px;text-align:right}}
    .mprod-del{{background:none;border:none;cursor:pointer;color:var(--red);font-size:1rem;padding:.1rem .3rem}}

    /* Spinner */
    .spin{{display:inline-block;width:18px;height:18px;border:2.5px solid rgba(255,255,255,.4);
           border-top-color:#fff;border-radius:50%;animation:spin .7s linear infinite}}
    @keyframes spin{{to{{transform:rotate(360deg)}}}}
  </style>
</head>
<body>

<!-- Header -->
<div class="hdr">
  <div class="hdr-left">
    <div>
      <h1>🛒 ZapDin PDV</h1>
      <div class="sub">{settings.pdv_nome} · {modo_label}</div>
    </div>
  </div>
  <div class="hdr-right">
    <span id="wa-badge" class="disconnected" onclick="abrirWA()" title="Clique para conectar WhatsApp">⏳ Verificando WA…</span>
    {'<span class="badge badge-warn">⚠️ Token não configurado</span>' if not token_ok else ''}
    <button class="hdr-btn" onclick="abrirGerenciarProdutos()">⚙️ Produtos</button>
    <a href="/testes" class="hdr-btn" style="text-decoration:none">🔬 Testes</a>
  </div>
</div>

<!-- Body -->
<div class="body">

  <!-- Catálogo -->
  <div class="catalog">
    <div class="cat-toolbar">
      <div class="search-wrap">
        <span class="search-ico">🔍</span>
        <input id="search" placeholder="Buscar produto…" oninput="filtrar()" autocomplete="off">
      </div>
      <div class="cat-tabs" id="cat-tabs">
        <button class="cat-tab active" data-cat="" onclick="filtrarCat(this,'')">Todos</button>
      </div>
    </div>
    <div class="prod-grid" id="prod-grid">
      <!-- Preenchido pelo JS -->
    </div>
  </div>

  <!-- Carrinho -->
  <div class="cart-panel">
    <div class="cart-head">
      <h2>
        Carrinho
        <span id="cart-count" style="background:#fee2e2;color:var(--red);
              border-radius:12px;font-size:.7rem;padding:.1rem .5rem;display:none">0</span>
      </h2>
    </div>

    <div class="cart-items" id="cart-items">
      <div class="cart-empty" id="cart-empty">
        <div style="font-size:2.5rem;margin-bottom:.5rem">🛒</div>
        Clique nos produtos para adicionar
      </div>
    </div>

    <div class="cart-totals">
      <div class="tot-row"><span>Subtotal</span><span id="tot-sub">R$ 0,00</span></div>
      <div class="tot-row"><span>Itens</span><span id="tot-itens">0</span></div>
      <div class="tot-row total"><span>TOTAL</span><span id="tot-total">R$ 0,00</span></div>
    </div>

    <div class="cart-form">
      <h3>📋 Dados do Cliente</h3>
      <div class="f-field">
        <label>Nome do cliente</label>
        <input id="cli-nome" placeholder="Ex: João Silva" autocomplete="off">
      </div>
      <div class="f-field">
        <label>Telefone (com DDD)</label>
        <input id="cli-fone" placeholder="44999990000" type="tel" oninput="this.value=this.value.replace(/\D/g,'')">
      </div>
      <div style="margin-top:.5rem">
        <label style="font-size:.72rem;font-weight:600;color:var(--muted);display:block;margin-bottom:.35rem">Forma de pagamento</label>
        <div class="pgto-grid">
          <button class="pgto-btn active" data-pgto="PIX" onclick="selPgto(this)">💚 PIX</button>
          <button class="pgto-btn" data-pgto="Cartão de Débito" onclick="selPgto(this)">💳 Débito</button>
          <button class="pgto-btn" data-pgto="Cartão de Crédito" onclick="selPgto(this)">💳 Crédito</button>
          <button class="pgto-btn" data-pgto="Dinheiro" onclick="selPgto(this)">💵 Dinheiro</button>
        </div>
      </div>
    </div>

    <div class="cart-actions">
      <button class="btn-finalizar" id="btn-fin" onclick="finalizarVenda()" disabled>
        💚 FINALIZAR VENDA
      </button>
      <button class="btn-limpar" onclick="limparCarrinho()">🗑 Limpar carrinho</button>
    </div>
  </div>
</div>

<!-- Modal sucesso -->
<div class="modal-bg" id="modal-ok">
  <div class="modal">
    <h2>✅ Venda Finalizada!</h2>
    <p class="sub" id="m-sub">Mensagem enviada via WhatsApp com sucesso.</p>
    <div class="recibo" id="m-recibo"></div>
    <div class="modal-actions">
      <button class="btn-novo" onclick="novaVenda()">🆕 Nova Venda</button>
      <button class="btn-wpp" id="m-wpp" onclick="abrirWppDireto()">
        <span>📲</span> Ver no WA
      </button>
    </div>
  </div>
</div>

<!-- Modal erro -->
<div class="modal-bg" id="modal-err">
  <div class="modal">
    <h2>❌ Erro no Envio</h2>
    <p class="sub">A venda foi registrada mas houve um problema ao enviar a mensagem.</p>
    <div class="recibo" id="m-err-detail" style="color:var(--red)"></div>
    <div class="modal-actions">
      <button class="btn-novo" onclick="fecharModal('modal-err')">Fechar</button>
      <button class="btn-novo" style="background:var(--red)" onclick="fecharModal('modal-err');finalizarVenda()">🔄 Tentar novamente</button>
    </div>
  </div>
</div>

<!-- Modal gerenciar produtos -->
<div class="modal-bg" id="modal-prod">
  <div class="modal" style="max-width:560px">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem">
      <h2 style="font-size:1rem">⚙️ Gerenciar Produtos</h2>
      <button style="background:none;border:none;font-size:1.1rem;cursor:pointer"
              onclick="fecharModal('modal-prod')">✕</button>
    </div>
    <!-- Form novo produto -->
    <div style="display:grid;grid-template-columns:1fr auto auto auto;gap:.5rem;align-items:end;margin-bottom:.75rem">
      <div>
        <label style="font-size:.72rem;font-weight:600;color:var(--muted);display:block;margin-bottom:.2rem">Nome</label>
        <input id="np-nome" placeholder="Nome do produto" style="width:100%;border:1px solid var(--border);border-radius:7px;padding:.4rem .6rem;font-size:.82rem;font-family:inherit;outline:none">
      </div>
      <div>
        <label style="font-size:.72rem;font-weight:600;color:var(--muted);display:block;margin-bottom:.2rem">Preço</label>
        <input id="np-preco" placeholder="9,90" style="width:80px;border:1px solid var(--border);border-radius:7px;padding:.4rem .6rem;font-size:.82rem;font-family:inherit;outline:none">
      </div>
      <div>
        <label style="font-size:.72rem;font-weight:600;color:var(--muted);display:block;margin-bottom:.2rem">Categoria</label>
        <input id="np-cat" placeholder="Bebidas" list="cats-list" style="width:100px;border:1px solid var(--border);border-radius:7px;padding:.4rem .6rem;font-size:.82rem;font-family:inherit;outline:none">
        <datalist id="cats-list"></datalist>
      </div>
      <button onclick="adicionarProduto()"
              style="background:var(--green);color:#fff;border:none;border-radius:7px;
                     padding:.4rem .8rem;font-size:.82rem;font-weight:700;cursor:pointer;white-space:nowrap">
        + Adicionar
      </button>
    </div>
    <div id="mprod-list" style="max-height:300px;overflow-y:auto;border-top:1px solid var(--border);padding-top:.5rem"></div>
    <p style="font-size:.7rem;color:var(--muted);margin-top:.6rem">
      Os produtos são salvos localmente no PDV e persistem entre reinicializações.
    </p>
  </div>
</div>

<!-- Modal QR WhatsApp -->
<div class="modal-bg" id="modal-wa">
  <div class="modal" style="max-width:380px;text-align:center">
    <div style="display:flex;justify-content:flex-end">
      <button style="background:none;border:none;font-size:1.1rem;cursor:pointer"
              onclick="fecharModal('modal-wa')">✕</button>
    </div>
    <h2 style="font-size:1rem;margin-bottom:.25rem">📱 Status WhatsApp</h2>
    <p style="font-size:.8rem;color:var(--muted);margin-bottom:1rem">
      Modo: <strong>{modo_label}</strong> · <code style="font-size:.75rem">{settings.zapdin_url}</code>
    </p>
    <div id="wa-detail" style="font-size:.85rem"></div>
    <div style="margin-top:1rem;display:flex;gap:.5rem;justify-content:center;flex-wrap:wrap">
      <a href="{settings.zapdin_url}/whatsapp" target="_blank"
         style="background:var(--green);color:#fff;border-radius:8px;padding:.5rem 1rem;
                font-size:.82rem;font-weight:700;text-decoration:none">
        🖥 Abrir painel ZapDin
      </a>
      <button onclick="fecharModal('modal-wa')"
              style="background:transparent;border:1px solid var(--border);border-radius:8px;
                     padding:.5rem 1rem;font-size:.82rem;font-weight:600;cursor:pointer">
        Fechar
      </button>
    </div>
  </div>
</div>

<script>
// ── Dados ────────────────────────────────────────────────────────────────────
const PRODS_INIT = {prods_json};
const CATS_INIT  = {cats_json};
const BASE       = 'http://localhost:{settings.pdv_port}';
const KEY        = '{settings.pdv_api_key}';
const ZAPDIN_URL = '{settings.zapdin_url}';

// Emojis por categoria
const CAT_EMOJI  = {{
  'Bebidas':'🥤','Lanches':'🥪','Snacks':'🍿','Combustível':'⛽',
  'Automotivo':'🔧','Serviços':'✨','Geral':'📦',
}};
function catEmoji(cat){{ return CAT_EMOJI[cat] || '📦'; }}

// ── Estado ───────────────────────────────────────────────────────────────────
let produtos  = PRODS_INIT;
let carrinho  = [];   // {{ id, nome, preco, unidade, quantidade }}
let catAtiva  = '';
let pgtoAtivo = 'PIX';
let _wppNum   = '';

// ── Carrinho ─────────────────────────────────────────────────────────────────
function addProdById(id) {{
  const p = produtos.find(x => x.id === id);
  if (!p) return;
  addProd(p);
}}

function addProd(p) {{
  const existing = carrinho.find(i => i.id === p.id);
  if (existing) {{
    existing.quantidade++;
  }} else {{
    carrinho.push({{ ...p, quantidade: 1 }});
  }}
  renderCarrinho();
  // Pulsa visual
  const card = document.querySelector('[data-id="' + p.id + '"]');
  if (card) {{ card.style.transform='scale(0.96)'; setTimeout(function(){{card.style.transform='';}},100); }}
}}

function changeQty(id, delta) {{
  const item = carrinho.find(i => i.id === id);
  if (!item) return;
  item.quantidade += delta;
  if (item.quantidade <= 0) carrinho = carrinho.filter(i => i.id !== id);
  renderCarrinho();
}}

function limparCarrinho() {{
  carrinho = [];
  renderCarrinho();
}}

function renderCarrinho() {{
  const el  = document.getElementById('cart-items');
  const emp = document.getElementById('cart-empty');
  const cnt = document.getElementById('cart-count');

  if (carrinho.length === 0) {{
    emp.style.display = 'block';
    el.innerHTML      = '';
    el.appendChild(emp);
    document.getElementById('btn-fin').disabled = true;
    cnt.style.display = 'none';
  }} else {{
    emp.style.display = 'none';
    cnt.style.display = '';
    cnt.textContent   = carrinho.reduce((a,i)=>a+i.quantidade,0);
    el.innerHTML = carrinho.map(item => {{
      const sub = (item.preco * item.quantidade).toFixed(2).replace('.',',');
      const pun = item.preco.toFixed(2).replace('.',',');
      return `<div class="cart-item">
        <div>
          <div class="ci-nome">${{item.nome}}</div>
          <div class="ci-sub">R$ ${{pun}} x${{item.quantidade}}</div>
        </div>
        <div class="ci-ctrl">
          <button class="ci-btn del" onclick="changeQty('${{item.id}}',-item.quantidade)">🗑</button>
          <button class="ci-btn" onclick="changeQty('${{item.id}}',-1)">−</button>
          <span class="ci-qty">${{item.quantidade}}</span>
          <button class="ci-btn" onclick="changeQty('${{item.id}}',1)">+</button>
          <span class="ci-val">R$ ${{sub}}</span>
        </div>
      </div>`;
    }}).join('');
    // Re-bind del buttons usando quantidade correta
    document.querySelectorAll('.ci-btn.del').forEach((btn,i) => {{
      btn.onclick = () => changeQty(carrinho[i].id, -carrinho[i].quantidade);
    }});
    document.getElementById('btn-fin').disabled = carrinho.length === 0;
  }}
  atualizarTotais();
}}

function atualizarTotais() {{
  const total = carrinho.reduce((a,i)=>a+(i.preco*i.quantidade),0);
  const itens = carrinho.reduce((a,i)=>a+i.quantidade,0);
  document.getElementById('tot-sub').textContent   = 'R$ '+total.toFixed(2).replace('.',',');
  document.getElementById('tot-total').textContent  = 'R$ '+total.toFixed(2).replace('.',',');
  document.getElementById('tot-itens').textContent  = itens;
}}

// ── Catálogo ─────────────────────────────────────────────────────────────────
function renderCatalogo(lista) {{
  const grid = document.getElementById('prod-grid');
  grid.innerHTML = lista.map(p => {{
    const emoji = catEmoji(p.categoria || 'Geral');
    const preco = parseFloat(p.preco).toFixed(2).replace('.',',');
    const un    = p.unidade && p.unidade !== 'un' ? '/' + p.unidade : '';
    return '<div class="prod-card" data-id="' + p.id + '" data-cat="' + (p.categoria||'') + '" onclick="addProdById(this.dataset.id)">'
      + '<div class="prod-emoji">' + emoji + '</div>'
      + '<div class="prod-nome">' + p.nome + '</div>'
      + '<div class="prod-preco">R$ ' + preco + '<span class="prod-un">' + un + '</span></div>'
      + '</div>';
  }}).join('');
}}

function renderCatTabs(cats) {{
  const tabs = document.getElementById('cat-tabs');
  const existing = tabs.querySelectorAll('[data-cat]:not([data-cat=""])');
  existing.forEach(e=>e.remove());
  cats.forEach(c => {{
    const b = document.createElement('button');
    b.className = 'cat-tab';
    b.dataset.cat = c;
    b.textContent = catEmoji(c) + ' ' + c;
    b.onclick = () => filtrarCat(b, c);
    tabs.appendChild(b);
  }});
}}

function filtrar() {{
  const q = document.getElementById('search').value.toLowerCase();
  document.querySelectorAll('.prod-card').forEach(card => {{
    const nome = card.querySelector('.prod-nome').textContent.toLowerCase();
    const cat  = card.dataset.cat.toLowerCase();
    const matchCat = !catAtiva || card.dataset.cat === catAtiva;
    const matchQ   = !q || nome.includes(q) || cat.includes(q);
    card.classList.toggle('hidden', !(matchCat && matchQ));
  }});
}}

function filtrarCat(btn, cat) {{
  catAtiva = cat;
  document.querySelectorAll('.cat-tab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('search').value = '';
  filtrar();
}}

// ── Pagamento ────────────────────────────────────────────────────────────────
function selPgto(btn) {{
  document.querySelectorAll('.pgto-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  pgtoAtivo = btn.dataset.pgto;
}}

// ── Finalizar venda ──────────────────────────────────────────────────────────
async function finalizarVenda() {{
  const nome  = document.getElementById('cli-nome').value.trim();
  const fone  = document.getElementById('cli-fone').value.trim();
  if (!nome) {{ document.getElementById('cli-nome').focus(); alert('Informe o nome do cliente'); return; }}
  if (!fone || fone.length < 10) {{ document.getElementById('cli-fone').focus(); alert('Informe o telefone com DDD'); return; }}
  if (carrinho.length === 0) {{ alert('Carrinho vazio'); return; }}

  const total = carrinho.reduce((a,i)=>a+(i.preco*i.quantidade),0);
  const btn   = document.getElementById('btn-fin');
  btn.disabled = true;
  btn.innerHTML = '<div class="spin"></div> Enviando…';

  const body = {{
    phone: fone,
    numero_venda: String(Date.now()).slice(-6),
    nome_cliente: nome,
    valor_total: total.toFixed(2).replace('.',','),
    forma_pagamento: pgtoAtivo,
    data: new Date().toLocaleDateString('pt-BR'),
    itens: carrinho.map(i => ({{
      descricao: i.nome,
      quantidade: i.quantidade,
      valor_unitario: i.preco.toFixed(2).replace('.',','),
    }})),
  }};

  try {{
    const r = await fetch(BASE + '/erp/venda', {{
      method: 'POST',
      headers: {{ 'Content-Type':'application/json', 'X-PDV-Key':KEY }},
      body: JSON.stringify(body),
    }});
    const d = await r.json();

    if (r.ok) {{
      _wppNum = fone;
      // Monta recibo
      const linhas = carrinho.map(i => {{
        const val = (i.preco*i.quantidade).toFixed(2).replace('.',',');
        return `  ${{i.nome.padEnd(22).slice(0,22)}} x${{i.quantidade}}  R$ ${{val}}`;
      }}).join('\n');
      document.getElementById('m-recibo').textContent =
        `Cliente: ${{nome}}\nTelefone: ${{fone}}\nPagamento: ${{pgtoAtivo}}\n` +
        `─────────────────────────────\n${{linhas}}\n─────────────────────────────\n` +
        `TOTAL: R$ ${{total.toFixed(2).replace('.',',')}}\n\n` +
        `Status: ${{d.via === 'zapdin_app' ? '✅ Fila ZapDin App' : '✅ Enviado'}}`;
      document.getElementById('m-sub').textContent =
        d.via === 'zapdin_app'
          ? 'Mensagem enfileirada no ZapDin App — será enviada assim que o WhatsApp estiver conectado.'
          : 'Mensagem enviada com sucesso!';
      document.getElementById('modal-ok').classList.add('open');
    }} else {{
      document.getElementById('m-err-detail').textContent =
        JSON.stringify(d, null, 2);
      document.getElementById('modal-err').classList.add('open');
    }}
  }} catch(e) {{
    document.getElementById('m-err-detail').textContent = 'Erro de conexão: ' + e.message;
    document.getElementById('modal-err').classList.add('open');
  }} finally {{
    btn.disabled = false;
    btn.innerHTML = '💚 FINALIZAR VENDA';
  }}
}}

function novaVenda() {{
  fecharModal('modal-ok');
  limparCarrinho();
  document.getElementById('cli-nome').value = '';
  document.getElementById('cli-fone').value = '';
}}

function fecharModal(id) {{
  document.getElementById(id).classList.remove('open');
}}

function abrirWppDireto() {{
  const num = _wppNum.replace(/\D/g,'');
  const full = num.startsWith('55') ? num : '55' + num;
  window.open(`https://wa.me/${{full}}`, '_blank');
}}

// ── WhatsApp status ───────────────────────────────────────────────────────────
async function checarWA() {{
  const badge = document.getElementById('wa-badge');
  try {{
    const r = await fetch(BASE + '/status', {{headers:{{'X-PDV-Key':KEY}}}});
    if (!r.ok) throw new Error('offline');
    const d = await r.json();

    if (d.zapdin_app?.conectado !== undefined) {{
      // Modo app: verifica sessão no ZapDin App
      try {{
        const r2 = await fetch(ZAPDIN_URL + '/api/stats/queue', {{
          headers: {{'X-Token':'{settings.zapdin_erp_token}'}}
        }});
        if (r2.ok) {{
          const d2 = await r2.json();
          const conn = d2.sessoes_conectadas || 0;
          if (conn > 0) {{
            badge.className = 'connected';
            badge.textContent = '✅ WA ' + d2.sessoes[0]?.phone?.slice(-4).padStart(d2.sessoes[0]?.phone?.length,'*') || 'Conectado';
          }} else {{
            badge.className = 'disconnected';
            badge.textContent = '❌ WA Desconectado';
          }}
        }} else {{
          badge.className = 'disconnected';
          badge.textContent = '❌ WA Offline';
        }}
      }} catch {{ badge.className='disconnected'; badge.textContent='❌ WA Offline'; }}
    }}
  }} catch {{
    badge.className = 'disconnected';
    badge.textContent = '⚠️ PDV offline';
  }}
}}

async function abrirWA() {{
  const r = await fetch(BASE + '/status', {{headers:{{'X-PDV-Key':KEY}}}}).catch(()=>null);
  const d = r?.ok ? await r.json() : {{}};
  const det = document.getElementById('wa-detail');

  if (d.zapdin_app?.conectado) {{
    det.innerHTML = '<p style="color:var(--ok);font-weight:700;margin-bottom:.5rem">✅ ZapDin App acessível</p>';
  }} else {{
    det.innerHTML = '<p style="color:var(--red);font-weight:700;margin-bottom:.5rem">❌ ZapDin App inacessível — verifique se está rodando na porta 4000</p>';
  }}
  document.getElementById('modal-wa').classList.add('open');
}}

// ── Gerenciar produtos ────────────────────────────────────────────────────────
function abrirGerenciarProdutos() {{
  renderMprodList();
  // Preenche datalist de categorias
  const dl = document.getElementById('cats-list');
  dl.innerHTML = CATS_INIT.map(c=>`<option value="${{c}}">`).join('');
  document.getElementById('modal-prod').classList.add('open');
}}

function renderMprodList() {{
  const el = document.getElementById('mprod-list');
  el.innerHTML = produtos.map(p =>
    `<div class="mprod-item">
      <span class="mprod-nome">${{catEmoji(p.categoria)}} ${{p.nome}}</span>
      <span class="mprod-cat">${{p.categoria||''}}</span>
      <span class="mprod-preco">R$ ${{parseFloat(p.preco).toFixed(2).replace('.',',')}}</span>
      <button class="mprod-del" onclick="deletarProduto('${{p.id}}')" title="Remover">✕</button>
    </div>`
  ).join('');
}}

async function adicionarProduto() {{
  const nome  = document.getElementById('np-nome').value.trim();
  const preco = parseFloat(document.getElementById('np-preco').value.replace(',','.'));
  const cat   = document.getElementById('np-cat').value.trim() || 'Geral';
  if (!nome || isNaN(preco) || preco <= 0) {{ alert('Preencha nome e preço válido'); return; }}

  const r = await fetch(BASE + '/pdv/produtos', {{
    method:'POST',
    headers:{{'Content-Type':'application/json','X-PDV-Key':KEY}},
    body: JSON.stringify({{nome, preco, categoria:cat, unidade:'un'}})
  }});
  if (r.ok) {{
    const novo = await r.json();
    produtos.push(novo);
    renderCatalogo(produtos);
    renderMprodList();
    document.getElementById('np-nome').value  = '';
    document.getElementById('np-preco').value = '';
    document.getElementById('np-cat').value   = '';
  }}
}}

async function deletarProduto(id) {{
  if (!confirm('Remover este produto?')) return;
  const r = await fetch(BASE + '/pdv/produtos/' + id, {{
    method:'DELETE', headers:{{'X-PDV-Key':KEY}}
  }});
  if (r.ok) {{
    produtos = produtos.filter(p => p.id !== id);
    renderCatalogo(produtos);
    renderMprodList();
  }}
}}

// ── Init ─────────────────────────────────────────────────────────────────────
renderCatalogo(produtos);
renderCatTabs(CATS_INIT);
renderCarrinho();
checarWA();
setInterval(checarWA, 30000);   // atualiza status WA a cada 30s
</script>
</body>
</html>"""


@app.get("/testes", response_class=HTMLResponse)
async def painel_testes():
    """Painel de testes avançado (APIs, fila, templates)."""
    modo = settings.modo_envio
    destino = settings.zapdin_url if modo == "app" else settings.evolution_url
    token_ok = bool(settings.zapdin_erp_token) if modo == "app" else True
    token_badge = (
        '<span class="badge-ok">✅ Token configurado</span>'
        if token_ok else
        '<span class="badge-err">⚠️ ZAPDIN_ERP_TOKEN não configurado no .env</span>'
    )
    modo_label = (
        f'<span class="badge-ok">📡 Modo: ZapDin App</span>'
        if modo == "app" else
        f'<span class="badge-warn">🔌 Modo: Evolution Local</span>'
    )

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>ZapDin PDV — Painel de Testes</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    :root{{
      --green:#3d7f1f;--green-l:#7cdc44;--bg:#f4f6f9;
      --surface:#fff;--border:#e4e6ea;--text:#1a1d23;--muted:#6b7280;
      --red:#dc2626;--yellow:#d97706;--ok:#15803d;
    }}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
         background:var(--bg);color:var(--text);min-height:100vh}}

    /* Header */
    .header{{background:var(--green);color:#fff;padding:.9rem 1.5rem;
             display:flex;align-items:center;justify-content:space-between;
             box-shadow:0 2px 8px rgba(0,0,0,.15)}}
    .header-left{{display:flex;align-items:center;gap:.75rem}}
    .header h1{{font-size:1.1rem;font-weight:800}}
    .header .sub{{font-size:.78rem;opacity:.85;margin-top:.1rem}}
    .badge-ok{{background:#dcfce7;color:#15803d;padding:.2rem .65rem;
               border-radius:12px;font-size:.75rem;font-weight:700}}
    .badge-err{{background:#fee2e2;color:#991b1b;padding:.2rem .65rem;
                border-radius:12px;font-size:.75rem;font-weight:700}}
    .badge-warn{{background:#fef9c3;color:#854d0e;padding:.2rem .65rem;
                 border-radius:12px;font-size:.75rem;font-weight:700}}
    .header-badges{{display:flex;flex-direction:column;align-items:flex-end;gap:.3rem}}

    /* Layout */
    .layout{{display:flex;height:calc(100vh - 56px)}}
    .sidebar{{width:200px;background:var(--surface);border-right:1px solid var(--border);
              padding:1rem .75rem;display:flex;flex-direction:column;gap:.25rem;
              flex-shrink:0}}
    .sidebar .nav-btn{{width:100%;text-align:left;background:none;border:none;
                        padding:.6rem .85rem;border-radius:8px;font-size:.875rem;
                        cursor:pointer;color:var(--text);display:flex;align-items:center;gap:.5rem}}
    .sidebar .nav-btn:hover{{background:#f0f7eb}}
    .sidebar .nav-btn.active{{background:#e8f5e9;color:var(--green);font-weight:700}}
    .sidebar .nav-sep{{font-size:.68rem;font-weight:700;color:var(--muted);
                        text-transform:uppercase;letter-spacing:.07em;
                        padding:.75rem .85rem .2rem}}
    .main{{flex:1;overflow-y:auto;padding:1.5rem}}

    /* Cards */
    .card{{background:var(--surface);border-radius:12px;border:1px solid var(--border);
           padding:1.5rem;margin-bottom:1rem;box-shadow:0 1px 4px rgba(0,0,0,.06)}}
    .card h2{{font-size:.95rem;font-weight:700;margin-bottom:1rem;
              display:flex;align-items:center;gap:.5rem}}

    /* Forms */
    .form-grid{{display:grid;grid-template-columns:1fr 1fr;gap:.75rem}}
    .form-grid.single{{grid-template-columns:1fr}}
    .form-grid.triple{{grid-template-columns:1fr 1fr 1fr}}
    .field{{display:flex;flex-direction:column;gap:.3rem}}
    .field.full{{grid-column:1/-1}}
    label{{font-size:.78rem;font-weight:600;color:var(--muted)}}
    input,textarea,select{{border:1px solid var(--border);border-radius:8px;
                            padding:.5rem .75rem;font-size:.875rem;font-family:inherit;
                            outline:none;width:100%;background:#fff;color:var(--text)}}
    input:focus,textarea:focus,select:focus{{border-color:var(--green);
                                              box-shadow:0 0 0 3px rgba(61,127,31,.12)}}
    textarea{{resize:vertical;min-height:80px}}

    /* Buttons */
    .btn{{border:none;border-radius:8px;padding:.6rem 1.25rem;font-size:.875rem;
          font-weight:700;cursor:pointer;display:inline-flex;align-items:center;
          gap:.4rem;transition:filter .15s}}
    .btn:hover:not(:disabled){{filter:brightness(.92)}}
    .btn:disabled{{opacity:.5;cursor:not-allowed}}
    .btn-primary{{background:var(--green);color:#fff}}
    .btn-ghost{{background:transparent;border:1px solid var(--border);color:var(--text)}}
    .btn-danger{{background:#fee2e2;color:var(--red)}}

    /* Response box */
    .resp-box{{position:sticky;bottom:0;background:var(--surface);
               border-top:1px solid var(--border);padding:1rem 1.5rem}}
    .resp-box .resp-header{{display:flex;align-items:center;justify-content:space-between;
                             margin-bottom:.5rem}}
    .resp-box .resp-title{{font-size:.78rem;font-weight:700;color:var(--muted);
                            text-transform:uppercase;letter-spacing:.06em}}
    .resp-pre{{background:#1e2433;color:#a8ff78;border-radius:8px;padding:.9rem 1rem;
               font-size:.78rem;font-family:'SFMono-Regular',Consolas,monospace;
               max-height:160px;overflow-y:auto;white-space:pre-wrap;word-break:break-all}}
    .resp-ok{{color:#4ade80}}
    .resp-err{{color:#f87171}}

    /* Status grid */
    .stat-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:1rem}}
    .stat-card{{background:var(--surface);border-radius:10px;border:1px solid var(--border);
                padding:1rem;text-align:center}}
    .stat-num{{font-size:2rem;font-weight:800;color:var(--green)}}
    .stat-lbl{{font-size:.78rem;color:var(--muted);margin-top:.2rem}}
    .sessao-row{{display:flex;align-items:center;gap:.6rem;padding:.5rem 0;
                 border-bottom:1px solid var(--border);font-size:.85rem}}
    .sessao-row:last-child{{border-bottom:none}}
    .dot{{width:9px;height:9px;border-radius:50%;flex-shrink:0}}
    .dot-ok{{background:#22c55e}}.dot-disc{{background:#ef4444}}.dot-conn{{background:#f59e0b}}

    /* Item list (itens de venda) */
    .item-row{{display:grid;grid-template-columns:1fr auto auto auto;
               gap:.5rem;align-items:center;margin-bottom:.4rem}}
    .item-row input{{margin:0}}
    .page{{display:none}}.page.active{{display:block}}
  </style>
</head>
<body>

<div class="header">
  <div class="header-left">
    <div>
      <h1>📱 ZapDin PDV — Painel de Testes</h1>
      <div class="sub">Simule chamadas ERP e veja o envio em tempo real</div>
    </div>
  </div>
  <div class="header-badges">
    {modo_label}
    <span style="font-size:.72rem;color:rgba(255,255,255,.8)">{destino}</span>
    {token_badge}
  </div>
</div>

<div class="layout">
  <!-- Sidebar -->
  <nav class="sidebar">
    <div class="nav-sep">Enviar</div>
    <button class="nav-btn active" onclick="showPage('texto',this)">💬 Texto livre</button>
    <button class="nav-btn" onclick="showPage('venda',this)">🧾 Simular Venda</button>
    <button class="nav-btn" onclick="showPage('nfe',this)">📄 Nota Fiscal</button>
    <button class="nav-btn" onclick="showPage('arquivo',this)">📎 Arquivo</button>
    <div class="nav-sep">Sistema</div>
    <button class="nav-btn" onclick="showPage('status',this)">📊 Status</button>
    <button class="nav-btn" onclick="showPage('fila',this)">🗂 Fila</button>
    <button class="nav-btn" onclick="showPage('templates',this)">📝 Templates</button>
    <div style="flex:1"></div>
    <a href="/docs" target="_blank"
       style="font-size:.75rem;color:var(--muted);text-decoration:none;
              padding:.4rem .85rem;display:block">📖 Swagger /docs</a>
  </nav>

  <!-- Main area -->
  <div class="main" id="mainArea">

    <!-- ── Página: Texto livre ── -->
    <div class="page active" id="page-texto">
      <div class="card">
        <h2>💬 Enviar Mensagem de Texto</h2>
        <div class="form-grid single">
          <div class="field">
            <label>Telefone (com DDD, sem +55)</label>
            <input id="t-phone" placeholder="44999990000" value="">
          </div>
          <div class="field">
            <label>Mensagem</label>
            <textarea id="t-msg" rows="4" placeholder="Digite a mensagem que será enviada via WhatsApp..."></textarea>
          </div>
        </div>
        <div style="display:flex;gap:.5rem;margin-top:1rem">
          <button class="btn btn-primary" onclick="enviarTexto()">📤 Enviar</button>
          <button class="btn btn-ghost" onclick="limpar('t-phone','t-msg')">🗑 Limpar</button>
        </div>
      </div>
    </div>

    <!-- ── Página: Simular Venda ── -->
    <div class="page" id="page-venda">
      <div class="card">
        <h2>🧾 Simular Comprovante de Venda</h2>
        <div class="form-grid">
          <div class="field">
            <label>Telefone (com DDD)</label>
            <input id="v-phone" placeholder="44999990000">
          </div>
          <div class="field">
            <label>Nome do cliente</label>
            <input id="v-nome" placeholder="João Silva">
          </div>
          <div class="field">
            <label>Número da venda</label>
            <input id="v-numero" placeholder="00123" value="00001">
          </div>
          <div class="field">
            <label>Valor total (R$)</label>
            <input id="v-valor" placeholder="150,00" value="100,00">
          </div>
          <div class="field">
            <label>Forma de pagamento</label>
            <select id="v-forma">
              <option>Cartão de débito</option>
              <option>Cartão de crédito</option>
              <option>PIX</option>
              <option>Dinheiro</option>
              <option>Boleto</option>
            </select>
          </div>
          <div class="field">
            <label>Data</label>
            <input id="v-data" type="date">
          </div>
          <div class="field full">
            <label>Observação (opcional)</label>
            <input id="v-obs" placeholder="Entrega prevista para amanhã">
          </div>
        </div>

        <div style="margin-top:1rem">
          <label style="font-size:.78rem;font-weight:600;color:var(--muted);display:flex;
                         align-items:center;gap:.5rem;margin-bottom:.5rem">
            📦 Itens (opcional)
            <button class="btn btn-ghost" style="padding:.2rem .6rem;font-size:.75rem"
                    onclick="addItem()">+ Item</button>
          </label>
          <div id="itens-list"></div>
        </div>

        <div style="display:flex;gap:.5rem;margin-top:1rem">
          <button class="btn btn-primary" onclick="enviarVenda()">📤 Enviar Venda</button>
          <button class="btn btn-ghost" onclick="previewVenda()">👁 Preview JSON</button>
        </div>
      </div>
    </div>

    <!-- ── Página: NF-e ── -->
    <div class="page" id="page-nfe">
      <div class="card">
        <h2>📄 Simular Envio de Nota Fiscal</h2>
        <div class="form-grid">
          <div class="field">
            <label>Telefone (com DDD)</label>
            <input id="n-phone" placeholder="44999990000">
          </div>
          <div class="field">
            <label>Nome do cliente</label>
            <input id="n-nome" placeholder="João Silva">
          </div>
          <div class="field">
            <label>Número da NF-e</label>
            <input id="n-numero" placeholder="000001" value="000001">
          </div>
          <div class="field">
            <label>Valor total (R$)</label>
            <input id="n-valor" placeholder="250,00">
          </div>
          <div class="field">
            <label>Data</label>
            <input id="n-data" type="date">
          </div>
          <div class="field">
            <label>Chave de acesso (opcional)</label>
            <input id="n-chave" placeholder="35240312345678000195550010000012341000012348">
          </div>
          <div class="field full">
            <label>Link DANFE (opcional)</label>
            <input id="n-link" placeholder="https://www.nfe.fazenda.gov.br/...">
          </div>
        </div>
        <div style="display:flex;gap:.5rem;margin-top:1rem">
          <button class="btn btn-primary" onclick="enviarNFe()">📤 Enviar NF-e</button>
        </div>
      </div>
    </div>

    <!-- ── Página: Arquivo ── -->
    <div class="page" id="page-arquivo">
      <div class="card">
        <h2>📎 Enviar Arquivo</h2>
        <div class="form-grid">
          <div class="field">
            <label>Telefone (com DDD)</label>
            <input id="a-phone" placeholder="44999990000">
          </div>
          <div class="field">
            <label>Legenda (opcional)</label>
            <input id="a-caption" placeholder="Segue seu boleto em anexo">
          </div>
          <div class="field full">
            <label>Arquivo (PDF, imagem, etc.)</label>
            <input type="file" id="a-file" accept="*/*"
                   style="padding:.4rem;cursor:pointer">
          </div>
        </div>
        <div style="display:flex;gap:.5rem;margin-top:1rem">
          <button class="btn btn-primary" onclick="enviarArquivo()">📤 Enviar Arquivo</button>
        </div>
      </div>
    </div>

    <!-- ── Página: Status ── -->
    <div class="page" id="page-status">
      <div class="stat-grid" id="stat-grid">
        <div class="stat-card"><div class="stat-num" id="st-total">–</div><div class="stat-lbl">Sessões cadastradas</div></div>
        <div class="stat-card"><div class="stat-num" id="st-conn">–</div><div class="stat-lbl">Conectadas</div></div>
        <div class="stat-card"><div class="stat-num" id="st-modo">{'App' if modo == 'app' else 'Local'}</div><div class="stat-lbl">Modo de envio</div></div>
      </div>
      <div class="card" style="margin-top:1rem">
        <h2>📱 Sessões WhatsApp</h2>
        <div id="sessoes-list"><em style="color:var(--muted);font-size:.85rem">Carregando…</em></div>
      </div>
      <div class="card">
        <h2>⚙️ Configuração Atual</h2>
        <table style="width:100%;font-size:.83rem;border-collapse:collapse">
          <tr><td style="padding:.4rem 0;color:var(--muted);width:160px">Modo</td>
              <td><strong>{settings.modo_envio}</strong></td></tr>
          <tr><td style="padding:.4rem 0;color:var(--muted)">ZapDin App URL</td>
              <td><code style="font-size:.78rem">{settings.zapdin_url}</code></td></tr>
          <tr><td style="padding:.4rem 0;color:var(--muted)">ERP Token</td>
              <td>{'<span style="color:var(--ok)">✅ Configurado</span>' if settings.zapdin_erp_token else '<span style="color:var(--red)">❌ Não configurado (ZAPDIN_ERP_TOKEN no .env)</span>'}</td></tr>
          <tr><td style="padding:.4rem 0;color:var(--muted)">Porta PDV</td>
              <td><code style="font-size:.78rem">{settings.pdv_port}</code></td></tr>
        </table>
      </div>
      <div style="text-align:center;margin-top:.5rem">
        <button class="btn btn-ghost" onclick="carregarStatus()">🔄 Atualizar</button>
      </div>
    </div>

    <!-- ── Página: Fila ── -->
    <div class="page" id="page-fila">
      <div class="card">
        <h2>🗂 Status da Fila de Envio</h2>
        <p style="font-size:.83rem;color:var(--muted);margin-bottom:1rem">
          Mostra mensagens e arquivos pendentes na fila do ZapDin App.
        </p>
        <div id="fila-content"><em style="color:var(--muted);font-size:.85rem">Carregando…</em></div>
        <div style="margin-top:1rem">
          <button class="btn btn-ghost" onclick="carregarFila()">🔄 Atualizar</button>
        </div>
      </div>
    </div>

    <!-- ── Página: Templates ── -->
    <div class="page" id="page-templates">
      <div class="card">
        <h2>📝 Templates de Mensagem (PDV Local)</h2>
        <p style="font-size:.83rem;color:var(--muted);margin-bottom:1rem">
          Quando modo=local, estes templates são usados para formatar mensagens de venda/nf-e.<br>
          No modo app, o template configurado no ZapDin App é usado.
        </p>
        <div id="templates-content"><em style="color:var(--muted)">Carregando…</em></div>
      </div>
    </div>

  </div><!-- /main -->
</div><!-- /layout -->

<!-- Response box fixo -->
<div class="resp-box">
  <div class="resp-header">
    <span class="resp-title" id="resp-title">Aguardando envio…</span>
    <button class="btn btn-ghost" style="padding:.2rem .6rem;font-size:.75rem"
            onclick="document.getElementById('resp-pre').textContent=''">Limpar</button>
  </div>
  <pre class="resp-pre" id="resp-pre">Faça um envio acima para ver o resultado aqui.</pre>
</div>

<script>
const BASE = 'http://localhost:{settings.pdv_port}';
const KEY  = '{settings.pdv_api_key}';

// ── Navegação ─────────────────────────────────────────────────────────────────
function showPage(id, btn) {{
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('page-' + id).classList.add('active');
  btn.classList.add('active');
  if (id === 'status')    carregarStatus();
  if (id === 'fila')      carregarFila();
  if (id === 'templates') carregarTemplates();
}}

function limpar(...ids) {{ ids.forEach(id => {{ const el = document.getElementById(id); if(el) el.value = ''; }}); }}

// ── Response helper ───────────────────────────────────────────────────────────
function showResp(titulo, ok, data) {{
  document.getElementById('resp-title').textContent = titulo;
  const pre = document.getElementById('resp-pre');
  pre.textContent = JSON.stringify(data, null, 2);
  pre.className = 'resp-pre ' + (ok ? 'resp-ok' : 'resp-err');
}}

// ── Chamada API helper ────────────────────────────────────────────────────────
async function apiCall(method, path, body) {{
  try {{
    const r = await fetch(BASE + path, {{
      method,
      headers: {{'Content-Type':'application/json','X-PDV-Key':KEY}},
      body: body ? JSON.stringify(body) : undefined,
    }});
    const data = await r.json().catch(() => ({{error: 'Resposta não-JSON'}}));
    return {{ ok: r.ok, status: r.status, data }};
  }} catch(e) {{
    return {{ ok: false, status: 0, data: {{error: e.message}} }};
  }}
}}

// ── Enviar texto ──────────────────────────────────────────────────────────────
async function enviarTexto() {{
  const phone = document.getElementById('t-phone').value.trim();
  const msg   = document.getElementById('t-msg').value.trim();
  if (!phone || !msg) {{ alert('Preencha telefone e mensagem'); return; }}
  showResp('Enviando…', true, {{aguarde:'...'}} );
  const r = await apiCall('POST', '/erp/notificar', {{
    phone, evento: 'custom', vars: {{ mensagem: msg }}
  }});
  showResp(r.ok ? '✅ Mensagem enviada!' : '❌ Erro no envio', r.ok, r.data);
}}

// ── Itens de venda ────────────────────────────────────────────────────────────
let _itemCnt = 0;
function addItem() {{
  _itemCnt++;
  const row = document.createElement('div');
  row.className = 'item-row';
  row.id = 'item-' + _itemCnt;
  row.innerHTML = `
    <input placeholder="Descrição do produto" data-field="descricao">
    <input placeholder="Qtd" data-field="quantidade" style="width:70px">
    <input placeholder="R$ valor" data-field="valor_unitario" style="width:100px">
    <button class="btn btn-danger" style="padding:.3rem .55rem;font-size:.75rem"
            onclick="document.getElementById('item-{{}}_itemCnt').remove()">✕</button>
  `;
  row.querySelector('button').onclick = () => row.remove();
  document.getElementById('itens-list').appendChild(row);
}}

function coletarItens() {{
  const rows = document.querySelectorAll('#itens-list .item-row');
  return Array.from(rows).map(r => ({{
    descricao: r.querySelector('[data-field=descricao]').value,
    quantidade: parseFloat(r.querySelector('[data-field=quantidade]').value) || 1,
    valor_unitario: r.querySelector('[data-field=valor_unitario]').value,
  }}));
}}

function _buildVendaBody() {{
  return {{
    phone: document.getElementById('v-phone').value.trim(),
    numero_venda: document.getElementById('v-numero').value.trim(),
    nome_cliente: document.getElementById('v-nome').value.trim(),
    valor_total: document.getElementById('v-valor').value.trim(),
    forma_pagamento: document.getElementById('v-forma').value,
    data: document.getElementById('v-data').value,
    observacao: document.getElementById('v-obs').value.trim(),
    itens: coletarItens().filter(i => i.descricao),
  }};
}}

async function enviarVenda() {{
  const body = _buildVendaBody();
  if (!body.phone) {{ alert('Preencha o telefone'); return; }}
  showResp('Enviando venda…', true, {{aguarde:'...'}} );
  const r = await apiCall('POST', '/erp/venda', body);
  showResp(r.ok ? '✅ Venda enviada!' : '❌ Erro', r.ok, r.data);
}}

function previewVenda() {{
  showResp('📋 Preview do payload de venda', true, _buildVendaBody());
}}

// ── Enviar NF-e ───────────────────────────────────────────────────────────────
async function enviarNFe() {{
  const body = {{
    phone: document.getElementById('n-phone').value.trim(),
    numero_nf: document.getElementById('n-numero').value.trim(),
    nome_cliente: document.getElementById('n-nome').value.trim(),
    valor_total: document.getElementById('n-valor').value.trim(),
    data: document.getElementById('n-data').value,
    chave_acesso: document.getElementById('n-chave').value.trim(),
    link_danfe: document.getElementById('n-link').value.trim(),
  }};
  if (!body.phone) {{ alert('Preencha o telefone'); return; }}
  showResp('Enviando NF-e…', true, {{aguarde:'...'}} );
  const r = await apiCall('POST', '/erp/nota-fiscal', body);
  showResp(r.ok ? '✅ NF-e enviada!' : '❌ Erro', r.ok, r.data);
}}

// ── Enviar arquivo ────────────────────────────────────────────────────────────
async function enviarArquivo() {{
  const phone   = document.getElementById('a-phone').value.trim();
  const caption = document.getElementById('a-caption').value.trim();
  const fileEl  = document.getElementById('a-file');
  if (!phone) {{ alert('Preencha o telefone'); return; }}
  if (!fileEl.files[0]) {{ alert('Selecione um arquivo'); return; }}

  const file = fileEl.files[0];
  const reader = new FileReader();
  reader.onload = async (e) => {{
    const b64 = e.target.result.split(',')[1];   // remove prefixo data:...
    showResp('Enviando arquivo…', true, {{aguarde:'...'}} );
    const r = await apiCall('POST', '/erp/notificar', {{
      phone,
      evento: 'custom',
      vars: {{ mensagem: caption || file.name }},
      arquivo_base64: b64,
      arquivo_nome: file.name,
      arquivo_caption: caption,
      apenas_arquivo: !caption,
    }});
    showResp(r.ok ? '✅ Arquivo enviado!' : '❌ Erro', r.ok, r.data);
  }};
  reader.readAsDataURL(file);
}}

// ── Status ────────────────────────────────────────────────────────────────────
async function carregarStatus() {{
  try {{
    const r = await fetch(BASE + '/status', {{headers:{{'X-PDV-Key':KEY}}}});
    const d = await r.json();
    document.getElementById('st-total').textContent = d.sessoes_total ?? '–';
    document.getElementById('st-conn').textContent  = d.sessoes_conectadas ?? '–';

    const list = document.getElementById('sessoes-list');
    if (!d.sessoes?.length) {{
      list.innerHTML = '<em style="color:var(--muted);font-size:.85rem">Nenhuma sessão cadastrada.</em>';
      return;
    }}
    list.innerHTML = d.sessoes.map(s => {{
      const dotClass = s.status === 'connected' ? 'dot-ok' : s.status === 'connecting' ? 'dot-conn' : 'dot-disc';
      const phone = s.phone ? ` · <code style="font-size:.75rem">${{s.phone}}</code>` : '';
      return `<div class="sessao-row">
        <span class="dot ${{dotClass}}"></span>
        <strong>${{s.nome}}</strong>
        <span style="color:var(--muted);font-size:.8rem">${{s.status}}</span>
        ${{phone}}
      </div>`;
    }}).join('');
  }} catch(e) {{
    document.getElementById('sessoes-list').innerHTML =
      `<em style="color:var(--red)">Erro ao conectar no PDV: ${{e.message}}</em>`;
  }}
}}

// ── Fila ──────────────────────────────────────────────────────────────────────
async function carregarFila() {{
  const el = document.getElementById('fila-content');
  try {{
    // O PDV consulta o ZapDin App para ver a fila
    const base = '{settings.zapdin_url}';
    const token = '{settings.zapdin_erp_token}';
    if (!token) {{
      el.innerHTML = '<em style="color:var(--red)">Token ERP não configurado — não é possível consultar a fila do App.</em>';
      return;
    }}
    const r = await fetch(base + '/api/stats/queue', {{headers:{{'X-Token':token}}}});
    if (!r.ok) {{ throw new Error('HTTP ' + r.status); }}
    const d = await r.json();
    el.innerHTML = `
      <div class="stat-grid">
        <div class="stat-card"><div class="stat-num">${{d.mensagens_queued ?? 0}}</div><div class="stat-lbl">Mensagens pendentes</div></div>
        <div class="stat-card"><div class="stat-num">${{d.arquivos_queued ?? 0}}</div><div class="stat-lbl">Arquivos pendentes</div></div>
        <div class="stat-card"><div class="stat-num">${{d.mensagens_sent ?? 0}}</div><div class="stat-lbl">Enviadas hoje</div></div>
      </div>`;
  }} catch(e) {{
    el.innerHTML = `<em style="color:var(--muted);font-size:.85rem">Não foi possível carregar a fila do ZapDin App: ${{e.message}}</em>`;
  }}
}}

// ── Templates ─────────────────────────────────────────────────────────────────
async function carregarTemplates() {{
  const el = document.getElementById('templates-content');
  try {{
    const r = await fetch(BASE + '/erp/templates', {{headers:{{'X-PDV-Key':KEY}}}});
    const d = await r.json();
    const entries = Object.entries(d);
    if (!entries.length) {{
      el.innerHTML = '<em style="color:var(--muted)">Nenhum template configurado.</em>';
      return;
    }}
    el.innerHTML = '<table style="width:100%;border-collapse:collapse;font-size:.83rem">' +
      '<tr><th style="text-align:left;padding:.4rem;color:var(--muted);font-weight:700">Evento</th>' +
      '<th style="text-align:left;padding:.4rem;color:var(--muted);font-weight:700">Mensagem</th></tr>' +
      entries.map(([ev, t]) => `
        <tr style="border-top:1px solid var(--border)">
          <td style="padding:.5rem .4rem"><code>${{ev}}</code></td>
          <td style="padding:.5rem .4rem;color:var(--muted)">
            ${{(t.mensagem||'').slice(0,80)}}${{(t.mensagem||'').length>80?'…':''}}
          </td>
        </tr>`).join('') + '</table>';
  }} catch(e) {{
    el.innerHTML = `<em style="color:var(--muted)">Erro: ${{e.message}}</em>`;
  }}
}}

// ── Init ──────────────────────────────────────────────────────────────────────
// Preenche data de hoje nos campos de data
document.querySelectorAll('input[type=date]').forEach(el => {{
  el.value = new Date().toISOString().slice(0,10);
}});
</script>
</body>
</html>"""


# ── CRUD Produtos ─────────────────────────────────────────────────────────────

@app.get("/pdv/produtos")
async def listar_produtos(x_pdv_key: Optional[str] = Header(default=None)):
    _check_key(x_pdv_key)
    from . import produtos as cat
    return cat.listar()


@app.post("/pdv/produtos")
async def criar_produto(body: dict, x_pdv_key: Optional[str] = Header(default=None)):
    _check_key(x_pdv_key)
    from . import produtos as cat
    return cat.salvar(body)


@app.put("/pdv/produtos/{produto_id}")
async def atualizar_produto(
    produto_id: str, body: dict,
    x_pdv_key: Optional[str] = Header(default=None)
):
    _check_key(x_pdv_key)
    from . import produtos as cat
    body["id"] = produto_id
    return cat.salvar(body)


@app.delete("/pdv/produtos/{produto_id}")
async def deletar_produto(
    produto_id: str,
    x_pdv_key: Optional[str] = Header(default=None)
):
    _check_key(x_pdv_key)
    from . import produtos as cat
    ok = cat.deletar(produto_id)
    if not ok:
        raise HTTPException(404, "Produto não encontrado")
    return {"ok": True}


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


@app.get("/pdv/wa-status")
async def wa_status_proxy(x_pdv_key: Optional[str] = Header(default=None)):
    """
    Proxy server-side para checar WA sem problema de CORS no browser.
    - modo_envio=app  → consulta /api/stats/queue no ZapDin App
    - modo_envio=local → consulta sessões locais Evolution API
    """
    _check_key(x_pdv_key)
    if settings.modo_envio == "app":
        import httpx as _httpx
        try:
            async with _httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(
                    f"{settings.zapdin_url.rstrip('/')}/api/stats/queue",
                    headers={"X-Token": settings.zapdin_erp_token or ""},
                )
            if r.status_code == 200:
                d = r.json()
                return {
                    "sessoes_conectadas": d.get("sessoes_conectadas", 0),
                    "sessoes": d.get("sessoes", []),
                    "modo": "app",
                    "app_url": settings.zapdin_url,
                }
        except Exception as exc:
            return {"sessoes_conectadas": 0, "modo": "app", "erro": str(exc)}
        return {"sessoes_conectadas": 0, "modo": "app"}
    # Modo local
    sessoes = local_evo.get_status()
    conectadas = [s for s in sessoes if s["status"] == "connected"]
    return {
        "sessoes_conectadas": len(conectadas),
        "sessoes": sessoes,
        "modo": "local",
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
