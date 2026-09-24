---
name: sondenbefund-gegen-den-test-lesen
description: Ein Verhalten, das in der Fenstersonde falsch aussieht, kann eine getestete Entscheidung sein — vor dem Umbau die Tests des Bedienelements lesen
metadata:
  type: feedback
---

Am 24.09.2026 zeigte die Fenstersonde nach *Abbrechen* in der Maßgruppe einer
Bohrung: Maße und Langlochknöpfe weg, rechts *Zum Langloch ziehen* scharf mit
Vorgabelänge und freiem Übernehmen. Das sah nach einem Fehler aus, und der
Umbau (Abbrechen setzt zurück, Maße kommen frisch wieder) war schon
geschrieben — bis `grep _measure_cancel tests/` den Test
`test_cancel_below_apply_discards_what_waits` fand: „die Maße im Bild sind
zu", „der Weg zurück ins Bild steht". Eine andere Sitzung hatte genau dieses
Verhalten entschieden und festgeschrieben. Der Umbau ist wieder heraus; die
Frage ging an Robert. Seine Antwort war eine dritte Lesart, die keiner der
beiden Entwürfe hatte: „abbrechen = deselektieren".

**Why:** Die Fenstertests laufen nur beim Release. Ein Umbau gegen einen
solchen Test fällt im Entwicklungstor nicht auf, sondern erst Tage später —
und dann sieht es aus, als hätte der Test sich geirrt.

**How to apply:**
- Vor jeder Verhaltensänderung aus einem Sondenbefund: Tests nach dem
  Bedienelement durchsuchen (Objektname, Attribut, Knopftext), die Docstrings
  lesen.
- Sichert ein Test das Verhalten zu, ist es eine Entscheidung: nicht still
  umentscheiden, sondern Robert mit beiden Lesarten fragen.
- Siehe [[beheben-statt-notieren]] — das gilt für Fehler, nicht für
  Entscheidungen, die jemand anders getroffen hat.
