; Inno Setup script for Pipevoice.
; Build Pipevoice.exe first (run build_exe.bat), then compile this with Inno Setup
; (ISCC.exe installer\Pipevoice.iss, or open in the Inno Setup IDE).
; Produces installer\Output\Pipevoice-Setup.exe — a per-user install (no admin).

#define AppName "Pipevoice"
#define AppVersion "2.1.0"
#define AppExe "Pipevoice.exe"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Pipevoice
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename={#AppName}-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\assets\wisprlite.ico
UninstallDisplayIcon={app}\{#AppExe}

[Files]
Source: "..\dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\.env.example"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
; Seed a real .env on first install only (user pastes their key into it).
Source: "..\.env.example"; DestDir: "{app}"; DestName: ".env"; Flags: onlyifdoesntexist

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Edit API keys (.env)"; Filename: "notepad.exe"; Parameters: """{app}\.env"""
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{userstartup}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: startup

[Tasks]
Name: "startup"; Description: "Start {#AppName} automatically when I log in"; GroupDescription: "Startup:"; Flags: unchecked

[Run]
; The app prompts for the API key on first launch, so just start it.
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{userappdata}\{#AppName}"
