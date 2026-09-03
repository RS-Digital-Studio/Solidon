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
actions.py    ──> „was kann ich damit tun" — und warum nicht, wo nichts geht
```

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

## Die Karte

| Datei | Rolle |
|---|---|
| `features.py` | Merkmalserkennung (§21.1) — **2 200 Zeilen**, das größte Modul des Kerns |
| `maps.py` | Analysekarten (§18.4) |
| `digest.py` | Der Steckbrief der Szene für den Agenten (§23) |
| `matching.py` | Merkmalsbezeichner über Operationen hinweg stabil halten (§21.2, §21.3) |
| `actions.py` | Was der Kunde mit einem erkannten Merkmal tun kann — und was nicht, mit Grund. Die Liste fürs Merkmalspanel, **aus dem Register abgeleitet** (§10, §21) |

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
- **Was für kein Werkzeug groß genug ist, ist kein Merkmal.**
  `MIN_CYLINDER_DIAMETER` (0,5 mm) gilt für **alle sechs** eingepassten
  Arten — Bohrung, Zapfen, Verrundung, Kegel, Kugel, Torus. Die Frage steht
  einmal als `_too_small_to_make`, damit die nächste Art sie nicht wieder
  übersieht; beim Torus entscheidet das kleinere von Ring und Röhre.
