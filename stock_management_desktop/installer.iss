[Setup]
AppId={{8F6F8D80-B0C2-4A2C-BE57-6A7E53E9F001}
AppName=Stock Management Desktop App
AppVersion=1.0.0
AppPublisher=Shane Idana
DefaultDirName={autopf}\Stock Management Desktop App
DefaultGroupName=Stock Management Desktop App
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=StockManagementAppInstaller
SetupIconFile=assets\app_icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\StockManagementApp.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "dist\StockManagementApp.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Stock Management Desktop App"; Filename: "{app}\StockManagementApp.exe"; IconFilename: "{app}\StockManagementApp.exe"
Name: "{autodesktop}\Stock Management Desktop App"; Filename: "{app}\StockManagementApp.exe"; Tasks: desktopicon; IconFilename: "{app}\StockManagementApp.exe"

[Run]
Filename: "{app}\StockManagementApp.exe"; Description: "Launch Stock Management Desktop App"; Flags: nowait postinstall skipifsilent
