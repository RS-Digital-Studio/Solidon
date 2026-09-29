# Review Handbuchumbau (RM-283) vor dem Merge

Geprüft: `git diff f1cfff619 8d83c1c32` (Zweig `handbuch-umbau`, 30 Commits,
62 Dateien), Code und Verhalten. Die Texte der Erklärseiten (HB-9) und die
Sätze der zehn neuen Anleitungen (HB-8) sind laut Auftrag schon geprüft und
hier nur auf Verweise, Platzhalter und Struktur gelesen.

Arbeitsbäume `F:\3D Druck.review-051\wt-revhb` (auf `8d83c1c32`) und
`wt-revhbmain` (auf `f1cfff619`, nur für Vergleiche), nach dem Review wieder
entfernt; Läufe gepinnt über `skripte/lauf-wt.sh`, Protokolle unter
`laeufe\rev-hb-*.txt`. Sonden liegen im Scratchpad der Review-Sitzung und
wurden nicht eingecheckt; im Hauptbaum wurde nichts geändert. Befunde nach
Schwere geordnet.

Stand: abgeschlossen, 28.09.2026 früh.

## Urteil

**Mergebar: nein, in dieser Form.** B2 macht das Entwicklungstor im
Release-Baum rot, sobald gemergt ist (dort steht `APP_VERSION` schon auf
0.5.1). Mit B2 behoben — im Zweig oder im Merge-Commit — ist der Merge in
Ordnung: Der übrige Code ist sauber, alle gefahrenen Tests, ruff, format und
mypy auf drei Plattformen sind grün, und kein Katalogeintrag von `main` ging
verloren. **Vor dem Tag** muss B1 behoben sein, denn Changelog und README
versprechen F1 „ihren Eintrag“, und für 53 von 142 Operationen stimmt das
nicht. B3 und B4 sind je ein paar Zeilen und gehören sinnvoll dazu; B5 bis B7
können nach 0.5.1 warten.

**Hinweis für den Merge im Hauptbaum:** Die Release-Sitzung hat
`website/{,en/,es/,fr/,it/,pt/}index.html` ungesichert geändert (Zeitleiste
0.5.1), der Zweig ändert dieselben sechs Dateien an anderer Stelle („Nach der
Installation“). `git merge` verweigert sich, solange sie ungesichert sind; die
Stücke überlappen nicht, nach dem Sichern läuft der Merge ohne Konflikt
(`git merge-tree --write-tree main 8d83c1c32` = Baum des Zweigs, `main` steht
noch auf `f1cfff619`).

## Befunde

### B2 — Der Changelog 0.5.1 hat nach dem Merge 121 Punkte, das Update-Fenster zeigt 120 (blockiert den Merge in dieser Form)

**Ort:** `changelog/*.md`, Abschnitt 0.5.1, Gruppe *Handbuch und Website*
(`ac7af532f`); Grenze `app/core/updates.py:217` (`MAX_CHANGES = 120`),
Wächter `tests/test_changelog.py:201`
(`test_the_window_never_sees_more_than_it_shows`).

**Beleg:** `changelog_for("0.5.1", "de")` zählt auf `f1cfff619` 118 Punkte, auf
`8d83c1c32` 121 (der Zweig bringt drei dazu). Der Wächter prüft nur den
Abschnitt von `APP_VERSION`; auf dem Zweig steht die Version noch auf 0.5.0,
deshalb war das Tor der Handbuch-Sitzung grün. Im Hauptbaum der
Release-Sitzung steht `APP_VERSION` schon auf 0.5.1. Nachgestellt mit einem
Plugin, das die Version auf 0.5.1 setzt
(`laeufe\rev-hb-changelog051-zweig.txt`): `assert 121 <= 120`, 1 failed; auf
`f1cfff619` derselbe Lauf grün (`…-main.txt`). Dazu schneidet die Anwendung
beim Lesen der Versionsdatei nach 120 Punkten ab (`updates._changes`,
`_groups`): Der Kunde sähe den letzten Punkt der letzten Gruppe nicht — das ist
genau die Handbuch-Gruppe.

**Warum es zählt:** Nach dem Merge ist das Entwicklungstor im Release-Baum rot
(`auslieferung.md`: „wer vorher schreibt, zählt selbst“).

**Fix:** Die sieben Handbuch-Punkte auf höchstens sechs zusammenlegen (in allen
sechs Sprachen gleich, etwa den Punkt zu den kürzeren Erklärseiten mit dem zur
Gliederung von Website und PDF), dann die Presseentwürfe auf die neue Zahl
ziehen. `MAX_CHANGES` zu erhöhen verlangt laut Kommentar die Prüfung des
Update-Fensters und vergrößert die Leseschranke der Versionsdatei — kurz vor
dem Tag der schlechtere Weg.

### B1 — F1 schlägt bei 53 von 142 Operationen die falsche Seite auf (vor dem Tag beheben)

**Ort:** `app/core/manual.py:2368-2382` (`help_for`),
`app/ui/manual_window.py:573-593` (`show_page`), Ursache
`app/core/manual.py:2319-2341` (`pages`).

**Beleg:** Zwei Seitenschlüssel gibt es doppelt: `parts` (Erklärseite „Die
Bausteine“ und das erzeugte Referenzkapitel „Bausteine“) und `sketch`
(Erklärseite „Zeichnen“ und Referenzkapitel „Skizze“). `help_for` liefert für
jede nicht gelehrte Operation `spec.category` als Seite; `show_page` nimmt die
erste Seite mit diesem Schlüssel, also die Erklärseite. Dort steht der Eintrag
nicht, die Stelle wird nicht gefunden, die Seite bleibt oben.

- Sonde am echten `ManualWindow` über alle Operationen und Sprachen
  (`laeufe\rev-hb-probe-f1.txt`): in jeder der sechs Sprachen 53 Befunde,
  genau die nicht gelehrten Operationen der Kategorien `parts` (45 von 48)
  und `sketch` (8 von 10). Die übrigen 89 schlagen richtig auf und markieren.
- Über den ganzen Weg der Anwendung (Hauptfenster, `_open_operation_dialog`,
  F1-Kürzel im Dialog; `laeufe\rev-hb-probe-dialog.txt`): F1 in *Mutternfalle*
  öffnet „Die Bausteine“, F1 in *Tasche schneiden* „Zeichnen“; die Gegenprobe
  *Bohrung ändern* markiert ihren Eintrag.

Die Tests sehen es nicht: `test_f1_on_every_other_operation_finds_its_entry_in_the_reference`
(`tests/test_manual.py:538`) baut `{page.key: … for page in manual.pages()}`,
dort gewinnt die **letzte** Seite je Schlüssel (das Referenzkapitel), im
Fenster die **erste**. `test_a_page_opens_at_the_entry_it_was_asked_for`
(`tests/test_manual.py:1040`) prüft `fillet_edges`, das seit HB-8 *Kanten
abrunden oder anfasen* lehrt: `spot` ist leer, und `selectedText() == ""` ist
immer wahr — der Test prüft keinen Referenzeintrag mehr, obwohl sein Docstring
es sagt. `test_guide_keys_are_unique_and_differ_from_every_page`
(`tests/test_guides.py:38`) vergleicht Anleitungen mit geschriebenen Seiten,
nicht die erzeugten mit den geschriebenen. `make_manual._anchor` und
`test_manual_search` (`parts@G`) kennen die Kollision und lösen sie nur für
Website und Suche.

**Warum es zählt:** Konzept §7, Changelog („F1 im Dialog einer Operation
schlägt ihre Anleitung oder ihren Eintrag auf“) und README versprechen den
Eintrag; bei jedem Baustein ohne Anleitung und jeder Skizzenart außer
*Grundform hochziehen* und *An Körper anfügen* landet der Kunde oben auf
einer Erklärseite und sucht selbst.
Konzept §9 HB-7 meldet „per Sonde belegt“.

**Fix:** Seitenschlüssel eindeutig machen: Die erzeugten Kategorieseiten
bekommen `ref-<kategorie>` als `Page.key` (derselbe Wert, den `_anchor` heute
als Anker baut; `_anchor` wird dann `page.key`), `help_for` liefert diesen
Schlüssel, `manual.find("holes")` in den Tests zieht nach (in den Texten zeigt
kein Verweis auf ein erzeugtes Kapitel, der einzige `manual:sketch` meint die
Erklärseite). Dazu ein Test „kein Seitenschlüssel doppelt“, der F1-Test über
alle Operationen am `ManualWindow` statt über das Wörterbuch (die Sonde
braucht wenige Sekunden je Sprache, mit Zusicherung, dass `REGISTRY.all()`
nicht leer ist, `tests.md`), und `test_a_page_opens_at_the_entry…` auf eine
nicht gelehrte Operation aus `parts` umstellen, etwa `insert_nut_trap` — er
ist dann ohne Fix rot. `test_f1_in_the_local_editor_opens_the_manual_at_its_operation`
prüft die Markierung nur unter `if spot:`; ein `assert spot` davor hält ihn
scharf, falls `resize_hole` einmal eine Anleitung bekommt. Kleinster
Notbehelf, falls vor dem Tag keine Zeit ist:
`show_page` wählt bei gleichem Schlüssel und gesetztem `spot` die erzeugte
Seite.

### B3 — F1 im Dialog wirft die offene Anleitung an ihren Anfang zurück (vor dem Tag, klein)

**Ort:** `app/ui/manual_window.py:585-588`.

**Beleg:** Ist die Seite schon offen, setzt `show_page` den Cursor an den
Anfang, auch ohne `spot`. Bei einer gelehrten Operation ist `spot` leer.
Sonde über `MainWindow.action_manual` (`laeufe\rev-hb-probe-scroll.txt`):
Seite auf 11 005 von 22 011 gerollt; F1 im Hauptfenster lässt sie dort, der Weg
aus dem Dialog (`action_manual(seite, "")`) stellt sie auf 4.

**Warum es zählt:** Genau der Weg durch eine Bildanleitung, den
`action_manual` beschreibt: Schritt 3 von *Ein Loch bohren* öffnet *Bohrung
setzen*, der Kunde drückt im Dialog F1, um den nächsten Schritt zu lesen, und
steht wieder bei Schritt 1.

**Fix:** In `show_page` nur mit `spot` an den Anfang springen (die Suche nach
der Stelle braucht ihn); ohne `spot` bleibt die offene Seite, wo sie ist. Test:
Seite rollen, `show_page(seite, "")`, Rollwert unverändert.

### B4 — Vier Zuordnungen in `Guide.teaches` lehren die Operation nicht (vor dem Tag, klein)

**Ort:** `app/core/guides.py`, `teaches` von *Zweifarbig drucken*
(`assign_slot`, `clear_filament`), *Ein Teil beschriften* (`create_label`),
*Ein zu großes Teil teilen* (`arrange_bed`).

**Beleg:** Keiner der Schritte zeigt *Filament entfernen*, *Schriftzug als
Körper* oder *Filament zuweisen*; *Zweifarbig drucken* malt nur eine Fläche an,
*Ein Teil beschriften* setzt nur *Text aufbringen* auf eine Fläche.
*Auf dem Bett anordnen* ist ein Klick im Prüfbericht nach dem Teilen, die
Operation selbst gilt jeder Szene. F1 in diesen Dialogen führt zu einer
Anleitung, die die Frage nicht beantwortet; der Referenzeintrag täte es.
Die übrigen neunzehn Zuordnungen passen (am Schritt geprüft, auch
`drill_brep_hole` und `create_box` als Zwillinge im selben Dialog und
`sketch_join` als Variante im Dialog *Hochziehen*).

**Warum es zählt:** Konzept §7: „die Anleitung zu dieser Operation“, sonst
der Eintrag.

**Fix:** Mindestens `clear_filament` und `create_label` aus `teaches` nehmen;
`assign_slot` und `arrange_bed` nach Produktsicht entscheiden. Alle vier
stehen in Kategorien ohne doppelten Schlüssel (`colour`, `label`, `scene`),
ihr Referenzeintrag wird also schon heute richtig aufgeschlagen, B1 hängt
nicht daran.

### B5 — Welcher Teil eine Anleitung trägt, steht an zwei Stellen (nach 0.5.1)

**Ort:** `app/core/guides.py` (`Guide.part`) und `app/core/manual.py:2225`
(`OUTLINE`).

**Beleg:** „Wo fange ich an?“ (`_where_to_start_page.listed`) und die Filme
(`make_guide_video.films`) gliedern nach `Guide.part` und der Reihenfolge von
`GUIDES`; Handbuchfenster, Website und PDF nach `OUTLINE`. Heute stimmen beide
überein, kein Test hält sie zusammen (`test_guides` prüft nur, dass jede
Anleitung genau einmal in `OUTLINE` steht). Der Docstring von `Page.part` sagt
selbst: „steht deshalb an einer Stelle“.

**Warum es zählt:** `zwillinge.md`, Klasse „ungewollt“.

**Fix:** `Guide.part` aus `OUTLINE` ableiten oder umgekehrt; bis dahin ein Test,
dass Teil und Reihenfolge jeder Anleitung in beiden gleich sind.

### B6 — Die Spulennamen der Aufnahme stehen in einer festen Sprachtabelle (nach 0.5.1)

**Ort:** `tools/make_guides.py:122` (`SPOOLS`).

**Beleg:** Sechs Sprachen fest eingetragen, eine siebte bekäme englische
Spulennamen in den Bildern von *Zweifarbig drucken* (`SPOOLS.get(…, "en")`).

**Warum es zählt:** `AGENTS.md`, Sprachregelung: „Eine weitere Sprache ist eine
Datei in `app/i18n/locales/` und sonst nichts“; `app/i18n/CLAUDE.md`: feste
Sprachtabellen im Generator sind kein zulässiger zweiter Katalog.

**Fix:** `tr("PLA weiß")`, `tr("PLA rot")` und `tools/make_guides.py` in
`extract.EXTRA_SOURCES`.

### B7 — Die Agentenbeschreibungen ändern sich auf Französisch, und „Où:“ bleibt fest (nach 0.5.1)

**Ort:** `app/core/agent/tools.py:406` und `:515`, `app/core/agent/offer.py:125`
(`f"… {tr('Ort')}: …"`).

**Beleg:** Vergleich aller betroffenen Texte `f1cfff619` gegen `8d83c1c32`
(`caveat_line` mit und ohne Auszeichnung, `menu_path`, `documentation`,
`rules_text`, `tool_schemas` voll und kompakt, `ToolOffer`): in de, en, es,
it, pt Zeichen für Zeichen gleich. Auf Französisch ändern sich 41 Zeilen
„Quand ne pas le faire :“, 30 Menüwege „(avec une entité sélectionnée : …)“
und damit 66 volle und 41 kompakte Werkzeugbeschreibungen. Die Meldung sagt
„unberührt“ — das gilt für den Code, nicht für die französische Ausgabe. Im
selben Satz steht danach „Où: … (… sélectionnée : …)“, weil der Agent sein
„Ort:“ weiter fest setzt. `test_agent_suite` fährt deutsch und ist grün.

**Warum es zählt:** `uebersetzung.md`: „Vor : ; ? ! steht eines, auch wo der
Code einen Satz zusammensetzt“. Der Chat kann den Ort wörtlich weitergeben.

**Fix:** Gehört zum Registerpunkt der festen Doppelpunkte, den die Meldung
schon nennt (`print_settings_dialog.py`): `tr("Ort: {path}", path=…)` an den
drei Stellen.

## Geprüft ohne Befund

- **afc251ae4, deutsche Ausgabe:** Zeichen für Zeichen gleich (siehe B7), ebenso
  en, es, it und pt.
- **Kataloge:** Dreiwegvergleich an allen sechs Merges des Zweigs (Basis,
  Zweigseite, zusammengeführte Seite, Ergebnis) in fünf Sprachen: an keinem
  Merge ging eine Änderung von `main` verloren, kein Eintrag von `main` wurde
  still überschrieben. Am Merge `ce36836dc` stehen Änderungen, die keine der
  beiden Seiten trug (gerader Apostroph, neue Namen aus texte-051) — das ist
  der dort gemeldete Nachzug, und `main` hatte diese Schlüssel nicht geändert.
  „Gilt für“ entfernte der Zweig mit `afc251ae4`, der Merge holte es zurück,
  weil `print_settings_dialog.py` es auf `main` benutzt; der Wert ist in allen
  Sprachen der von `main`. Endstand gegen `main`: je Sprache 65 Schlüssel
  entfernt, 155 neu; geändert en 5, es 5, fr 31, it 21, pt 7, alle auf der
  Zweigseite entstanden. `test_translations` (vollständig, nichts verwaist)
  grün.
- **HB-10:** Kopf- und Fußzeile ab der ersten Seite mit laufendem Kapitel,
  gelesen aus den benannten Zielen (`_chapter_starts`, `_running_chapters`),
  `SKIP_STAMP` entfernt; Lesezeichen Teile über Kapiteln, `UseOutlines`;
  Druckkopie mit JPEG nur, wo leichter, und ohne Verweise um die
  Bildschirmfotos; zwei Druckanläufe gelten erst mit vollständiger Bildzahl.
  Tests dazu vorhanden und aussagekräftig (Gegenprobe gegen die alte feste
  Grenze wäre rot). `pypdf` ist keine neue Abhängigkeit.
- **HB-12 `tools/make_guide_video.py`:** führt keinen fremden Code aus (kein
  `eval`, `exec`, keine Shell; Regel 11). `ffmpeg` und `ffprobe` über
  `shutil.which` mit Argumentliste, die ffconcat-Liste wird selbst geschrieben
  (Pfade im eigenen Temp-Ordner, `'` maskiert), `--quelle`/`--ziel` sind
  Eingaben des Entwicklers und gehen nur als Pfad an Qt und ffmpeg. Keine neue
  Python-Abhängigkeit (Regel 22); `ffmpeg` samt `libx264` wird wie in
  `make_video.py` nur extern aufgerufen und nicht mitgeliefert (Regel 15),
  das Werkzeug reist nicht im Paket. Musik selbst erzeugt.
- **HB-11:** `test_a_way_in_a_written_page_is_the_one_the_interface_shows` hat
  eine Untergrenze (≥ 10 Wege), prüft Pfeile außerhalb eines Wegs, Anfang an
  der Menüleiste und Glied für Glied die Übersetzung.
- **HB-5:** erste Seite, Teilüberschriften (gesperrt, Pfeiltasten übergehen
  sie, zugängliche Beschreibung), Startknopf und Hilfe-Menü. F1 im Hauptfenster
  und im Bearbeitungsdialog der lokalen Suche verdrahtet; minimiertes Handbuch
  kommt zurück; Variantenwechsel im Dialog fragt die aktuelle Operation.
- **`remote_server.py`:** 403/415 verwerfen den anliegenden Rumpf wie 404,
  zeitlich (0,25 s) und in der Menge gedeckelt; die Entscheidung fällt vorher.
- **`guide_targets.py`, `panels.py`, `local_recognition*.py`, `markup.py`,
  `extract.py`, `manual_search.py`:** ohne Befund (Verweise maskiert, Ziel nur
  als Anker; Objektnamen der Kontextmenüeinträge nur als Adresse).

## Läufe

| Lauf | Ergebnis |
|---|---|
| `rev-hb-kern-a`: test_guides, test_manual, test_manual_search, test_start_screen, test_local_recognition_flow (ohne Fenster) | 235 passed, 187 deselected, Exit 0 |
| `rev-hb-kern-b`: test_translations, test_wording, test_language_rules | 574 passed, 8 deselected, Exit 0 |
| `rev-hb-kern-c`: test_remote_server, test_agent, test_agent_suite, test_registry_consistency, test_changelog, test_directory_docs, test_agent_mirror, test_core_isolation, test_hard_rules, test_shared_constants, test_interface_limits, test_toolchain, test_errors | 2231 passed, 5 skipped, 51 deselected, Exit 0 |
| `rev-hb-kern-d`: test_locked_says_why, test_operation_ui, test_parts_catalog, test_recipes, test_registry, test_spacemouse, test_theme_and_palette, test_viewport_decisions, test_website, test_cli | 920 passed, 2 skipped, 483 deselected, Exit 0 |
| `rev-hb-agentsuite`: test_agent_suite, test_changelog mit `-rs` | 135 passed, 1 skipped (Presseentwürfe: im Arbeitsbaum fehlt `marketing/`), Exit 0 |
| `rev-hb-fenster-1…10`: zehn Fenstertests des Gebiets einzeln, `faulthandler_timeout=120` | je 1 passed, Exit 0 (`test_a_page_opens_at_the_entry…` grün, aber leer, siehe B1) |
| `rev-hb-ruff`, `rev-hb-format` | All checks passed; 1045 files already formatted; Exit 0 |
| `rev-hb-mypy-win`, `-linux`, `-darwin` | je „no issues found in 330 source files“, Exit 0 |
| `rev-hb-changelog051-zweig` / `-main`: test_changelog mit Version 0.5.1 | Zweig 1 failed (121 > 120), main 48 passed; siehe B2 |
| `rev-hb-probe-f1`: F1 aller 142 Operationen am `ManualWindow`, sechs Sprachen | je 53 Befunde, siehe B1 |
| `rev-hb-probe-dialog`: F1 über Hauptfenster und Dialog für `insert_nut_trap`, `sketch_pocket`, `resize_hole` | 2 failed, 1 passed, siehe B1 (Sondentest nur im eigenen Arbeitsbaum, danach gelöscht) |
| `rev-hb-probe-scroll`: Rollstand nach F1 aus Hauptfenster und Dialog | 11 005 bleibt, 4 nach dem Dialog-Weg; siehe B3. Der Prozess endete danach beim Abbau des freistehenden Hauptfensters mit 127, die Messung stand vorher |
| `rev-hb-dump-zweig` / `-main`: alle von `afc251ae4` berührten Ausgaben je Sprache | siehe B7 und „Geprüft ohne Befund“ |

Nicht gefahren: Erzeuger (`make_guides.py`, `make_manual.py`,
`make_guide_video.py`, laut Auftrag), die `rendered`-Tests und die übrigen
Fensterdateien; die Aussagen zu HB-10 und HB-12 stützen sich dort auf Lesen
und die Kerntests.
