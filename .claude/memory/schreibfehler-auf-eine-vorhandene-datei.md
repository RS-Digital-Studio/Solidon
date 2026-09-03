---
name: schreibfehler-auf-eine-vorhandene-datei
description: "OSError 22 oder 13 beim Öffnen einer Datei zum Schreiben, die es gibt: entweder hält der eigene Prozess sie noch offen, oder eine andere Sitzung schreibt gerade — beides heilt derselbe Weg."
metadata:
  node_type: memory
  type: feedback
---

Am 03.09.2026 zweimal aufgeschlagen, mit zwei verschiedenen Fehlernummern und
zwei verschiedenen Ursachen:

- **`tools/make_manual.py`, `OSError 22`** beim Öffnen der fertigen PDF zum
  Schreiben. Zweimal gerissen, einmal bei Englisch, einmal bei Französisch, und
  dazwischen gingen dieselben Sprachen durch. Ursache: `_chapter_of_each_page`
  liest die PDF mit `QPdfDocument`, **Qt hält die Datei offen, solange das
  Dokument lebt**, und das Dokument ist eine lokale Variable, deren Ende der
  Einsammler bestimmt. Ein `document.close()`, und der Bau lief in einem Zug
  durch alle sechs Sprachen.
- **`app/i18n/locales/en.json`, `OSError 13`** mitten in einer Reihe von fünf
  Dateien. Ursache: eine andere Sitzung schrieb dieselbe Datei. Der zweite
  Versuch 0,4 Sekunden später gelang.

**Why:** Ein Schreibfehler auf eine Datei, die es gibt und die man selbst
angelegt hat, liest sich wie ein Fehler der Datei oder des Pfades. Er ist
keiner. Er ist eine Aussage über **Zeitpunkte** — und das Erkennungszeichen ist
genau das: Der Fehler wechselt die Stelle. Wandert er zwischen Läufen, ist
keine Datei die Ursache (siehe [[absturz-frame-ist-die-naechste-allokation]]).
Auf dieser Maschine arbeiten bis zu vier Sitzungen an denselben Dateien
([[parallele-sitzungen-solidon3d]]), deshalb ist die zweite Ursache hier der
Normalfall und nicht die Ausnahme.

**How to apply:** Wer eine Datei liest und gleich darauf beschreibt, **schließt
den Leser ausdrücklich** — nicht dem Einsammler überlassen, und bei Qt- oder
nativen Lesern nie annehmen, der Handle sei mit der letzten Zeile weg. Und wer
eine geteilte Datei schreibt, schreibt sie **daneben und benennt um**
(`tmp.write_text(...)`, `os.replace(tmp, ziel)`) und wiederholt es zwei- bis
dreimal mit kurzer Pause. Beides zusammen kostet zehn Zeilen und nimmt einem
Lauf die Eigenschaft, an einer beliebigen Stelle zu reißen. Ein `retry` allein
reicht nicht, wenn der eigene Prozess der Halter ist — dann wartet man auf sich
selbst.
