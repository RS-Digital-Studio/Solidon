# Gebietsbericht: Sicherungsnetz (tests/, tools/, website/, .githooks/, pyproject/constraints)

Strikt lesend; Skripte unter `review-tests\`. Einzelne Testdateien gefahren (test_website/updates/toolchain/licences, ein test_analysis_ui) — alle grün.

## Hoch

### 1 [hoch] Die §38-Isolation greift auf macOS nicht — die Suite schreibt dort ins echte Nutzerprofil — VERIFIZIERT
`tests/conftest.py:26-28` setzt `APPDATA`/`LOCALAPPDATA`/`XDG_*`; `app/core/paths.py:28-50,159-160` liest unter `darwin` keine Umgebungsvariable, sondern `Path.home()/Library/…`. Gemessen: win32/linux isoliert, darwin data/config/cache/log alle `isoliert=False` (echtes Profil). Die CI fährt die Suite auf `macos-latest` (`build.yml:50`), macOS ist Auslieferungsplattform. **Fix:** in `conftest.py` zusätzlich `HOME=_ISOLATED` setzen + Test, der die Isolation für alle drei Plattformen zusichert.

### 2 [hoch] Die Fehlerprüfung sieht nicht „jede Ausnahme", und welche entscheidet die Importreihenfolge — VERIFIZIERT
`tests/test_errors.py:30-37` (`all_error_classes()` über `__subclasses__()`) — findet nur importierte Klassen; `test_errors.py` importiert nur `app.core.errors`. Gemessen: 15 ohne Importe, 20 im Sammellauf, 24 nach Backend/Support-Import; nie erfasst: `BackendUnavailable/TooSlow/AnswerUnreadable`, `GenerationFailed`, `SendFailed` — die häufigsten beim Kunden. **Fix:** vor dem Sammeln alle Kernmodule laden (`walk_packages`) und die Menge zusichern (`>= 24`).

## Mittel
- **3** Fünf Sichtbarkeits-Asserts können nie rot werden (`test_update_ui.py:54,77,137`, `test_first_run.py:556`, `test_generate_ui.py:593`: `isVisible() or not dialog.isVisible()`, Dialog nie `show()`); zwei Geschwister (`test_interface_limits.py:841` `or True`, `test_ui.py:446` `or True`). VERIFIZIERT. Fix: `assert not widget.isHidden()`.
- **4** `test_parts.py:1113` prüft die Bausteinversion 23-mal für denselben Baustein (`name` aus voriger Schleife, konstant `snap_connector`; `or` macht die scharfe Hälfte wirkungslos). VERIFIZIERT (mit `spec.name` wären 3 rot). Fix: `if spec.version != "1": assert spec.name in changed_since(...)`.
- **5** Der Telemetrie-Verbotstest sieht nur in `support_dialog` (`test_support.py:202-219`, `getsource` einer Datei), ein zweiter `support.send(` woanders bliebe unsichtbar; `kern.md` verlässt sich darauf. Fix: über `app/**/*.py` suchen, Grundmenge zusichern.
- **6** Elf Verbotstests über erhobene Grundmengen ohne Zusicherung (`test_style/value_labels/cache/ui/translations`, glob/rglob → leere Menge = grün); `test_translations.py` parametrisiert → null Tests bei leerer Liste. VERIFIZIERT. Fix: je Datei eine Grundmengen-Zusicherung.
- **7** `licences.check()` wird nie mit einem Verstoß gefüttert (`test_licences.py:37-44` prüft nur Zeichenketten; `check()` nur gegen die saubere Umgebung). Entscheidungslogik (`licences.py:188-212`, LGPL-Ausnahme) ungetestet — `and`→`or` bliebe grün (Regel 15/22). Fix: `runtime_packages` monkeypatchen, vier Fälle.
- **8** Die CI wiederholt jeden Fehlschlag, nicht nur einen Absturz (`build.yml:211-217`, `run || run` kann Exit 1 nicht von Abriss trennen; `tests.md` warnt davor). Ein sporadisch roter Test geht als grün ins Paket. Fix: nur bei Exit > 5 wiederholen.
- **9** Nichts hält `pyproject.toml` und `constraints.txt` gegeneinander (AGENTS.md-Checkliste Punkt 5); `check_env.py:299-311` prüft nur eine Richtung. Heute keine Lücke, aber ungesichert (Schaden vom 06.08.). Fix: zehn Zeilen in `test_toolchain.py`.

## Gering
- **10** Schlüsselbund und `SOLIDON3D_LLM_KEY` nicht zentral isoliert (`conftest.py`); `keys.py:42-59` liest die Umgebungsvariable weiter. Heute folgenlos. Zentral auf `None`.
- **11** `Release.package()` nur von Tests gerufen, Testdocstring behauptet Anschluss (`test_updates.py:235`, null Aufrufer in app/tools; `make_download.py` erzeugt den Fall nie). Auf `startable()` reduzieren.
- **12** `test_discover.py:448-464` ohne wirksames Assert auf Windows/macOS (beide in `if linux`), meldet „passed" statt „skipped". `skipif`.
- **13** Migrationstest zählt statt Abdeckung (`test_project.py:472`, `>= FORMAT_VERSION`); gelöschte v3 + zwei neue bliebe grün. `set(range(1, FORMAT_VERSION+1))`.
- **14** `test_analysis_ui.py:298-305` schaltet sich still ab (skip bei keinen Befunden, prüft nur `item(0)` statt „every finding"); §22.5. Befund erzwingen.
- **15** `test_selection.py:471` lässt den Fehlerfall zu (`is None or …`). `assert not None` davor.
- **16** `link_memory.py:117-134` verspricht „nichts geht verloren", `rmtree` löscht Nicht-`.md`. Über `iterdir()` benennen oder umbenennen.
- **17** Wöchentlicher CI-Job prüft den kompilierten Schichtkern nicht (`build.yml:611-629`, kein `build_slice_core.py`). Frühwarnung blind.
- **18** Fenster-Suchmuster in drei Fassungen, bereits auseinander (`build.yml:170,625` `MainWindow|Viewport\(` vs `suite-getrennt.sh` `…|pyvista`); ROADMAP führt das Grundthema. Drei Stellen.
- **19** `pytest-randomly` begründet drei Fixtures, ist nicht installiert; Suite läuft in fester Reihenfolge. Aufnehmen oder Begründung entschärfen.

## Hinweis außerhalb der Befundliste
Im Arbeitsbaum sind 199 Dateien unter `.claude/.state/` gelöscht (alle in diesem Ordner), darunter `suite-getrennt.sh` — laut CLAUDE.md der einzige Weg, auf dem das Tor durchläuft, seit 22.08. eingecheckt. Nichts angefasst; falls keine gewollte Aufräumaktion, nimmt der nächste `git commit -a` es mit und der post-commit-Hook schickt es hinaus. (Nachbarsitzung 3d-druck-ce hat `suite-getrennt.sh` inzwischen aus HEAD wiederhergestellt.)

## Geprüft und in Ordnung
`check_env.py` (grün), `bump_version.py` (beide + drei abgeleitete Stellen konsistent auf 0.1.5), `.githooks/post-commit` + `core.hooksPath`, `session_board.py` (`Path(pipe).exists()` auf Windows), `release_signing.py`, `test_roadmap.py`, `agent_cases.py` (39 Fälle), `test_website.py` (154 passed, Sitemap/robots/Download konsistent, vier Pakete auf 0.1.5).

**Kann das so rein: ja** — Bestand lauffähig, Tor grün; die zwei hohen Befunde (macOS-Isolation, unvollständige Ausnahmenmenge) decken eine harte Regel nur scheinbar und sollten vor dem nächsten Paket fallen.
