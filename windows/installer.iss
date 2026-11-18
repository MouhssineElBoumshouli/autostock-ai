; Inno Setup recipe for AutoStock-Setup.exe (run by windows/build.ps1).
; Installs for the current Windows user only: no administrator password needed.
; The shop's data (%LOCALAPPDATA%\AutoStock) and backups (Documents\AutoStock backups) are never
; deleted, not even by uninstalling, so a reinstall or an update finds everything again.

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{6B1F2D9E-3C44-4A57-9E61-2A7D5C0B8E14}
AppName=AutoStock AI
AppVersion={#AppVersion}
AppPublisher=AutoStock AI
DefaultDirName={localappdata}\Programs\AutoStock
DefaultGroupName=AutoStock AI
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\build
OutputBaseFilename=AutoStock-Setup
SetupIconFile=autostock.ico
UninstallDisplayIcon={app}\AutoStock.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=no

[Files]
Source: "..\build\dist\AutoStock\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{userdesktop}\AutoStock AI"; Filename: "{app}\AutoStock.exe"
Name: "{group}\AutoStock AI"; Filename: "{app}\AutoStock.exe"
Name: "{group}\Stop AutoStock"; Filename: "{app}\AutoStock.exe"; Parameters: "--stop"
Name: "{group}\AutoStock backups"; Filename: "{userdocs}\AutoStock backups"
; Starts quietly when Windows starts, so the shop's other computers and phones can always reach it.
Name: "{userstartup}\AutoStock AI"; Filename: "{app}\AutoStock.exe"; Parameters: "--background"

[Run]
Filename: "{app}\AutoStock.exe"; Description: "Open AutoStock now"; Flags: postinstall nowait skipifsilent

[InstallDelete]
; An update replaces the program's files completely (never the shop's data, which lives elsewhere).
Type: filesandordirs; Name: "{app}\_internal"

[Code]
procedure StopAutoStock();
var Code: Integer;
begin
  if FileExists(ExpandConstant('{app}\AutoStock.exe')) then
    Exec(ExpandConstant('{app}\AutoStock.exe'), '--stop', '', SW_HIDE, ewWaitUntilTerminated, Code);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopAutoStock();  { an update can only replace files that are not running }
  Result := '';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then StopAutoStock();
end;
