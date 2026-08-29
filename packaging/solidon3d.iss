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
; findet — dann entscheidet er über den Ort, ohne zu fragen. Wer eine Version
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
; Version stehen — SmartScreen zeigt sie im Aufklappen des Hinweises.
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
; Die Namen sind die Kürzel der Anwendung und nicht "german"/"english": So
; steht in ActiveLanguage() genau das, was app/i18n/locales erwartet, und
; zwischen Installer und Anwendung liegt keine Übersetzungstabelle, die beim
; siebten Katalog jemand nachziehen müsste.
Name: "de"; MessagesFile: "compiler:Languages\German.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "it"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "pt"; MessagesFile: "compiler:Languages\Portuguese.isl"

; Wie der Dateityp im Explorer heißt. Eine Zeile je Sprache, und der Name
; kommt auch hier aus app/branding.py. Das Präfix vor dem Punkt MUSS ein
; Name aus [Languages] sein — mit den alten Präfixen (german., english.)
; brach ISCC mit "Unknown language name" ab, seit die Sektion oben die
; Kürzel der Anwendung trägt.
[CustomMessages]
de.ProjectFileType={#AppName}-Projekt
en.ProjectFileType={#AppName} project
es.ProjectFileType=Proyecto de {#AppName}
fr.ProjectFileType=Projet {#AppName}
it.ProjectFileType=Progetto {#AppName}
pt.ProjectFileType=Projeto {#AppName}

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
; Die Dateizuordnung steht **angehakt** da, anders als das Desktop-Symbol: Wer
; ein Programm für Projektdateien installiert, will sie damit öffnen. Abwählbar
; bleibt sie trotzdem — auf einem Rechner mit zwei Versionen nebeneinander ist
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
; Und derselbe Start noch einmal, für den stillen Lauf.
;
; Der Eintrag darüber trägt ``skipifsilent`` und greift bei ``/SILENT`` gerade
; nicht — richtig so, denn dort gibt es keine Schlussseite mit einem Häkchen
; darauf. Ein Update aus der Anwendung heraus ist aber genau dieser Fall: Solidon
; beendet sich, der Installer läuft still, und ohne diese Zeile bliebe der Nutzer
; vor einem geschlossenen Programm und müsste selbst darauf kommen, es zu
; starten. ``updates.SETUP_ARGUMENTS`` übergibt den Schalter.
Filename: "{app}\{#AppName}.exe"; Flags: nowait; Check: WantsRestart

[UninstallDelete]
; install-language.txt schreibt der [Code]-Abschnitt unten selbst — was nicht
; über [Files] kam, steht in keinem Protokoll, und ohne diese Zeile überlebte
; die Datei die Deinstallation und hielt den Programmordner am Leben.
Type: files; Name: "{app}\install-language.txt"

[Code]
function WantsRestart: Boolean;
begin
  (* Ob Solidon nach einem stillen Lauf wieder starten soll.

    ``/RESTARTAPP=1`` ist kein Schalter von Inno Setup, sondern unserer — die
    Anwendung setzt ihn, wenn sie das Update selbst angestoßen hat
    (``app/core/updates.py``, ``SETUP_ARGUMENTS``). Wer die Setup-Datei von Hand
    doppelklickt, setzt ihn nicht und bekommt die gewohnte Schlussseite mit dem
    Häkchen.

    Die Vorgabe hinter dem senkrechten Strich ist der ganze Trick: Ohne sie
    liefert ``{param:...}`` bei einem fehlenden Schalter eine leere
    Zeichenkette, und die verglich sich hier stillschweigend als "nicht
    gewünscht" — dasselbe Ergebnis, aber aus Zufall statt aus Absicht. *)
  Result := ExpandConstant('{param:RESTARTAPP|0}') = '1';
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  { Die Sprachwahl an die Anwendung weitergeben.

    Der Installer fragt sechs Sprachen ab und zeigte sich bis zum 25.08.2026
    als Einziger darin: Die Anwendung startete danach auf Deutsch, gleich was
    gewählt wurde, und fragte in "Erste Schritte" ein zweites Mal. Wer den
    Installer auf Portugiesisch durchgeklickt hat, hat die Frage längst
    beantwortet.

    Eine Zeile neben der Anwendung, kein Registry-Eintrag: Sie gehört zur
    Installation, wird genau einmal gelesen (beim allerersten Start, bevor es
    Einstellungen gibt) und verschwindet mit der Deinstallation. }
  if CurStep = ssPostInstall then
    SaveStringToFile(ExpandConstant('{app}\install-language.txt'), ActiveLanguage(), False);
end;
