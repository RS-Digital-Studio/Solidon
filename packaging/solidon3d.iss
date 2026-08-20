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

; Wie der Dateityp im Explorer heißt. Eine Zeile je Sprache, und der Name
; kommt auch hier aus app/branding.py.
[CustomMessages]
german.ProjectFileType={#AppName}-Projekt
english.ProjectFileType={#AppName} project
spanish.ProjectFileType=Proyecto de {#AppName}
french.ProjectFileType=Projet {#AppName}
italian.ProjectFileType=Progetto {#AppName}
portuguese.ProjectFileType=Projeto {#AppName}

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
; Die Dateizuordnung steht **angehakt** da, anders als das Desktop-Symbol: Wer
; ein Programm für Projektdateien installiert, will sie damit öffnen. Abwählbar
; bleibt sie trotzdem — auf einem Rechner mit zwei Fassungen nebeneinander ist
; genau das die Frage, die zählt.
Name: "associate"; Description: "{cm:AssocFileExtension,{#AppName},{#ProjectSuffix}}"

; Die Zuordnung von {#ProjectSuffix}. Sie hängt an der Aufgabe darüber und
; verschwindet mit der Deinstallation wieder — ``uninsdeletekey`` auf dem
; eigenen Schlüssel, ``uninsdeletevalue`` auf dem fremden unter der Endung, wo
; andere Programme ihre eigenen Einträge haben.
;
; HKA ist HKLM bei einer Installation für alle und HKCU bei einer fürs eigene
; Profil — dieselbe Wahl, die der Nutzer oben schon getroffen hat.
[Registry]
Root: HKA; Subkey: "Software\Classes\{#ProjectSuffix}\OpenWithProgids";   ValueType: string; ValueName: "{#AppId}.project"; ValueData: "";   Flags: uninsdeletevalue; Tasks: associate
Root: HKA; Subkey: "Software\Classes\{#AppId}.project";   ValueType: string; ValueName: ""; ValueData: "{cm:ProjectFileType}";   Flags: uninsdeletekey; Tasks: associate
Root: HKA; Subkey: "Software\Classes\{#AppId}.project\DefaultIcon";   ValueType: string; ValueName: ""; ValueData: "{app}\{#AppName}.exe,0"; Tasks: associate
Root: HKA; Subkey: "Software\Classes\{#AppId}.project\shell\open\command";   ValueType: string; ValueName: ""; ValueData: """{app}\{#AppName}.exe"" ""%1""";   Tasks: associate
; Damit die Anwendung auch im Dialog „Öffnen mit" steht, wenn die Zuordnung
; abgewählt wurde oder ein anderes Programm sie später übernimmt.
Root: HKA; Subkey: "Software\Classes\Applications\{#AppName}.exe\shell\open\command";   ValueType: string; ValueName: ""; ValueData: """{app}\{#AppName}.exe"" ""%1""";   Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\{#AppName}.exe\SupportedTypes";   ValueType: string; ValueName: "{#ProjectSuffix}"; ValueData: ""

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppName}.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppName}.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppName}.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
