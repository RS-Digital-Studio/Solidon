# Signierung — Windows, macOS, Linux

Was ein Kunde beim Herunterladen und Starten sieht, hängt an
drei verschiedenen Mechanismen: SmartScreen unter Windows, Gatekeeper unter
macOS, und unter Linux an nichts. Die CI (`.github/workflows/build.yml`)
signiert macOS selbst, sobald Konto und Geheimnisse da sind; Windows baut sie
und übergibt es zur lokalen Signatur mit `tools/sign_release.py`. **Ab 0.5.0
wird Windows nur signiert veröffentlicht.** Anwendung und Installer werden
in der CI gebaut; lokal erfolgen die Certum-Signaturen. Diese Datei
sagt, welcher Weg je Plattform der günstigste sichere ist, was er kostet, was
dafür zu tun ist und wer dann wo baut.

**Die Entscheidung in einem Absatz:** Windows über ein Certum-Standard-Zertifikat
auf Roberts Namen, in der Cloud, lokal signiert aus der Signierübergabe der CI.
macOS über das Apple Developer Program als Einzelperson, vollständig in der CI
signiert und notarisiert. Linux bleibt unsigniert; dort tragen Prüfsummen und die
signierte Versionsdatei. Zusammen rund 240 Dollar im Jahr, einmalig zwei Wochen
Prüfzeit. Weder Gewerbeanmeldung noch Steuernummer sind dafür nötig. Azure
Artifact Signing und der PFX-Weg sind aus der CI entfernt (Entscheidung
Robert, 02.09.2026): Azure verlangt drei Jahre nachweisbare Steuerhistorie
einer Organisation, und exportierbare PFX-Schlüssel geben die
Zertifizierungsstellen seit 2023 nicht mehr heraus.

---

## Windows — Certum Standard Code Signing für eine Einzelperson

### Zertifikat und lokale Anmeldung

Das ausgestellte Zertifikat gehört **Robert Schneider**. Sein SHA-1-
Fingerabdruck zur eindeutigen Auswahl lautet:

```
235C54FC71D79BD03449DBC62FFB14D0AC58AEB3
```

Gültigkeit: 23.09.2026 bis 26.12.2027. Die öffentliche DER-Kopie liegt auf
Roberts Rechner unter
`%USERPROFILE%\OneDrive\477e7c0243c8df3da3a667dd8968351d.cer`.
Sie enthält keinen privaten Schlüssel. Dieser bleibt bei Certum; eine
manuelle Installation der `.cer` ersetzt die SimplySign-Anmeldung nicht.

Auf dem Handy SimplySign über Certums Aktivierungsmails einrichten. Auf dem
Windows-PC SimplySign Desktop mit `abrechnung@solidon3d.de` und einem
Einmalcode aus der Handy-App verbinden. Einmalcodes, Aktivierungsgeheimnis
und QR-Code werden weder im Repository noch in GitHub hinterlegt.

Der Vorabcheck liest nur Werkzeuge und Zertifikatsmetadaten; er lädt kein
Artefakt herunter und signiert nichts:

```powershell
.venv\Scripts\python.exe tools/sign_release.py --check --thumbprint 235C54FC71D79BD03449DBC62FFB14D0AC58AEB3
```

Er prüft die eindeutige Auswahl, Gültigkeit, Code-Signing-Verwendung und
Zuordnung zum privaten Schlüssel im Windows-Benutzerspeicher. Ein grüner
Vorabcheck belegt noch keine erfolgreiche Cloud-Signatur. Dafür müssen die
echten Dateien signiert und einschließlich Zeitstempel geprüft werden.

### Was es ist

Ein OV-Zertifikat (Organization Validation) auf eine natürliche Person. Im
Zertifikat stehen Vor- und Nachname als Common Name und als Organisation, dazu
Ort und Land, keine Straße. Die Certum-Produktseite nennt es „Code signing for
an individual or a company", und genau das ist die mittlere der drei Spalten
dort. Die linke Spalte (Open Source, 25 Euro) scheidet aus: Im Zertifikat stünde
„Open Source Developer" statt des Namens, und Certum widerruft es, sobald die
Software kommerziell verteilt wird. Die rechte (EV, 329 Euro) gibt es nur für
Unternehmen, und den früheren SmartScreen-Vorteil hat EV seit 2024 nicht mehr,
Microsoft schreibt es ausdrücklich.

### Zwei Auslieferungen, eine Empfehlung

| | Karte | Cloud (SimplySign) |
|---|---|---|
| Schlüssel liegt | auf einer Chipkarte, verlässt sie nie | im Certum-HSM in der EU, verlässt es nie |
| Braucht | Karte plus Lesegerät (Set bei Certum), proCertum-Treiber | SimplySign Desktop auf dem PC, SimplySign-App auf dem Handy (Einmalcode) |
| Preis, erstes Jahr | ab 139 Euro, Leser einmalig dazu | rund 209 Euro direkt bei Certum, 139 Dollar über den Händler SSLmentor |
| Signieren | Karte stecken, PIN, `signtool` | SimplySign Desktop verbinden, Einmalcode, `signtool` |
| Später automatisierbar | nein | ja, mit Vorbehalt (siehe „Wer baut wo") |

Empfehlung: **Cloud.** Keine Hardware, kein Treiber, und der Schlüssel ist in
beiden Fällen gleich gut geschützt. Beide Varianten sind sicherer als jeder
PFX-Weg, weil nie ein Schlüssel in GitHub-Geheimnissen oder auf einer Platte
liegt.

Seit dem 27.02.2026 gilt ein Code-Signing-Zertifikat höchstens 459 Tage. „1 bis
3 Jahre" auf der Produktseite ist die Laufzeit des Dienstes; bei zwei oder drei
Jahren kommt die Neuausstellung kostenlos, je Jahr etwas günstiger.

### Bestellen und prüfen lassen

1. Bestellen: „Standard Code Signing in the Cloud", Variante Einzelperson
   (natural person / individual developer). Bei SSLmentor 139 Dollar für ein
   Jahr, 127 je Jahr bei zwei, 115 je Jahr bei drei Jahren, ohne Mehrwertsteuer.
2. Identität: online, Ausweis scannen und Gesichtsscan. Alternativ vor Ort an
   einer Registrierungsstelle oder notariell, beides teurer und langsamer.
3. Adresse: eine Versorgerrechnung (Strom, Gas, Wasser, Telefon) auf Roberts
   Namen, wenn die Adresse nicht im Ausweis steht. Ein Mietvertrag geht auch.
4. Warten: Certum nennt drei bis fünf Werktage nach vollständigen Unterlagen.
5. Aktivieren: SimplySign Desktop installieren, die App auf dem Handy mit dem
   QR-Code koppeln, Zertifikat im Konto aktivieren. Certum hat dazu eine
   Anleitung als PDF („Standard Code Signing in the cloud certificate activation").

### Signieren — zwei CI-Bauschritte mit lokaler Signatur

Die CI baut die Windows-Anwendung und legt einen prüfsummengebundenen
Signiereingang ab: das Artefakt `solidon3d-windows-signing-input` mit
`windows-signing-input.zip` und der zugehörigen `.sha256`. Darin liegen der
gebaute Anwendungsordner, das Inno-Setup-Skript, Lizenz, Symbol, Lizenzmanifest
und `packaging/build/windows-signing.json` mit den Prüfsummen jeder Eingabe.
Dieser Eingang wird lokal geprüft und signiert. Das Artefakt lebt sieben Tage
(`retention-days: 7`) — genug, um nach dem Lauf in Ruhe zu signieren.

Der Ablauf ist verbindlich:

1. `build.yml` baut die Anwendung in der CI und liefert den Signiereingang.
2. Lokal wird ausschließlich `Solidon3D.exe` signiert und geprüft.
3. `windows-signed-installer.yml` baut den Installer in der CI aus genau dieser
   signierten Anwendung und den ursprünglichen, geprüften Eingängen.
4. Lokal wird ausschließlich dieser Installer signiert und geprüft. Danach
   werden Prüfsumme und Releaseakte für das endgültige Kundenpaket geschrieben.

**Erster lokaler Schritt**, mit der Nummer des erfolgreichen Anwendungslaufs:

```powershell
.venv\Scripts\python.exe tools/sign_release.py --phase application --run <bau-lauf> --stage build/signing-<bau-lauf> --output dist/signing-<bau-lauf> --thumbprint 235C54FC71D79BD03449DBC62FFB14D0AC58AEB3
```

Das Werkzeug prüft den Lauf, das Archiv gegen seine `.sha256`, Produktangaben
und jede Eingangsdatei. Ein vorhandener Arbeitsordner wird nie überschrieben.
Es signiert die Anwendung mit SHA-256 und RFC-3161-Zeitstempel, prüft mit
`signtool verify /pa /all /tw /v` und bindet die neue Prüfsumme in der Übergabe.
Es liefert `Solidon3D.exe` und `windows-application-signature.json`. Der
JSON-Nachweis nennt Version, ursprünglichen CI-Lauf und Commit, Archivhash,
Anwendungshash vor und nach der Signatur sowie den Zertifikatsfingerabdruck.

Diese beiden Dateien werden für den beauftragten Release als Assets eines
**unveröffentlichten GitHub-Release-Entwurfs** hinterlegt. Der separate
Installer-Workflow lädt sie anhand dieses Entwurfs, vergleicht die Herkunft
mit dem erfolgreichen Anwendungslauf und prüft Hash, Signatur und das genaue
Herausgeberzertifikat. Der Anwendungslauf muss erfolgreich abgeschlossen sein
— rot allein im meldenden Job „Neueste Versionen“ zählt als erfolgreich
(`sign_release.ADVISORY_JOBS`; die Jobliste wird vollständig gelesen, jeder
andere Job muss grün oder übersprungen sein) — und
entweder manuell über `workflow_dispatch` auf `main` oder durch den Push des
zur Anwendungsversion passenden Tags `v<Version>` gestartet sein. Beim Tag-Lauf
prüft das Werkzeug die tatsächliche GitHub-Tagreferenz und ihren Zielcommit;
ein gleichnamiger Branch genügt nicht. Leichte und einmal annotierte Tags sind
zulässig. `target_commitish` des Entwurfs nennt denselben vollständigen
Commit-Hash; eine bewegliche Angabe wie `main` genügt dort nicht. Der
Installer-Workflow läuft weiterhin manuell auf `main`. Eine reine Korrektur
des Signierablaufs darf auf einem späteren Commit erfolgen: Der gemeinsame
Herkunftsprüfer vergleicht dazu beide vollständigen Git-Bäume und verlangt
gleiche Blattpfade, Typen, Dateimodi und Objekt-SHAs außerhalb einer kleinen,
ausdrücklich benannten Liste von Signierwerkzeugen, Workflow, Tests und
Dokumentation. Abgeschnittene oder fehlerhafte Antworten sperren den Lauf;
beliebige Produkt-, Abhängigkeits- oder Installeränderungen sind nicht erlaubt.
Zwischen Tag und Installerlauf geht deshalb nichts nach `main`, was nicht in
`INSTALLER_ORCHESTRATION_FILES` (`tools/sign_release.py`) steht — auch keine
Doku —, sonst hält der Installerlauf am Baumvergleich an.
Das Versions-Tag und der Quellcommit in der Anwendungssignatur bleiben dabei
unverändert. Die Installer-Rückgabe nennt ihren eigenen tatsächlichen Commit
und ihre Laufnummer. Der lokale Signierer prüft beides gegen den erfolgreichen
Installerlauf und wiederholt denselben Baumvergleich.

Der Installerjob braucht für den unveröffentlichten Transport `contents: write`.
GitHub macht Release-Entwürfe nur mit Push-Rechten zugänglich; `contents: read`
genügt dafür nicht. Dieses Recht steht nur am Installerjob, der weder einen
Release veröffentlicht noch Windows-Signiergeheimnisse erhält.

Der unveröffentlichte Signiertransport erhält einen eigenen Namen mit der
Quelllaufnummer. Das Versions-Tag bleibt dem eigentlichen Release zugeordnet:

```powershell
$signing = Get-Content 'dist/signing-<bau-lauf>/windows-application-signature.json' -Raw | ConvertFrom-Json
$transportTag = "signing-v$($signing.app_version)-$($signing.source_run_id)"
gh release create $transportTag 'dist/signing-<bau-lauf>/Solidon3D.exe' 'dist/signing-<bau-lauf>/windows-application-signature.json' --repo RS-Digital-Studio/Solidon --draft --target $signing.source_commit --title "Solidon3D $($signing.app_version)" --notes 'Unveröffentlichter Signiertransport für den CI-Installerbau.'
$draftId = gh release view $transportTag --repo RS-Digital-Studio/Solidon --json databaseId --jq '.databaseId'
gh workflow run windows-signed-installer.yml --repo RS-Digital-Studio/Solidon --ref main -f "build_run_id=$($signing.source_run_id)" -f "source_commit=$($signing.source_commit)" -f "app_version=$($signing.app_version)" -f "draft_release_id=$draftId" -f "signed_app_sha256=$($signing.signed_application_sha256)"
```

Diese Befehle gehören zum ausdrücklich beauftragten Release. Existiert dafür
bereits ein unveröffentlichter Entwurf mit genau diesem `target_commitish`,
werden die beiden Dateien mit `gh release upload` diesem Entwurf hinzugefügt;
ein veröffentlichter Release wird dafür nicht verändert. Nach jedem Befehl
muss der Exitcode null sein, bevor der nächste Schritt folgt.

Die Entwurfs-ID ist die numerische GitHub-Release-ID, nicht der Tagname.
`gh release view` findet sie auch am Entwurf; `gh api …/releases/tags/<tag>`
kennt nur veröffentlichte Releases und antwortet bei einem Entwurf mit 404.
Erst der vollständig erfolgreiche Installerlauf ist ein Signiereingang.
Er baut mit Inno Setup in der CI. Das Ergebnis ist das
Artefakt `solidon3d-windows-installer-signing-input`: Setup-Datei, `.sha256`
und `windows-installer-build.json`, das die Herkunft und den Installerhash bindet.
Die Transportdateien sind keine Kundendownloads.

**Zweiter lokaler Schritt**, mit der Nummer des erfolgreichen Installerlaufs
und demselben Arbeitsordner wie im ersten Schritt:

```powershell
.venv\Scripts\python.exe tools/sign_release.py --phase installer --installer-run <installer-lauf> --stage build/signing-<bau-lauf> --output dist --thumbprint 235C54FC71D79BD03449DBC62FFB14D0AC58AEB3
```

Vor der Setup-Signatur müssen Installerherkunft und der unveränderte signierte
App-Baum zusammenpassen. Danach prüft das Werkzeug auch die Setup-Signatur
mit Zeitstempel, schreibt die neue `.sha256` und erneuert die Release-Evidenz
(`make_licence_notices.py --write-evidence`, anschließend `--release-check`).
**Jeder Fehler hält die Weitergabe an.** Eine rote Releaseakte wird nicht
durch eine Warnung ersetzt. Nur das erfolgreiche Ergebnis unter `dist/` wird
veröffentlicht; der unsignierte Installer aus dem normalen Baujob gehört
nicht dazu. `--release-evidence` verlegt die Akte (Vorgabe
`build/release-evidence.json`).

Danach wie bisher: `tools/make_download.py`, `tools/sign_version.py`,
`tools/stamp_assets.py`, `tools/upload_website.py`.

Drei Dinge dabei:

- **Der Zeitstempel ist Pflicht.** Ohne `/tr` verfällt die Signatur mit dem
  Zertifikat; mit Zeitstempel bleibt ein einmal signiertes Paket gültig, auch
  wenn das Zertifikat nach 459 Tagen abläuft oder gewechselt wird.
- **Erst die Anwendung, dann die Setup-Datei.** Der Installer packt die
  Anwendung ein; wer nur die Setup-Datei signiert, liefert eine signierte Hülle
  um eine unsignierte `Solidon3D.exe`. SmartScreen prüft die heruntergeladene
  Datei, Virenscanner und Firmenrichtlinien sehen die installierte.
- **Inno Setup läuft in der CI.** Der lokale Rechner braucht SimplySign
  Desktop, SignTool aus dem Windows SDK, `gh` und die Projektumgebung für die
  Prüfung. Er kompiliert weder Anwendung noch Installer.

Die CI erhält keine Windows-Signiergeheimnisse. Ihr normaler Baujob darf ein
unsigniertes Prüfpaket erzeugen; der separate Installerlauf verwendet die
lokal signierte Anwendung. Die Veröffentlichung verlangt die abschließende
Signatur. `tests/test_sign_release.py` prüft den Vorabcheck, die beiden
lokalen Schritte, Herkunftsabweichungen und das Anhalten bei fehlerhaften
Signaturen, Zeitstempeln oder Releasebelegen.

### Was SmartScreen dann tut

Die gültige Signatur weist **Robert Schneider** als Herausgeber aus und macht
nachträgliche Änderungen erkennbar. SmartScreen kann bei neuen Dateien
trotzdem einen Hinweis zeigen. Die Signatur ist deshalb keine Zusage, dass
jeder Windows-Rechner das Paket ohne Warnung öffnet.

---

## macOS — Apple Developer Program als Einzelperson

### Was es ist

Der einzige Weg, den Gatekeeper akzeptiert, und zugleich der günstigste:
99 Dollar im Jahr. Ohne Developer ID und Notarisierung meldet macOS bei jedem
Paket „kann nicht geöffnet werden, weil es von einem nicht verifizierten
Entwickler stammt", und der Umweg über die Systemeinstellungen ist kein Weg für
einen Kunden ohne Vorwissen.

### Anmelden

1. Apple-Account mit Zwei-Faktor-Authentifizierung, bürgerlicher Name in den
   Namensfeldern (kein Firmenname, kein Kürzel, das verzögert die Prüfung).
2. Anmeldung als „Individual / Sole Proprietor" über die Apple-Developer-App auf
   iPhone oder iPad oder über die Website. Apple prüft Name, Telefon, Adresse
   (kein Postfach) und verlangt in der Regel ein Foto des Ausweises.
3. Keine D-U-N-S-Nummer, keine beglaubigten Unterlagen; das gilt nur für
   Organisationen.
4. Ergebnis: eine Mitgliedschaft mit einer **Team-ID** (zehn Zeichen).

### Zertifikate anlegen

Im Entwicklerkonto unter „Certificates" zwei Zertifikate:

| Zertifikat | Signiert | Name der Identität |
|---|---|---|
| Developer ID Application | die `.app` | `Developer ID Application: Robert Schneider (TEAMID)` |
| Developer ID Installer | das `.pkg` | `Developer ID Installer: Robert Schneider (TEAMID)` |

Bei der Zwischenstelle **G2 Sub-CA** wählen, nicht das vorausgewählte „Previous
Sub-CA": Zertifikate der alten Zwischenstelle laufen am 01.02.2027 ab,
unabhängig davon, wann sie ausgestellt wurden. Mit G2 sind es fünf Jahre.

Jedes braucht eine **eigene** Zertifikatsanfrage (CSR) auf einem **eigenen
Schlüssel**: Apple lehnt eine zweite Anfrage auf demselben Schlüssel ab („has
already been used to generate another certificate"). Auf einem Mac erzeugt die
Schlüsselbundverwaltung sie; ohne Mac geht es mit `openssl` — je Zertifikat
Schlüssel und CSR erzeugen, CSR hochladen, das ausgestellte `.cer`
herunterladen und mit seinem Schlüssel zu einer `.p12` bündeln, zusammen mit
der Kette aus Developer ID G2 CA und Apple Root CA. Es entstehen zwei `.p12`,
die sich ein Passwort teilen dürfen; beide mit Passwort sind das, was die CI
bekommt. Dazu unter account.apple.com ein **app-spezifisches Passwort** für die
Notarisierung anlegen.

### In der CI einschalten

Die Variable `MACOS_SIGNING_MODE` auf `notarized` setzen (`signed` signiert nur,
ohne Apples Prüfung, das reicht für Gatekeeper nicht). Dazu die sechs
Geheimnisse, die `build.yml` erwartet:

| Geheimnis | Inhalt |
|---|---|
| `APPLE_CERTIFICATE` | die `.p12` des Application-Zertifikats, base64-kodiert |
| `APPLE_INSTALLER_CERTIFICATE` | die `.p12` des Installer-Zertifikats, base64-kodiert |
| `APPLE_CERTIFICATE_PASSWORD` | das Passwort beider Dateien |
| `APPLE_NOTARY_ID` | die Apple-ID (E-Mail) |
| `APPLE_NOTARY_PASSWORD` | das app-spezifische Passwort |
| `APPLE_TEAM_ID` | die Team-ID |

Die CI macht dann je Architektur (Apple Silicon und Intel): `codesign` mit
Hardened Runtime und Zeitstempel, `notarytool submit --wait` (Apples Prüfung,
meist Minuten), `stapler` heftet das Ticket an und prüft es, `spctl` prüft
zuletzt den Installationsweg. Notarisierung kostet nichts.

Die Schlüssel liegen hier zwangsläufig in den GitHub-Geheimnissen, einen
Cloud-HSM-Weg bietet Apple nicht. Das ist vertretbar: Ein Developer-ID-Zertifikat
lässt sich im Konto jederzeit widerrufen, und Apple kann notarisierte Software
nachträglich sperren. Die beiden `.p12` liegen außerhalb der CI nur im
Passwortmanager, nirgends sonst.

---

## Linux — keine Signaturpflicht

AppImage, Flatpak und das tar.gz starten ohne Signatur; kein Linux-Desktop
prüft eine. Was trägt, ist etwas anderes:

- Die CI schreibt neben jedes Paket eine `.sha256`.
- `tools/make_download.py` trägt die SHA-256 jedes Pakets in `version.json`
  ein, `tools/sign_version.py` signiert die Datei mit Ed25519, und der Updater
  in `app/core/updates.py` prüft Signatur und Prüfsumme, bevor er ein Geholtes
  je startet. Das gilt auf allen drei Plattformen und ist von der Code-Signierung
  unabhängig.

Möglich, aber nicht geplant: eine GPG-Signatur im AppImage (`appimagetool
--sign`) und ein signiertes Flatpak-Repository. Beides prüft praktisch niemand,
und Flathub würde ohnehin selbst signieren.

---

## Wer baut wo

Die CI baut weiter alle drei Plattformen, an dem Ablauf ändert sich nichts.
Nur die Windows-**Signierung** wandert nach draußen:

| Plattform | Bauen | Signieren | Paket entsteht |
|---|---|---|---|
| Windows | CI, einschließlich Installer | lokal, vor und nach dem Installerbau | CI (`windows-signed-installer.yml`, Inno Setup) |
| macOS | CI | CI (Developer ID, Notarisierung) | CI |
| Linux | CI | keine | CI |

Anwendung und Setup-Datei entstehen in der CI. Zwischen den beiden Bauschritten
wird lokal die Anwendung signiert, anschließend der fertige Installer. macOS
bleibt vollständig in der CI, einschließlich Signierung und Notarisierung.

**Warum die Windows-Signierung lokal bleibt:** Certums Cloud-Schlüssel lässt sich nicht
als PFX exportieren, und SimplySign verlangt einen Einmalcode vom Handy. Es
gibt einen bekannten Trick, das zu automatisieren (der QR-Code beim Koppeln ist
eine `otpauth://`-URI, aus der ein Skript den Code selbst erzeugen kann). Damit
lägen aber Zugangsdaten und OTP-Geheimnis zusammen in GitHub, und das ist so
gut wie der Schlüssel selbst. Für einen Herausgeber, der eine Handvoll
Fassungen im Jahr signiert, ist der lokale Weg sicherer und nicht langsamer.
Sollte die Zahl der Fassungen einmal wöchentlich werden, ist das der Punkt,
den Trick mit einem eigenen Certum-Konto nur für die CI neu zu bewerten.

---

## Kosten und Zeit

| | Kosten je Jahr | Einmalig | Prüfzeit |
|---|---|---|---|
| Windows, Certum Cloud (Einzelperson, über SSLmentor) | 139 Dollar, ab dem zweiten Jahr 115 bis 127 | keine | 3 bis 5 Werktage |
| macOS, Apple Developer Program | 99 Dollar | keine | Stunden bis wenige Tage |
| Linux | 0 | 0 | 0 |

Die früheren Windows-Demos wurden unsigniert ausgeliefert. Die erste
verbindlich signierte Windows-Fassung ist **0.5.0**. Fehlende Anmeldung,
ungültige Signatur oder unvollständige Releasebelege halten die Veröffentlichung an.

## Quellen (abgerufen am 02.09.2026)

- GitHub, Zugriff auf unveröffentlichte Release-Entwürfe (für den
  Installeranschluss geprüft): https://docs.github.com/en/rest/releases/releases#list-releases
- Certum, aktuelle SimplySign-Desktop-Installation und Code-Signing-Anleitung
  (für die Einrichtung am 23.09.2026 geprüft):
  https://support.certum.eu/en/software/procertum-smartsign/ und
  https://support.certum.eu/en/installation-of-the-simplysign-applications/
- Certum, Produktfamilie Code Signing: https://www.certum.eu/en/code-signing-certificates/
- Certum, Standard Code Signing in the Cloud: https://shop.certum.eu/standard-code-signing-in-the-cloud.html
- Certum, benötigte Unterlagen: https://support.certum.eu/en/code-signing-required-documents/
- Certum, Verkürzung der Laufzeit auf 459 Tage: https://www.certum.eu/en/news/shortening-code-signing-certificate-validity/
- SSLmentor, Certum Cloud Code Signing für Einzelentwickler: https://www.sslmentor.com/certum/certumcodecloudindividual
- Microsoft, Artifact Signing FAQ (drei Jahre Steuerhistorie, Einzelpersonen nur USA/Kanada): https://learn.microsoft.com/en-us/azure/artifact-signing/faq
- Apple, Developer Program Enrollment: https://developer.apple.com/programs/enroll/
- Apple, Identity Verification: https://developer.apple.com/help/account/membership/identity-verification/
- SimplySign-Automatisierung (der Trick, und warum er hier nicht gilt): https://www.devas.life/how-to-automate-signing-your-windows-app-with-certum/
