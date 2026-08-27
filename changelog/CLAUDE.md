# `changelog/` — was im Update-Fenster steht

Eine Datei je Sprache: `de` `en` `es` `fr` `it` `pt`. Gelesen wird sie von
`app/core/updates.py` und im Update-Dialog gezeigt.

## Das ist kein Änderungsprotokoll

**Es ist eine Auswahl in Kundensprache.** Wer hier eine Liste der Commits
ablegt, hat den Zweck verfehlt: Der Kunde will wissen, was *er* jetzt tun
kann, nicht welche Datei sich geändert hat.

- „Der Deckel sitzt jetzt auch auf schrägen Öffnungen" — ja.
- „`lid.py`: Kantenerkennung überarbeitet" — nein.

Die technische Geschichte steht in der Git-History und in `ROADMAP-ARCHIV.md`.

## Sechs Dateien, ein Stand

Alle sechs Sprachen ziehen gemeinsam nach. Eine Version, die nur auf Deutsch
etwas zu sagen hat, ist ein halber Eintrag — der Kunde sieht seine Sprache
oder gar nichts.

## Ein Verweis muss ankommen

Wer auf das Handbuch verweist, verweist auf einen Abschnitt, den es gibt. Ein
Punkt, der den Kunden ins Handbuch schickt, wo nichts steht, ist schlimmer als
kein Punkt — das ist einmal passiert und trägt seinen eigenen Commit.
