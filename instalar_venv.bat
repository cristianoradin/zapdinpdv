@echo off
:: Instala o ambiente virtual e dependências do ZapDin PDV no Windows
echo === ZapDin PDV — Instalação ===
echo.

:: Verifica Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERRO: Python não encontrado. Instale Python 3.11+ em python.org
    pause
    exit /b 1
)

echo Criando ambiente virtual...
python -m venv .venv

echo Instalando dependências...
.venv\Scripts\pip install --upgrade pip
.venv\Scripts\pip install -r requirements.txt

echo.
echo === Instalação concluída! ===
echo.
echo Para configurar:
echo   1. Copie .env.example para .env
echo   2. Edite o .env com as configurações do seu servidor ZapDin
echo   3. Execute: iniciar.bat
echo.
pause
