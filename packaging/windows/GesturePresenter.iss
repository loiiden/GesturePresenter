#define AppName "Gesture Presenter"
#define AppVersion "0.1.0"

[Setup]
AppId={{B3685285-704F-46C6-93A1-C81EA1B98156}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={autopf}\Gesture Presenter
DefaultGroupName={#AppName}
OutputDir=..\..\dist
OutputBaseFilename=Gesture-Presenter-Windows-Setup
SetupIconFile=..\..\assets\icon.ico
UninstallDisplayIcon={app}\GesturePresenter.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "..\..\dist\GesturePresenter.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\GesturePresenter.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\GesturePresenter.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{app}\GesturePresenter.exe"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
