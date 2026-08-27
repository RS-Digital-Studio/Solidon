---
name: gemessene-frage-ist-nicht-die-gestellte
description: "Eine Suche liefert immer eine Antwort — aber auf die Frage, die sie stellt, nicht auf die, die man hat. Vor dem Schluss prüfen, ob beide dieselbe sind."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: fd3340f1-dc7c-45b2-a76c-25431a7a9212
  modified: 2026-08-27T04:32:09.949Z
---

Jede Suche liefert ein Ergebnis, und das Ergebnis sieht aus wie die Antwort.
Es ist aber die Antwort auf die Frage, die das **Werkzeug** stellt — und die
ist selten wörtlich die, die man im Kopf hatte.

Am 27.08.2026 dreimal an einem Abend, in zwei Sitzungen:

- **Ich:** „Welche Operationen brauchen ein Merkmal?" Gemessen habe ich
  „welche Dateien erwähnen `ValidationError` neben `at_feature`" — drei. Nur
  eine verlangt es wirklich; die anderen beiden werfen für ein *untaugliches*
  Merkmal, nicht für ein fehlendes. Ich stellte zwei Operationen auf Pflicht,
  `origin/main` wurde rot, und ein ausgeliefertes Beispiel begrüßte den Kunden
  mit einem Fehler.
- **27:** „Welcher Commit hat `lid.py` kaputtgemacht?" Gemessen hat sie
  `git log --oneline -3 -- <datei-a> <datei-b>` und den obersten Treffer
  genommen — das beantwortet „wer fasste zuletzt **eine der beiden** an".
  `git show --stat` hätte in einer Sekunde gezeigt, dass der Commit `lid.py`
  gar nicht berührt.
- **27, eine halbe Stunde vorher:** „Wessen Commit nahm meine Zeilen mit?" Dass
  sie mitgingen, war gemessen und stimmte; wem der Commit gehörte, war geraten.

**Why:** Die Ersatzfrage ist immer die, die leichter zu greifen ist — ein
`grep` über Text statt einer Prüfung am Verhalten, ein `git log` über Pfade
statt `git show --stat` über einen Commit. Sie liefert eine plausible Zahl,
und niemand fragt, ob sie zur Ausgangsfrage passt. **Schlimmer wird es, wenn
ein Test die Fehlmessung festschreibt:** Er wiederholt die Unwahrheit nicht
nur, er macht sie haltbar. (Derselbe Abend: `["obj_2", "obj_3"]` sicherte
jahrelang grün einen Fehler beim Duplizieren zu.)

**How to apply:** Vor dem Schluss den Satz laut bilden — „Ich habe gemessen:
X. Ich will wissen: Y. Ist X = Y?" Wo sie auseinandergehen, ist die Prüfung am
Verhalten billig:

- Verhalten statt Text: die Funktion mit dem Grenzfall aufrufen, nicht ihre
  Datei durchsuchen. `plane_of` sagte die Antwort **im ersten Satz seines
  Docstrings** — eine Ebene tiefer als die Stelle, an der gezählt wurde.
- Urheberschaft: `git show --stat <commit>` statt `git log -- <pfade>`. In
  einem Baum mit vier Sitzungen ist „wer war das" nie aus dem Verlauf zu
  lesen, nur aus dem, was der Commit tatsächlich anfasst.

Verwandt: [[bekannte-familie-erklaert-nicht-den-ausloeser]] (dort ist die
Erklärung bequem, hier die Messung), [[messwerkzeug-misst-sich-selbst]] und
[[sollwert-aus-dem-pruefling]].
