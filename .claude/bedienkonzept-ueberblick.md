# Überblick über einen langen Agentenlauf

Bedienkonzept für Claude Code, entworfen an einem echten Fall: der
Übersetzungsrunde vom 31.07. bis 01.08.2026 — 21 Commits, 289 Dateien, 16 269
eingefügte Zeilen, mehrere hundert Werkzeugaufrufe. Die Arbeit war richtig. Was
fehlte, war die Möglichkeit zuzusehen, ohne alles zu lesen.

Dieses Dokument liefert Abläufe, keine Prosa. Wo Prosa steht, begründet sie eine
Entscheidung.

---

## 1. Die Analogie, aus der alles folgt

**Eine Agentensitzung ist eine Auswertung.** Solidon hat für genau dieses
Problem schon Regeln — `.claude/rules/oberflaeche.md`, aus Bauplan §2.8 und
§15.3 — und sie übertragen sich eins zu eins:

| Solidon | Claude Code |
|---|---|
| Der Stapel wird ausgewertet | Die Sitzung läuft |
| Lange Rechnungen laufen nicht im Hauptthread | Der Nutzer bleibt eingabefähig |
| Die letzte gültige Darstellung bleibt sichtbar | Der letzte Commit bleibt der Stand |
| Fortschritt mit **Abbrechen** | Fortschritt mit **Abbrechen** |
| Befunde sammeln sich im Prüfbericht | Testlage, offene Punkte, bekannte Fehler |
| Keine Bedeutung allein über Farbe | dito |

Das ist kein Vergleich, das ist dieselbe Aufgabe. Die Wartezeit-Tabelle aus §2.8
gilt unverändert — nur die Zahlen wandern um zwei Größenordnungen:

| Dauer | Anzeige |
|---|---|
| unter 2 s | nichts |
| bis 30 s | laufende Zeile, was gerade passiert |
| darüber | Sitzungsleiste mit Fortschritt und **Abbrechen** |
| über 10 min | zusätzlich eine Schätzung, wenn eine Arbeitsliste existiert |

---

## 2. Die vier Fragen

Ein Überblick ist keine Zusammenfassung. Er beantwortet vier Fragen, jederzeit,
ohne dass jemand danach fragt:

1. **Woran wird gerade gearbeitet?** — nicht „Bash läuft", sondern
   „test_slice.py, Docstrings tauschen"
2. **Wie weit ist es?** — nur wenn es eine erklärte Arbeitsliste gibt. Sonst
   schweigen, statt zu raten.
3. **Was ist bisher herausgekommen?** — Commits, Testlage, geänderte Dateien
4. **Was ist kaputt, und war es das schon vorher?** — der Unterschied entscheidet,
   ob jemand eingreifen muss

Was in dieser Sitzung sichtbar war: nur Frage 1, und die nur als Werkzeugname.
Frage 4 habe ich viermal in Prosa beantwortet, weil sie nirgends stand.

---

## 3. Konzept A — Die Sitzungsleiste

Drei Zeilen, direkt über der Eingabezeile, immer sichtbar, scrollen nie weg.

```
┌──────────────────────────────────────────────────────────────┐
│ Übersetzungsrunde tests/            ▓▓▓▓▓▓▓░░░  7/11  ~40 min │
│ ▸ test_slice.py · Docstrings tauschen                    2:14 │
│ ✓ 4 Commits · 1926 grün · ⚠ 1 rot (schon bei Start)          │
└──────────────────────────────────────────────────────────────┘
```

**Zeile 1 — Wohin.** Titel des laufenden Kapitels. Der Balken erscheint *nur*,
wenn eine Arbeitsliste existiert; ohne sie steht dort nichts. Eine geratene
Prozentzahl ist schlimmer als keine — sie wird geglaubt.

**Zeile 2 — Was jetzt.** Das laufende Werkzeug in der Sprache der Aufgabe, nicht
in der des Werkzeugs. Rechts die Laufzeit *dieses Schritts*; springt sie über
30 s, färbt sich nichts, aber die Zahl bleibt stehen statt zu blinken.

**Zeile 3 — Was schon.** Ergebnisse, die den Lauf überleben: Commits, Testlage,
bekannte Fehler. `⚠ 1 rot (schon bei Start)` ist die wichtigste Zelle des ganzen
Entwurfs — siehe Konzept E.

**Regeln:**

- Erscheint ab 30 s Laufzeit, verschwindet nie wieder bis zum Sitzungsende.
- Keine Bedeutung allein über Farbe: `✓`, `⚠`, `▸` tragen sie mit.
- Der Balken ist Zeichen, nicht Pixel — er bleibt in jedem Terminal lesbar.
- **Kein zweites Fenster.** Drei Zeilen an einer festen Stelle sind ein
  Überblick; ein Dashboard, das man wegklicken kann, ist eine zweite Baustelle.

---

## 4. Konzept B — Kapitel

Eine Sitzung hat Abschnitte, ob sie markiert sind oder nicht. Diese hatte elf:
`app/core/scene`, `geom`, `brep+registry+agent`, `perceive+slice`, `knowledge`,
`ui+cli`, dann viermal `tests/`. Markiert war keiner.

### Ablauf: Kapitel entsteht

```
Agent wechselt das Arbeitsgebiet
  └─ setzt Kapitelmarke (Titel, Zeitstempel)
       └─ Trennlinie im Transkript
       └─ neuer Eintrag im Inhaltsverzeichnis links
       └─ voriges Kapitel klappt zu, eine Zeile bleibt stehen
```

Die zugeklappte Zeile ist das Kapitel in Kurzform:

```
▾ 3. Geometrieschicht          18 min · 23 Dateien · 1 Commit · grün
```

### Ablauf: Nutzer sucht eine Stelle

```
Nutzer klickt Kapitelzeile im Inhaltsverzeichnis
  └─ Transkript springt an den Kapitelanfang
  └─ Kapitel klappt auf

Nutzer klickt ▾ an einem Kapitel
  └─ klappt zu; Titel, Dauer, Ergebnis bleiben

Nutzer klickt „alle zu"
  └─ nur die Kapitelliste bleibt
  └─ das ist die ganze Sitzung auf einem Bildschirm
```

**Das ist der eigentliche Überblick.** Elf Zeilen statt tausend, und jede führt
zurück in die Einzelheiten. Kein neuer Zustand, keine Betriebsart — dieselbe
Ansicht, anders zusammengeklappt.

**Wann eine Marke fällt:** beim Wechsel des Arbeitsgebiets, nach einem Commit,
bei einem Fehlschlag, der die Richtung ändert. Nicht bei jedem Werkzeugaufruf.
Drei bis acht Kapitel sind eine gute Sitzung; dreißig sind ein Protokoll.

---

## 5. Konzept C — `/stand`

Ein Befehl, der die vier Fragen auf einmal beantwortet. Für den Fall, dass
jemand nach einer Stunde zurückkommt.

### Ablauf

```
Nutzer tippt /stand
  └─ keine Werkzeugaufrufe, keine Neuberechnung
  └─ liest nur, was ohnehin vorliegt: Arbeitsliste, git log, letzter Testlauf
  └─ ein Bildschirm, kein Scrollen
```

```
Sitzung · Übersetzungsrunde · läuft seit 4 h 12 min

  Erledigt      7 von 11 Paketen, zuletzt knowledge/
  Jetzt         tests/ — Geometrietests, seit 2 min
  Offen         tests/ Wege+Agent · tests/ Rest · tools/

  Commits       21, zuletzt „Die Wissensschicht spricht Deutsch"
  Änderungen    289 Dateien, +16 269 / −4 820
  Tests         1926 grün · 1 rot
  Rot seit      Sitzungsbeginn (Leistungsmessung, fremde Last)

  Fremde Hand   app/core/drawing.py, app/ui/manual_window.py
                (parallele Sitzung — nicht angefasst)
```

Der Block **Fremde Hand** ist neu und in dieser Sitzung dreimal relevant
gewesen: eine zweite Sitzung hat Dateien unter mir geändert. Ich habe es
bemerkt und umgangen, aber der Nutzer hatte keinen Blick darauf.

---

## 6. Konzept D — Der Sitzungsbericht

Am Ende, oder auf `/bericht`. Nicht das Transkript, sondern was davon bleibt.

### Ablauf

```
Sitzung endet (oder Nutzer fragt)
  └─ Bericht als eine Bildschirmseite
  └─ jede Zeile führt in die Einzelheiten zurück
  └─ nichts wird gesendet, nichts geschrieben außer auf Verlangen
```

Aufbau, absteigend nach Wichtigkeit:

1. **Was jetzt anders ist** — Commits mit ihren Meldungen, gruppiert nach Kapitel
2. **Was grün ist** — Tor-Ergebnis, Testzahl
3. **Was rot ist, und seit wann** — die Unterscheidung ist der Punkt
4. **Was offen blieb** — unerledigte Arbeitsliste, ausgelassene Pfade und warum
5. **Was auffiel** — Funde, die nicht Teil des Auftrags waren

Punkt 5 hätte in dieser Sitzung drei Einträge gehabt: die kaputte
Escape-Sequenz, die vier Regeltests riss; die unterbestimmte Skizze als offene
Konzeptfrage; die rote Leistungsmessung unter Fremdlast. Alle drei standen
verstreut in Prosa.

---

## 7. Konzept E — Bekannt-rot

Das größte Einzelärgernis dieser Sitzung. Ein Test war **von Anfang an** rot —
eine Leistungsmessung, gestört von einem parallel laufenden Spiel mit 4,4 GB.
Er blieb es 21 Commits lang. Ich habe das viermal erklärt, weil es nirgends
stand.

### Ablauf

```
Erster vollständiger Testlauf der Sitzung
  └─ Ergebnis wird zur Basislinie
  └─ was hier rot ist, gilt als „bekannt rot"

Jeder weitere Lauf
  ├─ rot in Basislinie  → ⚠ bekannt, keine Unterbrechung
  ├─ neu rot            → ✗ HALT: das war ich
  └─ war rot, jetzt grün → ✓ nebenbei repariert
```

In der Leiste:

```
✓ 1926 grün · ⚠ 1 rot (bekannt)          ← ruhig weiterarbeiten
✗ 1925 grün · 2 rot (1 NEU)              ← anhalten und ansehen
```

**Warum das zählt:** ohne die Unterscheidung ist jeder rote Lauf entweder ein
Alarm, den man ignoriert, oder eine Unterbrechung, die nicht nötig war. Beides
bringt Leuten bei, die Farbe nicht mehr zu lesen — dieselbe Erkenntnis, die in
`.claude/rules/oberflaeche.md` hinter „keine Bedeutung allein über Farbe" steht,
eine Ebene höher.

---

## 8. Konzept F — Fremde Hand

Zwei Sitzungen auf einem Arbeitsbaum sind hier der Normalfall, nicht die
Ausnahme. Das steht schon als Erfahrung im Gedächtnis dieses Projekts
(`parallele-sitzungen-solidon3d.md`): *nur eigene Pfade stagen*.

### Ablauf

```
Vor jedem Commit
  └─ git status lesen
  └─ Dateien in drei Gruppen teilen:
       eigene    → stagen
       fremde    → in Ruhe lassen, in der Commit-Meldung nennen
       unklar    → nachfragen, nicht raten

Sitzungsleiste zeigt fremde Änderungen dauerhaft:
  ✎ 2 Dateien fremde Hand
```

Die Zuordnung ist nicht zu raten, sondern zu wissen: was ich selbst geändert
habe, weiß ich. Alles andere im Baum ist fremd. In dieser Sitzung war das
Muster sogar am Diff ablesbar — eine Übersetzung ändert etwa gleich viele
Zeilen, wie sie entfernt (`27/26`); ein Umbau nicht (`125/6`).

---

## 9. Was nicht gebaut wird

- **Keine geratene Prozentzahl.** Ohne erklärte Arbeitsliste kein Balken. Eine
  Schätzung, die man nicht halten kann, kostet mehr Vertrauen, als sie an
  Beruhigung bringt.
- **Kein zweites Fenster, kein Dashboard.** Drei Zeilen an fester Stelle.
- **Keine Betriebsarten.** Kein Umschalten zwischen „Übersicht" und „Details" —
  es gibt eine Ansicht, und die klappt zusammen.
- **Kein Live-Diff.** Wer den Diff sehen will, fragt danach; ihn dauerhaft
  danebenzustellen macht aus dem Überblick eine zweite Einzelheit.
- **Keine Telemetrie.** Der Bericht ist ein Text auf dieser Maschine und bleibt
  einer.

---

## 10. Was davon heute schon geht

Ohne Änderung an Claude Code selbst, allein in `.claude/` dieses Projekts:

| Konzept | Heute umsetzbar als | Aufwand |
|---|---|---|
| B Kapitel | Kapitelmarken konsequent setzen — das Werkzeug gibt es, benutzt wurde es nicht | keiner, nur Disziplin |
| C `/stand` | Skill neben `/pruefen` und `/roadmap`, liest Arbeitsliste + `git log` + letzten Lauf | klein |
| D Bericht | Skill `/bericht`, Aufbau aus §6 | klein |
| E Bekannt-rot | Basislinie beim ersten Lauf in den Scratchpad, `/pruefen` vergleicht | mittel |
| F Fremde Hand | Regel in `AGENTS.md` plus Prüfung im `/regelcheck` vor dem Commit | klein |
| A Sitzungsleiste | braucht Claude Code selbst | — |

Fünf von sechs Konzepten sind Repo-Arbeit. Die Sitzungsleiste ist das einzige,
was ins Werkzeug gehört — und sie ist das, was den Rest zusammenhält.

---

## 11. Der Prüfstein

Ein Überblick taugt, wenn jemand nach vier Stunden Abwesenheit in **zehn
Sekunden** weiß: *läuft es, ist etwas kaputt, muss ich eingreifen.*

Diese Sitzung hätte dafür etwa hundert Zeilen Transkript gebraucht. Konzept A
und C beantworten es in einem Blick, Konzept E entscheidet die dritte Frage
allein.
