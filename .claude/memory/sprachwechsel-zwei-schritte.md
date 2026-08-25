---
name: sprachwechsel-zwei-schritte
description: install_language lädt den Katalog, set_language aktiviert ihn — wer nur eines ruft, misst seine eigene Aufrufreihenfolge
metadata:
  type: project
---

Ein Sprachwechsel in Solidon braucht **beide** Aufrufe, und zwar in dieser
Reihenfolge:

```python
install_language("pt")   # lädt den Katalog
set_language("pt")       # aktiviert ihn
```

Wer nur einen von beiden ruft, bekommt die deutsche Quelle zurück — und zwar
lautlos, denn die Message-ID *ist* der deutsche Text. Am 25.08.2026 zweimal
hintereinander darauf hereingefallen, mit entgegengesetzten Ergebnissen: einmal
mit `install_language` allein („alle Sprachen zeigen Deutsch, `choice_label` ist
kaputt"), einmal mit `set_language` allein nach frischem Import (dasselbe Bild).
Beide Male war der Code in Ordnung.

**Why:** Der Befund sieht wie ein Übersetzungsfehler aus, ist aber eine
Eigenschaft des Messaufbaus. Ein Test, der so misst, meldet einen Fehler, wo
keiner ist — und schlimmer: Er würde einen echten nicht von seinem eigenen
unterscheiden können.

**How to apply:** Vor jeder Aussage über fehlende Übersetzungen erst an einem
Text prüfen, dessen Übersetzung im Katalog nachweislich steht. Und die zwei
Funktionen unterscheiden: `_()` gibt einen `TranslatableText`, der seine Sprache
beim Anzeigen sucht; `tr()` übersetzt **sofort** und friert auf Modulebene die
Sprache des Importzeitpunkts ein — beim Start ist das keine, denn `app.py` holt
`MainWindow` siebzehn Zeilen vor `install_language`.

Siehe [[was-die-suite-nicht-findet]] und [[messwerkzeug-misst-sich-selbst]].
