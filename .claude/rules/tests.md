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
| `test_layer_direction.py` | die vier Schichten importieren nur nach unten (`app/CLAUDE.md`) — auch träge, auch für Typen |
| `test_lazy_exports.py` | die drei Listen jedes Lazy-Pakets stimmen überein, jeder Eintrag löst auf |
| `test_hard_rules.py` | was auf jeder Plattform gilt, aber nur auf einer läuft: Puffergrenzen im Quelltext, Nutzerverzeichnisse je Plattform |

Eine neue Testart bekommt eine eigene Datei; ein neues Fehlerbild wird eine
Testdatei, kein Sonderfall im Code.

## Isolation ist Teil des Tests

`tests/conftest.py` setzt `QT_QPA_PLATFORM=offscreen`, biegt die
Nutzerverzeichnisse in einen Temp-Ordner (§38) und hält die Maschine aus dem
Ergebnis heraus: ein Entwicklerrechner mit installiertem Slicer sieht sonst
etwas anderes als ein Bauserver ohne. Wer diese Fixtures umgeht, prüft nicht,
was er zu prüfen vorgibt.

Dasselbe gilt eine Ebene tiefer, bei den Paketversionen: die Umgebung wird
gegen `constraints.txt` aufgebaut, sonst installiert ein frischer Klon andere
Versionen als der letzte grüne Lauf — und die Suite wird rot, ohne dass sich
eine Zeile Code geändert hat.

`filterwarnings = ["error"]` ist gesetzt: eine Warnung bricht den Lauf. Das ist
Absicht — sie wird behoben, nicht unterdrückt.

### Isolation heißt Betriebslage, nicht Nullzustand

Eine Rücksetz-Fixture stellt her, was der **Kunde** hat — nicht ein nacktes
Nichts. `apply_theme` legt das Stylesheet über die **Anwendung**, und `app.py`
tut das beim Start; die Oberfläche existiert im Betrieb also nie ohne. Eine
Fixture, die es nach jedem Test abräumt, macht Tests verlässlich grün gegen
einen Zustand, den niemand je sieht.

**Offscreen hat gar keine Schrift.** Die Punktgröße ist negativ, und jede
angeforderte Familie — `Segoe UI`, `DejaVu Sans`, `Sans Serif` — liefert
dieselbe synthetische Metrik. Der Wächter, der hier als Beleg stand, war selbst
der Fehler: Er maß eine Kartenbreite in einer Schrift, die es nicht gibt, und
hat eine Änderung erzwungen, die niemand brauchte (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

Daraus **drei** Sätze, und der dritte ist der teuerste:

* **Wer eine Rücksetzung baut, prüft ihren Zielzustand.** Sprache auf die
  Quellsprache, Anzeigeeinheit auf Millimeter — das *ist* der
  Auslieferungszustand. Ein Thema, ein Stylesheet, ein geladenes Register
  gehören dagegen zur Betriebslage; sie wegzuräumen erzeugt eine Lage, die es
  beim Kunden nicht gibt.
* **Wer eine Breite, ein Layout oder eine Metrik misst, stellt die Betriebslage
  her** (`apply_theme` im Test), statt sie wegzuräumen. Sonst misst der Test
  etwas, das niemand je sieht.
* **Und wer sie herstellt, stellt sie ganz her.** Das Stylesheet war die eine
  Hälfte der Betriebslage; die andere ist die Schrift, und die kam aus dem
  Testlauf. Eine halb hergestellte Betriebslage ist gefährlicher als gar keine:
  Sie sieht aus wie eine Messung am Kundenzustand, trägt eine Zahl, die
  plausibel wirkt, und bringt ihre eigene Begründung mit. **Eine Größe, die von
  Schriftmetrik abhängt, ist offscreen nicht messbar** — auch nicht mit
  ausdrücklich gesetzter Familie, denn offscreen ignoriert sie. Wer so etwas
  prüfen will, fährt die echte Plattform (`WA_DontShowOnScreen` hält das
  Fenster dabei unsichtbar) oder prüft es gar nicht.

Und die allgemeine Form, weil sie über Fixtures hinausgeht: **Ein Test, der nur
in einer Lage grün ist, die es im Betrieb nicht gibt, ist keine Zusicherung,
sondern eine Tarnung.** Das gilt in beide Richtungen — auch rot in einer Lage,
die es nicht gibt, erzwingt Änderungen, die niemand braucht. Die Frage davor
ist dieselbe wie überall in dieser Datei — was habe ich gerade gemessen, und
ist das, was der Kunde hat?

**Und die Gegenrichtung, damit daraus kein Kult wird: Die Betriebslage
herzustellen trägt nur, wo die Messgröße selbst an ihr hängt.** Eine
Kartenbreite hängt an der Schrift, und die fehlt offscreen — gar nicht messen.
Eine Kürzelübersicht zeigt „Home" ohne und „Pos1" mit Qt-Katalog — hier ist der
Fix, **über dieselbe Funktion zu vergleichen, die auch anzeigt** (`_native`),
und damit neutralisiert sich die Lage auf beiden Seiten. Ein zusätzliches
`install_qt_translations` im Test war deshalb Zierat, und die Gegenprobe hat es
entlarvt: Entfernt man es, wird nichts rot. **Eine Zeile, deren Entfernen
nichts rot macht, prüft nichts** — und in vier Wochen unterscheidet sie niemand
mehr von den tragenden. Die Frage lautet also nicht „habe ich die Betriebslage
hergestellt", sondern: **Hängt das, was ich messe, an ihr?**

### Und bei einer Farbe hängt es immer an ihr — die Suite fährt ohne Stylesheet

Der Abschnitt oben liest sich als Frage an eine **Fixture**. Aber `apply_theme`
und `apply_style` stehen in `app.py` und in **keiner** Fixture. Jeder Test, der
eine Farbe, eine Breite oder eine Einrückung misst, misst deshalb Windows,
solange er die Betriebslage nicht selbst herstellt: Systemschrift statt der
Symbolfarbe des Themas, Systemakzent statt `palette().highlight()` des Themas,
Qts eigene Menüabstände statt der des Stylesheets — und `isDefault()` eines
Dialogknopfs ist vor `show()` überall `False`. Ein solcher Test kann dabei
**grün** sein: Zwei falsche Werte, deren Verhältnis stimmt, sind von zwei
richtigen nicht zu unterscheiden — und ein Test, der so grün wird, wird es
jahrelang (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

Praktisch, und es sind drei Zeilen:

```
before = QApplication.instance().styleSheet()
apply_theme(QApplication.instance(), "dark")
apply_style(QApplication.instance(), "dark")
...                                    # messen
QApplication.instance().setStyleSheet(before)   # ins finally
```

**Und wo die Messgröße von der Schriftmetrik abhängt, hilft auch das nicht** —
offscreen gibt es keine Schrift, und der Abschnitt darüber sagt, dass so etwas
gar nicht offscreen zu messen ist. Farben sind der Fall, der sich herstellen
lässt; Breiten sind es nicht.

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

`rendered` für Tests, deren Grün an einem **Erzeugerlauf** hängt: Sie
vergleichen den Code gegen eine eingecheckte, erzeugte Datei — die
Handbuchseiten der Website, die Referenz daraus, die Abbildungsstempel. **Die
CI fährt sie nicht** (Entscheidung Robert, 03.09.2026), und der Grund ist
derselbe, aus dem `AGENTS.md` „Bilder und Handbuch nur beim Release" sagt: Eine
neue Operation macht sie rot, und was sie dann verlangt, ist kein Codefehler,
sondern `tools/make_manual.py` und `tools/stamp_assets.py` (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

Sie bleiben im lokalen Lauf, und dort sind sie richtig: Wer vor einem Release
`/pruefen` fährt, soll erfahren, dass die Seiten hinterherhängen. Wer sie
ausdrücklich allein will, nimmt `-m rendered`.

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

* **`$?` in derselben Zeile, die auch etwas anderes ausführt, ist kein `$?`
  mehr.** Die Falle darüber kennt die Pipe und das nachgestellte `echo`; dies
  ist ihre dritte Gestalt, und sie sieht harmlos aus:

      echo "Lauf $i: Exit=$?  $(grep -c passed datei)"

  Die Kommandosubstitution läuft mit, bevor die Zeile steht, und `$?` trägt
  danach ihren Status — die Zeile meldet „Exit=0", während die Shell daneben
  `Segmentation fault` schreibt.

  Der Griff ist eine Zeile mehr: **den Code als allerersten Befehl in eine
  Variable**, dann alles übrige.

      "$py" -m pytest … > "$log" 2>&1
      code=$?
      zeichen=$(head -c 3000 "$log" | …)
      echo "Exit=$code  gelaufen=$zeichen"

  Die allgemeine Form dahinter ist immer dieselbe und steht schon in dieser
  Datei: **`$?` gehört dem letzten Befehl, und „letzter" heißt wörtlich.**

* **Ein Hintergrundlauf meldet den Status seiner Hülle, nicht den des Programms
  darin.** Die Abschlussmeldung sagt „completed (exit code 0)" auch über einem
  Lauf, der mit **139** abgebrochen ist. Das ist die Pipe-Falle in neuer Gestalt
  und die gefährlichere von beiden: Eine Pipe baut man selbst und weiß davon,
  ein Hintergrundlauf sieht aus wie ein Lauf. Also auch hier: Der Lauf schreibt
  seinen eigenen Exit-Code in eine Datei (`…; echo "Exit=$?" > …`), und gelesen
  wird der, nicht die Meldung.

**Ein Prozessabbruch macht das Tor auch nach „N passed" rot.** Ein Riss
beim Aufräumen und eine fehlgeschlagene Zusicherung sind unterschiedliche
Ursachen. Beide verhindern die Abnahme; Fortschrittszeichen und Schlusszeile
ersetzen keinen erfolgreichen Prozessausgang. Zur Diagnose gehören sowohl
native Rückgabewerte als auch schon vorher gemeldete `F`/`E` ins Ergebnis.

Praktisch: **Beim Melden eines Laufs gehört die Zahl der `F` dazu, nicht nur die
Zusammenfassung.** Ein Riss verschluckt die Zusammenfassung, in der die Namen
stünden; die Fortschrittszeichen davor überleben ihn.

### Und die dritte Gestalt, die tückischste: die Tests *nach* dem Abriss

Die zwei Richtungen oben handeln davon, ein `F` und einen Riss zu verwechseln.
Die dritte verwechselt gar nichts — sie zählt richtig und schließt falsch:
Fortschrittszeichen und **null `F`** bis zur Abrissstelle, und daraus wird
„grün", obwohl die Tests dahinter nie gelaufen sind (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

> **Ein Lauf, der abbricht, hat nicht bestanden, sondern aufgehört.** Die Zahl
> der gelaufenen Tests gehört neben den Exit-Code, und zwar als Bruch: 124 von
> 372 ist keine Aussage über die übrigen 248.

Der Handgriff dagegen kostet nichts: `pytest --collect-only -q | wc -l` nennt
die Sollzahl, und die Fortschrittszeichen nennen die Istzahl. Sind sie
ungleich, ist das Ergebnis **unvollständig** und nicht grün.
`suite-getrennt.sh` halbiert dann die betroffene Portion und reiht beide
Hälften wieder ein — auch wenn die ganze Fensterdatei kleiner als die normale
Portionsgröße ist. Der ursprüngliche Prozessabbruch bleibt gezählt;
erfolgreiche kleinere Teile ergänzen die Diagnose und machen diesen Lauf
nicht rückwirkend grün. Das Tor endet mit 0 oder 1, nie mit einer Anzahl,
die bei 256 Fehlern auf 0 umbrechen kann.

Und der Grund, aus dem gerade diese Gestalt so leicht durchgeht: Die beiden
anderen fühlen sich wie ein Urteil an — man entscheidet, ob ein Zeichen ein
Fehler ist. Diese hier fühlt sich wie gar keine Entscheidung an. Man liest
eine Zahl, die stimmt, und ergänzt still eine zweite, die man nicht gemessen
hat.

## Ein roter Leistungstest ist erst dann eine Regression, wenn er es zweimal ist

`tests/.performance.json` hält die Bestwerte, gegen die die 25-%-Schwelle
misst. Die Datei ist **absichtlich** ignoriert (`.gitignore`), und der Grund
steht bisher nur dort: Die Werte sind maschinenabhängig (Bauplan §31). An
diesem Projekt arbeiten drei Maschinen; die Bestwerte des schnellsten Rechners
würden den Laptop dauerhaft rot färben, ohne dass eine Zeile langsamer
geworden wäre (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

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

### Die Regel fängt Fremdlast — sie fängt keinen Wert, der um die Schwelle streut

„Zweimal fahren" trennt Last von Code, weil Last kommt und geht: Schwankt die
**Menge** der roten Tests, war es die Maschine. Ein einzelner Messwert, der um
die Regressionsschwelle **streut**, erfüllt dieselbe Regel dagegen zuverlässig
— er reißt in Serie und wird von selbst wieder grün, ohne dass sich eine Zeile
geändert hätte. In der Ausgabe sieht beides identisch aus. **Der Wert liegt
nicht über der Schwelle, er liegt auf ihr:** vier Überschreitungen in Folge,
und der fünfte Lauf setzt `strikes` zurück (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

Der Unterschied ist keine Nuance, weil er auf zwei verschiedene Suchen
schickt: „stabil verschlechtert" heißt, jemand sucht eine Ursache im Code.
„Streut über die Schwelle" heißt, jemand prüft die **Bestmarke** — stammt sie
aus einem besonders ruhigen Lauf? Entschieden wird das durch eine Messreihe
gegen einen **älteren Stand**, nicht durch einen weiteren Lauf gegen den
heutigen.

**Und zwei Läufe im selben Zeitfenster sind eine Messung.** Was die Regel oben
verlangt, ist nicht „zweimal", sondern **zweimal unter anderen Bedingungen**.

### Die Messreihe wurde gefahren, und sie entschied gegen die Bestmarke

Die Messreihe gegen einen älteren Stand ergab: Kein Code war langsamer
geworden, die Bestmarken waren auf keinem Stand reproduzierbar, kein Budget war
gerissen. Rot war der Regressionszähler, und die Zusicherung dazu liest sich
als `assert 13 < 2`, was wie eine Zeitangabe aussieht und keine ist (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

**Daraus folgte der Umbau von Minimum auf Median** (`measure`, `WINDOW`,
`MIN_RUNS`). Das Argument fürs Minimum war: Eine Messung ist nach oben beliebig
verrauschbar und nach unten nicht. Das stimmt für **Fremdlast** und nicht für
den **Maschinenzustand** — ein Rechner mit hohem Takt und ohne
Hintergrunddienst ist schneller, und dieser Zustand ist nicht
wiederherstellbar. Ein Minimum kann nur sinken; ein einziger günstiger Lauf
nagelt es für immer fest.

Ein Median über die letzten fünf Läufe verschiebt sich mit dem
Maschinenzustand und nicht mit einem Ausreißer. Fremdlast fängt er weiter, denn
sie hebt die Mehrzahl der Läufe. Und er verdeckt keine echte Verlangsamung: Wer
eine Rechnung um mehr als ein Viertel teurer macht, reißt die Schwelle sofort,
und `REGRESSION_STRIKES` schlägt zu, bevor der Median nachgezogen ist.

**Der Umbau hatte eine Delle, und sie zeigte sich erst im zweiten Lauf.** Der
migrierte alte Bestwert ist selbst ein Ausreißer und zieht den Median nach
unten, solange das Fenster halb leer ist. Deshalb `MIN_RUNS = 3`: **Zwei Läufe
bewusst blind sind ehrlicher als zwei Läufe falsch rot.** Ab dem dritten Wert
steht der Ausreißer außen und bestimmt den Median nicht mehr — genau die
Eigenschaft, wegen der dort ein Median steht.

Für den nächsten, der eine Marke prüft: **Die Baseline ist maschinenlokal**
(`tests/.performance.json`, in `.gitignore`). Sie zurückzusetzen betrifft
niemanden sonst, und nach einem begründeten Verfahrenswechsel ist es richtig —
ein Zähler, der Überschreitungen gegen eine alte Marke zählte, sagt gegen die
neue nichts.

## Fremdlast macht auch funktionale Tests rot, nicht nur Messungen langsam

Der Abschnitt oben handelt von Zeiten, und deshalb liest man ihn als Regel für
Leistungstests. Er ist zu eng gefasst: Ein Lauf **ohne Schloss** mitten in
einem fremden Tor endete mit **Exit 139** und Zugriffsverletzung; dieselben
Tests einzeln liefen in einer Sekunde grün durch (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

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
  Aussage. Sie kosten zwanzig Sekunden.

  1. **Welche Prozesse gehören überhaupt zum Lauf?** Nicht die aus dem
     Prozessbaum: Windows setzt die Elternnummer nicht um, wenn ein
     Zwischenprozess endet, und der `pytest` fällt dann heraus. Und nicht alle
     mit `pytest` in der Kommandozeile: Die Hülle von `gate_lock` trägt den
     ganzen geschützten Befehl, wartet aber nur — wartende Hüllen sehen aus
     wie hängende Läufe.

     ```
     Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
       Where-Object { $_.CommandLine -match '-m pytest' -and
                      $_.CommandLine -notmatch 'gate_lock' }
     ```

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
überflüssiger.** Es auf die Leistungstests zu schrumpfen ist gemessen
widerlegt, und zwar aus der Gegenrichtung: Mit `-n 8` lastet die Sammelgruppe
die Maschine so aus, dass der **fremde** Lauf kippt — nicht wegen Parallelität
oder Reihenfolge, sondern wegen **Speicher**: Acht Prozesse, die je eine
speicherhungrige Geometrie rechnen, sind etwas anderes als einer. Parallelität
macht Speicherhunger sichtbar — als Korrektheitsfehler. Vorher belegte ein
serieller Torlauf einen Kern und störte niemanden. Also: **Je paralleler das
Tor, desto strenger das Schloss.** Der Gewinn kommt trotzdem, nur an anderer
Stelle: nicht dadurch, dass das Schloss fällt, sondern dadurch, dass das, was
es umschließt, kleiner wird (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

**Eine feste Zahl statt `-n auto`.** Auf 32 logischen Kernen startet xdist 32
Worker und stirbt beim Verteilen (`INTERNALERROR KeyError <WorkerController
gw13>`, keine Tests gesammelt). Wichtiger als der Absturz ist aber der Grund
dahinter: Auf einer anderen Maschine ist `auto` etwas anderes, und ein Tor,
das je nach Kernzahl anders misst, hat eine stille Variable. Dieselbe
Begründung wie bei `.performance.json`.

**Zweimal fahren und die Mengen vergleichen, nicht die Zahlen.** Ein Test, der
von einem Vorgänger abhängt, wird bei paralleler Ausführung nicht rot — er wird
*manchmal* rot. Zwei gleiche Läufe sind kein Beweis, zwei ungleiche sind sofort
einer.

### Wer das Schloss belegt sieht, schreibt nicht

Das Schloss schützt den Halter vor **Rechenlast**. Es schützt ihn nicht vor
**dir**. Wer bei belegtem Schloss eine Datei ändert, verfälscht nicht den
eigenen Lauf — der kommt ja erst noch —, sondern den fremden, der gerade läuft:
ein neuer `tr()`-Text, den die laufende fremde Suite ohne Katalog sieht, oder
eine Zeile in `suite-getrennt.sh`, die Bash in den laufenden Lauf nachliest
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026). Der zweite Fall ist behoben — das Skript kopiert sich beim
Start. Der erste nicht: Eine Datei, die der laufende Test importiert, lässt
sich nicht wegkopieren. Dafür bleibt nur die Regel. `gate_lock.py status` sagt
in einer Sekunde, ob jemand fährt.

**Und zwar vor jeder Schreiboperation, nicht vor jeder Arbeitseinheit.** Das
Schloss kann zwischen zwei Schreibvorgängen den Halter wechseln. Wer schreibt,
sieht **jedes Mal** nach; die Sekunde kostet weniger als ein fremder Torlauf.

### Der fremden Messung glaubt man so wenig wie der eigenen

Eine Zahl, die eine Sitzung weiterreicht, wird auf dem Weg **fester**, nicht
lockerer: Jede Weitergabe streift eine Unsicherheit ab, bis am Ende eine Zahl
steht, die niemand mehr hinterfragt. Und der häufigste Grund für eine falsche
Zahl ist immer derselbe: **Eine Mustersuche misst, was das Muster kennt — und
schweigt über den Rest, ohne es zu sagen** — ohne Wortgrenze zu viel, mit einem
Muster für einen Fall zu wenig, mit `"pytest" in CommandLine` wartende
`gate_lock`-Hüllen als laufende Tests (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

Wer eine Zahl weitergibt, gibt deshalb das **Muster** mit, nicht nur das
Ergebnis. Und wer eine bekommt, prüft sie an einem Fall, von dem er weiß, wie
er ausgehen muss — bevor er auf ihr aufbaut.

### Wie viele Läufe trägt eine Aussage?

„Zweimal fahren" ist keine Zahl, sondern eine Faustregel — und wie viele Läufe
eine Aussage wirklich braucht, hängt daran, **wie oft die Sache ohne jede
Änderung schon schiefgeht**. Gemessene Basisraten reichen von 1/10 in ruhiger
Lage bis 5/5 unter Fremdlast (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

Daraus folgen drei Dinge, und das dritte kostet am meisten Zeit, wenn man es
vergisst:

* **Bei 1/10 ist „0 von 10" kein Beleg, sondern kein Widerspruch.** Wer nach
  zehn grünen Läufen „behoben" meldet, meldet eine Wahrscheinlichkeit von
  ungefähr einem Drittel als Gewissheit. Sagen, was die Zahl trägt, ist Teil
  des Ergebnisses.
* **Bei 5/5 ist gar nichts messbar.** Eine Änderung kann die Rate nicht mehr
  erhöhen, also entlastet ein „gleich schlecht" sie nicht. Solche Läufe zählen
  nicht als Messung, auch wenn sie Zahlen liefern.
* **Die Messlatte gehört vor die Messung.** Sie wird festgelegt, bevor
  irgendjemand ein Ergebnis kennt. Wer die Grenze hinterher zieht, findet immer
  eine, die zum Ergebnis passt.

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
importiert.

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
stehenden Lauf nicht.

## Wer mit privatem Index committet, zieht den Haupt-Index nach

Das stand hier und gehörte nicht hierher: Es ist Commit-Betrieb, nicht
Testwissen — beim Ändern einer Testdatei lud es mit, beim Committen ohne
Testdatei gar nicht. Es steht jetzt in `.claude/skills/liefern/SKILL.md`.

## Was habe ich gerade gemessen?

Vier Sitzungen haben an einem Abend **sieben** Messfehler gemacht, und alle
sieben hatten dieselbe Form:

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

Drei weitere aus drei Sitzungen zeigen die Asymmetrie, die in der Tabelle oben
noch nicht steht:

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
(`assert gb_texte`), und `suite-getrennt.sh` auch — die Zeile
„Sammelgruppe: 3554 passed" ist genau diese Zusicherung, nur für das Tor.

Die zweite Hälfte kostet noch weniger: **Gib dem Werkzeug einen Fall, dessen
Ausgang du kennst.** Ein Prüfer für Doppelungen, der den bekannten Fall nicht
findet, ist kaputt; einer, der ihn findet, hat seine erste Zusicherung (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

## Ein eingechecktes Artefakt überlebt seinen Erzeuger

`app/examples/*.p3d` liegen im Repository, und neun Tests fragen sie ab: Öffnen
sie, rechnen sie, sind ihre Op-Kennungen eindeutig? Alle neun bleiben grün,
wenn `tools/make_examples.py` aufhört zu laufen — die Dateien sind ja da.

**Und es fährt sie fast nie jemand.** Das Werkzeug läuft im Paketier-Job, und
der startet nur bei einem Tag. Zwischen zwei Veröffentlichungen ist es also
ungeprüft, während alles, was es aufruft, sich weiterbewegt — bis ein Paketbau
an einer Änderung abbricht, hinter der jeder Lauf grün war (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

Die Frage dazu ist eine eigene, weil keine andere in dieser Datei sie stellt:

> **Prüfe ich das Ergebnis oder das, was es erzeugt — und wann läuft der
> Erzeuger das nächste Mal?**

Steht die Antwort auf „beim nächsten Release", gehört ein Test daneben, der
ihn fährt. Der hier kostet ein Hundertstel: Die Bau-Funktionen stellen nur den
Op-Stapel auf, und `History.apply` prüft die Kennungen dabei — gerechnet wird
erst bei der Auswertung, die niemand anstößt.

Dieselbe Frage lohnt bei jedem eingecheckten Erzeugnis: Bildschirmfotos,
Handbuchseiten, Lizenzmanifest, Vorschaubilder.

## Prüft dieser Test eine Zusage — oder den Ist-Zustand?

Ein Test kann einen Fehler **festschreiben**. Er ist dann grün, solange der
Fehler da ist, und wird rot, sobald jemand ihn behebt — **er hat die
Verbesserung blockiert, statt sie zu tragen** (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

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
  Test es fragen kann — und die anderen vier sehen danach mitgeprüft aus
  (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026). Wer ein Argument herauszieht, um es prüfbar zu machen, zählt
  die übrigen desselben Aufrufs — die Extraktion prüft eines und tarnt den
  Rest.

  Derselbe Aufruf trug einen zweiten stillen Fehler von der anderen Sorte: ein
  `Signal(str)` mit einem Namen darin an einem Slot, der einen Suchtext
  erwartet. Qt verbindet alles, dessen Stelligkeit passt. Was dagegen hilft,
  steht in `.claude/memory/signal-passt-an-den-falschen-slot.md`; die zwei
  gehören zusammen gelesen, weil dieser Punkt sagt, wie man den Fehler beim
  **Schreiben** vermeidet, und jener, wie man ihn beim **Prüfen** findet.

* **Am Prüfobjekt vorbei.** Der Test baute den `QThread` selbst und startete ihn
  selbst. Damit blieb er grün, als der Dialog von `start()` auf `run()` fiel —
  also genau dann, als die Rechnung wieder im Hauptthread lief. Gebaut wird, was
  die Anwendung baut.
* **An der Aussage vorbei.** `str(op_id) in tooltip` war grün, weil „2" auch in
  „2,40 mm" steht. Eine Teilzeichenkette, die zufällig vorkommt, ist keine
  Prüfung — verglichen wird mit dem ganzen Satz. In seiner peinlichsten
  Gestalt: `"2" in "1 von 2"` — die Zusage galt dem **Platz** in der
  Trefferliste, erfüllt hat sie die **Anzahl** daneben.
* **Am erfundenen Beleg vorbei — und das ist der teuerste der Liste.** Ein
  Docstring begründete eine Zusage mit einem Wort, das im ganzen Bestand nicht
  vorkommt; die Mutation blieb grün, und die Lücke war durch eine Begründung
  gedeckt, die sich wie eine Messung las (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

  Der Unterschied zu den vier Punkten darüber: Die messen am falschen Ort,
  dieser **behauptet einen Ort, den es nicht gibt** — und ein Leser, der die
  Begründung glaubt, prüft die Stelle nie wieder
  ([[benannte-falle-schuetzt-nicht]] ist derselbe Mechanismus, eine Ebene
  höher). Der Griff dagegen kostet zehn Sekunden: **Ein Beleg, der ein
  konkretes Wort, eine Zahl oder eine Datei nennt, wird gegen den Bestand
  gegriffen, bevor er in einen Docstring kommt.**

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

Ein Registerpunkt hat vorgeschlagen, überall eine Zeile danebenzuschreiben.
Angewandt auf 29 Kandidaten waren **14 echte Lücken** und 15 nicht. Der Schnitt
läuft entlang einer Frage:

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
meldet `no tests ran` und gibt **Exit 5**. Das geteilte Tor wertet diesen
Nichtnull-Exit als Fehler. Eine Zusicherung im Testkörper fängt eine leere
Parameterliste dennoch nicht: Sie liefe nie.

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
einmal passiert, aufgefallen nur, weil danach ein `grep` lief.

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

**Die Grenze davon ist gemessen worden:** Ein Job `in_progress` antwortet mit
`BlobNotFound`, HTTP 404. Was die API hergibt, ist das Protokoll eines
**fertigen** Jobs, während der **Lauf** noch läuft — und das genügt, weil ein
Job, der rot geworden ist, fertig ist (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

**Und die Falle daneben, die dabei prompt zugeschnappt hat:** `gh api … |
tail -6` meldet **Exit 0** über einer 404-Antwort — der Rückgabewert von
`tail`. Dieselbe Pipe-Falle, die weiter oben in dieser Datei steht, an einem
Werkzeug, das kein Testlauf ist. Sie gilt für jeden Befehl, dessen
Rückgabewert man liest, nicht nur für `pytest`.

Der Handgriff davor halbiert die Suche: Die neueste `ruff` in einer
**eigenen** Umgebung gegen das Projekt zu fahren (nicht in der `.venv` — vor
einem Paketbau wird dort nichts installiert) schließt die wahrscheinlichste
Ursache aus, bevor das Protokoll überhaupt da ist.

### Eine Automatik, die in Wahrheit Handarbeit ist, ist gefährlicher als keine

`CLAUDE.md` sagt zu: „Jeder Commit geht sofort hinaus, `.githooks/post-commit`
pusht ihn." Im Arbeitsbaum gab es diesen Hook zeitweise **nicht** —
`core.hooksPath` war nicht gesetzt, und ohne ihn sieht Git `.githooks/` nie an.
Gemerkt hat es niemand, **weil das Ergebnis stimmte** — es hat immer jemand von
Hand gepusht (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

Daraus folgen zwei Dinge, und das zweite ist die eigentliche Regel:

* Eingeschaltet wird sie mit `git config core.hooksPath .githooks` — **nicht**
  mitten in einem Release, weil ein Hook, der ab sofort bei jedem Commit pusht,
  während jemand Pakete baut, mehr kostet als er rettet.
* **Woran merkt man, dass sie läuft?** Eine Automatik, deren Ausbleiben
  niemandem auffällt, ist keine. Also gehört zu ihr eine Zusicherung:
  `core.hooksPath` zeigt auf `.githooks`, und jede Datei darin ist ausführbar.

### Die Isolation deckt Qt, Verzeichnisse, die Fremdprogramme und das Netz ab

`conftest.py` hält die Maschine aus dem Ergebnis heraus: Offscreen-Qt,
Nutzerverzeichnisse in einem Temp-Ordner, kein gefundenes Fremdprogramm — und
seit der Fixture `_the_network_stays_out_of_it` auch kein erreichbares Modell.
Sie leert die Liste der Backends; `llm.available()` fragte sonst über
`socket.create_connection`, ob eines antwortet, und ein Rechner mit laufendem
Ollama misst damit etwas anderes als einer ohne; die CI hat gar keins —
dieselbe Klasse wie ein installierter Slicer, nur eine Ebene weiter. Gefunden
in einem Absturzstapel von `test_ui.py` (Vorfall: ROADMAP-ARCHIV.md,
04.09.2026).

**Kein Test öffnet eine echte Netzwerkverbindung.** Wer eine Erreichbarkeit
prüfen will, tut es wie `test_backends.py` an einer selbst gebauten Instanz
gegen einen garantiert geschlossenen Port (`localhost:1`). Geleert wird die
Liste der Backends, nicht die Prüfung selbst — sonst wird aus dem Test eine
Attrappe, die nichts mehr misst.

### Ein Testdatensatz, in dem alles gleich heißt, prüft weniger als er aussieht

Zweimal an derselben Stelle, beide Male von der Gegenprobe gefangen:
`website/version.json` nennt jedes Paket zweimal — als `"file"` und in der
`"url"` —, und `updates.py` liest **beide**. Ein Test, der nur eines der Felder
prüft, und ein Testdatensatz, der beide gleich füllt, blieben bei der Mutation
grün (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

> **Zwei Felder mit gleichem Wert machen jeden Test grün, der nur eines liest.**

Die Lösung ist nicht, die Gegenprobe zu verschärfen, sondern **den Datensatz zu
entzerren**: `{"url": "…f=geladen.exe", "file": "benannt.exe"}`. Ein Test, der
zwei Wege unterscheiden soll, braucht zwei unterscheidbare Werte — sonst prüft
er, dass zwei Kopien derselben Zahl übereinstimmen.

Verwandt mit „an der Aussage vorbei" oben (`str(op_id) in tooltip` war grün,
weil „2" auch in „2,40 mm" steht): Beide Male stimmt der Vergleich zufällig.

### Lokal gegen lokal sagt nichts darüber, was oben liegt

Beim Veröffentlichen wurden einmal die alten Pakete gelöscht, **bevor** die
Seiten und `version.json` hochgeladen waren. **Keine Prüfung hat es gemerkt,
und alle waren grün.** Lokal war durchgehend alles stimmig. Falsch war nur, was
**oben** lag, und danach hatte niemand gefragt (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

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

Vor „2 von 4 sauber" hat ein Blick von zwei Minuten in die fremde Fixture die
Zeile gefunden, die zehn weitere Läufe nur schärfer beziffert und nie genannt
hätten (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

Die Faustregel dazu:

> **Zeigt der Verdacht auf eine benennbare Stelle, ist Lesen billiger als
> Zählen. Zeigt er nirgendwohin, hilft nur die Rate.**

## Ein Signal, das jedes Mal kommt, lässt sich halbieren

Der Abbau-Absturz galt als Eigenschaft ganzer Fensterdateien — 86 Sekunden für
ein Ja/Nein, drei Ausgänge bei drei Läufen —, und deshalb hat ihn niemand
eingegrenzt. Er ist aber **deterministisch**, und damit war die Suche billig:
Halbieren über die Zahl der Tests fand den einen, der **allein** riss (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

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
Lösung. Die war ein einheitliches `release()` auf jeder Klasse mit Arbeiter, dazu eine
Prüfung, die per `ast` liest, wer eine `WorkerLeash` anlegt, und von jedem
dasselbe Wort verlangt. Ein sechster Name kann seitdem nicht mehr entstehen.

**Und der Umbau hat sofort einen Fehler freigelegt**, den fünf Namen verdeckt
hatten — er war vorher da und hatte nur keine Stelle, an der er auffallen
konnte (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

## Eine Zusicherung in beide Richtungen kann den Fehler festhalten

`test_registry.py` prüfte mit `assert named == declared`, dass jedes
Merkmalsfeld sich als solches deklariert. Der Zweck war richtig: §21.3 sucht
Merkmalsverweise nach der **Art**. Getestet wurde davon aber nur die eine
Richtung; die andere sagt etwas ganz anderes, nämlich **„kein Merkmalsfeld
darf anders heißen"** — und genau daran ist die Behebung eines echten Fehlers
hängengeblieben (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026). **Ein Test, der einen Fehler am Behobenwerden
hindert, prüft die Gewohnheit und nicht die Zusage.**

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
aufgelöst, also zeigt er ins Leere, wenn die Operation nichts verbraucht.

## Ein Messwerkzeug, das den Absturz nicht überlebt, misst nichts

Ein Messwerkzeug, das sich an `gc.callbacks` hängt und seine Treffer erst in
`pytest_sessionfinish` ausgibt, liefert **null Zeilen**, wenn der Lauf, um den
es geht, abstürzt — ein abgestürzter Prozess erreicht kein Sitzungsende. Ein
Werkzeug, das genau den Fall nicht überlebt, für den es gebaut ist, gibt nur
dann eine Zahl aus, wenn sie niemanden interessiert. Zeilenweise in eine Datei
geschrieben (`open(pfad, "w", buffering=1)`) stand die Antwort nach **einem**
Lauf (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

Der Umweg, der beinahe gegangen worden wäre: **sechzehn Läufe**, acht je Seite,
abwechselnd mit und ohne einen vermuteten Fix — eine halbe Stunde für eine
Wahrscheinlichkeitsaussage, wo eine direkte Messung die Ursache nennt.

**Die Frage davor lohnt sich also:** Will ich wissen, *ob* etwas hilft, oder
*warum* es passiert? Das zweite ist oft billiger zu messen und immer mehr wert.

## Nach einer Änderung an `app/` oder `tools/`: zwei Läufe von je drei Sekunden

Viermal an einem Tag ist ein deutscher Bezeichner ins Tor gekommen, und die
Ursache war jedes Mal dieselbe und jedes Mal vernünftig: Gefahren wurden die
Tests des *Gebiets*, in dem die Änderung lag — nicht die, die *jede* Datei
prüfen.

```
.venv\Scripts\python.exe -m pytest tests/test_language_rules.py -q   # ~3 s, 745 Fälle
.venv\Scripts\python.exe -m ruff check .                             # ~2 s
```

**`ruff check .` ohne Pfadangabe**, und das ist der Teil, der zweimal fehlte:
Ein eingegrenzter Prüflauf über `app/ui/` spart Sekunden und lässt eine
Testdatei durch, die dann einen fremden Torlauf kostet. Beides ist Code, und
das Tor prüft beides.

**Und welche Testdateien sonst noch betroffen sind, sagt der Importgraph,
nicht das Gefühl:** `tools/affected_tests.py` liest, wer ein geändertes
Modul mittelbar importiert, wer den Baum liest (`rglob`, `walk_packages`)
und wer eine geänderte Nicht-Python-Datei beim Namen nennt — `--why` nennt
je Datei den Grund, `--split` die Aufrufe (Fensterdateien einzeln), `--run`
fährt sie. Die Auswahl ist das Werkzeug *zwischen* den Schritten; das Tor vor
dem Commit bleibt `/pruefen`. Eine Änderung an `types.py` oder `errors.py`
berührt über den Graphen fast alles, und das Werkzeug sagt das dann auch.

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

Die Regel „wer das Schloss belegt sieht, schreibt nicht" ist zweimal erfüllt
worden und hat trotzdem nichts verhindert. Beide Male so:

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

Dieselbe Form gibt es ohne Schloss: Eine Messung, die **nach** dem Testlauf
läuft, während dazwischen jemand geschrieben hat, misst einen anderen Baum.
**In einem Baum, in dem vier Sitzungen schreiben, misst man nicht den Baum,
sondern einen Zeitpunkt** — und der steht nicht im Ergebnis (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).
