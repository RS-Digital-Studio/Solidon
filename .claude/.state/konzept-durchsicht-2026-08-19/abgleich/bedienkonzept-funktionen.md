# Abgleich: `.claude/bedienkonzept-funktionen.md`

**Geprüft am:** 19.08.2026 · **Repository-Stand:** `b0415d6` (main, sauber)
**Dokument-Stand laut eigener Angabe:** Sitzung vom 31.07./01.08.2026, 21 Commits
**Entstanden in:** `bad9f86` — „Sechzehn Funktionen, jede mit dem Beleg, woran sie sich gerieben hat" (01.08.2026, 15:29)
**Seither unverändert:** ja — `git log -- .claude/bedienkonzept-funktionen.md` nennt nur `bad9f86`

---

## Ergebnis in einem Satz

Das Dokument ist als *Protokoll* weitgehend belastbar, aber als *Mängelliste*
an zwei Stellen schon am Tag der Niederschrift falsch gewesen (A1, B4) und an
einer Stelle inzwischen von außen erledigt (C4).

Die drei Befunde, die am meisten kosten:

1. **A1 ist falsch, und war es immer.** `/pruefen` kann die schmale Form seit
   `82ffe26` (31.07.) — einen Tag vor dem Dokument. Die Regel, die daraus
   abgeleitet wird, fordert etwas, das schon dastand.
2. **Der Testlauf dauert nicht mehr drei Minuten, sondern 22 — und kommt am
   Stück gar nicht mehr durch.** Gemessen heute: 1324 s bis zum nativen
   Abriss, ohne Ergebniszeile. Die daraus abgeleitete
   Zwei-Minuten-Regel (C3) beschreibt eine Welt, die es nicht mehr gibt.
3. **Widerspruch zwischen `CLAUDE.md` und diesem Dokument.** `CLAUDE.md:151`
   schickt den Leser in die Schlusstabelle, um den Umsetzungsstand zu erfahren
   — die Schlusstabelle sagt über den Umsetzungsstand nichts, sie sagt nur,
   *wo* etwas umzusetzen wäre. Und keine der sechzehn Regeln steht in
   `ROADMAP.md`.

Zählung: **8 stimmt · 3 überholt · 2 falsch · 1 unprüfbar** (14 interne
Behauptungen).

---

## 1. Die Belegsitzung umfasste 21 Commits

**Urteil: stimmt** (mit einer Einschränkung, die im Text fehlt)

*Beleg.* `git rev-list --count 7d52958..bad9f86` → **21**. `7d52958` ist der
zweite Übersetzungs-Schub (01.08., 09:33), `bad9f86` das Dokument selbst. Vom
ersten Schub `ce402cc` (31.07., 14:25) an gerechnet sind es 22 bzw. 23
einschließlich `ce402cc`. Die Zahl ist mit einem plausiblen Zuschnitt exakt
reproduzierbar.

*Einschränkung.* Die Datumsangabe „31.07./01.08.2026" deckt im Repository **76**
Commits ab (`git log --format=%ad --date=short | sort | uniq -c`: 20 am 31.07.,
56 am 01.08.). Wer „21 Commits" als Tagesleistung dieser beiden Tage liest,
liegt um mehr als das Dreifache daneben — es waren 21 Commits *dieser einen
Sitzung*, die parallel zu anderer Arbeit im selben Baum lief.

**Stattdessen im Konzept:** „…er steht auf der Sitzung vom 31.07./01.08.2026,
21 eigenen Commits (`ce402cc`…`bad9f86`) in einem Baum, in dem an denselben
zwei Tagen 76 Commits entstanden, mehrere hundert Werkzeugaufrufe."

---

## 2. `/pruefen` kann nur den vollen Lauf — der Ablauf nutzt das `argument-hint` nicht

**Urteil: falsch** — und zwar schon am 01.08.2026, nicht erst heute.

*Beleg.* `.claude/skills/pruefen/SKILL.md`, Zeilen 20–27:

> „Wenn ein Argument übergeben wurde, läuft `pytest` nur darauf; die anderen
> drei Läufe bleiben vollständig."
>
> ```
> .venv\Scripts\python.exe -m pytest -q $ARGUMENTS
> ```

`git log -S 'Wenn ein Argument übergeben wurde' -- .claude/skills/pruefen/SKILL.md`
nennt als einzigen Commit **`82ffe26` (31.07.2026)** — einen Tag *vor* dem
Dokument. `git show bad9f86:.claude/skills/pruefen/SKILL.md` zeigt denselben
Satz und dasselbe `$ARGUMENTS` im Ablauf. Die Behauptung „der Ablauf nutzt es
nicht" war zum Zeitpunkt des Schreibens bereits unzutreffend.

*Weiter.* Die abgeleitete Forderung „Jeder Skill braucht eine schmale Form" ist
heute im ganzen Verzeichnis erfüllt: 7 der 8 Skills tragen ein `argument-hint`
(`grep -rn "argument-hint" .claude/skills/`), und alle sieben verwenden das
Argument auch im Ablauf — `bauplan`, `neue-op`, `neuer-baustein`,
`neues-druckteil` und `roadmap` über `$ARGUMENTS` in der Überschrift,
`regelcheck` über „Ohne Argument … Mit Argument …" (Zeilen 19–20), `pruefen`
wie oben. Der achte, `liefern`, hat bewusst keins: er ist mit
`disable-model-invocation: true` markiert und beendet eine Arbeitseinheit als
Ganzes.

**Stattdessen im Konzept:** „`/pruefen` gibt es, es kann seit `82ffe26` auch die
schmale Form (`pytest` nur auf dem übergebenen Pfad, die anderen drei Läufe
vollständig) — und ich habe es diese Sitzung trotzdem kein einziges Mal
benutzt, sondern die vier Befehle vierzehnmal von Hand getippt. Der Mangel liegt
nicht am Skill, sondern daran, dass ich seine Fassung nicht gelesen habe."
Und in der Regel: „Ein Skill mit schmaler Form nützt nichts, solange niemand
weiß, dass er sie hat — der `argument-hint` gehört in die Rückmeldung des
Skills, nicht nur in seinen Kopf."

---

## 3. Fünfzehn definierte Subagenten, darunter `solidon3d-sprache`

**Urteil: falsch** in der Zahl, **stimmt** im Namen.

*Beleg.* Heute: `ls .claude/agents/ | wc -l` → **14**. Damals: `git ls-tree
--name-only bad9f86 .claude/agents/ | wc -l` → ebenfalls **14**. Alle vierzehn
stammen aus einem einzigen Commit (`82ffe26`, 31.07.); seither wurde keiner
angelegt und keiner entfernt (`git log --diff-filter=AD --name-status --
.claude/agents/`). Es waren nie fünfzehn.

Der genannte Agent existiert: `.claude/agents/solidon3d-sprache.md` — damals als
`formwerk-sprache.md`, umbenannt in `9c420bf` („Aus Formwerk wird Solidon3D, und
zwar überall", 07.08.2026). Seine Beschreibung deckt die Arbeit der Belegsitzung
tatsächlich wörtlich ab.

**Stattdessen im Konzept:** „**Vierzehn** definierte Agenten, null Einsätze."

---

## 4. Freigegeben sind pytest, ruff, mypy, git diff|status|log|show — nicht `sed -i`, Heredocs, `python - <<PY`

**Urteil: stimmt**, unverändert — die Regel A3 ist unumgesetzt.

*Beleg.* `.claude/settings.json`, `permissions.allow` (14 Einträge). Kein
`sed`, kein `bash -c`, kein Heredoc-Muster. `settings.local.json` existiert
nicht. `git log -p -- .claude/settings.json` zeigt: die Liste steht seit
`7129984` („Hooks setzen durch, was bisher nur aufgeschrieben war", 31.07.2026)
unverändert; die drei späteren Commits an der Datei (`aa73ef0`, `9c420bf`,
`ee4e3cb`, `7d1e7a6`) betreffen nur Hooks und Pfade.

*Präzisierung.* Die Aufzählung im Dokument ist unvollständig: freigegeben sind
außerdem `.venv/Scripts/python.exe -m app.cli.main:*` und
`.venv/Scripts/python.exe tools/:*`, und jede der fünf Python-Zeilen existiert
doppelt — einmal als `Bash(...)`, einmal als `PowerShell(...)`. Das ändert am
Befund nichts: freigegeben ist das Prüfen und das Lesen, nicht das Tun.

**Stattdessen im Konzept:** unverändert lassen, nur die Aufzählung ergänzen:
„…freigegeben sind `pytest`, `ruff`, `mypy`, `app.cli.main`, `tools/` und
`git diff|status|log|show`, jeweils für Bash und PowerShell — das Tor, die
Hilfsprogramme und das Lesen."

---

## 5. tests/ hat 583 englische Bausteine; insgesamt 1627 Bausteine in 142 Dateien

**Urteil: unprüfbar** im Wortlaut (das Zählskript der Sitzung liegt nicht im
Repository), **plausibel** in der Größenordnung — aber als Aussage über *heute*
wäre sie um mehr als das Doppelte daneben.

*Beleg.* Nachbau des Verfahrens (AST-Docstrings + Kommentarzeilen, deutsche und
englische Wortliste, Auszählung über `git archive` in einen Temp-Baum):

| Baum | app/ englisch | tests/ englisch | .py-Dateien |
|---|---|---|---|
| `ce402cc~1` (vor dem ersten Schub) | **1691** | 673 | app: 156, tests: 84 |
| `6092ed1` (app/ fertig, tests/ noch nicht) | 55 | **673** | 248 gesamt |
| heute `b0415d6` | 61 | 34 | **359** gesamt |

Damit wird der Zuschnitt der Zahlen lesbar: **1627 in 142 Dateien meint `app/`
allein** (Nachbau: 1691 in bis zu 156 Dateien), nicht `app/ + tests/ + tools/`;
**583 meint `tests/`** (Nachbau: 673). Die Abweichungen von 4 % und 15 % sind
der andere Wortliste geschuldet, nicht einem Fehler im Dokument.

*Nebenbei bestätigt.* A2 behauptet, „ein Scan über alle drei Bereiche kostet
dreißig Sekunden". Der Nachbau braucht heute über den **größeren** Baum
**1,5 Sekunden** (`zaehl.py` über 359 Dateien). Die Aussage ist also eher zu
vorsichtig als zu kühn — das Argument, das sie trägt, wird dadurch stärker.

*Für heute.* `app/`, `tests/` und `tools/` umfassen zusammen **359** `.py`-Dateien
und rund **12 449** Docstring- und Kommentarblöcke. Wer die Zahl 1627 heute als
Umfang der Aufgabe liest, unterschätzt sie um den Faktor 7.

**Stattdessen im Konzept:** „…dann fiel auf, dass `tests/` 583 Bausteine hat,
dann `tools/`. … 1627 Bausteine in 142 Dateien **allein unter `app/`, Stand
31.07.2026** ist eine andere Aufgabe als „übersetz mal die Kommentare"."

---

## 6. Die Zahlenreihe der Übersetzung endete bei 0

**Urteil: stimmt** — und der Zustand hält.

*Beleg.* `AGENTS.md`, Abschnitt Sprachregelung: „`app/`, `tests/` und `tools/`
sind vollständig übersetzt." `CLAUDE.md`: „seit ‚Doku nachziehen' (b2e6e28), der
Bestand ist vollständig nachgezogen." Nachzählung heute (dieselbe Heuristik wie
unter 5): **11 528 deutsche gegen 103 englische Blöcke** bei 818
unentscheidbaren — der Rest ist Rauschen der Wortliste (kurze Kommentare mit
englischen Bezeichnern darin), kein Restbestand.

**Stattdessen im Konzept:** unverändert.

---

## 7. Der volle Testlauf dauert drei Minuten

**Urteil: überholt** — und zwar so gründlich, dass die Aussage heute in die
Irre führt: der volle Lauf am Stück **kommt gar nicht mehr durch.**

*Beleg (gemessen am 19.08.2026, 21:27–21:49).*

```
.venv/Scripts/python.exe -m pytest -q
=== DAUER: 1324 Sekunden ===
```

**22 Minuten 4 Sekunden** — und am Ende steht keine Ergebniszeile, sondern ein
`faulthandler`-Stapelabzug ohne C-Stack (`<cannot get C stack on this
system>`); der Prozess stirbt nativ, nachdem er auf über 3 GB gewachsen ist.
Das ist derselbe Abriss, den `.claude/durchsicht-2026-08-16.md:12-14` bereits
festhält: „Suite portionsweise in acht Blöcken: **4009 Tests grün** … Der Lauf
am Stück stirbt weiterhin am bekannten nativen rtree-Abriss — das ist Umgebung,
nicht Code."

Zum Vergleich: die Sammlung allein (`pytest -q --co`) meldet **4251 Tests in
2,92 s**; die drei anderen Läufe des Tors sind mit 1 s (`ruff check` +
`ruff format --check`, 428 Dateien) und 2 s (`mypy`, 209 Quelldateien) heute
praktisch kostenlos. Das Tor besteht zeitlich nur noch aus `pytest`.

*Folge für die Regel.* Die Zwei-Minuten-Schwelle, die das Dokument aus den drei
Minuten ableitet, wird davon nicht falsch — sie wird gegenstandslos in die
andere Richtung. Ein Lauf, der zweiundzwanzig Minuten braucht und dann
abstürzt, gehört nicht „in den Hintergrund", sondern **aufgeteilt**: die
Durchsicht vom 16.08. fährt ihn in acht Blöcken, und das ist inzwischen die
Praxis, ohne dass es irgendwo als Regel stünde.

**Stattdessen im Konzept:** „Der volle Testlauf dauerte damals **drei Minuten**
und lief mindestens sechsmal — zwanzig Minuten, in denen nichts anderes
passierte. (Stand 19.08.2026: derselbe Lauf braucht **22 Minuten** und endet am
nativen rtree-Abriss, statt eine Zahl zu melden; gefahren wird er seit dem
16.08. in acht Blöcken.) Ein Hintergrundlauf hätte das gedeckt — heute deckt
ihn nur noch die Aufteilung."

Und die Regel C3 müsste einen zweiten Satz bekommen: „**Ab zwei Minuten in den
Hintergrund — ab zehn in Blöcke.** Ein Lauf, dessen Ergebnis nur als Ganzes
zählt und der als Ganzes nicht durchkommt, ist keine Bestätigung mehr, sondern
ein Ritual."

---

## 8. Im Gedächtnis steht genau ein Eintrag (parallele Sitzungen — nur eigene Pfade stagen)

**Urteil: überholt** — es gibt heute kein Gedächtnis, in dem er stünde; die
Erkenntnis ist stattdessen fest verdrahtet.

*Beleg.* Kein Gedächtnisverzeichnis vorhanden: weder `.claude/memories` noch
`~/.claude/memories` existiert (`find ~/.claude -maxdepth 2 -iname "*memor*"` →
leer). Die Zeichenkette „eigene Pfade" findet sich im ganzen Baum nur an drei
Stellen, und keine davon ist ein Gedächtnis:

- `.claude/bedienkonzept-ueberblick.md:241` — als Konzept F, „Fremde Hand":
  „Die Erfahrung dieses Projekts dazu passt in einen Satz: *nur eigene Pfade
  stagen*."
- `.claude/hooks/solidon3d_hooks.py:231-235` — im Stop-Hook, als ausgeführter
  Text: „Der Hook sieht nur den Zeitstempel, nicht den Urheber: stammt die
  Änderung aus einer parallel laufenden Sitzung, gehört sie nicht dir."
- `.claude/bedienkonzept-funktionen.md:203` — die geprüfte Stelle selbst.

Weder `AGENTS.md` noch `CLAUDE.md` nennt die Regel. Die Erkenntnis, die das
Dokument als „dreimal direkt entscheidend" beschreibt, hat den Weg in die
Hausordnung also nie gefunden — sie lebt in einem Hook-Text und in einem
Konzeptpapier.

**Stattdessen im Konzept:** „Der eine Eintrag, an den ich mich hielt (*parallele
Sitzungen — nur eigene Pfade stagen*), war dreimal direkt entscheidend. Ein
Gedächtnis, in dem er stünde, gibt es in diesem Projekt gar nicht — der Satz
steht im Stop-Hook (`solidon3d_hooks.py:231`) und in Überblick §8, und damit an
zwei Stellen, die niemand als Gedächtnis liest. Geschrieben habe ich diese
Sitzung **keinen** …"

---

## 9. `app/cli/main.py` enthält `_speak_utf8` als gelöste cp1252-Falle

**Urteil: stimmt**

*Beleg.* `app/cli/main.py:488` — `def _speak_utf8() -> None:`; Aufruf in
`:544`.

**Stattdessen im Konzept:** unverändert.

---

## 10. `PYTHONIOENCODING=utf-8` fehlt in den Projekt-Einstellungen

**Urteil: stimmt**, unverändert — die Regel D2 ist unumgesetzt.

*Beleg.* `grep -rn "PYTHONIOENCODING" .claude/settings.json` → kein Treffer;
die Datei hat überhaupt keinen `env`-Block (`grep -n '"env"'
.claude/settings.json` → leer). `settings.local.json` existiert nicht. Der
Vergleichsfall aus demselben Satz stimmt dagegen: `tests/conftest.py:19` setzt
`os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")`.

**Stattdessen im Konzept:** unverändert — die Zeile ist seit über zwei Wochen
richtig und wartet nur darauf, umgesetzt zu werden.

---

## 11. Die Arbeitsliste ist nur sichtbar, wenn sie angefasst wird; eine Sitzungsleiste existiert nicht

**Urteil: stimmt**

*Beleg.* `.claude/bedienkonzept-ueberblick.md` §3 („Konzept A — Die
Sitzungsleiste") beschreibt drei Zeilen über der Eingabezeile; §10 („Was davon
heute schon geht") führt sie als einziges der sechs Konzepte mit
„braucht Claude Code selbst" und Aufwand „—". Im Repository gibt es dazu keine
Spur: keine Skill-, Hook- oder Settings-Datei erwähnt sie
(`grep -rn "Sitzungsleiste" .claude/*.md AGENTS.md ROADMAP.md` trifft nur die
beiden Konzeptpapiere).

**Stattdessen im Konzept:** unverändert.

---

## 12. Verweise auf Überblick §3, §4, §8

**Urteil: stimmt** — alle drei Nummern treffen.

*Beleg.* `.claude/bedienkonzept-ueberblick.md`: `:58` „## 3. Konzept A — Die
Sitzungsleiste" (B1 verweist darauf), `:92` „## 4. Konzept B — Kapitel" (B2),
`:238` „## 8. Konzept F — Fremde Hand" (D4).

*Nebenbefund, dokumentübergreifend.* B2 schreibt „Elf natürliche Kapitel, null
Marken" und stützt sich damit auf Überblick §4 — dort steht aber „Diese hatte
elf" und die anschließende Aufzählung nennt **zehn**: `app/core/scene`, `geom`,
`brep+registry+agent`, `perceive+slice`, `knowledge`, `ui+cli`, „dann viermal
`tests/`". Der Zahlendreher sitzt im Überblick; das Funktionen-Dokument
übernimmt ihn.

**Stattdessen im Konzept:** unverändert — aber der Nebenbefund gehört beim
nächsten Anfassen des Überblicks korrigiert (dort zehn statt elf, oder die
Aufzählung um das fehlende Kapitel ergänzen).

---

## 13. Schlusstabelle: zwölf ohne neues Werkzeug, vier ins Werkzeug — implizit „noch nichts umgesetzt"

**Urteil: überholt** — und die Stelle trägt zugleich den schwersten Widerspruch
des Dokuments.

### Zeile für Zeile gegen `.claude/`

| # | Regel | laut Tabelle | Stand am 19.08.2026 | Beleg |
|---|---|---|---|---|
| A1 | Jeder Skill braucht eine schmale Form | `.claude/skills/`, klein | **war schon erfüllt, bevor die Zeile geschrieben wurde** | `pruefen/SKILL.md:20-27`; 7 von 8 Skills mit `argument-hint`; `liefern` bewusst ohne (`disable-model-invocation: true`) |
| A2 | Zählbares wird vorher gezählt | Haltung + `/roadmap` | nicht umgesetzt — `/roadmap` zählt nichts, es liest das Register | `roadmap/SKILL.md` |
| A3 | Freigabeliste deckt den Arbeitsrhythmus | `settings.json`, klein | **nicht umgesetzt**, Liste seit `7129984` (31.07.) unverändert | `.claude/settings.json` |
| A4 | Nachricht im Lauf → auf die Arbeitsliste | Haltung | nicht prüfbar am Repo (Haltung) | — |
| B1 | Erinnerung auf Zustand, nicht auf Zeit | Werkzeug | keine Repo-Spur | — |
| B2 | Kapitelmarke bei Gebietswechsel und Commit | Haltung | nicht prüfbar am Repo (Haltung); das Werkzeug dafür existiert | — |
| B3 | Gedächtnis schreibt die überstandene Überraschung | Haltung | **kein Gedächtnisort vorhanden** — siehe Befund 8 | `find ~/.claude -iname "*memor*"` leer |
| B4 | Passender Agent wird genannt, nicht erfragt | Haltung | nicht prüfbar am Repo; die 14 Agenten stehen unverändert | `.claude/agents/` |
| C1 | Ändernder Hook sagt, was er geändert hat | Werkzeug | **nicht umgesetzt — und der ändernde Hook ist der eigene** | `.claude/hooks/solidon3d_hooks.py:149` ruft `ruff("format", str(datei))` und meldet die Formatierung nirgends |
| C2 | Wichtiges auf die Platte | Haltung | in Praxis: `.claude/.state/` trägt heute ganze Durchsichten | `.claude/.state/konzept-durchsicht-2026-08-19/` |
| C3 | Ab zwei Minuten in den Hintergrund | Haltung | nicht prüfbar am Repo (Haltung) | — |
| C4 | Nicht eingerichteter Dienst schweigt | Werkzeug | **faktisch erledigt, außerhalb des Repos** | `~/.claude/settings.json`: `enabledPlugins` sind **alle** auf `false` (`anthropic-skills`, `data`, `design`, `engineering`, `finance`, `pdf-viewer`, `cowork-plugin-management`); das Projekt hat keine `.mcp.json` |
| D1 | Geänderte Datei nennt die Herkunft | Werkzeug | nicht umgesetzt, aber im Projekt anerkannt | Stop-Hook `solidon3d_hooks.py:231-235` sagt ausdrücklich, dass er den Urheber nicht kennt |
| D2 | Bekannte Falle gehört in die Vorgabe | `settings.json`, klein | **nicht umgesetzt** | kein `env`-Block in `.claude/settings.json` |
| D3 | Wo eine Aufgabe eine Zahl hat, wird sie gezeigt | Skill + Leiste, mittel | nicht umgesetzt — es gibt weder `/stand` noch `/bericht` noch eine Leiste | `ls .claude/skills/` |
| D4 | Ein Thema, ein Commit | Haltung | in Praxis gelebt: 678 Commits seit `bad9f86` | `git rev-list --count bad9f86..HEAD` |

### Der Widerspruch

`CLAUDE.md:148-151` schreibt: „Wie die Sitzung selbst bedienbar sein soll, steht
in … `.claude/bedienkonzept-funktionen.md` (sechzehn Funktionen einzeln).
**Entwurf, noch nicht Praxis — was daraus umgesetzt ist, steht dort in der
Schlusstabelle.**"

Die Schlusstabelle enthält keine Spalte zum Umsetzungsstand. Ihre beiden
Spalten heißen „Wo umzusetzen" und „Aufwand"; sie ist ein Arbeitsplan, kein
Standsbericht. Wer `CLAUDE.md` folgt, findet dort nicht, was er sucht — und
liest im günstigsten Fall „Aufwand: klein" als „ist klein geblieben".

Verschärfend: **keine der sechzehn Regeln steht in `ROADMAP.md`**
(`grep -n "Bedienkonzept\|Sitzungsleiste\|Kapitelmarke" ROADMAP.md` → kein
Treffer). Der Entwurf ist also weder umgesetzt noch als offener Punkt geführt;
er liegt seit dem 01.08. unverändert da, während drei seiner sechzehn Regeln
inzwischen erfüllt (A1), erledigt (C4) oder gegenstandslos (B3) sind.

*Randnotiz zu C4.* Von den vier im Text genannten Diensten (`amplitude`,
`asana`, `bigquery`, `pagerduty`) findet sich auf dieser Maschine nur
`amplitude` wieder (`~/.claude/mcp-needs-auth-cache.json` nennt
`data:amplitude`, `data:amplitude-eu`, `data:hex`, `engineering:notion`,
`engineering:linear`, `engineering:slack`, `engineering:atlassian`,
`engineering:datadog`, `pdf-viewer:pdf`). Die drei anderen Namen sind
entweder inzwischen verschwunden oder aus der Erinnerung geschrieben — sie
sind kein tragender Teil des Befunds, aber sie sollten nicht als Beleg
zitiert werden.

**Stattdessen im Konzept:** Der Tabelle eine dritte Spalte „Stand" geben und den
Schlussabsatz um einen Satz ergänzen: „**Stand 19.08.2026:** A1 war schon bei
der Niederschrift erfüllt, C4 hat sich außerhalb des Repositories erledigt
(alle Plugins abgeschaltet), B3 ist gegenstandslos, weil es kein
Gedächtnisverzeichnis gibt. A3, D2 und D3 sind unverändert offen und stehen in
keiner Arbeitsliste." — Und in `CLAUDE.md` müsste der Verweis lauten: „Entwurf,
noch nicht Praxis; der Umsetzungsstand steht in der Spalte *Stand* der
Schlusstabelle."

---

## 14. Innere Rechnung: sieben Haltung + drei Dateien ergeben zehn, nicht zwölf

**Urteil: stimmt** — die Rechnung des Dokuments deckt nur zehn der zwölf.

*Beleg.* Auszählung der Spalten „Wo umzusetzen" / „Aufwand" der sechzehn
Tabellenzeilen:

- **„Haltung"** allein: 7 Zeilen — A4, B2, B3, B4, C2, C3, D4
- **„klein" in `.claude/`**: 3 Zeilen — A1 (`.claude/skills/`), A3
  (`settings.json`), D2 (`settings.json`)
- **„Werkzeug" / „—"**: 4 Zeilen — B1, C1, C4, D1
- **nicht zugeordnet**: 2 Zeilen — A2 („Haltung + `/roadmap`", Aufwand keiner)
  und D3 („Skill + Leiste", mittel)

7 + 3 + 4 + 2 = 16. Der Satz „Zwölf von sechzehn brauchen kein neues Werkzeug"
ist als Subtraktion (16 − 4) richtig; die anschließende Aufschlüsselung „sieben
sind reine Haltung und drei sind kleine Dateien in `.claude/`" beschreibt aber
nur zehn davon. A2 und D3 fallen zwischen die Kategorien.

*Und D3 ist keine reine Repo-Arbeit.* „Skill + **Leiste**" nennt die
Sitzungsleiste, die laut Überblick §10 ausdrücklich „Claude Code selbst"
braucht. Streng gerechnet gehören also fünf der sechzehn Regeln ganz oder
teilweise ins Werkzeug, nicht vier.

**Stattdessen im Konzept:** „**Zwölf von sechzehn** brauchen kein neues
Werkzeug — sieben sind reine Haltung, drei sind kleine Dateien in `.claude/`,
dazu A2 (Haltung, gestützt auf `/roadmap`) und D3, dessen Skill-Hälfte im Repo
liegt und dessen Leisten-Hälfte nicht. Vier gehören ganz ins Werkzeug…"

---

## Warum das Dokument driften konnte

`ROADMAP.md` wird von `tests/test_roadmap.py` am Bestand gehalten — wer einen
Punkt abhakt, ohne das Register nachzuziehen, bekommt einen roten Lauf. Für die
beiden Bedienkonzepte gibt es nichts dergleichen: kein Test unter `tests/`
liest `.claude/bedienkonzept-*.md` (`grep -rn "bedienkonzept" tests/` → kein
Treffer; die einzige `.claude`-Erwähnung im ganzen Testbaum ist ein
Kommentarverweis in `tests/test_ui.py:3746`). Das Dokument ist damit die einzige
Unterlage des Projekts, die eine Mängelliste führt, ohne dass irgendetwas
merkt, wenn ein Mangel behoben wird — genau das ist bei A1, C4 und B3
passiert.

---

## Was am Dokument nicht altert

Die sechzehn *Regeln* selbst halten dem Abgleich stand. Keine ist durch eine
Codeänderung falsch geworden; drei sind erfüllt oder gegenstandslos, die
übrigen dreizehn beschreiben unverändert eine Lücke. Was gealtert ist, sind
ausschließlich die Zahlen (1, 5, 7), zwei Momentaufnahmen, die schon bei der
Niederschrift nicht stimmten (2, 3), und der Umsetzungsstand (13).
