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
| `surfaces.py` | Alles, was **aus** dem Register erzeugt wird — die sechs Funktionen oben, dazu `parameter_table()` und `caveat_line()` |

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

- **`REGISTRY` ist erst nach `load_operations()` vollständig.** Ohne den
  Aufruf fehlen die Operationen aus der Bausteinbibliothek — der Unterschied
  war zuletzt 61 gegen 86. Wer Operationen zählt, ruft erst
  `app.core.bootstrap.load_operations()`.
- **Ein Schemavorgabewert ist keine Dialogvorbelegung.** Was der Dialog
  anbietet, kann aus der Auswahl kommen (`scene/placement.py`). Wer beides
  verwechselt, meldet Fehlbefunde.

## Grenzen

Hier steht **keine Geometrie**. Das Register deklariert, `geom/` rechnet.
