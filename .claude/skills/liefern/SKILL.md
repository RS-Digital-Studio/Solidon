---
name: liefern
description: >
  Schließt eine geprüfte Arbeitseinheit ab: Änderungen abgrenzen, in logischen
  Einheiten mit deutschen Meldungen committen und Commit sowie Push prüfen.
  Nur auf ausdrückliche Anweisung.
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob
---

# Liefern

## Umfang und Nachweis

Die aktuelle Anweisung von Robert bestimmt den Umfang. Das vollständige Tor
über `/pruefen` gehört vor den Commit; ein passender bereits grüner Lauf muss
nicht wiederholt werden. Liegt ein Fehllauf vor, seine Ursache und den
betroffenen Stand benennen und zuerst beheben.

`git status --short` und `git diff HEAD` lesen — **gegen HEAD, nicht gegen den
Index**, sonst zeigt der Vergleich den Stand des Index statt den des letzten
Commits. Die Einheit umfasst genaue Dateien. Verzeichnisangaben, `git add .`
und `git commit -a` gehören nicht in diesen Ablauf; eine neue oder gelöschte
Datei muss ausdrücklich zur Liste gehören. `3D Drucker/`, Umgebungen,
Messdaten und Testartefakte bleiben draußen, soweit sie nicht beauftragt sind.

**Ein Thema ergibt einen Commit.** Mehrere Themen ergeben mehrere Commits,
jeder eine logische Einheit — keine Mega-Commits, keine Mini-Commits pro Datei.

## Meldung

Die deutsche Meldung verwendet **echte Umlaute** — `.githooks/commit-msg`
bricht sonst ab — und beschreibt das **Ergebnis**, nicht das Etikett: „Hohle
Querschnitte kamen als nichts zurück", nicht „fix: section". Der Rumpf nennt
den nötigen Grund. Der tatsächliche Mitautor bleibt angegeben: das verwendete
Claude-Modell mit `noreply@anthropic.com` oder `Codex <noreply@openai.com>`.

Deutscher Text geht nicht zuverlässig durch die Shell: Die Meldung in eine
Datei schreiben und mit `git commit -F <datei>` übergeben, statt sie als
`-m`-Argument zu übergeben.

## Committen

```bash
git add -- tools/sync_agents.py tests/test_agent_mirror.py
git diff --cached --stat
```

Die Liste im `git add` durch die geprüfte Dateiliste ersetzen und den `--stat`
gegen die Erwartung halten, **bevor** committet wird. Stimmt sie, folgt der
Commit:

```bash
git commit -F "$TEMP/commit-meldung.txt"
git rev-parse HEAD
```

Vor jedem Commit an `app/` oder `tools/` fährt `.githooks/pre-commit` die zwei
Sprachprüfungen — rund zehn Sekunden. Er bricht ab, wenn eine Datei aus diesem
Commit darin genannt ist; `SOLIDON_KEIN_TOR=1` schaltet ihn ab. Beides läuft
nur, wenn `core.hooksPath` auf `.githooks` zeigt.

Eine laufende Merge-, Rebase- oder Cherry-pick-Operation wird nicht durch
diesen Ablauf abgeschlossen — erst den Zustand lesen und ihn eigens auflösen.

## Ergebnis kontrollieren

Die vom Commit ausgegebene Kennung verwenden, nicht ein später weitergewandertes
`HEAD`. Mit `git show <kennung> --name-status` und `git show <kennung> --numstat`
die tatsächlich enthaltenen Dateien und Zahlen gegen die Erwartung halten.

Der eingerichtete `.githooks/post-commit` pusht nach `origin`, wie in
`CLAUDE.md` festgelegt. Seine Ausgabe und den Remote-Zweig getrennt prüfen:
**Ein erfolgreicher Commit beweist keinen erfolgreichen Push.** Ein Remote-Tip,
der genau die Commitkennung trägt, bestätigt die Veröffentlichung. Ist der
Remote-Zweig weiter, nach dem Fetch seine Abstammung prüfen; eine abweichende
Spitze allein beweist weder Erfolg noch Verlust.

Eine ausdrücklich gewünschte lokale Sammlung nutzt `SOLIDON_KEIN_PUSH=1` im
Commitaufruf. Bei einer weitergewanderten Gegenstelle zusammenführen — Merge,
kein Rebase, kein Force-Push.

Melden: Commitkennungen und Zweck, Prüfstand, Push-Ergebnis und welche Arbeiten
noch offen sind. `ROADMAP.md` nur fortschreiben, wenn die Einheit das erfordert.
Bei einem Fehler nach dem Commit vorwärts korrigieren; keine History umschreiben.
