---
name: worktree-venv-verstellt-den-hook
description: "Ein Worktree mit eigener alter .venv lässt den pre-commit-Hook mit dem falschen Interpreter laufen (vier Minuten je Commit, dann 'fremde Arbeit', durchgewinkt) und macht Kindprozess-Tests rot; für Commits dort SOLIDON_KEIN_TOR=1 und die Sprachprüfung von Hand mit der richtigen Umgebung."
metadata:
  type: feedback
  originSessionId: f07e3f31-b0f2-4cae-b55c-218ecd11e007
  modified: 2026-09-06T13:22:15.784Z
---

Am 06.09.2026 committete ich die Gesamtdurchsicht in zwölf Einheiten im
Worktree `F:\Solidon-Fixes-01a07020`. Der Worktree trug eine eigene `.venv`
vom 02.09. (Python 3.13) neben der `.venv314`, mit der alle Tests gefahren
waren. `.githooks/pre-commit` nimmt stur `.venv/Scripts/python.exe`: Die
Sprachprüfung lief mit 3.13 gegen 3.14-Code, brach mit `SyntaxError` in
`app/core/types.py` ab, fand den Namen in keinem gestagten Pfad und winkte
nach **vier Minuten je Commit** als „fremde Arbeit im geteilten Baum" durch.
Zwölf Commits hätten fast eine Stunde gekostet und nichts geprüft.

Dieselbe alte `.venv314`-Umgebung ließ `tests/test_process.py` (drei
Zeitüberschreitungen beim Start von Kindprozessen) und den Sicherungstest in
`test_project.py` rot werden — mit der frisch gebauten `.venv-314` des
Hauptbaums waren beide grün, bei identischem Code.

**Why:** Der Hook prüft nicht, ob seine Umgebung zum Code passt; er glaubt
dem Pfad. Ein `SyntaxError` sieht für ihn aus wie ein roter Test in einer
Datei, die nicht im Commit ist — genau der Fall, den er durchlassen soll.

**How to apply:** Im Worktree vor dem Commit prüfen, welches Python
`.venv/Scripts/python.exe --version` ist. Passt es nicht: Sprachprüfung von
Hand mit der richtigen Umgebung (`pytest tests/test_language_rules.py
tests/test_translations.py`), dann `SOLIDON_KEIN_TOR=1 git commit`. Einen
Worktree, dessen `.venv` alt ist, nicht für Kindprozess-Tests nehmen — die
Umgebung des Hauptbaums läuft auch aus dem Worktree heraus, `import app`
findet über das Arbeitsverzeichnis den Worktree-Code. Verwandt:
[[lokale-umgebung-python-version]], [[hintergrundlauf-stirbt-mit-der-sitzung]].
