@echo off
:: ============================================================
::  build_evo.bat — Prepara os assets do Evolution API para
::  o instalador ZapDin PDV (Windows).
::
::  O que faz:
::    1. Baixa Node.js 20 LTS portátil (zip, sem instalar)
::    2. Baixa Evolution API v2 do GitHub
::    3. Roda npm install --production
::    4. Gera a pasta dist\evo\ pronta para o Inno Setup
::
::  Pré-requisito: acesso à internet nesta máquina (uma vez só)
::  Resultado:     dist\nodejs\   e   dist\evo\
:: ============================================================
setlocal EnableDelayedExpansion

set SCRIPT_DIR=%~dp0
set DIST_DIR=%SCRIPT_DIR%dist
set NODE_DIR=%DIST_DIR%\nodejs
set EVO_DIR=%DIST_DIR%\evo

:: Versões
set NODE_VERSION=20.14.0
set NODE_ZIP=node-v%NODE_VERSION%-win-x64.zip
set NODE_URL=https://nodejs.org/dist/v%NODE_VERSION%/%NODE_ZIP%

set EVO_VERSION=2.1.1
set EVO_ZIP=evolution-api-v%EVO_VERSION%.zip
set EVO_URL=https://github.com/EvolutionAPI/evolution-api/archive/refs/tags/v%EVO_VERSION%.zip

echo.
echo ============================================================
echo   ZapDin PDV - Preparando Evolution API para Windows
echo ============================================================
echo.

:: Garante que dist\ existe
if not exist "%DIST_DIR%" mkdir "%DIST_DIR%"

:: ── 1. Node.js portátil ──────────────────────────────────────────────────────
if exist "%NODE_DIR%\node.exe" (
    echo [OK] Node.js já extraído em dist\nodejs\
) else (
    echo [1/4] Baixando Node.js %NODE_VERSION%...
    if not exist "%DIST_DIR%\%NODE_ZIP%" (
        powershell -Command "Invoke-WebRequest -Uri '%NODE_URL%' -OutFile '%DIST_DIR%\%NODE_ZIP%' -UseBasicParsing"
        if errorlevel 1 ( echo ERRO ao baixar Node.js & pause & exit /b 1 )
    )
    echo [2/4] Extraindo Node.js...
    powershell -Command ^
        "Expand-Archive -Path '%DIST_DIR%\%NODE_ZIP%' -DestinationPath '%DIST_DIR%\nodejs_tmp' -Force"
    :: move a subpasta para nodejs\
    for /d %%d in ("%DIST_DIR%\nodejs_tmp\*") do (
        if not exist "%NODE_DIR%" move "%%d" "%NODE_DIR%"
    )
    rmdir /s /q "%DIST_DIR%\nodejs_tmp" 2>nul
    echo [OK] Node.js extraído.
)

set NODE_EXE=%NODE_DIR%\node.exe
set NPM_CMD=%NODE_DIR%\npm.cmd

:: ── 2. Evolution API ─────────────────────────────────────────────────────────
if exist "%EVO_DIR%\package.json" (
    echo [OK] Evolution API já extraída em dist\evo\
) else (
    echo [3/4] Baixando Evolution API v%EVO_VERSION%...
    if not exist "%DIST_DIR%\%EVO_ZIP%" (
        powershell -Command "Invoke-WebRequest -Uri '%EVO_URL%' -OutFile '%DIST_DIR%\%EVO_ZIP%' -UseBasicParsing"
        if errorlevel 1 ( echo ERRO ao baixar Evolution API & pause & exit /b 1 )
    )
    echo        Extraindo...
    powershell -Command ^
        "Expand-Archive -Path '%DIST_DIR%\%EVO_ZIP%' -DestinationPath '%DIST_DIR%\evo_tmp' -Force"
    :: move a subpasta para evo\
    for /d %%d in ("%DIST_DIR%\evo_tmp\*") do (
        if not exist "%EVO_DIR%" move "%%d" "%EVO_DIR%"
    )
    rmdir /s /q "%DIST_DIR%\evo_tmp" 2>nul
    echo [OK] Evolution API extraída.
)

:: ── 3. npm install --production ──────────────────────────────────────────────
if exist "%EVO_DIR%\node_modules" (
    echo [OK] node_modules já instalados.
) else (
    echo [4/4] Instalando dependências ^(npm install --production^)...
    cd /d "%EVO_DIR%"
    call "%NPM_CMD%" install --production --no-audit --no-fund
    if errorlevel 1 ( echo ERRO no npm install & pause & exit /b 1 )
    echo [OK] Dependências instaladas.
)

:: ── 4. Gera .env padrão para o Evolution API ─────────────────────────────────
if not exist "%EVO_DIR%\.env" (
    echo Gerando .env padrão do Evolution API...
    (
        echo # Evolution API — Gerado pelo ZapDin PDV Installer
        echo SERVER_TYPE=http
        echo SERVER_PORT=8080
        echo SERVER_URL=http://localhost
        echo CORS_ORIGIN=*
        echo CORS_METHODS=GET,POST,PUT,DELETE
        echo CORS_CREDENTIALS=true
        echo.
        echo LOG_LEVEL=ERROR
        echo LOG_COLOR=true
        echo LOG_BAILEYS=error
        echo.
        echo DEL_INSTANCE=false
        echo.
        echo # Banco de dados local (SQLite via Prisma)
        echo DATABASE_PROVIDER=sqlite
        echo DATABASE_CONNECTION_URI=file:./dev.db
        echo DATABASE_CONNECTION_CLIENT_NAME=evolution_api
        echo DATABASE_SAVE_DATA_INSTANCE=true
        echo DATABASE_SAVE_DATA_NEW_MESSAGE=true
        echo DATABASE_SAVE_MESSAGE_UPDATE=true
        echo DATABASE_SAVE_DATA_CONTACTS=true
        echo DATABASE_SAVE_DATA_CHATS=true
        echo.
        echo AUTHENTICATION_TYPE=apikey
        echo AUTHENTICATION_API_KEY=zapdin-pdv-local
        echo AUTHENTICATION_EXPOSE_IN_FETCH_INSTANCES=true
        echo.
        echo QRCODE_LIMIT=30
        echo QRCODE_COLOR=#3d7f1f
    ) > "%EVO_DIR%\.env"
    echo [OK] .env do Evolution API criado.
)

:: ── Resultado ────────────────────────────────────────────────────────────────
echo.
echo ============================================================
echo   Assets prontos!
echo   dist\nodejs\   — Node.js %NODE_VERSION% portátil
echo   dist\evo\      — Evolution API v%EVO_VERSION%
echo.
echo   Proximo passo: compile o Inno Setup (setup_pdv.iss)
echo   para gerar ZapDinPDV_Setup.exe
echo ============================================================
echo.
pause
