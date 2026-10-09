---
name: liefern
description: >
  Schließt eine fertige, geprüfte Arbeitseinheit ab: eigene Pfade abgrenzen,
  mit deutscher Meldung committen und pushen — ein Commitauftrag schließt den
  Push ein. Ist die Gegenstelle weiter, wird per Merge zusammengeführt, nie per
  Rebase. Nach grünem Tor und behobenem Review ohne Rückfrage.
argument-hint: "[optional: Thema oder Pfade der Einheit; „nicht pushen“]"
allowed-tools: Bash, Read, Write, Grep, Glob
---

# Liefern

## Auftrag

**Commit heißt Commit und Push.** Grünes Tor und behobenes Review sind die
Freigabe (Entscheidung Robert) — danach wird ohne Rückfrage geliefert, und der
Push gehört ohne Rückfrage dazu; nur ein
ausdrückliches „nicht pushen“ von Robert hält den Commit lokal — dann für genau
diesen Aufruf `SOLIDON_KEIN_PUSH=1`. Holen und Zusammenführen gehören dazu,
wenn der Push daran scheitert. Tag, Release und Force-Push sind eigene Aufträge.

Vor einem Merge oder Commit auf main ist das Entwicklungstor nach `/pruefen` grün; auf
einem Paket- oder Fixzweig genügen die betroffenen Tests, ruff, format und
mypy (Entscheidung Robert). Ein grüner Nachweis über
denselben Stand muss nicht wiederholt werden; was sich seither geändert hat,
wird geprüft. Ein roter oder abgebrochener Lauf wird mit Ursache gemeldet und
nicht committet.

**Vor dem Commit steht ein Review** über genau den Stand, der hinausgeht
(Entscheidung Robert: vor jedem Push nach main, immer, auch für Unterlagen
und für Fixes aus einem früheren Review) — Agent `solidon3d-review` über den
Prüfbaum (ein Worktree auf HEAD mit genau den eigenen Änderungen) oder, nach
Schritt 5 unten, über den vorgemerkten Index (`git diff --cached`); ohne
Angabe läse er im Hauptbaum alle fremden Änderungen mit. Jeder Fund wird
behoben oder mit Beleg als kein Fehler festgehalten; ein Fix ändert den Stand,
also danach die betroffenen Tests. Eine Nachprüfung als zweites Review gibt es
nur, wenn das erste mehrere mittlere oder schwere Befunde hatte, und danach
keine weitere Runde (Entscheidung Robert). Mehrere Punkte, die zusammen
hinausgehen, teilen sich ein Review. Weil `post-commit` pusht, ist das Review
vor dem Commit das Review vor dem Push.

**Nach dem Push nach main laufen die betroffenen Fenster- und Slicertests auf
Linux und macOS, auf Zweigen nie** (Entscheidung Robert, `.claude/rules/tests.md`,
CI-09):

1. Eine neue oder geänderte Oberfläche bringt ihren Fenstertest mit, eine
   Änderung an Slicerübergabe, Profilen, Druckerwahl, Druckzeit oder
   Slicererkennung ihren Test mit `installed_slicer` und
   `@pytest.mark.slicer(<programm>)`.
2. Nach dem Push nennt `.venv\Scripts\python.exe tools/ci_selection.py --diff
   <main vorher>...origin/main` beide Listen; die liefernde Sitzung startet
   `fenster-auswahl.yml` und `slicer-auswahl.yml` mit `--ref main`, bis der
   Push sie selbst auslöst (RM-344).
3. Ein roter Lauf wird auf main vorwärts behoben, nicht übergangen. Meldet das
   Werkzeug keinen Fenster- und keinen Slicertest, entfällt der Schritt. Die
   Laufnummern gehören in den Bericht.

**Vor dem Merge nach main steht der Kundenpunkt im Changelog** (Entscheidung
Robert, `.claude/rules/auslieferung.md`): Merkt ein Kunde, was die Einheit
ändert, trägt der Zweig ihren Punkt als Teil der Einheit, also vor Tor und
Review, in den offenen Abschnitt aller sechs `changelog/<sprache>.md` ein,
geprüft wie dort beschrieben. Unterlagen, Tests
und Werkzeuge ohne Wirkung beim Kunden brauchen keinen.

## Die Einheit abgrenzen

Andere Sitzungen arbeiten im selben Baum. Geliefert wird nur, was zu dieser
Einheit gehört.

1. `git status --short`, dann je Datei `git diff HEAD -- <pfad>`: Welche
   Änderungen sind die eigenen? Einen laufenden Merge, Rebase oder Cherry-pick
   nicht anfassen.
2. Ein Thema ergibt einen Commit; mehrere Themen, mehrere Commits.
3. Nur die eigenen Pfade vormerken, einzeln genannt: `git add -- <pfad> …`.
   Neue und gelöschte Dateien bewusst aufnehmen. Kein `git add .`, kein
   `git commit -a`, kein Stash oder Reset über fremde Arbeit.
4. Trägt eine eigene Datei auch fremde Hunks, nur die eigenen vormerken: den
   Patch aus `git diff -- <datei>` auf die eigenen Hunks kürzen, mit
   `git apply --cached` aufnehmen und `git diff --cached -- <datei>` lesen.
   Lässt sich das nicht sauber trennen, die Datei zurückhalten und im Bericht
   nennen.
5. **Vor dem Commit:** `git diff --cached --name-only` nennt genau die eigenen
   Pfade, `git diff --cached --stat` die erwarteten Zeilen. Steht ein fremder
   Pfad im Index, nicht committen — er gehört einer anderen Sitzung; klären
   statt zurücksetzen.

Geliefert wird mit einem gewöhnlichen Commit über den Index — kein privater
Index (`GIT_INDEX_FILE`), kein `git commit -o`.

## Meldung und Commit

Die Meldung ist deutsch, mit echten Umlauten, und sagt, was jetzt stimmt
(Ton wie in `CLAUDE.md`). Der Rumpf nennt den nötigen Grund; am Ende steht der
tatsächliche Mitautor als `Co-Authored-By:` — das verwendete Claude-Modell mit
`noreply@anthropic.com` oder `Codex <noreply@openai.com>`.

Die Meldung mit dem Write-Werkzeug als UTF-8-Datei schreiben und mit
`git commit -F <datei>` übergeben — nicht über `-m`, `echo` oder ein Heredoc:
Umlaute und typografische Anführungszeichen überstehen die Shell nicht
zuverlässig. Fehlt auf der Maschine die Git-Identität (Exit 128), den Bestand
aus `git log -3 --format="%an <%ae>"` mit `-c user.name=… -c user.email=…`
fortsetzen, nicht konfigurieren.

Die Hooks laufen mit: `pre-commit` (Bezeichner, neue Texte dieses Commits),
`commit-msg` (echte Umlaute), `post-commit` (Push). Einen Befund beheben, nicht
mit `SOLIDON_KEIN_TOR` oder `--no-verify` umgehen.

## Push

`post-commit` pusht und endet immer mit 0, auch wenn der Push scheitert.
Maßgeblich ist seine Ausgabe („ist auf der Gegenstelle“ oder „PUSH
GESCHEITERT“) und danach `git status -sb` beziehungsweise `git rev-parse HEAD`
gegen `git ls-remote origin <zweig>`.

Ist die Gegenstelle weiter: `git fetch`, die fremden Commits ansehen
(`git log HEAD..origin/<zweig>`, `git diff --name-only HEAD...origin/<zweig>`),
dann `git merge origin/<zweig>` und `git push origin <zweig>`. **Merge, nie
Rebase** — auch wenn die Meldung des Hooks `pull --rebase` vorschlägt.
Konflikte anhand beider Seiten auflösen. Blockieren ungestagete Änderungen den
Merge, eigene fertige Arbeit zuerst liefern; fremde oder unfertige Arbeit nie
stashen oder zurücksetzen, sondern anhalten und melden. Eine gesetzte
`solidon.noAutoPush` in der lokalen Konfiguration ist die Sperre einer
laufenden Arbeitsrunde: nicht aufheben, melden.

## Ergebnis

Die Kennung aus der Ausgabe von `git commit` verwenden, nicht ein später
weitergewandertes `HEAD`, und `git show --stat <kennung>` gegen die Einheit
halten. Melden: je Commit Kennung und Aussage, Prüfstand, Review,
Push-Ergebnis und was an eigenen und fremden Änderungen im Baum bleibt.

Danach die eigenen Worktrees und Prüfbäume abbauen, deren Stand auf main liegt
und die nichts Ungesichertes tragen — belegt mit `git merge-base
--is-ancestor <zweig> origin/main`, bei einem Prüfbaum ohne Zweig je Datei
`git hash-object` gegen den Blob im Commit. Dann `git worktree remove`,
`git worktree prune`, Zweige lokal und auf der Gegenstelle löschen; fremde
nicht anfassen.
