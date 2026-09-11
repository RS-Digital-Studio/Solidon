---
name: liefern
description: >
  Schließt eine geprüfte Arbeitseinheit ab: Änderungen abgrenzen, mit deutschen
  Meldungen committen und den beauftragten Push oder Pull prüfen. Nur auf
  ausdrückliche Anweisung; fremde Änderungen und bestehende Git-Zustände erhalten.
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob
---

# Liefern

## Auftrag und Prüfstand

Die aktuelle Anweisung von Robert bestimmt Commit, Push und Pull getrennt.
Ein reiner Commitauftrag enthält keine zusätzliche Push-Freigabe; den
vorhandenen automatischen Push-Hook dann für diesen Prozess mit
`SOLIDON_KEIN_PUSH=1` unterdrücken. Eine bereits ausdrücklich erteilte
Push-Freigabe bleibt gültig. Keine neue Nachfrage für autorisierte Schritte.

Vor dem Commit gilt das vollständige Tor über `.agents/skills/pruefen/SKILL.md`. Ein passender
bereits grüner Lauf muss nicht wiederholt werden; relevante Änderungen seit
dem Nachweis vorher prüfen. Einen Fehllauf mit Ursache und Stand benennen.

## Änderungen abgrenzen

Prüfe Branch, `HEAD`, `git status --short`, `git diff HEAD`, vorgemerkte und
unversionierte Dateien sowie laufende Merge-/Rebase-/Cherry-pick-Vorgänge.
Beachte parallele Schreiber und lokale Betriebssperren. Die Einheit besteht
aus genauen Dateien und den eigenen darin enthaltenen Änderungen, nicht aus
pauschalen Verzeichnissen. Änderungen vor dem Commit kurz zusammenfassen.

Ein Thema ergibt einen Commit. Für neue und gelöschte Dateien muss die
Aufnahme ausdrücklich geprüft sein. Keine ungezielten `git add .`,
`git commit -a` oder Stash-Aktionen über fremde Arbeit.

Im geteilten Arbeitsbaum einen eigenen temporären Index verwenden:
`GIT_INDEX_FILE` pro Prozess setzen, mit `git read-tree HEAD` aus dem **aktuellen**
Stand aufbauen und nur die vereinbarten Pfade aufnehmen. Vor dem Commit den
privaten staged Diff vollständig gegen `HEAD`, Dateiliste und erwartete
Einfügungs-/Löschzahlen prüfen. Der private Index trennt Dateien, nicht
verschiedene Autoren innerhalb derselben Datei; gemischte Hunks müssen
abgegrenzt werden. Keine fremde laufende Git-Operation abschließen.

Hat sich `HEAD` oder eine betroffene Datei währenddessen geändert, zunächst
den neuen Stand prüfen und die Einheit neu aufbauen. Das ist kein Grund für
einen Reset über fremde Dateien. Nach dem eigenen Vorgang `GIT_INDEX_FILE`
wiederherstellen und den tatsächlichen Hauptindex prüfen. Einen veralteten
Hauptindex nur nach Klärung seiner vorgemerkten Änderungen abgleichen.

## Meldung und Commit

Die deutsche Meldung mit echten Umlauten beschreibt das Ergebnis. Der Rumpf
nennt den nötigen Grund, am Ende steht der tatsächliche Mitautor: verwendetes
Claude-Modell mit `noreply@anthropic.com` oder `Codex <noreply@openai.com>`.
Schreibe die Meldung in eine UTF-8-Datei und übergib sie mit
`git commit -F <datei>`. Benutze bei privatem Index keinen Pfad-Commit, der
statt der geprüften Indexfassung erneut ganze Arbeitsdateien aufnehmen kann.

Die vorhandenen Hooks vorher lesen, insbesondere `core.hooksPath`,
`.githooks/pre-commit` und `.githooks/post-commit`. Ihre Existenz beweist
keinen erfolgreichen Lauf. Prüfschritte nicht zum Umgehen eines Fehlers
abschalten. Eine lokale `solidon.noAutoPush`-Sperre nicht eigenmächtig aufheben.

## Push und Pull

Bei beauftragtem Pull zuerst fetch ausführen und anschließend Divergenz,
Dateiüberschneidungen und den aktuellen Arbeitsbaum ansehen. Ohne lokale
Commits bevorzugt Fast-forward. Bei Divergenz den bestehenden Projektweg
beachten; kein automatischer Rebase oder Force-Push. Lokale Änderungen nur
gezielt sichern, mit identifizierbarer Ablage; nach dem Pull wiederherstellen
und Konflikte anhand beider Änderungen auflösen. Eine Sicherung erst nach
überprüfter Wiederherstellung entfernen. Bei unklarer Eigentümerschaft
koordinieren, statt fremde Arbeit zu verschieben oder zu überschreiben.

Der post-commit-Hook kann automatisch pushen und meldet auch bei einem
Pushfehler Prozessausgang 0. Deshalb sein Ergebnis und den Remote-Zweig
separat prüfen. Ein erfolgreicher Commit beweist keinen erfolgreichen Push.
Falls ein autorisierter Push ausbleibt, den konkreten Branch ausdrücklich
pushen und das Ergebnis kontrollieren; keine Betriebssperre dafür umgehen.

## Ergebnis

Die vom Commit ausgegebene Kennung verwenden, nicht ein später weitergewandertes
`HEAD`. `git show <kennung> --name-status` und `--numstat` gegen die geprüfte
Einheit halten. Ein frisch geholter Remote-Tip auf dieser Kennung bestätigt die
Veröffentlichung; bei weitergewandertem Remote seine Abstammung prüfen.

Melden: Commitkennung und Zweck, Prüfstand, separat Push-/Pull-Ergebnis und
verbleibende lokale Änderungen. Nicht beauftragte Schritte ausdrücklich als
nicht ausgeführt nennen. Keine History umschreiben, um einen Fehler zu verbergen.
