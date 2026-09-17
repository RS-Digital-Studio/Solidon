---
name: geteilter-index-nach-fremdem-commit-veraltet
description: "Nach einem fremden Commit über privaten Index steht der geteilte .git/index noch auf dem alten HEAD und zeigt dessen ganzen Commit als gestagete Löschungen; vor jedem Commit git diff --cached --stat lesen, git reset -q heilt ohne den Arbeitsbaum; und zwischen git add und git commit staget die Parallelsitzung ihre Dateien dazwischen — im geteilten Baum mit Pathspec committen (git commit -F datei -- pfade) statt über den Index"
metadata: 
  node_type: memory
  type: project
  originSessionId: 6cc3ee18-dc46-4c89-b9d6-d1e1862ffcc1
  modified: 2026-09-17T21:12:21.832Z
---

Am 14.09.2026, Übernahme von RM-080 aus einem Worktree in `F:\3D Druck`
(vier Sitzungen gleichzeitig): Mitten in meinem `update-index`-Lauf
committete eine andere Sitzung (e4856ff → 17d4ce85) — `index.lock` mitten
im Lauf, die Hälfte der Blobs im Index, die andere nicht. Danach zeigte
`git diff --cached --stat` **sechzehn Dateien als gelöscht**, die niemand
gelöscht hatte: d1 hatte 280dbe51 über einen privaten Index
(`GIT_INDEX_FILE`) committet, der geteilte Index stand noch auf 17d4ce85, und
gegen den neuen HEAD sah ihr ganzer Commit wie eine Rücknahme aus. Ein
`git commit` ohne Pfade hätte ihn zurückgenommen.

Dazu ein verwaister `index.lock` (0 Byte, 18:34), den keine Sitzung
beanspruchte und kein Prozess hielt (`Win32_Process` ohne `git`) — bis er weg
war, kam kein `update-index` und kein `git add` mehr durch.

**Why:** Der geteilte Index ist kein Zustand, dem man trauen kann, sobald
andere über private Indizes committen; er altert still und zeigt fremde Arbeit
als eigene Löschung ([[zweite-sitzung-im-selben-baum]],
[[datei-die-vor-dem-patch-modifiziert-war-geht-nur-als-blob]]).

**Und zwischen `git add` und `git commit` liegt eine Lücke.** Am 17.09.2026
stagete ich drei Pfade, las `git diff --cached --numstat` (genau meine drei),
und der Commit danach hatte **sechs** Dateien — die Parallelsitzung hatte in
diesen Sekunden ihre eigenen gestaget. Ihre Arbeit an
`perceive/features.py` ging unter meiner Meldung nach origin, gepusht vom
post-commit-Hook, bevor ich es sah. Die Prüfung war richtig und trotzdem
wertlos: Sie galt für den Augenblick, in dem sie lief.

**How to apply:**

- **Im geteilten Baum nie über den Index committen, sondern mit Pathspec:**
  `git commit -F meldung.txt -- pfad1 pfad2`. Das nimmt genau diese Pfade aus
  dem Arbeitsbaum, ignoriert den Index und lässt fremde Staging-Stände
  unberührt — es gibt keine Lücke, in die jemand hineinschreiben kann. Der
  zweite Commit desselben Tages ging so und trug genau seine drei Dateien.
- **Vor jedem Commit `git diff --cached --stat` lesen.** Steht dort etwas,
  das nicht meines ist — vor allem Löschungen —, `git reset -q` (ohne Pfade
  setzt es nur den Index auf HEAD, der Arbeitsbaum bleibt) und den eigenen
  Index danach neu bauen. Den anderen sagen, dass ihr Index-Stand weg ist.
- **Index-Aufbau als Ganzes gegen einen HEAD:** `git rev-parse HEAD` vor dem
  ersten und nach dem letzten `update-index`; ungleich heißt: alles verwerfen
  und gegen den neuen HEAD neu bauen — ein halber Index ist keiner.
- **Gegenprobe, dass der Index genau die eigenen Zeilen trägt:**
  `git diff --cached --numstat | sort` gegen
  `git -C <worktree> diff <basis> --numstat | sort` — gleiche Zahlen je Datei,
  abweichen dürfen nur neue Dateien und die per Skript gemergten (ROADMAP,
  Kataloge), deren Zeilen man einzeln zählt.
- **Verwaister `index.lock`:** kein git-Prozess (`Get-CimInstance
  Win32_Process | Where Name -match '^git'`) und keine Sitzung, die ihn
  beansprucht → löschen; vorher fragen, nachher sagen.
- **Arbeitskopie und Index getrennt bedienen** (mein Weg, der hielt):
  Arbeitskopie per `patch -p1` mit dem Diff aus dem Worktree, ein
  abgewiesener Hunk per Anker-Skript; Index per HEAD-Blob plus demselben
  Patch in einem Temp-Ordner, `hash-object -w` und
  `update-index --cacheinfo`; Kataloge per JSON-Merge in derselben
  Sortierung wie `catalog.write_catalog` (HEAD-Katalog für den Index, die
  Arbeitskopie für den Arbeitsbaum). Ein `git add` einer geteilten Datei nimmt
  fremde Hunks mit — d1s 280dbe51 trug so meinen `app/ui/CLAUDE.md`-Absatz.
