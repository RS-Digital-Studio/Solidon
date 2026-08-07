; Inno-Setup-Skript für den Windows-Installer (Bauplan §37.2).
;
; Baut aus dem PyInstaller-Ordner eine Setup-Datei. Das Skript trägt keine
; eigenen Werte: Name, Version, Hersteller und Kennung liegen in
; app/branding.py fest und kommen als Defines herein —
; tools/make_installer.py liest sie und ruft ISCC auf. Ein fehlendes Define
; ist hier ein Kompilierfehler, kein stiller Rückfall.
;
;     python tools/make_installer.py
;
; Das Anwendungssymbol kommt als Define herein (packaging/solidon.ico,
; erzeugt von tools/make_icon.py aus der SVG-Quelle).

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppVendor}
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}
AppUpdatesURL={#AppUrl}
DefaultDirName={autopf}\{#AppName}
; Eine Programmgruppe mit einem einzigen Eintrag ist eine Frage zu viel (§19.3
; dem Geist nach): der Startmenü-Eintrag entsteht ohne Rückfrage.
DisableProgramGroupPage=yes
LicenseFile={#LicenseFile}
OutputDir={#OutputDir}
OutputBaseFilename={#AppName}-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Ohne Adminrechte ins Nutzerprofil, mit ihnen nach Program Files — die
; Nachfrage überlässt die Wahl dem Nutzer, statt sie zu treffen.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
SetupIconFile={#SetupIconFile}
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppName}.exe

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppName}.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppName}.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppName}.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
