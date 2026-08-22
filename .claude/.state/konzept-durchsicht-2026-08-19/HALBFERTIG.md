# Achtung: fünf Dokumente sind halb redigiert (Stand 19.08.2026, 21:53)

Die Redaktion wurde mitten im Lauf angehalten. **Kein einziger der achtzehn
Redakteure hat sein Ergebnis zurückgegeben** — das Journal des Laufs
`wf_e029d966-55f` enthält achtzehn `started` und null `result`. Fünf Dokumente
tragen trotzdem schon Änderungen im Arbeitsbaum:

| Datei | Zeilen geändert | Kopf datiert | Schlussabschnitt |
|---|---:|---|---|
| `konzept-agent-vertiefung.md` | +114 | nein | nein |
| `konzept-durchsicht-2026-08-14.md` | +23 | nein | nein |
| `konzept-erstnutzer-2026-08.md` | +128 | nein | nein |
| `konzept-erzeugen-agent-oberflaeche-2026-08.md` | +58 | **ja** | nein |
| `konzept-kundensicht-2026-08.md` | +86 | nein | **ja** |

Keine dieser fünf ist nachweislich fertig: Zu einer vollständigen Redaktion
gehören beide Marken — das fortgeschriebene Stand-Datum im Kopf und der
Abschnitt `## Nachrecherchiert am 19.08.2026` am Ende. Keine Datei hat beide.

## Beim Weitermachen zuerst entscheiden

Für diese fünf gibt es zwei Wege, und die Wahl gehört Robert:

1. **Vorwärts.** Die Redakteure für genau diese fünf noch einmal laufen lassen,
   mit dem Zusatz: „Die Datei ist bereits teilweise nachgezogen — prüfe, was
   schon steht, und ergänze nur, was fehlt, ohne einen Vermerk doppelt zu
   setzen." Das entspricht der Hausregel „kein Revert, vorwärts fixen".
2. **Zurück auf Anfang.** `git checkout --` auf diese fünf und die Redaktion
   sauber neu fahren. Schneller und ohne Doppelvermerke, kostet aber die
   angefangene Arbeit.

Die übrigen dreizehn Dokumente sind unberührt und können ohne Vorbehalt
redigiert werden.

## Nicht verwechseln

Im selben Arbeitsbaum liegen **elf geänderte Dateien einer parallelen Sitzung**
(`app/ui/panels.py`, `sketch_editor.py`, `style.py`, `theme.py`, `tour.py`,
`viewport.py`, `packaging/solidon3d.spec`, `tools/make_figures.py`,
`tests/test_analysis_ui.py`, `test_style.py`, `test_theme_and_palette.py`).
Die gehören **nicht** zu dieser Durchsicht. Weder prüfen noch anfassen, und bei
einem Commit nicht mit einsammeln.
