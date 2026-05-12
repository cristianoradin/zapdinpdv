@echo off
:: ============================================================
::  INSTALAR_PDV.bat — Instalador completo ZapDin PDV
::
::  Execute como ADMINISTRADOR.
::  Faz tudo sozinho:
::    1. Baixa Python portátil (se necessário)
::    2. Instala dependências do PDV
::    3. Baixa Node.js portátil
::    4. Baixa e configura Evolution API
::    5. Registra Evolution API como Serviço Windows
::    6. Cria atalhos na área de trabalho
::    7. Abre wizard de configuração
:: ============================================================
setlocal EnableDelayedExpansion

:: ── Verificar se é Admin ─────────────────────────────────────────────────────
net session >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [ERRO] Execute este arquivo como ADMINISTRADOR.
    echo  Clique com o botao direito ^> "Executar como administrador"
    echo.
    pause
    exit /b 1
)

:: ── Configuração ─────────────────────────────────────────────────────────────
set INSTALL_DIR=C:\ZapDinPDV
set NODE_VERSION=20.14.0
set NODE_ZIP=node-v%NODE_VERSION%-win-x64.zip
set NODE_URL=https://nodejs.org/dist/v%NODE_VERSION%/%NODE_ZIP%
set EVO_VERSION=2.1.1
set EVO_ZIP=evo-v%EVO_VERSION%.zip
set EVO_URL=https://github.com/EvolutionAPI/evolution-api/archive/refs/tags/v%EVO_VERSION%.zip
set NSSM_URL=https://nssm.cc/ci/nssm-2.24-101-g897c7ad.zip
set PYTHON_URL=https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip
set PIP_URL=https://bootstrap.pypa.io/get-pip.py

set NODE_DIR=%INSTALL_DIR%\nodejs
set EVO_DIR=%INSTALL_DIR%\evo
set PY_DIR=%INSTALL_DIR%\python
set PDV_DIR=%INSTALL_DIR%\pdv
set NSSM=%INSTALL_DIR%\nssm.exe

title ZapDin PDV — Instalador

cls
echo.
echo  ============================================================
echo   %%  ZapDin PDV — Instalador v1.0
echo  ============================================================
echo.
echo   Pasta de instalacao: %INSTALL_DIR%
echo.
echo   Pressione qualquer tecla para iniciar...
pause >nul

:: ── Criar estrutura de pastas ────────────────────────────────────────────────
echo.
echo  [1/8] Criando estrutura...
if not exist "%INSTALL_DIR%"     mkdir "%INSTALL_DIR%"
if not exist "%INSTALL_DIR%\tmp" mkdir "%INSTALL_DIR%\tmp"

:: ── Copiar arquivos do PDV ───────────────────────────────────────────────────
echo  [2/8] Copiando arquivos do ZapDin PDV...
set SRC_DIR=%~dp0

:: Copia todos os arquivos .py e de configuração
for %%f in (
    config.py
    evolution_local.py
    erp_router.py
    main.py
    templates.py
    zapdin_client.py
    __init__.py
    requirements.txt
    launcher.py
    .env.example
) do (
    if exist "%SRC_DIR%%%f" (
        if not exist "%PDV_DIR%" mkdir "%PDV_DIR%"
        copy /y "%SRC_DIR%%%f" "%PDV_DIR%\%%f" >nul
    )
)

:: ── Python portátil ──────────────────────────────────────────────────────────
echo  [3/8] Verificando Python...

:: Tenta usar Python já instalado primeiro
python --version >nul 2>&1
if not errorlevel 1 (
    set PY_EXE=python
    echo         Python do sistema encontrado. OK.
    goto :python_ok
)

:: Python embutido
if exist "%PY_DIR%\python.exe" (
    set PY_EXE=%PY_DIR%\python.exe
    echo         Python portátil já instalado. OK.
    goto :python_ok
)

echo         Baixando Python portátil...
powershell -Command "Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%INSTALL_DIR%\tmp\python.zip' -UseBasicParsing"
powershell -Command "Expand-Archive -Path '%INSTALL_DIR%\tmp\python.zip' -DestinationPath '%PY_DIR%' -Force"

:: Habilita imports no Python embed (remove comentário do ._pth)
for %%f in ("%PY_DIR%\python*._pth") do (
    powershell -Command "(Get-Content '%%f') -replace '#import site','import site' | Set-Content '%%f'"
)

:: Instala pip
powershell -Command "Invoke-WebRequest -Uri '%PIP_URL%' -OutFile '%PY_DIR%\get-pip.py' -UseBasicParsing"
"%PY_DIR%\python.exe" "%PY_DIR%\get-pip.py" --no-warn-script-location >nul 2>&1

set PY_EXE=%PY_DIR%\python.exe
echo         Python portátil instalado. OK.

:python_ok

:: ── Criar venv e instalar dependências ──────────────────────────────────────
echo  [4/8] Instalando dependências do PDV...

if not exist "%INSTALL_DIR%\.venv\Scripts\python.exe" (
    %PY_EXE% -m venv "%INSTALL_DIR%\.venv"
)
"%INSTALL_DIR%\.venv\Scripts\pip" install --upgrade pip --quiet
"%INSTALL_DIR%\.venv\Scripts\pip" install -r "%PDV_DIR%\requirements.txt" --quiet
if errorlevel 1 (
    echo  [ERRO] Falha ao instalar dependências Python.
    pause & exit /b 1
)
echo         Dependências instaladas. OK.

:: ── Node.js portátil ─────────────────────────────────────────────────────────
echo  [5/8] Verificando Node.js...
if exist "%NODE_DIR%\node.exe" (
    echo         Node.js já instalado. OK.
    goto :node_ok
)
echo         Baixando Node.js %NODE_VERSION%...
powershell -Command "Invoke-WebRequest -Uri '%NODE_URL%' -OutFile '%INSTALL_DIR%\tmp\%NODE_ZIP%' -UseBasicParsing"
if errorlevel 1 ( echo  [ERRO] Falha ao baixar Node.js. & pause & exit /b 1 )
powershell -Command "Expand-Archive -Path '%INSTALL_DIR%\tmp\%NODE_ZIP%' -DestinationPath '%INSTALL_DIR%\tmp\node_tmp' -Force"
for /d %%d in ("%INSTALL_DIR%\tmp\node_tmp\*") do (
    if not exist "%NODE_DIR%" move "%%d" "%NODE_DIR%"
)
echo         Node.js instalado. OK.
:node_ok

:: ── Evolution API ─────────────────────────────────────────────────────────────
echo  [6/8] Verificando Evolution API...
if exist "%EVO_DIR%\package.json" (
    echo         Evolution API já instalada. OK.
    goto :evo_installed
)
echo         Baixando Evolution API v%EVO_VERSION%...
powershell -Command "Invoke-WebRequest -Uri '%EVO_URL%' -OutFile '%INSTALL_DIR%\tmp\%EVO_ZIP%' -UseBasicParsing"
if errorlevel 1 ( echo  [ERRO] Falha ao baixar Evolution API. & pause & exit /b 1 )
powershell -Command "Expand-Archive -Path '%INSTALL_DIR%\tmp\%EVO_ZIP%' -DestinationPath '%INSTALL_DIR%\tmp\evo_tmp' -Force"
for /d %%d in ("%INSTALL_DIR%\tmp\evo_tmp\*") do (
    if not exist "%EVO_DIR%" move "%%d" "%EVO_DIR%"
)

echo         Instalando dependências do Node...
cd /d "%EVO_DIR%"
"%NODE_DIR%\npm.cmd" install --production --no-audit --no-fund
if errorlevel 1 ( echo  [ERRO] Falha no npm install. & pause & exit /b 1 )
echo         Evolution API instalada. OK.
:evo_installed

:: Gera .env do Evolution API se não existir
if not exist "%EVO_DIR%\.env" (
    (
        echo SERVER_TYPE=http
        echo SERVER_PORT=8080
        echo SERVER_URL=http://localhost
        echo CORS_ORIGIN=*
        echo CORS_METHODS=GET,POST,PUT,DELETE
        echo CORS_CREDENTIALS=true
        echo LOG_LEVEL=ERROR
        echo LOG_COLOR=false
        echo LOG_BAILEYS=error
        echo DEL_INSTANCE=false
        echo DATABASE_PROVIDER=sqlite
        echo DATABASE_CONNECTION_URI=file:./dev.db
        echo DATABASE_CONNECTION_CLIENT_NAME=evolution_api
        echo DATABASE_SAVE_DATA_INSTANCE=true
        echo DATABASE_SAVE_DATA_NEW_MESSAGE=true
        echo DATABASE_SAVE_MESSAGE_UPDATE=true
        echo DATABASE_SAVE_DATA_CONTACTS=true
        echo DATABASE_SAVE_DATA_CHATS=true
        echo AUTHENTICATION_TYPE=apikey
        echo AUTHENTICATION_API_KEY=zapdin-pdv-local
        echo AUTHENTICATION_EXPOSE_IN_FETCH_INSTANCES=true
        echo QRCODE_LIMIT=30
    ) > "%EVO_DIR%\.env"
)

:: ── NSSM — Gerenciador de serviços ──────────────────────────────────────────
echo  [7/8] Configurando serviços Windows...
if not exist "%NSSM%" (
    echo         Baixando NSSM...
    powershell -Command "Invoke-WebRequest -Uri '%NSSM_URL%' -OutFile '%INSTALL_DIR%\tmp\nssm.zip' -UseBasicParsing"
    powershell -Command "Expand-Archive -Path '%INSTALL_DIR%\tmp\nssm.zip' -DestinationPath '%INSTALL_DIR%\tmp\nssm_tmp' -Force"
    for /r "%INSTALL_DIR%\tmp\nssm_tmp" %%f in (nssm.exe) do (
        copy /y "%%f" "%NSSM%" >nul
    )
)

:: Para serviço antigo se existir
"%NSSM%" stop ZapDinEvo >nul 2>&1
"%NSSM%" remove ZapDinEvo confirm >nul 2>&1

:: Registra Evolution API como serviço
"%NSSM%" install ZapDinEvo "%NODE_DIR%\node.exe" "%EVO_DIR%\dist\main.js"
"%NSSM%" set ZapDinEvo AppDirectory "%EVO_DIR%"
"%NSSM%" set ZapDinEvo DisplayName "ZapDin PDV - WhatsApp Local"
"%NSSM%" set ZapDinEvo Description "Evolution API local para o ZapDin PDV"
"%NSSM%" set ZapDinEvo Start SERVICE_AUTO_START
"%NSSM%" set ZapDinEvo AppStdout "%INSTALL_DIR%\evo.log"
"%NSSM%" set ZapDinEvo AppStderr "%INSTALL_DIR%\evo_err.log"
"%NSSM%" start ZapDinEvo
echo         Serviço ZapDinEvo instalado e iniciado. OK.

:: ── Atalhos e inicialização automática ──────────────────────────────────────
echo  [8/8] Criando atalhos...

:: Cria o script de inicialização do PDV
(
    echo @echo off
    echo cd /d "%INSTALL_DIR%"
    echo start "" /b "%INSTALL_DIR%\.venv\Scripts\pythonw.exe" "%INSTALL_DIR%\run_pdv.py"
) > "%INSTALL_DIR%\ZapDinPDV.bat"

:: Cria o run_pdv.py (entry-point)
(
    echo import sys, os
    echo sys.path.insert^(0, r'%INSTALL_DIR%'^)
    echo os.chdir^(r'%INSTALL_DIR%'^)
    echo exec^(open^(r'%PDV_DIR%\launcher.py'^).read^(^)^)
) > "%INSTALL_DIR%\run_pdv.py"

:: Atalho na área de trabalho
powershell -Command ^
    "$s=(New-Object -COM WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\ZapDin PDV.lnk'); $s.TargetPath='%INSTALL_DIR%\ZapDinPDV.bat'; $s.WorkingDirectory='%INSTALL_DIR%'; $s.Description='ZapDin PDV'; $s.Save()"

:: Inicialização automática com o Windows (todos os usuários)
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" ^
    /v "ZapDinPDV" ^
    /t REG_SZ ^
    /d "\"%INSTALL_DIR%\ZapDinPDV.bat\"" ^
    /f >nul

:: Limpa temporários
rd /s /q "%INSTALL_DIR%\tmp" 2>nul

:: ── Concluído ────────────────────────────────────────────────────────────────
cls
echo.
echo  ============================================================
echo   %%  ZapDin PDV instalado com sucesso!
echo  ============================================================
echo.
echo   Pasta: %INSTALL_DIR%
echo.
echo   Servicos instalados:
echo     ZapDinEvo  (Evolution API - porta 8080^)  [Automatico]
echo     ZapDinPDV  (PDV Python    - porta 4600^)  [Inicializ. Windows]
echo.
echo   Abrindo configuração inicial...
echo.
pause

:: Inicia o PDV — o wizard vai abrir automaticamente
start "" "%INSTALL_DIR%\ZapDinPDV.bat"
