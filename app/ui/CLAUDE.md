# `app/ui/` — die Oberfläche

PySide6. Darf `app.core` benutzen, die Gegenrichtung ist verboten (§8). Die
Oberfläche rechnet keine Geometrie und ändert keine — **sie ruft Ops auf.**

Die Regeln dieses Gebiets stehen in `.claude/rules/` und laden sich selbst —
**vier Dateien, je nachdem, was man anfasst:**

| Regeldatei | Lädt bei |
|---|---|
| `oberflaeche.md` | jeder Datei hier — Texte, Zahlen, Grenzen, Barrierefreiheit |
| `ansicht.md` | `viewport.py`, `overlay.py`, `cursors.py` und den Leisten |
| `wartezeit.md` | `session.py`, `loading.py`, `leash.py`, `splash.py`, `main_window.py` |
| `zeichenflaeche.md` | `sketch_editor.py` |

Hier steht die Karte, dort das Gesetz.

## Der Weg durch die Schicht

```
main_window.py   Menüs, Auswahl, Zustand
      │  ruft eine Operation auf
      ▼
session.py       die Brücke zum Kern: Stapel, Auswertung, Threads
      │  wertet aus (im Arbeiter-Thread)
      ▼
app.core         rechnet
      │  EvaluationResult
      ▼
viewport.py      zeigt an
```

`session.py` ist die einzige Stelle, an der die Oberfläche den Kern anfasst.
Wer an ihr vorbei rechnet, bricht Regel 2.

## Die vier Dinge, die an `session.py` überraschen

Ende zu Ende gemessen am 27.08.2026 — vier Anläufe gingen daran verloren,
bevor es jemand wusste:

- **`session.last_result` ist die ausgewertete Szene.** Ein
  `session.scene` gibt es nicht.
- **`evaluate_now()` ist der synchrone Weg** — für Kommandozeile, Tests und
  Export. Er gibt das Ergebnis zurück, statt es nur anzustoßen.
- **`session.apply()` endet mit `evaluate_async()`.** Nach dem Aufruf steht
  das Ergebnis noch **nicht**. Und es wirft nicht: Fehler kommen über das
  Signal `failed`. Ein `try` um den Aufruf läuft ins Leere — nach dem
  Ergebnis fragen, nicht nach dem Grund.
- **`Scene.objects` ist ein Wörterbuch.** Darüber zu iterieren gibt die
  Kennungen. Die Folgemeldung `'str' object has no attribute 'mesh'` sieht
  aus wie ein leerer Import und ist keiner.

## Die Karte

**Rahmen und Einstieg**

`app.py` (Einstiegspunkt, §38) · `main_window.py` (**8 600 Zeilen** — das
Hauptfenster, §2.5) · `splash.py` · `first_run.py` (der erste Start) ·
`start_screen.py` (die ersten fünf Minuten, §2.3) · `header.py`

**Brücke zum Kern**

`session.py` (§7, §15.6) · `leash.py` (die Halteleine für Arbeiter-Threads)

**Ansicht**

`viewport.py` (**7 300 Zeilen** — §18, §2.9) · `overlay.py` (Zonen über der
Ansicht statt neben ihr) · `loading.py` (Ladeanzeige, §2.8) · `cursors.py`

**Panels und Leisten**

`panels.py` (die drei Panels links, Prüfbericht rechts, §2.5) ·
`tool_strip.py` · `analysis_bar.py` · `section_bar.py` · `split_bar.py` ·
`transform_bar.py` · `explode_bar.py` · `sculpt_bar.py` · `pose_bar.py` ·
`scale_widget.py` · `facts.py` (was das Teil kostet, während man daran baut)

**Dialoge**

| Datei | Besonderheit |
|---|---|
| `op_dialog.py` | **Wird aus dem Parameterschema erzeugt** (§10, §2.4). Kein Dialog wird von Hand gebaut — wer einen tippt, hat das Register umgangen |
| `dialogs.py` | Fragen und Fehler, wie §2.7 sie beschreibt |
| `print_settings_dialog.py` | Druckeinstellungen und Slicer-Übergabe (§29) |
| weitere | `settings_dialog` · `generate_dialog` (Weg 3) · `recipe_dialog` · `variants_dialog` · `comfy_dialog` · `install_dialog` · `support_dialog` · `update_dialog` · `changes_dialog` |

**Editor**

`sketch_editor.py` (**4 100 Zeilen** — §30.1, Stufe zwei)

**Agent**

`chat.py` (§26.3, §2.5) · `snapshots.py` (Ansichten für den Agenten) ·
`remote_server.py` (MCP im Fenster)

**Bibliothek**

`catalog.py` (Bausteinkatalog, §24.3) · `filament_picker.py` (Farbe und Name
statt einer Zahl von 0 bis 7)

**Erscheinung**

`style.py` (Stylesheet, Typografie-Skala, Abstandsraster, §19.3) · `theme.py`
(hell und dunkel) · `palette.py` (**Farbe trägt nie allein Bedeutung**,
§19.1) · `icons.py` · `motion.py` (Bewegung an einer Stelle, nicht an
zwanzig) · `labels.py` (kurze Texte, auf die sich mehrere Teile einigen)

**Hilfe und Bedienung**

`manual_window.py` · `tour.py` · `shortcuts_window.py` ·
`shortcut_schemes.py` (zwei Belegungen, eine Quelle) · `command_palette.py`

**Einstellungen** `settings.py` · `survey.py`

## Grenzen

- **Keine feste Zeichenkette** — alles über `tr()` (Regel 20).
- **Keine Bestätigungsdialoge vor rücknehmbaren Handlungen** (Regel 19).
- **Keine Bedeutung allein über Farbe** — immer eine zweite Kodierung
  (Regel 18).
- **Höchstens neun Menüs, zwölf Zeilen je Menü, acht Werkzeuge, acht Felder
  vorn** — `tests/test_interface_limits.py` zählt nach.
- **Nichts rechnet im Qt-Hauptthread**, was länger dauert als ein Lidschlag
  (§2.8).

## Testen

Die Tests laufen offscreen; `tests/conftest.py` setzt `QT_QPA_PLATFORM`
selbst. Zwei Fallen, beide gemessen:

- **Qt lügt vor dem Anzeigen.** `setExpanded`, `isVisible` und `hasFocus`
  antworten falsch, solange nichts angezeigt wurde — ein Test kann grün
  bleiben gegen einen Zweig, der nie läuft.
- **Gesetzt heißt nicht gezeigt.** `QMenu` verschluckt Tooltips; ein Test über
  den Wert eines Hinweises sagt nichts über seine Sichtbarkeit.

Die Suite baut über siebenhundert VTK-Fenster nacheinander auf und reißt am
Stück ab. Fensterdateien werden **je Prozess einzeln** gefahren — siehe
`CLAUDE.md` im Wurzelverzeichnis.
