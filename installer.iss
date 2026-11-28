; Установщик Новы (Inno Setup). Собирается автоматически в GitHub Actions, руками ничего делать не нужно.
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{B5C1D0E2-7F4A-4C3B-9E21-6A8D5F0C1E77}
AppName=Nova
AppVersion={#AppVersion}
AppPublisher=fundreamer365
AppPublisherURL=https://github.com/fundreamer365/Nova
; Ставим в папку пользователя: права администратора не нужны, а самообновление Новы может заменять файл
DefaultDirName={localappdata}\Programs\Nova
DefaultGroupName=Nova
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=Nova-Setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\Nova.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
AppMutex=NovaAssistant_fundreamer365
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\Nova.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Nova"; Filename: "{app}\Nova.exe"
Name: "{autodesktop}\Nova"; Filename: "{app}\Nova.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Nova.exe"; Description: "{cm:LaunchProgram,Nova}"; Flags: nowait postinstall skipifsilent
