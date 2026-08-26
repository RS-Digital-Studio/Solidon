# Gebietsbericht: Szene, Register, expressions/types/changes

Grundlage: `AGENTS.md`, `.claude/rules/kern.md`, `dateiformat.md`, `operationen.md`, Bauplan §11–§16, §21, §32. Register in `ROADMAP.md` gegengelesen — keiner der Befunde steht dort. Prüfskripte unter `review-szene\`.

## Hoch

### 1 [hoch] Cache-Schlüssel deckt fremde Objekte nicht — Cache liefert falsche Geometrie — VERIFIZIERT
`app/core/scene/hashing.py:65-80`, `evaluate.py:1080-1120`, `geom/ops.py:616`, `sketch/ops.py:102,187`

`operation_hash` deckt Op, Parameter, Hashes der **eigenen** Eingänge, Profil, Qualität, Startwert — nicht aber fremde Objekte, die drei Ops aus `ctx.scene.objects` lesen: `align_to_feature` (Zielobjekt), `sketch_extrude` mit `up_to` (`consumes=0`), die Skizzenebene `feature:<id>` bei allen vier `sketch_*`-Ops.

Gemessen: Platte um 40 mm verschoben → ausgerichteter Körper bleibt mit Cache bei x=-25,0, ohne Cache x=+15,0. Quader 10→30 mm → Extrusion `up_to="face_top"` bleibt mit Cache bei z=10,0, frisch z=30,0. Der Docstring von `_height_of` verspricht „wächst der Körper darunter, wächst dieser mit" — hält genau nicht. `disk_backed_cache()` läuft, der falsche Eintrag überlebt das Schließen.

**Fix:** In `_with_nested_context` neben `kind=="source"` einen Zweig für `kind=="feature"` und `up_to`/Skizzenebene, der den Objekt-Hash des benannten Trägers mitgibt (`context[f"#{spec.name}"] = hashes[objekt_id]`).

### 2 [hoch] Drei Dokumentänderungen kommen ohne Freischaltung durch — VERIFIZIERT
`scene/history.py:416` (`change_params`), `:466` (`change_inputs`), `:516` (`change_kernel`)

`History.apply` ruft `activation.require(activation.CHANGE)`; die drei Änderungsmethoden nicht, schreiben aber direkt in `document.ops`. Gemessen mit `Activation(days_left=0)`: apply blockiert, change_params/change_inputs laufen durch (Bohrungsdurchmesser 3,0→25,0). Über die Oberfläche erreichbar (`ui/session.py:699,716,731`). Nach Ablauf der Demo bleibt jeder Schritt umparametrierbar, Speichern ist frei → vollständige Umkonstruktion möglich.

**Fix:** `activation.require(activation.CHANGE)` als erste Zeile in allen dreien, je ein Fall in `test_licence_boundary.py`.

### 3 [hoch] `Feature.recognised` überlebt den Plattencache nicht — Merkmale verwaisen — VERIFIZIERT
`scene/cache.py:227-253`

`_feature_to_data` schreibt `recognised` nicht; `_feature_from_data` baut ohne das Feld, also Vorgabe `True`. Gemessen: vorher `recognised=False`, nach Cache `True`. `evaluate.py:805` filtert `f.recognised` — kommt der Baustein-Schritt aus dem Cache, wandert das Merkmal in `checked`, findet keinen Partner, verwaist. Zwilling des `created_by`-Fixes vom 23.08.

**Fix:** `"recognised": feature.recognised` schreiben, `recognised=data.get("recognised", True)` lesen.

## Mittel

### 4 [mittel] Projektdatei hat keine Grenze für die entpackte Größe — VERIFIZIERT
`scene/project.py:352-435` — `check_unpacked` existiert (`ingest/loader.py:143`), wird von `scene/project.load` nicht gerufen. Gemessen: 306 KB Datei → 314 MB entpackt (1027:1), load() in 0,23 s durch. §32 verlangt die Grenze auch für die Projektdatei (reist zwischen Leuten, §16.2). **Fix:** in `load()` `sum(info.file_size …)` gegen `MAX_FILE_BYTES` prüfen.

### 5 [mittel] Nachträgliche Parameteränderung ist nicht rücknehmbar — Strg+Z trifft anderen Schritt — VERIFIZIERT
`scene/history.py:416-464`, `ui/session.py:696-706` — `change_params` legt keine Transaktion an; `undo()` nimmt die letzte Transaktion, also einen anderen Schritt. Gemessen: alter Wert 3,0 unwiederbringlich weg, Strg+Z entfernt die ganze Bohrung. Gilt auch für `change_inputs`/`change_kernel`. Bricht `oberflaeche.md`: „jeder Wert nachträglich änderbar". **Fix:** über eine Transaktion mit Vorher-/Nachher-Fassung führen (Format kennt `DocumentChange`, v5).

### 6 [mittel] NaN in einem Op-Parameter läuft ungehindert durch — VERIFIZIERT
`registry/params.py:167-199` — `is_less`/`is_greater` sind für NaN falsch, NaN besteht jede Grenze. `.p3d` mit `{"factor": NaN}` an `scale_object`: kein Halt, 10 verwaiste Merkmale, `RuntimeWarning: invalid value in det`. `json.loads` akzeptiert `NaN`, `json.dumps` schreibt es zurück → Solidon erzeugt Dateien, die strikte JSON-Leser ablehnen. **Fix:** `math.isfinite` in `_coerce`, `json.dumps(..., allow_nan=False)` in `project.save`.

### 7 [mittel] `load()` lässt einen `IndexError` roh durch — VERIFIZIERT
`scene/project.py:450-463`, `serialise.py:468` — Fang deckt `KeyError, ValueError, TypeError`; `finding_from_data` greift positionell auf `location[0..2]`, `IndexError` erbt von `LookupError`. `report.json` mit `"location":[1.0]` → rohe Ausnahme beim Öffnen (Regel 17). Zweiter Fall: `"location":"hoch"` läuft durch → `('h','o','c')`, Kamera fährt zu drei Buchstaben. Gleiche Lücke in `cache.DiskCache.get` über `colour[0..2]`. **Fix:** `IndexError` fangen, `isinstance(location, list|tuple) and len==3` prüfen.

### 8 [mittel] Überzählige Eingänge lassen Körper lautlos verschwinden — VERIFIZIERT
`evaluate.py:1133-1169`, `:364-366` — `_missing_inputs` prüft nur die Untergrenze; danach entfernt `evaluate` jeden nicht wieder ausgegebenen Eingang. `rename_object` (`consumes=1`) mit `in:["obj_1","obj_2"]`, `out:["obj_1"]` → `obj_2` weg, kein Ton. §15.2: „Objektzahländerung hält an statt zu raten". `History._plan` fängt es beim Anlegen, eine geöffnete/handbearbeitete Datei geht vorbei. Nachbar: `change_kernel` prüft `consumes` des Zwillings nicht. **Fix:** auch `len(inputs) > consumes` melden; in `change_kernel` `consumes` gegen `len(entry.inputs)` prüfen.

### 9 [mittel] Lesekopie von `ctx.scene` ist an zwei Stellen keine — Regel 3 hat ein Loch — VERIFIZIERT
`evaluate.py:297-306` — kopiert werden `objects`, `parameters`, `fits`, je Objekt `features`; **nicht** `SceneObject.material_slots` (list) und `Feature.params` (dict). Eine Op mit `material_slots.append(...)` erreicht das Ergebnis. Zwilling des Fixes vom 25.08. **Fix:** `material_slots=list(...)`, Merkmale mit `replace(f, params=dict(f.params))`.

### 10 [mittel] §32-Warnhinweis wird auf zwei Wegen nicht eingelöst — VERIFIZIERT
`scene/foreign.py:35`, `cli/main.py:127`, `ui/session.py:129-134` — `foreign.findings_for` hat nur `session.py` als Aufrufer. (a) **CLI warnt nie**: `cli/main.py` lädt und rechnet inkl. `create_from_scad`; Regel 11 greift, die zweite Hälfte (§32-Warnung) fehlt. Auch `orphans.check` und `part_check.check` haben nur `session.py`. (b) **Im Fenster** wird `pending_foreign_check=False` **vor** `run_evaluation()` gesetzt; scheitert die Auswertung, ist das Flag verbraucht — die Warnung kommt nie mehr, ausgerechnet für die Datei, die beim Rechnen eines fremden Programms scheiterte. **Fix:** `findings_for` in `project.load` ziehen (Befunde in den Bericht, den `load` ohnehin baut); Flag erst nach Übergabe löschen.

## Gering

- **11** `Feature.params` wechselt beim Cache von Tupel auf Liste (`cache.py:227-253`); `dict(frisch.params)==dict(warm.params)` False, `Operation.matches`-Abdrücke fallen auseinander. VERIFIZIERT.
- **12** `FEATURE_TITLES` kennt `sphere`/`torus` nicht (`registry/registry.py:269-277`); latent, da keine Op sie in `applies_to` deklariert. Fix: gegen `get_args(FeatureKind)` prüfen.
- **13** Zwei Fehlertitel behaupten „Ausdruck lässt sich nicht lesen" für lesbare Ausdrücke mit falschem Ergebnis (Division/Overflow) — `expressions.py:67-78,198,287`. VERIFIZIERT.
- **14** `FIT_TOLERANCE` verweist auf einen Roadmap-Punkt, den es nicht gibt (`fits.py:44`, lebt nur im Archiv unter abgehaktem Punkt). VERIFIZIERT.
- **15** Variantenname schreibt die Zahl mit Punkt statt lokalisiert (`variants.py:207`) → „Deckel Variante 0.15" im Objektbaum/3MF. PLAUSIBEL.
- **16** `values()` (gerundet) und `build()` (ungerundet) rechnen dieselbe Beschriftungszahl zweimal (`variants.py:140` vs `:217`). PLAUSIBEL.

## Geprüft und in Ordnung
Kerntrennung (Qt gesperrt importierbar); zweimal auswerten identisch; Speicher-Roundtrip bitgleich; gleichnamige Quellen aus verschiedenen Ordnern (`embedded_source_path` + `taken`); Migrationskette 1→11 lückenlos, v11-Ablehnung; Regel 12 (`_check_relative` gegen `/etc`, `C:/`, `..`, UNC, Zip-Slip auf jedem Eintrag); Regel 10 (eigener Parser, Tiefe 32); Zyklenerkennung; Passungen/`auto:`; Registerkonsistenz (91 Ops, `produces_from`/`depends_on` gültig, Startwerte); Kürzel eindeutig; Undo/Redo auf Transaktionsebene inkl. `DocumentChange`; Cache nur nach vollem Lauf und `to_disk=False` nach `ctx.ask`; LRU-`touch` auf Windows; `scene.fits` in der Lesekopie geschützt.

**Kann das so rein: nein** — drei hohe Befunde (Cache-Schlüssel, verwaiste Merkmale, offene Lizenzgrenze), alle mit wenigen Zeilen zu schließen.
