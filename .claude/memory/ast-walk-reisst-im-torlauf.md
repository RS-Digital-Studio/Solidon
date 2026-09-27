---
name: ast-walk-reisst-im-torlauf
description: "TypeError oder Zugriffsverletzung mitten in ast.walk ist diese Maschine, nicht der Test, nicht die conftest und nicht CPython — am 27.09.2026 auch ohne pytest und unter Python 3.13, nur in Fenstern, in denen die bevorzugten Kerne am höchsten takten; zuordnen nur mit verschränkter Gegenprobe."
metadata:
  type: project
---

Am 12.09.2026 in zwei aufeinanderfolgenden Torläufen (tor2, tor3 über
`suite-getrennt.sh`, abgekoppelt per pwsh): `test_every_text_is_translated`
riss einmal bei `[it]`, einmal bei `[fr]` — dieselbe Funktion, `[en]` und
`[es]` davor grün —, und `test_no_operation_runs_a_foreign_program` einmal.
Beide Tests parsen alle Quelldateien und laufen mit `ast.walk` darüber; die
Ausnahme kommt aus `ast.iter_fields` — `for field in node._fields` mit
„'str' object is not an iterator" oder „'Constant' object is not iterable".
Ein Tupel, dessen Iterator ein `str` ist, gibt es in reinem Python nicht.

Gemessen: kein `pytest-randomly`, feste Reihenfolge; die Tests davor in
beiden Dateien rechnen keine Geometrie (Dokument-, Tour-, Katalogprüfungen),
eine Heap-Beschädigung aus eigenem Code scheidet damit aus. Dreimal
nacheinander standalone gefahren (`tests/test_foreign.py
tests/test_translations.py`, 209 Tests): dreimal grün. Der Torlauf davor
(tor1, 11.09.2026, 22:30) hatte den Fehler nicht. Im selben Lauf riss der
Leistungslauf mit Zugriffsverletzung **beim Formatieren einer Fehlermeldung**
(`_pytest._code.code.firstlineno`), nicht im Test.

**Why:** Ein Fehler, der die Stelle wechselt, keine Spur hinterlässt und in
einem frischen Prozess nicht wiederkommt, ist eine Aussage über die Umgebung
und nicht über den Test — dieselbe Familie wie
[[speicherriss-hat-keine-ausloesende-zeile]] und
[[rtree-abstuerze-im-langen-lauf]]. Wer ihn als Testfehler liest, sucht in
Katalogen und Registern nach etwas, das nicht da ist.

**How to apply:** Die Regel „standalone dreimal fahren, grün ist der
Nachweis" ist seit dem 27.09.2026 ersetzt — siehe unten. Das Tor zählt
trotzdem rot (die Regel aus `CLAUDE.md`: ein späterer sauberer Lauf ist ein
eigener Nachweis).

## Gemessen am 27.09.2026 — die Maschine, und wann

Anlass: `test_language_rules.py` fiel im Pre-Commit-Hook und in Einzelläufen
mit denselben Bildern (`'Load' object is not iterable` für
`node._fields`, `'in <string>' requires string as left operand, not
str_ascii_iterator` im Umlaut-Generatorausdruck). Eingegrenzt in der
Durchsicht 0.5.1, jeder Lauf ein eigener Prozess, im selben Zeitfenster:

| Variante | rot |
|---|---|
| mit conftest | 1/20, dazu 2/12 im Hauptbaum |
| conftest ohne jede autouse-Fixture | 2/30 |
| conftest vollständig leer geschaltet (kein `app.ui`, keine Kernimporte, keine Umgebung, kein Importhaken) | 7/30 |
| `--noconftest` | 4/30 |
| `PYTHONMALLOC=debug` | 2/10, dasselbe Bild, keine Heap-Signatur |

Beim ersten Test sind ohne conftest nur Erweiterungen der
Standardbibliothek geladen. Eine Nachstellung **ohne pytest und ohne
Solidon-Code** — parsen, zweimal `ast.walk`, der Umlaut-Generatorausdruck,
nur Standardbibliothek — stürzte im nächsten Fenster unter 3.14.7 **und
unter 3.13.14** ab, im selben `ast.iter_fields`. Die frühere Vermutung
„CPython 3.14.7 und die nativen Bibliotheken" ist damit widerlegt; 3.14.7
hat außerdem wieder den generationellen Sammler von 3.13 (Rückbau in
3.14.5), ein inkrementeller Sammler ist nicht beteiligt. Der Sammler ist
überhaupt nicht nötig: Mit `gc.disable()` ab Sitzungsbeginn — am Ende
nachgewiesen, keine einzige Sammlung — fiel die Sprachprüfung 4 von 60 Mal,
die Kontrolle daneben 5 von 60.

**Die Rate hängt an der Uhrzeit, nicht an der Einstellung.** 19 von 147
Läufen rot zwischen 02:34 und 03:04, danach über 120 grün in Folge — frei,
auf P-Kernen, auf E-Kernen —, dann um 03:50 sechs Abstürze in drei
Minuten. Ein Protokoll von Last und Takt je Kern alle zwei Sekunden
(PDH-Zähler `\Processor Information(0,N)\% Processor Performance` über
`PdhAddEnglishCounterW`, das System ist deutsch lokalisiert) zeigt das
Fenster: Gesamtlast 9–20 %, der Prozess auf einem der beiden bevorzugten
Kerne (logisch 8–11, Scheduling-Klasse 2), und die takteten mit 184–188 %
des Nenntakts statt sonst 181–183 %. Unter Volllast der Nachbarsitzungen
(60–97 %, 167–175 %) fiel nichts. Das ist das Muster der Raptor-Lake-
Instabilität: höchster Einzelkerntakt auf den bevorzugten Kernen.

Das Fehlerbild passt dazu und nicht zu einem Programmfehler: Es sind keine
freigegebenen Blöcke (der Debug-Allokator sieht nichts), sondern Zeiger, die
einen Stapelplatz daneben liegen — ein plausibles Nachbarobjekt, daher
`'str' object is not an iterator` mit dem Feldnamen als „Iterator" — oder
weit daneben, dann Zugriffsverletzung, einmal sogar im C-Parser von
`ast.parse`.

**Why:** Eine Einzelmessung sagt bei einer Rate, die mit der Uhrzeit
zwischen null und einem Viertel springt, nichts. Die ersten Affinitätsreihen
dieses Tages sahen wie ein Befund aus („auf einer Kernsorte fest: grün");
erst die verschränkte Reihe mit freier Planung daneben zeigte, dass nur das
Fenster zu Ende war. Und „mit conftest 2/12, ohne 0/12" hatte schon eine
Zuordnung zur conftest nahegelegt — 0 aus 12 kommt bei 13 % Rate mit 19 %
Wahrscheinlichkeit vor.

**How to apply:**

- `TypeError`, `NameError` für einen eingebauten Namen oder eine
  Zugriffsverletzung an einer Stelle, die so nicht fehlschlagen kann: nicht in
  conftest, CPython oder den nativen Bibliotheken suchen, sondern
  [[native-bibliotheken-speicher]] lesen.
- Zuordnen nur **verschränkt**: Variante und Kontrolle abwechselnd im selben
  Zeitraum, je Lauf ein Prozess, Exit-Code direkt gelesen, und das
  Takt-Protokoll daneben. Dreimal grün hintereinander beweist bei 13 % Rate
  nichts (0 aus 3 kommt mit 66 % vor).
- Die schnellste Gegenprobe ist der Kern: dieselbe Variante einmal frei und
  einmal per `SetProcessAffinityMask` auf die nicht bevorzugten P-Kerne
  (Maske `F0FF`, logisch 0–7 und 12–15) im Wechsel. Am 27.09.2026 fiel die
  Nachstellung frei 6 von 60 Mal und gepinnt 0 von 60 Mal im selben
  Zeitraum. Fällt die gepinnte Variante genauso, ist es etwas anderes.
- Ein Befund, der nur in einem Fenster auftritt, ist erst dann Code, wenn er
  im Fenster **mit** und **ohne** die verdächtige Änderung unterschiedlich
  häufig ist.
