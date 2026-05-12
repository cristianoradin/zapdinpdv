"""
launcher.py — Entry-point do executável ZapDin PDV (Windows).

Fluxo:
  1. Detecta se é primeiro uso (.env sem configuração real)
  2. Se sim → abre wizard tkinter para configurar
  3. Após configuração → inicia servidor FastAPI
  4. Mostra ícone na bandeja do sistema (systray)
"""
import sys
import os
import threading
import logging
import webbrowser
from pathlib import Path

# ── Resolve pasta base (executável PyInstaller ou desenvolvimento) ────────────
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
    # Garante que o diretório do exe está no path para imports do pacote pdv
    pkg_dir = BASE_DIR.parent
    if str(pkg_dir) not in sys.path:
        sys.path.insert(0, str(pkg_dir))
else:
    BASE_DIR = Path(__file__).parent

os.chdir(str(BASE_DIR))

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(str(BASE_DIR / "zapdin_pdv.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

ENV_PATH = BASE_DIR / ".env"


# ── Verificação de primeiro uso ───────────────────────────────────────────────

def _is_primeira_vez() -> bool:
    """Retorna True se .env não existe ou não tem configuração real."""
    if not ENV_PATH.exists():
        return True
    content = ENV_PATH.read_text(encoding="utf-8", errors="ignore")
    # Considera configurado se tiver ZAPDIN_URL preenchido
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("ZAPDIN_URL=") and len(line) > len("ZAPDIN_URL=http"):
            return False
    return True


# ── Wizard tkinter ────────────────────────────────────────────────────────────

def _show_wizard():
    """Janela de configuração inicial. Bloqueia até o usuário concluir ou fechar."""
    import tkinter as tk
    from tkinter import ttk, messagebox

    resultado = {"ok": False}

    root = tk.Tk()
    root.title("ZapDin PDV — Configuração Inicial")
    root.geometry("520x600")
    root.resizable(False, False)
    root.configure(bg="#f4f6f9")

    try:
        from PIL import Image, ImageTk, ImageDraw
        img = Image.new("RGBA", (48, 48), (61, 127, 31, 255))
        d = ImageDraw.Draw(img)
        d.ellipse([4, 4, 44, 44], fill="white")
        d.text((14, 8), "Z", fill=(61, 127, 31, 255))
        photo = ImageTk.PhotoImage(img)
        root.iconphoto(True, photo)
    except Exception:
        pass

    # ── Estilo ──────────────────────────────────────────────────────────────
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Green.TButton",
                    background="#3d7f1f", foreground="white",
                    font=("Segoe UI", 10, "bold"), padding=8)
    style.map("Green.TButton",
              background=[("active", "#2d5f17"), ("disabled", "#9ca3af")])
    style.configure("TEntry", padding=6, font=("Segoe UI", 10))
    style.configure("TLabel", background="#f4f6f9", font=("Segoe UI", 10))
    style.configure("Title.TLabel", background="#f4f6f9",
                    font=("Segoe UI", 16, "bold"), foreground="#3d7f1f")
    style.configure("Sub.TLabel", background="#f4f6f9",
                    font=("Segoe UI", 9), foreground="#6b7280")
    style.configure("Section.TLabel", background="#f4f6f9",
                    font=("Segoe UI", 9, "bold"), foreground="#374151")

    # ── Cabeçalho ────────────────────────────────────────────────────────────
    frame_top = tk.Frame(root, bg="#3d7f1f", pady=18)
    frame_top.pack(fill="x")
    tk.Label(frame_top, text="📱 ZapDin PDV",
             bg="#3d7f1f", fg="white",
             font=("Segoe UI", 18, "bold")).pack()
    tk.Label(frame_top, text="Configure a conexão com o ZapDin App",
             bg="#3d7f1f", fg="#a8d5a2",
             font=("Segoe UI", 9)).pack(pady=(2, 0))

    # ── Formulário ───────────────────────────────────────────────────────────
    frame = tk.Frame(root, bg="#f4f6f9", padx=30, pady=20)
    frame.pack(fill="both", expand=True)

    def campo(parent, label, placeholder="", show=""):
        tk.Label(parent, text=label,
                 bg="#f4f6f9", fg="#374151",
                 font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", pady=(10, 2))
        var = tk.StringVar()
        e = tk.Entry(parent, textvariable=var, show=show,
                     font=("Segoe UI", 10),
                     relief="solid", bd=1, bg="white", fg="#1a1d23",
                     highlightthickness=1, highlightcolor="#3d7f1f",
                     insertbackground="#3d7f1f")
        e.pack(fill="x", ipady=5)
        var.set(placeholder)
        return var

    # Seção ZapDin App
    sep1 = tk.Frame(frame, bg="#e4e6ea", height=1)
    sep1.pack(fill="x", pady=(0, 5))
    tk.Label(frame, text="🌐  ZAPDIN APP REMOTO",
             bg="#f4f6f9", fg="#6b7280",
             font=("Segoe UI", 8, "bold")).pack(anchor="w")

    var_url  = campo(frame, "URL do ZapDin App *",
                     placeholder="https://app.seuservidor.com.br")
    var_user = campo(frame, "Usuário *", placeholder="usuario@empresa.com")
    var_pass = campo(frame, "Senha *", show="●")

    # Seção PDV local
    sep2 = tk.Frame(frame, bg="#e4e6ea", height=1)
    sep2.pack(fill="x", pady=(18, 5))
    tk.Label(frame, text="🖥️  PDV LOCAL",
             bg="#f4f6f9", fg="#6b7280",
             font=("Segoe UI", 8, "bold")).pack(anchor="w")

    var_nome  = campo(frame, "Nome do caixa *", placeholder="Caixa 01")
    var_key   = campo(frame, "Chave de API (PDV_API_KEY) *",
                      placeholder="minha-chave-secreta-123")
    var_porta = campo(frame, "Porta local (padrão 4600)", placeholder="4600")

    # Rodapé
    lbl_status = tk.Label(frame, text="", bg="#f4f6f9",
                          font=("Segoe UI", 9), fg="#dc2626",
                          wraplength=440, justify="left")
    lbl_status.pack(fill="x", pady=(12, 0))

    def salvar():
        url   = var_url.get().strip()
        user  = var_user.get().strip()
        pw    = var_pass.get().strip()
        nome  = var_nome.get().strip()
        key   = var_key.get().strip()
        porta = var_porta.get().strip() or "4600"

        erros = []
        if not url or url == "https://app.seuservidor.com.br":
            erros.append("• URL do ZapDin App é obrigatória")
        if not user or user == "usuario@empresa.com":
            erros.append("• Usuário é obrigatório")
        if not pw:
            erros.append("• Senha é obrigatória")
        if not nome or nome == "Caixa 01":
            erros.append("• Nome do caixa é obrigatório")
        if not key or key == "minha-chave-secreta-123":
            erros.append("• Chave de API é obrigatória")
        if not porta.isdigit():
            erros.append("• Porta deve ser um número")

        if erros:
            lbl_status.config(text="\n".join(erros), fg="#dc2626")
            return

        # Escreve .env
        env_content = f"""# ZapDin PDV — Gerado pelo wizard de configuração
# Para alterar: edite este arquivo e reinicie o ZapDin PDV

# Evolution API rodando localmente (instalado junto com o PDV)
EVOLUTION_URL=http://localhost:8080
EVOLUTION_API_KEY=zapdin-pdv-local

# ZapDin App REMOTO — credenciais
ZAPDIN_URL={url}
ZAPDIN_USERNAME={user}
ZAPDIN_PASSWORD={pw}

# Configuração do PDV local
PDV_PORT={porta}
PDV_API_KEY={key}
PDV_NOME={nome}
PDV_EMPRESA_ID=1

SESSION_REFRESH_MINUTES=60
"""
        try:
            ENV_PATH.write_text(env_content, encoding="utf-8")
            resultado["ok"] = True
            lbl_status.config(text="✅ Configuração salva!", fg="#15803d")
            root.after(1000, root.destroy)
        except Exception as exc:
            lbl_status.config(text=f"Erro ao salvar: {exc}", fg="#dc2626")

    btn_salvar = ttk.Button(frame, text="✅  Salvar e Iniciar",
                            style="Green.TButton", command=salvar)
    btn_salvar.pack(fill="x", pady=(14, 0), ipady=4)

    tk.Label(frame,
             text="Você pode alterar estas configurações depois editando o\n"
                  "arquivo .env na pasta de instalação.",
             bg="#f4f6f9", fg="#9ca3af",
             font=("Segoe UI", 8), justify="center").pack(pady=(10, 0))

    root.mainloop()
    return resultado["ok"]


# ── Servidor FastAPI ──────────────────────────────────────────────────────────

def _run_server():
    """Inicia o servidor FastAPI."""
    import uvicorn
    from pdv.config import settings
    from pdv.main import app

    logger.info("ZapDin PDV iniciando na porta %s…", settings.pdv_port)
    uvicorn.run(app, host="127.0.0.1", port=settings.pdv_port, log_level="warning")


# ── Systray ───────────────────────────────────────────────────────────────────

def _try_systray(port: int):
    """Ícone na bandeja do sistema. Cai no loop infinito se não disponível."""
    try:
        import pystray
        from PIL import Image, ImageDraw

        # Ícone verde com letra Z
        img = Image.new("RGBA", (64, 64), (61, 127, 31, 255))
        d = ImageDraw.Draw(img)
        d.ellipse([6, 6, 58, 58], fill="white")
        d.text((19, 14), "Z", fill=(61, 127, 31, 255))

        def _abrir_docs(icon, item):
            webbrowser.open(f"http://localhost:{port}/docs")

        def _abrir_painel(icon, item):
            webbrowser.open(f"http://localhost:{port}/erp/templates/painel")

        def _abrir_whatsapp(icon, item):
            webbrowser.open(f"http://localhost:{port}/setup/qr")

        def _abrir_status(icon, item):
            webbrowser.open(f"http://localhost:{port}/status")

        def _sair(icon, item):
            logger.info("ZapDin PDV encerrando via systray.")
            icon.stop()
            os._exit(0)

        menu = pystray.Menu(
            pystray.MenuItem("ZapDin PDV", None, enabled=False),
            pystray.MenuItem(f"Porta {port}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("📊  Ver status",        _abrir_status),
            pystray.MenuItem("📝  Templates ERP",     _abrir_painel),
            pystray.MenuItem("📱  Conectar WhatsApp", _abrir_whatsapp),
            pystray.MenuItem("📖  Documentação API",  _abrir_docs),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("❌  Sair", _sair),
        )
        icon = pystray.Icon("ZapDinPDV", img, "ZapDin PDV", menu)
        icon.run()

    except Exception as exc:
        logger.debug("Systray indisponível: %s", exc)
        import time
        while True:
            time.sleep(60)


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # 1. Wizard de primeiro uso
    if _is_primeira_vez():
        logger.info("Primeiro uso detectado — abrindo wizard de configuração.")
        configurado = _show_wizard()
        if not configurado:
            logger.warning("Wizard cancelado. Encerrando.")
            sys.exit(0)

    # 2. Carrega settings (lê .env recém-criado)
    from pdv.config import settings  # noqa: E402

    # 3. Inicia servidor em thread daemon
    t = threading.Thread(target=_run_server, daemon=True, name="pdv-server")
    t.start()

    import time
    time.sleep(2)  # aguarda o servidor subir
    logger.info("ZapDin PDV rodando em http://localhost:%s", settings.pdv_port)

    # 4. Systray (bloqueia até o usuário clicar em Sair)
    _try_systray(settings.pdv_port)
