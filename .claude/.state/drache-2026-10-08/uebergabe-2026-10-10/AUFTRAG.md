# Gemeinsame Regeln für die Agenten der Sitzung „Einstellungen nach dem Modell“ (ab 10.10.2026)

Gilt zusätzlich zu `AGENTS.md`, `CLAUDE.md`, den Karten (`<verzeichnis>/CLAUDE.md`) und
Regeln (`.claude/rules/*.md`) der berührten Verzeichnisse und zu
`F:\3D Druck\output\konsolidierung-2026-10-07\AUFTRAG-PAKETE.md` (Abschnitte Bauen, Prüfen,
Eigener Ablageort, Falle). Wo sich beide widersprechen, gilt diese Datei.

## Arbeitsort
- Nur im eigenen Worktree auf dem eigenen Zweig (steht im Auftrag). Interpreter
  `F:\3D Druck\.venv\Scripts\python.exe` (Editable-Install auf den Hauptbaum!), Arbeitsverzeichnis
  ist der Worktree. Jedes Hilfsskript setzt den Worktree als erstes `sys.path`-Element und prüft
  `app.__file__`, bevor es etwas schreibt.
- Nie nach main, welle2 oder welle3 pushen, keine fremden Zweige oder Worktrees anfassen, nichts im
  Hauptbaum `F:\3D Druck` ändern (außer dem eigenen Bericht unten). Kein Revert, kein stash, kein
  reset, kein checkout über Arbeit — vorwärts beheben. Einen anderen Zweig nur mergen, wenn der
  Auftrag ihn nennt.
- Keine RM-Nummer selbst vergeben; neue Funde im Bericht als „neuer Punkt“ mit Vorschlag nennen.

## Prüfen
- **Kein volles Tor** (`suite-getrennt.sh`), **keine CI** (`gh workflow run`, `ci_start.py`).
- Je Schritt die betroffenen Tests: `tools/affected_tests.py <dateien> --run` — bevorzugt so, nicht
  von Hand: die Auswahl nimmt die Baumleser mit (`test_shared_constants.py`, Sprachregeln …;
  welle3 war einmal rot, weil eine Handauswahl sie ausließ). Meldet es „das ist die Suite“, die
  betroffenen Testdateien gezielt wählen und **immer** `test_shared_constants.py`,
  `test_language_rules.py`, `test_registry_consistency.py`, `test_toolchain.py`,
  `test_finding_ways.py`, `test_finding_actions.py`, `test_hard_rules.py`, `test_errors.py`,
  `test_core_isolation.py`, `test_interface_limits.py`, `test_value_labels.py` mitnehmen (sie lesen jeden Baum; welle4
  war am 11.10. rot, weil `test_toolchain`/`test_finding_ways` fehlten), dazu `test_translations.py`,
  `test_wording.py`, `test_directory_docs.py`, `test_roadmap.py`, `test_changelog.py` wenn
  berührt. **Jede Änderung an einem Kundentext** (Befund, Rat, Feld, Dialog, Changelog) fährt
  zusätzlich `tests/test_text_length.py` — der Importgraph findet ihn nicht (welle3 war deshalb
  einmal rot). Ohne Fenster mit
  `-m "not performance and not windowed and not rendering and not rendered"` (`rendered`
  vergleicht gegen Handbuch und Website, die erst beim Release neu entstehen — dort rot ist
  erwartbar); Fenstertests je Datei mit
  `-m "(windowed or rendering) and not performance and not rendered"`.
- Vor jedem Commit `ruff check .`, `ruff format --check .`, `mypy` (je über `-m`).
- Exit-Code direkt lesen: `befehl > datei 2>&1; echo "Exit: $?"` — nie durch eine Pipe.
- Slicer und lange Rechenläufe gepinnt (der i9 rechnet auf den Kernen 8–11 sporadisch falsch):
  `cmd //c "start /b /wait /affinity FFFFF0FF bash skript.sh" > datei` — dabei geht der Exit-Code
  verloren, also im Skript `echo "EXIT=$?"` in die Datei schreiben und von dort lesen.
- Mehrere Agenten rechnen gleichzeitig: Zeiten als CPU-Zeit messen und vergleichen, Wanduhr nur
  nennen. Ein einzelner unerklärlicher Absturz (OverflowError, SystemError, Zugriffsverletzung an
  korrekter Zeile) ist erst die Maschine — gepinnt wiederholen, bevor im Code gesucht wird.
- Nie `python -` mit Heredoc (hängt stundenlang), nie System-Python. Deutsche Texte und Pfade mit
  Backslash nur über Write/Edit, nicht durch die Shell. Eigene Prozesse nur per PID beenden.
- Echte Slicer: Wege, Profile und Eigenheiten in der Erinnerung
  `<Erinnerungen>\vergleichsprogramme-und-korpus.md`;
  vorhandene Sonden unter `F:\3D Druck\.claude\.state\drache-2026-10-08\` (Übersicht `STAND.md`),
  Matrix mit `tools/matrix_unit.py`.

## Gebündelt rechnen, druckgleich statt bitgleich (Robert, 09.10. ~23:05–23:30, gilt sofort)
Wortlaut: `F:\3D Druck\output\konsolidierung-2026-10-07\AUFTRAG-WELLE3.md`, Abschnitt
„Gebündelt rechnen“ (kommt als Regel 6 in `AGENTS.md` und Bauplan §11.1/§11.2 nach main).
- Python-Schleifen je Element (Fleck, Facette, Paar, Dreieck, Gang) im heißen Pfad als
  Feldrechnung bündeln; Speicher: Sicht statt Kopie, Felder statt Objekte je Element,
  Zwischenstände früh freigeben. Messung vorher/nachher im Wechsel (CPU-Zeit, Spitze).
- **Druckgleich** (korrigierte Fassung, Bauplan §11.2 auf Zweig `regel/druckgleich`) misst nur
  eine Änderung: Stand nach der Beschleunigung gegen den davor und gegen den letzten
  veröffentlichten Stand. (1) Diskret gleich: Objekte und Folge, Slots, Merkmale mit Art und
  Kennung, Befunde, Fragen, Rückfallstufe, dicht nach dem Verschweißen, Stützen ja/nein;
  (2) Maße und Lagen höchstens um die **Druckgrenze 2,5 µm** verschieden
  (`PRINT_LIMIT = SMALLEST_NOZZLE/40`, kleinste Düse des Druckdialogs 0,1 mm); (3) Netze bleiben
  sauber (wasserdicht, mannigfaltig, ohne Selbstdurchdringung und entartete Dreiecke),
  Import/Export in jedem Format wie vorher. **Bitgleich bleibt jeder Gleichheitsvertrag zwischen
  zwei Wegen desselben Stands:** gleicher Startwert, jede Plattform, Hilfsprozess = Prozess,
  mit = ohne Cache, örtliche = ganze Erkennung, Vorschau = Op, übersetzter Kern =
  NumPy-Rückfall; Projektdateien inhaltsgleich; ändern sich gespeicherte Bits, steigt
  `cache_version`. Größte Abweichung im Bericht nennen.
- Gerechnet wird in float64; float32/int32 beim Halten von Netzen baut nur RM-698 — nicht selbst
  umstellen.
- Eine Leistungs- oder Speicherverbesserung im eigenen Gebiet wird gleich umgesetzt (Messung,
  Test); in fremdem Gebiet als neuer Punkt mit Messung melden.

## Budgets der Karten
`tests/CLAUDE.md` hat nur rund 290 Byte Luft (Budget 25 KB, `test_directory_docs`). Wer dort eine
Zeile ergänzt, verschiebt im selben Zug eine ausführliche Fassung nach
`konzepte/begruendungen/karte-tests.md`. Nach jedem Merge von welle3 `test_directory_docs.py` fahren.

## Kundenwirkung
- Kundenspürbare Änderung: ein Punkt im offenen Abschnitt `## 0.6.0` aller sechs
  `changelog/<sprache>.md`, gleiche Gliederung, je Sprache höchstens 200 Zeichen, kein Wort der
  Testfamilie (test/prueba/prova/Prüfstück), Großbuchstabe am Anfang, kurz und nicht nach KI
  (`.claude/rules/auslieferung.md`). Eine Behebung nur als Behebung, wenn die Ursache in einem Tag
  lag (`git tag --contains <ursache>`); sonst als Eigenschaft.
- Oberflächentexte über `tr()`, deutsche Quelle, alle fünf übrigen Kataloge selbst übersetzen.
- Register: Ein erledigter Punkt geht aus dem Register von `ROADMAP.md` ins Archiv
  `ROADMAP-ARCHIV.md` (Format der vorhandenen Einträge, `tests/test_roadmap.py`).

## Abschluss
- Commits mit `SOLIDON_KEIN_PUSH=1`, Meldung über Datei (`git commit -F <datei im eigenen
  Scratch>`), deutsch als Aussage über das Ergebnis, Abschluss
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; vorher `git diff --cached
  --name-only` lesen; danach `git push origin <eigener zweig>`.
- Nach jedem behobenen Befund (grün) committen und pushen — so übersteht der Stand einen Abbruch
  durch das Nutzungslimit. Muss ein Lauf mitten in roter Arbeit enden: Commit
  „Zwischenstand: …, noch unfertig“ und im Bericht sagen, was fehlt.
- Bericht **fortlaufend** nach
  `F:\3D Druck\.claude\.state\drache-2026-10-08\berichte-2026-10-10\<kürzel>.md`: je Befund
  Ursache, Änderung, Commit, Gegenprobe (am alten Stand rot, am neuen grün), Läufe mit Zahlen und
  Exit-Codes; offene Fragen und neue Punkte. Am Ende eine kurze Zusammenfassung mit Commits.
- Scratch nur unter
  `%TEMP%\claude\F--3D-Druck\b00d64ab-ed49-460e-9651-1d89ea000640\scratchpad\<kürzel>\`,
  nie unter allgemeinen Namen; fremde Ordner nie löschen.

## Reviews (Agent solidon3d-review)
- Nur lesen und messen, nichts im Worktree ändern, nichts committen. Sonden und Ausgaben im eigenen
  Scratch-Unterordner. Bericht fortlaufend nach
  `F:\3D Druck\.claude\.state\drache-2026-10-08\reviews-2026-10-10\<name>.md`, je Fund
  Schwere (schwer/mittel/leicht), Datei:Zeile, Beleg (Messung, Sonde, Gegenprobe) und Fix;
  am Ende ein Urteil „kann landen“ oder „nicht“.
