---
name: reparierter-fehler-hat-zwillinge
description: "Wer einen Fehler behebt, sucht seine Geschwister — der Gesamtreview vom 25.08.2026 fand denselben behobenen Fehler fünffach unbehoben an Nachbarstellen."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 16dae8e9-6992-47e8-9e0f-c3edfb514eea
  modified: 2026-08-25T13:08:25.694Z
---

**Der Gesamtreview vom 25.08.2026 (~180 Befunde, ~30 hoch; der Bericht
liegt seit ff7eaaae nur noch in der Git-History)
zeigte ein tragendes Muster: Ein reparierter Fehler hat unreparierte
Zwillinge.** Fünf der schwersten Befunde waren exakt der Fehler, der an einer
Nachbarstelle schon einmal behoben und dort sogar im Docstring dokumentiert
war:

- `drill` bekam `anchor="mouth"` gegen „bohrt ab der Mitte" — `countersink`
  und `plug_hole` nicht.
- `sketch_extrude`/`loft` lesen die Zeichenebene seit einem dokumentierten
  Fix — `sketch_pocket`/`sketch_sweep` nicht.
- `ValueField` fängt Ausdrücke in float-Feldern (Docstring beschreibt den
  alten Absturz) — der int-Zwilling stürzt weiter.
- `_on_split_busy` blendet den Abbrechen-Knopf richtig aus — `_on_agent_busy`
  hat den alten Fehler.
- `write_plan` wandelt `OSError` in einen Satz — `write_assembly` daneben
  nicht.

**Fall sechs, und er verschärft die Regel (25.08. abends):** `moved_features`
bekam beim C-Paket `dataclasses.replace` gegen die Fünf-von-sieben-Handkopie,
samt warnendem Kommentar — und 150 Zeilen weiter oben in **derselben Datei**
stand die zweite Handkopie (`apply_mapping`) und blieb. Unsichtbar, weil die
zwei verlorenen Felder bei erkannten Merkmalen bis dahin immer leer waren;
messbar erst, als ce's created_by-Tor ihnen Inhalt gab. Sechs Merkmale mit
Erzeuger hinein, null heraus.

**Fall sieben, und er dreht die Sache um (03.09.2026):** Nicht der *Fehler*
hatte ein Geschwister, sondern die *Regel* hat eines verloren.
`MIN_CYLINDER_DIAMETER` — „was für kein Werkzeug zu klein ist, ist
für keine Passung zu klein" — stand in `detect_holes` und in
`detect_pins`, nicht in `detect_fillets`. An einem Kundenmodell meldete der
Objektbaum daraufhin „Hohlkehle R0,00 mm": 109 Verrundungen, die kleinste mit
0,0007 mm Radius, zweiundzwanzig unter einer Extrusionsbahn.

Das Bemerkenswerte ist der Kommentar an der zweiten Stelle: „**Dieselbe
Schranke wie bei der Bohrung**". Er belegt, dass jemand die Frage „wo gilt das
noch?" gestellt hat — und beim Beantworten bei zwei Geschwistern stehen
blieb. Ein solcher Kommentar liest sich hinterher wie eine Vollständigkeits-
zusage und ist keine: Er nennt die Stellen, die die Regel **haben**, nie die,
die sie bräuchten. Wer eine Schranke setzt, sucht deshalb nicht ihre
Nachbarn, sondern **alle Aufrufer derselben Einpassung** — hier
`fit_cylinder`, drei Erkenner, und der dritte war zwanzig Tage unbemerkt.

**Und am 03.09.2026 dreimal an einem Tag, mit derselben Signatur — damit
ist es ein Muster und keine Anekdote (a0s Formulierung):**

| Regel | hatten sie | hatte sie nicht |
|---|---|---|
| Werkzeugschranke `MIN_CYLINDER_DIAMETER` | Bohrung, Zapfen | Verrundung — und nach dem Fix immer noch Kegel, Kugel, Torus |
| Zusammenführung zerfallener Flächen | Zylinder, Ring | **Kegel** |
| Gründetabellen der Leiste | zwei Rollen | die dritte |

**Die Signatur ist immer dieselbe:** zwei Geschwister tragen die Regel, das
dritte nicht, und an den zweien steht sogar ein Kommentar, der die
Vollständigkeit nahelegt („dieselbe Schranke wie bei der Bohrung"). Wer
nach der Regel sucht, findet die Stellen, die sie **haben** — nie die, die
sie bräuchten.

**Was daraus als Suchweg folgt:** nicht nach dem Muster suchen, sondern nach
der **gemeinsamen Quelle** der Geschwister. Bei der Werkzeugschranke war das
die Einpassung (drei Erkenner rufen dieselbe, drei eine andere — und genau
die drei anderen fehlten). Beim Zusammenführen war es die Fleckenbildung,
die jede Mantelart zerlegt. Wer „alle Aufrufer von X" fragt, bekommt eine
vollständige Antwort auf eine zu enge Frage
([[gemessene-frage-ist-nicht-die-gestellte]]).

Und die beste Vorbeugung ist keine Suche: **die Regel eine benannte Frage
werden lassen**, die eine neue Art beantworten muss (`_too_small_to_make`).
Eine verstreute Prüfung findet nur, wer sie schon kennt.

**Why:** Ein Fix wird dort gemacht, wo der Fund war, und der Docstring
dokumentiert die Lehre — aber niemand fragt, wo dieselbe Konstruktion noch
steht. Die Lehre reist nicht von selbst zu den Geschwistern.

**How to apply:** Nach jedem behobenen Fehler die Geschwister suchen, bevor
der Commit fertig ist: grep nach dem Muster (dieselbe API, derselbe
Signalname, dieselbe Vorbelegungsquelle) — **zuerst in derselben Datei**,
denn dort wohnen Zwillinge am dichtesten und werden am sichersten übersehen, und jede Fundstelle entweder
mitfixen oder im Commit benennen, warum sie nicht betroffen ist. Beim Review
umgekehrt: Wo ein Docstring einen behobenen Fehler beschreibt, ist die
Nachbarschaft der erste Ort zum Suchen.

**Die schärfste Form: der Docstring nennt den Zwilling beim Namen.** Am
03.09.2026 verloren übersetzbare Texte beim Ablegen ihre Werte — der Kunde las
`{closed} von {total} offenen Kanten geschlossen` statt der Zahlen. Der Fehler
war zu dem Zeitpunkt **zweimal woanders behoben**: in `i18n.source_text` für
Dateinamen und in `cache._name_to_data` für Slotnamen. Und der Docstring des
zweiten Fixes schrieb wörtlich: *„Dasselbe tut `transaction_to_data` für den
Titel einer Transaktion, dort über drei Felder."* Die Fundstelle stand
ausgeschrieben da, ein halbes Jahr lang, und niemand ist hingegangen — es waren
fünf Stellen. Ein benannter Zwilling ist kein erledigter: Wer beim Fixen den
Nachbarn erwähnt, hat ihn beschrieben, nicht behoben. **Der Satz gehört als
Aufgabe ins Register, nicht als Beobachtung in den Docstring.**

Verwandt: [[was-die-suite-nicht-findet]], [[eine-kette-endet-am-letzten-glied]],
[[sollwert-aus-dem-pruefling]].
