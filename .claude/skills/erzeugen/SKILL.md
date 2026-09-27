---
name: erzeugen
description: >
  Erzeugt Solidons Artefakte und liefert sie im beauftragten Umfang aus:
  Beispielprojekte, Handbuchbilder, Verkaufsbilder und Videos, Handbuch,
  Changelog- und Rechtsseiten, SEO, Symbol, Pakete, Signierung, Download-Kasten
  und Website-Upload — dazu Version, Umgebung und Einrichtung eines Rechners.
  Benutzen vor jedem dieser Werkzeuge und vor einem Release; veröffentlicht
  wird nur, was beauftragt ist. Arbeit am Bauweg selbst (Spec, CI,
  Lizenzprüfung): Agent solidon3d-auslieferung.
argument-hint: "[Artefakt oder Auslieferungsschritt]"
allowed-tools: Bash, Read, Edit, Write, Grep, Glob
---

# Erzeugen und Ausliefern

## Umfang und Quellen

Ein Auftrag für Bilder, lokale Pakete oder eine Prüfung ist kein Auftrag für
Tag, Website-Upload, Löschung auf dem Server oder eine Support-Sendung.
Bereits beauftragte Auslieferungsschritte ohne erneute Nachfrage ausführen.
Produktdateien, Prüfbilder und öffentliche Release-Artefakte auseinanderhalten.
Keine Zugangsdaten, Signierschlüssel oder Betreiber-Tokens in Ausgaben kopieren.

Was wo liegt, sagen `tools/CLAUDE.md`, `packaging/CLAUDE.md` und
`website/CLAUDE.md`; was dabei einzuhalten ist, `.claude/rules/auslieferung.md`.
Alle Werkzeuge über den Interpreter des Arbeitsbaums ausführen — Windows
`.venv/Scripts/python.exe`, Linux/macOS `.venv/bin/python`; nur
`tools/check_env.py` ist für den Erstaufbau ohne `.venv` gedacht.

**Kein Werkzeug mit `--help` erkunden.** Die Erzeuger ohne `argparse` werten es
nicht aus und starten ihren vollen Lauf: `make_manual.py` schreibt dann alle
Sprachen samt PDFs, `make_examples.py` alle Beispielprojekte. Welche Argumente
ein Werkzeug nimmt, steht im Moduldocstring am Dateikopf — lesen, nicht
ausprobieren. Die Beispiele unten tragen Platzhalter; vor dem Aufruf durch
belegte Werte ersetzen.

## Werkzeuge

| Aufgabe | Werkzeug und Hinweis |
|---|---|
| Beispielprojekte | `tools/make_examples.py`, ohne Argumente; nach jeder Änderung an `LIBRARY_VERSION` oder einer Beispielkette — `tests/test_examples.py` hält die Bausteinversion der Beispiele fest. |
| Handbuch-Bildschirmfotos | `tools/make_figures.py <sprache>`; `--schirm N` wählt den Monitor. |
| Bildanleitungen | `tools/make_guides.py` ohne Sprache für alle, `--schirm N` wählt den Monitor. Läuft **bei jedem Release in allen Sprachen**, nach dem Versionssprung und vor `make_manual.py`: Der Stempel `app/images/manual/<sprache>/guides.json` trägt die Version, und `test_guides` verlangt die aktuelle. Endet es mit Exit 1, nennt es Anleitung und Schritt — dann die Anleitung oder ihre Geschichte nachziehen, nie den Schritt auslassen. |
| Anleitungsfilme | `tools/make_guide_video.py` ohne Sprache für alle, **nach** `make_guides.py`: je Sprache *Vom Start bis zum Druck* und *Einzelne Aufgaben* mit Kapitelmarken unter `marketing/video/guides/<sprache>/` (nur lokal), `--nur <anleitung>` je Anleitung ein Film. Bricht ab, wenn die Bilder nicht zu Anleitung oder Version passen — dann zuerst `make_guides.py`. Hochgeladen wird von Hand. |
| Verkaufsbilder | `tools/make_web_images.py <sprache>`: das maximierte Hauptfenster, ein Kindprozess je Sprache, Zuschnitte nur aus der Vollbildaufnahme. Der Bausteinkatalog braucht vorher einen gültigen Bereichsnachweis. |
| Website-Loops | `tools/make_video.py <ordner> webloop anpassen <sprache>` und `… formen loop website/teile/weg4-stein-formen.p3d --name weg4-formen <sprache>`, ein Prozess je Sprache. |
| Schaustück, Galerie, Funktionsbilder | `tools/make_showpiece.py`, `tools/make_gallery.py`, `tools/make_feature_images.py` — Funktionsbilder erst in einen Prüfordner, nach der Sichtprüfung das WebP nach `website/bilder/`. |
| Tutorials | `tools/make_longform_video.py --language <sprache>`, `tools/make_workshop_videos.py <film> --language <sprache>`, danach `tools/make_workshop_shorts.py`; Schnittplan und Belege mitprüfen. |
| Handbuch und PDF | `tools/make_manual.py` **kennt keine Argumente** und erzeugt immer alle Sprachen aus `app/i18n/locales/` samt Seiten und PDFs — deshalb nur beim Paketbau. Auf einem Rechner mit exaktem Kern (OCP): Die Menüwege der Referenz lesen `registry.MENU_TWINS`, und die hängen daran, ob der Kern da ist. |
| Changelog- und Rechtsseiten | `tools/make_changelog.py` aus `changelog/<sprache>.md`; `tools/make_legal.py` aus den Rechtstexten im Wurzelverzeichnis, samt `packaging/eula.txt`. |
| SEO-Dateien | `tools/make_seo.py`, nach allen Seiten- und Handbuchgeneratoren. |
| Symbol | `tools/make_icon.py`; Rasterdateien und Favicon aus `app/images/icon/`. |
| Asset-Stempel | `tools/stamp_assets.py` — nach allen Erzeugern, unmittelbar vor dem Upload. |
| Bausteinnachweis | `tools/check_part_ranges.py --all` (Release-Schritt, Regel in `auslieferung.md`). |
| Version | `tools/bump_version.py`; `--minor` und `--major` nur auf Produktentscheidung. |
| Windows-Setup und Signierung | Gebaut wird in der CI, signiert lokal: `tools/sign_release.py --phase application`, dann `--phase installer`; Ablauf in `packaging/CLAUDE.md` und `Signierung/README.md`. `tools/make_installer.py` nur für einen beauftragten lokalen Probebau. |
| Linux und macOS | `tools/make_linux_packages.py` (`--files` schreibt nur die Beschreibungen), `tools/make_macos_package.py`; tatsächliche Pakete entstehen im passenden Bauumfeld. |
| Download-Kasten | `tools/make_download.py <pakete>`; **ohne Argument leert es Kasten und Versionsliste**. |
| Versionsdatei | `tools/sign_version.py` mit der vorgesehenen externen Schlüsseldatei. |
| Website | `tools/upload_website.py` mit ausdrücklichen Dateien oder geprüfter Auswahl wie `--seit <commit>`. |
| Support Ende zu Ende | `tools/check_support.py`; sendet eine echte Nachricht, nur bei entsprechendem Auftrag. |
| ComfyUI, Schnittkern | `tools/setup_comfyui.py` (Umfang, Gewichte, Speicher und vorhandene Installation prüfen); `tools/build_slice_core.py` nach jedem Python-Wechsel, Wirkung am aktuellen Stand messen. |
| Umgebung | `tools/check_env.py` mit `--install`, `--outdated`, `--freeze` — Prüfung, Installation und Neufestlegung getrennt. |

## Bilder und Handbuch

Release-Bilder und Handbuch nicht nach jedem Arbeitsschritt erzeugen, sondern
vor einem Release und nur für geänderte Inhalte und Sprachen; ein
ausdrücklicher Auftrag zur Bilderzeugung bleibt möglich. Die Sprachen kommen
aus `app/i18n/locales/` beziehungsweise `available_languages()`. Zwischen zwei
Paketbauten sind Erzeugnisvergleiche (`rendered`, etwa `test_wording`,
`test_manual`) erwartbar rot — das ist kein Anlass für einen Erzeugerlauf.

Die GUI-Erzeuger brauchen eine echte Plattform mit geladenen Schriften;
`QT_QPA_PLATFORM=offscreen` liefert keinen verlässlichen Bildnachweis.
Umgebungsänderungen auf den eigenen Prozess begrenzen. Fenster und Bildschirm
für den Lauf tatsächlich prüfen, keine Monitorgröße aus früheren Läufen
annehmen.

Wegen nativer Abbrüche jede Sprache in einem eigenen Prozess erzeugen. Vorher
festlegen, welche Ausgabedateien der Lauf erzeugen soll; danach Prozessausgang,
Vollständigkeit, Aktualität und sichtbaren Inhalt prüfen. Zeitstempel beweisen
keine brauchbaren Bilder, ein Nichtnull-Exit bleibt ein Fehllauf. Einen
plausibel vorübergehenden Fehler einmal gezielt wiederholen; bei wiederholt
gleichem Fehler die Ursache klären und den offenen Umfang nennen.

Sind alle betroffen, gilt die Reihenfolge Beispielprojekte → Handbuchbilder →
Bildanleitungen → Anleitungsfilme → Verkaufsbilder und Videos → Handbuch → Changelog- und
Rechtsseiten → SEO → Asset-Stempel. Handgepflegte Bildmaße im HTML danach mit den tatsächlichen
Dateien abgleichen. Prüfbilder aus `/website-review` sind keine
Release-Bilder und gehören nicht in den Uploadpfad.

## Release in seiner Reihenfolge

1. **Druckrelevante Korrekturen zuerst.** Ist vor dem Tag ein Fehler bekannt,
   der Drucke verdirbt, wartet der Tag, bis die Korrektur fertig und im echten
   Slicer belegt ist — auch wenn sie in einer anderen Sitzung läuft. Kein
   Teilrelease, ohne dass Robert es so will.
2. **Changelog** der nächsten Version vor dem Sprung, in jeder Sprache
   (Regeln in `auslieferung.md`). Die Grenzen von `test_changelog` greifen erst
   nach dem Sprung: bis dahin je Punkt selbst zählen.
3. **Release-Tor** nach `/pruefen --release` — Kernsammlung, getrennte
   Fensterdateien, Leistungslauf, Ruff, Format, mypy — über den Stand, der
   ausgeliefert wird; ein grünes Entwicklungstor genügt nicht. Dann committen.
4. **Version** mit `bump_version.py` vor Prüfmodul und Bau; ein für diesen
   Release schon erfolgter Schritt wird beim Wiederholen nicht erneut gezählt,
   ein reiner Diagnosebau erhöht nichts. `website/version.json` bleibt auf dem
   veröffentlichten Stand.
5. **Bausteinnachweis** mit `check_part_ranges.py --all`: Exit 0 und eine
   unveränderte oder eingecheckte `part_ranges.toml`.
6. **Erzeugen**, was sich geändert hat, in der Reihenfolge oben.
7. **Kein zweites Tor vor dem Tag.** Nach Versionssprung und Erzeugern nur die
   betroffenen Wächter (`test_changelog`, `test_toolchain`, `test_website`,
   `test_wording`, `test_manual`, `test_guides`), committen, taggen — die CI fährt die Suiten
   am Tag auf allen Plattformen.
8. **CI-Bau:** `.github/workflows/build.yml` bestimmt Trigger, Plattformen und
   die getrennten Signier- und Prüfjobs. Vor Tag oder Handstart Commit und
   Versionsstand feststellen; kein fest eingetragenes Beispiel-Tag. Laufkennung
   und Commit gehören zum Nachweis, `gh run watch <lauf-id> --exit-status`
   liefert den Abschluss. Gehen Commit und Tag zusammen hinaus, laufen zwei
   Bauten über denselben Commit; der auf `main` lässt sich abbrechen.
9. **Artefakte** gezielt aus diesem Lauf laden — die öffentlichen, nicht alle
   Zwischenstände mit Signier- oder privaten Dateien; Namen und Herkunft im
   Workflow abgleichen. Ein fertiger Baujob belegt weder Signierung,
   Notarisierung, vollständige Releaseakte noch Veröffentlichung. Fehlende
   Voraussetzungen nicht durch Abschalten von Prüfungen umgehen.

Für einen beauftragten lokalen Probe- oder Ersatzbau einen eigenen
Arbeitsbaum mit bewusst gewähltem Stand verwenden und dort eine Umgebung gegen
`constraints.txt` einrichten — ein Worktree bringt keine `.venv` mit. Prüfmodul,
Paket und Installer stammen aus demselben Stand; der Weg führt über
`tools/build_licence_module.py` und `packaging/solidon3d.spec`.

## Downloads und Website-Release

Angeboten wird, was `DELIVERED` in `tools/make_download.py` nennt. Archive und
private Zwischenartefakte nicht als zusätzliche Downloads veröffentlichen.
Prüfsummen, Signaturen, Version und Vollständigkeit vor dem Erzeugen des
Kastens abgleichen. Bei einem beauftragten Website-Release:

1. Rechtekette öffentlicher Medien in `ASSET-RIGHTS.toml` prüfen, bei unklaren
   Nutzungsrechten `/legal-review`. Lokale Modellquellen unter `website/teile/`
   bleiben intern; die Auswahlfilter von `upload_website.py` erhalten.
2. **Den Hinweistext der Version schreiben**, unmittelbar vor
   `make_download.py`: `notes_by_language` in `website/version.json` ist das
   einzige Feld, das ein Mensch schreibt und das `make_download.py` stehen
   lässt — ohne neuen Text reist der alte Satz in die nächste Version.
   `notes_version` nennt die Version, für die er geschrieben ist. Solange
   `version` noch den veröffentlichten Stand trägt, weist die Prüfung der
   Versionsdatei ein neueres `notes_version` ab; `make_download.py` hält an,
   wenn es nicht zur gebauten Version passt.
3. `make_download.py` mit den tatsächlich angebotenen Paketen aufrufen, dann
   die Versionsdatei mit `sign_version.py` signieren; keine ungeschützte
   Ersatzversion veröffentlichen. **Jede Änderung an `version.json` verlangt
   eine neue Unterschrift** — sie deckt jedes Feld außer sich selbst, und eine
   ungültige Datei verwirft jede ausgelieferte Installation ungelesen.
4. Betroffene Seiten und Generatorausgaben prüfen, dann `stamp_assets.py`.
5. Große Pakete einzeln und zuerst hochladen, mit Pfad ab `website/`; Ausgabe
   und Prozessausgang je Upload lesen.
6. Seiten und signierte Versionsdatei über die passende geprüfte Dateiauswahl
   hochladen. `--fehlend` nimmt Pakete aus und ersetzt ihren Upload nicht.
7. `upload_website.py --nachpruefen --mit-pruefsumme` gegen den Server
   ausführen, bevor `version.json` hochgeht: Jede versprochene Datei wird ganz
   geladen und ihre SHA-256 gegen `website/dl/` oder das Manifest gehalten.
   Ohne den Zusatz prüft der Lauf nur die Länge. Lokale Dateien und ein
   erfolgreicher Uploadaufruf belegen nicht den ausgelieferten Inhalt. Bei
   sichtbaren Änderungen zusätzlich `/website-review` auf den Zielseiten.
8. Alte Pakete zuerst mit `--alte-pakete` nur auflisten. Löschen mit
   zusätzlichem `--wirklich` nur im beauftragten Bereinigungsumfang und nach
   Prüfung der konkreten Liste, nie pauschal als Teil eines Uploads.

## Umgebung und Einrichtung

Erstaufbau über `python tools/check_env.py --install`; den passenden
Python-Interpreter zuvor prüfen. Abhängigkeiten bleiben an `constraints.txt`
gebunden. Eine geteilte Umgebung nicht während fremder Läufe installieren oder
aktualisieren. `--outdated` ist eine Bestandsaufnahme, kein Auftrag zum
Aktualisieren; neue Versionsbindungen erst nach erfolgreicher Prüfung mit
`--freeze` festschreiben.

Der Sprachserver hinter `pyright-lsp` wird je Rechner separat installiert
(`npm install --global pyright`). Das npm-Bin-Verzeichnis muss im `PATH` des
gestarteten Editors liegen; nach einer PATH-Änderung den Editor neu starten.
`[tool.pyright]` in `pyproject.toml` begrenzt die Suche auf den Quelltext und
verweist auf `.venv`, damit Druckprojekte und Prüfartefakte nicht mitindiziert
werden.

Bei einer Einrichtungsprüfung den tatsächlich laufenden Editor bestimmen:
Claude Desktop kann eine andere gebündelte Claude-Code-Version verwenden als
der Befehl `claude` im `PATH`. Dessen `auth status` prüft den aufgerufenen
CLI-Kontext und belegt keine fehlende Desktop-Anmeldung. Gemeinsame
Projektdateien und sichtbar ausgeführte Editorfunktionen getrennt prüfen;
eine konfigurierte Terminal-Statuszeile ist noch kein Nachweis für ihre
Darstellung in der Desktop-Oberfläche.

## Bericht

Erzeugte Dateien, Stand und Version, durchgeführte Prüfungen sowie je
Plattform den tatsächlichen Bau- und Signierstatus. Lokale Erstellung, Upload
und öffentliche Erreichbarkeit getrennt nennen; eine offene Plattform- oder
Serverprüfung nicht durch ein lokales Grün ersetzen.
