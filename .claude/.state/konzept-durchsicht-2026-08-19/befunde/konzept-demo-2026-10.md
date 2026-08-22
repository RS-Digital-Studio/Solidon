# Sondierung: .claude/konzept-demo-2026-10.md

**Titel:** Konzept: Öffentliche Demo bis 30.10.2026
**Stand laut Dokument:** Stand 12.08.2026.
**Zweck:** Fachliche SSOT für die kostenlose, befristete Demo-Fassung von Solidon: Zeitmodell (harter Stichtag 30.10.2026), Arbeitspakete D0–D9, Termine bis zum Start am 20.08.2026 und der Entscheidungspunkt am 10.10.2026 zwischen 1.0 und zweiter Demo.

**Alterung:** 5/5 — Termingetriebenes Planungsdokument mit Tagesplan vom 12.–20.08.2026, Entscheidungspunkt 10.10.2026 und Stichtag 30.10.2026 — alle diese Daten liegen zum heutigen 19.08.2026 unmittelbar bevor oder sind teils schon überholt. Es enthält zudem einen ungepushten CI-Stand, zeilengenaue Codeverweise, eine Fassungsnummer, die sich im Dokument selbst zweimal geändert hat (0.9.0 → 0.7.0 → 0.1.0), und einen Fortschrittsstand, der laut eigener Aussage schon einmal zwei Tage falsch war.

## Gliederung

- §1 Ist-Zustand — was schon steht
- §2 Entscheidungen
- §3 Was fehlt — die Arbeitspakete
- §4 Reihenfolge und Termine
- §5 Was während der Demo läuft
- §6 Der Entscheidungspunkt: 10.10.2026
- §7 Risiken
- §8 Was ausdrücklich nicht zur Demo gehört
- §9 Offene Entscheidungen
- §10 Fortschritt

## Extern prüfbare Behauptungen (20)

- **[hoch/datum] Let's Encrypt / netcup (solidon3d.de)** — HTTPS-Zertifikat von Let's Encrypt läuft bis 06.11.2026  
  _Ort:_ §1 Tabelle, Zeile Website
- **[mittel/funktionsumfang] netcup Webhosting** — Website liegt bei netcup, Webspace mit 75 GB Platz, rund 255 MB je Fassung  
  _Ort:_ §3 D7 Punkt 5; §7 Risikotabelle
- **[mittel/recht] netcup (AV-Vertrag, DSGVO Art. 28)** — Bei netcup ist ein Auftragsverarbeitungsvertrag abzuschließen  
  _Ort:_ §1.1 Schluss; §3 D5 Punkt 2
- **[hoch/marktlage] GitHub RS-Digital-Studio/Formwerk** — Das GitHub-Repository RS-Digital-Studio/Formwerk steht auf PUBLIC  
  _Ort:_ §1.2 a
- **[niedrig/funktionsumfang] GitHub (Repository umbenennen)** — GitHub legt bei Umbenennung eines Repositories eine Weiterleitung an  
  _Ort:_ §9 Punkt 0b
- **[hoch/recht] CA/Browser Forum Code Signing Baseline Requirements (Schlüsselspeicher auf Hardware)** — Seit Juni 2023 gibt es für neu gekaufte Code-Signing-Zertifikate keine exportierbare PFX-Datei mehr  
  _Ort:_ §3 D6 Einleitung
- **[hoch/funktionsumfang] Microsoft Azure Trusted Signing** — Azure Trusted Signing verlangt Unternehmensnachweise, Bearbeitung dauert Tage bis Wochen  
  _Ort:_ §3 D6; §2 A/§4
- **[hoch/funktionsumfang] Microsoft SmartScreen** — SmartScreen-Reputation baut sich über Zeit und Downloadzahl auf; unsignierte Setups werden gewarnt  
  _Ort:_ §2 A; §3 D6; §7
- **[hoch/funktionsumfang] Paddle (Merchant of Record)** — Paddle-Konto: Nachweise, Bankverbindung und Steuerangaben dauern Tage bis Wochen  
  _Ort:_ §2 H; §5
- **[mittel/funktionsumfang] Paddle** — Ein Testkauf bei Paddle lässt sich durchführen und stornieren  
  _Ort:_ §5; §6 Kriterium 3
- **[mittel/preis] Solidon Preismodell (eigene Website, aber öffentlich nachprüfbar)** — Einführungspreis 49 € als Einmalkauf, bisher beworben als „14 Tage kostenlos testen, danach Einmalkauf 49 €“  
  _Ort:_ §1.2 Website-Stellen; §3 D4 Punkt 3
- **[hoch/recht] Fernabsatzrecht / Widerrufsrecht (BGB §§ 312g, 355)** — Widerrufsbelehrung greift ohne entgeltlichen Vertrag nicht; AGB beschreiben einen noch nicht existierenden Vorgang  
  _Ort:_ §2 H; §3 D3 Punkt 2
- **[mittel/recht] Schenkungs-/Leihrecht BGB (Haftungsmaßstab)** — Haftung wie bei unentgeltlicher Überlassung für eine befristete, kostenlose Demo  
  _Ort:_ §3 D3 Punkt 1
- **[mittel/recht] DSGVO / Server-Logs netcup** — Datenschutztext muss Update-Abfrage und Download-Logs (IP, Zeitpunkt im netcup-Server-Log) ausweisen  
  _Ort:_ §2 G; §3 D3 Punkt 3
- **[niedrig/api] RFC 8032 (EdDSA)** — Ed25519-Prüfkern gegen RFC-8032-Vektoren  
  _Ort:_ §1 Tabelle, Zeile Prüfkern
- **[mittel/funktionsumfang] Ollama** — Der Chat braucht ein Sprachmodell: entweder Ollama lokal (ein Befehl) oder ein eigener API-Schlüssel  
  _Ort:_ §2 E
- **[mittel/funktionsumfang] OpenSCAD / ComfyUI / OCP (OpenCASCADE) / V-HACD** — Externe Werkzeuge OpenSCAD, Ollama und ComfyUI müssen fehlen dürfen; Paketierung braucht OCP und V-HACD  
  _Ort:_ §3 D8 Punkte 3 und Abnahme
- **[mittel/api] pytest-forked / GitHub Actions ubuntu-runner** — pytest --forked bzw. mehrere Aufrufe als Rückfallweg gegen Segmentierungsfehler auf dem Ubuntu-Runner  
  _Ort:_ §3 D7 Punkt 3
- **[niedrig/funktionsumfang] PyInstaller / Inno Setup 6** — PyInstaller und Inno Setup als Paketierungsweg für Windows, tar.gz für Linux  
  _Ort:_ §1 Tabelle Paketierung; §3 D7 Punkt 4
- **[mittel/api] SPF / DMARC (solidon3d.de)** — support@solidon3d.de eingerichtet; SPF und DMARC noch gegen eine Testmail von außen zu prüfen  
  _Ort:_ Vorgaben-Kasten oben; §1.1 Schluss; §3 D5

## Intern prüfbare Behauptungen (15)

- **[hoch]** P0–P15 durch, 77 Operationen, drei Hauptwege als Ende-zu-Ende-Tests  
  _Prüfen:_ ROADMAP.md-Phasenstand lesen; Op-Zahl aus dem Register zählen (Registereinträge in app/core/registry/ bzw. Registerkonsistenztest); AGENTS.md/Bauplan §2.2 nennt vier Hauptwege — Widerspruch prüfen  
  _Ort:_ §1 Tabelle, Zeile Anwendung
- **[mittel]** Vier Stellen im Datenpfad rufen require()  
  _Prüfen:_ grep nach require( in app/core/ und tests/test_licence_boundary.py ausführen  
  _Ort:_ §1 Tabelle, Zeile Lizenzgrenze; §2 B
- **[mittel]** Prüfmodul mit Cython kompiliert, signiertes Manifest über vier Grenzdateien, am Paket belegt  
  _Prüfen:_ packaging/-Spec und Build-Schritte ansehen, tests/test_packaging.py laufen lassen  
  _Ort:_ §1 Tabelle, Zeile Härtung; §2 C
- **[niedrig]** Handbuch hat 33 Seiten und 28 Abbildungen  
  _Prüfen:_ .venv\Scripts\python.exe tools/make_manual.py laufen lassen und Seiten-/Abbildungszahl gegen app/core/figures.py prüfen  
  _Ort:_ §1 Tabelle, Zeile Handbuch
- **[hoch]** store.TRIAL_DAYS = 14, kein Stichtag vorhanden; Licence trägt kein expires_on  
  _Prüfen:_ app/core/activation/store.py und key/licence-Datenklasse lesen — laut §10 inzwischen überholt (DEMO_UNTIL existiert)  
  _Ort:_ §1.1 Punkt 1
- **[hoch]** Es ist nie ein Paket auf einem fremden Rechner gelaufen (V6 Punkt 3 offen, D8 offen)  
  _Prüfen:_ §10-Fortschrittstabelle und ROADMAP.md-Demo-Abschnitt gegenlesen; ggf. Robert fragen  
  _Ort:_ §1.1 Punkt 2; §3 D8; §10
- **[hoch]** Kein Menüeintrag zum Suchen nach neuen Fassungen; updates.check() schweigt in zwei von drei Fällen (main_window.py:4202 und :4222)  
  _Prüfen:_ app/ui/main_window.py an den genannten Zeilen lesen — laut §10 durch D5 (Commit 1c50fab) erledigt  
  _Ort:_ §1.1 Punkt 3; §2 G
- **[hoch]** 205 Commits sind nicht gepusht, origin/main steht auf dem 06.08., letzter grüner CI-Lauf 02.08., Segmentierungsfehler (139) in app/ui/panels.py::show_document aus tests/test_operation_ui.py  
  _Prüfen:_ git log origin/main..main --oneline | Measure-Object; gh run list für .github/workflows/build.yml  
  _Ort:_ §1.2 c; §3 D7
- **[hoch]** package hängt an needs: suite — ohne grüne Suite kein Artefakt  
  _Prüfen:_ .github/workflows/build.yml lesen  
  _Ort:_ §1.2 c
- **[mittel]** Setup-Bau war kaputt (dist/Solidon vs. dist/Solidon3D) und Handbuchbilder fehlten im Paket — beides am 12.08. behoben  
  _Prüfen:_ tools/make_installer.py, die PyInstaller-Spec in packaging/ und tests/test_packaging.py prüfen  
  _Ort:_ §1.2 d und e
- **[hoch]** Zeilengenaue Fundstellen der Testlauf-Texte: website/index.html:84,670; en/index.html:85,664; agb.html:34,50; eula.html:39–40; widerruf.html:28; app/ui/first_run.py:119; store.py:35  
  _Prüfen:_ Die genannten Dateien an diesen Zeilen lesen; laut §10 sind D3 und D4 fertig, die Zeilennummern also vermutlich verschoben  
  _Ort:_ §1.2 „Was heute falsch auf der Seite steht“
- **[hoch]** D1 schreibt Fassung 0.9.0 vor, §10 nennt 0.1.0 als gebaute Fassung an sieben Stellen  
  _Prüfen:_ app/branding.py APP_VERSION und pyproject.toml version vergleichen; test_the_version_is_the_same_in_both_places_that_carry_it laufen lassen; website/version.json ansehen  
  _Ort:_ §3 D1 gegen §10 Schlussabschnitt
- **[mittel]** settings.check_for_updates steht per Vorgabe auf False  
  _Prüfen:_ Einstellungsvorgaben in app/core (settings-Modul) lesen  
  _Ort:_ §2 G
- **[hoch]** Fortschrittsstand: D0–D5 fertig, D6 halb, D7 und D8 offen, D9 halb; kern.md nennt den Stichtag noch nicht  
  _Prüfen:_ .claude/rules/kern.md auf DEMO_UNTIL prüfen; genannte Commits f8ac8c1, 7c2e6d6, 1c50fab, 57d1d7b, 9a88bfa mit git show ansehen; ROADMAP.md Demo-Abschnitt  
  _Ort:_ §10 Tabelle
- **[hoch]** Vier ROADMAP-Punkte offen: Sprachkataloge ES/FR/IT/PT fehlen, Skizzen-Restpunkte, Plattenvorschlag in der Oberfläche; Paketierung sah OCP und V-HACD zuletzt nicht (ROADMAP.md:515)  
  _Prüfen:_ app/i18n/locales/ auflisten (CLAUDE.md nennt en/es/fr/it/pt bereits als vorhanden — Widerspruch); ROADMAP.md um Zeile 515 lesen  
  _Ort:_ §5; §3 D8 Abnahme