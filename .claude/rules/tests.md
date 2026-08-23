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

Er altert auch nach jedem Aufräumen wieder, solange alle privat committen. Also
gehört das Nachziehen zum Commit und nicht zur Fehlersuche:

```
git reset            # ohne --hard: nur der Index, keine Datei
```

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

Keiner war Nachlässigkeit. Jeder maß etwas, das echt, greifbar und benachbart
war — **man misst, was leicht zu greifen ist, und nicht, was gemeint war.** Das
ist die Normalform des Messfehlers, nicht die Ausnahme.

Die Gegenfrage ist dieselbe, die Bauplan §35 an einen Test stellt, nur an ein
Werkzeug gerichtet, und sie kostet zehn Sekunden: **Was habe ich gerade
gemessen, und ist das dasselbe wie das, was ich wissen wollte?**

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
