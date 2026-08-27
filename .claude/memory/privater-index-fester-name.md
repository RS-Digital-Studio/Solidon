---
name: privater-index-fester-name
description: "GIT_INDEX_FILE mit $$ im Namen zeigt im nächsten Bash-Aufruf ins Leere — ein nicht existierender Index ist ein leerer, und der committet jede Datei als gelöscht."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: d52f0866-6a6b-49d3-a8c5-73c0be546ada
  modified: 2026-08-27T13:41:20.083Z
---

Ein privater Index (`GIT_INDEX_FILE`) hält fremde Arbeit aus dem eigenen
Commit heraus. Der Name dafür darf **kein `$$`** enthalten: Das ist die
Prozessnummer der Shell, und **jeder Bash-Aufruf ist eine eigene Shell mit
einer eigenen.**

Am 27.08.2026 zugeschnappt: Aufbau (`git read-tree HEAD` + `git add`) und
Prüfung liefen in einem Aufruf und stimmten — 32 Dateien, keine fremde. Der
`git commit` lief im nächsten Aufruf, `$$` war eine andere Zahl, und der
Index-Pfad zeigte auf eine Datei, die niemand angelegt hatte.

**Ein nicht existierender Index ist ein leerer.** Leer heißt „nichts ist
verfolgt", und beim Committen heißt das **„alles ist gelöscht"**: 1175
Dateien entfernt, halbe Anwendung, `.claude/rules/`, Teile der Suite — und
`.githooks/post-commit` schob es sofort nach origin.

**Woher der `$$` kam, und warum das die eigentliche Lehre ist:** Aus einem
Rat einer Nachbarsitzung, die ihn selbst nie benutzt hat — abgeleitet aus
*meinem* Hinweis, dass `$TEMP` maschinenweit ist und Ausgabedateien deshalb
die Prozessnummer tragen sollen. Für eine **Ausgabedatei** stimmt das: Sie
wird in einem Aufruf geschrieben und im selben gelesen. Ein **Index** wird in
einem Aufruf gebaut und in einem anderen benutzt. Derselbe Rat, ein anderer
Ort, und er trägt nicht mehr. *Wer einen Rat gibt, der von der eigenen Praxis
abweicht, hat einen Verdachtsfall — der Unterschied hat einen Grund, den man
benennen können muss.*

**Why:** Die Prüfung war echt und galt für einen anderen Index als der
Commit. Beide Zahlen kamen aus demselben Muster, deshalb war der Unterschied
unsichtbar — dieselbe Familie wie [[gemessene-frage-ist-nicht-die-gestellte]]
und [[messung-traegt-nur-am-ort-ihrer-messung]].

**How to apply:**

- **Fester Name mit dem Sitzungsnamen**, etwa `$TEMP/idx-de` — nie `$$`,
  nie `$RANDOM`. Der Sitzungsname löst **beides**: eindeutig gegen andere
  Sitzungen (dafür war `$$` gedacht) und stabil über Bash-Aufrufe hinweg
  (dafür ist `$$` untauglich).
- **Aufbau, Prüfung und Commit in einem einzigen Bash-Aufruf.** Über zwei
  Aufrufe verteilt ist die Umgebungsvariable schon eine andere Welt.
- **Neuen Index immer mit `git read-tree HEAD` füllen.** Ohne das ist er leer,
  auch wenn der Name stimmt. **`read-tree` ist nicht die Absicherung, für die
  man es hält:** Es schützt gegen einen *veralteten* Index, nicht gegen einen
  *fehlenden* — den legt git kommentarlos leer an, und leer heißt beim
  Committen „alles gelöscht". Es gibt dabei keine Warnung.
- **Danach `git show --stat HEAD` lesen**, nicht den Index davor. Die einzige
  Prüfung, die etwas taugt, ist die nach dem Commit
  ([[commit-o-nimmt-den-dateistand]]).
- `git commit -o -- <pfade>` verträgt **keine Optionen hinter `--`**: `-F`
  landet dort als Pfadname. Entweder Optionen davor, oder ganz ohne `-o`
  committen und den privaten Index für sich sprechen lassen.

**Die Reparatur ist ein Schritt nach vorn, kein Revert:** Index mit
`git read-tree <commit-davor>` füllen, die eigenen Pfade dazulegen, committen.
Der Arbeitsbaum ist dabei nie betroffen — die Dateien liegen unversehrt auf
der Platte, kaputt ist nur HEAD. Danach den **gemeinsamen** Index aufräumen
(`git reset HEAD -- <eigene pfade>`), sonst trägt die nächste Sitzung die
Löschungen weiter; fremdes Staging bleibt dabei unberührt
([[parallele-sitzung-im-arbeitsbaum]]).
