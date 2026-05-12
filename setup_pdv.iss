; ============================================================
;  setup_pdv.iss — Inno Setup 6
;  Gera: ZapDinPDV_Setup.exe
;
;  Pré-requisitos (rodar nesta ordem antes de compilar):
;    1. python build_exe.py        → gera dist\ZapDinPDV\
;    2. build_evo.bat              → gera dist\nodejs\ e dist\evo\
;    3. Baixar NSSM em nssm.cc/download → salvar como dist\nssm.exe
;
;  O que o instalador faz:
;    • Copia tudo para C:\ZapDinPDV\
;    • Instala Evolution API como Serviço Windows (ZapDinEvo)
;    • Adiciona ZapDinPDV.exe à inicialização do Windows
;    • Cria atalhos na área de trabalho e menu Iniciar
;    • Abre o wizard de configuração no fim da instalação
; ============================================================

#define AppName      "ZapDin PDV"
#define AppVersion   "1.0.0"
#define AppPublisher "ZapDin"
#define AppURL       "https://zapdin.com.br"
#define AppExeName   "ZapDinPDV.exe"
#define AppInstDir   "ZapDinPDV"

[Setup]
AppId={{E7A3C2F1-4B8D-4E9A-BC12-3D5F6A7E8901}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\{#AppInstDir}
DefaultGroupName={#AppName}
AllowNoIcons=yes
; Compressão máxima
Compression=lzma2/ultra64
SolidCompression=yes
; Requer admin para registrar serviços
PrivilegesRequired=admin
; Saída
OutputDir=dist
OutputBaseFilename=ZapDinPDV_Setup_{#AppVersion}
; Aparência
WizardStyle=modern
WizardSizePercent=120
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\ZapDinPDV.exe
; Mínimo Windows 10
MinVersion=10.0
; Cria uninstaller
Uninstallable=yes
UninstallDisplayName={#AppName}

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked

[Files]
; ── ZapDin PDV (compilado pelo PyInstaller) ────────────────────────────────
Source: "dist\ZapDinPDV\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; ── Node.js portátil ───────────────────────────────────────────────────────
Source: "dist\nodejs\*"; DestDir: "{app}\nodejs"; Flags: ignoreversion recursesubdirs createallsubdirs

; ── Evolution API ──────────────────────────────────────────────────────────
Source: "dist\evo\*"; DestDir: "{app}\evo"; Flags: ignoreversion recursesubdirs createallsubdirs

; ── NSSM (gerenciador de serviços Windows) ────────────────────────────────
Source: "dist\nssm.exe"; DestDir: "{app}"; Flags: ignoreversion

; ── Scripts auxiliares ─────────────────────────────────────────────────────
Source: "iniciar.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: ".env.example"; DestDir: "{app}"; DestName: ".env.example"; Flags: ignoreversion

[Icons]
; Menu Iniciar
Name: "{group}\{#AppName}";          Filename: "{app}\{#AppExeName}"
Name: "{group}\Painel de Templates"; Filename: "{app}\{#AppExeName}"; Parameters: "--open-templates"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"

; Área de trabalho (opcional)
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
; Auto-iniciar junto com o Windows (para o usuário atual)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
      ValueType: string; ValueName: "ZapDinPDV"; \
      ValueData: """{app}\{#AppExeName}"""; Flags: uninsdeletevalue

[Run]
; ── 1. Para e remove serviço antigo (se reinstalando) ─────────────────────
Filename: "{app}\nssm.exe"; Parameters: "stop ZapDinEvo"; \
    Flags: runhidden waituntilterminated; StatusMsg: "Parando serviço anterior..."; \
    Check: IsServiceInstalled

Filename: "{app}\nssm.exe"; Parameters: "remove ZapDinEvo confirm"; \
    Flags: runhidden waituntilterminated; StatusMsg: "Removendo serviço anterior..."; \
    Check: IsServiceInstalled

; ── 2. Instala Evolution API como serviço Windows ─────────────────────────
Filename: "{app}\nssm.exe"; \
    Parameters: "install ZapDinEvo ""{app}\nodejs\node.exe"" ""{app}\evo\dist\main.js"""; \
    Flags: runhidden waituntilterminated; StatusMsg: "Instalando serviço ZapDinEvo..."

Filename: "{app}\nssm.exe"; \
    Parameters: "set ZapDinEvo AppDirectory ""{app}\evo"""; \
    Flags: runhidden waituntilterminated

Filename: "{app}\nssm.exe"; \
    Parameters: "set ZapDinEvo DisplayName ""ZapDin PDV - WhatsApp Local"""; \
    Flags: runhidden waituntilterminated

Filename: "{app}\nssm.exe"; \
    Parameters: "set ZapDinEvo Description ""Evolution API local para ZapDin PDV"""; \
    Flags: runhidden waituntilterminated

Filename: "{app}\nssm.exe"; \
    Parameters: "set ZapDinEvo Start SERVICE_AUTO_START"; \
    Flags: runhidden waituntilterminated

Filename: "{app}\nssm.exe"; \
    Parameters: "set ZapDinEvo AppStdout ""{app}\evo_service.log"""; \
    Flags: runhidden waituntilterminated

Filename: "{app}\nssm.exe"; \
    Parameters: "set ZapDinEvo AppStderr ""{app}\evo_service_err.log"""; \
    Flags: runhidden waituntilterminated

; ── 3. Inicia o serviço Evolution API ─────────────────────────────────────
Filename: "{app}\nssm.exe"; Parameters: "start ZapDinEvo"; \
    Flags: runhidden waituntilterminated; StatusMsg: "Iniciando Evolution API..."

; ── 4. Abre o wizard de configuração ──────────────────────────────────────
Filename: "{app}\{#AppExeName}"; \
    Description: "Abrir ZapDin PDV e configurar"; \
    Flags: postinstall nowait skipifsilent

[UninstallRun]
; Para e remove o serviço ao desinstalar
Filename: "{app}\nssm.exe"; Parameters: "stop ZapDinEvo"; \
    Flags: runhidden waituntilterminated

Filename: "{app}\nssm.exe"; Parameters: "remove ZapDinEvo confirm"; \
    Flags: runhidden waituntilterminated

[Code]
// ── Verifica se o serviço Windows já existe ─────────────────────────────────
function IsServiceInstalled: Boolean;
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{app}\nssm.exe'), 'status ZapDinEvo',
       '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := (ResultCode = 0);
end;

// ── Página de boas-vindas personalizada ─────────────────────────────────────
procedure InitializeWizard;
begin
  WizardForm.WelcomeLabel1.Caption :=
    'Bem-vindo ao ZapDin PDV ' + '{#AppVersion}';
  WizardForm.WelcomeLabel2.Caption :=
    'Este assistente irá instalar o ZapDin PDV na sua máquina.' + #13#10 + #13#10 +
    'O ZapDin PDV permite que o ERP envie mensagens WhatsApp ' +
    'diretamente desta máquina, usando seus próprios recursos.' + #13#10 + #13#10 +
    'O que será instalado:' + #13#10 +
    '  • ZapDin PDV (servidor local na porta 4600)' + #13#10 +
    '  • Evolution API (WhatsApp local na porta 8080)' + #13#10 +
    '  • Node.js portátil (não afeta outros programas)' + #13#10 + #13#10 +
    'Clique em Avançar para continuar.';
end;

// ── Pergunta ao desinstalar ──────────────────────────────────────────────────
function InitializeUninstall(): Boolean;
begin
  Result := MsgBox(
    'Deseja realmente desinstalar o ZapDin PDV?' + #13#10 + #13#10 +
    'O serviço WhatsApp local (Evolution API) também será parado.',
    mbConfirmation, MB_YESNO) = IDYES;
end;
