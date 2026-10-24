#ifndef AppSource
  #error AppSource is required
#endif
#ifndef OutputDirectory
  #error OutputDirectory is required
#endif
#ifndef AppVersion
  #define AppVersion "0.2.0"
#endif
#ifndef NumericVersion
  #define NumericVersion "0.2.0.0"
#endif
#ifndef AppName
  #define AppName "Framewise"
#endif
#ifndef ProductGuid
  #define ProductGuid "11A814C4-205B-4EEB-A103-B8DA5D846E87"
#endif
#ifndef PayloadBytes
  #define PayloadBytes "0"
#endif
#ifndef OutputName
  #define OutputName "Framewise-Windows-x64-Setup"
#endif

#ifndef CompressionMethod
  #define CompressionMethod "lzma2/fast"
#endif

[Setup]
AppId={{{#ProductGuid}}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
VersionInfoVersion={#NumericVersion}
VersionInfoProductName={#AppName}
#ifdef OnlineArchiveInclude
VersionInfoDescription={#AppName} verified online installation core
#else
VersionInfoDescription={#AppName} per-user offline installer
#endif
AppComments=Uninstall preserves your Framewise courses, notes, settings and models stored outside this program folder.
DefaultDirName={localappdata}\Programs\Framewise
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=no
UsePreviousAppDir=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline
UsePreviousPrivileges=no
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
SetupArchitecture=x64
MinVersion=10.0.17763
AllowRootDirectory=no
AllowUNCPath=no
AllowNetworkDrive=no
OutputDir={#OutputDirectory}
OutputBaseFilename={#OutputName}
Compression={#CompressionMethod}
SolidCompression=no
CompressionThreads=2
#ifdef OnlineArchiveInclude
DiskSpanning=no
ArchiveExtraction=full
#else
DiskSpanning=yes
DiskSliceSize=1000000000
SlicesPerDisk=1
#endif
ExtraDiskSpaceRequired=536870912
WizardStyle=modern
CloseApplications=no
RestartApplications=no
RestartIfNeededByRun=no
Uninstallable=yes
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\versions\{#AppVersion}\Framewise.exe
SetupLogging=yes
SetupMutex=FramewiseInstaller-{#ProductGuid}
InfoBeforeFile={#UpgradeInfo}

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "zh"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Messages]
en.ConfirmUninstall=Uninstall %1? Your courses, notes, settings and downloaded models in your user data folder will be kept.
zh.ConfirmUninstall=确定卸载 %1？用户数据文件夹中的课程、笔记、设置和已下载模型会保留。

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
#ifdef OnlineArchiveInclude
#include OnlineArchiveInclude
#else
Source: "{#AppSource}\*"; DestDir: "{app}\versions\{#AppVersion}"; Flags: ignoreversion recursesubdirs createallsubdirs
#endif

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\versions\{#AppVersion}\Framewise.exe"; WorkingDir: "{app}\versions\{#AppVersion}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\versions\{#AppVersion}\Framewise.exe"; WorkingDir: "{app}\versions\{#AppVersion}"; Tasks: desktopicon

[INI]
Filename: "{app}\install-state.ini"; Section: "Install"; Key: "CurrentVersion"; String: "{#AppVersion}"; Flags: uninsdeleteentry
Filename: "{app}\install-state.ini"; Section: "Install"; Key: "CurrentExecutable"; String: "{app}\versions\{#AppVersion}\Framewise.exe"; Flags: uninsdeleteentry
Filename: "{app}\install-state.ini"; Section: "Install"; Key: "PreviousVersion"; String: "{code:PreviousVersion}"; Flags: uninsdeleteentry
Filename: "{app}\install-state.ini"; Section: "Install"; Key: "PreviousExecutable"; String: "{code:PreviousExecutable}"; Flags: uninsdeleteentry
Filename: "{app}\install-state.ini"; Section: "Install"; Key: "DataPolicy"; String: "External user data is never removed by this installer. Restore an application backup before running an older schema."; Flags: uninsdeleteentry

[Run]
Filename: "{app}\versions\{#AppVersion}\Framewise.exe"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent unchecked

[Code]
var
  SavedPreviousExecutable: String;
  SavedPreviousVersion: String;

function GetFileAttributesW(lpFileName: String): LongWord;
  external 'GetFileAttributesW@kernel32.dll stdcall';

function ReparseAncestor(Target: String): Boolean;
var
  Attr: LongWord;
  Parent: String;
begin
  Result := False;
  while Length(Target) > 3 do begin
    Attr := GetFileAttributesW(Target);
    if (Attr <> $FFFFFFFF) and ((Attr and $400) <> 0) then begin
      Result := True;
      exit;
    end;
    Parent := ExtractFileDir(Target);
    if Parent = Target then exit;
    Target := Parent;
  end;
end;

function ReparseTree(Target: String): Boolean;
var
  Item: TFindRec;
  Child: String;
begin
  Result := ReparseAncestor(Target);
  if Result then exit;
  if FindFirst(AddBackslash(Target) + '*', Item) then begin
    try
      repeat
        if (Item.Name <> '.') and (Item.Name <> '..') then begin
          Child := AddBackslash(Target) + Item.Name;
          if ((Item.Attributes and $400) <> 0) then begin
            Result := True;
            exit;
          end;
          if ((Item.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0) and ReparseTree(Child) then begin
            Result := True;
            exit;
          end;
        end;
      until not FindNext(Item);
    finally
      FindClose(Item);
    end;
  end;
end;

#ifdef OnlineArchiveInclude
function OnlineCache(Param: String): String;
begin
  Result := ExpandConstant('{param:DOWNLOADCACHE|}');
  if (Length(Result) < 4) or (ExtractFileDrive(Result) = '') or ReparseAncestor(Result) then
    RaiseException('Invalid or linked download cache. Start the Framewise online installer.');
end;
#endif

function PreviousExecutable(Param: String): String;
begin
  Result := SavedPreviousExecutable;
end;

function PreviousVersion(Param: String): String;
begin
  Result := SavedPreviousVersion;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  FreeBytes, TotalBytes, RequiredBytes: Int64;
  StateFile, CurrentVersion: String;
begin
  Result := '';
  if ReparseTree(ExpandConstant('{app}')) then begin
    Result := 'The selected installation folder contains a symbolic link or junction. Choose a normal program folder.';
    exit;
  end;
  RequiredBytes := StrToInt64('{#PayloadBytes}') + 536870912;
  if not GetSpaceOnDisk64(ExtractFileDrive(ExpandConstant('{app}')) + '\', FreeBytes, TotalBytes) then begin
    Result := 'Unable to check available disk space. Choose a local program folder.';
    exit;
  end;
  if FreeBytes < RequiredBytes then begin
    Result := 'Not enough free disk space for this version and its offline runtime. Free space and retry; existing versions and user data will be kept.';
    exit;
  end;
  StateFile := ExpandConstant('{app}\install-state.ini');
  CurrentVersion := GetIniString('Install', 'CurrentVersion', '', StateFile);
  if CurrentVersion = '{#AppVersion}' then begin
    SavedPreviousVersion := GetIniString('Install', 'PreviousVersion', '', StateFile);
    SavedPreviousExecutable := GetIniString('Install', 'PreviousExecutable', '', StateFile);
  end else begin
    SavedPreviousVersion := CurrentVersion;
    SavedPreviousExecutable := GetIniString('Install', 'CurrentExecutable', '', StateFile);
  end;
end;
