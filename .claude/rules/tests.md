---
paths:
  - "tests/**/*.py"
  - "conftest.py"
---

# Regeln für die Suite

Jede harte Regel aus `AGENTS.md` hat einen Test. Ein Verstoß ist ein roter
Lauf, keine Geschmacksfrage — also ist die Suite die eigentliche Version des
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
| `test_way_one/two/three/four.py` | die vier Hauptwege Ende zu Ende |
| `test_agent_suite.py` | was die Agentenschicht ohne Modell garantiert |
| `test_interface_limits.py` | Oberflächengrenzen §35: höchstens neun Menüs, zwölf Zeilen je Menü, acht Umschalter, acht Felder auf der Vorderseite |

Eine neue Testart bekommt eine eigene Datei; ein neues Fehlerbild wird eine
Testdatei, kein Sonderfall im Code.

## Isolation ist Teil des Tests

`tests/conftest.py` setzt `QT_QPA_PLATFORM=offscreen`, biegt die
Nutzerverzeichnisse in einen Temp-Ordner (§38) und hält die Maschine aus dem
Ergebnis heraus: ein Entwicklerrechner mit installiertem OpenSCAD sieht sonst
etwas anderes als ein Bauserver ohne. Wer diese Fixtures umgeht, prüft nicht,
was er zu prüfen vorgibt.

Dasselbe gilt eine Ebene tiefer, bei den Paketversionen: die Umgebung wird
gegen `constraints.txt` aufgebaut, sonst installiert ein frischer Klon andere
Versionen als der letzte grüne Lauf — und die Suite wird rot, ohne dass sich
eine Zeile Code geändert hat.

`filterwarnings = ["error"]` ist gesetzt: eine Warnung bricht den Lauf. Das ist
Absicht — sie wird behoben, nicht unterdrückt.

Für eine Warnung aus **Fremdcode**, die sich nicht beheben lässt, stehen
darunter Ausnahmen — eng, und nur unter drei Bedingungen: sie nennen den
Meldungstext *und* das auslösende Modul, nicht bloß die Kategorie; der eigene
Code löst die Warnung nachweislich nicht aus; und der Kommentar sagt, wann die
Ausnahme wieder wegfällt. Eine Ausnahme ohne Modulangabe verdeckt irgendwann
einen eigenen Fehler. Wann eine überflüssig geworden ist, zeigt der
wöchentliche CI-Lauf gegen die neuesten Versionen.

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

## Den Lauf messen, nicht einen Filter darüber

Drei Fehlalarme an zwei Tagen, alle aus derselben Wurzel: Gemessen wurde etwas,
das *neben* dem Testlauf stand.

* **Kein `| tail`, kein `| head`, keine Pipe um `pytest`.** Der Rückgabewert der
  Pipe ist der des **letzten** Glieds, nicht der von pytest — ein Absturz mit
  139 sah zweimal wie ein grüner Lauf aus. Und pytest puffert hinter einer Pipe:
  Ein Lauf mit `-q 2>&1 | tail -25` gab anderthalb Stunden lang **kein einziges
  Zeichen** aus und stand dabei längst. In eine Datei schreiben und die lesen;
  wer den Fortschritt sehen will, nimmt `python -u`.
  **Dasselbe gilt für `suite-getrennt.sh`, und der Fall steht in `CLAUDE.md`**
  unter „Auf den Exit-Code sehen, nicht auf eine Schlusszeile" — dort mit der
  Gegenfalle zusammen, weil die beiden sich aufheben, wenn man nur eine kennt.
  Hier steht er nicht ein zweites Mal: Von zwei Fassungen desselben Satzes
  veraltet immer eine.

* **Die Schlusszeilen erscheinen erst am Schluss.** `grep -cE "^(FAILED|ERROR)"`
  über ein laufendes Protokoll liefert immer null, auch wenn zwei Tests längst
  rot sind — die `FAILED`-Zeilen schreibt pytest in der Zusammenfassung. Gezählt
  wird über die **Fortschrittszeichen** (`.` `s` `F` `E` `x`), und ihre Position
  im Strom nennt zusammen mit `pytest --collect-only -q` den Namen des Tests.

* **Die Zusicherung ist der Exit-Code, die Zählzeile ist eine Anzeige.** Das gilt
  auch für `suite-getrennt.sh`: Es zählt „Läufe mit Fehler: N" und gibt sie als
  Exit zurück. Wer die Zeile liest statt `$?`, misst wieder einen Filter.

* **Ein Hintergrundlauf meldet den Status seiner Hülle, nicht den des Programms
  darin.** Am 22.08.2026 dreimal an einem Abend, in drei Sitzungen: Die
  Abschlussmeldung sagte „completed (exit code 0)" — einmal über einem Lauf,
  der mit **139** abgebrochen war, einmal über `geteilt Exit=5`, einmal über
  `geteilt Exit=3`. Das ist die Pipe-Falle in neuer Gestalt und die
  gefährlichere von beiden: Eine Pipe baut man selbst und weiß davon, ein
  Hintergrundlauf sieht aus wie ein Lauf. Also auch hier: Der Lauf schreibt
  seinen eigenen Exit-Code in eine Datei (`…; echo "Exit=$?" > …`), und gelesen
  wird der, nicht die Meldung.

Und die Umkehrung, die dabei aufgefallen ist: Ein Lauf, der **grün meldet und
rot endet**, ist kein roter Test. Drei Fensterdateien enden nach „N passed" mit
`0xC0000409` beziehungsweise einer Zugriffsverletzung — ein Riss beim Abbau. Der
Unterschied steht in `ROADMAP.md`; wer ihn nicht kennt, sucht den Fehler in
einem Test, der nie fehlgeschlagen ist.

## Ein roter Leistungstest ist erst dann eine Regression, wenn er es zweimal ist

`tests/.performance.json` hält die Bestwerte, gegen die die 25-%-Schwelle
misst. Die Datei ist **absichtlich** ignoriert (`.gitignore`), und der Grund
steht bisher nur dort: Die Werte sind maschinenabhängig (Bauplan §31). An
diesem Projekt arbeiten drei Maschinen; die Bestwerte des schnellsten Rechners
würden den Laptop dauerhaft rot färben, ohne dass eine Zeile langsamer
geworden wäre.

Am 22.08.2026 ist das belegt worden, weil zwei Sitzungen gleichzeitig am selben
Projekt rechneten:

| Lauf | Fremdlast | Ergebnis |
|---|---|---|
| A | 48 % | 5 failed, 14 passed |
| B | 16 % | **19 passed, Exit 0** |

Dieselbe Software, derselbe Tag, dieselbe Maschine. Alle fünf roten waren die
Regressionsschwelle, kein absoluter Zielwert aus §31, und im ruhigen Lauf lagen
alle Einzelzeiten darunter (Orientierungssuche 17,47 s, Subdivision 2,46 s,
Blending 1,33 s, Skizzenlöser 0,21 s).

**Daraus folgt für jeden roten Leistungstest:**

* **Denselben Stand ein zweites Mal fahren**, bevor eine Regression gemeldet
  wird — nicht den Vorgängerstand. Schwankt die *Menge* der roten Tests, ist es
  Last und kein Code. Das kostet eine Minute statt eines Arbeitsbaums.
* **Auch die Reihenfolge zählt.** `sketch_solve_200` misst 114 ms allein und
  162 ms hinter `test_slice.py` — 38 % Unterschied bei einer Schwelle von 25.
* **Die Fremdlast ist meistens die eigene Arbeit.** Ein zweiter Testlauf, eine
  parallele Sitzung, ein offenes Fenster. „Auf einer ruhigen Maschine messen"
  hilft niemandem, weil eine Maschine immer ruhig aussieht; nachsehen, was
  sonst rechnet, hilft.

Das ist der einzige Teil des Tors, dessen Rot nicht „nicht fertig" bedeutet.

## Fremdlast macht auch funktionale Tests rot, nicht nur Messungen langsam

Der Abschnitt oben handelt von Zeiten, und deshalb liest man ihn als Regel für
Leistungstests. Am 22.08.2026 hat sich gezeigt, dass er zu eng gefasst ist: Eine
Sitzung fuhr `test_ui.py` **ohne Schloss** mitten in einem fremden Tor und bekam
**Exit 139** mit Zugriffsverletzung, zwei Fehlschlägen und acht Minuten
Stillstand bei elf von 255 Tests. Sie hielt es für eine Folge ihrer eigenen
Änderung an Objektlebensdauern — plausibel, und falsch. Dieselben zwölf Tests
einzeln: **0,87 s, grün.** Im selben Zeitraum lief `test_ui.py` in einem anderen
Prozess unter dem Schloss vollständig durch (255 passed).

Bei einer Messung äußert sich Last als *langsamer*, und dagegen hilft die Regel
„zweimal fahren". Bei einem funktionalen Test äußert sie sich als **rot** — und
dann sucht man den Fehler im eigenen Code, wo keiner ist. Die Reihenfolge kehrt
sich damit um:

* **Unter dem Schloss fahren, bevor überhaupt geurteilt wird**
  (`tools/gate_lock.py run --who <name> --wait 1800 -- …`), nicht erst, wenn ein
  Ergebnis merkwürdig aussieht. Das Schloss kostet Wartezeit; ein falsch
  zugeordneter Absturz kostet eine halbe Stunde Suche im richtigen Code.
* **Der billigste Gegenbeweis ist der einzelne Test.** Läuft er allein in einer
  Sekunde durch, war es die Maschine.
* **Steht er oder rechnet er?** Der Prozessbaum sagt, welche Datei offen ist
  (`Get-CimInstance Win32_Process`), und `Get-Process -Id N | Select CPU` zweimal
  im Abstand von acht Sekunden trennt „hängt" von „dauert". Am selben Tag stand
  ein Lauf zwölf Minuten bei **0,00 CPU-Sekunden** und 508 MB — ohne diese Zahl
  wäre es eine Vermutung geblieben, und die Datei lief einzeln in 10,77 s durch.

**Und die Grenze des Schlosses, weil sie nicht offensichtlich ist:** Es
serialisiert die *Rechenzeit*, nicht den *Arbeitsbaum*. Wer im geteilten Baum
misst, liest die ungestageten Dateien aller Sitzungen mit. Gefährlich ist dabei
nicht der falsche Fehler — der fällt auf —, sondern der **falsche Erfolg**: Ein
fremder Zwischenstand kann einen Lauf auch grün machen, und dann hält jemand
seine Arbeit für abgesichert. Ein eigener Arbeitsbaum ist die einzige
vollständige Antwort (`claude --worktree <name>`).


## Wenn ein Lauf steht: py-spy

Ein Testlauf, der bei 0,00 CPU-Sekunden über ein Intervall steht, sagt nicht,
**wo** er steht. Der Exit-Code kommt nie, das Protokoll endet mitten in einer
Datei, und `faulthandler` hilft nur dem Faden, der stürzt — hier stürzt keiner,
hier wartet einer.

`py-spy` hängt sich an einen **laufenden** Prozess und liest seinen Stapel,
ohne ihn anzufassen:

```
py-spy dump --pid 60560 --native
```

`--native` ist der Teil, der zählt: Ohne ihn endet der Stapel an der
Python-Grenze, und genau dahinter liegt die Frage — in Qt, in VTK, im Warten
auf ein Ereignis, das nicht kommt.

**Es liegt in der Nutzer-Umgebung und nicht in der `.venv`**
(`%APPDATA%\Python\Python313\Scripts\py-spy.exe`), und das ist kein Zufall:
Ein Werkzeug, das man an einen fremden Prozess hängt, ist so wenig Bestandteil
des Produkts wie `git` oder ein Debugger. In `constraints.txt` hätte es die
Lizenzprüfung und den nächsten Klon berührt, ohne dass die Anwendung es je
importiert. Entschieden am 22.08.2026.

**Die Prozessnummer findet man nicht über die Elternkette.** Auf Windows setzt
niemand die Elternnummer um, wenn der Elternprozess endet — der `pytest` unter
einem Schloss hängt dann sichtbar an einer ganz anderen Kette oder an keiner.
Gesucht wird deshalb am Kommando:

```
Get-CimInstance Win32_Process -Filter "Name like '%python%'" |
  Select-Object ProcessId, CommandLine
```

Dasselbe tut `tools/gate_lock.py` in `_test_processes()`, und aus demselben
Grund. Wer nur die direkten Kinder des Schlosshalters zählt, findet den
stehenden Lauf nicht — an einem Abend zweimal passiert.

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
