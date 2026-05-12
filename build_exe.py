"""
build_exe.py — Gera ZapDinPDV.exe com PyInstaller (Windows).

Pré-requisitos (rodar UMA VEZ antes):
  pip install -r requirements.txt
  pip install pyinstaller

Uso:
  python build_exe.py

Saída:
  dist/ZapDinPDV/         ← pasta completa
  dist/ZapDinPDV/ZapDinPDV.exe
"""
import os
import sys
import shutil
import textwrap
import subprocess
from pathlib import Path

# ── Caminhos ──────────────────────────────────────────────────────────────────
ROOT  = Path(__file__).parent          # pdv/
BASE  = ROOT.parent                    # Zapdin2/
DIST  = ROOT / "dist" / "ZapDinPDV"
BUILD = ROOT / "build"
ENTRY = ROOT / "launcher.py"
SPEC  = ROOT / "ZapDinPDV.spec"
ICON  = ROOT / "icon.ico"             # opcional — cria automaticamente se não existir

# ── Cria ícone padrão se não existir ─────────────────────────────────────────
def _criar_icone():
    if ICON.exists():
        return str(ICON)
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGBA", (256, 256), (61, 127, 31, 255))
        d = ImageDraw.Draw(img)
        d.ellipse([20, 20, 236, 236], fill=(255, 255, 255, 255))
        d.text((78, 60), "Z", fill=(61, 127, 31, 255))
        img.save(str(ICON))
        print(f"  ✅ Ícone criado: {ICON}")
        return str(ICON)
    except Exception as exc:
        print(f"  ⚠️  Não foi possível criar ícone: {exc}")
        return None


# ── Gera arquivo .spec ────────────────────────────────────────────────────────
def _gerar_spec(icon_path):
    sep = os.pathsep
    icon_line = f"icon=r'{icon_path}'," if icon_path else ""

    # Arquivos extras a empacotar
    datas = [
        (str(ROOT / ".env.example"), "."),
    ]
    # templates.json só existe em runtime — não precisa empacotar
    datas_str = repr(datas)

    spec_content = textwrap.dedent(f"""\
        # -*- mode: python ; coding: utf-8 -*-
        # Gerado automaticamente por build_exe.py

        block_cipher = None

        a = Analysis(
            [r'{ENTRY}'],
            pathex=[r'{BASE}'],
            binaries=[],
            datas={datas_str},
            hiddenimports=[
                # uvicorn
                'uvicorn.logging',
                'uvicorn.loops',
                'uvicorn.loops.auto',
                'uvicorn.loops.asyncio',
                'uvicorn.protocols',
                'uvicorn.protocols.http',
                'uvicorn.protocols.http.auto',
                'uvicorn.protocols.http.h11_impl',
                'uvicorn.protocols.websockets',
                'uvicorn.protocols.websockets.auto',
                'uvicorn.lifespan',
                'uvicorn.lifespan.on',
                # fastapi / starlette
                'fastapi',
                'starlette.routing',
                'starlette.middleware.cors',
                # pydantic
                'pydantic_settings',
                'pydantic_settings.env_settings',
                'pydantic.v1',
                # anyio
                'anyio._backends._asyncio',
                'anyio._backends._trio',
                # httpx
                'httpx',
                'httpcore',
                # imagem / qrcode
                'PIL._tkinter_finder',
                'qrcode',
                'qrcode.image.pil',
                # pystray
                'pystray',
                'pystray._win32',
                # pdv package
                'pdv',
                'pdv.config',
                'pdv.main',
                'pdv.erp_router',
                'pdv.templates',
                'pdv.evolution_local',
                'pdv.zapdin_client',
            ],
            hookspath=[],
            hooksconfig={{}},
            runtime_hooks=[],
            excludes=['matplotlib', 'numpy', 'pandas', 'scipy', 'tkinter'],
            win_no_prefer_redirects=False,
            win_private_assemblies=False,
            cipher=block_cipher,
            noarchive=False,
        )

        pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

        exe = EXE(
            pyz,
            a.scripts,
            [],
            exclude_binaries=True,
            name='ZapDinPDV',
            debug=False,
            bootloader_ignore_signals=False,
            strip=False,
            upx=True,
            console=False,       # sem janela console
            disable_windowed_traceback=False,
            argv_emulation=False,
            target_arch=None,
            codesign_identity=None,
            entitlements_file=None,
            {icon_line}
        )

        coll = COLLECT(
            exe,
            a.binaries,
            a.zipfiles,
            a.datas,
            strip=False,
            upx=True,
            upx_exclude=[],
            name='ZapDinPDV',
        )
    """)

    SPEC.write_text(spec_content, encoding="utf-8")
    print(f"  ✅ Spec gerado: {SPEC.name}")


# ── Build ─────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  ZapDin PDV — Build Windows (PyInstaller)")
    print("=" * 60)

    # Limpa builds anteriores
    for d in (DIST, BUILD):
        if d.exists():
            shutil.rmtree(d)
            print(f"  🗑  Removido: {d.name}/")

    # Cria ícone
    icon_path = _criar_icone()

    # Gera spec
    _gerar_spec(icon_path)

    # Roda PyInstaller
    print("\n  🔧 Rodando PyInstaller…")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", str(SPEC)],
        cwd=str(BASE),
    )

    if result.returncode != 0:
        print("\n❌ Falha no build. Verifique os erros acima.")
        sys.exit(1)

    # Copia arquivos extras para dist
    extras = [
        (".env.example", ".env.example"),
    ]
    for src_name, dst_name in extras:
        src = ROOT / src_name
        if src.exists():
            shutil.copy(src, DIST / dst_name)

    # Cria .env vazio para o wizard detectar primeiro uso
    env_dest = DIST / ".env"
    if not env_dest.exists():
        env_dest.write_text("# Configurado pelo wizard na primeira execução\n")

    print(f"""
{'=' * 60}
  ✅ Build concluído!
  📁 Pasta: {DIST}

  Próximo passo:
    Execute build_evo.bat  →  prepara Evolution API
    Execute setup_pdv.iss  →  gera ZapDinPDV_Setup.exe
{'=' * 60}""")


if __name__ == "__main__":
    main()
