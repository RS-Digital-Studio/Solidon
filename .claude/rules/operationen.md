---
paths:
  - "app/core/geom/**/*.py"
  - "app/core/registry/**/*.py"
  - "app/core/scene/**/*.py"
---

# Regeln für Operationen

Eine Operation ist die einzige Stelle, an der Geometrie entsteht oder sich
ändert — auch nicht „kurz" im Viewport, auch nicht im Agenten (Regel 2).

**Eine Geste ist nicht dasselbe wie ein Schritt.** Eine Op darf beliebig viele
Nutzergesten sammeln, solange ihr Ergebnis vollständig aus ihren Parametern
folgt: Der Editor schreibt in einen Parameterwert, die Geometrie entsteht erst
bei der Auswertung, und was das Fenster währenddessen zeigt, ist eine Vorschau.
Die Skizze macht es so (§30.1), das Sculpting wird es so machen. Was dabei
einzuhalten ist, steht unten unter „Sammelparameter" und wird von
`tests/test_gesture_ops.py` über das ganze Register geprüft.

## Vollständig oder gar nicht

Keine Op ohne Registereintrag, Parameterschema, Geometrietest und übersetzte
Texte. Die acht Schritte stehen als Checkliste in `AGENTS.md`; `/neue-op`
führt sie durch. Der Registereintrag braucht `name`, `title`, `category`,
`params`, `reversible`, `consumes`/`produces`, `applies_to`, `deterministic`,
`doc`, optional `shortcut`.

`tests/test_registry_consistency.py` parametrisiert über das Register: eine
unvollständige Op fällt dort auf, ein doppeltes Kürzel auch.

**Was die Operation von ihrer Eingabe verlangt, steht im Register.** Eine Op
des exakten Kerns trägt `requires_kind="brep"`; das Menü graut sie bei einem
Netz aus und schreibt den Grund in den Tooltip, statt sie anzubieten und nach
dem ausgefüllten Dialog abzulehnen (Regel 19). Der gute Satz im Kern bleibt —
er ist die zweite Hürde, nicht die erste. Eine Aufzählung in der Oberfläche
wäre beim nächsten Zuwachs des exakten Kerns unvollständig.

## Parameter

Jeder Parameter hat Titel, Vorgabe, Einheit, Grenzen und einen `doc`-Satz, der
sagt, was er bewirkt — nicht, wie er heißt. Vorderseite des Dialogs: die zwei
bis drei Werte, die man tatsächlich ändert. Alles Weitere hinter „Weitere
Einstellungen" (§2.4).

Toleranzen verweisen ins Materialprofil (`auto:<material>`), nie als Zahl.
Wo ein Projektparameter passt, steht keine Streuzahl.

### Sammelparameter (`kind` in `sketch`, `strokes`, `armature`)

Ein Editor sammelt darin, was er nicht in Zahlen fassen kann: eine Skizze als
JSON-Text (§30.1), eine Strichliste, ein Skelett. Fünf Eigenschaften machen
aus so einem Wert einen zulässigen Schritt statt eines Lochs in Regel 2 —
`tests/test_gesture_ops.py` prüft alle fünf über das Register: er geht in den
Op-Hash ein, er übersteht die runde Reise durch die Projektdatei, er ist
reiner Text, der Agent sieht ihn nicht, und er steht auf der Rückseite des
Dialogs.

Zwei davon sind leicht zu übersehen:

**Der Cache-Schlüssel muss die Parameter enthalten, die *in* einem
Sammelparameter gelesen werden.** Ein Maß in der Skizze darf ein Ausdruck sein,
ein Gelenkwinkel einer Stellung auch; ändert sich der Projektparameter
dahinter, ändert sich der **Text** nicht — die Auswertung gäbe das alte
Ergebnis zurück. `resolve_params` hilft dabei nicht: Sie sieht die **oberste**
Ebene eines Parametersatzes, und ein Sammelparameter steht dort als *ein* Wert.

`NESTED_REFERENCES` in `scene/evaluate.py` ordnet jedem betroffenen `kind`
seinen Sammler zu — `sketch` → `sketch_parameter_references()`, `armature` →
`pose_parameter_references()` —, und `_with_nested_context()` mischt die Werte
in den Schlüssel. **Eine Zuordnung und keine Bedingung**, weil genau das schon
einmal schiefging: `"sketch"` stand dort hart verdrahtet, die Pose kam später
dazu und wurde übersehen — obwohl vier Stellen zusagten, dass ein Gelenkwinkel
ein Projektparameter sein darf. Wer einen neuen Sammelparameter mit Ausdrücken
baut, trägt ihn hier ein; das ist eine Zeile und keine Suche.

`strokes` steht bewusst nicht drin: Ein Pinselstrich *ist* eine Koordinate,
kein Maß, das jemand an einen Parameter hängt.

**Der Agent bekommt den Parameter nicht zu sehen.** Skizzen entstehen über
benannte Grundformen und Maße, nie über rohe Punktlisten (§26, Leitprinzip 5).
`json_schema()` lässt `kind="sketch"` deshalb ganz aus, und die Sitzung lehnt
ein trotzdem mitgeschicktes Argument ab. Zwei Ebenen, weil eine Lücke im
Schema noch kein Verbot ist.

## Boolesche Operationen

Die Rückfallkette (§17.2) hat fünf Stufen, und die erreichte Stufe gehört in
`solver`:

| Stufe | Verfahren | Vermerk |
|---|---|---|
| 1 | direkt | `direct` |
| 2 | verschweißen, Toleranz erhöhen, erneut | `welded` |
| 3 | minimale Störung der Eingangsgeometrie | `jittered` (+ Startwert) |
| 4 | voxelbasiert rechnen, zurück vernetzen | `voxel` |
| 5 | Abbruch mit Befund und Handlungsvorschlag | — |

Stufe 4 kostet Genauigkeit und wird im Prüfbericht ausgewiesen, nie
stillschweigend verwendet. In Entwurfsqualität endet die Kette nach Stufe 2.
Nach `voxel` ist die Materialslot-Zuweisung neu zu übertragen — die Vernetzung
wurde ersetzt (§20).

## Beide Qualitätsstufen

`ctx.quality` kennt Entwurf und Fein. Entwurf ist das, womit iteriert wird und
worin der Agent arbeitet; Fein gilt beim Export und im finalen Prüfbericht.
Eine Op, die beide gleich behandelt, sollte das bewusst tun.

## Befunde

Findings zurückgeben, nicht selbst protokollieren. Der Prüfbericht setzt sie
zusammen, der Agent liest sie über `read_report`.

## Test

Kennzahlen gegen eine Datei aus `tests/data/`, nicht gegen ein selbst
erzeugtes Ergebnis. Bei Geometrie zuerst der Test, dann die Umsetzung. Ein
neues Fehlerbild wird eine Testdatei, kein Sonderfall im Code.
