---
paths:
  - "tools/**/*.py"
  - "packaging/**"
  - ".github/workflows/*.yml"
---

# Regeln für Paket, Version und Veröffentlichung

Was **wo liegt**, sagen `tools/CLAUDE.md` und `packaging/CLAUDE.md`; der
Weg eines Releases in seiner Reihenfolge steht im Skill `/erzeugen`. Hier
steht, was dabei **einzuhalten** ist — die Entscheidungen, jede mit ihrem
Anlass. Bis zum 14.09.2026 gab es diese Datei nicht; die Regeln lagen in
Karten, Erinnerungen und Commit-Meldungen verstreut (RM-098).

## Die Version wird vor dem Bau erhöht, und nur über das Werkzeug

`tools/bump_version.py` fasst beide Orte an, die die Zahl tragen —
`app/branding.py` und `pyproject.toml` —, und läuft **vor** dem Prüfmodul
und dem Bau. Danach trüge das Paket eine Nummer, die es schon gab.
`website/version.json` bleibt dabei liegen: Sie sagt, was veröffentlicht
*ist*, und wird zuletzt hochgeladen. Ein Bau, der ausgeliefert wird, erhöht
die Version, ohne zu fragen (Robert); ein Bau zum Messen nicht.

**Der Changelog-Abschnitt der nächsten Version entsteht vor dem Sprung** und
nimmt auch unfertige Arbeit auf — `changelog/<sprache>.md`, sechs Sprachen,
Kundensprache, kein Verzeichnis der Änderungen. Der Wächter
`test_changelog` prüft nur den Abschnitt von `APP_VERSION`; seine Grenzen
(höchstens 200 Zeichen je Punkt, Großbuchstabe am Anfang, keine Bausteine mit
„test" im Namen) greifen also erst nach `bump_version` — wer vorher
schreibt, zählt selbst. Und vor jedem Punkt über einen behobenen Fehler
fragt man `git tag --contains <ursache>`: Ein Fehler, den keine
veröffentlichte Version hatte, gehört nicht in den Changelog — der Kunde
suchte ihn sonst bei sich.

## Keine Abhängigkeit ohne Lizenz, keine Lizenz ohne Nachweis am Artefakt

Regel 15 und 22 aus `AGENTS.md` gelten hier wörtlich; dazu kommt, was sie im
Paket bedeuten:

- **Untergrenze in `pyproject.toml`, feste Version in `constraints.txt`** —
  sonst installiert der nächste Klon etwas anderes als die CI. Prüfen mit
  `tools/check_env.py`; `--freeze` übernimmt lokale Versionen und erhält nur
  die in `PLATFORM_PINS` belegten Abhängigkeiten anderer Plattformen.
- **Die Stückliste kommt aus dem Kundenartefakt**, nicht aus `pip`: Eine SBOM
  aus der Entwicklungsumgebung ist eine Vorschau. `tools/make_sbom.py` liest
  PyInstallers Zielanalyse und das fertige Paket; jede native Kundendatei
  hat dort einen ausgewiesenen Besitzer, Bauwerkzeuge fehlen. Nach einer
  Änderung an Abhängigkeiten, Hooks, `hiddenimports`, `datas`, `binaries`
  oder `excludes` muss jede Zielplattform nativ bauen — der Vorschautest
  reicht nicht.
- **Ändert sich eine der Lizenz-Grenzdateien, wird das Manifest neu
  gebaut**, nicht der rote Test weggedrückt: `test_packaging` meldet dann
  „dein lokales Manifest ist alt", nicht „Repository kaputt".
- **Eine Abhängigkeitsrechnung darf sagen, dass etwas fehlt — nie, dass
  etwas weg darf.** Was aus dem Paket entfernt wird (Systembibliotheken des
  Linux-Grundbestands, die GPL-Terminalmodule), wird **benannt** und
  begründet (`make_linux_packages.HOST_PROVIDED_LIBRARIES`); die Rechnung
  prüft nur die Gegenrichtung gegen den eingecheckten Korpus, und eine
  offene Kante ist ein Fehler. „Ist überall vorhanden" ist keine Messung.

## Signieren ist ein eigener Vertrauensraum

Signiergeheimnisse gehören nicht in den Baujob. Eine prüfsummengebundene
Übergabe trennt Bauen, Freigeben und Signieren; auf Windows geht der Weg
bis auf Roberts Rechner (`tools/sign_release.py`), in die CI kommt er nicht.
Was daraus folgt:

- Neue Actions nur mit vollständiger 40-stelliger Commit-ID.
- Downloads im Workflow nur von einer unveränderlichen Veröffentlichung und
  nach Prüfsummenprüfung.
- Vor einem Signierschlüssel läuft kein Repositorycode; die Lizenzprüfung
  (`make_licence_notices --release-check`) läuft **nach** der Signatur und
  ungeschützt, und `sign_release.py` schreibt die Evidenz danach neu — der
  äußere Installer ist dann ein anderer als der, den die CI geprüft hat.
- Ein Prüfschritt, der nur am Tag läuft, ist bis zum ersten Tag eine
  Behauptung: Wer einen anbindet, fährt ihn **einmal über ein echtes
  Artefakt** (die alten Pakete liegen in `website/dl/`), und Prüfer und
  Erzeuger gehören in denselben Commit.

## Was der Kunde bekommt, ist geprüft — und zwar die verteilte Menge

- **Der Download-Kasten zeigt die fünf Plätze aus `DELIVERED`** — Setup,
  AppImage, Flatpak, beide macOS-Pakete —, nicht die Artefakte des Baulaufs;
  `tools/make_download.py` erzwingt es. Hochgeladen wird in dieser Folge:
  die Pakete einzeln und zuerst, dann die Seiten, `website/version.json`
  zuletzt — sie ist das Register, und ein Register vor der Datei verspricht
  etwas, das noch nicht liegt.
- **Vor einer Auslieferung die verteilte Menge gegen die geprüfte halten:**
  Was liegt in `website/dl/`, was verlinken die Seiten, was steht im
  Manifest? Wo die Zahlen auseinandergehen, steht eine Datei ohne Prüfer
  (die AppImage stand in keiner `version.json`).
- **Ein Fix im Manifest eines Paketformats ist kein Fix der Anwendung.** Er
  reist in den anderen Formaten weiter; die Regel gehört in den Startpfad
  (`app/ui/qt_platform.py` ist das Muster), das Manifest trägt sie zusätzlich.
- **Wer täglich baut, sieht den Cache-Fehler nie.** Der Ergebniscache trägt
  den Code-Hash im Pfad, der Kunde fährt denselben Stand wochenlang. Bei
  Verdacht den Cache absichtlich warm fahren: dieselbe Lage zweimal, mit einer
  Änderung dazwischen, die den Op-Hash nicht berührt.

## Erzeugtes läuft nicht in der CI

Bilder, Handbuch, Website-Bilder, SEO-Dateien und PDFs entstehen beim
Paketbau, nicht nach jedem Schritt — und nur die Sprachen und Bilder, deren
Grundlage sich geändert hat. Ein Test, dessen Grün an einem Erzeugerlauf
hängt, trägt `@pytest.mark.rendered` **und** einen Eintrag in
`RENDERED_TESTS` (`tests/test_toolchain.py`); `build.yml` wählt den Marker
ab. Zwischen zwei Releases ist ein rotes `test_manual` oder `test_wording`
deshalb ein Zustand, kein Fund.

Drei Fallen der Werkzeuge stehen in `tools/CLAUDE.md` („Drei Dinge, die man
einmal falsch macht"); die Karte des Pakets sagt, was in die `.spec` muss,
wenn sich etwas ändert.
