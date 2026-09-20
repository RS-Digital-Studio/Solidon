# `app/cli/` — die Kommandozeile

Eine zweite Oberfläche auf demselben Kern (§10). Kein zweiter Rechenweg, keine
eigene Logik — was hier möglich ist, ist möglich, weil es im Register steht.

## Die eine Idee

`app/core/registry/surfaces.py` erzeugt aus dem Register die Befehle:

```
REGISTRY  ──>  cli_commands()  ──>  argparse-Unterbefehle
```

**Eine neue Operation bekommt ihren Befehl damit von selbst.** Wer in
`main.py` einen Unterbefehl von Hand einträgt, hat das Register umgangen — und
die Oberfläche und der Agent, die dieselbe Quelle lesen, wissen nichts davon.

## Die Karte

| Datei | Rolle |
|---|---|
| `__init__.py` | Der konfigurierte Skripteinstieg `launch()` richtet den Prozessschutz vor dem Laden der Kommandozeile ein |
| `main.py` | Der Einstieg. Argumentbaum, Projekt öffnen, auswerten, Befunde und Bericht ausgeben |

Skripteinstieg und `python -m app.cli.main` installieren denselben idempotenten
Absturzschutz vor den schweren Kernimports. Ein normaler Modulimport ändert
keine Prozesshooks. Unbehandelte Python- und Threadfehler sowie der letzte
Fehlerfang im CLI-Befehl verwenden `report.exception_report()`; auch ein
Fehler beim Schreiben des Berichts lässt die ursprüngliche Diagnose und den
Fehlerausgang erhalten. Qt wird für den Bericht nicht geladen.

Die festen Befehle daneben — `ops`, `docs`, `profiles`, `new`, `info`,
`import`, `run`, `undo`, `export` — sind die, die kein Register erzeugen kann,
weil sie über dem Dokument stehen statt in ihm.

## Was hier anders ist als im Fenster

- **`TerminalProgress`** statt einer Ladeanzeige, **`terminal_ask()`** statt
  eines Dialogs. Beide erfüllen den `OpContext`-Vertrag — der Kern merkt den
  Unterschied nicht.
- **Ausgewertet wird synchron.** Kein Thread, keine Halteleine.
- **`tr()` gilt auch hier.** Eine Meldung auf der Kommandozeile ist ein
  Oberflächentext wie jeder andere (Regel 20).

## Probelauf

```bash
.venv/Scripts/python.exe -m app.cli.main --help
```

Die Kommandozeile ist der schnellste Weg, eine Operation ohne Fenster
auszuprobieren — und der einzige, der in einem Testlauf ohne Fenster durchkommt.

`kind="features"` wird als Liste übergeben, etwa
`--at-features face_1 face_2`. Der Parser reicht echte Kennungen als Liste an
das Parameterschema weiter. Bei `clear_filament` bleibt das alte einzelne
`--at-feature` gültig; ohne beide Angaben betrifft die Abwahl den ganzen Körper.

`scad --set NAME=WERT` nennt in jeder Sprache dieselben Wahrheitswerte:
`true`/`false`, alternativ `1`/`0`. Ziffern werden nur bei einem im
Bausteinschema als `bool` deklarierten Parameter in Wahrheitswerte umgewandelt.
Die bisherigen deutschen Wörter bleiben für bestehende Skripte gültig;
ein anderer Text nennt die sprachunabhängigen Werte in der Fehlermeldung.
