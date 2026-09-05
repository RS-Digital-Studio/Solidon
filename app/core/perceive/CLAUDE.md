# `app/core/perceive/` — Wahrnehmung

Was das Modell **ist**, nicht was es anzeigt: Merkmale, stabile Bezeichner,
Analysekarten und der Steckbrief (§21, §18.4, §23).

Die Regeln stehen in `.claude/rules/schichtanalyse.md`.

## Wozu das gut ist

Ohne diese Schicht könnte der Agent nur Zahlen sehen. Mit ihr sieht er
„Bohrung Ø5 auf der Oberseite" — und der Nutzer kann sie anklicken, ohne dass
jemand Dreiecke zählt.

```
features.py   ──> „hier ist eine Bohrung, eine Tasche, eine Fase"
helix.py      ──> „hier ist ein Gewinde" — und darum sind die anderen weg
relations.py  ──> „diese zwei gehören zusammen" — und was daraus folgt
matching.py   ──> derselbe Name auch nach der nächsten Operation
digest.py     ──> der Steckbrief: was der Agent zu sehen bekommt
maps.py       ──> Analysekarten für die Ansicht (Überhang, Wandstärke …)
actions.py    ──> „was kann ich damit tun" — und warum nicht, wo nichts geht
```

## Zwei Fragen, zwei Dateien

`features.py` beantwortet **„was ist das hier"**, `relations.py` die Frage
danach: **„gehören zwei davon zusammen?"** Das ist keine Aufteilung nach
Zeilenzahl, sondern nach Aufgabe — eine Wandstärke steht in keinem der beiden
Merkmale, sie entsteht erst aus ihrem Verhältnis.

Die Nachbarschaften werden nicht bei einer bleiben: Senkung über Bohrung, Rohr,
Bohrungsraster, Bohrung durch zwei Wände. Jede davon in das größte Modul des
Kerns zu hängen hieße, es weiter wachsen zu lassen.

**Die Richtung ist einseitig:** `relations.py` liest `features.py`, nie
umgekehrt — samt dessen Schwellen (`SINK_AXIS_LIMIT`, `SINK_FIT_LIMIT`). Zwei
Achsenprüfungen mit zwei Zahlen wären zwei Antworten auf dieselbe Frage.

## Die Auskunft für das Merkmalspanel

`actions.py` ist die eine Stelle, an der steht, welche Handlung für welche
Merkmalsart gilt — **abgeleitet aus `applies_to` im Register**, nicht als
Liste daneben. Eine zweite Tabelle wüsste beim nächsten Registereintrag die
Hälfte.

Zwei Entscheidungen darin sind Absicht und keine Bequemlichkeit:

- **Was nicht gilt, steht trotzdem in der Liste**, mit `op=None` und einem
  Satz. Ein Panel, das bei einer Verrundung nur den Radius zeigt, lässt den
  Kunden raten, ob der Rest fehlt oder vergessen wurde.
- **Jedes Feld trägt seinen heutigen gemessenen Wert** als Vorgabe. Eine
  Vorgabe, die nicht der gemessene Wert ist, wäre eine stille Änderung, sobald
  jemand auf Übernehmen drückt.

Die Oberfläche fragt die Merkmalsart **nicht** — sie rendert die Liste. Sonst
führt sie dieselbe Tabelle ein zweites Mal.

**Und der Kern fragt hier ebenfalls nach.** `reason_against(op, kind)` gibt
`None` zurück, wenn die Operation diese Art annimmt, und sonst den Satz, der im
Panel in der ausgegrauten Zeile steht. `geom/prepare_ops.py` ruft es, bevor es
ein Merkmal anfasst — damit gilt `applies_to` auch über Chat und
Kommandozeile, und der Kunde bekommt auf beiden Wegen denselben Wortlaut.

Dass beide Wege zusammenbleiben, hält
`tests/test_features.py::test_the_operation_refuses_exactly_what_the_panel_greys_out`
über alle Merkmalsarten und alle Zeilen fest — nicht ein Kommentar.

Wo eine Zeile zwei Operationen zusammenfasst, nennt der Satz die richtige beim
Namen: `instead_of(op, kind)` sucht die Schwester in derselben Zeile von
`ACTION_ORDER`, und wer `resize_feature` auf eine Bohrung ruft, liest „Dafür
ist *Bohrung ändern* da" statt „geht nicht".

## Die Karte

| Datei | Rolle |
|---|---|
| `features.py` | Merkmalserkennung (§21.1) — **2 200 Zeilen**, das größte Modul des Kerns |
| `helix.py` | Wendelflächen (§21.1): Achse, Steigung, Gangtiefe. Ein eingelesener Bolzen bringt sonst je nach Größe drei bis zwanzig Merkmale mit, die es nicht gibt — die Flanke eines Gewindegangs ist örtlich eine Kegelfläche und passt sich sauber ein. Wo eine Wendel liegt, steht danach **ein** `thread` statt vieler Erfundener |
| `relations.py` | Nachbarschaften zwischen Merkmalen (§21.1, §21.2): Was zusammengehört und was daraus folgt. Heute das koaxiale Rohr — eine Bohrung und das Material um sie herum, mit der Wand dazwischen |
| `maps.py` | Analysekarten (§18.4) |
| `digest.py` | Der Steckbrief der Szene für den Agenten (§23) |
| `matching.py` | Merkmalsbezeichner über Operationen hinweg stabil halten (§21.2, §21.3) |
| `actions.py` | Was der Kunde mit einem erkannten Merkmal tun kann — und was nicht, mit Grund. Die Liste fürs Merkmalspanel, **aus dem Register abgeleitet** (§10, §21); `reason_against` beantwortet dieselbe Frage für den Kern |

## Die Sache mit der Stabilität

Ein Merkmal, das nach jeder Operation einen neuen Namen bekäme, wäre wertlos
— Passungen und Agentenverweise hingen ins Leere. `matching.py` hält die IDs;
was es trotzdem verliert, fängt `scene/orphans.py` auf und **fragt**, statt
zu raten.

Ein verlorenes erkanntes oder erzeugtes Merkmal und eine bereits geschlossene
Fehlstelle haben im aktuellen Körper keine Fläche mehr, die eine
Merkmalskarte ehrlich färben könnte. `perceive.orphaned`,
`perceive.generated_lost` und `perceive.mended` führen deshalb nur zum
betroffenen Körper und erzeugenden Schritt; eine Karte bleibt aus. Andere
`perceive.*`-Befunde behalten ihre Merkmalskarte.

## Grenzen

- **Erkennen heißt nicht ändern.** Hier entsteht keine Geometrie.
- Mehrdeutigkeit wird gemeldet, nicht aufgelöst (§15.7, Regel 21).
- **Eine Freiform bekommt keine Rundformen.** Ein Scan oder eine Figur
  zerfällt an den Krümmungssprüngen in Dutzende Flecken, und auf jeden passt
  eine Kugel; `is_a_freeform` erkennt das an der fertigen Liste, und
  `_shapes_on_a_freeform` lässt Kugel, Ring, Kegel und Verrundung weg —
  Bohrung, Zapfen und Fläche bleiben. `freeform_dropped` nennt der Auswertung
  die Zahl für den Befund `perceive.freeform`. Die Regel steht in
  `.claude/rules/schichtanalyse.md`.
- **Der Merkmals-Cache hat zwei Schranken.** `CACHE_LIMIT` zählt
  Einträge, `CACHE_INDEX_LIMIT` ihr Gewicht in Flächenindizes —
  ein Eintrag für ein 400 000-Dreieck-Modell wiegt 3,9 MiB, und
  die Anzahl allein ließe fast ein Gigabyte zu.
- **Was zerfällt, wird wieder zusammengeführt.** Ein Mantel kommt aus
  der Fleckenbildung oft in Stücken; `_merged_cylinders`, `_merged_cones`
  und `_merged_tori` machen daraus wieder **ein** Merkmal. Anker ist, was von
  der Größe des Ausschnitts unabhängig ist: beim Zylinder der
  Achsabschnitt, beim Kegel die **Spitze**, beim Ring der Mittelpunkt.
- **Eine Wendel ist keine Grundform, und sie verschluckt die, die man auf ihr
  findet.** `helix.py` misst sie am Netz statt an den Einpassungen: scharfe
  Kanten zu Zügen verbinden, je Zug die Steigung über die Konzentration von
  `z − p·θ/2π` suchen, und dann fünf Bedingungen. Die tragende ist die
  **Gangtiefe** — 0,54 · Steigung nach Norm; über Korpus, Kundendatei und
  kurze Bolzen gezählt ist sie die einzige, die je allein ablehnt. Der Grund,
  aus dem es sie braucht: Ein Mantel mit Spiral-Naht ist eine echte Wendel
  über zwanzig Windungen und hat trotzdem kein Gewinde. Ein Gewinde aus einem
  **Baustein** läuft hier nie durch — es steht ohnehin in der Szene (§24.1).
- **Was für kein Werkzeug groß genug ist, ist kein Merkmal.**
  `MIN_CYLINDER_DIAMETER` (0,5 mm) gilt für **alle sechs** eingepassten
  Arten — Bohrung, Zapfen, Verrundung, Kegel, Kugel, Torus. Die Frage steht
  einmal als `_too_small_to_make`, damit die nächste Art sie nicht wieder
  übersieht; beim Torus entscheidet das kleinere von Ring und Röhre.
