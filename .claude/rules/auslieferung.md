---
description: "Paket, Version, Lizenznachweis, Signierung und die verteilte Menge — was auf dem Release-Weg einzuhalten ist"
paths:
  - "tools/**/*.py"
  - "packaging/**"
  - ".github/workflows/*.yml"
---

# Regeln für Paket, Version und Veröffentlichung

Was **wo liegt**, sagen `tools/CLAUDE.md` und `packaging/CLAUDE.md`; den Weg
eines Releases in seiner Reihenfolge der Skill `/erzeugen`. Hier steht, was
dabei **einzuhalten** ist; das Warum steht unter denselben Überschriften in
`konzepte/begruendungen/regel-auslieferung.md`.

## Die Pflichtprüfungen geben das Paket frei

Die CI-Prüfjobs folgen `konzepte/konzept-ci-testlaufzeiten-2026-09.md`. Der
Paketbau wartet auf Qualität, jeden Teil der Kernmatrix auf jeder Plattform,
die plattformübergreifenden Fensterverträge und jede Windows-Fenstergruppe;
ein übersprungener, abgebrochener oder roter Pflichtjob ergibt keine
Paketfreigabe. Signierung und Veröffentlichung behalten ihre eigenen Grenzen.

- Die Teilmatrix eines Jobs ist genau `0 … N−1` für das `N` in seinem Aufruf;
  wer Teile dazunimmt, ändert beides zusammen.
- **GitHub-Listen werden über alle Seiten gelesen** (`sign_release.paged_listing`,
  je Seite 100): Artefakte im Installerlauf, Jobs bei der Freigabe eines rot
  beendeten Hauptbaus. Geht die Zahl nicht auf oder ändert sie sich zwischen
  den Seiten, hält der Lauf fail-closed an.
- Alle CI-Jobs haben einheitlich zwei Stunden, einschließlich Paketbau,
  Signierfolge, Releaseaktenprüfung und Diagnose; ausdrücklich begrenzte
  Prüfschritte nutzen dieselbe Frist und verlängern die Jobfrist nicht. Die
  vollständige Windows-Fenstergruppe protokolliert die Testnamen, bei einem
  stehenden Test liefert `faulthandler` nach zwei Minuten den Stapel. Ein
  Fristablauf ist ein roter Lauf und sperrt die Paketierung.
- **Der Job „Neueste Versionen“ meldet und hält nichts an**
  (`continue-on-error`; `sign_release.ADVISORY_JOBS` nimmt einen Hauptbau an,
  der nur dort rot ist). Sein Ergebnis wird gelesen und ein Rot als
  Registerpunkt übernommen — Ablauf in `/erzeugen`, Schritt „CI-Bau“.

## Der Einstieg des Pakets startet auch den Hilfsprozess des Kerns

Im Paket ist `sys.executable` die Anwendung selbst; der Hilfsprozess
(`core.geom.kernel_process`, `spawn`) startet genau sie noch einmal. Deshalb
ruft `app/ui/app.py` — der Einstieg der Spec — im `__main__`-Block zuerst
`multiprocessing.freeze_support()`, vor Absturzprotokoll und Qt; sonst öffnet
der Hilfsprozess ein zweites Fenster und die Rechnung fällt nach der
Startfrist in den Prozess zurück. `tests/test_kernel_process.py` hält die
Reihenfolge; `multiprocessing` darf nicht in die `excludes`.

**Der Paketjob startet den Hilfsprozess aus dem gebauten Paket**, direkt nach
*Bauen* und auf allen vier Runnern (`tools/check_frozen_helper.py`): eine
Boolesche bitgleich, danach weder Prozess noch Temp-Ordner.
`tests/test_packaging.py` hält den Schritt. Jeder Prozess des Pakets bekommt
vom Laufzeithaken `pyi_rth_mplconfig` einen Temp-Ordner, den erst `atexit`
wegräumt; der Hilfsprozess räumt seinen beim Start weg (`kernel_jobs.serve`),
weil er meist hart endet.

## Jedes Kundenpaket startet bei jedem Release einmal

Entscheidung Robert: auf allen unterstützten Plattformen, in jedem
Release-Lauf. `tools/check_frozen_start.py` startet wie ein erster Kunde
(leeres Profil, Erstlauf) und verlangt Fenster, gezeichnete 3D-Ansicht, ein
Ende mit 0, keinen Absturz im Absturzprotokoll, keinen überlebenden Hilfsprozess und
einen unveränderten Paketbaum; die Anwendung steht dafür
`start_check.SECONDS` lang und schließt sich selbst (`app/ui/start_check.py`).
Gestartet wird der gebaute Baum im Paketjob aller vier Runner, AppImage und
Flatpak, das installierte Windows-Setup in `build.yml` und in
`windows-signed-installer.yml` und das finale Mac-Paket nach Quarantäne,
Installer und Gatekeeper. Grund: Suite, Bau, Signatur und Notarisierung können
grün sein, während das Paket beim Kunden nach Sekunden endet. Eine Ausnahme,
die der Hauptfaden oder ein bis zum Ende beendeter Faden überlebt hat (etwa COM),
steht mit dem Vermerk des geordneten Endes im Protokoll und hält den Start nicht
an (`log.fatal_records`); eine aus einem noch laufenden Faden oder einem ohne
Python-Zustand (Treiber) zählt als Absturz.

- **Ohne Bildschirm (`--offscreen`) nur der Intel-Mac-Runner**: Sein
  Symboldienst (`iconservicesagent`) stürzt in Metal ab, jedes Fenster wartet
  dann auf ein Symbol. Eine neue Ausnahme braucht einen solchen Beleg.
- `tests/test_packaging.py` hält die Schritte samt Gegenproben; ein neues
  Paketformat bekommt seinen Start, bevor es ausgeliefert wird.

## Die Version wird vor dem Bau erhöht, und nur über das Werkzeug

`tools/bump_version.py` fasst beide Orte an, die die Zahl tragen —
`app/branding.py` und `pyproject.toml` —, und läuft **vor** dem Prüfmodul und
dem Bau; danach trüge das Paket eine Nummer, die es schon gab.
`website/version.json` bleibt liegen: Sie sagt, was veröffentlicht *ist*, und
wird zuletzt hochgeladen. Ein Bau, der ausgeliefert wird, erhöht die Version
ohne Nachfrage (Robert); ein Bau zum Messen nicht.

**Der Changelog-Abschnitt der nächsten Version entsteht vor dem Sprung** und
nimmt auch unfertige Arbeit auf — `changelog/<sprache>.md`, sechs Sprachen,
Kundensprache, kein Verzeichnis der Änderungen. `test_changelog` prüft nur den
Abschnitt von `APP_VERSION`; seine Grenzen (höchstens 200 Zeichen je Punkt,
Großbuchstabe am Anfang, keine Bausteine mit „test" im Namen) greifen also
erst nach `bump_version` — wer vorher schreibt, zählt selbst. Vor jedem Punkt
über einen behobenen Fehler steht `git tag --contains <ursache>`: Ein Fehler,
den keine veröffentlichte Version hatte, gehört nicht in den Changelog.

## Kein Release ohne frischen Bausteinnachweis

Die Website verspricht, jeder Baustein sei über seinen ganzen Maßbereich
geprüft, und der Katalog sagt es je Baustein. Vor dem Bau läuft deshalb der
Schritt **Bausteinnachweis**: `python tools/check_part_ranges.py --all` —
alle Bausteine, gleich ob ihr Abdruck passt, denn der Abdruck enthält den
Netzkern nicht (`parts/range_proof.py`), und eine Änderung dort sieht nur ein
frischer Lauf. Exit 0 und eine unveränderte oder eingecheckte
`data/part_ranges.toml` sind die Bedingung; ein gebrochener Baustein hält den
Release an, statt mit Warnung im Katalog hinauszugehen.

## Keine Abhängigkeit ohne Lizenz, keine Lizenz ohne Nachweis am Artefakt

Regeln 15 und 22 und die Checkliste „neue Abhängigkeit" aus `AGENTS.md` gelten
wörtlich; im Paket heißt das zusätzlich:

- `tools/check_env.py --freeze` übernimmt lokale Versionen in
  `constraints.txt` und erhält nur die in `PLATFORM_PINS` belegten
  Abhängigkeiten anderer Plattformen.
- **Die Stückliste kommt aus dem Kundenartefakt**, nicht aus `pip`:
  `tools/make_sbom.py` liest PyInstallers Zielanalyse und das fertige Paket;
  jede native Kundendatei hat einen ausgewiesenen Besitzer, Bauwerkzeuge
  fehlen. Nach einer Änderung an Abhängigkeiten, Hooks, `hiddenimports`,
  `datas`, `binaries` oder `excludes` muss jede Zielplattform nativ bauen —
  der Vorschautest reicht nicht.
- **Vor dem Paketieren decken Lizenzmanifest und Prüfmodul die aktuellen
  Grenzdateien.** Nach einer Änderung wird das Paar gemeinsam neu erzeugt; ein
  altes Manifest wird weder passend geschrieben noch seine Prüfung umgangen.
  Entwicklungstests prüfen den echten Manifestprüfer mit isolierten aktuellen
  und manipulierten Manifesten gegen die tatsächlichen Grenzdateien — auch
  ohne lokalen Build und ohne ein Release-Artefakt zu verändern.
- **Eine Abhängigkeitsrechnung darf sagen, dass etwas fehlt — nie, dass etwas
  weg darf.** Was aus dem Paket entfernt wird (der GTK-Stapel hinter Qts
  GTK-Erscheinungsbild, die GPL-Terminalmodule), wird **benannt** und
  begründet (`make_linux_packages.ORPHANED_LIBRARIES`); die Rechnung prüft nur
  die Gegenrichtung gegen den eingecheckten Korpus, und eine offene Kante ist
  ein Fehler. „Ist überall vorhanden" ist keine Messung.

## Signieren ist ein eigener Vertrauensraum

Signiergeheimnisse gehören nicht in den Baujob. Eine prüfsummengebundene
Übergabe trennt Bauen, Freigeben und Signieren; auf Windows geht der Weg bis
auf Roberts Rechner (`tools/sign_release.py`), in die CI kommt er nicht.

- Neue Actions nur mit vollständiger 40-stelliger Commit-ID.
- Downloads im Workflow nur von einer unveränderlichen Veröffentlichung und
  nach Prüfsummenprüfung.
- Vor einem Signierschlüssel läuft kein Repositorycode; die Lizenzprüfung
  (`make_licence_notices --release-check`) läuft **nach** der Signatur und
  ungeschützt, und `sign_release.py` schreibt die Evidenz danach neu — der
  äußere Installer ist dann ein anderer als der, den die CI geprüft hat.
- **Ein Prüfschritt, der nur am Tag läuft, ist bis zum ersten Tag eine
  Behauptung**: Wer einen anbindet, fährt ihn **einmal über ein echtes
  Artefakt** (die alten Pakete liegen in `website/dl/`), und Prüfer und
  Erzeuger gehören in denselben Commit.

## Was der Kunde bekommt, ist geprüft — und zwar die verteilte Menge

- **Der Download-Kasten zeigt die fünf Plätze aus `DELIVERED`** — Setup,
  AppImage, Flatpak, beide macOS-Pakete —, nicht die Artefakte des Baulaufs;
  `tools/make_download.py` erzwingt es. Hochgeladen wird in dieser Folge: die
  Pakete einzeln und zuerst, dann die Seiten, `website/version.json` zuletzt —
  sie ist das Register, und ein Register vor der Datei verspricht etwas, das
  noch nicht liegt.
- **Vor einer Auslieferung die verteilte Menge gegen die geprüfte halten**:
  Was liegt in `website/dl/`, was verlinken die Seiten, was steht im Manifest?
  Wo die Zahlen auseinandergehen, steht eine Datei ohne Prüfer.
- **Ein Fix im Manifest eines Paketformats ist kein Fix der Anwendung** — der
  Fehler reist in den anderen Formaten weiter. Die Regel gehört in den
  Startpfad (`app/ui/qt_platform.py` ist das Muster); das Manifest trägt sie
  zusätzlich.
- **Wer täglich baut, sieht den Cache-Fehler nie**: Der Ergebniscache trägt
  den Code-Hash im Pfad, der Kunde fährt denselben Stand wochenlang. Bei
  Verdacht den Cache absichtlich warm fahren — dieselbe Lage zweimal, mit einer
  Änderung dazwischen, die den Op-Hash nicht berührt.

## Erzeugtes läuft nicht in der CI

**Aufgenommen wird in 2K** auf dem Aufnahmeschirm; kleinere Bilder und die
Filme entstehen daraus durch Verkleinern, nie durch Hochrechnen (Robert).

Bilder, Handbuch, Website-Bilder, SEO-Dateien und PDFs entstehen beim
Paketbau, nicht nach jedem Schritt — und nur für die Sprachen und Bilder, deren
Grundlage sich geändert hat. Ein Test, dessen Grün an einem Erzeugerlauf
hängt, trägt `@pytest.mark.rendered` **und** einen Eintrag in `RENDERED_TESTS`
(`tests/test_toolchain.py`); `build.yml` wählt den Marker ab. Zwischen zwei
Releases ist ein rotes `test_manual` oder `test_wording` deshalb ein Zustand,
kein Fund.

Die Fallen der Werkzeuge stehen in `tools/CLAUDE.md`; was in die `.spec` muss,
wenn sich etwas ändert, sagt die Karte des Pakets.
