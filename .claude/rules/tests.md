---
paths:
  - "tests/**/*.py"
  - "conftest.py"
---

# Regeln für die Suite

Jede harte Regel aus `AGENTS.md` hat einen Test. Ein Verstoß ist ein roter
Lauf, keine Geschmacksfrage — also ist die Suite die eigentliche Fassung des
Regelwerks.

## Was wo geprüft wird

| Datei | Prüft |
|---|---|
| `test_core_isolation.py` | `core` ohne Qt importierbar |
| `test_language_rules.py` | keine deutschen Stämme in Bezeichnern |
| `test_registry_consistency.py` | jede Op vollständig, Kürzel eindeutig |
| `test_corpus.py` | Kennzahlen je Op gegen den Referenzkorpus |
| `test_errors.py` | jede Ausnahme mit Handlungsvorschlag |
| `test_support.py` | die Rückmeldung geht raus — und nur am Knopf (§37.2) |
| `test_licences.py` | Abhängigkeiten gegen die Freigabeliste |
| `test_performance.py` | Budget §31, Regressionsschwelle 25 % |
| `test_way_one/two/three.py` | die drei Hauptwege Ende zu Ende |
| `test_agent_suite.py` | was die Agentenschicht ohne Modell garantiert |

Eine neue Testart bekommt eine eigene Datei; ein neues Fehlerbild wird eine
Testdatei, kein Sonderfall im Code.

## Isolation ist Teil des Tests

`tests/conftest.py` setzt `QT_QPA_PLATFORM=offscreen`, biegt die
Nutzerverzeichnisse in einen Temp-Ordner (§38) und hält die Maschine aus dem
Ergebnis heraus: ein Entwicklerrechner mit installiertem OpenSCAD sieht sonst
etwas anderes als ein Bauserver ohne. Wer diese Fixtures umgeht, prüft nicht,
was er zu prüfen vorgibt.

Dasselbe gilt eine Ebene tiefer, bei den Paketfassungen: die Umgebung wird
gegen `constraints.txt` aufgebaut, sonst installiert ein frischer Klon andere
Fassungen als der letzte grüne Lauf — und die Suite wird rot, ohne dass sich
eine Zeile Code geändert hat.

`filterwarnings = ["error"]` ist gesetzt: eine Warnung bricht den Lauf. Das ist
Absicht — sie wird behoben, nicht unterdrückt.

Für eine Warnung aus **Fremdcode**, die sich nicht beheben lässt, stehen
darunter Ausnahmen — eng, und nur unter drei Bedingungen: sie nennen den
Meldungstext *und* das auslösende Modul, nicht bloß die Kategorie; der eigene
Code löst die Warnung nachweislich nicht aus; und der Kommentar sagt, wann die
Ausnahme wieder wegfällt. Eine Ausnahme ohne Modulangabe verdeckt irgendwann
einen eigenen Fehler. Wann eine überflüssig geworden ist, zeigt der
wöchentliche CI-Lauf gegen die neuesten Fassungen.

## Marker

`slow` für alles, was spürbar länger dauert, `performance` für Messungen gegen
das Budget. Messwerte je Lauf festhalten; eine Verschlechterung um mehr als ein
Viertel gilt als Fehler, nicht als Rauschen.

## Korpus

`tests/data/` ist der Referenzkorpus. Erwartete Kennzahlen stehen gegen Dateien
daraus, nicht gegen selbst erzeugte Ergebnisse. Das Millionen-Dreieck-Modell
liegt nicht im Repository — es wird bei Bedarf erzeugt.

## Beim Schreiben

Deutsche Docstrings sind in `tests/` üblich und in Ordnung; die Sprachprüfung
gilt den Bezeichnern in `app/`. Ein Test beschreibt, **was** er sicherstellt und
**warum** — der Name allein reicht dafür selten.

## Die Gegenprobe

Ein neuer Test, der einen Fund festnagelt, wird **einmal ohne den Fix gefahren**.
Bleibt er grün, prüft er etwas anderes als er behauptet — und das ist kein
Randfall: an einem Tag hat diese Probe fünf Tests verworfen, die alle
überzeugend aussahen.

Die drei Weisen, auf denen sie danebengingen, sind alle dieselbe:

* **Am Weg vorbei.** Der Test rief `_stop_or_close()` von Hand statt den Knopf
  zu drücken — die Verbindung war nie geprüft, und ein
  `rejected.connect(self.reject)` blieb unbemerkt. Wer eine Oberfläche prüft,
  drückt, tippt und wählt; die Methode dahinter ist die zweite Zusicherung, nicht
  die erste.
* **Am Prüfobjekt vorbei.** Der Test baute den `QThread` selbst und startete ihn
  selbst. Damit blieb er grün, als der Dialog von `start()` auf `run()` fiel —
  also genau dann, als die Rechnung wieder im Hauptthread lief. Gebaut wird, was
  die Anwendung baut.
* **An der Aussage vorbei.** `str(op_id) in tooltip` war grün, weil „2" auch in
  „2,40 mm" steht. Eine Teilzeichenkette, die zufällig vorkommt, ist keine
  Prüfung — verglichen wird mit dem ganzen Satz.

Und zweimal hat sie den *Fix* verworfen, nicht den Test: der Einzeiler traf die
falsche von drei gleichen Codestellen, und ein Testfall löste den Fehler gar
nicht aus. Beides wäre ohne sie eingecheckt worden.
