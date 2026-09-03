---
name: prognose-ohne-gepruefte-voraussetzung
description: "„Das heilt sich später von selbst\" setzt jemanden voraus, der heilen kann; wer die Voraussetzung nicht nachmisst, hat eine Inkonsistenz begründet statt behoben."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7fe92054-2daa-4d76-92ed-67a2464096bd
  modified: 2026-08-27T19:43:02.701Z
---

Am 27.08.2026 ließ ich `MEMORY.md` bewusst aus einem Commit heraus, weil sie
Zeilen aus Nachbarsitzungen trug, und begründete es so: „die zwei Indexzeilen
ohne Datei sind die kleinere Inkonsistenz, **und es heilt sich, sobald jemand
`MEMORY.md` mit allen Zeilen nachzieht**." Der erste Teil stimmte. Der zweite
war eine Prognose, deren Voraussetzung ich nicht geprüft hatte: Die
Urheber-Sitzung der vierten Zeile war seit über zwei Stunden **beendet** und
hätte ihre Datei nie committet. Ohne einen fremden Eingriff (`f3cca83f`) wäre
nichts geheilt — die Lücke wäre geblieben, mit einer Begründung davor, die
erklärt, warum sie in Ordnung sei.

**Warum:** Eine Prognose in einer Begründung liest sich wie ein Beleg und ist
keiner. Sie ist die gefährlichere Hälfte einer richtigen Entscheidung: Das
Auslassen *war* richtig, und genau deshalb prüft niemand mehr den Halbsatz
dahinter. Verwandt und doch anders als
[[beleg-stand-im-eigenen-kontext]] — dort war eine Messung durch eine Suche mit
zu kleinem Umfang ersetzt; hier gab es überhaupt keine.

**Wie anwenden:** Bei jedem „später", „von selbst", „der nächste macht das",
„das heilt sich" die Voraussetzung als **Frage** formulieren und beantworten:
*Wer* genau, und lebt der noch? Bei Sitzungen ist das eine Zeile
(`/list-agents`, oder `originSessionId` in der Frontmatter gegen die
Sitzungsliste). Ist die Antwort „niemand", ist es keine Prognose, sondern eine
Entscheidung, die Lücke zu lassen — und die gehört so benannt und ins Register,
nicht in einen Nebensatz.

Für den konkreten Fall heißt es: **Eine eigene Memory-Datei und ihre Zeile in
`MEMORY.md` gehören in dieselbe Runde.** Findet sich dort eine fremde Zeile, ist
der Sammel-Nachzug mit ausgewiesener Herkunft je Zeile der Weg (`f3cca83f`
taugt als Vorlage), nicht das Auslassen. Siehe auch
[[commit-o-nimmt-den-dateistand]] für den Grund, aus dem die Datei nicht
zerlegbar ist, und [[bekannte-familie-erklaert-nicht-den-ausloeser]] sowie
[[gemessene-frage-ist-nicht-die-gestellte]] für dieselbe Familie ungeprüfter
Zwischenbehauptungen.

---

**Die Schwester in der Gegenwartsform, und sie hat mich am 03.09.2026 fast
einen Fund gekostet.**

Ich habe 19 einen Zwilling gemeldet: `TranslatableText` hatte ein Feld `values`
bekommen, `scene/cache.py` schrieb es mit, drei gleichartige Stellen in
`scene/serialise.py` nicht. Der Befund war richtig. Dahinter stand ein
Halbsatz: Heute trage dort noch kein Text Werte, also sei nichts kaputt — es
sei nur dieselbe Bauart.

**Der Halbsatz war falsch, und ich hatte ihn nicht gemessen.**
`repair.holes_filled` baut seine Meldung seit langem mit Werten, und der Kunde
las im Prüfbericht `{closed} von {total} offenen Kanten geschlossen`. Es waren
außerdem fünf Stellen, nicht drei — eine vierte in `finding_to_data`, dazu
`evaluate.py:742`, das `.msgid` roh ins Protokoll schrieb. Ausgerechnet die
Zeile, die nach einem Kundenprotokoll sprechend gemacht worden war, verlor
damit ihre Zahlen.

**Why:** Die Prognose oben und diese Entwarnung sind derselbe Fehler in zwei
Zeitformen. Beide stehen als Nebensatz hinter einer richtigen Aussage, beide
klingen wie ihr Abschluss, und genau deshalb liest sie niemand als Behauptung.
Meine war sogar teurer: Sie hätte den Empfänger dazu bringen können, den Fund
als theoretisch abzulegen.

**How to apply:** Wer einen Befund meldet, meldet den Befund — und **misst**,
was er über dessen Tragweite sagt, oder schreibt „nicht gemessen" dazu. Für
diesen Fall war die Messung ein Einzeiler: eine Suche nach `_(`-Aufrufen mit
Schlüsselwortargument findet jeden Text, der Werte trägt. Eine Minute gegen
einen halben Fund.

Die Gegenprobe steckte schon im eigenen Text: Der Docstring von `_name_to_data`
sagt wörtlich, dass `transaction_to_data` dasselbe „über drei Felder" tut. Der
Zwilling stand geschrieben, seit Monaten, und niemand ist hingegangen — siehe
[[benannte-falle-schuetzt-nicht]]. Und `source_text` löste denselben Fehler
seit langem für Dateinamen. Derselbe Fehler war zweimal behoben und fünfmal
offen.

Verwandt: [[reparierter-fehler-hat-zwillinge]] (die Suche selbst),
[[eigener-messfehler-widerlegt-den-befund-nicht]] (dort entwertet ein eigener
Messfehler den Fund, hier ein eigener Nebensatz).
