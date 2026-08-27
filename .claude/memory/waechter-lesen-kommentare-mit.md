---
name: waechter-lesen-kommentare-mit
description: Quelltext-Wächter der Suite treffen auch Kommentare und Docstrings — wer über ein verbotenes Muster schreibt, darf es nicht zitieren.
metadata:
  type: feedback
---

Zwei Wächter der Suite lesen den **rohen Quelltext** einer Funktion, nicht
ihren Code: `test_nothing_runs_without_a_click` verbietet `download(` im
Text von `updates.check`, `test_every_worker_survives_the_delivery_of_its_own_signal`
verbietet `self._split = None` im Text der finished-Slots. Am 25.08.2026
beide an **Kommentaren** ausgelöst: Ein Verweis „wie in ``download()``" und
ein Kommentar, der das verbotene Muster als Negativbeispiel zitierte, machten
die Tests rot, obwohl der Code selbst regelkonform war.

**Why:** Die Wächter sind absichtlich stumpf (Textsuche fängt auch Umbauten,
die eine AST-Analyse verfehlt), und das ist ihr Wert — aber wer einen Fix an
so einer Stelle **dokumentiert**, schreibt das Muster leicht wörtlich hin.

**How to apply:** Beim Umformulieren an bewachten Stellen die Sache
umschreiben statt zitieren („das nackte Nullen des Feldes", „beim Paketholen
weiter unten"). Wird ein Wächter rot, zuerst prüfen, ob er Code oder
Kommentar getroffen hat — und den Wächter dabei nicht aufweichen: Er liest
Text, weil Text die billigste vollständige Frage ist.
