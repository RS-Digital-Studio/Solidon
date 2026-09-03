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

**Nachtrag vom selben Tag, und er ist der wichtigere Teil:** Der erste Fall kam
nach dem `document.close()` wieder — beim englischen Handbuch, nachdem das
deutsche mit 12,4 MB durchgegangen war. **Es gab zwei Halter derselben Datei,
und geschlossen war einer.** Drei Zeilen unter dem Qt-Dokument stand
`PdfReader(str(pdf))`: pypdf liest verzögert und hält den Handle, bis der Reader
eingesammelt wird — und genau darauf ruft dieselbe Funktion `pdf.open("wb")`.
Behoben, indem beide Leser ihren Inhalt aus `BytesIO(pfad.read_bytes())`
bekommen statt über den Pfad.

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

**Und nach dem Fix wird gezählt, nicht gehofft:** Wie viele Stellen öffnen diese Datei? Ein Riss, der nach der Reparatur bei einer *anderen* Sprache oder einem *anderen* Durchgang wiederkommt, ist kein neuer Fehler, sondern der zweite Halter — der erste Fix hat ihn nur seltener gemacht.

**Und gezählt wird mit einer Probe, nicht mit dem Blick.** Der zweite Halter war
gesehen und wieder verworfen worden, weil der Lauf nach dem ersten Fix durchkam
— was fehlte, war eine Messung, die den zweiten zeigt, *während der erste noch
da ist* (3d-druck-81, 03.09.2026). Die gibt es, und sie ist zwei Zeilen: an der
Stelle, an der gleich geschrieben wird, den **exklusiven Zugriff** probieren.

```python
try:
    with pfad.open("r+b"):
        pass
except OSError as fehler:
    print(f"jemand hält {pfad.name} noch: {fehler.errno}")
```

Nach einem Abbruch war die Datei sofort exklusiv öffenbar — der Halter war also
der eigene Lauf. Dieselbe Probe zwischen den beiden Lesern hätte beide auf
einmal gezeigt, statt den zweiten auf die nächste Sprache zu verschieben.
