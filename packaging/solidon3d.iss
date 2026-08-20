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
; Das Anwendungssymbol kommt als Define herein (packaging/solidon3d.ico,
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
; **Die Verzeichnisseite wird immer gezeigt.** Die Vorgabe (``auto``) versteckt
; sie, sobald der Installer eine frühere Installation in der Registrierung
; findet — dann entscheidet er über den Ort, ohne zu fragen. Wer eine Fassung
; auf eine andere Platte legen will, weil die Systemplatte voll ist, käme dort
; nicht mehr heran. Vorbelegt bleibt der alte Pfad; es ist eine Seite mehr, und
; sie hat einen Knopf „Weiter".
DisableDirPage=no
; Windows 10 oder neuer — so steht es auf der Download-Seite. Ohne die Zeile
; installiert sich das Paket auch auf Windows 7 und scheitert erst beim Start
; an einer fehlenden Systembibliothek, und dann sucht der Nutzer den Fehler bei
; sich.
MinVersion=10.0
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
; Was die Dateieigenschaften der Setup-Datei zeigen. Bei einem unsignierten
; Paket ist das die einzige Stelle, an der vor dem Ausführen Hersteller und
; Fassung stehen — SmartScreen zeigt sie im Aufklappen des Hinweises.
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppVendor}
VersionInfoProductName={#AppName}
VersionInfoDescription={#AppName} Setup
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppName}.exe

; Sechs Sprachen, dieselben wie in app/i18n/locales — wer die Anwendung auf
; Portugiesisch benutzt, soll sie nicht auf Englisch installieren müssen. Alle
; fünf Kataloge liefert Inno Setup 6 selbst mit; Default.isl ist Englisch.
[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "portuguese"; MessagesFile: "compiler:Languages\Portuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppName}.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppName}.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppName}.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
