---
name: version-vor-jedem-bau-erhoehen
description: Vor jedem ausgelieferten Bau die Fassung selbst erhöhen — nicht fragen; tools/bump_version.py macht beide Stellen.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: d0bd4b75-5327-4ced-9591-8a6ee286ce59
  modified: 2026-08-20T19:52:32.430Z
---

Vor jedem Bau, der ausgeliefert wird, steigt die letzte Stelle der Fassung um
eins — **ohne Rückfrage**. Am 20.08.2026 habe ich stattdessen gefragt
(0.1.0 → 0.1.1), und Robert hat klargestellt: „du sollst das automatisch
machen".

**Why:** Die Zählregel steht im Projekt (`app/branding.py`) und in Roberts
globaler Vorgabe. Zwei Pakete mit derselben Nummer kann niemand
auseinanderhalten — nicht der Über-Dialog, nicht der Update-Hinweis
([[solidon3d-update-hinweis]]), nicht der Support vor einem Fehlerbericht. Die
vorderen Stellen sind dagegen eine Entscheidung und gehören ihm.

**How to apply:** `tools/bump_version.py` (seit 20.08.2026) fasst beide Orte
an, die die Zahl tragen — `branding.py` und `pyproject.toml`. Aufgerufen wird
es **vor** dem Prüfmodul und dem Bau; danach trüge das Paket eine Nummer, die
es schon gab. `website/version.json` bleibt dabei liegen: Sie sagt, was
veröffentlicht *ist*, und wird zuletzt hochgeladen. Der Weg steht vollständig
in der Skill `/erzeugen`.

---

## Und danach: Was steckt eigentlich im Paket?

Am 23.08.2026 lieferte eine Sitzung 0.1.4 aus, während ich noch committete. Die
Frage „sind Roberts gemeldete Fehler drin?" ließ sich aus **Dateizeitstempeln
nicht** beantworten: Die Pakete trugen 23:14, gebaut wurde gegen einen Stand von
**22:35** — der Zeitstempel ist das *Ende* des Laufs, nicht sein Anfang.

Der billige und exakte Weg, von `3d-druck-bd`:

```
gh run view <run-id> --json headSha        # gegen welchen Commit lief der Bau
git merge-base --is-ancestor <commit> <headSha>   # steckt meiner darin?
git grep <marke> <headSha> -- app/         # und der harte Beleg in der Datei
```

Zehn Sekunden statt zehn Minuten. **Die dritte Zeile ist die wichtigste:** Eine
Ahnenschaft im Graphen belegt, dass der Commit *erreichbar* war — nicht, was in
der Datei steht. `git grep CLICK_SLACK 5105e24` gab `= 10` statt `= 2`, und erst
das war der Beweis.

**Was nicht funktioniert:** `grep` über die gebaute EXE. PyInstaller komprimiert;
selbst `Solidon3D` und `MainWindow` finden **null** Treffer. Wer nur nach dem
neuen Namen sucht und null findet, meldet „fehlt im Paket" und liegt falsch — die
Gegenprobe an einem Namen, der drin sein *muss*, entlarvt das in einer Minute.
Siehe [[messwerkzeug-misst-sich-selbst]].
