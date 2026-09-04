---
name: docstring-nennt-den-weg-den-der-test-nicht-faehrt
description: "Die Begründung eines Tests nennt den Weg, den er absichern soll — und der Test fährt einen anderen. Der Docstring liest sich dann wie der Beleg für die Lücke, die er offenlässt."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 880d8f7a-c07e-4b8f-b374-5bef80997d00
  modified: 2026-09-04T04:20:25.481Z
---

Am 04.09.2026 in `tests/test_interface_limits.py`:

```
def test_switching_moves_the_tick(window):
    """Qt setzt den Haken beim Klick von selbst — nicht aber, wenn die
    Einstellung von woanders kommt, etwa aus dem Einstellungsdialog."""
    window.action_navigation("cad")
```

Der Docstring nennt den Einstellungsdialog als **den** Grund, aus dem es diesen
Test gibt. Gefahren wird `action_navigation` — der Weg über das **Menü**. Der
genannte Weg geht über `_apply_settings`, und dort standen drei der fünf
Aktionsgruppen; Thema und Navigation fehlten, also ausgerechnet die beiden, die
der Dialog anbietet. Wer die Steuerung dort umstellte, fuhr mit der neuen und
las im Menü weiter die alte als aktiv (Robert gemeldet).

**Why:** Ein Docstring, der einen Weg nennt, wird beim Lesen zur Zusicherung,
dass er gemeint **und geprüft** ist. Beim Schreiben ist er dagegen oft nur die
Motivation: „das kann von woanders kommen" erklärt, warum es `_tick` überhaupt
gibt — nicht, welchen Aufruf die Zeile darunter macht. Wer die Datei später
nach „ist der Dialogweg abgesichert?" durchsieht, findet den Satz, glaubt ihm
und hört auf zu suchen. Das ist die Umkehrung von
[[gefahren-ist-nicht-gefordert]]: Dort führt ein plausibler **Dateiname** an
der Sache vorbei, hier ein plausibler **Satz im Test selbst**. Verwandt mit
[[benannte-falle-schuetzt-nicht]] und [[zusage-die-nur-die-oberflaeche-einloest]].

**How to apply:** Beim Lesen eines Tests den Docstring gegen den **Rumpf**
halten, nicht gegen die Erwartung: Jeder Weg, den die Begründung nennt, muss im
Rumpf als Aufruf stehen — sonst ist er offen. Und beim Schreiben: Nennt die
Begründung zwei Wege, gehören zwei Aufrufe hinein oder ein Satz, der sagt,
warum nur einer. Der billige Griff dazu ist ein `grep` nach der Stelle, die den
Zustand *setzt* (`_tick(`, `save_`, `apply_`) — und dann zählen, ob jeder
Aufrufer dieser Stelle in einem Test vorkommt. Hier hätte das sofort gezeigt,
dass `_apply_settings` fünf Gruppen zu setzen hat und drei setzt
([[die-halbe-regel-sieht-aus-wie-eine-ganze]]).
