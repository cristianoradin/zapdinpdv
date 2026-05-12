@echo off
:: ============================================================
::  iniciar.bat — Inicia o ZapDin PDV manualmente
::
::  Uso normal:    duplo-clique para iniciar
::  Uso modo dev:  .venv\Scripts\python launcher.py
:: ============================================================
cd /d "%~dp0"
title ZapDin PDV

:: ── Modo executável (instalado via Setup) ──────────────────
if exist "ZapDinPDV.exe" (
    echo Iniciando ZapDin PDV...
    start "" "ZapDinPDV.exe"
    timeout /t 3 >nul
    start "" http://localhost:4600/status
    exit /b 0
)

:: ── Modo desenvolvimento (Python + venv) ───────────────────
if not exist ".env" (
    echo AVISO: .env nao encontrado. O wizard sera aberto.
)

if not exist ".venv\Scripts\python.exe" (
    echo Ambiente virtual nao encontrado. Instalando...
    call instalar_venv.bat
)

echo Iniciando ZapDin PDV ^(modo desenvolvimento^)...
.venv\Scripts\python launcher.py
pause
