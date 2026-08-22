# Abgleich: `.claude/bedienkonzept-ueberblick.md`

Geprüft am 19.08.2026 gegen den Stand von `main` (b0415d6). Die Datei wurde am
01.08.2026 geschrieben (6902a04) und seither zweimal angefasst — 9c420bf
(Umbenennung Formwerk → Solidon3D) und 05392c9 (ein Verweis auf eine nicht
existierende Gedächtnisdatei entfernt). Inhaltlich ist sie also seit 18 Tagen
und rund 686 Commits unverändert.

**Zusammenfassung:** 6 × stimmt · 2 × überholt · 3 × falsch · 0 × unprüfbar.

Der Kern — die sechs Konzepte und ihre Begründung — hält. Was nicht hält, sind
drei Dinge: die Herleitung aus Bauplan §2.8 (Zahlen), die Kapitelzählung in §4
(sagt elf, listet zehn) und vor allem der Status, den `CLAUDE.md` der
Schlusstabelle §10 zuschreibt. Von den fünf als „Repo-Arbeit" ausgewiesenen
Konzepten ist bis heute **keines** gebaut.

---

## 1. „21 Commits, 289 Dateien, 16 269 eingefügte Zeilen" (Kopfabsatz, §5)

**Urteil: stimmt** (Zeilenzahlen mit Abweichung).

Beleg:

```
git log --oneline ce402cc..6902a04 | wc -l          → 21
git diff --shortstat ce402cc~1 6902a04
  → 289 files changed, 16619 insertions(+), 4808 deletions(-)
```

`ce402cc` ist „Die Verträge sprechen jetzt Deutsch — Übersetzungsrunde, erster
Schub" (31.07.2026 14:25), `6902a04` der Commit, der dieses Dokument anlegt
(01.08.2026 15:10). Commitzahl und Dateizahl treffen exakt. Die Zeilenzahlen
weichen um rund zwei Prozent ab (16 619 statt 16 269 eingefügt, 4 808 statt
4 820 entfernt) — erklärbar durch den Messzeitpunkt mitten im Lauf, mit noch
ungestagten Änderungen im Baum. Kein Handlungsbedarf, außer man will die Zahl
exakt.

Ersatzsatz, wenn korrigiert wird: „21 Commits, 289 Dateien, +16 619 / −4 808
(gemessen `ce402cc~1..6902a04`)".

---

## 2. „1926 grün · 1 rot" (§3 Zeile 3, §5-Block, §7)

**Urteil: überholt.**

Beleg:

```
.venv/Scripts/python.exe -m pytest -q --collect-only  → 4246 tests collected
```

Die Suite ist seit dem 01.08.2026 von rund 1 900 auf **4 246** Tests gewachsen;
die Zahl 1926 kommt in `ROADMAP.md` nirgends vor, die nächsten dort
festgehaltenen Stände sind 2 106 (ROADMAP.md:1668), 2 122 (:1749), 2 129
(:1800), 2 136 (:1855) und später 3 174 (Commit 9c420bf).

Und die „1 rot" trägt heute nicht mehr, sondern deutlich mehr:

```
.venv/Scripts/python.exe -m pytest -q -m performance -p no:randomly
  → 13 failed, 6 passed, 4232 deselected in 119.26s
```

Das entwertet Konzept E nicht — im Gegenteil, es macht es dringender. Aber die
Zelle `⚠ 1 rot (schon bei Start)` in §3, §5 und §7 ist eine Momentaufnahme vom
01.08.2026 und liest sich ohne Stand-Datum wie eine Aussage über heute.

Ersatzsatz: „Testlage am 01.08.2026: 1926 grün, 1 rot (Stand der Bezugssitzung;
heute sind es 4 246 Tests)." Und: dem Dokument gehört eine Kopfzeile
`**Stand:** 01.08.2026` — sie fehlt bisher ganz, was das Altern unsichtbar
macht.

---

## 3. „Diese hatte elf: `app/core/scene`, `geom`, … dann viermal `tests/`" (§4)

**Urteil: falsch — Widerspruch im Dokument.**

Der Satz behauptet elf Kapitel und zählt zehn auf: `scene`, `geom`,
`brep+registry+agent`, `perceive+slice`, `knowledge`, `ui+cli` (sechs) plus
„viermal `tests/`" (vier) = zehn.

Der `git log` der Runde nennt die fehlenden beiden:

```
ce402cc  Die Verträge sprechen jetzt Deutsch — erster Schub      (core/types)
7d52958  Auswertung, Verlauf und Projektdatei — zweiter Schub
4b5c506  Die Geometrieschicht — dritter Schub
237c532  B-Rep-Kern, Register, Agent und Backends — vierter Schub
6c4c5bc  Wahrnehmung, Schichtanalyse, Ein- und Ausgang — fünfter Schub
f9cb47f  Die Wissensschicht — sechster Schub
2db31f3  Oberfläche und Kommandozeile — siebter Schub, Runde beendet
c8b0dc3 / e60a636 / d248fc8 / a14029d / 2a23c07   tests/ (fünf Commits,
         der letzte „Der letzte Rest von tests/ und tools/")
```

Der erste Schub (`core/types` — die Verträge) fehlt in der Aufzählung, `tools/`
ebenfalls. Beide tauchen anderswo im Dokument sehr wohl auf: §5 rechnet
„7 von 11 Paketen" und führt `tools/` unter *Offen*, §3 zeigt `7/11`. Die
Gesamtzahl elf ist also richtig, nur die Liste in §4 ist eine zu kurz.

Ersatzsatz: „Diese hatte elf: `core/types`, `app/core/scene`, `geom`,
`brep+registry+agent`, `perceive+slice`, `knowledge`, `ui+cli`, dann viermal
`tests/` und zuletzt `tools/`."

---

## 4. „Kapitelmarken — das Werkzeug gibt es, benutzt wurde es nicht" (§10, Zeile B)

**Urteil: stimmt.**

Beleg: `grep -rni "kapitel" .claude/ AGENTS.md CLAUDE.md ROADMAP.md` findet
außerhalb der beiden Bedienkonzept-Dateien und des Laufzeitzustands unter
`.claude/.state/` keinen einzigen Treffer, der Kapitelmarken verlangt oder
erwähnt — die übrigen Treffer sind Handbuchkapitel (`app/core/manual.py`).
Weder `AGENTS.md` (22 Regeln), noch `CLAUDE.md`, noch ein Skill, noch eine
Gebietsregel in `.claude/rules/` fordert eine Kapitelmarke.

Das Werkzeug existiert in Claude Code (Sitzungswerkzeug `mark_chapter`). Die
Zeile ist damit weiterhin korrekt — und nach 18 Tagen bemerkenswert: „keiner,
nur Disziplin" als Aufwand, und in 686 Commits ist die Disziplin nie in eine
Vorgabe übersetzt worden. Die Schwesterdatei führt dieselbe Sache als B2
(„Kapitelmarke bei Gebietswechsel und Commit — Haltung, kein Aufwand"), also
zweimal unerledigt an zwei Stellen.

Ersatzsatz (nur falls man den Stand ausweisen will): „B Kapitel — das Werkzeug
gibt es; bis 19.08.2026 fordert keine Datei in `.claude/` eine Marke, benutzt
wurde es nicht."

---

## 5. „`/stand` existiert noch nicht, ist als Skill vorgeschlagen" (§5, §10 Zeile C)

**Urteil: stimmt.**

Beleg: `ls .claude/skills/` → `bauplan  liefern  neue-op  neuer-baustein
neues-druckteil  pruefen  regelcheck  roadmap`. Kein `stand`. Alle acht Skills
stammen aus einem einzigen Commit (82ffe26, 31.07.2026) — seither ist kein
Skill dazugekommen.

Die Bezugspunkte der Zeile stimmen: `/pruefen`
(`.claude/skills/pruefen/SKILL.md`) und `/roadmap`
(`.claude/skills/roadmap/SKILL.md`) gibt es.

---

## 6. „`/bericht` existiert noch nicht, ist als Skill vorgeschlagen" (§6, §10 Zeile D)

**Urteil: stimmt.**

Beleg: dieselbe Auflistung — kein `bericht`-Skill,
`git log --diff-filter=A --name-only -- .claude/skills/` zeigt nur die
ursprünglichen acht.

---

## 7. „Bekannt-rot ist nicht gebaut, `/pruefen` vergleicht keine Basislinie" (§7, §10 Zeile E)

**Urteil: stimmt** (mit einer Präzisierung zum Ablageort).

Beleg: `.claude/skills/pruefen/SKILL.md` kennt keinen Basislinienbegriff. Es
steht dort das Gegenteil einer Basislinie — die Beweislast beim Prüfenden:

> „es gibt keine Ausnahme, keine ‚unwichtige' Warnung und kein ‚das war vorher
> schon so', ohne dass du es nachweist."

Der Hook `.claude/hooks/solidon3d_hooks.py` merkt sich in `testlauf()` nur
einen **Zeitstempel** (`MARKE = .claude/.state/letzter-testlauf`, Zeile 181–191),
kein Ergebnis, keine Liste roter Tests.

Präzisierung: Die Zeile schlägt den Scratchpad als Ablage vor. Das Projekt hat
dafür längst einen eigenen, in `.gitignore` ausgenommenen Ort —
`.claude/.state/` (`.gitignore:63`), in dem `letzter-testlauf` und
`letzte-erinnerung` bereits liegen. Eine Basislinie gehört dorthin, nicht in
den sitzungsflüchtigen Scratchpad.

Ersatzsatz: „E Bekannt-rot — Basislinie beim ersten Lauf nach
`.claude/.state/`, wo der Hook schon `letzter-testlauf` ablegt; `/pruefen`
vergleicht. mittel"

---

## 8. „Fremde Hand ist keine Regel in `AGENTS.md` und keine Prüfung im `/regelcheck`" (§8, §10 Zeile F)

**Urteil: stimmt** — die Zeile untertreibt allerdings, was schon da ist.

Beleg für den Wortlaut: `AGENTS.md` führt genau 22 Regeln
(`grep -c "^[0-9]\+\. \*\*" AGENTS.md` → 22, letzte ist Regel 22 „Keine neue
Abhängigkeit", `AGENTS.md:75`); keine davon spricht von fremden Pfaden.
`.claude/skills/regelcheck/SKILL.md` enthält weder „fremd" noch „git status"
noch „stagen". `.claude/skills/liefern/SKILL.md` verlangt zwar `git status`
und `git diff` vor dem Schneiden der Commits (Abschnitt 2), unterscheidet aber
**nicht** zwischen eigenen und fremden Dateien — es geht dort um `.gitignore`
und Testartefakte.

Was die Zeile verschweigt: Der Stop-Hook trägt den Gedanken bereits, wörtlich:

> `.claude/hooks/solidon3d_hooks.py:233` — „Der Hook sieht nur den Zeitstempel,
> nicht den Urheber: stammt die Änderung aus einer parallel laufenden Sitzung,
> gehört sie nicht dir. Dann weder prüfen noch anfassen, sondern es beim
> Berichten erwähnen."

Und zwar seit **8e11a66** („Der Abschluss-Hook weiß nicht, wer geändert hat",
31.07.2026 01:58) — also einen Tag *vor* der Niederschrift dieses Dokuments.
Konzept F ist damit nicht bei null, sondern zu einem Drittel gebaut, und §10
weiß es nicht.

Ersatzsatz: „F Fremde Hand — der Stop-Hook warnt bereits (`solidon3d_hooks.py`,
`abschluss()`); offen sind die Regel in `AGENTS.md` und die Prüfung im
`/regelcheck` vor dem Commit. klein"

Nebenbei bestätigt: Die in §5 genannten fremden Dateien gab es und sie wurden
an diesem Tag tatsächlich von anderer Hand geändert —
`git log --since=2026-07-31 --until=2026-08-02 -- app/core/drawing.py
app/ui/manual_window.py` → `ce010e0` und `de79107` (Handbuch mit Bildern,
01.08.2026 10:26). Beide Dateien existieren heute noch.

---

## 9. „Die Wartezeit-Tabelle aus §2.8 gilt unverändert — nur die Zahlen wandern um zwei Größenordnungen" (§1)

**Urteil: falsch** (die Quelle stimmt, die Rechnung nicht).

Beleg — `3d-agent-bauplan.md:216-222`, §2.8 „Rückmeldung und Wartezeit":

```
- Unter 0,2 s: nichts anzeigen
- Bis 2 s: Mauszeiger und Statusleiste
- Darüber: Fortschritt in der Statusleiste mit Abbrechen, Oberfläche bedienbar
- Über 10 s: zusätzlich eine Schätzung, wenn möglich
```

Gleichlautend in `.claude/rules/oberflaeche.md:150-157`. `§15.3`
(`3d-agent-bauplan.md:715`) trägt „Angehaltene Kette" und damit die Zeile „Die
letzte gültige Darstellung bleibt sichtbar" — der Verweis ist korrekt.

Die Zahlen des Dokuments sind 2 s / 30 s / darüber / über 10 min. Die
Verhältnisse zum Original: 0,2 s → 2 s ist Faktor **10**, 2 s → 30 s ist Faktor
**15**, 10 s → 10 min ist Faktor **60**. Das ist eine Größenordnung, an einer
Stelle knapp zwei — nicht „zwei Größenordnungen", und vor allem kein
einheitlicher Faktor, also auch nicht „unverändert".

Ersatzsatz: „Die Wartezeit-Tabelle aus §2.8 trägt hier genauso — nur um rund
eine Größenordnung gedehnt, weil eine Sitzung in Minuten misst, was die
Auswertung in Sekunden misst."

---

## 10. „Punkt 5 hätte drei Einträge gehabt" (§6)

**Urteil: überholt** — einer stimmt, einer trägt die falsche Ursache und ist
heute erledigt, einer ist nicht auffindbar.

**a) Die kaputte Escape-Sequenz.** Stimmt. `ROADMAP.md:1475-1480`, Abschnitt
„Aus der Übersetzungsrunde": „**`ruff` und `mypy` fangen keine ungültige
Escape-Sequenz.** Beim Übersetzen von `export/writer.py` … Beide Werkzeuge
liefen grün darüber; vier Tests fielen um, weil sie die Datei mit `ast.parse`
lesen und `filterwarnings = ["error"]` aus der SyntaxWarning einen Fehler
macht." Repariert in `6092ed1`. Kleine Ungenauigkeit: das Dokument nennt sie
„vier Regeltests", die Roadmap „vier Tests", die die Datei mit `ast.parse`
lesen — es sind nicht die Regeltests im engen Sinn.

**b) Die rote Leistungsmessung „unter Fremdlast".** Der Fund existiert
(`ROADMAP.md:1449-1456`, Commit `9489ca7` „Die Orientierungssuche reißt ihr
Budget — festgehalten, nicht behoben", 01.08.2026 15:31). Aber die Ursache, die
das Dokument dreimal angibt — ein parallel laufendes Spiel mit 4,4 GB, „fremde
Last" —, wird von der Roadmap ausdrücklich verworfen:

> `ROADMAP.md:1450` — „`orient_200` braucht auf dieser Maschine 23,6 s, das
> Ziel aus §31 sind 20 s; zwei Läufe hintereinander lieferten 23606 und 23654
> ms, es ist also kein Rauschen."

Und heute ist der Punkt erledigt: `ROADMAP.md:208-210` („Nachgemessen am
14.08.2026") — „Die Orientierungssuche liegt mit 14,8 s im Ziel." Der
Vorzeigefall von Konzept E ist damit sowohl in der Ursache falsch als auch
inzwischen behoben. (Das Phänomen selbst besteht fort, nur an anderer Stelle:
`ROADMAP.md:685-691` beschreibt es für `sketch_solve_200` und `blending`, und
mein heutiger Lauf zeigt 13 rote Leistungstests.)

**c) Die unterbestimmte Skizze als offene Konzeptfrage.** Nicht auffindbar.
`grep -ni "unterbestimmt" ROADMAP.md` liefert genau einen Treffer,
`ROADMAP.md:1296`, und der ist abgehakt: „`[x]` 2D-Solver
(`core/sketch/solver.py`): … unterbestimmt zählt Freiheitsgrade im Ergebnis".
In der Übersicht „Was offen ist" (`ROADMAP.md:26-43`) steht nichts dazu. Als
offene Konzeptfrage ist der Punkt weder heute noch rückwirkend belegbar.

Ersatzsatz: „Punkt 5 hätte in dieser Sitzung zwei Einträge gehabt: die kaputte
Escape-Sequenz, die vier Tests riss (`6092ed1`); und die Orientierungssuche,
die ihr Budget aus §31 riss — festgehalten, nicht behoben (`9489ca7`, seit dem
14.08.2026 mit 14,8 s wieder im Ziel). Beide standen verstreut in Prosa."

---

## 11. Entwurfsstatus: „laut `CLAUDE.md` noch nicht Praxis, der Umsetzungsstand steht in der Schlusstabelle" (§10)

**Urteil: falsch — die Schlusstabelle sagt nicht, was `CLAUDE.md` von ihr
behauptet.**

`CLAUDE.md` schreibt über beide Bedienkonzept-Dateien: „Entwurf, noch nicht
Praxis — was daraus umgesetzt ist, steht dort in der Schlusstabelle."

§10 heißt aber „Was davon heute schon **geht**" und trägt die Spalten
*Konzept · Heute umsetzbar als · Aufwand*. Das ist ein Umsetzungs**weg** mit
Aufwandsschätzung, kein Umsetzungs**stand**. Wer der `CLAUDE.md` folgt und in
§10 nachschlägt, liest fünf Zeilen und hält sie für erledigt — tatsächlich ist
keine davon gebaut.

Zeile für Zeile gegen den heutigen Baum:

| Zeile | Behauptet | Heute im Repository | Urteil |
|---|---|---|---|
| B Kapitel | „nur Disziplin" | keine Datei in `.claude/`, `AGENTS.md` oder `CLAUDE.md` nennt Kapitelmarken | nicht umgesetzt |
| C `/stand` | Skill, klein | `.claude/skills/` = acht Skills aus 82ffe26, kein `stand` | nicht umgesetzt |
| D `/bericht` | Skill, klein | dito, kein `bericht` | nicht umgesetzt |
| E Bekannt-rot | Basislinie + `/pruefen` vergleicht | `pruefen/SKILL.md` ohne Basislinie; Hook speichert nur einen Zeitstempel (`solidon3d_hooks.py:181`) | nicht umgesetzt |
| F Fremde Hand | Regel in `AGENTS.md` + `/regelcheck` | 22 Regeln unverändert, `regelcheck` ohne Prüfung — **aber** der Stop-Hook warnt seit `8e11a66` | ein Drittel, an anderer Stelle |
| A Sitzungsleiste | braucht Claude Code | unverändert außerhalb des Repos | n. z. |

Was in `.claude/` seit dem 01.08.2026 tatsächlich dazugekommen ist, gehört zu
anderen Konzepten: die Hooks (`SessionStart`, `PreToolUse`, zwei `PostToolUse`,
`Stop`) und die Freigabeliste in `settings.json` stammen aus `7129984`
(31.07.2026), also ebenfalls von *vor* diesem Dokument. Aus dem
Bedienkonzept-Überblick selbst ist in 18 Tagen und rund 686 Commits nichts
geworden.

Ersatzsatz für §10, letzter Absatz: „Fünf von sechs Konzepten sind Repo-Arbeit;
umgesetzt ist davon (Stand 19.08.2026) keines — der einzige Teil, der trägt,
ist der Hinweis auf fremde Hand im Stop-Hook, und der stand schon vor diesem
Dokument dort. Die Sitzungsleiste ist das einzige, was ins Werkzeug gehört —
und sie ist das, was den Rest zusammenhält."

Zusätzlich: `CLAUDE.md` sollte entweder umformuliert werden („die Schlusstabelle
nennt den Weg, nicht den Stand") oder §10 eine vierte Spalte *Stand* bekommen.

---

## Was sonst auffiel, ohne Behauptung zu sein

- **Kein Stand-Datum.** Das Dokument nennt Zahlen (1926 grün, 21 Commits, 289
  Dateien) ohne Datum im Kopf. Das einzige Datum steht im Fließtext
  („Übersetzungsrunde vom 31.07. bis 01.08.2026"). Eine Kopfzeile
  `**Stand:** 01.08.2026 · Bezugssitzung: Übersetzungsrunde` würde alle
  Zahlenbefunde oben entschärfen, ohne eine einzige zu ändern.
- **Die Schwesterdatei doppelt sich.** `.claude/bedienkonzept-funktionen.md`
  führt B2 („Kapitelmarke bei Gebietswechsel und Commit"), D3 („Wo eine Aufgabe
  eine Zahl hat, wird sie gezeigt — Skill + Leiste") und D4 als eigene Punkte.
  Zwei Dokumente führen dieselben unerledigten Punkte in zwei Tabellen; wer sie
  abarbeitet, muss beide nachziehen.
- **A3 der Schwesterdatei ist erledigt.** `settings.json` trägt heute eine
  Freigabeliste über pytest/ruff/mypy/CLI/tools und vier Git-Lesebefehle. Das
  betrifft nicht diese Datei, zeigt aber, dass Tabellenzeilen hier durchaus
  altern.
