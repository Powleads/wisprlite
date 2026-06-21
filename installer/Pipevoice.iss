; Inno Setup script for Pipevoice.
; Build Pipevoice.exe first (run build_exe.bat), then compile this with Inno Setup
; (ISCC.exe installer\Pipevoice.iss, or open in the Inno Setup IDE).
; Produces installer\Output\Pipevoice-Setup.exe — a per-user install (no admin).

#define AppName "Pipevoice"
#define AppVersion "2.23.0"
#define AppExe "Pipevoice.exe"

[Setup]
AppId={{41C3C77C-2125-40AF-AE40-5AAC67809491}
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
CloseApplications=yes
RestartApplications=yes
SetupIconFile=..\assets\wisprlite.ico
UninstallDisplayIcon={app}\{#AppExe}

[Files]
; onedir build: bundle the whole PyInstaller folder (exe + _internal/ DLLs).
; This avoids the onefile _MEI runtime extraction that broke updates with
; "Failed to load Python DLL".
Source: "..\dist\Pipevoice\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
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
; Interactive install: optional "Launch Pipevoice" checkbox on the final page.
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
; Silent self-update (/VERYSILENT from the in-app updater): relaunch the app
; ourselves. Restart Manager's RESTARTAPPLICATIONS is unreliable after a forced
; close, and the postinstall entry above is skipped when silent, so without this
; the update could finish with no app running. The single-instance lock makes any
; overlap with RESTARTAPPLICATIONS safe (the second launch just exits).
Filename: "{app}\{#AppExe}"; Flags: nowait; Check: WizardSilent

[UninstallDelete]
Type: filesandordirs; Name: "{userappdata}\{#AppName}"
