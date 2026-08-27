---
name: vtk-qt-referenzen-halten-zu-lange
description: "Abstürze am Ende eines Suite-Laufs — und falsche Bilder im zweiten Fenster — kommen fast immer von einer Referenz, die ein Qt- oder VTK-Objekt am Leben hält."
metadata: 
  node_type: memory
  type: project
  originSessionId: 04b5a4bb-f8b4-48b1-8e60-384aa7e64159
  modified: 2026-08-07T22:36:37.634Z
---

„Windows fatal exception: access violation", ohne Zeile, am Ende eines
Suite-Laufs: In Formwerk ist das dreimal dieselbe Ursache gewesen — eine
Python-Referenz hält ein Qt- oder VTK-Objekt länger am Leben, als es soll. Der
Speicherbereiniger räumt es später ab, und dann steht ein C++-Objekt hinter
einer Referenz, die es nicht mehr gibt.

Die drei Fälle vom 4./5. August 2026:

1. **Referenzschleife.** Der Interaktionsstil bekam `self._on_right_click` als
   gebundene Methode: VTK hält den Stil → Stil hält den Viewport → Viewport
   hält den Plotter → Plotter hält den Interactor → Interactor hält den Stil.
   Gelöst mit `weakref.ref(self)` und einem Closure darüber
   (`app/ui/viewport.py`, `set_navigation`).
2. **Fenster ohne Aufräumung.** Ein Test baute sein eigenes `MainWindow`,
   statt die Fixture in `tests/test_analysis_ui.py` zu nehmen, die auf alle
   Arbeiter wartet.
3. **Fenster ohne Zweck.** Zwei Tests forderten die `window`-Fixture an und
   prüften nur eine reine Funktion. Jedes Fenster bringt einen VTK-Viewport
   mit.

Der vierte Fall, 8. August 2026, **stürzte nicht ab — er log**:
`tools/make_figures.py` baut je Sprache ein `MainWindow`, und im zweiten lag
der Orientierungswürfel als handtellergroßes Achsenkreuz quer über dem Modell.
`close()` gibt das `QtInteractor` nicht frei; es bleibt am Fenster hängen und
mit ihm sein Renderfenster, und das zweite Fenster erbt einen Kontext, der
dem ersten noch gehört (Begleitmusik in der Ausgabe: `wglMakeCurrent failed`).
`release_viewport` schließt den Plotter zwischen den Durchgängen.

**Why:** Vor dem ersten Fund galt das als unvermeidliches Rauschen — der
Docstring der Fenster-Fixture führte es als „unabhängig von dieser Fixture",
nachgemessen an vier Läufen. Die Messung stimmte, gesucht wurde an der
falschen Stelle. Nach Fall 1 lief die ganze Suite wieder in einem Zug durch.

**How to apply:** Beim nächsten Abriss — und bei jedem VTK-Fehlbild im
zweiten Fenster eines Prozesses — zuerst fragen: *welche Python-Referenz
hält ein Qt- oder VTK-Objekt am Leben, das längst weg sein sollte?* Die
Gegenprobe für den zweiten Durchgang ist billig: denselben Durchgang als
ersten fahren; ist er dann sauber, liegt es am Vorgänger. Callbacks
an VTK-Objekte gehen über `weakref`. Ein Test, der ein Fenster anfordert, muss
es benutzen — sonst nimmt er keins (`ReportPanel()` allein tut es meist).
Gegenprobe, ob es überhaupt die eigene Änderung ist: ein eigener Arbeitsbaum
auf HEAD, **nicht** `git stash` — im geteilten Baum nimmt der fremde Arbeit
mit (siehe [[leistungstests-fremdlast]]).

**Und seit dem 23.08.2026 gilt die Umkehrung genauso, sie ist die Kehrseite
derselben Sache:** Nicht nur „was wird zu lange gehalten", sondern **„was
wird im falschen Thread freigegeben"**. Solange Lambda-Ringe die Fenster
hielten, sammelte sie niemand ein; seit sie aufgelöst sind, tut es der
Speicherbereiniger — und der läuft in dem Thread, dessen Allokation gerade die
Schwelle reißt. Ruft er dort `~QMenuBar`, nimmt der Destruktor den Qt-Mutex
und will den GIL, den der Hauptthread hält, während der auf genau diesen Mutex
wartet. Das Ergebnis **steht** bei 0,00 CPU, statt zu stürzen.

Beide Stapelabzüge und die drei gescheiterten Anläufe (`gc.collect()`,
`leash.undisturbed()`, zweimal `deleteLater`) stehen in `tests/conftest.py`,
die Folge für die Oberfläche in `.claude/rules/oberflaeche.md`. Der Ring-Umbau
bleibt richtig — er ist nur nicht unbeteiligt.
