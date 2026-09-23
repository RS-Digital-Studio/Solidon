---
name: rauschen-auf-einer-maschine-ersetzt-drei-runner
description: "Plattformabhängigkeit lässt sich auf einer Maschine finden: jede plattformabhängige Rechnung um ein ULP verrauschen und den BLAS-Kern tauschen — der Fingerabdruck am Ende eines Weges darf sich nicht rühren."
metadata:
  type: feedback
---

**Man braucht keinen Mac, um zu sehen, was der Mac anders rechnet.** Am
22.09.2026 (RM-187) fand `tests/test_platform_identity.py` auf einer
Windows-Maschine, woran der Änderungsweg hing, den drei CI-Runner nur als
„verschiedene Fingerabdrücke" gemeldet hatten: eine SVD für die Ebene einer
schrägen Mündung und `np.dot` für ihre Lage. Dazu *Drehen*, *Druckoptimal
ausrichten*, den schrägen Schnitt, *Stellung geben* und *Offene Fläche
schließen* — acht rote Wege am HEAD, auf einer Maschine.

Zwei Hebel: `platform_noise()` legt auf BLAS, `einsum`, LAPACK und jede
Winkel-/Exponentialfunktion aus NumPy und `math` ein festes Rauschen von
einem ULP (exakte Ergebnisse ausgenommen), und ein Unterprozess mit
`OPENBLAS_CORETYPE=Nehalem` rechnet `@` mit einem anderen Kern. `@` lässt
sich nicht verrauschen — es ist ein Operator —, der Kerntausch fängt es.

**Why:** Die CI zeigt nur, *dass* es auseinanderläuft, und das erst nach
einem Tag-Lauf; welche Zeile es war, sagt sie nicht. Das Rauschen je
Funktion sagt es sofort, und ein Test daraus schützt jeden neuen Weg.

**How to apply:** Einen Weg, der Geometrie oder eine Wahl zwischen Lagen
erzeugt, in `_WAYS` aufnehmen; wird er rot, per Funktion einzeln
verrauschen, bis die Stelle feststeht (Sonden `noise.py`, `sites.py` unter
`sonden/netzkern/`). Grenze: Ein Vorzeichenwechsel eines LAPACK-Vektors
lässt sich so nicht nachbilden (die Importreparatur war am HEAD grün und
trotzdem abhängig); die Unterscheidung „AVX-512 gegen AVX2" auf gemischten
Linux-Runnern erklärt ein „einmal in vier Läufen" (RM-166). Siehe
[[arm-rechnet-anders-als-x86]] und [[plattformen-funktionieren-gleich]].
