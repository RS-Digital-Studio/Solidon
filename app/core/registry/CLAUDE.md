# `app/core/registry/` — das Register

Die eine Deklaration, die jede Oberfläche liest (§10). Wer eine Operation
anlegt, trägt sie **hier** ein — und bekommt Menü, Dialog, Kontextmenü,
Befehlspalette, Kommandozeilenbefehl, Agentenwerkzeug und Handbuchseite, ohne
sie irgendwo sonst zu erwähnen.

Die Regeln stehen in `.claude/rules/operationen.md`.

## Die eine Idee

```
                        ┌──> menu_tree()        Menüs im Fenster
                        ├──> context_menu()     Rechtsklick im Viewport
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
| `registry.py` | `register_op`, `OperationSpec`, `Registry`. Dazu die Ordnung: `CATEGORIES`, `MENU_GROUPS`, `MENU_TWINS`, `VARIANT_GROUPS` |
| `params.py` | Das Parameterschema: `param()`, `op_params()`, `validate()`, `json_schema()`. Grenzen, Einheiten, Vorgaben, Vorder- oder Rückseite des Dialogs |
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
das Kontextmenü (`panels._add_operations`), `menu_path` und drei Wächter in
`tests/`.

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
