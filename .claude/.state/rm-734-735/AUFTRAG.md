# Auftrag 0.6.1: RM-734 und RM-735

Für eine Sitzung, die diesen Zweig (`061/suche-und-palette`) übernimmt. Diese
Datei ist vollständig; die Erinnerungen anderer Sitzungen und der Ordner
`output/` liegen nur auf deren Rechner und werden nicht gebraucht.

## Worum es geht

**RM-734 — Boolesche Operationen auffindbar.** Ein anonymer Fragebogen
(S-20261011-8c5705, 0.5.3 auf macOS) wünschte sich „Boolesche Operationen“.
*Vereinigen*, *Abziehen* und *Schnittmenge* gibt es längst; gemessen findet die
Suche „boolesch“, „Boolean“, „kombinieren“, „subtrahieren“, „Differenz“ und
„difference“ aber nichts, „Boolesche Operation“ zeigt *Fläche versetzen*.

**RM-735 — Befehlspalette entfernen.** Robert: alles soll über das
Auswahlpanel oder in der Ansicht passieren.

Plan, Befund und Messung stehen in `plan.md` und `inventur.md` neben dieser
Datei. Lies beide ganz, bevor du anfängst.

## Entscheidungen Robert (11.10.2026), verbindlich

1. Beides kommt in **0.6.1**.
2. **Die Palette geht ganz:** Menüeintrag *Bearbeiten → Befehlspalette …* und
   der Dialog (`app/ui/command_palette.py`) fallen weg. Der Knopf *Funktion
   suchen* in der Werkzeugleiste und Strg+Umschalt+P **bleiben** und setzen den
   Fokus ins Suchfeld des Auswahlpanels.
3. **Das Suchfeld des Auswahlpanels steht immer**, auch ohne Auswahl und an
   jeder Merkmalsart. Das hebt die frühere Entscheidung „ohne Auswahl kein
   Suchfeld“ auf (`.claude/rules/grenzen.md`, Abschnitt Auswahlpanel); die
   Regel wird mit RM-735 neu gefasst.
4. **Einfach, an der Wurzel, kein Workaround:** die einfachste Lösung, die die
   Ursache beseitigt; kein Sonderfall, keine Ausnahmeliste, kein
   abgeschalteter Wächter, kein `cast`/`Any` gegen die Typprüfung, kein
   `try`/`except` um ein Symptom.
5. **Lokale Fenstertests:** je Fund darf die eine Fenstertestdatei lokal
   laufen, die ihn nachstellt (vorher rot, nachher grün); die übrigen
   Fenstertests fährt die CI nach dem Push auf main.

## Was zu bauen ist

Die Einzelheiten stehen in `plan.md` (Abschnitte A und B mit „Was daraus für
RM-735 folgt“) und `inventur.md`. Kurz:

**RM-734 zuerst** (klein):
- Kundenwörter in allen sechs Sprachen (`app/core/registry/search.py`,
  `CUSTOMER_WORDS`, Kontext „Suchwörter“; Kataloge `app/i18n/locales/*.json`):
  für alle drei „boolesch; Boolesche Operation; Boolean; kombinieren“, für
  *Abziehen* zusätzlich „subtrahieren; Differenz“, je Sprache die dort üblichen
  Wörter. Der Agent bleibt unberührt (`customer_words=False`). Test zuerst in
  `tests/test_theme_and_palette.py` bzw. dort, wohin die Suchtests mit RM-735
  ziehen; die Quote der Handbuchsuche (`tests/test_manual_search.py`) vorher
  und nachher messen.
- Hinweis im Auswahlpanel: ein Körper gewählt, mindestens zwei in der Szene →
  eine Zeile, wie man zu den Booleschen kommt (Kürzel je Plattform). Keine
  grauen Knöpfe. Ablauf und Text vorher mit den Agenten `bedienlogik` und
  `oberflaechentexte`.
- Website: der Begriff „Boolesche Operationen“ auf der Funktionsseite in allen
  sechs Sprachen (`website/funktionen.html`, `website/<sprache>/features.html`).

**Dann RM-735:**
- Suchfeld des Auswahlpanels immer da; es durchsucht alle Operationen jeder
  Stufe, Erzeuger, Bausteine und Fensterbefehle; was zur Auswahl passt, steht
  vorn, was dort nicht geht, nennt seinen Sperrgrund; Rangfolge und die Zeile
  „passt nur auf einzelne Wörter“ wie bisher in der Palette (`grenzen.md`,
  Abschnitt Suche).
- Szenehandlungen (`takes_whole_scene`) alle in die Karte ohne Auswahl,
  darunter *Überschneidungen prüfen* (heute nur über die Palette erreichbar)
  und *Auf dem Bett anordnen*.
- Die elf Erzeuger, die heute nur im Menü stehen, ins Panel ohne Auswahl oder in
  die Ansicht (Liste in `inventur.md`).
- `found_in_rounds`, `matches`, `native_key`, `fold` ziehen aus
  `command_palette.py` an ihren Ort, dann fällt die Datei; `surfaces._panel_place`
  nennt die Palette nicht mehr; `main_window.py`, `selection_operations.py`,
  `settings_dialog.py`, `shortcuts_window.py`.
- Bauplan §2.6, §10, §19.2 und §40 P0 neu fassen (Ansage Robert liegt vor:
  Universalzugang sind Auswahlpanel und Ansicht); Handbuch (`app/core/manual.py`,
  Referenz „Ort: Befehlspalette → …“), Website-Handbuch aller Sprachen; Regeln
  `grenzen.md`, `oberflaeche.md`, `fenster.md`, `vorderseite.md`,
  `zeichenflaeche.md`, `agentenschicht.md`; Karten `app/ui/CLAUDE.md`,
  `app/core/registry/CLAUDE.md`; Agenten und Skills `solidon3d-op`,
  `bedienlogik`, `neue-op`, danach `tools/sync_agents.py`.
- Tests: 30 Dateien sind betroffen (Tabelle in `inventur.md`).
- Bilder: der Knopf *Funktion suchen … Strg+Umschalt+P* bleibt, die
  Handbuchbilder bleiben gültig.

## Wie gearbeitet wird

Lies vorher `CLAUDE.md`, `AGENTS.md`, die Karten der berührten Ordner und die
Regeln, deren `paths:` passen. Danach:

- Eigener Worktree für diesen Zweig. Fremde Worktrees und Zweige nie anfassen,
  nichts revertieren (`checkout`/`restore`/`reset --hard`/`clean`), vorwärts
  fixen.
- Test zuerst. Je Schritt die betroffenen Tests
  (`.venv\Scripts\python.exe tools/affected_tests.py <dateien> --run`), dazu
  ruff, format, mypy. Meldet `affected_tests` „das ist die Suite“, zusätzlich
  die Baumleser von Hand: `test_toolchain`, `test_finding_ways`,
  `test_finding_actions`, `test_hard_rules`, `test_errors`,
  `test_core_isolation`, `test_core_package_direction`,
  `test_interface_limits`, `test_value_labels`, `test_shared_constants`,
  `test_language_rules`, `test_registry_consistency`, `test_text_length`,
  `test_directory_docs`, `test_roadmap`, `test_changelog`. Das Ergebnis ist der
  Exit-Code, direkt gelesen.
- TEMP, TMP und `--basetemp` auf ein Laufwerk mit Platz legen, wenn C: knapp ist.
- Kein `python -` mit Heredoc (hängt); Skripte als Datei.
- Commit-Meldungen deutsch mit echten Umlauten, über eine Datei
  (`git commit -F`), als Aussage über das Ergebnis, mit
  `Co-Authored-By`-Zeile. `.githooks/post-commit` pusht jeden Commit auf
  `origin/061/suche-und-palette`.
- Den Stand je Arbeitstag oben in `STAND.md` neben dieser Datei festhalten
  (was fertig ist, was offen, letzter Commit), damit andere Sitzungen ihn über
  `git fetch` lesen können.

## Was nach main darf und wann

**Bis Robert „main steht“ sagt, geht nichts nach main.** Zwischen dem Tag
`v0.6.0` und dem signierten Installer darf sich main nicht bewegen. Danach
landet die Koordinationssitzung zuerst `nach/0.6.0` (Konzepte Codestruktur,
RM-722 bis RM-733, Kopf `## 0.6.1` im Changelog). Prüfbar: der Tag `v0.6.0`
steht auf origin, und `origin/main` enthält den Merge von `nach/0.6.0`.

Erst danach, auf diesem Zweig:
1. `origin/main` hereinholen (Merge, kein Rebase).
2. RM-734 und RM-735 ins Register von `ROADMAP.md` eintragen. **Die Nummern
   RM-736 bis RM-749 gehören einer anderen Arbeit (Funktionsdurchgang) und
   werden hier nicht vergeben.**
3. `plan.md` als `konzepte/konzept-suche-und-palette-2026-10.md` und
   `inventur.md` als `konzepte/nachweise-palette-2026-10/inventur.md` ablegen,
   mit Indexzeilen in `konzepte/README.md`; diesen Ordner danach entfernen.
4. Changelog unter `## 0.6.1` in allen Sprachen, als Eigenschaft beschrieben.
5. Review über den ganzen Diff mit dem Agenten `solidon3d-review`, Funde
   beheben, bei mehreren mittleren oder schweren eine Nachprüfung.
6. Das Entwicklungstor (`bash .claude/scripts/suite-getrennt.sh`, ruff, format,
   mypy), dann Merge nach main (`--no-ff`) und Push; die CI fährt danach die
   Fenstertests.
7. Kein Release, kein Tag, keine Versionsnummer — das entscheidet Robert.
