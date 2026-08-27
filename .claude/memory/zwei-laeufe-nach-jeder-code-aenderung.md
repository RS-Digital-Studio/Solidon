---
name: zwei-laeufe-nach-jeder-code-aenderung
description: "Nach jeder Änderung an app/ oder tools/: test_language_rules und ruff check ohne Pfadangabe. Zusammen sechs Sekunden, und sie fangen den Fehler, der sonst auf origin landet."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: fd3340f1-dc7c-45b2-a76c-25431a7a9212
  modified: 2026-08-27T08:30:23.319Z
---

Zwei Läufe, zusammen unter zehn Sekunden, nach **jeder** Änderung an `app/`
oder `tools/`:

    .venv\Scripts\python.exe -m pytest tests/test_language_rules.py -q
    .venv\Scripts\python.exe -m ruff check .

Beide **ohne Pfadangabe**. Genau daran ist es am 27.08.2026 dreimal
gescheitert: Ich habe `ruff check app/core/figures.py` gefahren, grün bekommen
und committet — und `origin/main` war rot, weil `test_language_rules` fünf
deutsche Schleifenvariablen fand (`oben`, `titel`, `wert`, `aktiv`, `satz`).
Dieselbe Sorte an einem Tag: `vorhanden`/`gewaehlt` in `paint.py`,
`durchmesser`/`steigung` in `labels.py`, dann die fünf in `figures.py`.

**Why:** Die Sprachregel ist ein Test, keine Geschmacksfrage — und sie ist der
einzige, den ruff nicht mitfängt. Wer eine Datei anfasst, prüft die Datei;
diese beiden Läufe prüfen den **Bestand**, und das ist der Unterschied. Sie
kosten so wenig, dass jede Abwägung teurer ist als der Lauf.

**How to apply:** Bei Textänderungen (Docstrings, `tr()`-Zeichenketten,
Kommentare) reicht ruff. Sobald eine **Schleife, eine Zuweisung oder ein
Parameter** dazukommt, ist der Sprachtest fällig — dort entstehen die
Bezeichner. Eine `for a, b, c in (...)`-Zeile mit fünf deutschen Namen ist in
zwei Minuten geschrieben und in drei Sekunden gefunden.

Und: **`GERMAN_STEMS` nennt nicht alles.** Von meinen fünf standen drei in der
Liste, `oben` und `aktiv` nicht — der Test meldete drei, falsch waren fünf.
Wer nur die gemeldeten umbenennt, lässt die übrigen stehen, bis jemand den
Stamm nachträgt. Die Regel gilt der Sprache, nicht der Liste.

Verwandt: [[was-die-suite-nicht-findet]] (dort die Fehler, die kein Test
findet — hier der, den ein Test findet und den niemand fährt).
