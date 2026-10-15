# Bauplan D0 (RM-737): Prüfstand, Wortschatz, Funktionsliste, Szenenkatalog, Wächter

Grundlage ist das Konzept `konzepte/konzept-funktionsdurchgang-2026-10.md` mit seinen Nachweisen. Code-Stand: main `a615f8221`.

**Voraussetzungen:**
- `doc/funktionsdurchgang` ist nach main gemergt (Konzept, RM-736 bis RM-749).
- RM-734 und RM-735 sind gebaut; offen ist bei beiden nur die Abnahme am Fenster.

## 0 Was beim Lesen auffiel und den Zuschnitt bestimmt

| # | Befund | Folge für D0 |
|---|---|---|
| B1 | `Viewport.projection` (viewport.py:9106) ist der Projektions**modus** (orthografisch oder perspektivisch). Die Rechnung „Weltpunkt → Bildpunkt“ steckt im privaten `Viewport._display_of`. | `point_for` rechnet über `_display_of`, umbenannt in `display_of`. Das ist eine Umbenennung, keine neue Definition. Mitzuziehen sind 5 Stellen in viewport.py, 2 in `tools/make_video.py` und 2 in `tests/test_viewport_decisions.py`. |
| B2 | `area_for` deckt Ziele selbst auf: `_reveal` ruft `tabs.setCurrentIndex` und `open_section`, `_in_view` ruft `ensureWidgetVisible`. Für Bildanleitungen ist das richtig. Für den Prüfstand ist es eine Abkürzung: Klicks auf Reiter und Klappen würden nicht gezählt. | Neu kommt `next_click`, der nächste Klick auf dem Weg des Kunden. `_reveal` und `next_click` lesen dieselben Hindernisse aus einer Funktion `_obstacles`, damit kein Zwilling entsteht. |
| B3 | `area_for("operation:…")` fragt zuerst `_op_actions` und wirft ohne Menüaktion. | Die Reihenfolge dreht sich: erst der sichtbare Knopf, dann die Menüaktion, sonst ein Fehler. |
| B4 | Menüzeilen haben keinen `objectName`. `window_commands` vergibt `menu.{n}` nach Lage (main_window.py:12323), also instabil (Prüfbericht S1). `guide_targets._menu_actions` und `main_window._menu_lines` lesen die Leiste doppelt (Zwilling). | `_add_action`, `_menu` und `_submenu` nehmen einen `TranslatableText` und setzen `objectName = guides.menubar_name(msgid)`. Die Schlüssel in `_menu_commands` werden dadurch stabil. Die beiden Leser werden zu `guide_targets.menubar_entries` zusammengelegt. |
| B5 | `file_acceptance` nimmt Abkürzungen: `select_feature`, `set_value_mm`, ein Klick auf `feature_panel._apply` ohne Probe, `action_undo` und `action_redo`, `_show_start_screen(False)` und ein Lesen über `getattr(window, "_preview_approval")`. | Alle Datei- und Funktionsfälle gehen über Eingabeereignisse. Abgelesen wird, was der Kunde sieht: der Text im Vorschauband. |
| B6 | Ein Klick, der einen modalen Dialog per `exec()` öffnet, kehrt erst zurück, wenn der Dialog geschlossen ist. Ein linear geschriebener Ablauf bleibt dort stehen. | Der Prüfstand ist ereignisgetrieben. Jeder Schritt läuft über `QTimer` weiter, auch in verschachtelten Schleifen (Muster `make_web_images.while_open`). |
| B7 | Systemdateidialoge lassen sich nicht skripten (Stufe C). | Der Kindprozess setzt `Qt.AA_DontUseNativeDialogs`. Der Qt-Dateidialog steht stellvertretend in Stufe A. Den echten Systemdialog prüft nur Stufe C. |
| B8 | Zwillinge, die drohen: Die V1-Negativliste deckt sich weitgehend mit `test_wording.KONSTRUKTEURSWORT` und `DESIGNER_WORD`. Die E5-Zahlen 25 und 35 stehen nur in `test_interface_limits`, die 4 als `op_dialog.MAX_FRONT_FIELDS`. Die V2-Grenzen stehen in `test_text_length.LIMITS`. | Jede Liste bekommt eine Datei in `tests/data/`, die Zahlen ziehen in die Anwendung, V2 nutzt den eingefrorenen Bestand. Keine Zweitliste. |
| B9 | `FeatureAction` hat keine stabile Kennung. An Bausteinen tragen „Maße ändern“ und „Baustein verschieben“ dieselbe `op`, „Baustein entfernen“ trägt `op=None`. | Neues Feld `key` und eine Konstante `PART_ACTION_KEYS` in `perceive/actions.py`. Dieselbe Quelle bedient Funktionsliste und Wortschatz. |
| B10 | Befundcodes wie `op.<op>.<Ausnahme>` enthalten Großbuchstaben. `guides._NAME` erlaubt nur `[a-z0-9_.]`. | Für `finding:` gilt ein eigenes Namensmuster. |
| B11 | Die Ansicht hat keinen Bildzähler (Z1). | Wie in `window_bench.wrap` wird im Kindprozess `renderer.render` umwickelt. Das ist eine Messung, kein App-Code. |
| B12 | „Gekauft“ lässt sich nicht ohne private Schlüssel als Profil vorbereiten. Für „Slicer fehlt“ und „Modell fehlt“ gibt es keinen Umgebungsschalter. | Vorbedingungen werden über dieselben Nahtstellen gesetzt wie in `tests/conftest.py`, nur im Kindprozess. Offene Frage 1 in §5. |
| B13 | Die Ladelast von `app/ui/main_window.py` liegt bei 164 846 Byte, die Grenze bei 164 863 – also 17 Byte Luft. Mitgezählt werden `AGENTS.md`, `CLAUDE.md`, `app/ui/CLAUDE.md`, `fenster.md`, `grenzen.md`, `oberflaeche.md`, `wartezeit.md` und `zwillinge.md`. Weitere Budgets: `tests.md` hat 28 Byte, `tests/CLAUDE.md` 120 Byte, `tools/CLAUDE.md` 537 Byte frei. | Der neue Satz in `AGENTS.md` wird netto gegengerechnet (§4.6). Neue Regeltexte unter `paths: app/ui/**` gibt es nicht; die Einhaltung hält ein Test. |
| B14 | Codestruktur Schritt 0 (W1, Regel 6) läuft parallel: Gelistete große Dateien bekommen keine neue Definition. Unter W4 und W5 ist ein flaches `glob` über `app/` verboten, `getattr(window, "…")` ebenso. Später ziehen `panels.py` und `main_window.py` in Pakete um. | Neuer Code steht nur in neuen Modulen. In `main_window`, `panels`, `viewport`, `print_settings_dialog`, `placement_flow` und `perceive/actions` ändern sich nur Zeilen in bestehenden Rümpfen. Die Dialogsuche liest rekursiv und ordnet nach **Klassenname** zu, nicht nach Modulpfad. |
| B15 | Kontextaktionen von Baum und Ansicht (`_add_selection_entries`), die Knöpfe zum Befund (`_show_offers`) und die Zeilen des Merkmalfensters tragen keinen Namen. Der `objectName` `actionHeading` hängt am Stylesheet. | Aktionen bekommen einen `objectName`. Widgets bekommen die dynamische Eigenschaft `guides.TARGET_PROPERTY`, weil ihr `objectName` dem Stylesheet gehört. |

## 1 Zuschnitt in fünf Teilpakete

Kein Teilpaket fasst eine Datei an, die ein anderes anfasst. Jedes läuft auf eigenem Zweig und Worktree (`F:\sl-d0w` usw.), abgezweigt vom Integrationszweig `d0/integration`. Der koordinierende Ablauf folgt `/koordinieren`.

| Paket | Gebiet | Legt an | Ändert | Hängt ab von | Tage |
|---|---|---|---|---|---|
| **D0-W Wortschatz** | Ziele, Auflösung, Kennzeichen an der Oberfläche | – | `app/core/guides.py`, `app/ui/guide_targets.py`, `tests/test_guides.py`, `app/core/perceive/actions.py`, `app/ui/main_window.py`, `app/ui/panels.py`, `app/ui/placement_flow.py`, `app/ui/print_settings_dialog.py`, `app/ui/settings_dialog.py`, `app/ui/viewport.py`, `app/ui/selection_operations.py` (nur falls die Trefferzeilen ein Kennzeichen brauchen), `tools/make_video.py`, `tests/test_viewport_decisions.py` | – | 2,5–3 |
| **D0-L Liste und Szenen** | erzeugte Funktionsliste, Paketzuordnung, Szenenkatalog, Wächter im Tor | `tools/function_list.py`, `tests/test_function_list.py`, `tests/data/function_scenes.toml`, `tests/data/function_rows/d04.toml`, `d08.toml`, `d10.toml` (Probezeilen), `tests/data/customer_vocabulary.json`, `tests/data/common_goals.toml` | `tests/data/README.md`, `tests/test_wording.py` | Schnittstellen von W (§2.1, §2.2); grün erst nach W auf dem Integrationszweig | 1,5–2 |
| **D0-P Prüfstand** | Funktionsfälle am echten Fenster: Eingabeereignisse, Probe, Messungen, Lauf, Wiederaufnahme | `tools/function_bench.py`, `tools/function_capture.py`, `tests/test_function_bench.py` | `tools/file_acceptance.py`, `tests/test_file_acceptance.py` | W (API), L (Zeilen, Szenen), U (Bericht) | 3–3,5 |
| **D0-U Urteile** | Urteil je Prüfpunkt und Kriterium, Gegenproben, Urteile, Abhakliste, Funddatei, Übereinstimmung, `rendered`-Test der Fensterbefehle | `tools/function_checks.py`, `tools/function_report.py`, `tests/test_function_report.py` | `tests/test_toolchain.py` (`RENDERED_TESTS`), `app/ui/op_dialog.py` (nimmt `MAX_LEAD_WORDS*` auf), `tests/test_interface_limits.py` | Skill-Tabellen von S (Teil 1), Protokollschema (§2.7) | 1,5–2 |
| **D0-S Unterlagen** | Skills, der Satz in AGENTS, Regel- und Kartenverweise, Gerüst der Funddatei, Verweise im Konzept | `.claude/.state/funktionsdurchgang-2026-10/funde.md` | `AGENTS.md`, `.claude/rules/tests.md`, `.claude/skills/ux-review/SKILL.md`, `.claude/skills/ui-design/SKILL.md`, `.claude/skills/pruefen/SKILL.md`, `.agents/skills/…` (nur über `tools/sync_agents.py`), `app/ui/CLAUDE.md`, `app/core/CLAUDE.md`, `tools/CLAUDE.md`, `tests/CLAUDE.md`, `tests/data/CLAUDE.md`, `konzepte/konzept-funktionsdurchgang-2026-10.md` | Teil 1 hat keine Abhängigkeit; Teil 2 (Karten) kommt nach W, L, P und U | 0,5–1 |
| Integration, Probelauf, Review | | | | alle | 1 |

### 1.1 D0-W Wortschatz – Schritte

1. **`guides.py`:**
   - `TARGET_KINDS` um die neuen Arten aus §2.1 erweitern.
   - Feste Ziele in `TARGETS` ergänzen.
   - `TARGET_PROPERTY` anlegen.
   - `menubar_name(msgid, context)` anlegen: ä→ae, klein, sonst `_`, ohne „…“.
   - `is_target` bekommt ein Namensmuster je Art (`finding:` mit Großbuchstaben).
   - `history:` bleibt als Alias für `menu:history.<x>`. Drei Anleitungen nutzen ihn, so verlieren die Bilder ihren Abdruck nicht.
2. **`perceive/actions.py`:** `FeatureAction.key` einführen (Vorgabe ist die `op`) und `PART_ACTION_KEYS = ("part.measures", "part.move", "part.remove")` als Quelle, die `part_actions` selbst benutzt. Kantenvarianten werden zu `<op>.<mode>`.
3. **`viewport.py`:** `_display_of` in `display_of` umbenennen. Eigener Commit wegen Codestruktur-Regel 5. `make_video._world_to_window` und der Test ziehen nach.
4. **`main_window.py`:**
   - `_add_action`, `_menu` und `_submenu` nehmen `TranslatableText` und setzen den `objectName`. Die rund 140 Aufrufstellen gehen von `tr(` auf `_(`, ebenso die Menüs aus Schleifen.
   - `_menu_commands` nutzt den `objectName` als Schlüssel.
   - `_menu_lines` entfällt zugunsten von `guide_targets.menubar_entries` (Zwilling zusammengelegt).
   - `_add_selection_entries` setzt `objectName = spec.name`.
   - Der Commit wird kurz gehalten, direkt nach einem Wellenschnitt (Brennpunktdatei).
5. **`panels.py`:**
   - Eigenschaft `TARGET_PROPERTY` an Kopf und Feldern jeder Handlung des Merkmalfensters (`feature:`, `edge:`, `feature.field:`), an Übernehmen, *Im Bild einstellen* und *Auf alle N gleichartigen anwenden*.
   - An jedem Knopf in `_show_offers` (`finding.action:<id>`).
   - `objectName` an den Kontextaktionen von Baum (`tree.*`), Bericht (`report.<id>`) und Parameterleiste (`parameters.*`).
6. **Weitere Kennzeichen:**
   - `placement_flow.py`: Felder der Maßgruppe (`measure.field:`) und *Bezug ändern*.
   - `print_settings_dialog.py`: Editor je `print_fields.FIELDS`-Schlüssel.
   - `settings_dialog.py`: Zeile je `searchable_options`-Schlüssel.
7. **`guide_targets.py`:** Auflöser je Art, dazu `next_click`, `point_for`, `widget_under`, `zone_of`, `search_hits`, `menubar_entries`, `RESOLVED_KINDS` (§2.2) und B3 behoben.
8. **`test_guides.py`:**
   - Ohne Fenster: `TARGETS == RESOLVED`, `TARGET_KINDS == RESOLVED_KINDS`, das Muster je Art mit Gut- und Schlechtbeispielen, `menubar_name` an Umlauten und Kontext.
   - Mit Fenster (offscreen, Fenster-CI): jede Art löst an einem vorbereiteten Zustand auf. Jede Menüzeile trägt einen eindeutigen gültigen `objectName`. Jede Kontextaktion von Baum, Verlauf, Bericht und Parameterleiste trägt einen. `next_click` liefert Reiter, Klappe, Menütitel, Untermenü, Aufklappen und Rollen in der richtigen Folge. `point_for` trifft das Merkmal: Ein Klick dort wählt es aus.

Parallel innerhalb von W: Schritt 1 und 2 zuerst (ein halber Tag). Danach laufen 3 bis 6 unabhängig, 7 und 8 am Schluss.

### 1.2 D0-L Liste und Szenen – Schritte

1. **`tools/function_list.py`** (ohne Qt-Fenster; `app.ui`-Module nur importiert, kein Widget gebaut). Daraus entstehen die Zeilen:
   - Operationen aus `REGISTRY` nach `load_operations()`; die 83 Katalogoperationen werden zu **einer** Zeile `part:*`.
   - Dialogklassen: rekursive AST-Suche unter `app/ui/` nach Unterklassen von `QDialog` und `QMainWindow`, transitiv über eigene Basen.
   - Feste Wortschatzziele, Handlungsschlüssel aus `FINDING_ACTIONS`, `PART_ACTION_KEYS`, `EDGE_VARIANTS`, `selection_operations.REBUILD` und die Fensteraktionen, Kontexteinträge des Verlaufs.
   - Dazu Paketzuordnung (§2.6), Anforderung je Operation und die Tabelle „Anforderung → Szene“ (§2.5).
   - Kommandozeile `--paket D4 --format md|json` als Übersicht für die Zeilenspezifikation.
   - Die Szenen werden aus Rezepten gebaut (`History.apply` mit `OperationDraft`, `save` nach `--out`).
2. **`tests/data/function_scenes.toml`:** Rezepte nach §2.5; schwere Szenen tragen `heavy = true`.
3. **`tests/data/function_rows/`:** drei Probezeilen, je eine pro Art: `resize_hole` (D4), Fensterbefehl `Bearbeiten/Parameter anlegen …` (D10), `finding.action:place_on_bed` (D8).
4. **`customer_vocabulary.json`:** Negativ- und Positivliste (V1), je Wort `guarded` für die Teilmenge, die `test_wording` heute hält. `KONSTRUKTEURSWORT` und `DESIGNER_WORD` werden daraus gebaut, mit gleichem Ergebnis. `common_goals.toml` enthält die häufigsten Kundenziele für I3 (§2.2 Bauplan, Fragebögen ohne Kundenkennung).
5. **`tests/test_function_list.py`** mit den Wächtern aus §4.2.

### 1.3 D0-P Prüfstand – Schritte

1. **`file_acceptance.py`:**
   - `Case` bekommt die Felder `kind` (Vorgabe `"file"`), `row` und `variant`; alte `cases.json` bleiben lesbar.
   - `inventory --functions` erzeugt die Fälle aus `function_list` und den Zeilenspezifikationen, baut die Szenen nach `<out>/scenes/` und zählt die Fensterbefehle in einem Kindprozess (offscreen) über `menubar_entries` nach `<out>/menubar.json`.
   - `child` verteilt auf `function_bench.FunctionFlow`, `report` ruft `function_report.write`.
   - Die eigenen Abkürzungen weichen (B5): Auswahl per Klick auf `tree.row:` über `next_click`, Zahlen getippt, Übernehmen über `feature.apply` mit Probe, Rückgängig und Wiederholen per Taste aus `shortcut_schemes`.
   - `function_bench` bekommt **keinen** eigenen Einstieg. Das hält ein Test, damit kein drittes Fensterwerkzeug entsteht.
2. **`function_bench.py`:**
   - Ereignisgetriebener Schrittautomat (B6).
   - Jeder Klick über `next_click` mit Probe `widget_under`; ist der Treffer weder Ziel noch Kind, ergibt das den Fund „verdeckt“.
   - Zahlen getippt mit dem Dezimalzeichen der Sprache.
   - Vorbereitetes Profil: Sprache, Thema, Einheit und Druckerprofil aus Dateien. Lizenz und äußere Vorbedingungen über die Nahtstellen der Suite im Kindprozess (B12).
   - `AA_DontUseNativeDialogs`, Fenster auf dem gewählten Schirm (`--screen`), Szenenabdruck nach §2.7.
   - Startszene nur über `open_path` oder einen Klick auf `start.new`.
3. **`function_capture.py`:** Aufnahmen am Fenster für jedes Feld des Messprotokolls (§2.7):
   - Herzschlag-Zeitgeber, Bildzähler, Modale und rohe Qt-Fenster;
   - Texte mit Breitenbedarf, Felder, Tab-Kette, Layoutmaße, Schriften, Zustandsbilder, Kontraste, Symbole, Animationen, Rollleisten;
   - Matrix der Auswahlstufen, Suchränge, Meldungen und Handlungen.
4. **Sprachfälle:** je Sprache und Paket ein Prozess, der die Flächen aller Zeilen abgeht. Sechs Sprachen in einem Prozess brechen ab (tools/CLAUDE.md); wieder aufnehmbar je Fläche.
5. **Tests** nach §4.3.

### 1.4 D0-U Urteile – Schritte

1. **`function_checks.py`:**
   - `PRUEFPUNKTE` (1 bis 19) mit Stufe und Urteilsfunktion über das Protokoll.
   - `CRITERIA` (35 Kennungen) mit Stufe und Schwelle; die Quellen der Schwellen stehen in §2.12.
   - Geschlossene Liste der *entfällt*-Gründe, `BROKEN_SAMPLES` mit je einer Gegenprobe pro Prüfpunkt.
   - `MAX_LEAD_WORDS`, `MAX_LEAD_WORDS_TRANSLATED` und `USUAL_FRONT_SHARE` ziehen nach `op_dialog.py`; `test_interface_limits` importiert sie von dort.
2. **`function_report.py`:**
   - Urteile lesen und prüfen (§2.9), Abhakliste schreiben (§2.10), Funddatei lesen und prüfen (§2.11).
   - Übereinstimmung zweier Prüfer je Prüfpunkt, Paketanteile (E2, I3).
   - Vergleich der Fensterbefehle für den `rendered`-Test.
3. **`tests/test_function_report.py`** nach §4.4; Eintrag in `RENDERED_TESTS`.

### 1.5 D0-S Unterlagen – Schritte

- **Teil 1, am ersten Tag:**
  - Kriterientabellen in `ux-review` (E, V) und `ui-design` (G, Z, I) im Format von §2.12.
  - Satz in `AGENTS.md` mit beiden Ausnahmen, Verweis in `tests.md`, Zeile in `/pruefen`.
  - Danach `tools/sync_agents.py`.
- **Teil 2, nach P und U:**
  - Karten: `tools/CLAUDE.md` mit einer Sammelzeile zu den fünf neuen Werkzeugen, die `file_acceptance`-Zeile gekürzt; `tests/CLAUDE.md` mit einer Sammelzeile, andere Zeilen gekürzt; `app/ui/CLAUDE.md` (Zeile zu `guide_targets`, Abschnitt „Testen“); `app/core/CLAUDE.md` (`guides`); `tests/data/CLAUDE.md` (Ordner `function_rows/`).
  - Gerüst von `funde.md`.
  - Konzept §4 und §7 verweisen auf die Skills und die Dateien.

### 1.6 Reihenfolge und Parallelität

| Tag | W | L | U | S | P |
|---|---|---|---|---|---|
| 1 | Grammatik, `FeatureAction.key`, `display_of` | Generator: Operationen, Dialoge, Pakete, Anforderungen | `PRUEFPUNKTE`, Protokollschema, Urteilsformat | Teil 1 (Skills, AGENTS, tests.md, `/pruefen`) | `Case`, Inventar, Schrittautomat ohne Fenster, Abdruck |
| 2 | Menüleiste mit `objectName`, Kontextaktionen | Szenenrezepte, schwere Szenen kalibrieren | Urteilsfunktionen, Gegenproben | – | Aufnahmen ohne Fenster prüfbar (Herzschlag, Tabkette, Texte) |
| 3 | Kennzeichen in panels, Dialogen, Platzierung; `next_click`, `point_for` | Wortlisten, Probezeilen, Wächter | Abhakliste, Funddatei, Übereinstimmung, `rendered`-Test | – | Datei-Fälle auf Eingabeereignisse |
| 4 | Tests am Fenster | – | – | – | Funktionsfälle am Fenster gegen W und L |
| 5–6 | – | – | – | Teil 2 (Karten) | Sprach- und Variantenfälle, Probelauf |

- **Integrationsfolge auf `d0/integration`:** S1 → W → L → U → P → S2. Danach Probelauf am echten Fenster, Review (`solidon3d-review`), Entwicklungstor, main.
- **Kritischer Pfad:** W → P (Fensterteil) → Probelauf. Vier Agenten parallel ab Tag 1 (W, L, U, S); P beginnt ohne Fenster und schließt nach W und L.
- Die Grenze „parallel höchstens zwei Pakete“ (§6) gilt für D1 bis D12, nicht für die Teilpakete von D0.

## 2 Schnittstellen

### 2.1 Wortschatz: Art, Widget und was an der Oberfläche fehlt

| Art und Name | Löst auf zu | Fehlt heute, D0-W ergänzt |
|---|---|---|
| `operation:<op>` (vorhanden) | sichtbarer Knopf der Karte, sonst Menüaktion | Knopf vor Menüaktion (B3) |
| `feature:<key>` | Kopf der Handlung im Merkmalfenster; `key` = `FeatureAction.key` (`resize_hole`, `part.move`, …) | `FeatureAction.key`; Eigenschaft am Kopf (`actionHeading` gehört dem Stylesheet) |
| `edge:<op>[.<mode>]` | Kantenzeile (`EDGE_OPERATIONS`, Varianten aus `EDGE_VARIANTS`) | Eigenschaft am Kopf |
| `feature.field:<key>.<feld>` | Eingabefeld der Handlung | Eigenschaft am Feld; heute gibt es nur einen übersetzten `accessibleName` |
| `feature.apply`, `feature.in_view`, `feature.every` (fest) | *Übernehmen*, *Im Bild einstellen*, *Auf alle N gleichartigen anwenden* | Eigenschaft; heute liegt `_apply` privat |
| `measure.field:<feld>`, `measure.reference` (fest) | Feld der Maßgruppe im Bild, *Bezug ändern* | Eigenschaft in `placement_flow` |
| `menu:<objectName>` | `QAction` in der Menüleiste (`menubar.<slug>`) oder in einem offenen Kontextmenü (`history.*`, `tree.*`, Operationsname, `report.<id>`, `parameters.*`) | `objectName` an allen Zeilen der Menüleiste (aus der Message-ID) und an den Kontextaktionen |
| `history:<x>` (vorhanden) | Alias für `menu:history.<x>` | – |
| `finding:<code>` | Zeile in `reportFindings` mit diesem Code (Muster mit Großbuchstaben) | – |
| `finding.action:<id>` | Knopf zum gewählten Befund | Eigenschaft in `_show_offers` |
| `print:<feld>` | Editor im Druckdialog (`print_fields.FIELDS`-Schlüssel, z. B. `layers.layer_height`) | Eigenschaft am Editor |
| `setting:<schlüssel>` | Zeile in den Einstellungen (`searchable_options`) | Eigenschaft an der Zeile |
| `search`, `toolbar.search` (fest) | Suchfeld der Karte (`selection_operations.search`), *Funktion suchen …* (`functionSearch`) | – |
| `progress.cancel`, `preview.banner`, `selection.rebuild` (fest) | *Abbrechen* in der Statusleiste, Vorschauband, *Modell nachbauen* (`button_for(REBUILD)`) | – |
| `handle:<rolle>` | Griffe im Bild (`move.x` bis `rotate.z`, `scale`, `slot.end`, `feature.grip`, `part.grip`) → Punkt über `point_for` aus `gizmo_reach()` und `slot_handle_feature()`; Leisten (`bar.section`, `bar.split`, `bar.analysis`, `bar.explode`, `bar.sculpt`, `bar.pose`, `bar.draw`) → Widget über ein Fensterattribut | keine neue Methode an `Viewport` |
| `tree.row:<objekt>[.<merkmal>]` | Baumzeile (Spalte 0 und 1, `UserRole`) | – |
| `history.row:<n>` | Verlaufszeile mit Anzeigenummer n (`labels.step_number`) | – |
| `view:<objekt>[.<merkmal>]` | Punkt im Bild (`point_for`) | `display_of` öffentlich (B1) |
| `dialog:<klasse_snake>` | offener Dialog dieser Klasse | – (für Kennungen der Bedienflächen) |

### 2.2 API von `guide_targets` (die eine Zuordnung)

| Funktion | Rückgabe | Zusage |
|---|---|---|
| `widget_for(window, name)` | `QWidget` | wie bisher, für alle Arten mit Widget |
| `area_for(window, name)` | `QRect`, global | wie bisher; deckt für Tour und Anleitungen auf |
| `next_click(window, name)` | `Click(rect, button, why, target)`; `why` ∈ {ziel, reiter, klappe, menue, untermenue, aufklappen, rollen} | deckt **nicht** auf; nennt den nächsten Klick des Kunden; `MissingTargetError`, wenn kein Weg bleibt |
| `point_for(window, object_id, feature_id=None)` | `QPoint`, global | eine der Kamera zugewandte Stelle auf den Dreiecken des Merkmals, nie die Achse; über `Viewport.display_of` |
| `widget_under(point)` | `QWidget` oder `None` | eine Stelle für die Probe (`QApplication.widgetAt`) |
| `zone_of(window, widget)` | str: ansicht, karte_rechts, karte_links, dialog, statusleiste, kopf, menue | für E4 |
| `search_hits(window)` | Wortschatznamen der sichtbaren Treffer in Folge | für Prüfpunkt 1 und I6 |
| `menubar_entries(window)` | (objectName, Pfadtexte, QAction) | ersetzt `_menu_actions` und `_menu_lines` |
| `RESOLVED`, `RESOLVED_KINDS` | frozenset | gleich `guides.TARGETS` und `guides.TARGET_KINDS` |

In `app/core/guides.py`: `TARGET_PROPERTY = "guideTarget"`, `menubar_name(msgid, context=None)`, `is_target` mit Muster je Art.

### 2.3 Funktionszeile (erzeugt von `tools/function_list.py`)

| Feld | Typ | Herkunft | Inhalt |
|---|---|---|---|
| `id` | str | erzeugt | Registername (`drill_hole`), Menüpfad der Quellsprache (`Datei/Speichern unter …`) oder Wortschatzname (`history:edit`, `dialog:print_settings_dialog`, `finding.action:place_on_bed`, `feature:part.move`) |
| `kind` | operation, fensterbefehl, bedienflaeche | erzeugt | |
| `source` | register, menueleiste, dialogklasse, wortschatz, befundhandlung, merkmalfenster, verlauf | erzeugt | |
| `package` | D1 … D12 | erzeugt (§2.6) | |
| `requirement` | str | erzeugt (§2.5) | z. B. `koerper:1`, `merkmal:hole`, `kante`, `leer` |
| `start_scene` | str | aus der Tabelle, überschreibbar durch die Spezifikation | Szenenschlüssel |
| `target` | Wortschatzname | erzeugt | `operation:…`, `menu:menubar.…`, `dialog:…` |
| `menu_path`, `shortcut` | str | Register oder `QAction` | Prüfpunkt 1 und 17 |
| `spec` | Zeilenspezifikation oder leer | `tests/data/function_rows/<paket>.toml` | leer heißt „ungeprüft“, nie rot im Tor |

### 2.4 Zeilenspezifikation (`tests/data/function_rows/dNN.toml`, eine Datei je Paket)

| Schlüssel | Pflicht | Inhalt |
|---|---|---|
| `[row."<id>"]` | ja | muss eine erzeugte `id` treffen, sonst rot im Tor |
| `start_scene` | nein | weicht von der Tabelle ab |
| `route` | nein | Schritte `{target, button}` für das, was `next_click` allein nicht findet (Rechtsklick auf `tree.row:…`, dann `menu:…`) |
| `example_goal`, `inputs` | ja für Stufe A | Satz („Bohrung auf 5 mm“) und getippte Werte `{feature.field:… = 5.0}` |
| `search_probes` | ja für Prüfpunkt 1 | `[{word, origin}]`, `origin` ∈ slicer, cad, fragebogen; dazu `questions` für I6; keine Kundenkennungen (der Korpus wird veröffentlicht) |
| `expectation` | ja für Prüfpunkt 4 | Kennzahlen mit `tolerance` und `origin` (Konstruktion oder Formel, `tests.md` „Korpus“) |
| `fault_case` | ja für Prüfpunkt 7 | Eingabe oder Auswahl und erwartete Art der Absage |
| `preconditions` | nein | ki, comfyui, slicer: vorhanden oder fehlt; licence: demo, gekauft, abgelaufen; printer: filament oder resin; druckhinweis: gesehen (Vorgabe im Profil jedes Falls) oder offen (nur die Zeile des Hinweises, ohne Gegenlauf) |
| `not_applicable` | nein | `{prüfpunkt = grund}`, Grund aus der geschlossenen Liste |
| `budget_s`, `budget_ref` | nein | nur mit §31-Beleg, sonst „kein Budget“ |
| `manual`, `website` | ja für Prüfpunkt 11 außerhalb des Registers | Handbuchseite (`<seite>` oder `<ref-seite>#<anker>`) und Abschnitte der Funktionsseite (`["funktionen.html#<anker>"]`, die Übersetzungen an derselben Stelle); eine Stelle, die es nicht gibt, macht P11 nicht prüfbar (`tools/function_promises.py`) |

### 2.5 Szenenkatalog und Anforderung → Szene

`tests/data/function_scenes.toml`: Je Szene stehen `ops = [{op, inputs, params, title}]`, optional `sources` (Netz aus `tests/data/meshes/`), `kernel` (exakt oder netz), `heavy` und `promises` (Merkmalsarten, Dreiecke über X, Sekunden über Y, Körperzustand). Rezepte sind Daten wie `make_examples`. Die Datei aus einem Rezept wird nicht abgelegt (`tests/data/CLAUDE.md`).

| Szene | Aufbau (Ops) | trägt |
|---|---|---|
| `leer` | neues Projekt | Erzeuger, Fensterbefehle |
| `quader.exakt` / `quader.netz` | `create_brep_box` / `create_box` | ein Körper |
| `zwei_koerper.exakt` / `.netz` | zwei überlappende Quader | ≥ 2 Eingänge, ganze Szene |
| `merkmal.<art>.exakt` / `.netz`, je Art aus `FEATURE_KINDS` (13) | Quader + `drill_hole`, `countersink_hole`, `slot_hole`, `fillet_edges`, geschlossenes `hollow_object` (void), Textur (`pattern`), Kugel, Wulst (`torus`), Gewinde (Korpus `threads/` oder Baustein), Zapfen, Schrift mit Bogen (`curved_face`), offene Fläche (`edge_loop`, nur Netz) | Merkmalshandlungen |
| `kante.*`, `kantenzug.*` | Quader (Kante), Quader mit umlaufendem Zug | Kantenoperationen |
| `offen.netz`, `mehrteilig.netz`, `hohlraum.*` | Fläche entfernt, zwei getrennte Schalen, geschlossenes Aushöhlen | `requires_body` |
| `langsam_2s`, `langsam_10s` | fein vernetzte Boolesche, kalibriert auf die Referenzmaschine | Prüfpunkte 6 und 14 |
| `ueber_erkennungsgrenze` | > `FEATURE_LIMIT_TRIANGLES` (1,5 Mio.) per Verfeinerung | §21.1, Regel-19-Frage |
| `ueber_grober_vorschau` | > `COARSE_PREVIEW_ABOVE` (150 000) | Prüfpunkt 3 |
| `halt`, `zweites_projekt` | Stapel mit scheiterndem Folgeschritt; kleiner Quader | Prüfpunkte 15 und 16 |

| Anforderung (aus dem Register) | Szene |
|---|---|
| `consumes == 0` und nicht `whole_scene` | `leer` |
| `whole_scene` oder `needed_inputs ≥ 2` | `zwei_koerper.<kern>` |
| erste Art aus `applies_to` | `merkmal.<art>.<kern>` |
| Kantenparameter (`EDGE_OPERATIONS`) | `kante.<kern>` |
| `requires_body` = open, parts, cavity | `offen.netz`, `mehrteilig.netz`, `hohlraum.<kern>` |
| sonst `needed_inputs == 1` | `quader.<kern>` |

`<kern>` ist `exakt`, wenn `requires_kind == "brep"` oder kein Netzzwang besteht, sonst `netz`. Beide Fassungen existieren. Eine neue Anforderung ohne Szene ist rot – das ist der einzige Rotfall.

### 2.6 Paketzuordnung

| Quelle | Regel |
|---|---|
| Kategorie | `import`, `export` → D1 · `primitive`, `parts`, `variants` → D2 · `boolean`, `transform`, `shaping`, `surface` → D3 · `holes` → D4 · `repair`, `mesh` → D5 · `sketch` → D7 · `scene`, `prepare` → D8 · `colour`, `label`, `fits`, `parameters` → D10 |
| Gestenparameter | Parameterart `strokes` oder `armature` → D6, vor der Kategorie |
| Fensterbefehl | Hauptmenü als Vorgabe (Datei → D1, Erzeugen → D2, Ansicht → D11, Hilfe → D12, Bearbeiten → D11), dazu eine Tabelle von Ausnahmen nach `objectName` (Einstellungen → D12, Parameter anlegen → D10, Automatisch teilen → D8, G-Code gegenprüfen → D9) |
| Dialogklasse (nach **Klassenname**, B14) | Tabelle, z. B. `PrintSettingsDialog` → D9, `SettingsDialog` → D12, `PartCatalog` → D2; unbekannte Klasse → rot (eine Zeile nachtragen) |
| Wortschatzziel | Tabelle nach Art oder Präfix: `report.*`, `finding*` → D8; `print:` → D9; `setting:`, `dialog`-Rahmen → D12; `tree*`, `history*`, `view:`, `handle:`, `search` → D11; `feature:part.*` → D2; `edge:`, `feature:` → D4; `filament.*` → D10; `start.*` → D1 |

### 2.7 Messprotokoll eines Funktionsfalls (P schreibt, U liest): `cases/<nr>/function.json`

| Feld | Inhalt |
|---|---|
| `row`, `kind`, `package`, `spec` | Zeile und Kopie der Spezifikation; U braucht `tests/data` nicht |
| `variant` | language, theme, unit, licence, preconditions, platform, screen, scale, window_size |
| `version` | Commit, App-Version |
| `scene` | key, triangles, build_s, eval_s (umgerechnet auf die Referenz) |
| `steps[]` | target, why, button, rect, point, widget_at (Klasse, objectName, Kennzeichen), hit, zone, typed, t |
| `states{}` | before, preview, applied, undo, redo, escape, cancelled, after_switch: Szenenabdruck aus Ops, Parametern, Projektparametern, Passungen und Körperabdrücken; `selection` und `camera` getrennt |
| `preview` | Körperabdrücke der Differenz, `coarse`, `banner_text`, Volumen, Außenmaß |
| `result`, `cli` | Kennzahlen; Vergleich mit dem Kommandozeilenlauf (`tests/print_equal`), größte Abweichung |
| `timing` | total_s, first_feedback_s, progress_shown_s, cancel_shown_s, main_gap_ms, budget_s |
| `frames` | Bildverzug beim Ziehen in ms, Referenzfaktor |
| `modals[]`, `raw_windows[]` | Klasse, Titel, erlaubt; Instanzen von `QMessageBox`, `QInputDialog`, `QColorDialog` |
| `messages[]` | Text und Handlungen (label, target, clicked, effect) |
| `texts[]`, `fields[]` | sichtbarer Text, Träger, Bedarf und verfügbare Breite in px, abgeschnitten; Felder mit Beschriftung, accessibleName, Beschreibung, Tooltip, vorn |
| `tab_chain[]`, `names[]`, `focus_return` | Prüfpunkt 10 |
| `matrix{}` | sechs Auswahlstufen: angeboten, grau mit Grund oder fehlt; Klick wirksam |
| `search{}` | je Probe Rang und Treffer |
| `place` | Ort (karte, menue, werkzeugleiste, kuerzel, kontext), Pfad |
| `spot` | E4: an Merkmal oder Kante `point` und `covered_by` vor dem Übernehmen; an einer Handlung am ganzen Körper `frame` der geänderten `bodies` im Ergebnisbild, `view`, `inside`, `covered_by` (`tools/function_spot.py`) |
| `layout[]`, `fonts[]`, `state_images[]`, `contrast[]`, `icons[]`, `animations[]`, `scrollbars[]` | G1–G8, Z6 |
| `hover_labels[]`, `empty_states[]` | I1, Z4 |
| `licence_runs{}`, `halt`, `insertion`, `switch` | Prüfpunkte 18, 15, 16 |
| `images[]`, `errors[]` | Pfade relativ zu `--out`, Fehler des Prüfstands |

### 2.8 Ergebnis je Prüfpunkt (U → Abhakliste)

| Feld | Werte |
|---|---|
| `point` | 1 … 19 |
| `stage` | A, B, C |
| `measurement` | Zahlen aus dem Protokoll |
| `verdict` | erfuellt, fund, entfaellt, stufe_b, nicht_gelaufen, nicht_pruefbar |
| `reason` | bei *entfällt* aus der geschlossenen Liste (ohne Rechnung, ohne Auswahlbezug, ohne Dialog, ohne Agentenwerkzeug, nur Stufe C) |
| `evidence` | Bilder und Protokollstellen |
| `finding` | FD-n, falls vergeben |

### 2.9 Urteile: `.claude/.state/funktionsdurchgang-2026-10/urteile-<paket>.toml`

Ein Eintrag `[[verdict]]` je Urteil. Die Schlüssel sind englisch (Schemata), die Werte deutsch.

| Schlüssel | Pflicht | Inhalt |
|---|---|---|
| `row` | ja | Kennung der Zeile |
| `point` oder `criterion` | ja | 1–19 oder E1 … I6 |
| `verdict` | ja | gut, gut_nach_fix, offen, entfaellt |
| `reviewer` | ja | stufe_b, zweitpruefer, stufe_c |
| `reason` | ja | Begründung |
| `image`, `place` | ja bei B | Bild relativ zum Laufordner mit `/` (`cases/002/02-flaeche.png`; aus einer anderen Runde mit deren Kennung davor, `v4:cases/001/v4-nachher.png`) und Stelle in der Oberfläche, beide ohne Laufwerkspfad |
| `no_image` | statt `image` | warum der Lauf zu diesem Urteil kein Bild hat; nie Prosa im Bildfeld |
| `finding` | bei Fund | FD-n |
| `rm` | bei *offen* | RM-Nummer, sonst abgewiesen |
| `not_applicable` | bei *entfällt* | Grund aus der Liste |
| `design_judgement` | bei G9, Z3, Z4, I1–I6 und Vergleich | `true`: Gestaltungsurteil, kein bewiesener Fehler |
| `prediction` | bei V4 | vor dem Übernehmen geschriebene Vorhersage |
| `prediction_bound` | bei V4 *gut* | Pfad (relativ zum Lauf) und SHA256 der vor dem Klick freigegebenen Vorhersagedatei; ohne Bindung ist V4 *offen* (`tools/function_verdict_rules.py`) |

Jede Runde (Kopfkommentar eines Prüfers) nennt vor ihren Urteilen den Lauf, an
dem sie urteilt, als `[[run]]`, eine Runde wiederholt ihn gleich lautend.
Bilder liegen außerhalb des Baums und auf jedem Rechner woanders; Name und
Siegel finden sie, ein Laufwerkspfad nur an einem Rechner.

| Schlüssel | Pflicht | Inhalt |
|---|---|---|
| `key` | nur für eine weitere Runde | Kennung vor deren Bildern (`v4`); ohne `key` ist es der Laufordner |
| `name` | ja | Name des Laufordners in der Ablage der Läufe (`probelauf-d0-final-2ec37b23b-fortsetzung-03`) |
| `head` | ja | Commit, an dem der Lauf maß; `report` verlangt ihn in den Protokollen |
| `seal` | ja | Datei, die den Inhalt des Laufs bindet, mit SHA256 |

Die Abhakliste nennt als Laufordner diesen Namen, nicht die bildlose Kopie,
aus der `report` liest (`report` schreibt in `--out`; der Lauf selbst bleibt
unberührt).

### 2.10 Abhakliste: `abhakliste-<paket>.md` (erzeugt, nie von Hand)

| Teil | Inhalt |
|---|---|
| Kopf | Paket, Commit, Datum, Laufordner außerhalb des Baums (Name aus `[[run]]` der Urteile, sonst `--out`), Zahl der Zeilen; *gut*, *gut nach Fix*, *offen* mit RM, *nicht geprüft* |
| Tabelle 1 | eine Zeile je Funktion: Kennung · Art · Szene · Spalten 1–19 mit `ja`, `FD-n`, `—` (entfällt), `B`, `C`, `?` (nicht gelaufen), `n.p.` (nicht prüfbar) · Urteil · Funde |
| Tabelle 2 | Kriterien, die nicht erfüllt sind, je Zeile (Kennung, Messwert, Schwelle, FD) |
| Paketwerte | E2-Anteil, I3-Anteil, I4-Zahl; Übereinstimmung der Prüfer je Prüfpunkt über die Runde (alle Pakete mit demselben Laufordner, Schwelle 90 %, bindend), je Paket als Auskunft, Zellen ohne Gegenurteil markiert (`tools/function_agreement.py`) |

### 2.11 Funddatei: `.claude/.state/funktionsdurchgang-2026-10/funde.md`

Je Fund eine Überschrift `### FD-<n> <Kurztitel>`, Nummern werden nie wiederverwendet. Darunter:

| Feld | Werte |
|---|---|
| Art | Leistung, Stabilität, Fehler, Zwillinge, Aufräumen, Einfachheit, Verständlichkeit, Gestaltung |
| Schwere | schwer, mittel, leicht, Vorschlag (I ohne Bauplanzusage; G9 höchstens leicht) |
| Funktion, Prüfpunkt oder Kriterium | Kennung der Zeile, Nummer |
| Beleg | Bild, Kennzahl, Schrittfolge |
| Ursache, Vorschlag, Wirkung beim Kunden | Sätze |
| Stand | offen RM-…, behoben `<commit>`, gut nach Fix `<lauf>` |

### 2.12 Kriterien in den Skills und Quelle der Schwellen

Jedes Skill erhält eine Tabelle mit den Spalten `Kennung | Zählgröße | Schwelle | Stufe | Messung (Feld im Protokoll)`. Sie ist die eine Quelle für Menschen. Wo es eine Codequelle gibt, nimmt U deren Wert. Neue Zahlen stehen als Konstante in `function_checks.py`, und ein Test in U hält Skill-Text und Konstante gleich (gehaltener Zwilling mit Wächter, `zwillinge.md`).

| Schwelle | Quelle |
|---|---|
| E5: 4 und 3 Felder, 25 und 35 Wörter | `op_dialog.MAX_FRONT_FIELDS`, `MAX_LEAD_WORDS*` (Umzug aus `test_interface_limits`) |
| G2 `SPACE`, G4 `LEVELS`, G8 110–220 ms | `style.SPACE`, `style.LEVELS`, `motion.ACCENT_MS`, `MEDIUM_MS` |
| G6 4,5 und 3,0 | `theme.contrast_ratio` mit Konstanten in `function_checks` (Wächter) |
| V1 | `tests/data/customer_vocabulary.json` |
| V2 | `tests/data/text_lengths/` (eingefrorener Bestand) |
| Z6 1280 × 820 | Startgröße des Fensters; 1366 × 728 und 100/150/200 % als Konstanten (Wächter) |
| E1, E3, E4, E6, E7, V6, Z1 (33 ms), Prüfpunkt 6 (100 ms), E2 (90 %), I3 (80 %) | `function_checks.py` (Wächter gegen das Skill) |

### 2.13 Kommandozeile des Prüfstands (nur `tools/file_acceptance.py`)

| Befehl | Wirkung |
|---|---|
| `inventory --functions --out <ordner> [--package D4] [--rows …] [--variants basis,sprachen,zoll,lizenz,skalierung,dunkel]` | Fälle aus Funktionsliste und Spezifikationen, Szenen nach `<out>/scenes/`, Menüleiste nach `<out>/menubar.json` |
| `run --out … [--first --last --again --timeout] [--screen <name oder index>]` | je Fall ein Prozess mit eigenem Profil; wieder aufnehmbar |
| `report --out … [--package] [--verdicts <pfad>] [--checklist <pfad>]` | Zusammenfassung, Ergebnisse je Prüfpunkt, Abhakliste; Ausgang 1 nur bei ungültigen Eingaben |

## 3 Prüfpunkte und Kriterien: wer misst, welche Gegenprobe

Alle Gegenproben laufen ohne Fenster in `tests/test_function_report.py`. Sie speisen ein absichtlich kaputtes Protokoll oder Urteil ein und verlangen Rot.

### 3.1 Prüfpunkte 1–19

| # | Stufe | Messung (Protokoll) | Gegenprobe, die rot wird |
|---|---|---|---|
| 1 Auffindbar | A (B: Herkunft der Proben) | `place` über `next_click` vom Startzustand; `search` mit getippten Proben, Rang aus `search_hits` | Probe auf Rang 4; Weg mit `MissingTargetError` gibt Fund „nicht auffindbar“ (schwer) |
| 2 Weg | A zählt, B urteilt | `steps`: Klicks inklusive Wegklicks, Tasten, getippte Felder, Entscheidungen, Zonenfolge | 4 Klicks an einer Körperhandlung (E1 über der Schwelle); fehlende `steps` ergeben „nicht gemessen“, nie „gut“ |
| 3 Vorschau | A | `preview`: Abdruck gegen Übernommenes; über `COARSE_PREVIEW_ABOVE` der Satz im Band | ungleiche Abdrücke; grobe Szene ohne Bandsatz |
| 4 Ergebnis | A | `result` gegen `expectation`; `cli` druckgleich | Volumen außerhalb der Toleranz; Kommandozeilennetz mit verschobener Ecke; Erwartung ohne Herkunft |
| 5 Rückweg | A | `states`: Rückgängig = vorher, Wiederholen = übernommen, Escape und Abbrechen = vorher bei gleich langem Verlauf, nur an Zeilen mit Entwurf oder Dialog (`unmeasured`: `NO_DRAFT` und `WITHOUT_DIALOG`); Tasten aus `shortcut_schemes` | Rückgängig ≠ vorher; Escape mit gewachsenem Verlauf. Nur die Auswahl verschieden: Vermerk, nicht rot |
| 6 Rückmeldung und Zeit | A | `timing`: Lücke ≤ 100 ms; ab 0,2 s Zeiger, ab 2 s Balken und *Abbrechen*; Budget überschritten = Verdacht | Lücke 150 ms; Lauf von 3 s ohne sichtbares *Abbrechen* |
| 7 Fehlerweg | A misst, B (V5-Wortlaut) | `fault_case`, `messages[].actions` geklickt und wirksam | Meldung ohne Handlung; Handlung ohne Wirkung |
| 8 Verständlich | A (V1–V3, V6 Handbuch), B (V4–V6, Gesamturteil) | `texts`, `fields`, Handbuchfenster geöffnet | Negativwort; Feld ohne eigenen Satz; B „gut“ trotz V1-Treffer |
| 9 Sprachen und Darstellung | A (Textpassung in sechs Sprachen, Zoll), B (Regel 18 am Bild, jeder sichtbare Text im ganzen Fenster) | Sprachfälle: `texts` mit Bedarf und Platz (umbrochene Listenzeile: `axis` Höhe); Zolllauf; Bilder auf Deutsch hell und in der längsten Übersetzung | Bedarf über Platz; umbrochene Zeile höher als ihre Zelle; „mm“ an einem Längenwert im Zolllauf |
| 10 Tastatur | A | `tab_chain` per Tastendruck und `focusWidget()` mit `name` (wie ein Bildschirmleser liest), `class`, `mark`, `primary`; `names`, `focus_return`; Bildschirmleser wird als „ungeprüft“ vermerkt | Rücksprung in der Kette; doppelter Name; Klassenname als Name; Kette ohne Zielhandlung (Hauptknopf oder Ziel der Zeile); leere Kette ergibt „nicht gemessen“; Fokus kommt nicht zurück |
| 11 Versprechen | A (Fundstellen), B (Inhalt) | `manual.help_for`, Treffer auf `website/funktionen.html` und `website/{en,es,fr,it,pt}/` samt `alt` und `title`; außerhalb des Registers `spec.manual`, `spec.website` | Operation ohne Handbuchstelle; Fundstelle der Spezifikation, die es nicht gibt; B-Urteil ohne Bild oder Stelle wird abgewiesen |
| 12 Nachträglich ändern | A | `menu:history.edit` und Doppelklick auf `history.row:<n>`; an einer Zeile, die einen Projektparameter anlegt, `parameters.first.label` rechts mit `menu:parameters.edit` und Doppelklick auf `history.last`, Verlaufslänge dort die Zahl der Parameter; Felder = Parameter; Verlaufslänge gleich | Verlauf gewachsen; Feldwert ≠ Parameter; ein Weg öffnet nichts |
| 13 Auswahlstufen | A misst, B (gegen `grenzen.md`) | `matrix` über sechs Stufen | grau mit leerem Grund; angeboten ohne Wirkung |
| 14 Abbruch | A | `langsam_2s`: *Abbrechen* sichtbar, Klick auf `progress.cancel`, Stand = vorher, wartendes Übernehmen verfällt | Abdruck nach Abbruch ≠ vorher; Szene unter 2 s ergibt „nicht prüfbar“, nie grün |
| 15 Halt und Einfügemarke | A | `halt`: Grund mit Schrittnummer; Einfügen über `menu:history.insert`: Ergebnis davor oder Absage mit *Einfügen beenden* | Grund ohne Nummer; Absage ohne Handlung |
| 16 Projektwechsel | A | Wechsel über *Datei → Zuletzt geöffnet* während Vorschau, Entwurf und Rechnung, soweit die Zeile die Lage hat (`function_checks.SWITCH_ABSENT` je Lage unter `unmeasured.switch`; keine Lage: *entfällt* ohne Rechnung); `switch.late_events` | ein später Befund oder Dialog nach dem Wechsel |
| 17 Agentenweg | A ohne Fenster | `menu_path` aus `tool_schemas()` gegen `place`, an Zeilen außerhalb des Registers Ort und Weg des Zusatzwerkzeugs, das sie nennt (`agent.tools.extra_tool_rows`, `extra_tool_place`; Ort `leiste` gegen Karte oder Kontextmenü); Rücknahme des Vorschlags über die Agenten-Suite (Skriptmodell), nur verwiesen | Menüpfad „Datei → …“ bei Ort Karte |
| 18 Lizenzzustand | A | `licence_runs`: Demo abgelaufen, Testlauf abgelaufen, gekauft | schreibendes Ziel freigegeben trotz Ablauf; grau ohne Grund |
| 19 Gestaltung | A, B und C nach §3.3 | | je Kriterium nach §3.3 |

Auslegung nach der Zweitprüfung am finalen Lauf (Abweichungsbericht §4.1):
Prüfpunkte 9 und 11 und *gut nach Fix* im Konzept §4 (Tabelle der Prüfpunkte,
„Urteil und Schwere“), E1–E4, V1 und V4 unter der Kriterientabelle im Skill
`ux-review`, Z3, I1 und I4 unter der im Skill `ui-design`.

### 3.2 Einfachheit und Verständlichkeit

| Kriterium | Stufe und Messung | Gegenprobe |
|---|---|---|
| E1 Klicks ≤ 3, am Merkmal ≤ 2 | A: `steps`; B urteilt | 4 Klicks; 3 nach der Auswahl an einer Merkmalszeile |
| E2 Pflichteingaben ≤ 1 bei 90 % | A: getippte Felder; Anteil je Paket | 2 von 10 Zeilen mit 2 Eingaben ergibt 80 % |
| E3 Entscheidungen mit Vorwissen ≤ 1 | A zählt Entscheidungen, B wertet das Vorwissen | mehr als eine Entscheidung ohne B-Urteil ergibt „B offen“, nie gut |
| E4 Blickwechsel ≤ 2, kein Verdecken | A: Zonenwechsel; Dialogrechteck gegen `point_for` | 3 Wechsel; Dialog über der Stelle |
| E5 Felder und Wörter vorn | A am offenen Dialog oder Merkmalfenster | 5 Felder; 26 deutsche Wörter |
| E6 Nachfragen außerhalb Regel 19 = 0 | A: `modals` gegen die Ausnahmeliste | `QMessageBox` nach Übernehmen |
| E7 Sackgassen = 0 | A: gesperrt ohne Grund, leere Karte ohne Satz, Meldung ohne Handlung | gesperrter Knopf mit leerem Tooltip |
| V1 Negativliste = 0 | A: `texts` gegen die Wortliste | „wasserdicht“ |
| V2 Satzlängen | A: sichtbarer Text im eingefrorenen Bestand | Text aus `text_lengths/` ergibt einen leichten Fund |
| V3 Felder mit eigenem Satz | A: Tooltip oder Beschreibung, höchstens halbe Wortüberschneidung mit dem Titel | Satz gleich Titel |
| V4 Vorhersage | B mit `prediction` | V4-Urteil ohne `prediction` wird abgewiesen |
| V5 Meldungen | A: Handlung wirksam (Prüfpunkt 7); B: Wortlaut | Meldung ohne Handlung |
| V6 Kurzhilfen ≤ 1, nie Handbuch | A: Handbuchfenster geöffnet; B: Zahl der Kurzhilfen | `ManualWindow` im Protokoll |

### 3.3 Gestaltung, zeitgemäß, innovativ

| Kriterium | Stufe und Messung | Gegenprobe |
|---|---|---|
| G1 Hauptknöpfe und Akzent | A: `isDefault()` und halbfett je Dialog oder Karte | zwei Hauptknöpfe |
| G2 Abstände | A: `spacing()`, `contentsMargins()` | Abstand 6; zwei Abstände in einer Gruppe |
| G3 Ausrichtung | A: Kanten im QFormLayout, Werte rechtsbündig | Feldkanten 3 px versetzt |
| G4 Schrift | A: Größe aus `LEVELS`, kein `font-size` und keine Farbe im Stylesheet | Stylesheet `font-size: 13px` |
| G5 Zustände | A: Bildabdruck je Zustand über gesendete Ereignisse; zweite Kodierung B | Ruhe und Fokus mit gleichem Abdruck |
| G6 Kontrast | A: `contrast_ratio`, hell und dunkel | 3,9 bei normaler Schrift |
| G7 Symbole | A: Symbol aus `icons`, Tooltip mit Name und Kürzel | Symbolknopf ohne Tooltip |
| G8 Bewegung | A: Dauer der gestarteten Animationen; Lauf mit `SOLIDON3D_MOTION=0` | Animation 300 ms |
| G9 Direkt statt Formular | B (Gestaltungsurteil, höchstens leicht) | G9 als „mittel“ wird abgewiesen |
| Z1 Ziehen ≤ 33 ms | A: Zug über `handle:` oder `view:`, Bildzeitstempel, Referenzfaktor | 50 ms umgerechnet |
| Z2 Nicht-modal | A: `activeModalWidget()` nach jeder Handlung | Erfolg als Meldungsfenster |
| Z3 Am Objekt | A misst (kein Wegklick nach der Auswahl), B urteilt | Protokoll mit Klappenklick, B sagt „ja“: Widerspruch |
| Z4 Leere Zustände | B; A listet sie mit und ohne Knopf | ohne Knopf, B sagt „ja“: Widerspruch |
| Z5 Rohe Qt-Fenster = 0 | A: Instanzen im Weg | `QInputDialog` |
| Z6 Größen und Skalierung | A: 1280 × 820 und 1366 × 728 ohne Rollleiste vorn; 100/150/200 % `devicePixelRatio`; hell und dunkel gleiche Zahl Akzente | Rollleiste bei 1366 × 728; Pixmap 1,0 bei 200 % |
| Z7 Erste fünf Minuten | C (Protokoll) | Protokoll ohne Fehlklickzahl wird abgewiesen |
| I1 Name und Maß beim Überfahren | A: Überfahren über `view:` je Art; B; Bauplanzusage, Fehlen ist ein Fund | Art ohne Beschriftung, Urteil „gut“ |
| I2 Druckfolge im Band | A: Text von `preview.banner`; B | gerechnete Vorschau ohne Bandaufnahme ergibt „nicht gemessen“ |
| I3 Vorschlag statt Suche ≥ 80 % | A: `common_goals.toml`, Ziel ohne Wegklick als Hauptaktion oder Feld oben | Anteil 70 % |
| I4 Befund mit Lösung | A ohne Fenster: Befundarten mit und ohne Handlung | Zählung an {mit, ohne} ergibt 1 von 2, die andere ein Vorschlag |
| I5 Vorher und nachher | A an der D11-Zeile; B; Bauplanzusage | fehlt, Urteil „gut“ |
| I6 Sagen statt suchen | A: Frageformen der Proben, Rang ≤ 3 | Rang 5 |

## 4 Abnahme, Tests und Unterlagen je Teilpaket

### 4.1 D0-W

**Abnahme:**
- Jede Art aus §2.1 löst am Fenster auf.
- Alle Menüzeilen tragen eindeutige, gültige `objectName`; die Schlüssel von `window_commands` sind lageunabhängig.
- `next_click` deckt nie programmatisch auf.
- Eine Operation ohne Menüaktion löst über ihren Knopf auf.
- Keine neue Definition in den großen Dateien (W1-sicher).
- Kein neuer Zugriff von `guide_targets` auf private Attribute; neue Ziele laufen über Kennzeichen oder öffentliche Namen.

**Tests:**
- Im Tor: die Teile von `test_guides` ohne Fenster.
- In der Fenster-CI: die neuen Fälle in `test_guides`.
- Nachgezogen werden `test_viewport_decisions` und `make_video`.
- Dazu `test_search`, `test_text_length` (Aufrufort `_add_action`), `test_translations` (neue `_()`-Literale), `test_language_rules`, `test_shared_constants`, mypy und ruff.
- Die Auswahl trifft `affected_tests.py`.

**Unterlagen:** keine Regeländerung. Die Kartenzeilen schreibt S.

### 4.2 D0-L

**Abnahme (Wächter im Tor, über dem Bestand grün):**
- Zählung: mindestens 150 Operationen, 40 Dialogklassen und 30 feste Ziele, sonst bricht der Test ab.
- Jede Operation hat genau ein Paket.
- Jede Anforderung hat eine Szene.
- Jede Dialogklasse hat eine Zeile mit Paket.
- Die leichten Szenen werten aus und zeigen ihre Merkmalsart an beiden Kernen; exakt lokal nur mit `exact_kernel()`, in der CI Pflicht.
- Die Stapel der schweren Szenen sind gültig.
- Jede Spezifikation trifft eine erzeugte Zeile, Wortschatzziele (`is_target`), Szenen und Felder.

**Gegenproben:**
- eine erfundene Operation mit neuer Merkmalsart → rot;
- eine erfundene Dialogklasse → rot;
- unbekannte Kennung in einer Spezifikation → rot;
- eine Zeile ohne Spezifikation bleibt grün („ungeprüft“).

`test_wording` hält mit den Daten aus der Wortliste dieselben Zahlen (`MUSTER_BESTAND` unverändert). `tests/data/README.md` erhält je neuer Datei eine Zeile (`test_corpus`).

### 4.3 D0-P

**Abnahme:**
- Datei- und Funktionsfälle nur über Eingabeereignisse mit Probe.
- Zahlen getippt.
- Wiederaufnahme und Bericht wie bei RM-184.
- Je Prüfpunkt ein Feld im Protokoll oder der Vermerk „Stufe B“.

**Tests:**
- **Im Tor** (`test_function_bench.py`):
  - Schrittautomat mit nachgestellten Ereignissen: Wegklicks gezählt, „verdeckt“, „nicht auffindbar“;
  - Abdruck, Zahlenformat je Sprache, Herzschlaglücke, Vorbereitung von Profil und Lizenz;
  - AST-Wächter: keine Aufrufe `click`, `set_value*`, `emit`, `session.apply`, `trigger`, `select_*`, `action_undo/redo` in `function_bench`, `function_capture` und `WindowFlow`, mit Gegenprobe an einem Quelltext;
  - `function_bench` ohne `__main__` und ohne argparse.
- **In der Fenster-CI:** die beiden bestehenden Fensterwege von `test_file_acceptance` über Eingabeereignisse, dazu ein Funktionsfall `resize_hole` im Prozess und einer im eigenen Prozess.
- **Werkzeuglauf:** der Probelauf (§4.7).

**Unterlagen:** die Karte schreibt S.

### 4.4 D0-U

**Abnahme:**
- `PRUEFPUNKTE` hat 19 Einträge, `BROKEN_SAMPLES` deckt alle ab; ein Metatest macht einen neuen Prüfpunkt ohne Gegenprobe rot.
- Jede Gegenprobe aus §3 wird rot.
- Urteile werden geprüft: ohne Bild oder Stelle, Bild oder Stelle mit Laufwerkspfad, *offen* ohne RM, ein fremder *entfällt*-Grund, G9 schwerer als leicht, „gut“ gegen einen A-Fund → alle abgewiesen; ein Bild ohne seinen `[[run]]` macht `report` ungültig.
- Die Abhakliste wird aus Musterdaten deterministisch erzeugt, eine Datei je Paket.
- Funddatei: Nummern eindeutig, Art und Schwere aus der Liste, Stand gesetzt.
- Übereinstimmung unter 90 % wird markiert.
- Skill-Tabellen gleich den Konstanten.
- `rendered`-Test: Menüleiste am gebauten Fenster gegen die Fensterbefehlszeilen der Abhakliste, eingetragen in `RENDERED_TESTS`.

**Tests:** `test_function_report.py`, `test_toolchain`, `test_interface_limits`, `test_shared_constants`.

### 4.5 D0-S

**Abnahme:**
- `test_directory_docs`: Budgets, Ladelast, Verweise, keine Daten in Überschriften.
- `test_agent_mirror` grün nach `sync_agents.py`.
- `docs_scan --frage 1`: `main_window.py` nicht schwerer als vorher (Sollrechnung §4.6).
- `AGENTS.md` nennt beide Ausnahmen in einem Satz, `tests.md` verweist darauf, `/pruefen` sagt, wie die eine Fenstertestdatei läuft.
- Die Funddatei hat ihr Gerüst.
- Das Konzept verweist auf die Skills als Quelle der Kriterien.

### 4.6 Unterlagenbudget (gerechnet)

| Datei | Änderung | Byte |
|---|---|---|
| `AGENTS.md` Z. 181–187 | Satz mit beiden Ausnahmen (Codestruktur 7.2, Funktionsdurchgang §13.1); die Einzelheiten zur CI, die wortgleich in `tests.md` stehen, entfallen | 479 → 453, **−26** |
| `app/ui/CLAUDE.md` Zeile `guide_targets.py` | Wortschatz, `next_click`, `point_for`, Kennzeichen | 139 → 194, **+55** |
| `app/ui/CLAUDE.md` Abschnitt „Testen“ | statt „nur beim Release“ der Verweis auf `tests.md` und die Ausnahmen (sonst falsch) | 140 → 84, **−56** |
| **Summe Ladelast `main_window.py`** | | **−27** (Luft danach 44 Byte) |
| `.claude/rules/tests.md` Z. 20 | „auch nicht als gezielte Teilmenge (…)“ → „außer den zwei Ausnahmen in `AGENTS.md` („Arbeitsweise“)“ | +2 von 28 |
| `tools/CLAUDE.md` | Sammelzeile für fünf Werkzeuge, `file_acceptance` gekürzt | ≤ +400 von 537 |
| `tests/CLAUDE.md` | Sammelzeile für drei Testdateien, eine lange Zeile gekürzt | ≤ +120 |

Wortlaut für `AGENTS.md`:

> „Fenster, Renderer und Leistung lokal nur beim Release, mit zwei Ausnahmen (Entscheidungen Robert): vor dem Merge eines Oberflächenschritts der Codestruktur die Fenstertests, die `tools/ci_selection.py` zum Diff nennt, und je Fund des Funktionsdurchgangs dessen eine reproduzierende Fenstertestdatei, vorher rot, nachher grün. Alles Übrige fährt der Push nach main (`.claude/rules/tests.md`, `/liefern`); auf Zweigen läuft keine CI.“

### 4.7 Gesamtabnahme D0 (RM-737)

- Die Wächter sind über dem Bestand grün.
- Je Prüfpunkt wird eine Gegenprobe ohne Fenster rot.
- **Probelauf am echten Fenster** mit je einer Zeile pro Art (`resize_hole`, `Bearbeiten/Parameter anlegen …`, `finding.action:place_on_bed`): echte Plattform, eigenes Profil, zweiter Schirm. Er liefert Protokolle, Stufe-B-Urteile in `urteile-d04/d08/d10.toml`, die erzeugten Abhaklisten und echte Funde in `funde.md`.
- Review, dann Entwicklungstor auf dem Integrationszweig, dann main.
- RM-737 im Register fortschreiben; die Schätzung des Programms nach D1 geht an Robert.

## 5 Risiken und offene Fragen

### 5.1 Für Robert

1. **Lizenz „gekauft“ im Prüfstand (Rechte):** Ohne die privaten Aussteller-Schlüssel lässt sich kein freigeschaltetes Profil vorbereiten.
   - Vorgabe, ohne Rückfrage umsetzbar: Der Kindprozess setzt den Zustand über dieselbe Nahtstelle wie die Suite (`activation._cached`). Geprüft wird das Ausgrauen, und das ist der Vertrag („Die Oberfläche graut nur aus“).
   - Nur wenn Robert den echten Weg will: ein eigener Prüfschlüssel samt Geräteplatz auf der Prüfmaschine.

### 5.2 Selbst entschieden, mit Grund

| Entscheidung | Grund |
|---|---|
| `objectName` der Menüleiste aus der Message-ID, mit Umstellung von `tr` auf `_` an rund 140 Aufrufstellen | Das Konzept verlangt Kennungen „aus den unübersetzten Quelltexten“. Es beseitigt S1 (`menu.N`) an der Wurzel und trägt in allen sechs Sprachen. Andernfalls ginge es nur auf Deutsch oder über eine zweite Zuordnung (§12). |
| `history:` bleibt als Alias | Drei Anleitungen; sonst wären alle Anleitungsbilder neu zu erzeugen. |
| Kennzeichen als Eigenschaft an Widgets, `objectName` nur an Aktionen | Widget-`objectName` gehören dem Stylesheet (`actionHeading`, `fenster.md` „Der Hauptknopf“). |
| `AA_DontUseNativeDialogs` im Kindprozess | Systemdialoge sind Stufe C. So bleibt der Rest des Wegs in Stufe A und der Fall bricht nicht ab. |
| Vorbedingungen „fehlt“ (Slicer, Modell, ComfyUI) über die Nahtstellen von `conftest` im Kindprozess | Es gibt keinen Schalter, und das Einrichten ist nicht die geprüfte Handlung. |
| Textpassung je Sprache als ein Prozess pro Sprache und Paket über alle Flächen | Sechs Sprachen in einem Prozess brechen ab; je Zeile und Sprache wären es Tausende Läufe (§12, „Bilder in allen Sprachen“). |
| Szenen als Rezeptdaten in `tests/data/`, gebaut zur Laufzeit | „Aus Ops gebaut“; Erzeugtes wird nicht abgelegt. |
| Zeilenspezifikation in `tests/data/function_rows/`, Urteile und Abhakliste in `.state` | Die Spezifikation überlebt den Zustandsordner und braucht sie für die Wiederholung (§8). Die Ergebnisse ziehen am Ende nach `konzepte/`. |
| Ausdrücke im Wortschatz aus Arten, die das Konzept nicht nennt: `dialog:`, `view:`, `feature.apply` und weitere | Jede Bedienfläche braucht einen festen Namen (§3). Was nicht erreichbar ist, wird ein Ziel im Wortschatz (§5). |
| Schwellen ohne Codequelle als Konstante, mit Wächter gegen das Skill | Das Skill bleibt die Quelle für Menschen, und der Prüfstand braucht Zahlen. Das ist ein gehaltener Zwilling mit Test. |

### 5.3 Risiken

| Risiko | Gegenmittel |
|---|---|
| Konflikte in `main_window.py` (rund zehn Commits am Tag) beim Umstellen der Menüleiste | ein mechanischer Commit direkt nach einem Wellenschnitt; der Fenstertest auf vollständige `objectName` fängt Vergessenes |
| Codestruktur Schritt 0 landet vorher (W1 und W5) | nur Zeilen in bestehenden Rümpfen; Umbenennung statt neuer Methode; kein `getattr(window, "…")`; Zuordnung nach Klassenname, rekursive Suche |
| `QApplication.widgetAt` könnte offscreen nicht verlässlich sein | eine Funktion `widget_under` (topLevel, dann `childAt`); erst am offscreen-Test belegen, bevor der Prüfstand darauf baut |
| Modale `exec()`-Schleifen | ereignisgetriebener Automat (B6) |
| Schwere Szenen (über 10 s, über 1,5 Mio. Dreiecke) kosten Zeit und Speicher | nur im Werkzeuglauf gebaut; der Prüfstand belegt Dauer und Größe; zu schnell ergibt „nicht prüfbar“ |
| Fremdlast verfälscht Zeiten (Z1, Prüfpunkt 6) | Referenzfaktor; eine Überschreitung ist ein Verdacht, den `window_bench.py` bestätigt |
| Offscreen gibt es keine Schrift | Textpassung, Kontrast und Zustandsbilder nur in Stufe A am echten Fenster; Gegenproben mit nachgestellten Daten |
| Sehr wenig Unterlagenbudget | Rechnung in §4.6; S schreibt alle Karten, sodass die Budgets an einer Stelle liegen |
| Probelauf belegt den Bildschirm der Maschine | `--screen` auf den zweiten Schirm; Zeitfenster absprechen (keine Computersteuerung nötig) |

## 6 Schätzung

| Teilpaket | Arbeitstage |
|---|---|
| D0-W Wortschatz | 2,5–3 |
| D0-L Liste und Szenen | 1,5–2 |
| D0-P Prüfstand | 3–3,5 |
| D0-U Urteile | 1,5–2 |
| D0-S Unterlagen | 0,5–1 |
| Integration, Probelauf, Review | 1 |
| **Summe** | **10–12,5** (Konzept §11: 8–12) |

Mit vier parallelen Agenten dauert es rund sechs Kalendertage, der kritische Pfad ist W → P. Der Aufwand liegt am oberen Rand des Konzepts. Gründe: die Umstellung der Menüleiste, der ereignisgetriebene Ablauf und das Zusammenlegen der Wortlisten.

---

### Critical Files for Implementation
- `F:\3D Druck\app\ui\guide_targets.py`
- `F:\3D Druck\tools\file_acceptance.py`
- `F:\3D Druck\app\core\guides.py`
- `F:\3D Druck\app\ui\main_window.py`
- `F:\3D Druck\app\ui\panels.py`