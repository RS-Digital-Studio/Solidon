# Windows-CI: fehlende Matplotlib-Lizenzbeilagen

## Befund und Ursache

Windows-CI `35911449478` meldete zusätzlich zwei echte Fehler:
`tests/test_licence_notices.py::test_checked_in_notice_is_the_deterministic_target_output`
und `tests/test_licences.py::test_the_notice_file_names_every_runtime_package`.
Log: `tore/codex-ci-windows.txt`. Der eingecheckten Entwicklungsvorschau fehlten
Matplotlib und sieben weitere Komponenten: contourpy, cycler, fonttools,
kiwisolver, pyparsing, python-dateutil und six.

Matplotlib 3.11.2 war lokal bereits installiert und in `constraints.txt`
festgeschrieben. `pyproject.toml` nennt seit Commit
`9bb1542b22e5b0329efa82e2f1bb6a58cbea62b5` vom 23.09.2026, 21:36:36 +02:00,
`matplotlib>=3.8` ausdrücklich im Laufzeit-Extra `geom`. Die tatsächlich von
`importlib.metadata` gefundenen Solidon-Metadaten nannten diese Anforderung
jedoch noch nicht. Die Lizenzbaumsuche zählte deshalb lokal nur 42 statt 50
Komponenten; die frische CI-Installation las bereits die richtige Anforderung.

## Herkunft und Vorrang der zweiten lokalen Metadatenquelle

Der Build-Backend ist weiterhin **`setuptools.build_meta`**, laut Git-Blame
seit 27.08.2026; die Untergrenze `setuptools>=77.0.3` steht seit 07.09.2026.
Lokal installiert ist Setuptools 84.0.0. Es gab für diesen Fix keinen
Build-Systemwechsel.

Im Hauptbaum liegt eine durch `.gitignore` ausdrücklich ignorierte
`F:\3D Druck\solidon3d.egg-info`. Ihre Dateien waren vor dem Fix zuletzt am
23.09.2026 um **16:29:18** geschrieben worden, also vor der Matplotlib-
Abhängigkeit. Das ist nachgewiesener Altbestand einer früheren lokalen
Metadatenerzeugung. **Welcher damalige Befehl ihn erzeugte, ist nicht belegt.**
Es wird weder eine frühere andere Backendwahl noch ein bestimmter pip-Aufruf
als Ursache behauptet.

Die zuerst freigegebene Auffrischung lief mit dem vorhandenen Interpreter:

```text
F:\3D Druck\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation --no-index --disable-pip-version-check -e ".[dev,geom,ui,agent,brep]"
```

Sie endete mit Exit 0 und schrieb die richtige neue
`F:\3D Druck\.venv\Lib\site-packages\solidon3d-0.5.0.dist-info`.
Im Prozess mit cwd `F:\3D Druck` fand `importlib.metadata.distributions()`
danach jedoch weiterhin zuerst `solidon3d.egg-info` ohne Matplotlib und erst
danach die neue installierte `.dist-info` mit Matplotlib. Der jetzige
Editable-Bau ließ den alten Root-Ordner unverändert.

Deshalb wurde zusätzlich der bereits vorhandene Setuptools-Backend zur
**Erneuerung dieses erzeugten Root-Bestands aus derselben pyproject.toml**
aufgerufen:

```text
F:\3D Druck\.venv\Scripts\python.exe -c "from setuptools import setup; setup(script_args=['egg_info'])"
```

Auch dieser Aufruf endete mit Exit 0. Er **synchronisiert beide weiterhin
vorhandenen Metadatenquellen**, beseitigt die zweite Quelle nicht. Kein Ordner
und kein unbekanntes Artefakt wurden gelöscht. Bei einer späteren Änderung
der Projektanforderungen kann ein erneut veralteter Root-Bestand deshalb
wieder Vorrang haben; der Hauptagent ergänzt dafür die Entwicklungsanweisung.

Der Melde-/Belegpfad ist jetzt konkret: Der bestehende Test
`test_the_runtime_tree_is_actually_walked` verlangt zusätzlich `matplotlib`
und meldet bei genau diesem Altbestand
`matplotlib is missing from the checked tree`. Zur Diagnose werden die
Solidon-Distributionen samt Metadatenpfad und Matplotlib-Anforderung gelesen.
`codex-notices-metadata-before.json`, `-after.json` und `-final.json` halten
den alten Stand, den noch überschatteten Stand nach pip und den endgültigen
Stand fest. **Alle installierten Paketnamen und Versionen sind vor/nachher
identisch** (`version_changes: {}`). Es wurde kein Fremdpaket installiert,
nachinstalliert oder aktualisiert.

## Erzeugnis und Prüfungen

Nach der Metadatenkorrektur schlugen vor der Erzeugung lokal exakt dieselben
beiden CI-Tests fehl und nannten dieselben acht fehlenden Pakete. Danach wurde
`THIRD-PARTY-NOTICES.md` über den vorhandenen Generator neu geschrieben:

```text
F:\3D Druck\.venv\Scripts\python.exe tools/make_licence_notices.py --output THIRD-PARTY-NOTICES.md --manifest F:\3D Druck.review-050\reports\codex-notices-manifest.json
```

Die Beilage enthält nun **50 Laufzeitkomponenten** einschließlich sämtlicher
vollständiger Wheel-Lizenztexte. Sie bleibt ausdrücklich die Windows-
Entwicklungsvorschau; die spätere Kundenbeilage entsteht je Plattform aus
deren Endartefakt-SBOM. Keine manuelle Textangleichung und keine Testabsenkung.

| Prüfung | Ergebnis | Beleg unter `reports` |
|---|---|---|
| Editable-Auffrischung, nur Solidon | Exit **0** | `codex-notices-editable-refresh.txt` |
| Root-egg-info aus pyproject erneuern | Exit **0** | `codex-notices-egg-info-refresh.txt` |
| Beide ursprünglichen CI-Fälle vor Generatorlauf | **2 fehlgeschlagen**, Exit **1** | `codex-notices-before.txt` |
| Vorhandener Beilagengenerator | **50 Komponenten**, Exit **0** | `codex-notices-generate.txt` |
| `test_licences.py` und `test_licence_notices.py` | **67 bestanden**, 13,96 s, Exit **0** | `codex-notices-tests.txt` |
| Danach gezielt ergänzter Matplotlib-Baumwächter | **1 bestanden**, Exit **0** | `codex-notices-runtime-guard.txt` |
| Gegenprobe dieses Wächters mit gesicherten alten `Requires-Dist` im isolierten Prozess | **1 fehlgeschlagen**, Exit **1**, erwartete Matplotlib-Meldung | `codex-notices-stale-guard.txt`, Skript `codex_notices_stale_guard.py` |
| Generator `--check` gegen Beilage und Manifest | Exit **0** | `codex-notices-generator-check.txt` |
| `tools/check_env.py`, ohne `--install`/`--freeze` | Exit **0**, entspricht `constraints.txt` | `codex-notices-check-env.txt` |
| Ruff / Format beider betroffenen Testdateien | jeweils Exit **0** | `codex-notices-ruff.txt`, `codex-notices-format.txt` |

Zusätzlicher Produktdiff dieses Auftrags: nur erzeugte
`THIRD-PARTY-NOTICES.md` und ein weiterer Pflichtname im bestehenden
`tests/test_licences.py`. Der frühere PyInstaller-Fix bleibt separat in seinen
drei Dateien erhalten. Kein Commit, Push oder Versionswechsel; fremde
Änderungen wurden nicht angefasst.
