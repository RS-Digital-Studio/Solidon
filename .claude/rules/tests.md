---
description: "Die Suite — Entwicklungs- und Release-Tor, Isolation als Betriebslage, Marker und Korpus, ehrlich gelesene Läufe und Tests, die prüfen, was sie behaupten"
paths:
  - "tests/**/*.py"
  - "conftest.py"
---

# Regeln für die Suite

Die harten Regeln aus `AGENTS.md` halten Tests, wo eine mechanische Prüfung
möglich ist — welche den ganzen Baum prüfen und welche nur Stellen, sagt
`AGENTS.md` dort. Welche Datei was prüft, steht in `AGENTS.md`
(„Testarten“) und `tests/CLAUDE.md` („Was wo geprüft wird“); wie ein Lauf
gefahren und gelesen wird, in `/pruefen`. Anlässe und Messwerte stehen unter
denselben Überschriften in `konzepte/begruendungen/regel-tests.md`.

## Entwicklung und Release

- **Je Schritt die betroffenen Tests, vor dem Commit das Entwicklungstor,
  Fenster, Renderer und Leistung ausschließlich beim Release** — auch nicht als gezielte
  Teilmenge (`CLAUDE.md`, `/pruefen`). Ein grüner Entwicklungslauf ist kein
  Release-Nachweis.
- **Wer ein Widget baut, fordert `qt_app` an.** Getrennt wird je Test, nicht je
  Datei, über den Marker `windowed`, den `tests/conftest.py` jedem `qt_app`-Test
  gibt (wer ein Fenster im Unterprozess öffnet, setzt ihn selbst). Ohne die
  Fixture lief ein solcher Test nur, weil ein Nachbar die Anwendung schon
  erzeugt hatte — im Tor stürzt er ab.
- **Wer echte Grafik abfragt oder aufbaut, fordert `require_graphics_adapter`
  an.** Direkte Adapter- und Kindprozessprüfungen setzen `rendering` selbst.
  Die Geräteabfrage läuft erst in der Fixture, nie beim Modulimport oder in der
  Sammlung. Reine Rechenfälle bleiben im Entwicklungstor, auch in gemischten
  Dateien.
- **CI-Aufteilung** nach dem Vertrag CI-01 bis CI-08 (`AGENTS.md`; Wächter
  `test_packaging.py` für Jobs, Plattformen, Releasegrenze und Berichte,
  `test_ci_runner.py` für vollständige Partitionen und echte
  Prozessausgänge). `--ci-shard I/N` teilt die Kernsuite je Datei nach der
  Markerwahl, eine Laufzeittabelle verteilt nur die gesammelte Menge, neue
  Dateien kommen von selbst dazu; Tabellen erzeugt `tools/ci_shards.py` aus
  JUnit-Berichten mit Herkunftsvermerk — keine Zahl von Hand.
- **Betroffene Tests folgen auch impliziten Paketimporten.** Eine Änderung an
  `__init__.py` betrifft die Importeure seiner Untermodule; gelöschte Module
  und Testhelfer behalten ihre Nutzer. Die Git-Auswahl liest NUL-getrennte
  Pfade und beide Seiten einer Umbenennung (`tools/affected_tests.py`).
- **Beim Verschieben und Zusammenlegen von Tests** bleiben Fallnamen,
  Parameter, Marker und aufgelöste Fixtures erhalten, Parameterwerte und
  Zusicherungen nachvollziehbar — Fallzahlen sind kein Deckungsnachweis.
  Gemeinsame Vorbereitung teilt keine veränderliche Eingabe; zusammengehörige
  statische Zusicherungen dürfen denselben AST oder dieselbe Extraktion teilen.
  Determinismus braucht zwei unabhängige Bauten, und eine gemeinsame Fixture
  spart keine importierte Geometrie ein, deren Verhalten geprüft wird.
- **Eine neue Testart bekommt eine eigene Datei**; ein neues Fehlerbild wird
  eine Testdatei, kein Sonderfall im Code.

## Isolation ist Teil des Tests

`tests/conftest.py` hält die Maschine aus dem Ergebnis: Offscreen-Qt,
Nutzerverzeichnisse im Temp-Ordner (§38), kein gefundenes Fremdprogramm, kein
erreichbares Modell (`_the_network_stays_out_of_it` leert die Liste der
Backends). Wer diese Fixtures umgeht, prüft nicht, was er zu prüfen vorgibt.

- **Kein Test öffnet eine echte Netzwerkverbindung.** Erreichbarkeit prüft man
  wie `test_backends.py` an einer selbst gebauten Instanz gegen einen sicher
  geschlossenen Port (`localhost:1`); geleert wird die Liste der Backends,
  nicht die Prüfung.
- **Ein PHP-Prüfserver startet über `php_command`** (`tests/php_probe.py`), der
  OPcache abschaltet: Unter Windows teilen sich alle PHP-Prozesse den
  Opcode-Speicher, und parallele Server mit anderen Erweiterungen stürzten ab.
- **Ein `pytest.main` im Prozess der Suite gibt `sys.modules` und `sys.path`
  zurück, wie es sie fand** (`tools/list_windowed_tests._collect`): Eine
  `conftest.py` ohne Paket verdrängt dort das Modul `conftest` der Suite, und
  spätere Tests im selben Arbeiter finden das fremde.
- **Das Torskript entfernt seine temporäre Skriptkopie und sein Protokoll bei
  jedem Ende**, auch beim Scheitern der Vorbereitung. Beim Laden der Funktionen
  über `source` bleiben Protokolle des Aufrufers unangetastet.
- **Die Umgebung wird gegen `constraints.txt` aufgebaut**, sonst wird die Suite
  ohne geänderte Zeile rot.
- **`filterwarnings = ["error"]`**: Eine Warnung wird behoben, nicht
  unterdrückt. Ausnahmen nur für unbehebbaren Fremdcode, mit Meldungstext
  **und** auslösendem Modul, dem Nachweis, dass eigener Code sie nicht
  auslöst, und einem Kommentar, wann sie wegfällt (das zeigt der Job „Neueste
  Versionen“ in `build.yml`, der nur öffentliche `v*`-Tag-Pushes und
  Handstarts mit `check_latest` im öffentlichen Repository ausführt).

### Isolation heißt Betriebslage, nicht Nullzustand

Wer eine Rücksetzung baut, prüft ihren Zielzustand: Sie stellt her, was der
**Kunde** hat. Quellsprache und Millimeter sind der Auslieferungszustand;
Thema, Stylesheet und geladenes Register gehören zur Betriebslage und werden
nicht weggeräumt.

- **Wer eine Breite, ein Layout oder eine Metrik misst, stellt die
  Betriebslage her** (`apply_theme` im Test), statt sie wegzuräumen — und
  **ganz**: Eine halb hergestellte Lage liefert eine plausible Zahl samt
  Begründung.
- **Offscreen gibt es keine Schrift** (negative Punktgröße, jede Familie
  dieselbe synthetische Metrik, auch ausdrücklich gesetzt). Was an der
  Schriftmetrik hängt, prüft die echte Plattform (`WA_DontShowOnScreen`) oder
  niemand. Die Fensterverträge der Linux-CI laufen offscreen mit DejaVu Sans;
  lokal nachgestellt mit `QT_QPA_FONTDIR` auf einen Ordner nur mit dessen
  TTF-Dateien (aus matplotlibs `mpl-data/fonts/ttf`).
- **Was am Anzeigen hängt, prüft nur ein gezeigter Dialog** (`show()`,
  `activateWindow()`): Ungezeigt gibt es keinen Erstfokus, und ein Test bleibt
  grün, während der erste Bildklick am Fenster ins falsche Feld geht (RM-416,
  `_focus_first_empty_feature`).
- **Ein Test, der nur in einer Lage grün ist, die es im Betrieb nicht gibt, ist
  keine Zusicherung, sondern eine Tarnung** — und Rot in einer solchen Lage
  erzwingt Änderungen, die niemand braucht.
- **Aber nur, wo die Messgröße an der Lage hängt**; sonst vergleicht man über
  dieselbe Funktion, die auch anzeigt (`_native`). **Eine Zeile, deren
  Entfernen nichts rot macht, prüft nichts.**

### Und bei einer Farbe hängt es immer an ihr — die Suite fährt ohne Stylesheet

`apply_theme` und `apply_style` stehen in `app.py`, in keiner Fixture. Wer
eine Farbe, eine Breite oder eine Einrückung misst, misst sonst Windows —
Systemschrift, Systemakzent statt `palette().highlight()`, Qts Menüabstände;
`isDefault()` ist vor `show()` überall `False`. Zwei falsche Werte mit
richtigem Verhältnis halten einen Test jahrelang grün. Der Griff (für Farben;
bei Schriftmetrik hilft er nicht):

```text
before = QApplication.instance().styleSheet()
apply_theme(QApplication.instance(), "dark")
apply_style(QApplication.instance(), "dark")
...                                    # messen
QApplication.instance().setStyleSheet(before)   # ins finally
```

## Marker

- `performance` für Messungen gegen das Budget; Messwerte je Lauf festhalten,
  mehr als ein Viertel schlechter ist ein Fehler. Ein Marker, den kein Lauf
  wählt oder abwählt, steuert nichts und wird nicht angelegt.
- `rendering` für Tests mit echter Adapterabfrage, Rendereraufbau, Zeichnen,
  GPU-Picks oder Bildrücklesen. Entwicklungstor und normale CI wählen sie ab;
  die Releasegruppe (CI-Gruppe `windowed`) fährt sie einmal mit.
- `rendered` für Tests, deren Grün an einem **Erzeugerlauf** hängt (Handbuch,
  Referenz, Abbildungsstempel). CI und reguläres Tor fahren sie nicht
  (Entscheidung Robert): Eine neue Operation macht sie rot, und was dann fehlt,
  ist `tools/make_manual.py` oder `tools/stamp_assets.py`, kein Codefix. Das
  Release-Tor fährt sie mit; allein mit `-m rendered`.

## Korpus

`tests/data/` ist der Referenzkorpus: Erwartete Kennzahlen stehen gegen
Dateien daraus, nicht gegen selbst erzeugte Ergebnisse. Das
Millionen-Dreieck-Modell wird bei Bedarf erzeugt, nicht eingecheckt.

**Ein Sollwert trägt seine Herkunft**: aus der Konstruktion im selben Test
(`cylinder(radius=2.6)` → Ø 5,2), aus dem Korpus (`data/README.md`) oder als
Formel im Assert (`24000.0 - math.pi * 9.0 * 20.0`). Eine aus einem Lauf
abgeschriebene Zahl trägt ihre Herleitung als Kommentar — oder sie ist ein
Determinismusnachweis, und der Test sagt das. Zwei Vernetzungen gegeneinander
zu halten fängt keinen Fehler, der beide gleich trifft.

## Beim Schreiben

Ein Test beschreibt, **was** er sicherstellt und **warum** — der Name allein
reicht dafür selten. Sprache in `tests/`: `AGENTS.md`, „Sprachregelung“.

## Den Lauf messen, nicht einen Filter darüber

Wie ein Lauf gelesen wird, sagt `/pruefen`; hier die Fallen, die schon
zugeschnappt sind:

- **Eine Pipe liefert den Code ihres letzten Glieds, und pytest puffert
  dahinter** — ein stehender Lauf schweigt dann, statt zu melden. In eine Datei
  schreiben, Fortschritt mit `python -u`. Das gilt auch für
  `.claude/scripts/suite-getrennt.sh` und jeden anderen Befehl
  (`gh api … | tail` meldet 0 über einer 404).
- **`$?` gehört dem letzten Befehl, wörtlich**: Ein nachgestelltes `echo`, auch
  eine Kommandosubstitution in derselben Zeile
  (`echo "Exit=$?  $(grep -c passed datei)"`), überschreibt ihn — `code=$?`
  als allererster Befehl nach dem Lauf.
- **Ein Hintergrundlauf meldet den Status seiner Hülle** („exit code 0“ über
  einem Abbruch mit 139): Der Lauf schreibt seinen Code selbst in eine Datei
  (`…; echo "Exit=$?" > …`).
- **`FAILED`-Zeilen schreibt pytest erst am Schluss.** Im laufenden Protokoll
  zählen die Fortschrittszeichen (`.` `s` `F` `E` `x`); im seriellen Lauf nennt
  ihre Position mit `pytest --collect-only -q` den Test. Wer einen Lauf meldet,
  nennt die Zahl der `F` — ein Riss verschluckt die Zusammenfassung.
- **`suite-getrennt.sh` zählt „Läufe mit Fehler: N“ und endet mit 0 oder 1** —
  eine Anzahl bräche bei 256 auf 0 um. Die Zählzeile ist Anzeige, der
  Exit-Code die Zusicherung; ein Prozessabbruch macht das Tor auch nach
  „N passed“ rot, und zur Diagnose gehören native Rückgabewerte und die schon
  gemeldeten `F`/`E`.

### Und die dritte Gestalt, die tückischste: die Tests *nach* dem Abriss

> **Ein Lauf, der abbricht, hat nicht bestanden, sondern aufgehört.** Die Zahl
> der gelaufenen Tests steht als Bruch neben dem Exit-Code: 124 von 372 sagt
> nichts über die übrigen 248.

Soll (`pytest --collect-only -q`) gegen Ist (Fortschrittszeichen): Ungleich
heißt **unvollständig**, nicht grün. `suite-getrennt.sh` halbiert dann die
betroffene Portion, auch eine kleine Fensterdatei, und reiht beide Hälften
wieder ein; der ursprüngliche Abbruch bleibt gezählt, erfolgreiche Teile
machen ihn nicht rückwirkend grün.

## Ein roter Leistungstest ist erst dann eine Regression, wenn er es zweimal ist

`tests/.performance.json` hält die Werte hinter der 25-%-Schwelle und steht
**absichtlich** in `.gitignore`: Sie sind maschinenabhängig (§31), drei
Maschinen teilen das Projekt. Sie nach einem begründeten Verfahrenswechsel
zurückzusetzen ist richtig.

- **Denselben Stand ein zweites Mal fahren**, nicht den Vorgängerstand, bevor
  eine Regression gemeldet wird: Schwankt die *Menge* der roten Tests, ist es
  Last. Auch die Reihenfolge zählt, und die Fremdlast ist meist die eigene
  Arbeit.
- **Zwei Läufe im selben Zeitfenster sind eine Messung** — gemeint ist zweimal
  unter anderen Bedingungen.
- **Ein Wert, der um die Schwelle streut, besteht diese Regel** — er reißt in
  Serie und wird von selbst grün. Ob er streut oder sich verschlechtert hat,
  entscheidet eine Messreihe gegen einen **älteren** Stand.
- **Die Bestmarke ist ein Median, kein Minimum** (`measure`, `WINDOW`,
  `MIN_RUNS`): Ein Minimum kann nur sinken, der Median der letzten fünf Läufe
  folgt dem Maschinenzustand, und eine echte Verlangsamung reißt die Schwelle
  trotzdem sofort (`REGRESSION_STRIKES`). `MIN_RUNS = 3`: Zwei Läufe bewusst
  blind sind ehrlicher als zwei Läufe falsch rot.

Das ist der einzige Teil des Tors, dessen Rot nicht „nicht fertig“ bedeutet.

## Fremdlast macht auch funktionale Tests rot, nicht nur Messungen langsam

Neben einem zweiten Testlauf endet ein Lauf mit Exit 139, dieselben Tests
einzeln laufen grün. Deshalb:

- **Erst nachsehen, was sonst rechnet, dann urteilen**; der billigste
  Gegenbeweis ist der einzelne Test.
- **Steht er oder rechnet er?** Die Prozesse an der Kommandozeile suchen, nicht
  über die Elternkette (Windows setzt sie nicht um; eine durchreichende Hülle
  sieht aus wie ein hängender Lauf):

  ```text
  Get-CimInstance Win32_Process -Filter "Name like '%python%'" |
    Select-Object ProcessId, CommandLine
  ```

  Dann über mindestens fünf Sekunden CPU-Zeit und Protokollgröße vergleichen —
  **ein Lauf, dessen Ausgabe nicht wächst, arbeitet nicht**; ein bis zwei
  Sekunden ohne CPU zwischen zwei Fensterdateien sind normal. Erst ohne
  CPU-Sekunde und ohne Byte über zwanzig Sekunden ist es ein Hänger.
- **Ein BLAS-Faden je Testprozess**: Tor und `affected_tests.py --run` setzen
  `OPENBLAS_NUM_THREADS=1`, wenn der Aufrufer nichts setzt; eigene Sonden und
  Skripte starten ebenso. Sonst sagt jeder Prozess mit numpy und scipy je
  Rechenkern einen Puffer zu, an 32 Kernen 1,5 GB, und Läufe nebeneinander
  reißen die Zusagegrenze. Leistungsläufe bleiben ohne Vorgabe.
- **Im Tor eine feste Arbeiterzahl, nie `-n auto`**: Parallelität zeigt
  Speicherhunger als Korrektheitsfehler, 32 Arbeiter sterben schon beim
  Verteilen, und eine Zahl, die an der Kernzahl hängt, ist eine stille
  Variable.
- **Zweimal fahren und die Mengen vergleichen**: Ein Test, der von einem
  Vorgänger abhängt, wird parallel *manchmal* rot — zwei gleiche Läufe sind
  kein Beweis, zwei ungleiche sofort einer.
- ComfyUI läuft mit rund einem Gigabyte im Hintergrund mit — bei der Lastfrage
  mitzählen.

### Wenn ein Lauf steht: py-spy

`py-spy dump --pid N --native` liest den Stapel eines laufenden Prozesses,
ohne ihn anzufassen; erst `--native` zeigt, was hinter der Python-Grenze
wartet. `faulthandler` hilft nur einem Faden, der stürzt. py-spy liegt in der
Nutzer-Umgebung (`%APPDATA%\Python\Python313\Scripts\py-spy.exe`), **nicht**
in der `.venv` oder `constraints.txt` — es gehört nicht zum Produkt.

### Wie viele Läufe trägt eine Aussage?

Das hängt an der Basisrate ohne jede Änderung (1/10 in Ruhe bis 5/5 unter
Fremdlast): Bei 1/10 ist „0 von 10“ kein Beleg, sondern kein Widerspruch —
sagen, was die Zahl trägt; bei 5/5 ist nichts messbar. **Die Messlatte steht
vor der Messung.** Eine Rate sagt, dass etwas anders ist, nie was: **Zeigt der
Verdacht auf eine benennbare Stelle, ist Lesen billiger als Zählen.**

## Was habe ich gerade gemessen?

Man misst, was leicht zu greifen ist, nicht, was gemeint war:

| Werkzeug | misst | gemeint |
|---|---|---|
| Prozessbaum | die direkten Kinder | die ganze Kette |
| Lebendprüfung | ob `OpenProcess` ein Handle gibt | ob der Prozess läuft |
| Wächter | irgendeinen `pytest` | den gemeinten Lauf |
| sein Selbsttest | `os.getpid()` | ob der Lauf sichtbar ist |
| `git diff` | den Index | HEAD |
| Sprachprüfstand mit `set_language` ohne `install_catalog` | sechsmal Deutsch | sechs Sprachen |

**Zu wenig zu finden ist teurer als zu viel**: Es erzeugt die Gewissheit, es
sei nichts da. In jedes selbstgebaute Prüfwerkzeug gehört deshalb:

- **Zuerst zählen, wie viel gefunden wurde, und bei zu wenig scheitern** —
  `tests/test_plan_references.py` (`assert len(sections) > 100`),
  `tests/test_translations.py` (`assert gb_texte`), im Tor „Sammelgruppe: N
  passed“.
- **Ein Fall, dessen Ausgang man kennt** — sind zwei Bilder gleich groß, zeigen
  sie dasselbe (`ansicht.md`, „Was nur das Bild zeigt“).
- **Eine weitergereichte Zahl reist mit ihrem Muster** (Wortgrenze, Fälle;
  `"pytest" in CommandLine` zählt auch wartende Hüllen), und wer sie bekommt,
  prüft sie an einem bekannten Fall, bevor er darauf baut.
- **Lokal gegen lokal sagt nichts darüber, was oben liegt**: Die Reihenfolge
  einer Veröffentlichung gehört in ein Werkzeug, das den Serverstand liest
  (`upload_website.py --alte-pakete`); nach jedem Hochladen wird gegen den
  Server gemessen, von Hand — das Tor hängt nicht am Netz.

## Ein eingechecktes Artefakt überlebt seinen Erzeuger

Tests über `app/examples/*.p3d` bleiben grün, wenn `tools/make_examples.py`
nicht mehr läuft, und der läuft nur beim Paketieren. **Prüfe ich das Ergebnis
oder das, was es erzeugt — und wann läuft der Erzeuger das nächste Mal?**
Lautet die Antwort „beim nächsten Release“, gehört ein Test daneben, der ihn
fährt (hier billig: Die Bau-Funktionen stellen nur den Op-Stapel auf,
`History.apply` prüft die Kennungen). Ebenso für Bildschirmfotos,
Handbuchseiten, Lizenzmanifest und Vorschaubilder.

## Prüft dieser Test eine Zusage — oder den Ist-Zustand?

Ein Test kann einen Fehler **festschreiben**: grün, solange er da ist, rot,
sobald jemand ihn behebt.

| Form | prüft |
|---|---|
| `assert werte == {...}` | den **Ist-Zustand**: genau das und nichts sonst |
| `assert werte["a"] == x` | die **Zusage**: das hier muss stimmen |

Vor dem `==` fragen: Ist die Abwesenheit dieses Schlüssels Teil der Zusage?
Eine Obergrenze *soll* die ganze Menge prüfen; `a == b` über zwei erhobene
Mengen sind dagegen meist zwei Zusagen, von denen eine gewollt ist — **ein
Test, der einen Fehler am Behobenwerden hindert, prüft die Gewohnheit, nicht
die Zusage.** Wer eine Richtung streicht, ersetzt ihre Deckung durch eine
Zusicherung über die Sache.

## Die Gegenprobe

Ein neuer Test, der einen Fund festnagelt, wird **einmal ohne den Fix
gefahren**. Bleibt er grün, prüft er etwas anderes, als er behauptet — und
manchmal verwirft die Probe den Fix statt des Tests.

- **Am Weg vorbei**: Wer eine Oberfläche prüft, drückt, tippt und wählt; die
  Methode dahinter (`_stop_or_close()`) ist die zweite Zusicherung.
- **Ein Wert herausgezogen**: Wer ein Argument in eine Methode hebt, um es
  prüfbar zu machen, zählt die übrigen desselben Aufrufs. Und Qt verbindet
  jedes Signal, dessen Stelligkeit passt — beim `connect` zählt, was das
  Argument beim Empfänger **bedeutet**; im Zweifel ein Slot ohne Parameter.
- **Am Prüfobjekt vorbei**: Gebaut wird, was die Anwendung baut; ein selbst
  gestarteter `QThread` blieb grün, als der Dialog auf `run()` fiel.
- **An der Aussage vorbei**: `str(op_id) in tooltip` ist grün, weil „2“ auch in
  „2,40 mm“ steht — verglichen wird mit dem ganzen Satz.
- **An den Daten vorbei**: **Zwei Felder mit gleichem Wert machen jeden Test
  grün, der nur eines liest** — den Datensatz entzerren
  (`{"url": "…f=geladen.exe", "file": "benannt.exe"}`).
- **Am erfundenen Beleg vorbei**: Ein Wort, eine Zahl oder eine Datei als Beleg
  wird gegen den Bestand gegriffen, bevor es in einen Docstring kommt. Ein
  Kommentar, der eine Falle richtig benennt, ist keine Zusicherung; eine Zahl
  darin wird nachgerechnet.
- **An der Maschine vorbei**: Ein Fall, der am letzten Bit steht (Löserlauf
  am Budget, Urteil an einer Schwelle), sichert nichts über **eine** Rechnung
  zu — auf einem anderen Runner kippt sie. Er wird über Lagen geprüft, die
  eigene Rechnung und feste Muster aus `platform_noise(pattern)`: „in keiner
  Lage“ für den Schutz, „in mindestens einer“ für die Gegenprobe
  (`test_refine.py`, `GUARD_PATTERNS`).

## Ein Verbotstest über eine leere Menge ist immer grün

Der Verbotstest filtert die Verstöße aus einer Menge und sichert zu, dass
keiner bleibt. **Ist die Grundmenge leer, besteht er**, weil nichts geprüft
wurde. Wird die Menge *erhoben*, braucht sie die Zusicherung „nicht leer“;
steht sie *da*, ist die Zeile Zierat, und überflüssige Zeilen unterscheidet
bald niemand mehr von den tragenden.

| Herkunft der Menge | Beispiel | zusichern |
|---|---|---|
| Dateisystem | `UI.glob("*.py")`, `rglob` | **ja** |
| Ladevorgang | `rules.load()`, `manual.pages()`, `REGISTRY.all()` | **ja** |
| Gebaute Oberfläche | `findChildren(...)`, `panel._buttons.values()` | **ja** |
| Rechenergebnis | `result.layers`, `island_layers(result)` | **ja** |
| Konstante im Modul | `REQUIRED_LINKS`, `FIELDS` | nein |
| Literal im Test | `{"Versatz": …, "Maß": …}` | nein |
| Vereinigung mit Festwert | `{"de"} \| set(available_languages())` | nein |

- **Bei `parametrize` gehört sie in die Funktion, die die Parameter liefert**:
  Eine leere Liste sammelt null Tests (Exit 5, den das geteilte Tor als Fehler
  wertet), eine Zusicherung im Testkörper liefe nie. **Was für die
  Gesamtmenge gilt, gilt nicht für jedes Element** (eine leere `__init__.py`
  hat legitim keine Bezeichner) — die Zusicherung summiert über alle
  Parameter.
- **Obergrenzen sind der gefährlichste Fall**: Ein leeres Register (ohne
  `load_operations()`) unterschreitet jede Grenze in
  `test_interface_limits.py`. Die Zusicherung steht dort einmal als eigener
  Test.
- **Und die Gegenprobe gilt auch hier**: Grundmenge leeren, der Test muss rot
  sein, zurückstellen — automatisiert mit der Rückstellung im `finally`.

## Ein Muster, das man abfragen muss, ist ein fehlender Vertrag

Fragt eine Fixture nach mehreren Namen für dieselbe Sache (`release`,
`wait_for_*`), ist das die Notlösung. Die Lösung ist ein Name — `release()` auf
jeder Klasse mit Arbeiter — und eine Prüfung per `ast`, die ihn von jedem
verlangt, der eine `WorkerLeash` anlegt.

## Eine Automatik, die in Wahrheit Handarbeit ist, ist gefährlicher als keine

Ihr Ausbleiben fällt nicht auf, weil jemand von Hand nachhilft. Zu jeder
Automatik gehört deshalb eine Zusicherung, dass sie läuft: `core.hooksPath`
zeigt auf `.githooks`, und jede Datei darin ist ausführbar. Eingeschaltet
wird mit `git config core.hooksPath .githooks`, nicht mitten in einem Release.

## Ein Signal, das jedes Mal kommt, lässt sich halbieren

Ein deterministischer Abbruch wird über die Zahl der Tests eingegrenzt — erst
prüfen, ob er deterministisch ist, sonst rät die Suche. Gemessen wird „alles
bis N“ gegen „alles bis N−1“, nicht der Test allein. Testnamen aus
`--collect-only -q` tragen ein CR: `sed 's/\r$//'`, sonst Exit 4.

## Ein Messwerkzeug, das den Absturz nicht überlebt, misst nichts

Wer seine Treffer erst in `pytest_sessionfinish` ausgibt, liefert beim Absturz
null Zeilen — zeilenweise schreiben (`open(pfad, "w", buffering=1)`). Vorher
fragen: *Ob* etwas hilft oder *warum* es passiert? Das zweite ist oft
billiger zu messen und immer mehr wert.

## Nach einer Änderung an `app/` oder `tools/`: zwei Läufe von je drei Sekunden

Die Prüfungen, die *jede* Datei lesen, liegen außerhalb des Gebiets einer
Änderung — wer nur die Tests seines Gebiets fährt, bringt deutsche Bezeichner
ins Tor:

```text
.venv\Scripts\python.exe -m pytest tests/test_language_rules.py -q
.venv\Scripts\python.exe -m ruff check .
```

**`ruff check .` ohne Pfad** — auch eine Testdatei ist Code. Die übrigen
betroffenen Tests nennt `tools/affected_tests.py` aus dem Importgraphen, samt
Baumlesern (`rglob`, `walk_packages`) und Nennung beim Namen (`--why`,
`--split`, `--run`; beim Release `--release`).

## Eine Fremdmeldung ist ein Zeitpunkt, keine Ursache

| Meldung | behauptet | war |
|---|---|---|
| `Exit 127` | „command not found“ | Shell-Konvention über vier Windows-Codes |
| `0xc0000374` | einen bestimmten Fehler | jede Heap-Beschädigung |
| `Background writer channel closed` | einen Schreibkanal | eine volle Platte |
| `MSVC 14.0 or greater is required` | einen fehlenden Compiler | `vswhere` fand Visual Studio 18 nicht |

Zur Ursache führt die Wiederholung, nicht der Text. Eigene Meldungen sagen,
was wir mehr wissen (Regel 17): „auf `C:` sind 0 Byte frei, das Paket braucht
7,5 GB“ statt „der Download brach ab“.

## Ein Prüfwerkzeug ist auch nur Code

**Ein Werkzeug, das nichts meldet, sieht aus wie eines, das nichts findet.**
Den Zweig prüfen, den es noch nie gab (gefälschtes Protokoll je Urteil, mit
Nachweis, dass der Fall entstand), und eine konstante Zahl als Zeiger lesen:
„1 von 10“, nie null, nie zehn, ist eine Referenz, kein Streuungsproblem.

### Die Abfrage muss den Befehl noch ändern können

`abfrage && python - <<'PY'` erfüllt „erst nachsehen, dann schreiben“ nur im
Text: **Ein Aufruf fragt, ein zweiter schreibt**, dazwischen liest jemand. Und
eine Messung nach dem Testlauf misst einen anderen Baum, wenn dazwischen
geschrieben wurde — **gemessen wird ein Zeitpunkt, nie ein Baum.**

## Ein fertiger Job in einem laufenden Lauf gibt sein Protokoll heraus

`gh run view --log-failed` schweigt bis zum Ende des ganzen Laufs; einen
fertigen Job liest `gh api repos/<eigner>/<repo>/actions/jobs/<job-id>/logs`
(ohne führenden Schrägstrich, sonst macht Git Bash einen Dateipfad daraus).
Ein laufender Job antwortet 404, ein rot gewordener ist fertig. Vorher die
neueste `ruff` in einer eigenen Umgebung gegen das Projekt fahren, nicht in
der `.venv`.
