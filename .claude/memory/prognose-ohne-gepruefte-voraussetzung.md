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
