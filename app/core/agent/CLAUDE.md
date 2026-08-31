# `app/core/agent/` — die Agentenschicht

Der Agent ist **kein Chatbot mit angehängtem 3D-Programm** (§26). Er arbeitet
mit genau den Operationen, die der Nutzer hat, sieht genau, was der Nutzer
sieht, und alles, was er tut, kommt als **eine** Transaktion an, die ein
einziges Undo zurücknimmt.

Die Regeln stehen in `.claude/rules/agentenschicht.md`.

## Der Zug

```
Anfrage
   │
   ▼
context.py    Steckbrief + Systemprompt + Regelsammlung  ──> was er sieht
   │
   ▼
session.py    der Zug: Modell fragen, Werkzeug rufen, wiederholen
   │              │
   │              ├─ tools.py     was er tun kann (aus dem Register!)
   │              ├─ analysis.py  Analysen als Werkzeugantwort
   │              └─ checks.py    nach JEDER Operation prüfen
   ▼
proposal.py   ein Vorschlag = eine Transaktion
   │
   ▼
apply.py      annehmen oder verwerfen — beides vollständig
```

## Die Karte

| Datei | Rolle |
|---|---|
| `session.py` | Ein Zug, von der Anfrage zum Vorschlag (§26.5) — 900 Zeilen |
| `context.py` | Was der Agent zu sehen bekommt (§26.1) |
| `prompt.py` | Der Systemprompt (§26.1, §39) |
| `tools.py` | Was er tun kann (§26.2) |
| `analysis.py` | Analysen als Werkzeugantwort |
| `checks.py` | Die Prüfung nach jeder Operation eines Vorschlags (§26.5) |
| `proposal.py` | `Proposal`, `Question` |
| `apply.py` | `accept`, `discard`, `record`, `undo_applied` |
| `remote.py` | Die Schnittstelle nach außen: MCP über JSON-RPC |

## Er bekommt keine Sonderwege

Die Werkzeuge des Agenten kommen aus `registry.tool_schemas()` — **derselben
Quelle** wie Menü und Kommandozeile. Eine Operation, die der Agent kann und
der Nutzer nicht, gibt es nicht; und ein Werkzeug, das an einer Op vorbei
Geometrie anfasst, bricht Regel 2.

## Was für alle gilt, steht im Systemprompt

Ein Werkzeugschema beschreibt **seine** Operation. Was für jedes Werkzeug
gleich gilt, gehört nicht in jedes einzelne, sondern einmal in den
Systemprompt — dieselbe Trennung, die das Handbuch für den Leser trifft
(`PART_PLACEMENT_PARAMS` steht dort einmal am Kopf der Kategorie und nicht in
jeder Bausteintabelle).

Zwei Fälle sind so gelöst: `objects` stand wortgleich in 79 Werkzeugen, die
sechs Platzierungsangaben eines Bausteins (`x`, `y`, `z`, `axis`, `angle`,
`at_feature`) in allen 27. Gemessen am 31.08.2026 fiel die Grundlast dadurch
von **24 161 auf 19 641 Token**.

**Die Bedingung dafür ist Wortgleichheit, nicht Namensgleichheit.** Ein
Parameter, der in zwei Operationen dasselbe *heißt* und Verschiedenes
*bedeutet*, verlöre seine Bedeutung — die sechs Platzierungsangaben werden
deshalb nur dort gestrichen, wo **alle sechs beisammen** sind, und ein
Werkzeug, das `x` aus eigenem Recht führt (verschieben, drehen), behält
seinen Text. `tests/test_agent.py` prüft, dass jede dieser Angaben
**irgendwo** erklärt wird, im Schema oder im Prompt — die Erklärung ist die
Zusage, ihr Ort nicht.

## Was der Prompt verspricht, müssen die Werkzeuge tragen

Der Systemprompt und die Werkzeugschemata sind zwei Quellen über dieselbe
Sache, und sie laufen auseinander, ohne dass etwas rot wird. Bis zum
31.08.2026 sagte der Prompt in jedem Zug „der Ort steht in jeder
Werkzeugbeschreibung (‚Menü: …')" — und `tool_schemas(compact=True)` lässt
genau diesen Ort weg: 95 Werkzeuge nennen ihn im vollen Schema, **null** im
kompakten, und das kompakte bekommt jedes lokale Modell.

Deshalb entscheidet `session.py` **einmal**, ob kompakt gefahren wird, und
reicht dieselbe Antwort an beide Seiten. Wer dem Prompt eine Zusage über die
Werkzeuge hinzufügt, baut den Wächter dazu.

## Fragen statt raten

Mehrdeutigkeit endet in einer `Question`, nicht in einem Versuch. Das ist
Regel 21 und zugleich das, was die Agenten-Suite misst.

## Viele Formdetails bleiben ein Zustand

`checks.check()` behält jeden Rohbefund für Vorschlag und Prüfbericht.
`checks.as_lines()` zählt nur `perceive.orphaned` je Körper und Schritt, bevor
der Text zum Modell geht. So bleiben Diagnose und Klickziele vollständig,
ohne dass hunderte wortgleiche Sätze den nächsten andersartigen Befund aus
dem Agentenkontext verdrängen.

## Änderungen werden gemessen, nicht behauptet

Am Verhalten geschraubt — Systemprompt, Regelsammlung, Werkzeugbeschreibung?
Dann läuft `tools/run_agent_suite.py` (39 Referenzanfragen) **vorher und
nachher**. Der Lauf kostet Geld und rund anderthalb Stunden je Modell; sein
Exit-Code 1 ist eine Quote, kein Fehlschlag.

**Er braucht einen hinterlegten Schlüssel, und der ist nicht auf jeder
Maschine da.** Ohne ihn endet der Läufer sofort mit „Kein Sprachmodell
erreichbar" (Exit 2) — geprüft wird mit `keys.read("anthropic")`. Der Weg
über Ollama steht offen, taugt für diese Frage aber nicht: Die volle Suite
endete dort bei 4 von 33 mit 17 Zeitüberschreitungen, und eine Quote, die von
der Auslastung der Maschine handelt, misst nicht den Prompt. Wer eine
Änderung nicht abnehmen kann, sagt das — „gebaut und gemessen, aber nicht
abgenommen" ist ein gültiger Stand.

Verschlechtert sich die Quote, wird die Änderung zurückgenommen.
