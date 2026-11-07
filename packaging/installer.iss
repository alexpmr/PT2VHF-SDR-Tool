; Instalador do PT2VHF SDR Tool (Inno Setup 6)
; iscc /DAppVersion=0.3.0 packaging\installer.iss
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppName "PT2VHF SDR Tool"
#define AppExe "PT2VHF-SDR-Tool.exe"

[Setup]
AppId={{6E0C2B9A-5F3D-4C1E-9A7B-2D8F4E6A1C30}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=PT2VHF
AppPublisherURL=https://www.pt2vhf.com/sdr
AppSupportURL=https://www.pt2vhf.com/contato
AppUpdatesURL=https://www.pt2vhf.com/sdr
DefaultDirName={autopf}\PT2VHF SDR Tool
DefaultGroupName=PT2VHF SDR Tool
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=PT2VHF-SDR-Tool-{#AppVersion}-win-x64-setup
SetupIconFile=pt2vhf.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
PrivilegesRequiredOverridesAllowed=dialog
CloseApplications=yes
RestartApplications=yes
WizardStyle=modern

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\PT2VHF-SDR-Tool\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
