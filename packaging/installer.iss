; Instalador do PT2VHF SDR Tool (Inno Setup 6) — mesmo padrão do PT2VHF Sat Tool.
; iscc /DAppVersion=0.4.0 packaging\installer.iss
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppName "PT2VHF SDR Tool"
#define AppExe "PT2VHF-SDR-Tool.exe"
#define BuildFlavor "Win11-x64"

[Setup]
; Mesmo AppId da 0.3.0: a atualização instala por cima, na mesma pasta.
AppId={{6E0C2B9A-5F3D-4C1E-9A7B-2D8F4E6A1C30}
AppName={#AppName} (Windows 10/11 x64)
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=PT2VHF
AppPublisherURL=https://www.pt2vhf.com/sdr
AppSupportURL=https://www.pt2vhf.com/contato
AppUpdatesURL=https://www.pt2vhf.com/sdr
; Instalação por usuário, sem administrador (como os demais programas PT2VHF);
; quem instalou a 0.3.0 em "Arquivos de Programas" continua lá (privilégios anteriores).
DefaultDirName={localappdata}\Programs\PT2VHF SDR Tool
DefaultGroupName=PT2VHF SDR Tool
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline dialog
UsePreviousPrivileges=yes
OutputDir=..\dist
OutputBaseFilename=PT2VHF-SDR-Tool-v{#AppVersion}-{#BuildFlavor}-Setup
SetupIconFile=pt2vhf.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
WizardStyle=modern
CloseApplications=yes
CloseApplicationsFilter=*.exe,*.dll,*.pyd
RestartApplications=no
AppMutex=PT2VHF_SDR_Tool_Running

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Atalhos adicionais:"
Name: "rtlsdr"; Description: "Preparar RTL-SDR (instala o driver WinUSB somente na interface 0 do dongle)"; GroupDescription: "Receptor SDR:"

[Files]
Source: "..\dist\PT2VHF-SDR-Tool\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\PT2VHF SDR Tool"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\PT2VHF SDR Tool"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\_internal\drivers\wdi-simple.exe"; Parameters: "-n ""RTL2832U (PT2VHF SDR Tool)"" -m Realtek -v 0x0BDA -p 0x2838 -i 0 -t 0 -f rtlsdr_2838_pt2vhf.inf -d ""{tmp}\rtlsdr"" --stealth-cert -s -o 60000"; StatusMsg: "Preparando driver do RTL-SDR (WinUSB)..."; Flags: runhidden waituntilterminated skipifdoesntexist; Tasks: rtlsdr; Check: not WizardSilent
Filename: "{app}\_internal\drivers\wdi-simple.exe"; Parameters: "-n ""RTL2832U (PT2VHF SDR Tool)"" -m Realtek -v 0x0BDA -p 0x2832 -i 0 -t 0 -f rtlsdr_2832_pt2vhf.inf -d ""{tmp}\rtlsdr"" --stealth-cert -s -o 60000"; Flags: runhidden waituntilterminated skipifdoesntexist; Tasks: rtlsdr; Check: not WizardSilent
Filename: "{app}\{#AppExe}"; Description: "Executar PT2VHF SDR Tool"; Flags: nowait postinstall skipifsilent
