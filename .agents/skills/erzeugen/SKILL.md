---
name: erzeugen
description: >
  Erzeugt Solidons Release-Artefakte und liefert sie im beauftragten Umfang aus:
  Handbuch, Website-Bilder, SEO-Dateien, Symbol, Installationspakete und Download-
  Kasten. Führt auch Umgebungseinrichtung und Versionspflege über check_env.
  Benutzen vor diesen Werkzeugen und vor einem Paketbau; keine automatische Veröffentlichung.
argument-hint: "[gewünschtes Artefakt oder Auslieferungsschritt]"
allowed-tools: Bash, Read, Edit, Grep, Glob
---

# Erzeugen und Ausliefern

## Umfang und Quellen

Ein Auftrag für Bilder, lokale Pakete oder eine Prüfung ist kein Auftrag für
Tag, Push, Website-Upload, Löschung auf dem Server oder eine Support-Sendung.
Bereits beauftragte Auslieferungsschritte ohne erneute Nachfrage ausführen.
Produktdateien, Prüfbilder und öffentliche Release-Artefakte auseinanderhalten.

Lies `CLAUDE.md`, die Karten unter `tools/`, `packaging/` und `website/`, soweit
betroffen. Befehle und Optionen im aktuellen Werkzeug prüfen. Die Beispiele
unten enthalten Platzhalter; vor dem Aufruf durch belegte Werte ersetzen.
Keine Zugangsdaten, Signierschlüssel oder Betreiber-Tokens in Ausgaben kopieren.

Alle Projektwerkzeuge über den geprüften Interpreter des Arbeitsbaums ausführen:
Windows `.venv/Scripts/python.exe`, Linux/macOS `.venv/bin/python`. Nur
`tools/check_env.py` ist ausdrücklich für den Erstaufbau ohne `.venv` gedacht.

## Werkzeugwahl

| Aufgabe | Werkzeug und relevanter Hinweis |
|---|---|
| Handbuch-Bildschirmfotos | `tools/make_figures.py <sprache>`; `--schirm N` wählt den Monitor. |
| Verkaufsbilder | `tools/make_web_images.py <sprache>`; eigene Ansichtsgröße, nicht verkleinerte Handbuchbilder. |
| Handbuch und PDF | `tools/make_manual.py`; Sprach- und Ausgabeoptionen vor dem Lauf nachsehen. |
| Symbol | `tools/make_icon.py`; Rasterdateien und Website-Favicon aus der vorhandenen Quelle. |
| SEO-Dateien | `tools/make_seo.py`; nach den Seiten- und Handbuchgeneratoren. |
| Tutorials | `tools/make_longform_video.py`; etwa `--language en`, Schnittplan und Belege mitprüfen. |
| Windows-Setup | `tools/make_installer.py`; Paketstand und lokale Bauwerkzeuge zuerst prüfen. |
| Linux-Metadaten | `tools/make_linux_packages.py --files`; tatsächliche Pakete entstehen im passenden Bauumfeld. |
| Download-Kasten | `tools/make_download.py <pakete>`; **ohne Argument leert es Kasten und Versionsliste**. |
| ComfyUI | `tools/setup_comfyui.py`; Umfang, Gewichte, Speicher und vorhandene Installation prüfen. |
| Optionaler Schnittkern | `tools/build_slice_core.py`; Wirkung am aktuellen Stand messen. |
| Asset-Stempel | `tools/stamp_assets.py`; nach allen Erzeugern und vor dem Upload. |
| Website | `tools/upload_website.py`; explizite Dateien oder geprüfte Auswahl wie `--seit <commit>`. |
| Support-Ende-zu-Ende | `tools/check_support.py`; sendet eine echte Nachricht, nur bei entsprechendem Auftrag. |
| Umgebung | `tools/check_env.py`, `--install`, `--outdated`, `--freeze`; Prüfung, Installation und Neufestlegung getrennt. |

## Bilder und Handbuch

Release-Bilder und Handbuch nicht nach jedem Arbeitsschritt neu erzeugen,
sondern vor einem Release und nur für geänderte Inhalte und Sprachen. Ein
expliziter Auftrag zur Bilderzeugung bleibt möglich. Verfügbare Sprachen aus
`app/i18n/locales/` beziehungsweise `available_languages()` ermitteln.

Die GUI-Erzeuger brauchen eine echte Plattform mit geladenen Schriften;
`QT_QPA_PLATFORM=offscreen` liefert dafür keinen verlässlichen Bildnachweis.
Umgebungsänderungen auf den eigenen Prozess begrenzen. Fenster und Bildschirm
für den Lauf tatsächlich prüfen, keine Monitorgröße aus früheren Läufen annehmen.

Wegen nativer Abbrüche jede Sprache in einem eigenen Prozess erzeugen. Vorher
ermitteln, welche Ausgabedateien dieser Lauf erzeugen soll. Danach Prozessausgang,
Vollständigkeit, Aktualität und sichtbaren Inhalt prüfen. Zeitstempel allein
beweisen keine brauchbaren Bilder; ein Nichtnull-Exit bleibt ein Fehllauf.
Bei einem plausibel vorübergehenden Fehler einmal gezielt wiederholen. Bei
wiederholtem gleichem Fehler Ursache klären und den offenen Umfang nennen.

Wenn alle betroffen sind, gilt die Reihenfolge Handbuchbilder → Verkaufsbilder
→ Handbuch → SEO → Inhaltsstempel. Handgepflegte Bildmaße in HTML danach mit
den tatsächlichen Dateien abgleichen. Prüfbilder aus `.agents/skills/website-review/SKILL.md` sind
keine Release-Bilder und gehören nicht in den öffentlichen Uploadpfad.

## Version und Paketbau

Bei einem neuen **auszuliefernden** Bau die Versionsregel in `app/branding.py`
und das aktuelle `tools/bump_version.py` prüfen. Die Patch-Version steigt vor
Prüfmodul und Bau; ein bereits für diesen Release erfolgter Versionsschritt
wird beim Wiederholen nicht erneut gezählt. Größere Versionssprünge folgen der
Produktentscheidung. Ein reiner Diagnosebau ist keine neue Veröffentlichung.

`branding.py` und `pyproject.toml` werden zusammen gepflegt. `website/version.json`
bezeichnet den ausgelieferten Stand und wird erst aus den richtigen fertigen
Paketen erzeugt und nach deren Upload veröffentlicht.

Vor dem Paketbau gilt das vollständige Tor über `.agents/skills/pruefen/SKILL.md`. Die CI ist der
reguläre Bauweg: `.github/workflows/build.yml` bestimmt Trigger, Plattformen,
Abhängigkeiten und die getrennten Signier- und Prüfjobs. Vor einem beauftragten
Tag oder Handstart den konkreten Commit und Versionsstand feststellen. Kein
fest eingetragenes Beispiel-Tag verwenden. Laufkennung und Commit gehören zum
Nachweis; `gh run watch <lauf-id> --exit-status` liefert den Abschlussstatus.

Lade die fertigen öffentlichen Artefakte gezielt aus diesem Lauf, nicht alle
Zwischenstände mit Signier- oder privaten Release-Dateien. Namen und Herkunft
im Workflow abgleichen. Ein fertiger Baujob allein belegt weder Signierung,
Notarisierung, vollständige Releaseakte noch Veröffentlichung. Fehlende
Voraussetzungen nicht durch Abschalten der Prüfungen umgehen.

Für einen beauftragten lokalen Probe- oder Ersatzbau einen isolierten
Arbeitsbaum mit bewusst gewähltem Stand verwenden. Die eigene Umgebung dort
gegen `constraints.txt` einrichten; ein Worktree bringt keine `.venv` mit.
Prüfmodul, Paket und Installer müssen aus demselben Stand stammen. Der Weg
führt über `tools/build_licence_module.py` und `packaging/solidon3d.spec`;
Signieranforderungen und Bauoptionen in den aktuellen Anleitungen prüfen.

## Downloads und Veröffentlichung

Maßgeblich für angebotene Pakete ist `DELIVERED` in `tools/make_download.py`.
Derzeit sind es fünf Plätze: Windows-Setup, Linux AppImage, Linux Flatpak und
je ein macOS-PKG für Intel und Apple Silicon. Archive und private Zwischen-
artefakte nicht als zusätzliche Downloads veröffentlichen. Prüfsummen,
Signaturen, Version und Vollständigkeit vor dem Erzeugen des Kastens abgleichen.

Bei einem beauftragten Website-Release:

1. Rechtekette öffentlicher Medien in `ASSET-RIGHTS.toml` prüfen, bei unklaren
   Nutzungsrechten `.agents/skills/legal-review/SKILL.md`. Lokale Modellquellen unter `website/teile/`
   bleiben intern; die Auswahlfilter von `upload_website.py` erhalten.
2. `make_download.py` mit den tatsächlichen angebotenen Paketen aufrufen.
   Versionsdatei über `tools/sign_version.py` mit der vorgesehenen externen
   Schlüsseldatei signieren; keine ungeschützte Ersatzversion veröffentlichen.
3. Betroffene Seiten und Generatorausgaben prüfen, dann `stamp_assets.py`.
4. Große Pakete einzeln und zuerst hochladen, mit Pfad ab `website/`.
   Ausgabe und Prozessausgang je Upload lesen.
5. Seiten und signierte Versionsdatei über die passende geprüfte Dateiauswahl
   hochladen. `--fehlend` nimmt Pakete aus und ersetzt ihren Upload nicht.
6. `upload_website.py --nachpruefen` gegen den Server ausführen. Lokale Dateien
   und ein erfolgreicher Uploadaufruf belegen nicht den ausgelieferten Inhalt.
   Bei visuellen Änderungen zusätzlich `.agents/skills/website-review/SKILL.md` auf den Zielseiten.
7. Alte Pakete zunächst mit `--alte-pakete` nur auflisten. Löschen mit
   zusätzlichem `--wirklich` nur im beauftragten Bereinigungsumfang und nach
   Prüfung der konkreten Liste; nicht pauschal als Teil jedes Uploads.

## Umgebung und Abschluss

Erstaufbau über `python tools/check_env.py --install`; den tatsächlich passenden
Python-Interpreter zuvor prüfen. Abhängigkeiten bleiben an `constraints.txt`
gebunden. Installation oder Aktualisierung einer geteilten Umgebung nicht
während fremder Läufe durchführen. `--outdated` ist eine Bestandsaufnahme,
kein Auftrag zum Aktualisieren. Neue Versionsbindungen erst nach erfolgreicher
Prüfung mit `--freeze` festschreiben.

Melde erzeugte Dateien, Stand und Version, durchgeführte Prüfungen sowie für
jede Plattform den tatsächlichen Bau-/Signierstatus. Upload, öffentliche
Erreichbarkeit und lokale Erstellung getrennt nennen. Eine noch offene
Plattform- oder Serverprüfung nicht durch ein lokales Grün ersetzen.
