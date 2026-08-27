# Bedienkonzepte je Funktion

Stand 01.08.2026, nachrecherchiert am 19.08.2026.

Ergänzung zu `bedienkonzept-ueberblick.md`. Dort ging es um die Sitzung als
Ganzes; hier um jede Funktion einzeln, die in der täglichen Arbeit an diesem
Projekt vorkommt.

Jeder Eintrag hat denselben Aufbau: **Wozu · Auslöser · Ablauf · Was schiefging
· Regel.** Der Abschnitt *Was schiefging* ist nicht ausgedacht — er steht auf
der Sitzung vom 31.07./01.08.2026, 21 Commits, mehrere hundert Werkzeugaufrufe.
Eine Funktion ohne Beleg bekommt dort ausdrücklich „nichts, aber —".

Sortiert danach, **wer sie auslöst.** Das ist keine Verlegenheitsordnung: wer
etwas auslöst, entscheidet, wer die Rückmeldung braucht.

---

# Teil A — Was der Nutzer auslöst

## A1. Skills (`/pruefen`, `/regelcheck`, `/roadmap`, `/neue-op` …)

**Wozu** — Eine wiederkehrende Arbeitsfolge unter einem Namen, damit sie jedes
Mal gleich läuft.

**Auslöser** — `/name` in der Eingabezeile, oder der Agent erkennt die Lage.

**Ablauf**

```
Nutzer tippt /pruefen
  └─ Skill lädt seine Anweisung in den Zug
  └─ führt die vier Befehle des Tors aus
  └─ meldet zusammengefasst: grün / rot mit Stelle
       └─ rot → nennt Datei, Zeile, Regel; kein Stapelabzug
```

**Was schiefging** — `/pruefen` gibt es, und ich habe es diese Sitzung **kein
einziges Mal benutzt.** Stattdessen habe ich die vier Befehle vierzehnmal von
Hand getippt. Der Grund ist kein Versehen: ich arbeitete an Teilmengen — sieben
Testdateien, ein Paket — und wollte je Befehl das einzelne Ergebnis sehen.
`/pruefen` kann nur alles.

**Regel** — Ein Skill, der nur den vollen Lauf kann, wird beim Iterieren
umgangen und ist damit nur beim letzten Mal im Einsatz. **Jeder Skill braucht
eine schmale Form.** `/pruefen tests/test_slice.py` muss dasselbe tun wie
`/pruefen`, nur auf weniger — das `argument-hint` steht schon in der Datei, der
Ablauf nutzt es nicht.

> **Der letzte Halbsatz war schon beim Schreiben falsch.** `/pruefen` kann die
> schmale Form seit `82ffe26` (31.07.2026) — einen Tag **vor** diesem
> Dokument: „Wenn ein Argument übergeben wurde, läuft `pytest` nur darauf; die
> anderen drei Läufe bleiben vollständig", samt `$ARGUMENTS` im Befehl
> (`.claude/skills/pruefen/SKILL.md:20–27`). `git show
> bad9f86:.claude/skills/pruefen/SKILL.md` zeigt denselben Satz.
>
> Der Befund selbst bleibt richtig — die vier Befehle wurden vierzehnmal von
> Hand getippt —, aber seine Ursache ist eine andere: **nicht der Skill konnte
> es nicht, sondern niemand hat seine Version gelesen.** Damit ändert sich
> auch die Regel. Sie muss nicht lauten „jeder Skill braucht eine schmale
> Form" (heute tragen sieben von acht ein `argument-hint`, und alle sieben
> benutzen es auch im Ablauf), sondern: **Ein Skill mit schmaler Form nützt
> nichts, solange niemand weiß, dass er sie hat.** Der Hinweis gehört in die
> Rückmeldung des Skills, nicht nur in seinen Kopf.
>
> Der achte Skill, `liefern`, hat bewusst kein `argument-hint`: Er ist mit
> `disable-model-invocation: true` markiert und beendet eine Arbeitseinheit
> als Ganzes. (Nachgeprüft am 19.08.2026.)

---

## A2. Plan-Modus

**Wozu** — Erst festlegen, was getan wird, dann tun. Für alles, was mehr als
einen Commit kostet.

**Auslöser** — Nutzer schaltet um, oder der Agent bittet darum.

**Ablauf**

```
Aufgabe größer als ein Commit
  └─ Plan-Modus: nur lesen, nichts ändern
  └─ Rückfragen, wo mehrere Lesarten zu anderer Arbeit führen
  └─ Plan vorlegen → Nutzer nimmt an / ändert / verwirft
       └─ angenommen: der Plan wird die Arbeitsliste (siehe B1)
```

**Was schiefging** — Nicht benutzt, bei 21 Commits. Der Zuschnitt entstand
unterwegs: erst „app/", dann fiel auf, dass `tests/` 583 Bausteine hat, dann
`tools/`. Ein Plan hätte das vorher gesehen — ein Scan über alle drei Bereiche
kostet dreißig Sekunden.

**Regel** — Der Plan ist die Arbeitsliste, bevor sie existiert. **Wo eine
Aufgabe zählbar ist, wird vor dem ersten Schritt gezählt.** Nicht um sie zu
schätzen, sondern um ihren Zuschnitt zu kennen: 1627 Bausteine in 142 Dateien
ist eine andere Aufgabe als „übersetz mal die Kommentare".

---

## A3. Berechtigungen

**Wozu** — Was ohne Rückfrage laufen darf, steht in `settings.json`. Alles
andere fragt.

**Auslöser** — Jeder Werkzeugaufruf, der nicht auf der Liste steht.

**Ablauf**

```
Werkzeugaufruf
  ├─ auf der Freigabeliste → läuft
  └─ nicht darauf → Rückfrage mit dem echten Befehl im Wortlaut
       ├─ einmal erlauben
       ├─ dauerhaft erlauben → wandert in settings.json
       └─ ablehnen → der Agent sucht einen anderen Weg,
                     nicht denselben noch einmal
```

**Was schiefging** — Nichts blockierte, aber die Liste zeigt eine Schieflage:
freigegeben sind `pytest`, `ruff`, `mypy`, `git diff|status|log|show` — das Tor
und das Lesen. Gearbeitet habe ich mit `sed -i`, Heredocs und
`python - <<'PY'`. Die Freigabeliste deckt das Prüfen ab, nicht das Tun.

**Regel** — Die Freigabeliste beschreibt den **Rhythmus** der Arbeit, nicht nur
ihre Kontrollpunkte. Was in einer Sitzung fünfzigmal vorkommt, gehört darauf
oder ausdrücklich nicht darauf — beides ist eine Entscheidung, „noch nie
aufgefallen" ist keine.

---

## A4. Unterbrechen und Steuern

**Wozu** — Der Nutzer sieht früher als der Agent, dass etwas in die falsche
Richtung läuft.

**Auslöser** — Eingabe während der Agent arbeitet.

**Ablauf**

```
Nutzer schreibt mitten im Lauf
  └─ Nachricht erreicht den Agenten beim nächsten Zug
  └─ Agent bestätigt in einem Satz, was sich ändert
  └─ läuft weiter oder schwenkt um — nie beides stillschweigend
```

**Was schiefging** — Es kam eine Nachricht mitten im Zug („schau nochmal durch
unseren Ordner 3D Drucker …"). Sie erreichte mich, ich habe sie zur Kenntnis
genommen — und sie ist danach untergegangen, weil der laufende Auftrag noch
Stunden dauerte. Kein Fehler des Werkzeugs, aber ein Loch im Ablauf.

**Regel** — Eine Nachricht, die während eines langen Laufs kommt und **nicht
sofort** bearbeitet wird, gehört auf die Arbeitsliste, nicht ins Gedächtnis.
Sonst hängt sie an der Aufmerksamkeit statt an einer Zeile.

---

# Teil B — Was der Agent auslöst

## B1. Arbeitsliste

**Wozu** — Die Zerlegung einer großen Aufgabe, sichtbar für beide Seiten.

**Auslöser** — Aufgabe mit drei oder mehr eigenständigen Schritten.

**Ablauf**

```
Aufgabe zerfällt in Schritte
  └─ je Schritt ein Eintrag, in der Sprache der Aufgabe
  └─ genau einer ist „läuft" — nie zwei
  └─ fertig heißt: verifiziert, nicht geschrieben
       └─ rot → bleibt „läuft", neuer Eintrag für die Blockade
```

**Was schiefging** — Zwei Dinge. Erstens die Erinnerung *„The task tools haven't
been used recently"* — sie kam gut fünfzehnmal, auch mitten in einem Schritt,
an dem ich sichtbar arbeitete. Zweitens war die Liste für den Nutzer nur zu
sehen, wenn ich sie zufällig anfasste.

**Regel** — Eine Erinnerung an die Arbeitsliste läuft **auf Zustand, nicht auf
Zeit.** Auslöser ist „ein Schritt ist fertig, aber keiner ist als fertig
markiert", nicht „seit zehn Zügen nichts angefasst". Und: die Liste ist Teil
der Sitzungsleiste (Überblick §3), nicht ein Ding, das man erfragt.

---

## B2. Kapitel

**Wozu** — Eine lange Sitzung in Abschnitte teilen, die man zusammenklappen
kann.

**Auslöser** — Wechsel des Arbeitsgebiets, Commit, ein Fehlschlag, der die
Richtung ändert.

**Ablauf** — siehe Überblick §4. Kurz: Marke setzen, voriges Kapitel klappt auf
eine Zeile zusammen, das Inhaltsverzeichnis ist die Sitzung.

**Was schiefging** — Nicht benutzt. Elf natürliche Kapitel, null Marken. Das
Werkzeug lag die ganze Zeit da.

**Regel** — Eine Kapitelmarke ist die **billigste Rückmeldung überhaupt**: ein
Aufruf, und eine Stunde Transkript bekommt eine Überschrift. Der Auslöser ist
nicht Gefühl, sondern eine Liste: Gebietswechsel, Commit, Richtungswechsel.
Danach schreibt sie sich von selbst.

---

## B3. Gedächtnis

**Wozu** — Was in der nächsten Sitzung noch gilt, überlebt diese.

**Auslöser** — Eine Erkenntnis, die weder im Code noch in der Git-History steht.

**Ablauf**

```
Etwas Nicht-Offensichtliches wird gelernt
  └─ prüfen: steht das schon irgendwo? (Code, CLAUDE.md, History)
  ├─ ja  → nichts tun
  └─ nein → eine Datei, eine Tatsache, Zeile im Index
```

**Was schiefging** — Der eine vorhandene Eintrag (*parallele Sitzungen — nur
eigene Pfade stagen*) war dreimal direkt entscheidend. Geschrieben habe ich
diese Sitzung **keinen** — obwohl mindestens zwei Dinge es verdient hätten: dass
`ruff` und `mypy` eine ungültige Escape-Sequenz durchlassen, die vier Regeltests
reißt, und dass Docstrings sicherer über die AST-Position ersetzt werden als
über Textsuche.

**Regel** — Der Auslöser fürs Schreiben ist **eine überstandene Überraschung**,
nicht das Sitzungsende. Wer am Ende zurückblickt, erinnert sich an das Ergebnis,
nicht an das, was ihn kurz aufgehalten hat — und genau das war es wert.

---

## B4. Subagenten

**Wozu** — Eine abgegrenzte Teilaufgabe mit eigenem Kontext und eigener Tiefe.

**Auslöser** — Ausdrücklich vom Nutzer.

**Ablauf**

```
Nutzer nennt einen Agenten oder bittet um Delegation
  └─ Agent bekommt die Aufgabe als eigenständigen Text
       (er sieht dieses Gespräch nicht)
  └─ läuft, meldet sich zurück
  └─ der Hauptlauf gibt weiter, was zählt — nicht den Bericht
```

**Was schiefging** — Fünfzehn definierte Agenten, null Einsätze. Das ist
richtig so: die Anweisung ist eindeutig, ohne Auftrag wird nicht delegiert. Aber
`solidon3d-sprache` beschreibt exakt die Arbeit dieser Sitzung.

**Regel** — Ein Agentenroster, den nie jemand öffnet, ist eine Speisekarte ohne
Kellner. **Wenn eine Aufgabe wörtlich der Beschreibung eines Agenten
entspricht, wird das gesagt** — einmal, als Angebot, nicht als Rückfrage: „Das
ist die Arbeit von `solidon3d-sprache` — ich mache es hier inline, sag Bescheid,
wenn du es lieber delegiert hättest."

---

# Teil C — Was von selbst läuft

## C1. Hooks

**Wozu** — Regeln, die die Maschine durchsetzt, nicht die Disziplin.

**Auslöser** — Sitzungsstart, vor/nach einem Werkzeugaufruf.

**Ablauf**

```
SessionStart
  └─ Projektkontext in den Zug (Stack, Sprache, Tor)

PostToolUse nach Edit/Write
  └─ ruff check über die Datei
  ├─ sauber → nichts
  └─ Befund → als Nutzer-Rückmeldung an den Agenten
       └─ Formatierer hat die Datei geändert?
            → ausdrücklich sagen, welche Datei
```

**Was schiefging** — Der `ruff`-Hook war die nützlichste Automatik der ganzen
Sitzung: er fing `F401`- und `F821`-Fehler in dem Moment, in dem ich sie
schrieb, oft bevor der Code überhaupt lief. Zweimal aber meldete er *„PostToolUse
hook modified X after your edit (likely a formatter)"* — eine dritte Hand in der
Datei, die ich gerade bearbeitete.

**Regel** — Ein Hook, der **prüft**, ist ein Geschenk. Ein Hook, der **ändert**,
ist ein zweiter Bearbeiter und muss sagen, was er getan hat — nicht „eine Datei
wurde geändert", sondern welche Zeilen. Diese Sitzung hat `ruff format` nach
jedem Schub selbst aufgerufen, um dem zuvorzukommen; das ist die richtige
Reihenfolge und sollte die Regel sein, nicht der Trick.

---

## C2. Kontextverwaltung

**Wozu** — Ein langes Gespräch überlebt seine eigene Länge.

**Auslöser** — Automatisch, wenn der Kontext eng wird.

**Ablauf**

```
Kontext läuft voll
  └─ Zusammenfassung des Älteren, Rest bleibt wörtlich
  └─ die Arbeit läuft weiter, kein Abschluss, kein Übergabepunkt
```

**Was schiefging** — Nichts Sichtbares. Aber die Sitzung schrieb sich Puffer
selbst: die Übersetzungen lagen als JSON im Scratchpad, die Ergebnisse in
Commits. Beides überlebt jede Zusammenfassung.

**Regel** — **Was wichtig ist, gehört auf die Platte, nicht ins Gespräch.**
Zwischenstände in den Scratchpad, Ergebnisse in Commits, Erkenntnisse ins
Gedächtnis. Ein Gespräch ist ein Arbeitsspeicher, und der wird knapp — das ist
kein Fehler, das ist seine Natur.

---

## C3. Hintergrundläufe

**Wozu** — Etwas Langes läuft, während weitergearbeitet wird.

**Auslöser** — `run_in_background`, oder ein Agent im Hintergrund.

**Ablauf**

```
Langer Lauf startet im Hintergrund
  └─ Sitzungsleiste bekommt eine vierte Zeile: ⧗ was, seit wann
  └─ Arbeit läuft weiter
  └─ fertig → Meldung, ohne den laufenden Zug zu unterbrechen
```

**Was schiefging** — Nicht benutzt, und das war falsch. Der volle Testlauf
dauerte **drei Minuten** und lief mindestens sechsmal — zwanzig Minuten, in
denen nichts anderes passierte. Ein Hintergrundlauf hätte das gedeckt.

**Regel** — Ab **zwei Minuten** gehört ein Lauf in den Hintergrund, wenn sein
Ergebnis nicht sofort gebraucht wird. Beim vollen Testlauf ist das die Regel,
nicht die Ausnahme: er bestätigt, er entscheidet nichts.

> **Die drei Minuten sind 22 geworden, und der Lauf kommt am Stück nicht mehr
> durch** (gemessen am 19.08.2026): 1324 Sekunden, und am Ende steht keine
> Ergebniszeile, sondern ein `faulthandler`-Stapelabzug — der Prozess stirbt
> nativ, nachdem er über 3 GB gewachsen ist. Es ist derselbe rtree-Abriss, den
> `../konzepte/durchsicht-2026-08-16.md` festhält (Abschnitt „Baseline vor der
> Durchsicht"); dort wurde die Suite
> **portionsweise in acht Blöcken** gefahren: 4009 Tests grün.
>
> Die Zwei-Minuten-Regel wird davon nicht falsch, sondern gegenstandslos in
> die andere Richtung: **Ein Lauf, der zweiundzwanzig Minuten braucht und dann
> abstürzt, gehört nicht in den Hintergrund, sondern aufgeteilt.** Genau das
> ist seit dem 16.08. die Praxis — ohne dass es irgendwo als Regel stünde.
>
> Nebenbei verschiebt sich damit das Gewicht im Tor: Sammlung 2,9 s für 4251
> Tests, `ruff check` und `ruff format --check` zusammen 1 s über 428 Dateien,
> `mypy` 2 s über 209 Quelldateien. **Das Tor besteht zeitlich nur noch aus
> `pytest`.**

---

## C4. MCP-Server

**Wozu** — Werkzeuge von außen: Datenbanken, Dienste, Browser.

**Auslöser** — Automatisch beim Start, danach bei Verbindungswechseln.

**Ablauf**

```
Server verbindet sich
  ├─ für dieses Projekt eingerichtet → Werkzeuge stehen bereit
  └─ nicht eingerichtet → still, kein Wort
```

**Was schiefging** — Das lauteste Nichts der Sitzung. Ankündigungen über
verbindende, getrennte, wiederverbundene und anmeldepflichtige Server kamen
mindestens **sechsmal**, mit langen Listen (`amplitude`, `asana`, `bigquery`,
`pagerduty` …). Benutzt wurde **kein einziges** dieser Werkzeuge. Solidon ist
eine Desktop-Anwendung ohne Netzanbindung — keiner dieser Server wird hier je
gebraucht.

**Regel** — Ein Dienst, der für dieses Projekt nicht eingerichtet ist, meldet
sich **nicht**. Nicht beim Start, nicht beim Trennen, nicht beim
Wiederverbinden. Er wird erwähnt, wenn jemand nach etwas fragt, das er könnte —
und dann einmal. Alles andere ist Aufmerksamkeit, die von der Arbeit abgezogen
wird, ohne je etwas beizutragen.

---

# Teil D — Die Werkzeuge der Arbeit

## D1. Lesen, Ändern, Schreiben

**Wozu** — Der eigentliche Eingriff.

**Ablauf**

```
Ändern
  └─ Datei muss gelesen sein
  └─ Treffer muss eindeutig sein
  ├─ Datei hat sich seit dem Lesen geändert
  │    → sagen, wer sie geändert hat (Formatierer? andere Sitzung?)
  └─ sauber → ändern, keine Bestätigung, keine Wiederholung des Inhalts
```

**Was schiefging** — Zweimal die Meldung *„the file had been modified on disk
since you last read it"*. Beide Male war es eine parallele Sitzung. Die Meldung
sagt, **dass** sich etwas geändert hat, nicht **wer** — und genau das entscheidet,
ob man weitermacht oder anhält.

**Regel** — Bei einer geänderten Datei gehört die **Herkunft** in die Meldung:
eigener Formatierer, fremde Sitzung, Nutzer. Das Muster ist sogar am Diff
ablesbar — eine Übersetzung ändert etwa so viele Zeilen, wie sie entfernt
(`27/26`), ein Umbau nicht (`125/6`).

---

## D2. Bash und PowerShell

**Wozu** — Alles, wofür es kein eigenes Werkzeug gibt.

**Ablauf**

```
Befehl läuft
  ├─ kurz → Ausgabe vollständig
  ├─ lang → gekürzt, mit Hinweis worauf
  └─ Fehler → Ausgabe, kein Deuten ohne Beleg
```

**Was schiefging** — Zweimal ein `UnicodeEncodeError` aus `cp1252`, beide Male
beim Ausgeben deutscher und chinesischer Zeichen. Behoben mit
`PYTHONIOENCODING=utf-8` — beim zweiten Mal wusste ich es schon. Bezeichnend:
genau dieser Fehler steht als Lektion in `app/cli/main.py`, `_speak_utf8` — die
Anwendung hat ihn gelöst, das Werkzeug drumherum nicht.

**Regel** — Wo eine Umgebung eine bekannte Falle hat, gehört ihre Lösung in die
**Vorgabe**, nicht in die Erinnerung. `PYTHONIOENCODING=utf-8` gehört in die
Projekt-Einstellungen, so wie `QT_QPA_PLATFORM=offscreen` in `conftest.py`
gehört.

---

## D3. Suchen

**Wozu** — Finden, ohne alles zu lesen.

**Ablauf**

```
Suche
  └─ Treffer mit Datei und Zeile, anklickbar
  └─ zu viele → Zahl nennen, nicht alle zeigen
  └─ keine → das ist eine Antwort, kein Fehlschlag
```

**Was schiefging** — Nichts. Die eigentliche Suche dieser Sitzung war ein
selbstgeschriebenes Skript (AST plus Wortlisten, das die englischen Bausteine
zählte). Es lief vierzehnmal und war die **einzige verlässliche
Fortschrittsanzeige**: 1627 → 945 → 762 → 544 → 432 → 196 → 0.

**Regel** — Wo eine Aufgabe eine Zahl hat, wird sie gemessen und gezeigt. Diese
Zahlenreihe hätte in die Sitzungsleiste gehört, statt in vierzehn einzelnen
Bash-Ausgaben zu stehen, die niemand nebeneinanderlegt.

---

## D4. Git und Commits

**Wozu** — Der Zwischenstand, der die Sitzung überlebt.

**Ablauf**

```
Ein Thema ist fertig und grün
  └─ nur eigene Pfade stagen (fremde Hand → Überblick §8)
  └─ Meldung: eine Aussage, kein Etikett
  └─ commit
       └─ Sitzungsleiste zählt hoch
```

**Was schiefging** — Nichts, und das ist der Punkt: die 21 Commits sind das
**einzige**, woran sich diese Sitzung von außen ablesen lässt. Jede andere Spur
— Werkzeugaufrufe, Zwischenstände, Erkenntnisse — ist mit dem Transkript
verschwunden.

**Regel** — Der Commit ist der Speicherpunkt, nicht die Zusammenfassung. Wer
alle zwanzig Minuten committet, kann jederzeit aufhören; wer am Ende committet,
hat einen Fehlschlag und nichts in der Hand. **Ein Thema, ein Commit, und der
Nutzer sieht die Zahl steigen.**

---

# Zusammenfassung: was daraus folgt

| # | Regel | Wo umzusetzen | Aufwand |
|---|---|---|---|
| A1 | Jeder Skill braucht eine schmale Form | `.claude/skills/` | klein |
| A2 | Zählbares wird vor dem ersten Schritt gezählt | Haltung + `/roadmap` | keiner |
| A3 | Freigabeliste deckt den Arbeitsrhythmus | `settings.json` | klein |
| A4 | Nachricht im Lauf → auf die Arbeitsliste | Haltung | keiner |
| B1 | Erinnerung auf Zustand, nicht auf Zeit | Werkzeug | — |
| B2 | Kapitelmarke bei Gebietswechsel und Commit | Haltung | keiner |
| B3 | Gedächtnis schreibt die überstandene Überraschung | Haltung | keiner |
| B4 | Passender Agent wird genannt, nicht erfragt | Haltung | keiner |
| C1 | Ändernder Hook sagt, was er geändert hat | Werkzeug | — |
| C2 | Wichtiges auf die Platte, nicht ins Gespräch | Haltung | keiner |
| C3 | Ab zwei Minuten in den Hintergrund | Haltung | keiner |
| C4 | Nicht eingerichteter Dienst schweigt | Werkzeug | — |
| D1 | Geänderte Datei nennt die Herkunft | Werkzeug | — |
| D2 | Bekannte Falle gehört in die Vorgabe | `settings.json` | klein |
| D3 | Wo eine Aufgabe eine Zahl hat, wird sie gezeigt | Skill + Leiste | mittel |
| D4 | Ein Thema, ein Commit | Haltung | keiner |

**Zwölf von sechzehn** brauchen kein neues Werkzeug — sieben sind reine Haltung
und drei sind kleine Dateien in `.claude/`. Vier gehören ins Werkzeug selbst,
und die schwerwiegendste davon ist C4: ein Dienst, der sechsmal von sich redet
und nie gebraucht wird, kostet mehr Aufmerksamkeit als jede fehlende Anzeige.

> **Die Aufschlüsselung deckt nur zehn der zwölf.** Sieben Haltung plus drei
> kleine Dateien sind zehn; A2 („Haltung + `/roadmap`") und D3 („Skill +
> Leiste") fallen zwischen die Kategorien. Und D3 ist keine reine Repo-Arbeit:
> Die Leiste braucht laut Überblick §10 ausdrücklich Claude Code selbst.
> Streng gerechnet gehören **fünf** der sechzehn Regeln ganz oder teilweise
> ins Werkzeug, nicht vier.
>
> **Die Tabelle nennt den Ort, nicht den Stand — und `CLAUDE.md` verweist auf
> sie, als nenne sie den Stand.** Dasselbe gilt für den Überblick; dort ist es
> in §10 vermerkt. Der Stand am 19.08.2026, Zeile für Zeile gegen `.claude/`:
>
> | # | Stand |
> |---|---|
> | A1 | **war schon erfüllt, bevor die Zeile geschrieben wurde** — siehe oben |
> | A2 | nicht umgesetzt; `/roadmap` zählt nichts, es liest das Register |
> | A3 | nicht umgesetzt — die Freigabeliste steht seit `7129984` (31.07.) unverändert |
> | A4, B2, C3, D4 | Haltung, am Repository nicht prüfbar; D4 ist gelebte Praxis (678 Commits seit `bad9f86`) |
> | B1 | keine Spur |
> | B3 | **kein Gedächtnisort vorhanden** |
> | B4 | die vierzehn Agenten stehen unverändert |
> | C1 | **nicht umgesetzt — und der ändernde Hook ist der eigene:** `solidon3d_hooks.py:149` ruft `ruff("format", …)` und meldet die Formatierung nirgends |
> | C2 | in der Praxis eingelöst: `.claude/.state/` trägt heute ganze Durchsichten |
> | C4 | **faktisch erledigt, außerhalb des Repositories** — alle Erweiterungen sind abgeschaltet, das Projekt hat keine `.mcp.json` |
> | D1 | nicht umgesetzt, aber anerkannt: der Stop-Hook sagt selbst, dass er den Urheber nicht kennt (`solidon3d_hooks.py:231–235`) |
> | D2 | nicht umgesetzt — kein `env`-Block in `.claude/settings.json` |
> | D3 | nicht umgesetzt — weder `/stand` noch `/bericht` noch eine Leiste |

---

## Nachrecherchiert am 19.08.2026

Vierzehn Aussagen geprüft: **acht stimmen, drei sind überholt, zwei sind
falsch, eine ist nicht prüfbar.** Als Protokoll einer Sitzung hält das Dokument;
als Mängelliste war es an zwei Stellen schon am Tag der Niederschrift falsch.

**Der teuerste Fund ist eine Zahl, die sich versiebenfacht hat.** Der volle
Testlauf dauerte drei Minuten. Heute braucht er **22 Minuten und kommt am Stück
nicht mehr durch** — 1324 Sekunden, dann ein nativer Abriss bei über 3 GB, ohne
Ergebniszeile. Seit dem 16.08. wird die Suite in acht Blöcken gefahren (4009
Tests grün), und das steht nirgends als Regel. Die Zwei-Minuten-Schwelle aus C3
ist damit nicht falsch, sondern gegenstandslos: Ein solcher Lauf gehört nicht in
den Hintergrund, sondern aufgeteilt.

**Was schon beim Schreiben falsch war:** A1 — `/pruefen` konnte die schmale
Form einen Tag vor diesem Dokument. Der Befund („vierzehnmal von Hand getippt")
stimmt, seine Ursache nicht: nicht der Skill konnte es nicht, sondern seine
Version war ungelesen. Die Regel ändert sich dadurch. Und die Zahl der
Subagenten war nie fünfzehn, sondern vierzehn.

**Ein Widerspruch, den dieses Dokument mit dem Überblick teilt:** `CLAUDE.md`
schickt den Leser in die Schlusstabelle, um den Umsetzungsstand zu erfahren —
die Tabelle nennt aber nur den Ort und den Aufwand. Sie hat jetzt eine
Standübersicht darunter. Von sechzehn Regeln ist bis heute **keine als Regel
umgesetzt**; drei sind auf anderem Weg eingelöst worden (C2 durch
`.claude/.state/`, C4 durch abgeschaltete Erweiterungen, D4 als gelebte Praxis),
und eine war von Anfang an erfüllt.

**Eine Ironie, die die Durchsicht nebenbei fand:** C1 verlangt, ein ändernder
Hook solle sagen, was er geändert hat. Der ändernde Hook ist der eigene —
`solidon3d_hooks.py:149` formatiert mit `ruff` und meldet es nirgends.

**Zur Rechnung in der Zusammenfassung:** „sieben Haltung plus drei Dateien"
deckt zehn der zwölf. A2 und D3 fallen zwischen die Kategorien, und D3 braucht
die Sitzungsleiste — also das Werkzeug. Fünf der sechzehn gehören ganz oder
teilweise dorthin, nicht vier.

**Nicht prüfbar und deshalb offen gelassen:** alles, was das Dokument als
*Haltung* führt (A4, B2, C3, D4) — Haltung hinterlässt keine Spur im
Repository. Und die Beobachtungen über Meldungstexte des Werkzeugs: Sie stammen
aus einer echten Sitzung im Juli/August 2026 und stehen nicht in der
Dokumentation, was nichts über ihre Richtigkeit sagt. Wer sie prüfen will,
prüft sie am laufenden Werkzeug, nicht an einer Seite.
