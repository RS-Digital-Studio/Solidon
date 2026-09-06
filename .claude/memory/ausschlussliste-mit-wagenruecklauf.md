---
name: ausschlussliste-mit-wagenruecklauf
description: "tools/list_windowed_tests.py schreibt CRLF; eine Bash-Schleife baut daraus --ignore=…\\r, pytest ignoriert nichts, und der 'Massenlauf' fährt still die ganze Suite mit Fensterdateien unter xdist — Zeilen mit tr -d '\\r' lesen und die Wirkung der Ausschlüsse an der gesammelten Zahl prüfen."
metadata:
  type: feedback
  originSessionId: f07e3f31-b0f2-4cae-b55c-218ecd11e007
  modified: 2026-09-06T13:22:29.060Z
---

Am 06.09.2026 fuhr mein Skript den Massenteil der Suite: Fensterdateien aus
`tools/list_windowed_tests.py` lesen, je Zeile `--ignore=<datei>` anhängen,
`pytest -n 4`. Das Werkzeug schreibt unter Windows `\r\n`; die Schleife
(`while read`) ließ das `\r` stehen, pytest bekam `--ignore=tests/test_ui.py\r`
— ein Pfad, den es nicht gibt — und ignorierte **nichts**. Der Lauf fuhr die
gesamte Suite samt 62 Fensterdateien mit vier Arbeitern: 11 448 grün, 22
rot, vier Arbeiterabstürze. Acht der 22 waren Fensterfälle, die einzeln
grün sind; die Diagnose kostete eine Stunde.

**Why:** Ein falscher Ausschluss ist unsichtbar: pytest meldet keinen
unbekannten `--ignore`-Pfad, und die Fortschrittszeichen sehen aus wie
immer. Die gesammelte Testzahl war das einzige Signal (11 470 statt der
rund 6 500 des Massenteils), und die stand erst am Ende.

**How to apply:** Werkzeugausgaben in Bash mit `tr -d '\r'` lesen
(`done < <(python tools/list_windowed_tests.py | tr -d '\r')`), und vor dem
Lauf die Wirkung messen: `pytest --collect-only -q $ignores | tail -1` muss
die Zahl **ohne** Fensterdateien nennen. Besser noch das Werkzeug selbst mit
`sys.stdout.reconfigure(newline="\n")` schreiben lassen — das steht als
Nacharbeit an. Verwandt: [[gefahren-ist-nicht-gefordert]],
[[jede-verkuerzung-ist-eine-messung]].
