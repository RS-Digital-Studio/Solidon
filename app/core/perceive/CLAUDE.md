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
matching.py   ──> derselbe Name auch nach der nächsten Operation
digest.py     ──> der Steckbrief: was der Agent zu sehen bekommt
maps.py       ──> Analysekarten für die Ansicht (Überhang, Wandstärke …)
```

## Die Karte

| Datei | Rolle |
|---|---|
| `features.py` | Merkmalserkennung (§21.1) — **2 200 Zeilen**, das größte Modul des Kerns |
| `maps.py` | Analysekarten (§18.4) |
| `digest.py` | Der Steckbrief der Szene für den Agenten (§23) |
| `matching.py` | Merkmalsbezeichner über Operationen hinweg stabil halten (§21.2, §21.3) |

## Die Sache mit der Stabilität

Ein Merkmal, das nach jeder Operation einen neuen Namen bekäme, wäre wertlos
— Passungen und Agentenverweise hingen ins Leere. `matching.py` hält die IDs;
was es trotzdem verliert, fängt `scene/orphans.py` auf und **fragt**, statt
zu raten.

## Grenzen

- **Erkennen heißt nicht ändern.** Hier entsteht keine Geometrie.
- Mehrdeutigkeit wird gemeldet, nicht aufgelöst (§15.7, Regel 21).
