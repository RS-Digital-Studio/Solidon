---
name: sollwert-aus-dem-pruefling
description: "Ein Test, der seine Erwartung mit der geprüften Funktion erzeugt, prüft Aktualität statt Richtigkeit — und ein Fehler, den eine spätere Stufe halb aufräumt, tarnt sich selbst."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 2eb507e7-921f-412b-8865-41547ee94d5d
  modified: 2026-08-23T21:59:12.086Z
---

**`expected = body_html(quelle); assert expected in seite`** — dieser Test lief
in `tests/test_legal.py` grün, während im Muster-Widerrufsformular sichtbares
Markup stand: `ich/wir (\<em>) den von mir/uns (\</em>)`, mitten in dem Text,
den Anlage 2 zu Art. 246a EGBGB **wörtlich** vorgibt.

Er konnte es nicht fangen. Seine Erwartung stammt aus `body_html` — also aus
genau der Funktion, die den Fehler machte. Gegen einen Konverter, der
verfälscht, ist er blind, weil er dieselbe Verfälschung erwartet.

**Why:** Selbstkonsistenz und Sollwert **sehen im Code gleich aus**. Beide sind
ein `assert` mit einer Erwartung daneben, beide werden grün, beide fühlen sich
wie Abdeckung an. Der Unterschied — woher die Erwartung kommt — entscheidet
allein, ob die Prüfung etwas wert ist. Betroffen ist jedes Erzeugnis:
`make_legal.py`, `make_manual.py`, `make_seo.py`, Changelog, Website.

**Der Fehler tarnte sich zusätzlich selbst.** Der Konverter räumte hinter den
Ersetzungen die *übrig gebliebenen einzelnen* `\*` auf. Die Fußnote am Ende
(„(*) Unzutreffendes streichen.") war deshalb korrekt — nur die Zeilen mit
**zwei** Sternchen waren zerstört, also genau die, auf die es ankam. Wer beim
Durchsehen unten anfängt, sieht ein heiles Dokument.

**How to apply:**

1. **Bei jedem Test über ein Erzeugnis fragen: woher kommt die Erwartung?**
   Aus dem Erzeuger → er prüft nur, ob neu gebaut wurde. Von außen (Gesetzestext,
   Norm, handgeschriebener Sollwert) → er prüft Richtigkeit. Beides ist
   berechtigt, aber nur das zweite fängt einen falschen Erzeuger.
2. **Eine spätere Stufe, die teilweise aufräumt, verkleinert das sichtbare
   Fehlerbild, nicht den Fehler.** Wo eine Bereinigung hinter einer
   Umwandlung steht, den Fall suchen, den sie *nicht* erwischt.
3. **Ein Positivtest schlägt fehl, wenn er nichts findet. Ein Negativtest
   schweigt.** Das ist der strukturelle Kern und keine Sorgfaltsfrage: Ein
   `not in`, das am echten Fehlerbild nicht anschlägt, ist von einem wirksamen
   **nicht zu unterscheiden** — beide sind grün. Der Nachfolgetest verbot
   `<em>`, `\*`, `\<` und `&lt;em&gt;`, aber auf dem Text *nach* dem Tag-Strip;
   gemessen am echten Fehlerbild greift dort **keine der vier** (`<em>` ist als
   Tag entfernt, `\*` steht nicht mehr da, weil das Sternchen zu `<em>` wurde).
   Übrig bleibt `(\)` — deshalb ist `"\\"` das Verbot, das trägt.
   **Konsequenz: die Gegenprobe gehört in den Test selbst.** Er stellt das
   Fehlerbild nach und prüft, dass sein eigenes Verbot daran anschlägt
   (`tests/test_legal.py`, `cf1160b`).
4. **Eine Gegenprobe, die man ausgibt, muss man auch lesen.** `3d-druck-3a`
   hatte die Ausgabe vor Augen — `ROT - fehlt: [...], Reste: -` — und las
   „Reste: —" als „keine Reste, gut" statt als „greift nicht". Am **kaputten**
   Text. Eine Stunde, nachdem ihr ein stummer Tabelleneintrag nachgewiesen
   worden war, in einem Test, der genau davor warnen sollte. Derselbe Fall wie
   [[messwerkzeug-misst-sich-selbst]] Punkt 6: ein stummer Eintrag sieht aus
   wie ein wirksamer.

5. **Und die Gegenrichtung: ein Sollwert aus einer Geometrie, die es nicht
   gibt.** Am 03.09.2026 verglich ich einen erkannten Merkmalskörper mit
   „einer halben Kugel r = 8" — 333,94 gegen 1072,3, ein Faktor drei, und
   fast eine Fehlmeldung an die Sitzung, die gerade die Erkennung repariert
   hatte. Die Kugel saß aber vier Millimeter **über** der Fläche; der
   Ausschnitt war eine Kalotte von 4 mm Höhe, analytisch 335,1, und die
   Messung traf sie auf drei Promille. Der Fehler lag nicht in der Messung
   und nicht im Prüfling, sondern im **Sollwert**: Eine halbe Kugel und eine
   flache Kalotte sehen im Kopf gleich aus, wenn man die Einsinktiefe nicht
   mitrechnet. Wer einen analytischen Vergleichswert hinschreibt, rechnet ihn
   **mit den Zahlen des Aufbaus** und nicht aus der Vorstellung des Körpers.

Verwandt: [[eine-kette-endet-am-letzten-glied]] — dort deckt eine *zutreffende*
Begründung im Docstring eine Lücke; hier deckt eine *tautologische* Erwartung
einen falschen Erzeuger. Und [[messwerkzeug-misst-sich-selbst]], Punkt 1:
an einem Fall prüfen, dessen Ausgang feststeht.
