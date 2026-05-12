"""
docs_router.py — Documentação HTML da API do ZapDin PDV para o ERP.

Acessível em: http://localhost:4600/erp/docs
Não requer autenticação — é uma página local de referência.
"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from .config import settings

router = APIRouter(tags=["Documentação"])


@router.get("/erp/docs", response_class=HTMLResponse, include_in_schema=False)
async def docs_erp():
    port    = settings.pdv_port
    api_key = settings.pdv_api_key or "SUA_CHAVE_AQUI"

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ZapDin PDV — Documentação ERP</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  :root{{
    --green:#3d7f1f;--green-l:#7cdc44;--blue:#3b82f6;
    --bg:#f4f6f9;--surface:#fff;--border:#e4e6ea;
    --text:#1a1d23;--muted:#6b7280;--code-bg:#1e2433;
  }}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
        background:var(--bg);color:var(--text);line-height:1.6}}

  /* Layout */
  .layout{{display:grid;grid-template-columns:260px 1fr;min-height:100vh}}
  .sidebar{{background:var(--surface);border-right:1px solid var(--border);
            position:sticky;top:0;height:100vh;overflow-y:auto;padding:1.5rem 0}}
  .content{{padding:2rem 2.5rem;max-width:900px}}

  /* Sidebar */
  .brand{{padding:0 1.25rem 1.25rem;border-bottom:1px solid var(--border);margin-bottom:1rem}}
  .brand-logo{{font-size:1.15rem;font-weight:800;color:var(--green)}}
  .brand-sub{{font-size:.75rem;color:var(--muted);margin-top:.1rem}}
  .nav-section{{font-size:.68rem;font-weight:700;text-transform:uppercase;
                letter-spacing:.1em;color:var(--muted);padding:.65rem 1.25rem .35rem}}
  .nav-item{{display:flex;align-items:center;gap:.5rem;padding:.45rem 1.25rem;
             font-size:.85rem;color:var(--text);cursor:pointer;border-left:3px solid transparent;
             text-decoration:none;transition:all .15s}}
  .nav-item:hover{{background:#f8faf5;color:var(--green)}}
  .nav-item.active{{background:#f0fdf4;color:var(--green);border-left-color:var(--green);font-weight:600}}
  .nav-badge{{margin-left:auto;font-size:.65rem;font-weight:700;padding:.1rem .4rem;
              border-radius:8px;background:#dcfce7;color:#15803d}}
  .nav-badge.post{{background:#dbeafe;color:#1e40af}}
  .nav-badge.del{{background:#fee2e2;color:#991b1b}}

  /* Conteúdo */
  h1{{font-size:1.6rem;font-weight:800;margin-bottom:.4rem}}
  h2{{font-size:1.15rem;font-weight:700;margin:2.5rem 0 .75rem;padding-bottom:.4rem;
      border-bottom:1px solid var(--border)}}
  h3{{font-size:.95rem;font-weight:700;margin:1.5rem 0 .5rem;color:var(--green)}}
  p{{font-size:.9rem;color:var(--muted);margin-bottom:.75rem}}
  a{{color:var(--green)}}

  /* Endpoint cards */
  .endpoint{{background:var(--surface);border:1px solid var(--border);border-radius:12px;
             margin-bottom:1.5rem;overflow:hidden}}
  .ep-header{{display:flex;align-items:center;gap:.75rem;padding:.9rem 1.25rem;
              border-bottom:1px solid var(--border);cursor:pointer;user-select:none}}
  .ep-header:hover{{background:#fafbfc}}
  .method{{font-size:.72rem;font-weight:800;padding:.2rem .55rem;border-radius:6px;
           text-transform:uppercase;letter-spacing:.05em;min-width:48px;text-align:center}}
  .get{{background:#dbeafe;color:#1e40af}}
  .post{{background:#dcfce7;color:#15803d}}
  .put{{background:#fef9c3;color:#854d0e}}
  .delete{{background:#fee2e2;color:#991b1b}}
  .ep-path{{font-family:'JetBrains Mono','Fira Code',monospace;font-size:.9rem;font-weight:600}}
  .ep-desc{{margin-left:auto;font-size:.8rem;color:var(--muted)}}
  .ep-body{{padding:1.25rem}}

  /* Campos */
  .fields{{width:100%;border-collapse:collapse;font-size:.83rem;margin:.5rem 0 1rem}}
  .fields th{{background:#f8faf5;font-size:.72rem;font-weight:700;text-transform:uppercase;
              letter-spacing:.05em;color:var(--muted);padding:.5rem .75rem;text-align:left;
              border-bottom:1px solid var(--border)}}
  .fields td{{padding:.5rem .75rem;border-bottom:1px solid #f1f5f9;vertical-align:top}}
  .fields tr:last-child td{{border-bottom:none}}
  .req{{background:#dcfce7;color:#15803d;font-size:.68rem;font-weight:700;
        padding:.1rem .35rem;border-radius:6px}}
  .opt{{background:#f1f5f9;color:#475569;font-size:.68rem;font-weight:700;
        padding:.1rem .35rem;border-radius:6px}}

  /* Code blocks */
  .code-wrap{{position:relative;margin:.5rem 0 1rem}}
  .code-lang{{position:absolute;top:.55rem;right:.65rem;font-size:.68rem;font-weight:600;
              color:#64748b;text-transform:uppercase;letter-spacing:.06em}}
  pre{{background:var(--code-bg);color:#e2e8f0;border-radius:10px;
       padding:1rem 1.25rem;overflow-x:auto;font-size:.8rem;
       font-family:'JetBrains Mono','Fira Code',monospace;line-height:1.7}}
  .k{{color:#7dd3fc}}  /* key */
  .s{{color:#86efac}}  /* string */
  .n{{color:#fca5a5}}  /* number/bool */
  .c{{color:#94a3b8}}  /* comment */
  .hdr{{color:#fbbf24}} /* header */
  .mth{{color:#a78bfa}} /* method */
  .pth{{color:#7dd3fc}} /* path */

  /* Alerts */
  .alert-box{{padding:.75rem 1rem;border-radius:8px;font-size:.83rem;margin:.5rem 0 1rem;
              border-left:3px solid}}
  .alert-blue{{background:#eff6ff;border-color:#3b82f6;color:#1e40af}}
  .alert-yellow{{background:#fffbeb;border-color:#f59e0b;color:#92400e}}
  .alert-green{{background:#f0fdf4;border-color:#22c55e;color:#15803d}}

  /* Tag */
  .tag{{display:inline-block;font-size:.72rem;font-weight:700;padding:.15rem .5rem;
        border-radius:8px;margin-right:.25rem}}
  .tag-green{{background:#dcfce7;color:#15803d}}
  .tag-blue{{background:#dbeafe;color:#1e40af}}
  .tag-orange{{background:#ffedd5;color:#9a3412}}

  code{{background:#f4f6f9;padding:.1rem .35rem;border-radius:4px;
        font-size:.82rem;font-family:'JetBrains Mono','Fira Code',monospace}}

  /* Intro cards */
  .info-grid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:1rem;margin:1.25rem 0}}
  .info-card{{background:var(--surface);border:1px solid var(--border);border-radius:10px;
              padding:1rem;text-align:center}}
  .info-card .ic-icon{{font-size:1.5rem;margin-bottom:.3rem}}
  .info-card .ic-label{{font-size:.72rem;color:var(--muted);font-weight:600;text-transform:uppercase}}
  .info-card .ic-val{{font-size:.95rem;font-weight:700;color:var(--text);font-family:monospace}}

  @media(max-width:768px){{
    .layout{{grid-template-columns:1fr}}
    .sidebar{{display:none}}
    .content{{padding:1.25rem}}
    .info-grid{{grid-template-columns:1fr 1fr}}
  }}
</style>
</head>
<body>
<div class="layout">

<!-- ── Sidebar ──────────────────────────────────────────────────────────────── -->
<nav class="sidebar">
  <div class="brand">
    <div class="brand-logo">📱 ZapDin PDV</div>
    <div class="brand-sub">Documentação da API — v1.0</div>
  </div>

  <div class="nav-section">Início</div>
  <a class="nav-item active" href="#intro">Introdução</a>
  <a class="nav-item" href="#auth">Autenticação</a>
  <a class="nav-item" href="#status">Status do PDV</a>

  <div class="nav-section">Envio de Mensagens</div>
  <a class="nav-item" href="#ep-notificar"><span class="nav-badge post">POST</span> /erp/notificar</a>
  <a class="nav-item" href="#ep-venda"><span class="nav-badge post">POST</span> /erp/venda</a>
  <a class="nav-item" href="#ep-nfe"><span class="nav-badge post">POST</span> /erp/nota-fiscal</a>
  <a class="nav-item" href="#ep-boleto"><span class="nav-badge post">POST</span> /erp/boleto</a>

  <div class="nav-section">Templates</div>
  <a class="nav-item" href="#ep-templates-list"><span class="nav-badge">GET</span> /erp/templates</a>
  <a class="nav-item" href="#ep-templates-save"><span class="nav-badge post">PUT</span> /erp/templates</a>
  <a class="nav-item" href="#ep-templates-del"><span class="nav-badge del">DEL</span> /erp/templates/&#123;evento&#125;</a>
  <a class="nav-item" href="#ep-templates-painel"><span class="nav-badge">GET</span> /erp/templates/painel</a>

  <div class="nav-section">WhatsApp</div>
  <a class="nav-item" href="#ep-sessoes">Sessões locais</a>
  <a class="nav-item" href="#ep-qr">QR Code</a>

  <div class="nav-section">Referência</div>
  <a class="nav-item" href="#eventos">Eventos disponíveis</a>
  <a class="nav-item" href="#erros">Códigos de erro</a>
  <a class="nav-item" href="#exemplos">Exemplos completos</a>
</nav>

<!-- ── Conteúdo ─────────────────────────────────────────────────────────────── -->
<main class="content">

<!-- Intro -->
<section id="intro">
  <h1>ZapDin PDV — API de Integração ERP</h1>
  <p>O ZapDin PDV roda localmente na máquina do caixa e expõe uma API REST
  para o ERP enviar mensagens WhatsApp sem depender de servidores externos.</p>

  <div class="info-grid">
    <div class="info-card">
      <div class="ic-icon">🌐</div>
      <div class="ic-label">Base URL</div>
      <div class="ic-val">http://localhost:{port}</div>
    </div>
    <div class="info-card">
      <div class="ic-icon">🔐</div>
      <div class="ic-label">Autenticação</div>
      <div class="ic-val">X-PDV-Key</div>
    </div>
    <div class="info-card">
      <div class="ic-icon">📄</div>
      <div class="ic-label">Formato</div>
      <div class="ic-val">JSON / UTF-8</div>
    </div>
  </div>

  <div class="alert-box alert-green">
    ✅ <strong>Tudo local.</strong> O ERP chama <code>http://localhost:{port}</code> —
    sem internet, sem latência externa. O WhatsApp também conecta nesta máquina.
  </div>
</section>

<!-- Auth -->
<section id="auth">
  <h2>Autenticação</h2>
  <p>Todas as rotas exigem o header <code>X-PDV-Key</code> com a chave configurada no <code>.env</code> do PDV.</p>

  <div class="code-wrap">
    <div class="code-lang">HTTP</div>
    <pre><span class="mth">POST</span> <span class="pth">http://localhost:{port}/erp/venda</span>
<span class="hdr">X-PDV-Key:</span> <span class="s">{api_key}</span>
<span class="hdr">Content-Type:</span> <span class="s">application/json</span></pre>
  </div>

  <div class="alert-box alert-yellow">
    ⚠️ <strong>Sem a chave</strong> o PDV retorna <code>401 Unauthorized</code>.
    A chave fica em <code>PDV_API_KEY</code> no arquivo <code>.env</code> do PDV.
  </div>
</section>

<!-- Status -->
<section id="status">
  <h2>Status do PDV</h2>

  <div class="endpoint">
    <div class="ep-header">
      <span class="method get">GET</span>
      <span class="ep-path">/status</span>
      <span class="ep-desc">Verifica se o PDV está ativo e o WhatsApp conectado</span>
    </div>
    <div class="ep-body">
      <div class="code-wrap">
        <div class="code-lang">Resposta 200</div>
        <pre>{{
  <span class="k">"ok"</span>: <span class="n">true</span>,
  <span class="k">"pdv"</span>: <span class="s">"Caixa 01"</span>,
  <span class="k">"sessoes_conectadas"</span>: <span class="n">1</span>,
  <span class="k">"sessoes"</span>: [
    {{
      <span class="k">"id"</span>: <span class="s">"a1b2c3"</span>,
      <span class="k">"nome"</span>: <span class="s">"Caixa 01"</span>,
      <span class="k">"status"</span>: <span class="s">"connected"</span>,
      <span class="k">"phone"</span>: <span class="s">"5544999990000"</span>
    }}
  ]
}}</pre>
      </div>
      <div class="alert-box alert-blue">
        💡 Verifique <code>sessoes_conectadas &gt; 0</code> antes de enviar mensagens.
        Se for 0, o WhatsApp precisa ser conectado via QR code.
      </div>
    </div>
  </div>
</section>

<!-- ── Endpoint: /erp/notificar ─────────────────────────────────────────────── -->
<section id="ep-notificar">
  <h2>Envio de Mensagens</h2>

  <div class="endpoint">
    <div class="ep-header">
      <span class="method post">POST</span>
      <span class="ep-path">/erp/notificar</span>
      <span class="ep-desc">Endpoint genérico — qualquer evento com template</span>
    </div>
    <div class="ep-body">
      <p>Endpoint principal. O ERP informa o evento e as variáveis; o PDV busca o template, monta a mensagem e envia.</p>

      <h3>Campos</h3>
      <table class="fields">
        <thead><tr><th>Campo</th><th>Tipo</th><th>Req.</th><th>Descrição</th></tr></thead>
        <tbody>
          <tr><td><code>phone</code></td><td>string</td><td><span class="req">Sim</span></td><td>Número destino. Ex: <code>44999990000</code> ou <code>+5544999990000</code></td></tr>
          <tr><td><code>evento</code></td><td>string</td><td><span class="req">Sim</span></td><td>Nome do template. Ex: <code>venda_realizada</code></td></tr>
          <tr><td><code>vars</code></td><td>object</td><td><span class="opt">Não</span></td><td>Variáveis para preencher o template</td></tr>
          <tr><td><code>arquivo_base64</code></td><td>string</td><td><span class="opt">Não</span></td><td>Arquivo em base64 (PDF, imagem…)</td></tr>
          <tr><td><code>arquivo_nome</code></td><td>string</td><td><span class="opt">Não</span></td><td>Nome do arquivo com extensão: <code>nf_001.pdf</code></td></tr>
          <tr><td><code>arquivo_caption</code></td><td>string</td><td><span class="opt">Não</span></td><td>Legenda do arquivo (substitui o template se informada)</td></tr>
          <tr><td><code>apenas_arquivo</code></td><td>bool</td><td><span class="opt">Não</span></td><td><code>true</code> = não envia texto, só o arquivo. Padrão: <code>false</code></td></tr>
          <tr><td><code>sessao_id</code></td><td>string</td><td><span class="opt">Não</span></td><td>ID da sessão WhatsApp. Omita para usar a primeira conectada</td></tr>
        </tbody>
      </table>

      <h3>Exemplo — mensagem simples</h3>
      <div class="code-wrap">
        <div class="code-lang">JSON</div>
        <pre>{{
  <span class="k">"phone"</span>: <span class="s">"44999990000"</span>,
  <span class="k">"evento"</span>: <span class="s">"venda_realizada"</span>,
  <span class="k">"vars"</span>: {{
    <span class="k">"nome_cliente"</span>: <span class="s">"João Silva"</span>,
    <span class="k">"numero_venda"</span>: <span class="s">"001234"</span>,
    <span class="k">"valor_total"</span>: <span class="s">"350,00"</span>,
    <span class="k">"forma_pagamento"</span>: <span class="s">"Cartão de Débito"</span>,
    <span class="k">"data"</span>: <span class="s">"12/05/2026"</span>
  }}
}}</pre>
      </div>

      <h3>Exemplo — com arquivo PDF</h3>
      <div class="code-wrap">
        <div class="code-lang">JSON</div>
        <pre>{{
  <span class="k">"phone"</span>: <span class="s">"44999990000"</span>,
  <span class="k">"evento"</span>: <span class="s">"nota_fiscal"</span>,
  <span class="k">"vars"</span>: {{
    <span class="k">"nome_cliente"</span>: <span class="s">"João Silva"</span>,
    <span class="k">"numero_nf"</span>: <span class="s">"000456"</span>,
    <span class="k">"valor_total"</span>: <span class="s">"350,00"</span>,
    <span class="k">"data"</span>: <span class="s">"12/05/2026"</span>
  }},
  <span class="k">"arquivo_base64"</span>: <span class="s">"JVBERi0xLjQK..."</span>,
  <span class="k">"arquivo_nome"</span>: <span class="s">"nfe_000456.pdf"</span>
}}</pre>
      </div>

      <h3>Resposta de sucesso</h3>
      <div class="code-wrap">
        <div class="code-lang">JSON 200</div>
        <pre>{{
  <span class="k">"ok"</span>: <span class="n">true</span>,
  <span class="k">"phone"</span>: <span class="s">"5544999990000"</span>,
  <span class="k">"sessao_id"</span>: <span class="s">"a1b2c3"</span>,
  <span class="k">"enviados"</span>: [<span class="s">"texto"</span>, <span class="s">"arquivo:nfe_000456.pdf"</span>]
}}</pre>
      </div>
    </div>
  </div>
</section>

<!-- ── Endpoint: /erp/venda ──────────────────────────────────────────────────── -->
<section id="ep-venda">
  <div class="endpoint">
    <div class="ep-header">
      <span class="method post">POST</span>
      <span class="ep-path">/erp/venda</span>
      <span class="ep-desc">Atalho para comprovante de venda</span>
    </div>
    <div class="ep-body">
      <p>Campos nomeados para facilitar a integração. Usa o template <code>venda_realizada</code>.</p>

      <table class="fields">
        <thead><tr><th>Campo</th><th>Tipo</th><th>Req.</th><th>Descrição</th></tr></thead>
        <tbody>
          <tr><td><code>phone</code></td><td>string</td><td><span class="req">Sim</span></td><td>Número do cliente</td></tr>
          <tr><td><code>numero_venda</code></td><td>string</td><td><span class="req">Sim</span></td><td>Número/código da venda</td></tr>
          <tr><td><code>nome_cliente</code></td><td>string</td><td><span class="req">Sim</span></td><td>Nome do cliente</td></tr>
          <tr><td><code>valor_total</code></td><td>string</td><td><span class="req">Sim</span></td><td>Ex: <code>"350,00"</code></td></tr>
          <tr><td><code>forma_pagamento</code></td><td>string</td><td><span class="opt">Não</span></td><td>Ex: <code>"Cartão de Débito"</code></td></tr>
          <tr><td><code>data</code></td><td>string</td><td><span class="opt">Não</span></td><td>Data da venda. Ex: <code>"12/05/2026"</code></td></tr>
          <tr><td><code>itens</code></td><td>array</td><td><span class="opt">Não</span></td><td>Lista de produtos (ver abaixo)</td></tr>
          <tr><td><code>observacao</code></td><td>string</td><td><span class="opt">Não</span></td><td>Observação livre</td></tr>
          <tr><td><code>arquivo_base64</code></td><td>string</td><td><span class="opt">Não</span></td><td>PDF do comprovante em base64</td></tr>
          <tr><td><code>arquivo_nome</code></td><td>string</td><td><span class="opt">Não</span></td><td>Nome do arquivo</td></tr>
        </tbody>
      </table>

      <h3>Estrutura de <code>itens</code></h3>
      <div class="code-wrap">
        <div class="code-lang">JSON</div>
        <pre><span class="k">"itens"</span>: [
  {{ <span class="k">"descricao"</span>: <span class="s">"Coca-Cola 2L"</span>, <span class="k">"quantidade"</span>: <span class="n">2</span>, <span class="k">"valor_unitario"</span>: <span class="s">"8,50"</span> }},
  {{ <span class="k">"descricao"</span>: <span class="s">"Pão de Forma"</span>,  <span class="k">"quantidade"</span>: <span class="n">1</span>, <span class="k">"valor_unitario"</span>: <span class="s">"12,00"</span> }}
]</pre>
      </div>

      <h3>Exemplo completo</h3>
      <div class="code-wrap">
        <div class="code-lang">JSON</div>
        <pre>{{
  <span class="k">"phone"</span>: <span class="s">"44999990000"</span>,
  <span class="k">"numero_venda"</span>: <span class="s">"001234"</span>,
  <span class="k">"nome_cliente"</span>: <span class="s">"João Silva"</span>,
  <span class="k">"valor_total"</span>: <span class="s">"29,00"</span>,
  <span class="k">"forma_pagamento"</span>: <span class="s">"PIX"</span>,
  <span class="k">"data"</span>: <span class="s">"12/05/2026"</span>,
  <span class="k">"itens"</span>: [
    {{ <span class="k">"descricao"</span>: <span class="s">"Coca-Cola 2L"</span>, <span class="k">"quantidade"</span>: <span class="n">2</span>, <span class="k">"valor_unitario"</span>: <span class="s">"8,50"</span> }},
    {{ <span class="k">"descricao"</span>: <span class="s">"Pão de Forma"</span>,  <span class="k">"quantidade"</span>: <span class="n">1</span>, <span class="k">"valor_unitario"</span>: <span class="s">"12,00"</span> }}
  ]
}}</pre>
      </div>
    </div>
  </div>
</section>

<!-- ── Endpoint: /erp/nota-fiscal ───────────────────────────────────────────── -->
<section id="ep-nfe">
  <div class="endpoint">
    <div class="ep-header">
      <span class="method post">POST</span>
      <span class="ep-path">/erp/nota-fiscal</span>
      <span class="ep-desc">Atalho para NF-e</span>
    </div>
    <div class="ep-body">
      <table class="fields">
        <thead><tr><th>Campo</th><th>Tipo</th><th>Req.</th><th>Descrição</th></tr></thead>
        <tbody>
          <tr><td><code>phone</code></td><td>string</td><td><span class="req">Sim</span></td><td>Número do cliente</td></tr>
          <tr><td><code>numero_nf</code></td><td>string</td><td><span class="req">Sim</span></td><td>Número da NF-e</td></tr>
          <tr><td><code>nome_cliente</code></td><td>string</td><td><span class="req">Sim</span></td><td>Nome do cliente</td></tr>
          <tr><td><code>valor_total</code></td><td>string</td><td><span class="req">Sim</span></td><td>Valor da nota</td></tr>
          <tr><td><code>data</code></td><td>string</td><td><span class="opt">Não</span></td><td>Data de emissão</td></tr>
          <tr><td><code>chave_acesso</code></td><td>string</td><td><span class="opt">Não</span></td><td>Chave de acesso da NF-e (44 dígitos)</td></tr>
          <tr><td><code>link_danfe</code></td><td>string</td><td><span class="opt">Não</span></td><td>URL para download da DANFE</td></tr>
          <tr><td><code>arquivo_base64</code></td><td>string</td><td><span class="opt">Não</span></td><td>PDF da NF-e em base64</td></tr>
          <tr><td><code>arquivo_nome</code></td><td>string</td><td><span class="opt">Não</span></td><td>Ex: <code>"nfe_000456.pdf"</code></td></tr>
        </tbody>
      </table>

      <div class="code-wrap">
        <div class="code-lang">JSON</div>
        <pre>{{
  <span class="k">"phone"</span>: <span class="s">"44999990000"</span>,
  <span class="k">"numero_nf"</span>: <span class="s">"000456"</span>,
  <span class="k">"nome_cliente"</span>: <span class="s">"João Silva"</span>,
  <span class="k">"valor_total"</span>: <span class="s">"350,00"</span>,
  <span class="k">"data"</span>: <span class="s">"12/05/2026"</span>,
  <span class="k">"arquivo_base64"</span>: <span class="s">"JVBERi0xLjQK..."</span>,
  <span class="k">"arquivo_nome"</span>: <span class="s">"nfe_000456.pdf"</span>
}}</pre>
      </div>
    </div>
  </div>
</section>

<!-- ── Endpoint: /erp/boleto ────────────────────────────────────────────────── -->
<section id="ep-boleto">
  <div class="endpoint">
    <div class="ep-header">
      <span class="method post">POST</span>
      <span class="ep-path">/erp/boleto</span>
      <span class="ep-desc">Atalho para boleto bancário</span>
    </div>
    <div class="ep-body">
      <table class="fields">
        <thead><tr><th>Campo</th><th>Tipo</th><th>Req.</th><th>Descrição</th></tr></thead>
        <tbody>
          <tr><td><code>phone</code></td><td>string</td><td><span class="req">Sim</span></td><td>Número do cliente</td></tr>
          <tr><td><code>nome_cliente</code></td><td>string</td><td><span class="req">Sim</span></td><td>Nome do cliente</td></tr>
          <tr><td><code>valor_total</code></td><td>string</td><td><span class="req">Sim</span></td><td>Valor do boleto</td></tr>
          <tr><td><code>data_vencimento</code></td><td>string</td><td><span class="req">Sim</span></td><td>Data de vencimento. Ex: <code>"20/05/2026"</code></td></tr>
          <tr><td><code>linha_digitavel</code></td><td>string</td><td><span class="opt">Não</span></td><td>Linha digitável do boleto</td></tr>
          <tr><td><code>link_boleto</code></td><td>string</td><td><span class="opt">Não</span></td><td>URL para visualizar/baixar o boleto</td></tr>
          <tr><td><code>arquivo_base64</code></td><td>string</td><td><span class="opt">Não</span></td><td>PDF do boleto em base64</td></tr>
          <tr><td><code>arquivo_nome</code></td><td>string</td><td><span class="opt">Não</span></td><td>Ex: <code>"boleto.pdf"</code></td></tr>
        </tbody>
      </table>
    </div>
  </div>
</section>

<!-- ── Templates ────────────────────────────────────────────────────────────── -->
<section id="ep-templates-list">
  <h2>Templates de Mensagem</h2>
  <p>O PDV usa templates JSON para montar as mensagens. O ERP pode consultar, criar e editar templates via API.</p>

  <div class="endpoint">
    <div class="ep-header">
      <span class="method get">GET</span>
      <span class="ep-path">/erp/templates</span>
      <span class="ep-desc">Lista todos os templates</span>
    </div>
    <div class="ep-body">
      <div class="code-wrap">
        <div class="code-lang">JSON 200</div>
        <pre>{{
  <span class="k">"venda_realizada"</span>: {{
    <span class="k">"descricao"</span>: <span class="s">"Comprovante de venda"</span>,
    <span class="k">"mensagem"</span>: <span class="s">"✅ *Venda Confirmada!*\\n\\n👤 {{nome_cliente}}\\n💰 R$ {{valor_total}}"</span>,
    <span class="k">"ativo"</span>: <span class="n">true</span>
  }},
  <span class="c">// ... demais templates</span>
}}</pre>
      </div>
    </div>
  </div>

  <div id="ep-templates-save" class="endpoint">
    <div class="ep-header">
      <span class="method put">PUT</span>
      <span class="ep-path">/erp/templates</span>
      <span class="ep-desc">Criar ou editar template</span>
    </div>
    <div class="ep-body">
      <div class="code-wrap">
        <div class="code-lang">JSON</div>
        <pre>{{
  <span class="k">"evento"</span>: <span class="s">"meu_evento"</span>,
  <span class="k">"descricao"</span>: <span class="s">"Minha mensagem personalizada"</span>,
  <span class="k">"mensagem"</span>: <span class="s">"Olá {{nome_cliente}}! Seu pedido {{numero}} está pronto."</span>,
  <span class="k">"ativo"</span>: <span class="n">true</span>
}}</pre>
      </div>
    </div>
  </div>

  <div id="ep-templates-del" class="endpoint">
    <div class="ep-header">
      <span class="method delete">DELETE</span>
      <span class="ep-path">/erp/templates/&#123;evento&#125;</span>
      <span class="ep-desc">Remove um template</span>
    </div>
    <div class="ep-body">
      <div class="code-wrap">
        <div class="code-lang">HTTP</div>
        <pre><span class="mth">DELETE</span> <span class="pth">http://localhost:{port}/erp/templates/meu_evento</span>
<span class="hdr">X-PDV-Key:</span> <span class="s">{api_key}</span></pre>
      </div>
    </div>
  </div>

  <div id="ep-templates-painel" class="endpoint">
    <div class="ep-header">
      <span class="method get">GET</span>
      <span class="ep-path">/erp/templates/painel</span>
      <span class="ep-desc">Painel web para editar templates visualmente</span>
    </div>
    <div class="ep-body">
      <p>Abra no navegador: <a href="/erp/templates/painel" target="_blank">http://localhost:{port}/erp/templates/painel</a>
      — interface gráfica para editar as mensagens sem mexer em código.</p>
    </div>
  </div>
</section>

<!-- ── WhatsApp ─────────────────────────────────────────────────────────────── -->
<section id="ep-sessoes">
  <h2>WhatsApp Local</h2>

  <div class="endpoint">
    <div class="ep-header">
      <span class="method get">GET</span>
      <span class="ep-path">/whatsapp/sessoes</span>
      <span class="ep-desc">Lista sessões WhatsApp</span>
    </div>
    <div class="ep-body">
      <div class="code-wrap">
        <div class="code-lang">JSON 200</div>
        <pre>[{{
  <span class="k">"id"</span>: <span class="s">"a1b2c3"</span>,
  <span class="k">"nome"</span>: <span class="s">"Caixa 01"</span>,
  <span class="k">"status"</span>: <span class="s">"connected"</span>,  <span class="c">// connected | connecting | disconnected</span>
  <span class="k">"phone"</span>: <span class="s">"5544999990000"</span>
}}]</pre>
      </div>
    </div>
  </div>

  <div id="ep-qr" class="endpoint">
    <div class="ep-header">
      <span class="method get">GET</span>
      <span class="ep-path">/whatsapp/sessoes/&#123;id&#125;/qr-page</span>
      <span class="ep-desc">Página HTML com QR code para conectar WhatsApp</span>
    </div>
    <div class="ep-body">
      <p>Abra no navegador da máquina local para escanear o QR code com o celular.
      Detecta automaticamente quando o WhatsApp conecta.</p>
      <div class="alert-box alert-blue">
        💡 Não requer <code>X-PDV-Key</code> — é uma página local de setup.
      </div>
    </div>
  </div>
</section>

<!-- ── Eventos disponíveis ──────────────────────────────────────────────────── -->
<section id="eventos">
  <h2>Eventos e Variáveis Disponíveis</h2>
  <p>Cada evento tem um template configurável. Use as variáveis entre <code>{{{{chaves}}}}</code>.</p>

  <table class="fields" style="font-size:.82rem">
    <thead><tr><th>Evento</th><th>Descrição</th><th>Variáveis</th></tr></thead>
    <tbody>
      <tr>
        <td><code>venda_realizada</code></td>
        <td>Comprovante de venda</td>
        <td><code>nome_cliente</code> <code>numero_venda</code> <code>valor_total</code> <code>forma_pagamento</code> <code>data</code> <code>itens</code></td>
      </tr>
      <tr>
        <td><code>nota_fiscal</code></td>
        <td>NF-e emitida</td>
        <td><code>nome_cliente</code> <code>numero_nf</code> <code>valor_total</code> <code>data</code> <code>chave_acesso</code> <code>link_danfe</code></td>
      </tr>
      <tr>
        <td><code>boleto</code></td>
        <td>Boleto bancário</td>
        <td><code>nome_cliente</code> <code>valor_total</code> <code>data_vencimento</code> <code>linha_digitavel</code> <code>link_boleto</code></td>
      </tr>
      <tr>
        <td><code>pedido_confirmado</code></td>
        <td>Confirmação de pedido</td>
        <td><code>nome_cliente</code> <code>numero_pedido</code> <code>valor_total</code> <code>previsao_entrega</code></td>
      </tr>
      <tr>
        <td><code>entrega_realizada</code></td>
        <td>Entrega concluída</td>
        <td><code>nome_cliente</code> <code>numero_pedido</code> <code>data</code></td>
      </tr>
      <tr>
        <td><code>cobranca</code></td>
        <td>Lembrete de pagamento</td>
        <td><code>nome_cliente</code> <code>valor_total</code> <code>data_vencimento</code></td>
      </tr>
      <tr>
        <td><code>custom</code></td>
        <td>Mensagem livre</td>
        <td><code>mensagem</code> (texto completo enviado pelo ERP)</td>
      </tr>
    </tbody>
  </table>

  <div class="alert-box alert-green">
    ✅ <strong>Variável não encontrada?</strong> O PDV mantém o marcador original —
    ex: se <code>forma_pagamento</code> não for enviado, aparece literalmente <code>{{forma_pagamento}}</code>
    na mensagem. Configure o template para omitir campos opcionais.
  </div>
</section>

<!-- ── Erros ─────────────────────────────────────────────────────────────────── -->
<section id="erros">
  <h2>Códigos de Erro</h2>

  <table class="fields">
    <thead><tr><th>HTTP</th><th>Situação</th><th>Solução</th></tr></thead>
    <tbody>
      <tr><td><code>401</code></td><td>X-PDV-Key ausente ou incorreta</td><td>Verifique <code>PDV_API_KEY</code> no .env do PDV</td></tr>
      <tr><td><code>400</code></td><td>Template não encontrado ou inativo</td><td>Verifique o nome do evento em <code>/erp/templates</code></td></tr>
      <tr><td><code>400</code></td><td>Erro ao enviar mensagem pelo WhatsApp</td><td>Número inválido ou sessão com problema</td></tr>
      <tr><td><code>503</code></td><td>Nenhuma sessão WhatsApp conectada</td><td>Conecte o WhatsApp em <code>/whatsapp/sessoes/{{id}}/qr-page</code></td></tr>
      <tr><td><code>422</code></td><td>Campos obrigatórios ausentes</td><td>Verifique os campos marcados como <span class="req">Sim</span></td></tr>
    </tbody>
  </table>
</section>

<!-- ── Exemplos completos ────────────────────────────────────────────────────── -->
<section id="exemplos">
  <h2>Exemplos Completos</h2>

  <h3>cURL</h3>
  <div class="code-wrap">
    <div class="code-lang">Shell</div>
    <pre>curl -X POST http://localhost:{port}/erp/venda \\
  -H <span class="s">"X-PDV-Key: {api_key}"</span> \\
  -H <span class="s">"Content-Type: application/json"</span> \\
  -d '{{
    "phone": "44999990000",
    "numero_venda": "001234",
    "nome_cliente": "João Silva",
    "valor_total": "350,00",
    "forma_pagamento": "PIX",
    "data": "12/05/2026"
  }}'</pre>
  </div>

  <h3>Python</h3>
  <div class="code-wrap">
    <div class="code-lang">Python</div>
    <pre><span class="k">import</span> requests

PDV_URL = <span class="s">"http://localhost:{port}"</span>
PDV_KEY = <span class="s">"{api_key}"</span>
HEADERS = {{"X-PDV-Key": PDV_KEY, "Content-Type": "application/json"}}

<span class="c"># Enviar comprovante de venda</span>
r = requests.post(f"{{PDV_URL}}/erp/venda", headers=HEADERS, json={{
    "phone": "44999990000",
    "numero_venda": "001234",
    "nome_cliente": "João Silva",
    "valor_total": "350,00",
    "forma_pagamento": "PIX",
    "data": "12/05/2026",
}})
print(r.json())  <span class="c"># {{"ok": true, "phone": "5544999990000", ...}}</span></pre>
  </div>

  <h3>C# / .NET</h3>
  <div class="code-wrap">
    <div class="code-lang">C#</div>
    <pre><span class="k">using</span> System.Net.Http;
<span class="k">using</span> System.Text;
<span class="k">using</span> System.Text.Json;

<span class="k">var</span> client = <span class="k">new</span> HttpClient();
client.DefaultRequestHeaders.Add(<span class="s">"X-PDV-Key"</span>, <span class="s">"{api_key}"</span>);

<span class="k">var</span> payload = <span class="k">new</span> {{
    phone = <span class="s">"44999990000"</span>,
    numero_venda = <span class="s">"001234"</span>,
    nome_cliente = <span class="s">"João Silva"</span>,
    valor_total = <span class="s">"350,00"</span>,
    forma_pagamento = <span class="s">"PIX"</span>,
    data = <span class="s">"12/05/2026"</span>
}};

<span class="k">var</span> json = JsonSerializer.Serialize(payload);
<span class="k">var</span> content = <span class="k">new</span> StringContent(json, Encoding.UTF8, <span class="s">"application/json"</span>);
<span class="k">var</span> response = <span class="k">await</span> client.PostAsync(
    <span class="s">"http://localhost:{port}/erp/venda"</span>, content);
<span class="k">var</span> result = <span class="k">await</span> response.Content.ReadAsStringAsync();</pre>
  </div>

  <h3>Delphi / Pascal</h3>
  <div class="code-wrap">
    <div class="code-lang">Delphi</div>
    <pre><span class="k">uses</span> IdHTTP, IdSSLOpenSSL, System.JSON;

<span class="k">procedure</span> EnviarVenda;
<span class="k">var</span>
  HTTP: TIdHTTP;
  Body, Resp: TStringStream;
  JSON: TJSONObject;
<span class="k">begin</span>
  HTTP := TIdHTTP.Create(<span class="k">nil</span>);
  <span class="k">try</span>
    HTTP.Request.CustomHeaders.AddValue(<span class="s">'X-PDV-Key'</span>, <span class="s">'{api_key}'</span>);
    HTTP.Request.ContentType := <span class="s">'application/json'</span>;

    JSON := TJSONObject.Create;
    JSON.AddPair(<span class="s">'phone'</span>,         <span class="s">'44999990000'</span>);
    JSON.AddPair(<span class="s">'numero_venda'</span>,  <span class="s">'001234'</span>);
    JSON.AddPair(<span class="s">'nome_cliente'</span>,  <span class="s">'João Silva'</span>);
    JSON.AddPair(<span class="s">'valor_total'</span>,   <span class="s">'350,00'</span>);
    JSON.AddPair(<span class="s">'forma_pagamento'</span>, <span class="s">'PIX'</span>);
    JSON.AddPair(<span class="s">'data'</span>,          <span class="s">'12/05/2026'</span>);

    Body := TStringStream.Create(JSON.ToString, TEncoding.UTF8);
    Resp := TStringStream.Create(<span class="s">''</span>, TEncoding.UTF8);
    <span class="k">try</span>
      HTTP.Post(<span class="s">'http://localhost:{port}/erp/venda'</span>, Body, Resp);
      ShowMessage(Resp.DataString); <span class="c">// {{"ok":true,...}}</span>
    <span class="k">finally</span>
      Body.Free; Resp.Free; JSON.Free;
    <span class="k">end</span>;
  <span class="k">finally</span>
    HTTP.Free;
  <span class="k">end</span>;
<span class="k">end</span>;</pre>
  </div>

</section>

<div style="margin:3rem 0 1rem;padding:1rem;background:var(--surface);border:1px solid var(--border);
            border-radius:10px;font-size:.8rem;color:var(--muted);text-align:center">
  ZapDin PDV v1.0 · Rodando em <strong>http://localhost:{port}</strong> ·
  <a href="/docs" target="_blank">Swagger UI</a> ·
  <a href="/erp/templates/painel" target="_blank">Painel de Templates</a>
</div>

</main>
</div>

<script>
// Scroll suave + highlight item ativo na sidebar
document.querySelectorAll('a[href^="#"]').forEach(a => {{
  a.addEventListener('click', e => {{
    e.preventDefault();
    const el = document.querySelector(a.getAttribute('href'));
    if (el) el.scrollIntoView({{behavior:'smooth', block:'start'}});
  }});
}});

const observer = new IntersectionObserver(entries => {{
  entries.forEach(e => {{
    if (e.isIntersecting) {{
      document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
      const id = e.target.id;
      const link = document.querySelector(`.nav-item[href="#${{id}}"]`);
      if (link) link.classList.add('active');
    }}
  }});
}}, {{threshold: 0.3}});

document.querySelectorAll('section[id]').forEach(s => observer.observe(s));
</script>
</body>
</html>"""
