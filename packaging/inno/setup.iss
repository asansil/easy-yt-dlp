; Inno Setup script for Easy yt-dlp. Build with packaging\build.ps1, or:
;   ISCC.exe /DAppVersion=2.0.0 /DAppNumericVersion=2.0.0.0 packaging\inno\setup.iss
; Expects the PyInstaller output in dist\EasyYtDlp.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef AppNumericVersion
  #define AppNumericVersion "0.0.0.0"
#endif

#define AppName "Easy yt-dlp"
#define AppExeName "EasyYtDlp.exe"
#define RepoUrl "https://github.com/asansil/easy-yt-dlp"
; Tools folder managed by the app; must match core/paths.py.
#define ToolsDir "{localappdata}\EasyYtDlp\bin"

[Setup]
; Never change the AppId: upgrades and the uninstaller depend on it.
AppId={{5BEE2B42-3B29-4957-9193-056DF2C789F4}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Easy yt-dlp
AppPublisherURL={#RepoUrl}
AppSupportURL={#RepoUrl}/issues
AppUpdatesURL={#RepoUrl}/releases
VersionInfoVersion={#AppNumericVersion}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=
DefaultDirName={localappdata}\Programs\{#AppName}
DisableDirPage=yes
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}
LicenseFile=..\..\LICENSE
SetupIconFile=..\..\assets\updater_installer.ico
OutputDir=..\..\dist
OutputBaseFilename=EasyYtDlp-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
ChangesEnvironment=yes
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[CustomMessages]
english.AddToPath=Add yt-dlp and FFmpeg to the PATH (use them from any terminal)
spanish.AddToPath=Añadir yt-dlp y FFmpeg al PATH (usarlos desde cualquier terminal)
english.RemoveData=Do you also want to remove your settings, history and the downloaded tools (yt-dlp, FFmpeg, deno)?%n%nYour downloaded videos are never removed.
spanish.RemoveData=¿Quieres eliminar también tu configuración, el historial y las herramientas descargadas (yt-dlp, FFmpeg, deno)?%n%nLos vídeos descargados nunca se eliminan.

[Tasks]
Name: "addtopath"; Description: "{cm:AddToPath}"
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\..\dist\EasyYtDlp\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion

[InstallDelete]
; Remove files of the previous version before copying the new ones.
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
; The in-app updater runs the Setup with /VERYSILENT /RELAUNCH=1 and exits; start it again.
Filename: "{app}\{#AppExeName}"; Flags: nowait; Check: ShouldRelaunch

[Code]
const
  EnvKey = 'Environment';

function ShouldRelaunch(): Boolean;
begin
  Result := WizardSilent() and (ExpandConstant('{param:RELAUNCH|0}') = '1');
end;

function NormalizeEntry(Value: String): String;
begin
  Result := Lowercase(Trim(Value));
  StringChangeEx(Result, '"', '', True);
  while (Length(Result) > 0) and (Result[Length(Result)] = '\') do
    Delete(Result, Length(Result), 1);
end;

{ Rebuild a PATH value without Entry (compared case-insensitively). }
function RemoveEntry(PathValue, Entry: String; var Found: Boolean): String;
var
  Rest, Part: String;
  P: Integer;
begin
  Result := '';
  Found := False;
  Rest := PathValue;
  while Length(Rest) > 0 do
  begin
    P := Pos(';', Rest);
    if P = 0 then
    begin
      Part := Rest;
      Rest := '';
    end
    else
    begin
      Part := Copy(Rest, 1, P - 1);
      Delete(Rest, 1, P);
    end;
    if Trim(Part) = '' then
      Continue;
    if NormalizeEntry(Part) = NormalizeEntry(Entry) then
      Found := True
    else if Result = '' then
      Result := Part
    else
      Result := Result + ';' + Part;
  end;
end;

procedure AddToUserPath(Entry: String);
var
  Current, Cleaned: String;
  Found: Boolean;
begin
  if not RegQueryStringValue(HKCU, EnvKey, 'Path', Current) then
    Current := '';
  Cleaned := RemoveEntry(Current, Entry, Found);
  if Found then
    Exit;
  if Cleaned = '' then
    Cleaned := Entry
  else
    Cleaned := Cleaned + ';' + Entry;
  RegWriteExpandStringValue(HKCU, EnvKey, 'Path', Cleaned);
end;

procedure RemoveFromUserPath(Entry: String);
var
  Current, Cleaned: String;
  Found: Boolean;
begin
  if not RegQueryStringValue(HKCU, EnvKey, 'Path', Current) then
    Exit;
  Cleaned := RemoveEntry(Current, Entry, Found);
  if Found then
    RegWriteExpandStringValue(HKCU, EnvKey, 'Path', Cleaned);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if WizardIsTaskSelected('addtopath') then
      AddToUserPath(ExpandConstant('{#ToolsDir}'))
    else
      RemoveFromUserPath(ExpandConstant('{#ToolsDir}'));
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    RemoveFromUserPath(ExpandConstant('{#ToolsDir}'));
  if CurUninstallStep = usPostUninstall then
  begin
    { A silent uninstall keeps user data and tools. }
    if (not UninstallSilent()) and
       (MsgBox(CustomMessage('RemoveData'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES) then
    begin
      DelTree(ExpandConstant('{userappdata}\EasyYtDlp'), True, True, True);
      DelTree(ExpandConstant('{localappdata}\EasyYtDlp'), True, True, True);
    end;
  end;
end;
