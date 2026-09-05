# Signierung — Windows, macOS, Linux

Was ein Kunde beim Herunterladen und Starten sieht, hängt an
drei verschiedenen Mechanismen: SmartScreen unter Windows, Gatekeeper unter
macOS, und unter Linux an nichts. Die CI (`.github/workflows/build.yml`)
signiert macOS selbst, sobald Konto und Geheimnisse da sind; Windows baut sie
und übergibt es zur lokalen Signatur mit `tools/sign_release.py`. Bis dahin
liefert sie unsignierte Pakete mit sichtbarer Warnung. Diese Datei
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

### Signieren — der lokale Weg über die Signierübergabe

Die CI baut die Windows-Anwendung und legt einen prüfsummengebundenen
Signiereingang ab: das Artefakt `solidon3d-windows-signing-input` mit
`windows-signing-input.zip` und der zugehörigen `.sha256`. Darin liegen der
gebaute Anwendungsordner, das Inno-Setup-Skript, Lizenz, Symbol, Lizenzmanifest
und `packaging/build/windows-signing.json` mit den Prüfsummen jeder Eingabe.
Genau dieser Eingang ist für den geschützten Signierjob gedacht, und er lässt
sich ebenso gut lokal verarbeiten. Das Artefakt lebt sieben Tage
(`retention-days: 7`) — genug, um nach dem Lauf in Ruhe zu signieren.

Ein Aufruf fährt die ganze Kette:

```
.venv\Scripts\python.exe tools/sign_release.py --run <lauf> --subject "Robert Schneider"
```

`--run` holt das Artefakt mit `gh` nach `dist/`; ohne `--run` nimmt das
Werkzeug ein schon dort liegendes `windows-signing-input.zip`. Dann, in
dieser Reihenfolge und bei jeder Abweichung mit Halt: Archiv gegen seine
`.sha256` prüfen, nach `build/signing` entpacken (ein vorhandener Ordner
wird nie überschrieben), die Übergabe gegen Produktangaben und jede
Prüfsumme prüfen, `Solidon3D.exe` mit `signtool sign /fd SHA256 /tr
http://time.certum.pl /td SHA256 /n <Name>` signieren und mit `signtool
verify /pa /v` prüfen, die Übergabe mit der neuen Prüfsumme neu binden,
die Setup-Datei mit Inno Setup bauen, sie genauso signieren und prüfen, die
`.sha256` daneben schreiben. Ergebnis und Prüfsumme liegen danach unter
`dist/`. Am Ende schreibt es die Release-Evidenz neu
(`make_licence_notices.py --write-evidence`) und fährt `--release-check`
gegen den signierten Installer, wie die CI es gegen den unsignierten tut —
der äußere Hash ist nach der Signatur ein anderer, und die Akte muss den
nennen, den der Kunde bekommt. Scheitert einer der beiden Schritte, warnt
das Werkzeug und legt den signierten Installer trotzdem ab, wie die CI seit
dem 02.09.2026: Kein Release hängt an einer Prüfung, die zum ersten Mal
läuft; der Befund gehört ins Register. Bei zwei Zertifikaten auf denselben Namen
entscheidet `--thumbprint <SHA-1>` statt `--subject`; `--release-evidence`
verlegt die Akte (Vorgabe `build/release-evidence.json`).

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
- **Inno Setup muss lokal installiert sein, 7 oder 6.** `make_installer.py`
  sucht ISCC auf dem PATH und an den üblichen Orten, die neuere zuerst.

In der CI gibt es keinen Windows-Signiermodus mehr: Sie baut aus derselben
Übergabe den unsignierten Installer für Demo und Releaseprüfung und übergibt
das Archiv. `tests/test_sign_release.py` stellt signtool, ISCC und das Archiv
nach und prüft, dass jede Abweichung die Kette anhält, bevor ein Zertifikat
ins Spiel kommt.

### Was SmartScreen dann tut

Auch mit gültiger Signatur warnt SmartScreen anfangs bei einem neuen
Herausgeber, „Unbekannter Herausgeber" wird aber zu „Herausgeber: Robert
Schneider", und die Warnung verschwindet mit der Zahl der Downloads. Ein
Zertifikatswechsel setzt die Reputation nicht auf null, solange der Herausgeber
derselbe bleibt.

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

Beide brauchen eine Zertifikatsanfrage (CSR). Auf einem Mac erzeugt sie die
Schlüsselbundverwaltung; ohne Mac geht es mit `openssl`: Schlüssel und CSR
erzeugen, CSR hochladen, das ausgestellte `.cer` herunterladen und mit dem
Schlüssel zu einer `.p12` bündeln. Die `.p12` mit Passwort ist das, was die CI
bekommt. Dazu unter account.apple.com ein **app-spezifisches Passwort** für die
Notarisierung anlegen.

### In der CI einschalten

Die Variable `MACOS_SIGNING_MODE` auf `notarized` setzen (`signed` signiert nur,
ohne Apples Prüfung, das reicht für Gatekeeper nicht). Dazu die sieben
Geheimnisse, die `build.yml` erwartet:

| Geheimnis | Inhalt |
|---|---|
| `APPLE_CERTIFICATE` | die `.p12`, base64-kodiert (beide Developer-ID-Zertifikate in einer Datei) |
| `APPLE_CERTIFICATE_PASSWORD` | ihr Passwort |
| `APPLE_SIGN_IDENTITY` | `Developer ID Application: Robert Schneider (TEAMID)` |
| `APPLE_INSTALLER_IDENTITY` | `Developer ID Installer: Robert Schneider (TEAMID)` |
| `APPLE_NOTARY_ID` | die Apple-ID (E-Mail) |
| `APPLE_NOTARY_PASSWORD` | das app-spezifische Passwort |
| `APPLE_TEAM_ID` | die Team-ID |

Die CI macht dann je Architektur (Apple Silicon und Intel): `codesign` mit
Hardened Runtime und Zeitstempel, `notarytool submit --wait` (Apples Prüfung,
meist Minuten), `stapler` heftet das Ticket an und prüft es, `spctl` prüft
zuletzt den Installationsweg. Notarisierung kostet nichts.

Der Schlüssel liegt hier zwangsläufig in den GitHub-Geheimnissen, einen
Cloud-HSM-Weg bietet Apple nicht. Das ist vertretbar: Ein Developer-ID-Zertifikat
lässt sich im Konto jederzeit widerrufen, und Apple kann notarisierte Software
nachträglich sperren. Die `.p12` liegt außerhalb der CI nur im
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
| Windows | CI | lokal, aus der Signierübergabe | lokal (`make_installer.py`, Inno Setup) |
| macOS | CI | CI (Developer ID, Notarisierung) | CI |
| Linux | CI | keine | CI |

Windows wird also nicht „abseits" gebaut; gebaut wird es in der CI wie heute,
nur die Setup-Datei entsteht am Ende auf Roberts Rechner, weil sie die signierte
Anwendung einpacken muss. macOS bleibt vollständig in der CI, das ist der
Grund, warum die Apple-Geheimnisse dort liegen dürfen.

**Warum Windows nicht auch in der CI:** Certums Cloud-Schlüssel lässt sich nicht
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

Für die Demo 0.3.0 kommt beides zu spät; sie geht wie im Demo-Konzept geplant
unsigniert hinaus, mit dem Satz zur SmartScreen-Warnung auf der Seite. Die
erste signierte Fassung ist die, die nach der Prüfung gebaut wird.

## Quellen (abgerufen am 02.09.2026)

- Certum, Produktfamilie Code Signing: https://www.certum.eu/en/code-signing-certificates/
- Certum, Standard Code Signing in the Cloud: https://shop.certum.eu/standard-code-signing-in-the-cloud.html
- Certum, benötigte Unterlagen: https://support.certum.eu/en/code-signing-required-documents/
- Certum, Verkürzung der Laufzeit auf 459 Tage: https://www.certum.eu/en/news/shortening-code-signing-certificate-validity/
- SSLmentor, Certum Cloud Code Signing für Einzelentwickler: https://www.sslmentor.com/certum/certumcodecloudindividual
- Microsoft, Artifact Signing FAQ (drei Jahre Steuerhistorie, Einzelpersonen nur USA/Kanada): https://learn.microsoft.com/en-us/azure/artifact-signing/faq
- Apple, Developer Program Enrollment: https://developer.apple.com/programs/enroll/
- Apple, Identity Verification: https://developer.apple.com/help/account/membership/identity-verification/
- SimplySign-Automatisierung (der Trick, und warum er hier nicht gilt): https://www.devas.life/how-to-automate-signing-your-windows-app-with-certum/
