---
name: koordinieren
description: >
  Führt eine koordinierte Sitzung, in der mehrere Agenten Pakete parallel
  bauen: Stand aufnehmen, Pakete schneiden, Agenten beauftragen, Reviews
  begrenzen, über einen Integrationszweig mit einem gesammelten Endnachweis
  nach main bringen und abbauen. Benutzen bei „mach alles fertig“, bei
  mehreren offenen Paketen oder Sitzungen zugleich und beim Fortsetzen einer
  Übergabe. Einen einzelnen Punkt liefert /liefern.
argument-hint: "[optional: Übergabedatei oder Paketliste]"
allowed-tools: Agent, Bash, Read, Write, Edit, Grep, Glob, SendMessage, ListAgents
---

# Koordinieren: $ARGUMENTS

Der Koordinator baut selbst wenig. Er schneidet Pakete, hält die
Integrationslinie und entscheidet; die Agenten bauen, prüfen und berichten.
Torregel, CI-Regel und Commitweg stehen in `/pruefen` und `/liefern` und
gelten hier unverändert.

## Ablageort

Ein Ordner `output/konsolidierung-<datum>/` (nicht versioniert) trägt alles,
was die Sitzung überdauern muss:

| Datei | Inhalt |
|---|---|
| `KOORDINATION.md` | Zeitleiste, Agenten, Entscheidungen, am Ende der Übergabeabschnitt |
| `AUFTRAG-*.md` | gemeinsame Regeln aller Agenten, einmal geschrieben statt in jedem Auftrag |
| `paket-<kürzel>.md` | Bericht je Paket, vom Agenten fortlaufend geschrieben |
| `review-<kürzel>.md`, `review-<kürzel>-sonden/` | Review und seine Sonden |

**Warum:** Agenten-IDs und Kontext reisen nicht in die nächste Sitzung; die
Berichte schon. Ein Agent, der abbricht, hinterlässt so seinen Stand.

## 1. Stand aufnehmen

- Übergabe lesen, dann `git worktree list`, je Worktree Zweig, Spitze gegen
  `origin`, `git status --porcelain`. Ungesicherte Arbeit zuerst als Patch in
  den Ablageort sichern, nie verwerfen.
- `ListAgents`: Läuft eine andere Sitzung, die Abmachung aus der Übergabe
  prüfen — wer wohin pusht, welche Worktrees fremd sind, welche RM-Nummern
  wem gehören. Untätige Sitzungen nicht anschreiben; jede Nachricht kostet
  dort Nutzung.

## 2. Pakete schneiden

- Ein Paket ist ein Gebiet ohne Dateiüberschneidung mit den anderen, auf
  eigenem Zweig und Worktree (`F:\sl-<kürzel>`), abgezweigt von der
  Integrationsbasis. Was dieselben Dateien braucht, kommt in dasselbe Paket
  oder nacheinander.
- Formatversion, `CACHE_FORMAT_VERSION`/`cache_version`, `LIBRARY_VERSION`
  und Sprachkataloge berühren fast alle; das ist kein Grund zu warten, sondern
  eine Konfliktregel beim Integrieren (Abschnitt 5).

## 3. Agenten beauftragen

- **Höchstens acht zugleich**, Reviews mitgezählt — sie teilen sich
  Nutzungslimit und Maschine. Fachagent nach Gebiet (`.claude/agents/`).
- Der Auftrag nennt: Worktree, Zweig, Spitze, Bericht, eigenen
  Scratch-Unterordner, Reihenfolge der Schritte, Abnahme, und dass Review und
  Landung beim Koordinator liegen. Gemeinsames steht in `AUFTRAG-*.md`:
  - Die `.venv` ist ein Editable-Install auf den Hauptbaum — jedes
    Hilfsskript setzt den Worktree als erstes `sys.path`-Element und prüft
    `app.__file__` vor dem ersten Schreiben.
  - Nur der `.venv`-Interpreter, nie `python -` mit Heredoc (hing stundenlang
    als System-Python); eigene Prozesse nur per PID beenden; lange Läufe
    abgekoppelt starten.
  - Auf dem Paketzweig nur betroffene Tests, ruff, format, mypy; kein volles
    Tor, keine CI (`/pruefen`, `/liefern`). Die Auswahl trifft
    `tools/affected_tests.py`, nie die Hand: Sie nimmt die Baumleser mit
    (`test_shared_constants`, Sprachregeln), die eine Handliste vergisst.
  - Neue Funde nennt der Agent als „neuer Punkt“; die Nummer vergibt der
    Koordinator aus seinem Bereich.
  - Unter Volllast zählen statt messen (Aufrufe, Erkennungen), Zeiten nur im
    Wechsel alt/neu mit CPU-Zeit.
- Jeder Start, jedes Ergebnis und jede Entscheidung kommt sofort in
  `KOORDINATION.md`.

## 4. Review-Regel

- **Höchstens zwei Reviews je Paket.** Review 1 über das ganze Paket; eine
  Nachprüfung nur, wenn Review 1 mehrere mittlere oder schwere Funde hatte,
  danach keine weitere Runde. Geringe Funde werden behoben, nicht notiert.
- Review früh starten, parallel zu anderer Arbeit — es dauert bis zu zwei
  Stunden. Der Prüfer liest nur und sondiert; behoben wird im Paket.

## 5. Integrationszweig

- `welle<N>` zweigt von main ab, eigener Worktree, gehört dem Koordinator.
  Jedes Paket mergt vorher `origin/welle<N>` in sich und fährt die
  betroffenen Tests der Konfliktdateien; dann `--no-ff` in den
  Integrationszweig, je Merge die betroffenen Tests.
- Konflikte: Kataloge nach Schlüssel (`read_catalog`/`write_catalog`), nie
  zeilenweise; Versionen (Format, Cache, Bibliothek) über allen beteiligten
  Ständen mit allen Migrationen und `PartChange`-Einträgen, danach
  `tools/make_examples.py` und der Bereichsnachweis der berührten Bausteine;
  `MUSTER_BESTAND`/`UEBERSETZT_BESTAND` neu zählen, Werte dürfen nur fallen;
  Register und Archiv samt Tabellenkopf (`test_roadmap.py`); das
  Unterlagenbudget je Quelldatei (`test_directory_docs.py`).

## 6. Gesammelter Endnachweis und Landung

- Einmal auf der Spitze des Integrationszweigs: volles Tor nach `/pruefen`
  und ein Review nur über die Merge-Auflösungen. Läuft danach ein Commit,
  gilt das Tor für ihn nicht mehr.
- Dann im Hauptbaum `git merge --no-ff welle<N>` (Meldung über Datei, nennt
  Pakete, Reviews und Torzahlen), Push, CI auf main nach `/liefern`. Ein Rot
  dort wird auf main vorwärts behoben.
- Danach melden: Robert und jeder beteiligten Sitzung „main steht“; den
  nächsten Integrationszweig anlegen und ebenfalls melden.

## 7. Abbau

Nach jeder Landung die eigenen Worktrees und Zweige (lokal und `origin`),
deren Stand in main liegt (`git merge-base --is-ancestor`) und die nichts
Ungesichertes tragen. Den Integrationszweig erst, wenn kein Agent ihn noch
mergen soll. Fremde Worktrees und Zweige nie.

## 8. Pause und Übergabe

Hält Robert an: Agenten sichern ihren Stand (Commit auf dem Zweig, Push,
Bericht). Der Koordinator schreibt in `KOORDINATION.md` einen Abschnitt
„ÜBERGABE an die nächste Sitzung“: Integrationsstand, je Paket Ort, Spitze,
Stand und nächster Schritt, Abmachungen mit anderen Sitzungen,
Nummernbereiche, geltende Regeln. Dazu ein Verweis in den Erinnerungen,
der beim Abschluss wieder fällt.
