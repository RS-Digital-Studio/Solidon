---
name: begrenzt-am-falschen-mass
description: "Ein Cache mit LRU-Grenze gilt als aufgeräumt — zählt sie Einträge und wiegen die verschieden viel, hält er trotzdem ein Gigabyte."
metadata:
  type: feedback
---

Am 03.09.2026 in `perceive/features.py`, gefunden auf Roberts Frage nach
Dingen, die gesetzt und nie abgeräumt werden.

Der Merkmals-Cache **räumt** auf: LRU mit `CACHE_LIMIT = 256`,
`forget_cache()` vorhanden, in den Tests über eine autouse-Fixture
isoliert. Nach jeder üblichen Prüfung sauber. Gemessen:

```
ein Eintrag für garden-hose-holder.3mf   3,9 MiB
  davon Flächenindizes                     2,7 MiB  (97 425 Stück à 28 Byte)
mal 256                                     991 MiB
der Kundenverlauf, mit dem 256 begründet ist (132 Netze)   ~500 MiB
```

**Die Grenze zählte das Falsche.** Für ein kleines Teil sind 256
Einträge sieben Megabyte — dort soll der Cache voll ausgenutzt werden,
und die Anzahl ist das richtige Maß. Für ein großes kostet
derselbe Zähler das Hundertfache. Die Antwort sind **zwei** Schranken, nicht
eine kleinere Zahl: Anzahl für die leichten, Gewicht für die schweren.

**Die Voraussetzung der Klasse, und sie ist eng** (Messung 3d-druck-19 über
alle fünf modulglobalen Caches in `app/`): Sie greift nur, wo die
Einträge **verschieden schwer** sind. `cursors.py` hält kleine
Pixmaps, `discover.py` Pfadangaben — dort ist Zählen das richtige
Maß, und eine Gewichtsschranke wäre Aufwand ohne Ertrag. Wer die Klasse
sucht, sucht also nicht „Cache ohne Gewicht", sondern „Cache, dessen
Einträge um Größenordnungen auseinanderliegen können".

**Why:** „Wird abgeräumt?" ist die falsche Frage, sobald eine Grenze
existiert — sie beantwortet sich mit ja, und die Suche hört auf. Die
Frage lautet: **Was misst die Grenze, und schwankt das?** Ein LRU-Zähler
ist eine Aussage über die Anzahl und keine über den Speicher.

**How to apply:** Bei jedem Cache mit Eintragsgrenze einmal ausrechnen, was
der **schwerste plausible** Eintrag wiegt, und mit der Grenze multiplizieren.
Steht dort eine Zahl, die man nicht als Speicherverbrauch akzeptieren
würde, gehört eine zweite Schranke dazu — und ein einzelner
Eintrag über der Gewichtsgrenze bleibt trotzdem drin, sonst ist der Cache
nicht begrenzt, sondern aus.

**Ein Nebenergebnis, das Suchaufwand spart** (dieselbe Messung): 19 hat die
Geschwister-Signatur aus [[reparierter-fehler-hat-zwillinge]] als AST-Sonde
gebaut — Funktionen nach Namensstamm gruppiert, Aufrufmengen verglichen.
209 Gruppen, 200 Kandidaten, und fast alle waren entweder Fehlalarme (das
Geschwister ruft dieselbe Sache unter anderem Namen) oder **dokumentierte**
Ausnahmen. Sein Schluss daraus ist der brauchbare Teil: *An den Stellen, wo
dieser Code eine Regel bricht, steht meist daneben, warum.* Eine
Struktursonde findet hier wenig; die Zwillinge fand jedes Mal eine Messung am
Verhalten.
