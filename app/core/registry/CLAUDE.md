# `app/core/registry/` — das Register

Die eine Deklaration, die jede Oberfläche liest (§10). Wer eine Operation
anlegt, trägt sie **hier** ein — und bekommt Menü oder Karte rechts, Dialog,
Befehlspalette, Kommandozeilenbefehl, Agentenwerkzeug und Handbuchseite, ohne
sie irgendwo sonst zu erwähnen.

Die Regeln stehen in `.claude/rules/operationen.md`.

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
| `registry.py` | `register_op`, `OperationSpec`, `Registry`. Dazu die Ordnung: `CATEGORIES`, `MENU_GROUPS`, `PANEL_CATEGORIES` mit `in_the_menu_bar` (welche Gruppen rechts in der Karte wohnen statt in der Leiste), `MENU_TWINS`, `VARIANT_GROUPS` |
| `params.py` | Das Parameterschema: `param()`, `op_params()`, `validate()`, `json_schema()`. Grenzen, Einheiten, Vorgaben, Vorder- oder Rückseite des Dialogs — und `optional` für eine Zahl, bei der die Null ein gültiger Wert ist (RM-154) |
| `surfaces.py` | Alles, was **aus** dem Register erzeugt wird — die sechs Funktionen oben, dazu `parameter_table()`, `caveat_line()` und die Menüstruktur (siehe unten) |

### Wie tief ein Menü wird, entscheidet der Kern

Vier Funktionen in `surfaces.py`, und sie bauen aufeinander auf:

| Funktion | Beantwortet |
|---|---|
| `menu_rows_of(kategorien)` | Wie viele Zeilen belegen die flach? Gezählt wird, **was zu sehen ist** — `MENU_TWINS` haben keinen Eintrag, eine Variantengruppe teilt einen |
| `folded_groups(größen, …, rank=…)` | Welche dieser Posten müssen ein Untermenü bekommen, damit der Rest in die Grenze passt? |
| `folded_categories(kategorie)` | Dasselbe für die Kategorien **einer Menügruppe** — die Antwort, die `menu_path` und `_build_menus` benutzen |
| `group_is_flat(kategorie)` | Kommt die Gruppe **ganz** ohne Zwischenebene aus? Ein dünner Aufrufer über `folded_categories` |

**Eine Rechnung, zwei Oberflächen.** `folded_groups` lag bis zum 27.08.2026 in
`app/ui/panels.py` — der Kern konnte sie von dort nicht fragen (§8) und hatte
deshalb ein eigenes, gröberes Modell: alles flach oder **jede** Kategorie eine
Ebene tiefer. Im Menü *Ändern* lagen damit alle sieben Kategorien im
Untermenü, auch *Reparatur* mit einem einzigen Eintrag. Wer eine dritte
Oberfläche baut, die Menütiefe braucht, fragt diese Funktionen — und schreibt
keine vierte.

### Wo eine Operation steht, entscheidet die Kachel — nicht die Kategorie

`catalogue_operations()` (ebenfalls `surfaces.py`) nennt die Operationen, die
im Bausteinkatalog eine Kachel haben. **Vier Stellen fragen sie**, und sie
müssen dieselbe Antwort bekommen: die Menüleiste (`_build_menus` über `skip`),
die Karte rechts (`selection_operations.body_operations`,
`feature_operations`), `menu_path` und die Wächter in `tests/`.

**Und ob eine Operation überhaupt in die Leiste gehört, sagt `in_the_menu_bar`**
(`registry.py`): Was einer Auswahl gilt — `PANEL_CATEGORIES` — steht rechts in
der Karte der Handlungen und in keinem Menü; `menu_path` nennt dafür
„Handlungen rechts (bei gewähltem Körper) → Titel". Die Regeln dazu stehen in
`.claude/rules/oberflaeche.md`.

Eine eigenständige Prüfkörperkachel umfasst sowohl ihren `create_`-Zugang als
auch das kompatible `insert_`. Beide nennen denselben Katalogort und erzeugen
keinen zusätzlichen Menüeintrag; die Kachel startet `creation_name()`.

Die Frage lautete bis zum 29.08.2026 „steht die Kategorie in `WITHOUT_MENU`",
und das war eine Näherung: Von den 29 Operationen der Kategorie `parts` haben
27 eine Kachel, zwei nicht — `create_lid` und `screw_lid` bauen einen Deckel,
statt einen fertigen einzusetzen. Die Näherung nahm beide aus der Menüleiste
und stellte sie nirgends hin; im Katalog stehen sie nicht, weil der
`PARTS.all()` zeigt. **Ein Wächter ist so scharf wie seine weiteste
Ausnahme** — der Test, der „jede Operation ist im Menü auffindbar" zusichert,
blieb dabei grün.

`__init__.py` exportiert lazy (siehe `app/core/CLAUDE.md`): neuer Name = drei
Einträge.

## Was ein Eintrag mitbringen muss

`name` · `title` · `category` · `params` · `reversible` ·
`consumes`/`produces` · `applies_to` · `deterministic` · `doc` · optional
`shortcut`

**Ohne vollständigen Eintrag gibt es die Operation nicht** — Regel 4, und
`tests/test_registry_consistency.py` prüft jede: Vollständigkeit, eindeutige
Kürzel, Startwert wo nötig.

`consumes` legt eine feste Eingangszahl fest; `VARIABLE` zusammen mit
`minimum_inputs` erlaubt alle gewählten Körper ab der angegebenen Untergrenze.
`needed_inputs()` liefert diese Grenze für Menü, Auswahlpanel, Agentenschema,
Verlauf und Auswertung. Feste Eingangszahlen sind zugleich die Obergrenze;
das Werkzeugschema bildet beides als `minItems` und `maxItems` ab, Erzeuger
ohne Eingänge tragen kein Objektfeld. Ausdrücklich mit `whole_scene`
deklarierte Operationen bekommen hingegen die vollständige Szene. Negative
Mindestzahlen und eine Mindestzahl neben fester Stelligkeit werden bereits
beim Registrieren abgewiesen.

`replace_state()` ist ausschließlich der Commit-Schritt für einen bereits in
einem isolierten Register vollständig geprüften Rezeptzustand. Er übernimmt die
vorbereitete Abbildung ohne zweite Validierung; nach einer atomar
veröffentlichten Rezeptdatei darf kein erneut fehlbarer Aufbau den Speicherstand
von der Platte trennen.

## Mehrere benannte Merkmale

`kind="features"` bezeichnet eine Liste benannter Merkmale. Validierung und
JSON-Schema erhalten jedes Element als Zeichenkette; Dialog und CLI liefern
dieselbe Liste. Ob eine leere Liste den ganzen Körper bezeichnet, legt die
Operation fest. Die Verwaistenbehandlung darf fehlende Elemente deshalb nicht
stillschweigend streichen und damit den Wirkungsbereich erweitern.

## Zwei Dinge, die beim Zählen schiefgehen

- **`REGISTRY` ist erst nach `load_operations()` vollständig.** In einem
  frischen Prozess ist es zunächst leer; der Aufruf lädt auch die aus der
  Bausteinbibliothek erzeugten Operationen. Wer Operationen zählt, ruft erst
  `app.core.bootstrap.load_operations()`.
- **Ein Schemavorgabewert ist keine Dialogvorbelegung.** Was der Dialog
  anbietet, kann aus der Auswahl kommen (`scene/placement.py`). Wer beides
  verwechselt, meldet Fehlbefunde.

## Grenzen

Hier steht **keine Geometrie**. Das Register deklariert, `geom/` rechnet.

Die gemeinsamen Bausteinfelder liest die Referenz über `part_placement_params`
aus dem jeweiligen Schema. Die `_surface_normal_fields`-Metadaten halten
Platzierungsrichtungen von gleichnamigen fachlichen Rezeptmaßen getrennt;
solche Maße bleiben in ihrer Parametertabelle sichtbar.
