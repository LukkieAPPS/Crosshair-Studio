#define MyAppName "Crosshair Studio"
#define MyAppVersion "1.0.1"
#define MyAppPublisher "Crosshair Studio"
#define MyAppExeName "CrosshairStudio.exe"

[Setup]
AppId={{B7D9E9A8-4C2A-4E89-9D51-4E6E98B31A10}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Crosshair Studio
DefaultGroupName=Crosshair Studio
OutputDir=installer_output
OutputBaseFilename=CrosshairStudio_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "dist\CrosshairStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Crosshair Studio"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Crosshair Studio"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Crosshair Studio"; Flags: postinstall nowait skipifsilent
