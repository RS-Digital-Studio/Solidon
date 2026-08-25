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

**Und die Kehrseite davon, die genauso teuer ist: Ein `F` unmittelbar vor einem
bekannten Riss sieht aus wie Teil des Risses.** Am 23.08.2026 stand im Torlauf
vor dem Release

    === tests/test_ui.py ===
    ..............F.Windows fatal exception: access violation

und wurde als ein einziges Ereignis gelesen — vierzehn Punkte, ein F, dann der
bekannte Abriss. Gemeldet wurde „kein einziger echter Testfehler". Das `F` war
eine Regression aus derselben Sitzung, die den Lauf fuhr; gefunden hat sie eine
**zweite** Sitzung, die dieselbe Datei unabhängig gefahren hatte.

Der Abschnitt darüber warnt vor der einen Richtung — einen Abriss für einen
Testfehler zu halten. Diese hier ist die andere: **einen Testfehler für einen
Abriss zu halten.** Wer nur eine der beiden kennt, macht zuverlässig die andere,
und diese Richtung ist die gefährlichere — die erste kostet eine Stunde Suche,
die zweite geht ins Paket.

Praktisch: **Beim Melden eines Laufs gehört die Zahl der `F` dazu, nicht nur die
Zusammenfassung.** Ein Riss verschluckt die Zusammenfassung, in der die Namen
stünden; die Fortschrittszeichen davor überleben ihn.

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
* **Steht er oder rechnet er?** Drei Fragen, und erst zusammen tragen sie eine
  Aussage. Sie kosten zwanzig Sekunden, und jede einzelne davon hat in der Nacht
  vom 22. auf den 23.08.2026 mindestens einmal jemanden in die Irre geführt.

  1. **Welche Prozesse gehören überhaupt zum Lauf?** Nicht die aus dem
     Prozessbaum: Windows setzt die Elternnummer nicht um, wenn ein
     Zwischenprozess endet, und der `pytest` fällt dann heraus. Und nicht alle
     mit `pytest` in der Kommandozeile: Die Hülle von `gate_lock` trägt den
     ganzen geschützten Befehl, wartet aber nur.

     ```
     Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
       Where-Object { $_.CommandLine -match '-m pytest' -and
                      $_.CommandLine -notmatch 'gate_lock' }
     ```

     Zwölf wartende Hüllen sahen einmal aus wie zwölf hängende Läufe — keine
     Rechenzeit, Protokoll steht, die perfekte Signatur, und vollständig falsch.

  2. **Wächst die Rechenzeit?** `Get-Process -Id N | Select CPU`, zweimal im
     Abstand von mindestens fünf Sekunden. Ein einzelner Blick genügt nicht:
     Ein Lauf, der je Fensterdatei einen Prozess startet, hat zwischen Abbau und
     Aufbau **regelmäßig** ein bis zwei Sekunden ohne CPU.

  3. **Wächst das Protokoll?** Die Größe der Ausgabedatei über dieselbe Spanne.
     Das ist die verlässlichste der drei, weil sie unabhängig davon ist, welchen
     Prozess man erwischt hat: **Ein Lauf, dessen Ausgabe nicht wächst, arbeitet
     nicht.**

  Erst wenn über zwanzig Sekunden **keine CPU-Sekunde und kein Byte** dazukommt,
  ist es ein Hänger. Dann sagt `py-spy dump --pid N --native` (siehe unten),
  woran er steht — und die Zahl der Fortschrittszeichen im Protokoll sagt
  zusammen mit `pytest --collect-only -q`, **welcher Test** es ist.

**Und die Grenze des Schlosses, weil sie nicht offensichtlich ist:** Es
serialisiert die *Rechenzeit*, nicht den *Arbeitsbaum*. Wer im geteilten Baum
misst, liest die ungestageten Dateien aller Sitzungen mit. Gefährlich ist dabei
nicht der falsche Fehler — der fällt auf —, sondern der **falsche Erfolg**: Ein
fremder Zwischenstand kann einen Lauf auch grün machen, und dann hält jemand
seine Arbeit für abgesichert. Ein eigener Arbeitsbaum ist die einzige
vollständige Antwort (`claude --worktree <name>`).


**Und die Beschleunigung des Tors macht das Schloss wichtiger, nicht
überflüssiger.** Am 22.08.2026 lag der Vorschlag auf dem Tisch, es auf die
Leistungstests zu schrumpfen — 49 Sekunden brauchen Ruhe, dreißig Minuten
nicht. Die Messung hat ihn widerlegt, und zwar aus der Gegenrichtung: Mit
`-n 8` lastet die Sammelgruppe die Maschine so aus, dass der **fremde** Lauf
kippt. Zwei Läufe derselben Gruppe ohne Schloss gaben **11 failed** und
**0 failed**; die elf lagen in `test_blend.py`, `test_examples.py` und
`test_real_models.py`, und dieselbe Datei allein mit `-n 8` lief grün durch.
Ursache war nicht die Parallelität und keine Reihenfolgeabhängigkeit, sondern
**Speicher**: Acht Prozesse, die je eine speicherhungrige Geometrie rechnen,
sind etwas anderes als einer. Parallelität macht Speicherhunger sichtbar — als
Korrektheitsfehler.

Vorher belegte ein serieller Torlauf einen Kern und störte niemanden. Also:
**Je paralleler das Tor, desto strenger das Schloss.**

Der Gewinn kommt trotzdem, nur an anderer Stelle: nicht dadurch, dass das
Schloss fällt, sondern dadurch, dass das, was es umschließt, kleiner wird. Auf
leerer Maschine gemessen, alles seriell gegen alles parallel:

| | seriell | mit `-n 8` |
|---|---|---|
| Sammelgruppe | 193 s | **57 s** (zweimal, gleiche Menge) |
| Tor insgesamt | ~30 min | **5 min 9 s** |

Die dreißig Minuten waren nie Testzeit. Sie waren Wartezeit, Fremdlast und der
Deadlock beim Fensterabbau. Vier Sitzungen × 30 Minuten sind zwei Stunden
Warten; vier × 5 sind zwanzig Minuten — **das** ist die Zahl, die zählt, nicht
die Laufzeit eines einzelnen Laufs.

**Eine feste Zahl statt `-n auto`.** Auf 32 logischen Kernen startet xdist 32
Worker und stirbt beim Verteilen (`INTERNALERROR KeyError <WorkerController
gw13>`, keine Tests gesammelt). Wichtiger als der Absturz ist aber der Grund
dahinter: Auf einer anderen Maschine ist `auto` etwas anderes, und ein Tor,
das je nach Kernzahl anders misst, hat eine stille Variable. Dieselbe
Begründung wie bei `.performance.json`.

**Zweimal fahren und die Mengen vergleichen, nicht die Zahlen.** Ein Test, der
von einem Vorgänger abhängt, wird bei paralleler Ausführung nicht rot — er wird
*manchmal* rot. Zwei gleiche Läufe sind kein Beweis, zwei ungleiche sind sofort
einer. Beim ersten Einsatz dieses Verfahrens fielen die elf oben auf.



### Wer das Schloss belegt sieht, schreibt nicht

Das Schloss schützt den Halter vor **Rechenlast**. Es schützt ihn nicht vor
**dir**. Wer bei belegtem Schloss eine Datei ändert, verfälscht nicht den
eigenen Lauf — der kommt ja erst noch —, sondern den fremden, der gerade läuft.

Zweimal in einer Nacht, beide Male mit einer „kleinen" Änderung:

* Eine Sitzung schrieb `tr("Außengewinde")` in `digest.py`, während ein fremdes
  Tor lief. Dessen Suite sah den Text und die Kataloge noch nicht: fünf rote
  Übersetzungstests, eine halbe Stunde Suche in einer Sache, die zwei Minuten
  später von selbst geschlossen war.
* Eine andere ergänzte `suite-getrennt.sh` um eine verabredete Zeile, während
  ein fremdes Tor **darauf** lief. Bash liest ein Skript zeilenweise nach: Der
  Lauf starb mit einem Syntaxfehler in einer Zeile, die es nie gegeben hat.

Der zweite Fall ist behoben — das Skript kopiert sich beim Start. Der erste
nicht: Eine Datei, die der laufende Test importiert, lässt sich nicht
wegkopieren. Dafür bleibt nur die Regel. `gate_lock.py status` sagt in einer
Sekunde, ob jemand fährt.

**Und zwar vor jeder Schreiboperation, nicht vor jeder Arbeitseinheit.** Der
dritte Fall derselben Nacht entstand nicht aus Nichtwissen: Die Sitzung hatte
vor dem *vorletzten* Schreiben nachgesehen — das Tor war frei — und danach in
einem Zug weitergearbeitet. Die Prüfung hatte stattgefunden und galt als
erledigt, während das Schloss in der Zwischenzeit den Halter wechselte. Wer
schreibt, sieht **jedes Mal** nach; die Sekunde kostet weniger als ein fremder
Torlauf.

### Der fremden Messung glaubt man so wenig wie der eigenen

Eine Zahl, die eine Sitzung weiterreicht, wird auf dem Weg **fester**, nicht
lockerer: Jede Weitergabe streift eine Unsicherheit ab, bis am Ende eine Zahl
steht, die niemand mehr hinterfragt. In derselben Nacht ist eine ungeprüfte
Zahl über drei Sitzungen gewandert und in einer Meldung gelandet, die sie als
Ergebnis führte — bis der Urheber selbst zurückzog.

Und der häufigste Grund für eine falsche Zahl ist immer derselbe:

**Eine Mustersuche misst, was das Muster kennt — und schweigt über den Rest,
ohne es zu sagen.** Dreimal an einem Morgen, in beide Richtungen:

| Suche | Fehler | Folge |
|---|---|---|
| `grep -o "le plaque"` | ohne Wortgrenze | zählte `seule plaque` mit — Befund war Rauschen |
| `re.search(r"\ble plaque\b")` | ein Muster, ein Fall | fand `un même plaque` nicht — „null Fehler" war blind |
| `"pytest" in CommandLine` | zu weit | zählte wartende `gate_lock`-Hüllen als laufende Tests |

Wer eine Zahl weitergibt, gibt deshalb das **Muster** mit, nicht nur das
Ergebnis. Und wer eine bekommt, prüft sie an einem Fall, von dem er weiß, wie
er ausgehen muss — bevor er auf ihr aufbaut.

### Wie viele Läufe trägt eine Aussage?

„Zweimal fahren" ist keine Zahl, sondern eine Faustregel — und wie viele Läufe
eine Aussage wirklich braucht, hängt daran, **wie oft die Sache ohne jede
Änderung schon schiefgeht**. Diese Basisraten sind am 22./23.08.2026 gemessen
worden, alle unter dem Schloss:

| Datei / Lage | ohne Änderung | Bemerkung |
|---|---|---|
| `test_pose_session.py`, ruhig | **1/10** | die Rate, gegen die ein Fix sich beweisen muss |
| `test_pose_session.py` nach dem Ring-Umbau | **6/10** | eine Änderung, die die Rate hob |
| `test_ui.py`, ruhig | **0/3** | |
| `test_ui.py` unter Fremdlast | **5/5** | *immer* — hier misst kein Lauf mehr etwas |

Daraus folgen drei Dinge, und das dritte kostet am meisten Zeit, wenn man es
vergisst:

* **Bei 1/10 ist „0 von 10" kein Beleg, sondern kein Widerspruch.** Wer nach
  zehn grünen Läufen „behoben" meldet, meldet eine Wahrscheinlichkeit von
  ungefähr einem Drittel als Gewissheit. Sagen, was die Zahl trägt, ist Teil
  des Ergebnisses.
* **Bei 5/5 ist gar nichts messbar.** Eine Änderung kann die Rate nicht mehr
  erhöhen, also entlastet ein „gleich schlecht" sie nicht. Solche Läufe zählen
  nicht als Messung, auch wenn sie Zahlen liefern.
* **Die Messlatte gehört vor die Messung.** Am 23.08. lautete sie „0 oder 1 von
  5 wirkt, 2 oder mehr nicht", festgelegt bevor irgendjemand ein Ergebnis
  kannte. Es wurden fünf, und die Entscheidung war damit schon getroffen. Wer
  die Grenze hinterher zieht, findet immer eine, die zum Ergebnis passt.

**Und ein Prozess, den keiner von uns startet, läuft immer mit:** ComfyUI liegt
mit rund einem Gigabyte und wachsender Rechenzeit im Hintergrund. Wer die Last
der Maschine beurteilt, sollte ihn kennen, sonst rechnet er ihn jemandem zu.

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
## Wer mit privatem Index committet, zieht den Haupt-Index nach

Im geteilten Arbeitsbaum committet jede Sitzung über `GIT_INDEX_FILE` und
`git commit -o -- <pfade>`, damit sie keine fremde Arbeit mitnimmt. Der
gemeinsame Index bleibt dabei stehen — **und niemand merkt es, weil niemand ihn
benutzt.** Am 22.08.2026 trug er einen Stand von vor den Commits des Abends:
27 Dateien, 87 Einfügungen, **1684 Löschungen**. Ein einziges `git commit` ohne
`-o` hätte daraus einen Commit gemacht, der die Arbeit von vier Sitzungen
löscht, und der `post-commit`-Hook hätte ihn sofort gepusht. Zweimal an einem
Abend aufgetreten.

**Und er wächst weiter, gemessen an drei Zeitpunkten:**

| Wann | Löschungen im Index |
|---|---|
| 22.08.2026 abends | 1684 |
| 23.08.2026 früh | 1424 |
| 23.08.2026 abends | **1824** |

Die mittlere Zahl ist die verräterische: Sie war kleiner, weil kurz zuvor
jemand aufgeräumt hatte. **Aufräumen hält nicht** — solange alle privat
committen, altert er ab dem nächsten Commit wieder, und zwar in die gefährliche
Richtung. Also gehört das Nachziehen zum Commit und nicht zur Fehlersuche, als
letzter Schritt jedes privaten Commits:

```
git reset            # ohne --hard: nur der Index, keine Datei
```

**Und der private Index muss auf `HEAD` stehen, nicht auf einem gemerkten
Stand.** Am 23.08.2026 schrieb ein Commit sechs fremde Dateien zurück — einen
doc-Satz und fünf Sprachkataloge, die eine andere Sitzung zwanzig Minuten
vorher committet hatte. Das Skript sah so aus:

```
STAND=$(git rev-parse HEAD)     # am Anfang gelesen
… Minuten Arbeit …
git read-tree "$STAND"          # hier war HEAD längst weiter
git update-index --cacheinfo …
git commit
```

`git commit` nimmt den **Index** als Baum und **HEAD** als Elternteil. Steht der
Index auf einem älteren Stand, ist der Commit inhaltlich ein Revert von allem,
was dazwischen kam — und der `post-commit`-Hook pusht ihn sofort. Also
`git read-tree HEAD` **unmittelbar vor** dem Commit, nicht am Anfang des
Skripts.

**Die Kontrolle danach gehört gegen `HEAD`, und das ist der eigentliche Fund:**

```
git diff --cached HEAD --stat        # richtig
git diff --cached "$STAND" --stat    # bestätigt die eigene Annahme
```

Die Kontrolle *war* eingebaut, und sie meldete brav „1 file changed“. Sie lief
gegen denselben gemerkten Stand, auf dem schon der Index stand — sie konnte den
Fehler nicht sehen, weil sie ihn teilte. **Eine Prüfung gegen die eigene Annahme
bestätigt sie, statt sie zu prüfen**; dieselbe Denkfigur wie ein Gegenbeispiel,
das dieselbe Bedingung trägt wie der Fall (siehe `oberflaeche.md`, „Was nur das
Bild zeigt“).

Gefunden hat es kein Test, sondern eine Sitzung, die vor dem Paketbau von Hand
kontrollierte. Kein Test hätte es sehen können: Der Code war lauffähig, die
Suite grün — es fehlte nur ein Satz, den fünf Sprachkataloge versprechen.

Es kostet Millisekunden, fasst keine Datei an, und der einzige Verlust ist ein
Staging — das in diesem Verfahren ohnehin niemand benutzt, weil `git commit -o`
an ihm vorbeigeht.

**Die zweite Spalte von `git status --short` lügt mit.** Das ist die Form, in
der einem der veraltete Index zuerst begegnet, und sie führt in die falsche
Richtung: Wer direkt nach einem privaten Commit `MM` an seinen eigenen Dateien
sieht, liest „fremde Arbeit liegt darin" — dabei ist die zweite Spalte der
Vergleich gegen den Index, und der ist alt. Am 23.08.2026 stand `MM` an
Dateien, die gerade committet worden waren; `git diff HEAD --numstat` zeigte
**keine einzige geänderte Zeile**. Die Frage, die trägt, ist immer die gegen
HEAD.

Und die Auskunft daneben: **`git diff` vergleicht gegen den Index, nicht gegen
HEAD.** In einem geteilten Baum stehen darin die Zwischenstände der anderen —
ein Katalog-Diff zeigte fünf fremde Zeilen, die längst committet waren, und für
eine Datei, die der veraltete Index gar nicht kannte, meldete `git diff HEAD`
sogar eine Löschung, obwohl die Datei unverändert dalag. Die Frage, die man
stellen will, ist `git diff HEAD`; die Frage, die `git diff` beantwortet, ist
eine andere.

## Was habe ich gerade gemessen?

Am 22.08.2026 haben vier Sitzungen an einem Abend **sieben** Messfehler
gemacht, und alle sieben hatten dieselbe Form:

| Werkzeug | maß | gemeint war |
|---|---|---|
| Pipe um `pytest` | den Rückgabewert von `tail` | den von pytest |
| Hintergrundlauf | den Status der Hülle | den des Programms darin |
| Prozessbaum | die direkten Kinder | die ganze Kette |
| `_alive()` | ob `OpenProcess` ein Handle gibt | ob der Prozess läuft |
| der Wächter | irgendeinen `pytest` | den Lauf **dieses** Halters |
| sein Selbsttest | `os.getpid()` | ob der Lauf sichtbar ist |
| `git diff` | den Index | HEAD |
| ein Sprachprüfstand | sechsmal denselben deutschen Dialog | sechs Sprachen |

Die vorletzte Zeile ist die, die am vollständigsten aussieht: Der Lauf schrieb sechs Dateien und gab sechs Zeilen aus. `set_language` setzt eine Variable, `install_catalog` lädt den Katalog — eine Sprachprüfung, die nur die erste ruft, misst sechsmal Deutsch. Die Gegenprobe steht in `oberflaeche.md` unter „Was nur das Bild zeigt“ und kostet nichts: **Sind zwei Bilder gleich groß, zeigen sie dasselbe.**

Keiner war Nachlässigkeit. Jeder maß etwas, das echt, greifbar und benachbart
war — **man misst, was leicht zu greifen ist, und nicht, was gemeint war.** Das
ist die Normalform des Messfehlers, nicht die Ausnahme.

Die Gegenfrage ist dieselbe, die Bauplan §35 an einen Test stellt, nur an ein
Werkzeug gerichtet, und sie kostet zehn Sekunden: **Was habe ich gerade
gemessen, und ist das dasselbe wie das, was ich wissen wollte?**

### Und in welche Richtung habe ich mich geirrt?

Am 24.08.2026 kamen drei weitere dazu, aus drei Sitzungen, und sie zeigen die
Asymmetrie, die in der Tabelle oben noch nicht steht:

| Werkzeug | maß | gemeint war |
|---|---|---|
| §-Prüfer über den Bauplan | 6 Abschnitte (Muster erwartete ein `§`) | 113 |
| Sphinx-Prüfer | Namen ohne die Lazy-Export-Tabelle | alle erreichbaren |
| `grep -c "^FAILED"` | die Zusammenfassung, die noch nicht geschrieben war | die roten Tests |

**Zu viel finden kostet Prüfzeit; zu wenig finden erzeugt die Gewissheit, es
sei nichts da.** Das ist der teurere Fehler, und er sieht wie ein Erfolg aus:
Ein Prüfer, der sechs von 113 Abschnitten liest, meldet „alles in Ordnung" —
und ein Test gegen eine leere Menge ist **immer** grün.

Daraus folgt eine Zusicherung, die in jedes selbstgebaute Prüfwerkzeug gehört:
**Zähle zuerst, wie viel du überhaupt gefunden hast, und lass den Lauf
scheitern, wenn es zu wenig ist.** `tests/test_plan_references.py` macht es so
(`assert len(sections) > 100`), `tests/test_translations.py` ebenfalls
(`assert gb_texte`), und `suite-getrennt.sh` seit dem 24.08. auch — die Zeile
„Sammelgruppe: 3554 passed" ist genau diese Zusicherung, nur für das Tor.

Die zweite Hälfte kostet noch weniger: **Gib dem Werkzeug einen Fall, dessen
Ausgang du kennst.** Ein Prüfer für Doppelungen, der den bekannten Fall nicht
findet, ist kaputt; einer, der ihn findet, hat seine erste Zusicherung. Der
Duplikat-Sucher vom 24.08. fand `size_for_thread` — den Fall, den eine andere
Sitzung eine Stunde vorher gemeldet hatte — und war damit brauchbar, bevor er
etwas Neues meldete.

## Prüft dieser Test eine Zusage — oder den Ist-Zustand?

Ein Test kann einen Fehler **festschreiben**. Er ist dann grün, solange der
Fehler da ist, und wird rot, sobald jemand ihn behebt.

Am 23.08.2026 stand in `tests/test_operation_ui.py`:

```python
assert values == {"at_feature": "hole_1"}
```

Das ist die vollständige Vorbelegung eines Dialogs — und sie sicherte damit zu,
dass die **Größe nicht mitkommt.** Genau das war der Fehler, den dieselbe
Sitzung am selben Tag gemeldet hatte: Eine 5,19-mm-Bohrung bekam M3
vorgeschlagen, M3 bohrt 4,00 mm, der Schnitt trägt nichts ab. Als die Größe
endlich mitkam, wurde der Test rot — **er hat die Verbesserung blockiert, statt
sie zu tragen.**

Die Gegenprobe dagegen ist nicht die übliche („einmal ohne den Fix fahren“),
sondern eine andere Frage:

| Form | prüft |
|---|---|
| `assert werte == {...}` | den **Ist-Zustand**: genau das und nichts sonst |
| `assert werte["a"] == x` | die **Zusage**: das hier muss stimmen |

Beides ist manchmal richtig — eine Obergrenze *soll* die vollständige Menge
prüfen. Aber wer eine Vorbelegung, eine Ausgabe oder eine Menge von Feldern
festnagelt, sollte wissen, dass er damit auch zusichert, **was nicht darin
steht**. Die Frage vor dem `==`: Ist die Abwesenheit dieses Schlüssels wirklich
Teil der Zusage?

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
* **Ein Wert herausgezogen, die Nachbarn geprüft aussehen lassen.** Ein Aufruf
  mit fünf Argumenten, eines davon in eine eigene Methode gehoben, damit ein
  Test es fragen kann — und die anderen vier sehen danach mitgeprüft aus. Am
  25.08.2026 hat das einen stillen Datenfehler gedeckt: `_save_as_part` reichte
  Merkmale (geprüft, eigene Methode, eigener Test) und `op_ids` (ungeprüft, in
  der Zeile) an denselben Aufruf. Die IDs waren `enumerate`-Plätze, `capture`
  filtert nach `Operation.id`, und die zählt ab eins — **der letzte Schritt fiel
  aus jedem Rezept**, ohne Fehler und ohne Meldung. Acht grüne Tests standen
  daneben, einer davon zwei Zeilen über der falschen. Wer ein Argument
  herauszieht, um es prüfbar zu machen, zählt die übrigen desselben Aufrufs —
  die Extraktion prüft eines und tarnt den Rest.

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

## Ein Verbotstest über eine leere Menge ist immer grün

Die häufigste Form eines Tests in diesem Projekt ist der Verbotstest: Er filtert
aus einer Menge die Verstöße heraus und sichert zu, dass keiner übrig bleibt.

```python
offenders = [f"{p.name}" for p in sorted(UI.glob("*.py")) if "setDefault(True)" in p.read_text()]
assert not offenders, f"noch von Hand: {offenders}"
```

**Ist die Grundmenge leer, findet der Filter nichts, und der Test besteht** —
nicht weil alles in Ordnung ist, sondern weil nichts geprüft wurde. Ein
umbenannter Ordner, ein nicht geladenes Register, ein Widget ohne Größe: Der
Test bleibt grün und niemand erfährt, dass er aufgehört hat zu prüfen.

### Wann die Zusicherung nötig ist, und wann sie Zierat ist

Am 23.08.2026 hat ein Registerpunkt vorgeschlagen, überall eine Zeile
danebenzuschreiben. Angewandt auf 29 Kandidaten waren **14 echte Lücken** und
15 nicht. Der Schnitt läuft entlang einer Frage:

**Wird die Menge *erhoben* oder steht sie *da*?**

| Herkunft | Beispiel | Zusicherung |
|---|---|---|
| Dateisystem | `UI.glob("*.py")`, `rglob` | **ja** — ein umbenannter Ordner ist still |
| Ladevorgang | `rules.load()`, `manual.pages()`, `REGISTRY.all()` | **ja** — fehlende Daten sind still |
| Gebaute Oberfläche | `findChildren(...)`, `panel._buttons.values()` | **ja** — ein Aufbaufehler ist still |
| Rechenergebnis | `result.layers`, `island_layers(result)` | **ja** |
| Konstante im Modul | `REQUIRED_LINKS`, `FIELDS` | nein — sie leert sich nicht von selbst |
| Literal im Test | `{"Versatz": …, "Maß": …}` | nein |
| Vereinigung mit Festwert | `{"de"} \| set(available_languages())` | nein — nie leer |

Fünfzehn überflüssige Zeilen sind nicht harmlos: Beim nächsten Lesen
unterscheidet sie niemand mehr von den vierzehn, die tragen.

### Bei `parametrize` gehört sie in die Funktion, nicht in den Test

Das ist der Fall, der am meisten kostet, wenn man ihn übersieht:

```python
@pytest.mark.parametrize("path", source_files(), ids=lambda p: p.name)
def test_identifiers_are_english(path: Path) -> None: ...
```

Ist `source_files()` leer, wird **kein Test rot**. pytest sammelt null Tests,
meldet `no tests ran` und gibt **Exit 5** — derselbe Exit, den `suite-getrennt.sh`
seit einer Datei ohne passende Marker kennt, nur hier als *stiller Erfolg*. Eine
Zusicherung im Testkörper fängt das nicht: Sie liefe nie.

Sie gehört in die Funktion, die die Parameterliste liefert.

**Und eine je Parameter ist falsch.** Der erste Anlauf setzte
`assert list(identifiers_of(tree))` in den Test — **elf Fehlschläge**, weil eine
leere `__init__.py` legitim keine Bezeichner hat. Was für die Gesamtmenge gilt,
gilt nicht für jedes Element.

### Obergrenzen sind der gefährlichste Fall

`test_interface_limits.py` prüft lauter Obergrenzen: höchstens neun Menüs, zwölf
Zeilen je Menü, acht Umschalter. **Ein leeres Register unterschreitet jede
davon.** Ohne `load_operations()` hat es null statt 86 Operationen, und die
ganze Datei wird grün, ohne eine einzige Grenze geprüft zu haben.

Wo eine Datei viele Grenzen über derselben Menge prüft, steht die Zusicherung
einmal als eigener Test — ein roter Test genügt, damit das Tor es merkt, und der
Grund ist nur an einer Stelle zu pflegen.

### Und die Gegenprobe gilt auch hier

Grundmenge leeren, Test fahren, muss rot sein, zurückstellen. Sechs von sechs
mutierbaren Fällen haben gegriffen — aber das ist kein Grund, sie zu lassen: Die
Probe hat an anderer Stelle schon fünf überzeugend aussehende Tests verworfen.
Wer sie automatisiert, packt die Rückstellung in ein `finally`; ein Abbruch
zwischen Mutation und Rückstellung lässt sonst eine verfälschte Datei liegen —
am 23.08.2026 einmal passiert, aufgefallen nur, weil danach ein `grep` lief.

### Was für die Gesamtmenge gilt, gilt nicht für jedes Element

Der Abschnitt oben sagt, eine erhobene Grundmenge brauche eine Zusicherung. Bei
einem **parametrisierten** Test ist damit die Parameterliste gemeint und nicht
der Inhalt je Parameter — und der Unterschied ist keine Feinheit:

* `test_language_rules.py` prüft je Quelldatei die Bezeichner. Eine Zusicherung
  „diese Datei hat Bezeichner" machte **elf Tests rot**: Eine leere
  `__init__.py` hat legitim keine.
* `test_website.py` prüft je Seite die Sprungmarken. Nur **12 von 30** Seiten
  haben welche, und **6 von 30** einen FAQ-Block. Eine Zusicherung je Seite wäre
  auf zwei Dritteln nicht zu streng, sondern **inhaltlich verkehrt**.

Die Lösung im zweiten Fall ist die allgemeine: Die Zusicherung steht daneben und
**summiert über alle Parameter** — „mindestens eine Seite hat Sprungmarken" ist
wahr und prüfbar, „jede Seite hat welche" ist falsch.

### Ein fertiger Job in einem laufenden Lauf gibt sein Protokoll heraus

`gh run view --log-failed` antwortet „logs will be available when it is
complete", solange der **Lauf** läuft — auch wenn der Job, den man lesen will,
längst fertig ist. Ein Lauf mit vier Jobs ist erst zu Ende, wenn der letzte
durch ist; bis dahin schweigt der Befehl über alle vier.

Die API antwortet je Job:

```
gh api repos/<eigner>/<repo>/actions/jobs/<job-id>/logs
```

Ohne führenden Schrägstrich vor `repos` — Git Bash schreibt einen mit `/`
beginnenden Pfad sonst in einen Dateisystempfad um.

**Die Grenze davon ist gemessen worden, und sie ist enger als sie zuerst
aussah.** Der Satz „die API gibt auch laufende Jobs heraus" stimmt nicht:

    Job in_progress   Exit 1   228 Bytes   BlobNotFound, HTTP 404
    Job completed     Exit 0   57 480 Bytes

Was sie hergibt, ist das Protokoll eines **fertigen** Jobs, während der **Lauf**
noch läuft — und das genügt, weil ein Job, der rot geworden ist, fertig ist. Am
23.08.2026 hat das eine Diagnose von „nach dem Lauf" auf „in einer Minute"
verkürzt.

**Und die Falle daneben, die dabei prompt zugeschnappt hat:** Der erste Versuch
lief als `gh api … | tail -6` und meldete **Exit 0** über einer 404-Antwort —
der Rückgabewert von `tail`. Dieselbe Pipe-Falle, die weiter oben in dieser
Datei steht, an einem Werkzeug, das kein Testlauf ist. Sie gilt für jeden
Befehl, dessen Rückgabewert man liest, nicht nur für `pytest`.

Der Handgriff davor hat die Suche zusätzlich halbiert: Die neueste `ruff` in
einer **eigenen** Umgebung gegen das Projekt zu fahren (nicht in der `.venv` —
vor einem Paketbau wird dort nichts installiert) schloss die wahrscheinlichste
Ursache aus, bevor das Protokoll überhaupt da war.

Am 23.08.2026 hat das eine Diagnose von „nach dem Lauf" auf „in einer Minute"
verkürzt. Und der Handgriff davor hat sie halbiert: Die neueste `ruff` in einer
**eigenen** Umgebung gegen das Projekt zu fahren (nicht in der `.venv` — vor
einem Paketbau wird dort nichts installiert) schloss die wahrscheinlichste
Ursache aus, bevor das Protokoll da war.

### Eine Automatik, die in Wahrheit Handarbeit ist, ist gefährlicher als keine

`CLAUDE.md` sagt zu: „Jeder Commit geht sofort hinaus, `.githooks/post-commit`
pusht ihn." Am 23.08.2026 zeigte sich, dass es diesen Hook im Arbeitsbaum **nicht
gibt**:

    .git/hooks/post-commit     existiert nicht
    core.hooksPath             auf keiner Ebene gesetzt

Ohne `core.hooksPath` sieht Git `.githooks/` nie an. Gemerkt hat es niemand,
**weil das Ergebnis stimmte** — es hat immer jemand von Hand gepusht. Aufgefallen
ist es erst, als zwei Commits vor einem CI-Start liegenblieben und die CI fast
den Stand *vor* zwei Fehlerbehebungen gebaut hätte.

Daraus folgen zwei Dinge, und das zweite ist die eigentliche Regel:

* Eingeschaltet wird sie mit `git config core.hooksPath .githooks` — **nicht**
  mitten in einem Release, weil ein Hook, der ab sofort bei jedem Commit pusht,
  während jemand Pakete baut, mehr kostet als er rettet.
* **Woran merkt man, dass sie läuft?** Eine Automatik, deren Ausbleiben
  niemandem auffällt, ist keine. Also gehört zu ihr eine Zusicherung:
  `core.hooksPath` zeigt auf `.githooks`, und jede Datei darin ist ausführbar.

### Die Isolation deckt Qt, Verzeichnisse und OpenSCAD ab — das Netz nicht

`conftest.py` hält die Maschine aus dem Ergebnis heraus: Offscreen-Qt,
Nutzerverzeichnisse in einem Temp-Ordner, kein installiertes OpenSCAD. Am
23.08.2026 stand in einem Absturzstapel von `test_ui.py`:

    app/core/backends/llm.py:501    available
    app/ui/first_run.py:445         _chat_text
    app/ui/leash.py:173             run              (Arbeitsthread)
    ... socket.py:853               create_connection

**Ein Test öffnet eine echte Netzwerkverbindung.** `llm.available()` fragt über
`socket.create_connection`, ob ein Backend erreichbar ist. Ein Rechner mit
laufendem Ollama misst damit etwas anderes als einer ohne, und die CI hat gar
keins — dieselbe Klasse wie das installierte OpenSCAD, nur eine Ebene weiter.

Ob es die Ursache des Absturzes war, ist offen. Ein Isolationsloch ist es
unabhängig davon.

### Ein Testdatensatz, in dem alles gleich heißt, prüft weniger als er aussieht

Zweimal an einem Tag, beide Male an derselben Stelle und beide Male von der
Gegenprobe gefangen:

> **Zwei Felder mit gleichem Wert machen jeden Test grün, der nur eines liest.**

* `website/version.json` nennt jedes Paket zweimal — als `"file"` und in der
  `"url"`. `updates.py` liest **beide**: das eine, um zu laden, das andere, um
  die geladene Datei zu benennen. Der erste Test prüfte nur `url`; die
  Mutation traf `file`, und der Test blieb grün.
* Dasselbe im Werkzeug daneben: `promised_files()` sammelt die Namen aus beiden
  Feldern, und der Test dazu fütterte sie mit **demselben** Wert. Die
  Gegenprobe „nur `url` auswerten" blieb grün, obwohl die Auswertung damit die
  Hälfte verlor.

Die Lösung ist nicht, die Gegenprobe zu verschärfen, sondern **den Datensatz zu
entzerren**: `{"url": "…f=geladen.exe", "file": "benannt.exe"}`. Ein Test, der
zwei Wege unterscheiden soll, braucht zwei unterscheidbare Werte — sonst prüft
er, dass zwei Kopien derselben Zahl übereinstimmen.

Verwandt mit „an der Aussage vorbei" oben (`str(op_id) in tooltip` war grün,
weil „2" auch in „2,40 mm" steht): Beide Male stimmt der Vergleich zufällig.

### Lokal gegen lokal sagt nichts darüber, was oben liegt

Am 23.08.2026 wurden beim Veröffentlichen von 0.1.3 die alten Pakete gelöscht,
**bevor** die Seiten und `version.json` hochgeladen waren. Mehrere Minuten lang
zeigte solidon3d.de in sechs Sprachen auf vier Dateien, die es nicht mehr gab,
und die Update-Prüfung bot jedem Kunden eine Fassung an, deren Datei 404 gab.

**Keine Prüfung hat es gemerkt, und alle waren grün** — 199 Tests, vier
hochgeladene Pakete mit verglichenen Prüfsummen, eine `version.json`, die zur
Anwendung passte. Lokal war durchgehend alles stimmig. Falsch war nur, was
**oben** lag, und danach hatte niemand gefragt.

Daraus folgen zwei Dinge:

* **Die Reihenfolge gehört in ein Werkzeug, nicht in ein Gedächtnis.**
  `upload_website.py --alte-pakete` liest die `version.json` **vom Server** und
  verweigert, solange dort die alte Fassung steht. Die Bedingung kann den
  Fehler nicht wiederholen, weil sie sich auf den Zustand stützt, um den es
  geht.
* **Nach jedem Hochladen wird gegen den Server gemessen**, nicht gegen die
  Platte: Version, Paketnamen, Größen, und ob die Seiten die neuen Namen
  tragen. Das ist Handarbeit und bleibt es — ein Test im Tor darf nicht vom
  Netz abhängen. Aber es ist die einzige Messung, die den Fehler oben findet.

Die allgemeine Form steht schon weiter oben („Was habe ich gerade gemessen?"),
hier ist die Antwort besonders unauffällig: Man hat *etwas Echtes* gemessen,
nur eben nicht das, was der Kunde sieht.

## Wann man aufhört zu zählen und anfängt zu lesen

Die Basisraten oben sagen, **wie viele** Läufe eine Aussage trägt. Sie sagen
nicht, wann Läufe überhaupt das richtige Werkzeug sind.

**Eine Rate sagt, dass etwas anders ist. Sie sagt nie, was.**

Am 23.08.2026 stand eine Sitzung vor „2 von 4 sauber" — nach der eigenen,
vorher festgelegten Latte also: keine Entscheidung, mehr Läufe. Statt zehn
weitere zu fahren, hat sie zwei Minuten in die fremde Fixture gesehen und die
Zeile gefunden:

```python
def release(self, timeout_ms: int = 2000) -> None:
    self.wait_for_look(timeout_ms)  # der fachliche Standardwert ist 30_000
```

Eine Erhebung, für die eine halbe Minute vorgesehen ist, bekam zwei Sekunden.
**Das erklärt auch die Zahl:** Der Thread braucht meistens weniger als zwei
Sekunden, manchmal nicht — daher zwei von vier und nicht null von vier. Zehn
Läufe hätten dieselbe Zahl schärfer gegeben und keine einzige Zeile genannt.

Die Faustregel dazu:

> **Zeigt der Verdacht auf eine benennbare Stelle, ist Lesen billiger als
> Zählen. Zeigt er nirgendwohin, hilft nur die Rate.**

## Ein Signal, das jedes Mal kommt, lässt sich halbieren

Der Abbau-Absturz galt als Eigenschaft ganzer Fensterdateien: 86 Sekunden für
ein Ja/Nein, drei Ausgänge bei drei Läufen, und deshalb hat ihn niemand
eingegrenzt. Er ist aber **deterministisch** — und damit war die Suche billig:

    1, 5, 10, 20, 30, 40, 50 Tests    sauber
    58 Tests                           Riss
    51 Tests                           sauber
    52 Tests                           Riss        <- die Grenze

Der 52. Test riss **allein**, ohne Vorgeschichte, dreimal von dreimal, in einer
Drittelsekunde. Dasselbe Verfahren fand in `test_chat_ui.py` zwei weitere.

Drei Dinge, die das Verfahren tragen:

* **Erst prüfen, ob das Signal deterministisch ist.** 24 von 26 Läufen rissen —
  damit trägt *ein* Lauf je Schritt. Bei einem sporadischen Fehler (etwa dem
  Hänger, 1 von 3) hätte dieselbe Suche geraten.
* **Die Vorgeschichte gehört dazu.** Gemessen wird „alles bis N" gegen „alles
  bis N−1", nicht „der Test allein" — sonst fehlt genau das, was ihn zum
  Reißen bringt. Dass er hier auch allein riss, war ein Ergebnis und keine
  Annahme.
* **Testnamen kommen aus `--collect-only -q`, und die Zeilen tragen ein CR.**
  Ohne `sed 's/\r$//'` hängt es am Ende jeder Node-ID, pytest findet sie nicht
  und antwortet mit Exit 4 — sechs Läufe, alle wertlos, in zwanzig Sekunden.

## Ein Muster, das man abfragen muss, ist ein fehlender Vertrag

Die Aufräum-Fixture suchte nach `release` und `wait_for_workers`. Die
Absturzsuche fand nacheinander `wait_for_survey` und `wait_for_look`; eine
Zählung ergab **fünf Namen für dieselbe Sache**, verteilt auf neun Klassen, und
drei weitere Klassen mit Arbeiter und ganz ohne Wartemethode.

Die Fixture fragt seitdem nach dem Muster (`release`, dann alles, was
`wait_for_` heißt) — das ist die richtige **Notlösung** und war nicht die
Lösung. Die war ein einheitliches `release()` auf allen elf Klassen, dazu eine
Prüfung, die per `ast` liest, wer eine `WorkerLeash` anlegt, und von jedem
dasselbe Wort verlangt. Ein sechster Name kann seitdem nicht mehr entstehen.

**Und der Umbau hat sofort einen Fehler freigelegt**, den fünf Namen verdeckt
hatten: Eine der Klassen reichte ihre 2000-ms-Frist an eine Methode durch,
deren fachlicher Standardwert 30 000 ist. Der Fehler war vorher da — er hatte
nur keine Stelle, an der er auffallen konnte.

## Eine Zusicherung in beide Richtungen kann den Fehler festhalten

`test_registry.py` prüfte, dass jedes Merkmalsfeld sich als solches
deklariert — und zwar so:

```python
named    = {… if entry.name == "at_feature"}
declared = {… if entry.kind == "feature"}
assert named == declared
```

Der Zweck war richtig und stand im Docstring: §21.3 sucht Merkmalsverweise
nach der **Art**, und achtzehn Operationen liefen an der Prüfung vorbei, bevor
sie sich deklarierten. Getestet wurde davon aber nur die eine Richtung; die
andere sagt etwas ganz anderes, nämlich **„kein Merkmalsfeld darf anders
heißen"**.

Genau daran ist die Behebung eines echten Fehlers hängengeblieben. *An Merkmal
ausrichten* nennt ihr Feld `feature`, war deshalb für §21.3 unsichtbar, und
`kind="feature"` zu setzen machte diesen Test rot. **Ein Test, der einen Fehler
am Behobenwerden hindert, prüft die Gewohnheit und nicht die Zusage.**

Die Frage, die das vorher gefunden hätte, ist nicht „ist die Zusicherung
scharf genug", sondern:

> Was genau darf nicht passieren — und sagt meine Zusicherung das, oder sagt
> sie mehr?

`a == b` über zwei erhobene Mengen ist fast nie die Zusage. Es sind zwei
Zusagen in einer Zeile, und meist ist nur eine gewollt.

**Beim Lockern nicht die Deckung wegnehmen.** Die gestrichene Richtung hatte
eine Aufgabe — sie fing jemanden, der `kind="feature"` an ein Feld setzt, das
gar kein Merkmal des Eingangsobjekts benennt. An ihre Stelle gehört eine
Zusicherung über die *Sache*: Ein Merkmalsverweis wird gegen `inputs[0]`
aufgelöst, also zeigt er ins Leere, wenn die Operation nichts verbraucht. Am
Bestand gemessen (22 Operationen, keine ohne Eingang), beide Richtungen einmal
mutiert und rot gesehen.

## Ein Messwerkzeug, das den Absturz nicht überlebt, misst nichts

Die Frage war, an welcher Zeile der Speicherbereiniger feuert, wenn
`test_ui.py` reißt. Der erste Entwurf hängte sich an `gc.callbacks`, sammelte
die Treffer in eine Liste und gab sie in `pytest_sessionfinish` aus.

**Er hat null Zeilen geliefert** — der Lauf, um den es geht, stürzt ab, und ein
abgestürzter Prozess erreicht kein Sitzungsende. Ein Werkzeug, das genau den
Fall nicht überlebt, für den es gebaut ist, gibt nur dann eine Zahl aus, wenn
sie niemanden interessiert.

Die zweite Fassung schreibt zeilenweise in eine Datei
(`open(pfad, "w", buffering=1)`), und damit stand die Antwort nach **einem**
Lauf von neunzig Sekunden:

    58 Sammelläufe insgesamt, 2 davon mit dem Hauptthread in wait_for_idle
    #53  Auslöser haupt      Zeile 1522
    #58  Auslöser ARBEITER   Zeile 1515   ARBEITER-LÄUFT   <- und hier starb er

Der Umweg, der beinahe gegangen worden wäre: **sechzehn Läufe**, acht je Seite,
abwechselnd mit und ohne einen vermuteten Fix — eine halbe Stunde für eine
Wahrscheinlichkeitsaussage, wo eine direkte Messung die Ursache nennt. Bei
einer Rissrate von 80 % (fünf Sitzungen auf der Maschine) hätte die Statistik
ohnehin nichts getrennt.

**Die Frage davor lohnt sich also:** Will ich wissen, *ob* etwas hilft, oder
*warum* es passiert? Das zweite ist oft billiger zu messen und immer mehr wert.

## Nach einer Änderung an `app/` oder `tools/`: zwei Läufe von je drei Sekunden

Viermal an einem Tag ist ein deutscher Bezeichner ins Tor gekommen, dreimal in
Code, der gerade repariert wurde, einmal in eigenem. Die Ursache war jedes Mal
dieselbe und jedes Mal vernünftig: Gefahren wurden die Tests des *Gebiets*, in
dem die Änderung lag — nicht die, die *jede* Datei prüfen.

```
.venv\Scripts\python.exe -m pytest tests/test_language_rules.py -q   # ~3 s, 745 Fälle
.venv\Scripts\python.exe -m ruff check .                             # ~2 s
```

**`ruff check .` ohne Pfadangabe**, und das ist der Teil, der zweimal fehlte:
Ein eingegrenzter Prüflauf über `app/ui/` spart Sekunden und lässt eine
Testdatei durch, die dann einen fremden Torlauf kostet. Beides ist Code, und
das Tor prüft beides.

## Eine Fremdmeldung ist ein Zeitpunkt, keine Ursache

Vier Meldungen an einem Tag, alle vier von fremden Programmen, alle vier
irreführend:

| Meldung | behauptet | war |
|---|---|---|
| `Exit 127` | „command not found" | Shell-Konvention über vier verschiedenen Windows-Codes |
| `0xc0000374` | ein bestimmter Fehler | *jede* Heap-Beschädigung, gleich welcher Herkunft |
| `Background writer channel closed` | ein Schreibkanal | die Platte war voll |
| `MSVC 14.0 or greater is required` | Compiler fehlt | Compiler da, `vswhere` fand Visual Studio 18 nicht |

> **Eine Fremdmeldung nennt, was das fremde Programm zuletzt *gesehen* hat —
> nicht, warum. Sie ist ein Zeitpunkt, keine Ursache.**

Wer sie als Diagnose liest, sucht am falschen Ort — dreimal von vier hat nicht
der Text zur Ursache geführt, sondern eine **Wiederholung**: dreimal derselbe
Abbruch an derselben Stelle (Platte), zwei Läufe mit verschiedenen Codes hinter
derselben 127, eine Notiz von vor zwei Wochen (MSVC). Der Text war jedes Mal
die Sackgasse.

Und die eigene Fehlermeldung ist deshalb anders zu schreiben: Regel 17 verlangt
einen Handlungsvorschlag, und der Grund dafür steht hier — **wo wir mehr wissen
als das fremde Programm, gehört das dazu.** „Der Download brach ab" ist eine
Fremdmeldung; „auf `C:` sind 0 Byte frei, das Paket braucht 7,5 GB" ist eine
Ursache.

## Ein Prüfwerkzeug ist auch nur Code, und es war viermal der Fehler

An **einem** Tag, und alle vier waren **grün**:

| Werkzeug | Fehler |
|---|---|
| der Wächter | meldete beim Fehlalarm und schwieg beim echten Hänger |
| ein Auswerter | schrieb „RISS VOR DER SUMME" über eine vollständige Zusammenfassung |
| zwei Tests | prüften eine Attrappe statt der Sache |
| die Aufräumfixture | hielt selbst fest, was sie loslassen sollte |

Der gemeinsame Nenner ist nicht die Bauart, sondern das Grün: **Ein Werkzeug,
das nichts meldet, sieht aus wie ein Werkzeug, das nichts findet.**

Zwei Handgriffe dagegen, beide billig:

* **Den Zweig prüfen, den es noch nie gegeben hat.** Der Auswerter hatte drei
  Urteile und in echten Läufen nur eines davon gezeigt. Ein gefälschtes
  Protokoll hat die anderen zwei in zwei Minuten geprüft — und der erste
  Fälschungsversuch ging daneben, was nur auffiel, weil danebengeschrieben
  stand, ob der Fall überhaupt entstanden ist.
* **Eine Zahl, die konstant ist, ist ein Zeiger.** „1 von 10 überlebten" — nie
  null, nie zehn — ist kein Streuungsproblem, sondern genau eine Referenz. Wer
  bei so einer Zahl die Rate verfeinert, misst am Befund vorbei.

### Die Abfrage muss den Befehl noch ändern können

Die Regel „wer das Schloss belegt sieht, schreibt nicht" ist am 23.08.2026
zweimal erfüllt worden und hat trotzdem nichts verhindert — einmal bei 3a,
einmal bei mir. Beide Male so:

```bash
gate_lock.py status && python - <<'PY'   # der Editor hängt schon dran
```

Die Abfrage stand davor, ihre Antwort stand in derselben Ausgabe wie die
Änderung. **Erfüllt war eine Bedingung an die Reihenfolge im Text, gemeint war
eine an die Kausalität:**

> **Die Antwort muss den Schreibbefehl beeinflussen können — und das kann sie
> nur, wenn er zum Zeitpunkt der Antwort noch nicht formuliert ist.**

Eine Prüfung im selben Aufruf wie die Änderung ist keine Prüfung, sondern eine
Notiz. Praktisch heißt das: **Ein Aufruf fragt, ein zweiter schreibt** — und
zwischen beiden liest jemand das Ergebnis. Das kostet einen Tastendruck und ist
der einzige Unterschied zwischen einer Zusicherung und einer Verzierung.

Dieselbe Form hat 64s Fehler am selben Tag, nur ohne Schloss: Sie maß, ob
Katalog und Quelltext zusammenpassen, bekam „0 fehlen, 0 tot" — und derselbe
Test war im selben Baum rot. Die Messung lief **nach** dem Testlauf, und
dazwischen hatte jemand geschrieben. **In einem Baum, in dem vier Sitzungen
schreiben, misst man nicht den Baum, sondern einen Zeitpunkt** — und der steht
nicht im Ergebnis.
