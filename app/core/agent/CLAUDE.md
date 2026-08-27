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

## Fragen statt raten

Mehrdeutigkeit endet in einer `Question`, nicht in einem Versuch. Das ist
Regel 21 und zugleich das, was die Agenten-Suite misst.

## Änderungen werden gemessen, nicht behauptet

Am Verhalten geschraubt — Systemprompt, Regelsammlung, Werkzeugbeschreibung?
Dann läuft `tools/run_agent_suite.py` (39 Referenzanfragen) **vorher und
nachher**. Der Lauf kostet Geld und rund anderthalb Stunden je Modell; sein
Exit-Code 1 ist eine Quote, kein Fehlschlag.

Verschlechtert sich die Quote, wird die Änderung zurückgenommen.
