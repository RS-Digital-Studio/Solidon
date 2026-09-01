# `packaging/` — was das Paket zusammenhält

Die Vorlagen und Beschreibungen, aus denen die Installationsdateien entstehen.
Gebaut wird nicht von hier, sondern über `tools/` und den Skill `/erzeugen`.

## Die Karte

| Datei | Für |
|---|---|
| `solidon3d.spec` | PyInstaller — **die Quelle für alle Plattformen** |
| `solidon3d.iss` | Inno Setup, der Windows-Installer |
| `de.rsdigital.solidon3d.yml` | Flatpak |
| `de.rsdigital.solidon3d.xml` | AppStream-Zuordnung |
| `de.rsdigital.solidon3d.metainfo.xml` | Was der Software-Katalog unter Linux zeigt |
| `solidon3d.desktop` | Startmenü-Eintrag unter Linux |
| `macos-distribution.xml`, `macos-conclusion.txt` | Das macOS-Paket |
| `install.sh` | Linux von Hand |
| `solidon3d.ico`, `solidon3d.icns` | Symbole je Plattform — **erzeugt** von `tools/make_icon.py` |
| `eula.txt` | Die Fassung, die der Installer zeigt — **erzeugt** von `tools/make_legal.py` aus `EULA.md` |
| `DATENSCHUTZ.md` | Lokale, mitgelieferte Fassung für den KI-Hinweis; ohne Webabruf im Fenster gelesen |

`THIRD-PARTY-NOTICES.md` liegt im Projektstamm und reist neben der Anwendung.
Die Spec bricht ab, wenn sie nicht bytegenau aus dem Manifest und den
eingecheckten Originaltexten mit `tools/make_licence_notices.py` erzeugbar ist.

## Die Symbolquelle liegt woanders

`app/images/icon/solidon3d.svg` (und `-small.svg`) ist die Quelle.
`tools/make_icon.py` rastert daraus die `.ico` und die `.icns` **hierher** und
legt zusätzlich `website/icon.svg` als Kopie ab. Was die exe zeigt und was das
Fenster zeigt, ist damit dasselbe.

Zwei Dateien hier sind also Ergebnisse, keine Quellen — sie werden nicht von
Hand bearbeitet.

## Der Installer wird zweimal gerufen, und nicht gleich

Von Hand doppelgeklickt zeigt `solidon3d.iss` seine Seiten und am Ende ein
Häkchen zum Starten. **Aus der Anwendung heraus läuft er still** — Solidon
übergibt `/SILENT /NORESTART /RESTARTAPP=1` (`updates.SETUP_ARGUMENTS`), und der
letzte Schalter ist keiner von Inno Setup, sondern unserer: Ein zweiter
`[Run]`-Eintrag liest ihn über `Check: WantsRestart` und holt das Fenster zurück.

Der vorhandene Eintrag kann das nicht — er trägt `skipifsilent` und greift beim
stillen Lauf gerade nicht. Wer an einem der beiden dreht, dreht am anderen mit;
`tests/test_updates.py` hält Argumentliste und Skript zusammen.

**Auf den anderen beiden Plattformen sieht es anders aus, und das ist
entschieden:** macOS bleibt beim `.pkg` und zeigt Apples Installer (Robert,
28.08.2026). Linux liefert **ab der nächsten Version** zwei Dateien aus:
AppImage zum direkten Start und Flatpak zur verwalteten Installation. Das
AppImage wird nicht installiert; nach dem einmaligen Setzen des Ausführrechts
startet es per Doppelklick. Das Flatpak-Bundle spielt die Anwendung mit
`flatpak install` ein und kommt mit `flatpak run` zurück — **ohne Repo**, weil
`flatpak install` eine Bundle-Datei unmittelbar nimmt. Das tar.gz bleibt ein
Bauartefakt und wird nicht hochgeladen.

Die macOS-Pipeline ist für Apples Freigabe vorbereitet: Nur wenn
`APPLE_CERTIFICATE`, `APPLE_CERTIFICATE_PASSWORD`, `APPLE_SIGN_IDENTITY`,
`APPLE_INSTALLER_IDENTITY`, `APPLE_NOTARY_ID`, `APPLE_NOTARY_PASSWORD` und
`APPLE_TEAM_ID` vollständig stehen, nennt der Schlusstext das Paket geprüft.
Danach müssen `notarytool`, `stapler` und `spctl` tatsächlich grün sein; sonst
entsteht kein auslieferbares Artefakt. Ohne diese Angaben bleibt der bestehende
Warntext für Gatekeeper erhalten.

Windows unterstützt Azure Artifact Signing über OIDC. Sobald
`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`,
`ARTIFACT_SIGNING_ENDPOINT`, `ARTIFACT_SIGNING_ACCOUNT` und
`ARTIFACT_SIGNING_PROFILE` stehen, signiert die CI Anwendung und Setup-Datei
mit der offiziellen Aktion und prüft beide Signaturen. Der bisherige
PFX-Secret-Weg bleibt als Rückfall für ein vorhandenes älteres Zertifikat;
fehlen beide Wege, nennt der Baulauf SmartScreen ausdrücklich.

## Was hier hineinmuss, wenn sich etwas ändert

- **Eine neue Abhängigkeit** kann in der `.spec` fehlen und erst im gebauten
  Paket auffallen — dort, wo kein `pip` mehr hilft.
- **Ein neues Datenverzeichnis** (Kataloge, Profile, Bausteindaten) reist nur
  mit, wenn die `.spec` es kennt.
- **Die Version** kommt aus `app/branding.py` über `tools/bump_version.py` —
  hier wird sie nicht getippt.

`tests/test_packaging.py` prüft, was sich prüfen lässt, ohne zu bauen.

## Der eigene Arbeitsbaum

Paketiert wird in einem **eigenen** Arbeitsbaum, nicht im Entwicklungsbaum —
sonst wandert hinein, was gerade offen ist. Die Reihenfolge und die Falle mit
den fehlenden Schriften stehen im Skill `/erzeugen`.
