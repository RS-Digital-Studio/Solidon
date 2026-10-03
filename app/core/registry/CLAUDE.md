# `app/core/registry/` — das Register

Die eine Deklaration, die jede Oberfläche liest (§10). Wer eine Operation
anlegt, trägt sie **hier** ein — und bekommt Menü oder Karte rechts, Dialog,
Befehlspalette, Kommandozeilenbefehl, Agentenwerkzeug und Handbuchseite, ohne
sie irgendwo sonst zu erwähnen.

Einzuhalten sind `.claude/rules/operationen.md` und `grenzen.md` (was wo
steht, Grenzen, Suche), dazu `kern.md`; die Anlässe dieser Karte stehen in
`konzepte/begruendungen/karte-app-core-registry.md`.

## Die eine Idee

```
                        ┌──> menu_tree()        Menüs im Fenster — oder die Karte rechts
                        ├──> context_menu()     Rohmenge je Merkmal (Karte rechts, Doppelklick)
@register_op(...)  ──>  ├──> palette_entries()  Befehlspalette
   REGISTRY             ├──> cli_commands()     Unterbefehle der CLI
                        ├──> tool_schemas()     was der Agent aufrufen kann
                        └──> documentation()    Referenzteil des Handbuchs
```

**Eine Quelle, sechs Oberflächen.** Eine Liste, die woanders gepflegt wird,
driftet ab — deshalb gibt es keine.

## Die Karte

| Datei | Rolle |
|---|---|
| `registry.py` | `register_op`, `OperationSpec`, `Registry`. Die Ordnung: `CATEGORIES`, `MENU_GROUPS`, `PANEL_CATEGORIES` mit `in_the_menu_bar` (welche Gruppen rechts in der Karte wohnen statt in der Leiste), `VARIANT_GROUPS`, `MENU_TWINS` — nach Verfügbarkeit des exakten Kerns gebaut und deshalb **faul** über `menu_twins()`, denn die Antwort lädt OpenCASCADE (wer sie im Modul braucht, ruft die Funktion): die fünf Grundkörper aus `PRIMITIVE_TWINS` sichtbar exakt, versteckt als Netz; Bohren und Aushöhlen sichtbar als die Operation, die die Körperart selbst fragt. `exact_names` (welche Zwillinge exakt rechnen, für Verlauf und Fenster), `kernel_twin_of` und `kernel_switch_label` (Kernwechsel am Schritt, nur an einem Grundkörper, in den exakten Kern nur, wenn er da ist), `twin_way` für den Menüweg |
| `params.py` | Das Parameterschema: `param()`, `op_params()`, `validate()`, `json_schema()` — Grenzen, Einheiten, Vorgaben, Vorder- oder Rückseite des Dialogs; `optional` für eine Zahl, bei der die Null gültig ist; `feature_kinds` für ein Merkmalsfeld, das nur bestimmte Arten annimmt (`scene.placement.values_for` trägt einen Klick auf eine andere Art nicht ein) |
| `surfaces.py` | Alles, was **aus** dem Register erzeugt wird — die sechs Funktionen oben, dazu `parameter_table()`, `caveat_line()`, die gemeinsamen Auswahlbeschriftungen (`choice_label`, `SIDE_NAMES`), die Menütiefe und `catalogue_operations()` (siehe unten) |
| `search.py` | Operationen nach Wörtern finden: Faltung (`fold`, „ä“ → „ae“), Wortstamm (`stem_of`), die Kundenwörter — `SYNONYMS` (deutsch) und `CUSTOMER_WORDS` (je Sprache ein Katalogtext mit Kontext „Suchwörter“, über `customer_phrases`) — und die Rangfolge: `rank_entries` über `search_fields` (Operationen und Fensterbefehle der Palette), `rank_operations` fürs Register. Der Agent wählt damit sein Angebot **nur mit `SYNONYMS`** (`customer_words=False`, Regel in `grenzen.md`), die Palette ordnet mit beiden. Seltene Wörter zählen, Füllwörter nicht (am ganzen Text gezählt); eine Kundenwendung zählt nur, wenn jedes Wort im Stamm beidseitig passt (`_same_word`) |
| `__init__.py` | Exportiert lazy (siehe `app/core/CLAUDE.md`): ein neuer Name steht an drei Stellen |

## Parameterarten mit Folgen

- `ParamSpec.internal` kennzeichnet gespeicherte Kompatibilitätswerte. CLI,
  Agentenschema und beide Referenzfassungen bieten sie nicht als Eingabe an;
  Validierung und Projektdatei behalten sie für alte Schritte.
- `documentation()` und `parameter_table()` behalten mit `technical=True`
  interne Schlüssel und Ausführungsverträge für technische Aufrufer. Das
  Handbuch verwendet `technical=False`: Kundentitel, Bedienort, Kürzel,
  Merkmale, Grenzen und Feldbeschreibungen bleiben; Auswahlwerte samt Vorgaben
  und Bedingungen heißen wie im Dialog. Kein Feldtyp gilt pauschal als
  versteckt. Überschriften in Beschreibungen werden mit
  `markup.below_heading` unter den Operationstitel eingeordnet, auch bei
  eigenen Rezepten mit ATX- oder Setext-Markdown; Codebeispiele bleiben Code.
- Auswahlbeschriftungen leben einmal in `surfaces.py`, ohne Qt.
  `choice_label()` leitet Normteilnamen aus der Normtabelle ab und erlaubt
  einen Zahlenformatierer für die Anzeigeeinheit der Oberfläche;
  `ui.labels.choice_label()` reicht ihn herein. `SIDE_NAMES` liefert auch die
  Flächennamen und Rückfragen der Platzierung.
- **`ParamKind="contours"`** bleibt im Kern Text mit einer JSON-Liste von
  Profilkennungen: `TEXT_KINDS`, nicht `GATHERED_KINDS` — Agent und Projekt
  führen die Auswahl als Daten, die Oberfläche zeigt einen Konturwähler;
  Koordinaten oder ausführbare Inhalte kommen nicht hinzu.
- **`ParamKind="organizer"`** ist ebenfalls Text mit reinen strukturierten
  Daten; der Sammler in `organizer.serialize` liefert die darin verwendeten
  Maßausdrücke an Auswertung, Cache, Rezepte und Parameteranzeige.
- **`kind="features"`** ist eine Liste benannter Merkmale; Validierung und
  JSON-Schema prüfen jedes Element als Zeichenkette, Dialog und CLI liefern
  dieselbe Liste. Ob eine leere Liste den ganzen Körper meint, legt die
  Operation fest — die Verwaistenbehandlung darf fehlende Elemente deshalb
  nicht still streichen und damit den Wirkungsbereich erweitern.
- **`OperationSpec.material_params`** nennt zusätzliche
  `kind="material"`-Felder; die Auswertung hasht ihre Kalibrierung je
  Materialrolle mit dem Druckprozess. Fehlende Profile halten am Schritt an,
  ein leeres Feld nimmt das Projektprofil; eine Materialkennung allein ist
  keine ausreichende Cacheabhängigkeit.
- **`required` gilt nur im aktiven `depends_on`-Zweig** (samt äußerer
  Bedingungen und Vorgaben nicht übergebener Steuerfelder); inaktive Werte
  bleiben gespeichert und typgeprüft. `json_schema()` beschreibt dieselbe
  Bedingung über `if`/`then`, damit ein Werkzeugaufruf keine unwirksame
  Eingabe erfinden muss.
- **`ParamSpec.sketch_planes`** nennt die Ebenen, auf denen die Zeichnung eines
  Skizzenfelds liegen darf (leer: jede; die erste ist die Vorgabe); Editor,
  Zeichenmodus und Ebenenfeld bieten nur diese an —
  `sketch_sweep.path_sketch` trägt `brep.profiles.PATH_PLANES`.
- Die gemeinsamen Bausteinfelder liest die Referenz über
  `part_placement_params` aus dem Schema; `_surface_normal_fields` hält
  Platzierungsrichtungen von gleichnamigen Rezeptmaßen getrennt.

## Wie tief ein Menü wird, entscheidet der Kern

| Funktion in `surfaces.py` | Beantwortet |
|---|---|
| `menu_rows_of(kategorien)` | Wie viele Zeilen belegen die flach? Gezählt wird, **was zu sehen ist** — `MENU_TWINS` haben keinen Eintrag, eine Variantengruppe teilt einen |
| `folded_groups(größen, …, rank=…)` | Welche Posten müssen ein Untermenü bekommen, damit der Rest in die Grenze passt? |
| `folded_categories(kategorie)` | Dasselbe für die Kategorien **einer Menügruppe** — die Antwort, die `menu_path` und `_build_menus` benutzen |

**Gefaltet wird nur so weit, bis der Rest passt, und nur, was etwas spart**:
Eine Gruppe mit einem einzigen Eintrag bekommt kein Untermenü, die einzige
Gruppe eines Menüs faltet nie. `fixed` sind Zeilen, die mitzählen und nicht
faltbar sind (im Bausteinmenü die Einträge ohne Baustein der Bibliothek);
`keep` nennt die Gruppen, die **zuletzt** an die Reihe kommen — über die
**Kategorie**, nie über den übersetzten Titel; `rank` ordnet, wen es zuerst
trifft (ohne Angabe `menu_rank`, die Reihenfolge der Leiste). Warum der Rang
vor der Größe geht, regelt `operationen.md` („Menütiefe: gefaltet wird hinten,
nicht beim Größten“), die Messung dazu steht in
`konzepte/begruendungen/regel-operationen.md`.

**Die Rechnung kommt ohne Qt aus** — sie nimmt Namen und Zeilenzahlen und ist
ohne Fenster prüfbar (Grund in derselben Regel). **Eine Rechnung, alle
Oberflächen**: Sie liegt im Kern, weil der Kern keine Oberfläche fragen darf
(§8); wer eine weitere baut, die Menütiefe braucht, fragt diese Funktionen und
schreibt keine eigene.

## Wo eine Operation steht, entscheidet die Kachel

`catalogue_operations()` nennt die Operationen mit Kachel im Bausteinkatalog.
**Vier Stellen fragen sie** und bekommen dieselbe Antwort: die Menüleiste
(`_build_menus` über `skip`), die Karte rechts
(`selection_operations.body_operations`, `feature_operations`), `menu_path`
und die Wächter in `tests/`. Ob eine Operation überhaupt in die Leiste gehört,
sagt `in_the_menu_bar`: Was einer Auswahl gilt (`PANEL_CATEGORIES`), steht
rechts in der Karte der Handlungen; `menu_path` nennt dafür „Handlungen
rechts (bei gewähltem Körper) → Titel“. Die Regeln stehen in `grenzen.md`
(„Wo eine Operation steht“). Eine eigenständige Prüfkörperkachel umfasst
ihren `create_`-Zugang und das kompatible `insert_`; beide nennen denselben
Katalogort, erzeugen keinen zusätzlichen Menüeintrag, und die Kachel startet
`creation_name()`.

## Was ein Eintrag mitbringen muss

`name` · `title` · `category` · `params` · `reversible` ·
`consumes`/`produces` · `applies_to` · `deterministic` · `doc` · optional
`shortcut` — **ohne vollständigen Eintrag gibt es die Operation nicht**
(Regel 4; `tests/test_registry_consistency.py`: Vollständigkeit, eindeutige
Kürzel, Startwert wo nötig).

- **`consumes`** legt eine feste Eingangszahl fest (zugleich Obergrenze);
  `VARIABLE` mit `minimum_inputs` erlaubt alle gewählten Körper ab der
  Untergrenze. `needed_inputs()` liefert sie für Menü, Auswahlpanel,
  Agentenschema (`minItems`/`maxItems`; Erzeuger ohne Eingänge ohne
  Objektfeld), Verlauf und Auswertung. `whole_scene` bekommt die ganze Szene;
  negative Mindestzahlen und Mindestzahl neben fester Stelligkeit weist schon
  das Registrieren ab.
- **`also_on_body`**: Eine Merkmalshandlung gilt ohne gewähltes Merkmal auch
  am ganzen Körper (die Formschräge) und steht dann an beiden Stufen, mit
  einem Knopf.
- **`edges_on_mesh`**: Die Operation liest ihre Kanten (`kind="edges"`) immer
  am **Netz**, auch an einem exakten Körper (*Wulst anlegen*); die
  Kantenbindung vor dem Verbrauchercache (`scene.edge_binding`) sieht dieselben
  Kanten. Ohne das Flag entscheidet die Bauart des Körpers.
- **`replace_state()`** ist ausschließlich der Commit-Schritt für einen in
  einem isolierten Register vollständig geprüften Rezeptzustand — ohne zweite
  Validierung, damit nach einer atomar veröffentlichten Rezeptdatei kein
  fehlbarer Aufbau den Speicherstand von der Platte trennt.

## Zwei Dinge, die beim Zählen schiefgehen

- **`REGISTRY` ist erst nach `load_operations()` vollständig.** In einem
  frischen Prozess ist es leer; der Aufruf lädt auch die aus der
  Bausteinbibliothek erzeugten Operationen. Wer zählt, ruft erst
  `app.core.bootstrap.load_operations()`.
- **Ein Schemavorgabewert ist keine Dialogvorbelegung.** Was der Dialog
  anbietet, kann aus der Auswahl kommen (`scene/placement.py`); wer beides
  verwechselt, meldet Fehlbefunde.

Hier steht **keine Geometrie**: Das Register deklariert, `geom/` rechnet.
