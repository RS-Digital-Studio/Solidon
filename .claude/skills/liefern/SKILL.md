---
name: liefern
description: >
  Schließt eine Arbeitseinheit ab: vollständiges Tor laufen lassen, Änderungen in
  logische Einheiten aufteilen und mit aussagekräftigen deutschen Meldungen
  committen. Nur auf ausdrückliche Anweisung.
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob
---

# Liefern

## 1. Tor

Erst `/pruefen`. Ist etwas rot, wird nicht committet — dann ist die Behebung
die Aufgabe, nicht der Commit. Melde den roten Lauf und halte an.

## 2. Aufteilen

`git status` und `git diff` lesen und die Änderungen in **logische Einheiten**
schneiden: ein Thema, ein Commit. Mehrere Themen werden mehrere Commits, in
einer Reihenfolge, in der jeder für sich Sinn ergibt. Keine Mega-Commits über
alles, keine Mini-Commits je Datei.

Nicht mitcommitten: `3D Drucker/` (steht in `.gitignore`), Messdaten,
Testartefakte, `.venv`. Prüfe vor dem `git add`, was tatsächlich hineinläuft —
ein `git add .` ohne Blick ist die häufigste Ursache für versehentliche
Dateien im Repository.

## 3. Meldung

Deutsch, mit echten Umlauten, im Ton dieses Projekts: eine **Aussage**, keine
Etikettierung. So klingen die bisherigen:

> Hohle Querschnitte kamen als nichts zurück
> Ein echtes Modell als Prüfstein — vier Funde
> Angeklickte Fläche setzt die Operation an, und Operationen sind änderbar

Kein `feat:`, kein `fix:`, kein Präfix. Der Betreff sagt, was jetzt anders ist.
Wenn es einen Grund gibt, den man später sucht, steht er im Rumpf — was war,
warum es falsch war, was jetzt gilt. Am Ende:

```
Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

## 4. Danach

Nicht pushen, außer es wurde ausdrücklich verlangt. Melde am Ende: welche
Commits entstanden sind, was bewusst uncommittet blieb und warum — und ob
`ROADMAP.md` fortzuschreiben ist, weil ein Punkt erledigt oder ein neuer Fund
aufgetaucht ist.

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

**Und danach wird nachgesehen, nicht angenommen.** Der Satz oben — „ab dem
nächsten Commit wieder" — ist am 28.08.2026 schärfer geworden, als zwei
Sitzungen ihn unabhängig voneinander erlebten: Er altert nicht erst durch die
*fremden* Commits, sondern durch die **eigenen**, und zwar sofort. Eine Sitzung
legte zwei private Commits hintereinander und fand hinterher 14 Dateien mit
**548 Löschungen** gegenüber `HEAD` im gemeinsamen Index — eine Rücknahme genau
der Arbeit, die eine Minute zuvor gelandet war. Die andere Sitzung hatte
dieselbe Lage nach ihrem einen Commit und warnte; ohne diese Warnung hätte
niemand hingesehen.

Das sichtbare Zeichen ist `MM` in `git status --short`: Der Index unterscheidet
sich von `HEAD` **und** der Arbeitsbaum vom Index. Die Kontrolle ist eine Zeile,
und sie muss nichts ausgeben:

```
git diff --cached --stat
```

Bleibt sie leer, ist der Index auf `HEAD`. Kommt etwas, ist noch nicht
aufgeräumt — dann `git reset` (oder `git add` auf die eigenen Pfade, wenn der
Arbeitsbaum bereits dem Commit entspricht) und **erneut** nachsehen. Sich auf
den Vollzug zu verlassen ist hier besonders teuer: Der `post-commit`-Hook pusht,
und ein Revert von 548 Zeilen ist auf den anderen Maschinen in derselben Minute.

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

### `-o` nimmt den Dateistand, nicht deine Hunks

**Der private Index schützt gemeinsame Dateien nicht.** Er hält fremde
**Dateien** heraus — nicht den fremden Stand einer **gemeinsamen**. Das gehört
ausdrücklich hierher, weil er sonst in falscher Sicherheit wiegt: `git commit
-o -- <pfad>` committet die Datei, wie sie im Baum liegt, samt allem, was eine
andere Sitzung darin ungespeichert stehen hat. Genauer: `git
commit -o -- <pfad>` committet die Datei, wie sie im Baum liegt, samt allem,
was eine andere Sitzung darin ungespeichert stehen hat.

Am 26.08.2026 in **beide** Richtungen zugeschnappt, innerhalb einer Stunde:

| Commit | nahm mit |
|---|---|
| `bc92469a` (OpenSCAD-Ausbau) | 145 Zeilen `_CHOICE_NOTES` aus `labels.py`, die 43 gerade schrieb |
| `2b48f288` (Ausdrucksfeld) | den `FINDING_ACTIONS`-Eintrag in `panels.py`, den ce gerade geschrieben hatte |

Kein inhaltlicher Schaden — HEAD war beide Male in sich stimmig. Der Schaden
ist die **Zurechnung**: Wer später fragt, warum eine Tabelle mit 67 Sätzen im
OpenSCAD-Commit steht, findet keine Antwort. Und die Folge kann teurer sein als
die Ursache: Mit den 67 neuen `tr()`-Quellen war `origin/main` rot, bis die
Kataloge nachkamen — ein Fenster, das der Urheber der Kataloge nicht geöffnet
hatte.

#### Und die Rettung, die man dagegen baut, wirkt mit `-o` nicht

Der naheliegende Ausweg ist, den Stand selbst zu bauen: die Datei aus `HEAD`
holen, die eigene Zeile hineinsetzen, mit `git hash-object -w` einen Blob
schreiben und ihn mit `git update-index --cacheinfo` in den privaten Index
legen. Das ist richtig gedacht und **wirkungslos, solange `-o` dabeisteht**:
`--only` heißt „nimm den aktuellen Stand genau dieser Pfade", und der aktuelle
Stand ist die Datei auf der Platte. Der hineingelegte Blob wird überschrieben,
bevor er etwas nützt.

Am 27.08.2026 dreimal hintereinander so gemacht, jedes Mal mit gebautem Blob,
jedes Mal ging die fremde Zeile mit:

    git show b304f04a --numstat -- app/i18n/locales/it.json
    1  1                    <- angesagt war 0/1
    git show aaad3d94 --numstat -- .claude/memory/MEMORY.md
    2  0                    <- angesagt war 1/0

**Und die Kontrolle davor konnte es nicht sehen, weil sie das Falsche maß.**
`git diff --cached HEAD --numstat` lief jedes Mal und nannte jedes Mal genau
die angesagte Zahl. Sie stimmte auch — **für den Index.** Committet wurde der
Baum. Dieselbe Denkfigur wie zwei Abschnitte weiter unten, nur eine Ebene
tiefer: Eine Prüfung, die gegen die eigene Annahme läuft, bestätigt sie.

Zwei Sätze, die daraus folgen:

* **Blob und `-o` schließen sich aus.** Wer den Index gezielt bestückt,
  committet **ohne** `-o` — nach `git read-tree HEAD` steht darin genau HEAD
  plus die eigene Änderung, und `git commit` nimmt den Index als Baum. `-o`
  ist die Krücke für den Fall, dass man *keinen* privaten Index hat.
* **Die einzige Prüfung, die etwas taugt, ist die nach dem Commit:**
  `git show <commit> --numstat`. Alles davor prüft eine Absicht, nicht ein
  Ergebnis.

#### Und ein Index, den es nicht gibt, löscht alles

Der teuerste Fall dieser Familie, am 27.08.2026: Ein Commit auf `origin/main`
löschte **1175 Dateien** — halbe Anwendung, `.claude/rules/`, Teile der Suite.
Er stand zwei Minuten, dann war er repariert.

Die Ursache ist eine Zeile, die richtig aussieht:

```bash
export GIT_INDEX_FILE="$PWD/.git/index-$$"   # NIE
```

**Jeder Bash-Aufruf ist eine eigene Shell mit eigener Prozessnummer.** Aufbau
und Prüfung liefen in einem Aufruf und stimmten — 32 Dateien, keine fremde.
Der Commit lief im nächsten und zeigte auf einen Namen, den niemand angelegt
hatte. **Ein nicht existierender Index ist ein leerer**, ein leerer heißt
„nichts ist verfolgt", und das heißt beim Committen „alles ist gelöscht".

Die Prüfung war echt und galt für einen anderen Index als der Commit — genau
das Muster aus „Was habe ich gerade gemessen?", nur mit dem größten möglichen
Preis.

Zwei Regeln, und die zweite ist die, die trägt:

* **Fester Name, kein `$$`.** `index-27`, `index-d1` — irgendetwas, das über
  Aufrufe hinweg dasselbe bedeutet.
* **Aufbau, Prüfung und Commit in einem einzigen Aufruf.** Wer sie auf zwei
  verteilt, hat zwischen ihnen eine Shell-Grenze, und über die reist keine
  Umgebungsvariable. Muss es doch getrennt sein, ist die einzige gültige
  Kontrolle `git show --stat HEAD` **danach**.

**Der Schaden war klein, weil der Arbeitsbaum ihn nicht mitmacht.** Die
Dateien lagen die ganze Zeit unversehrt auf der Platte; kaputt war allein
HEAD. Wer in diesen zwei Minuten gepullt hätte, hätte sie verloren — für alle
anderen war nichts zu tun. Das ist kein Trost, sondern der Grund, warum ein
`git log --oneline -3` nach einer fremden Warnung genügt: Steht der
Löschcommit ohne seine Reparatur darüber, fehlt die halbe Anwendung.

**Der Handgriff dagegen kostet fünf Sekunden, und er hat drei Glieder:**

1. **Die eigene Zahl ansagen, bevor man hinsieht** — „ich lösche zwei Zeilen,
   füge keine ein". Dann `git diff HEAD --numstat -- <pfade>` dagegen halten.
2. `git status --porcelain | grep "^ D"` — **gelöschte Dateien**.
3. `git status --porcelain | grep "^??"` auf den eigenen Pfaden — **neue
   Dateien**.

Die Reihenfolge im ersten Glied ist der ganze Punkt. Wer erst die Zahlen liest
und danach überlegt, ob sie passen, nickt den Istwert ab; das ist dieselbe
Figur wie der Sollwert aus dem Prüfling. Bei zwei gelöschten Zeilen schreit
„145 insertions" schon beim Ansagen — dafür braucht es den Diff nicht einmal.

**Die Glieder 2 und 3 sind da, weil `--numstat` blind ist für alles, was nicht
im Index steht.** `-o` nimmt den Stand **verfolgter** Dateien; eine gelöschte
braucht `git add -u`, eine neue `git add`, und beide tauchen ohne das in
keiner Zahl auf. Am 26.08.2026 beide Seiten an einem Tag:

- Der OpenSCAD-Ausbau löschte `app/core/backends/openscad.py` und
  `tests/test_openscad.py`. Die zweite stand in keiner Pfadliste — die Datei
  blieb auf origin stehen, ihr Import griff nach dem entfernten Modul, und
  **jeder CI-Lauf starb schon beim Einsammeln**. Der Paketbau hängt an der
  Suite, also blockierte es den Release.
- Auf der Neu-Seite dasselbe mit sechzig Handbuchbildern.

**Und der Grund, warum kein lokaler Lauf dagegen sichert:** Der eigene
Arbeitsbaum trägt die Löschung ja. Dort ist alles grün, und zwar zu Recht. Die
einzige Stelle, an der es auffällt, ist ein Klon ohne diesen Baum — die CI.
Deshalb sichert nur die Ansage, nicht das Fahren.

Und das ist der eigentliche Punkt: Die Zahl **stand da**. Der Diff-Stat vor dem
Commit nannte `app/ui/labels.py | 149 ++++-`, und gelesen wurde die
Dateiliste — welche Dateien mitgehen —, nicht die Spalte daneben. Dieselbe
Figur wie überall in dieser Datei: Man misst, was leicht zu greifen ist, und
nicht, was gemeint war.

**Und wenn es doch passiert ist: Die History bleibt stehen.** Ein Rewrite
kostet mehr, als er heilt. Drei Schritte, in dieser Reihenfolge:

1. **Zuerst prüfen, ob eine *halbe* Einheit hinausgeritten ist** — das ist das
   Dringende, nicht die Zurechnung. Am 26.08.2026 ging die `_CHOICE_NOTES`-
   Tabelle mit 67 neuen `tr()`-Quellen hinaus, ihre Kataloge blieben liegen:
   `origin/main` war rot, bis sie nachkamen, und der Urheber der Kataloge hatte
   das Fenster nicht geöffnet. Bei einem früheren Fall (`e65f1539`) blieb
   `loading.py` zurück und brach fremde Klone. **Die fehlende Hälfte schlägt
   die falsche Zurechnung an Dringlichkeit.**
2. **Den Besitzer sofort benachrichtigen** — er weiß am schnellsten, was zu
   seiner Einheit noch fehlt.
3. **Die Zurechnung im eigenen Folge-Commit geradeziehen**, im Meldungstext.
   Wer später fragt, warum eine Tabelle mit 67 Sätzen im OpenSCAD-Commit steht,
   findet die Antwort dann eine Stelle weiter.

**Wo mehrere an derselben Datei schreiben, hilft nur Reihenfolge statt
Gleichzeitigkeit** — sagen, wann man hineingeht, melden, wenn man heraus ist.
Ein eigener Arbeitsbaum (`claude --worktree <name>`) ist die vollständige
Antwort; er kostet aber jedes Mal einen Umzug.

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
