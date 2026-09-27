# Begründungen zu `app/core/registry/CLAUDE.md`

> Stand 27.09.2026. Aus der Karte verschoben, als sie auf Module, Datenfluss
> und Stolperfallen verdichtet wurde. Die Karte steht dort; hier stehen die
> ausführlichen Fassungen, das Warum und die Anlässe ihres Tages — wörtlich,
> gegliedert nach den Überschriften der Karte. *Früher unter …* nennt die Stelle
> der alten Karte.

## Die Karte

*Früher unter „Die Karte“.*

| Datei | Rolle |
|---|---|
| `registry.py` | `register_op`, `OperationSpec`, `Registry`. Dazu die Ordnung: `CATEGORIES`, `MENU_GROUPS`, `PANEL_CATEGORIES` mit `in_the_menu_bar` (welche Gruppen rechts in der Karte wohnen statt in der Leiste), `MENU_TWINS` (seit P2.8 nach Verfügbarkeit des exakten Kerns gebaut — **faul**, beim ersten Zugriff über `menu_twins()`, denn die Antwort lädt OpenCASCADE; wer sie im Modul braucht, ruft die Funktion: die fünf Grundkörper aus `PRIMITIVE_TWINS` sichtbar exakt, versteckt als Netz; Bohren und Aushöhlen sichtbar als die Operation, die die Körperart selbst fragt), `exact_names` (welche Zwillinge exakt rechnen — eine Antwort für Verlauf und Fenster), `kernel_twin_of` und `kernel_switch_label` für den Kernwechsel am Schritt im Verlauf (nur an einem Grundkörper, und in den exakten Kern nur, wenn er da ist), `twin_way` für den Menüweg, `VARIANT_GROUPS` |
| `params.py` | Das Parameterschema: `param()`, `op_params()`, `validate()`, `json_schema()`. Grenzen, Einheiten, Vorgaben, Vorder- oder Rückseite des Dialogs — und `optional` für eine Zahl, bei der die Null ein gültiger Wert ist (RM-154), `feature_kinds` für ein Merkmalsfeld, das nur bestimmte Arten annimmt (die Öffnungen des Aushöhlens sind Flächen; `scene.placement.values_for` trägt einen Klick auf eine andere Art nicht ein, die Registerprüfung kennt jede Art) |
| `surfaces.py` | Alles, was **aus** dem Register erzeugt wird — die sechs Funktionen oben, dazu `parameter_table()`, `caveat_line()` und die Menüstruktur (siehe unten) |
| `search.py` | Operationen nach Wörtern finden: Faltung (`fold`, „ä" → „ae"), Wortstamm (`stem_of`), die Kundenwörter — `SYNONYMS` (deutsch) und `CUSTOMER_WORDS` (je Sprache ein Katalogtext mit Kontext „Suchwörter", gelesen über `customer_phrases`) — und die Rangfolge für eine Anfrage in Sätzen: `rank_entries` über `search_fields` (Operationen und Fensterbefehle der Palette), `rank_operations` fürs Register. Der Agent wählt damit sein Werkzeugangebot — **nur mit `SYNONYMS`**, ohne `CUSTOMER_WORDS` (`customer_words=False`; Regel in `.claude/rules/grenzen.md`) —, die Palette ordnet damit ihre ungenauen Treffer, mit beiden. Seltene Wörter zählen, Füllwörter nicht (gezählt am ganzen Text, ohne Liste je Sprache); eine Kundenwendung zählt nur, wenn jedes ihrer Wörter im Stamm beidseitig passt (`_same_word`) |

## Wie tief ein Menü wird, entscheidet der Kern

*Früher unter „Wie tief ein Menü wird, entscheidet der Kern“.*

**Gefaltet wird nur so weit, bis der Rest passt** — und nur, was etwas
spart: Eine Gruppe mit einem einzigen Eintrag bekommt kein Untermenü, denn es
spart keine Zeile und kostet einen Klick; die einzige Gruppe eines Menüs faltet
nie, sonst bestünde das Menü aus einem Untermenü, das heißt wie der Klick davor.
`fixed` sind Zeilen, die mitzählen und nicht faltbar sind — im Bausteinmenü die
Einträge ohne Baustein der Bibliothek. `keep` nennt die Gruppen, die **zuletzt**
an die Reihe kommen, weil sie die Geste tragen, für die man überhaupt geklickt
hat; genannt werden sie über die **Kategorie** und nie über den übersetzten
Titel. `rank` ordnet, wen es zuerst trifft — ohne Angabe die Reihenfolge der
Menüleiste (`menu_rank`). **Warum dabei der Rang vor der Größe geht**, steht
mit seiner Messung in `.claude/rules/operationen.md`.

**Eine Rechnung, zwei Oberflächen.** `folded_groups` lag bis zum 27.08.2026 in
`app/ui/panels.py` — der Kern konnte sie von dort nicht fragen (§8) und hatte
deshalb ein eigenes, gröberes Modell: alles flach oder **jede** Kategorie eine
Ebene tiefer. Im Menü *Ändern* lagen damit alle sieben Kategorien im
Untermenü, auch *Reparatur* mit einem einzigen Eintrag. Wer eine dritte
Oberfläche baut, die Menütiefe braucht, fragt diese Funktionen — und schreibt
keine vierte.

## Wo eine Operation steht, entscheidet die Kachel

Die Regel dazu steht heute in `.claude/rules/grenzen.md` („Wo eine Operation
steht“): `create_lid` und `screw_lid` stehen ohne Kachel an der Fläche und
unter *Erzeugen → Bausteine*.

*Früher unter „Wo eine Operation steht, entscheidet die Kachel — nicht die Kategorie“.*

Die Frage lautete bis zum 29.08.2026 „steht die Kategorie in `WITHOUT_MENU`",
und das war eine Näherung: Von den 29 Operationen der Kategorie `parts` haben
27 eine Kachel, zwei nicht — `create_lid` und `screw_lid` bauen einen Deckel,
statt einen fertigen einzusetzen. Die Näherung nahm beide aus der Menüleiste
und stellte sie nirgends hin; im Katalog stehen sie nicht, weil der
`PARTS.all()` zeigt. **Ein Wächter ist so scharf wie seine weiteste
Ausnahme** — der Test, der „jede Operation ist im Menü auffindbar" zusichert,
blieb dabei grün.

## Was ein Eintrag mitbringen muss

*Früher unter „Was ein Eintrag mitbringen muss“.*

`also_on_body` sagt der Auswahlkarte, dass eine Merkmalshandlung auch ohne
gewähltes Merkmal am ganzen Körper gilt (die Formschräge, P6.4); sie steht
dann an beiden Stufen, mit einem Knopf.

`edges_on_mesh` sagt der Auswertung, dass eine Operation ihre Kanten
(`kind="edges"`) immer am **Netz** liest, auch an einem exakten Körper —
*Wulst anlegen* vereinigt am tessellierten Körper. Die Kantenbindung vor dem
Verbrauchercache (`scene.edge_binding`, P1.4c) muss dieselben Kanten sehen
wie die Operation; ohne das Flag entscheidet die Bauart des Körpers.
