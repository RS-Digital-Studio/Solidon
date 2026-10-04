"""Native Einzeldateiabnahme: jeder Fall im echten Fenster, jeder Schritt mit Bild (RM-184).

    .venv\\Scripts\\python.exe tools/file_acceptance.py inventory --manifest <json> --out <ordner>
    .venv\\Scripts\\python.exe tools/file_acceptance.py inventory --source <bestand> --out <ordner>
    .venv\\Scripts\\python.exe tools/file_acceptance.py run --out <ordner> [--first 1] [--last 9]
    .venv\\Scripts\\python.exe tools/file_acceptance.py report --out <ordner>

``--manifest`` nimmt das Manifest des Dateiaudits
(``ui-audit/2026-09-15-files/manifest.json``: 187 Fälle in seiner Zählung),
``--source`` einen Ordner wie ``F:\\3D Dateien``.

Gebaut aus dem Serienlauf des Dateiaudits vom 15.09.2026 (``audit.py``: ein
frischer Prozess je Datei, das echte Fenster, ein eigenes Nutzerprofil je
Fall) und seinem Kundenweg an der Bohrung (``detail_ui.py``). Je Fall:

1. **Import** über ``MainWindow.open_path`` — der Weg von Menü, Zuletzt-Liste
   und Ziehen; der Systemdialog gehört dem Betriebssystem.
2. **Erkennung**: Merkmale je Körper nach Art, dazu die funktionalen Gruppen.
3. **Maßänderung** an einem repräsentativen Merkmal (Bohrung vor Langloch vor
   Gewinde vor Kegel vor Zapfen vor Fläche): gewählt mit einem Klick in den
   Objektbaum, geändert am ersten Längenfeld des Merkmalfensters, das ein Maß
   und keine Lage nennt — gesetzt über das Feld wie im Kundenweg des Audits
   (``detail_ui.py``), nicht getippt; ob das Tippen dasselbe tut, gehört zur
   Fensterabnahme.
4. **Vorschau**, **Übernehmen** (der Knopf des Merkmalfensters),
   **Rückgängig**, **Wiederholen**.

Je Schritt ein Bild des Fensters und je Körper ein Netzabdruck (SHA-256 über
Ecken und Dreiecke, ein exakter Körper über seine Vernetzung im selben
Prozess). Geprüft wird, dass Rückgängig den Stand des Imports
wiederherstellt, Wiederholen den übernommenen, dass die Vorschau zeigt, was
übernommen wird, und dass die Änderung etwas geändert hat. An der Drillholder-
Datei geht das für **jede** Bohrung (``--bores`` oder ``BORE_CASES``).

**Ausgabe außerhalb des Repositorys** (``--out``): Bilder und Profile gehören
nicht in den Arbeitsbaum. Je Fall ein Ordner ``cases/<nummer>`` mit
``result.json``, ``process.json``, Protokollen und Bildern; dazu
``summary.json`` und ``summary.md``. Ein abgeschlossener Fall wird beim
nächsten Lauf übersprungen (``--again`` fährt ihn neu).

Kein Testlauf und nicht im Tor: Der Lauf braucht ein echtes Fenster und
dauert. Seine Logik — Bestand, Wahl des Merkmals, neue Zahl, Abgleich der
Abdrücke, Bericht — prüft ``tests/test_file_acceptance.py`` ohne Fenster.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
import zipfile
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

#: Was als Fall zählt — dieselben Endungen wie im Dateiaudit vom 15.09.
MODEL_SUFFIXES: frozenset[str] = frozenset(
    {".stl", ".3mf", ".step", ".stp", ".glb", ".svg", ".p3d"}
)

#: Fälle, an denen jede Bohrung einzeln abgenommen wird — Teil des Dateinamens.
BORE_CASES: tuple[str, ...] = ("drill-holder",)

#: Welches Merkmal für die Maßänderung steht: das erste dieser Arten, das ein
#: Längenfeld trägt. ``group`` ist der Boden einer Kammer, einer Nut oder eines
#: Kanals (*Kammer ändern*, RM-184). Wulst, Kugel und Muster ändert *Merkmal
#: ändern* ebenso — am 1x1-tray trugen nur die Wülste ein Maß.
FEATURE_PRIORITY: tuple[str, ...] = (
    "hole",
    "slot",
    "thread",
    "group",
    "cone",
    "pin",
    "fillet",
    "torus",
    "sphere",
    "pattern",
    "face",
)

#: Wie viele Merkmale höchstens versucht werden, bis eines ein Längenfeld hat.
MOST_FEATURE_TRIES = 12

#: Wie viele Merkmale einer Art höchstens darunter sind: Am 1x1-tray trugen
#: vier Kegel und sieben Rundungen kein Längenfeld und verbrauchten die
#: Versuche, bevor ein Wulst drankam.
MOST_TRIES_PER_KIND = 3

#: Was ein Durchgang notiert, wenn das Merkmalfenster kein Längenfeld zeigt.
NO_LENGTH_FIELD = "kein Längenfeld am Merkmal"

#: Was ein Durchgang notiert, wenn die Vorschau jede versuchte Zahl absagt —
#: am 1x1-bin brach die breitere Kammer durch die Wand.
REFUSED = "jede Maßänderung abgesagt"

#: Die Stufe eines Falls, an dem kein versuchtes Merkmal eine Änderung trug —
#: keine Abweichung, denn geprüft wurde nichts. Warum, sagen ``tried`` und
#: ``refusals`` im Ergebnis.
UNCHANGEABLE = "kein Merkmal ließ sich ändern"

#: Feldtitel, die eine Lage nennen und kein Maß. Am Drillholder stand
#: „Merkmal verschieben — X“ vor „Bohrung ändern — Durchmesser“, und der Lauf
#: verschob jede Bohrung, statt ihr Maß zu ändern.
POSITION_TITLES: frozenset[str] = frozenset({"X", "Y", "Z"})

#: Wie lange ein Fall höchstens dauern darf (Sekunden), Import und Schritte zusammen.
CASE_TIMEOUT = 600.0

#: Dasselbe für einen Fall mit jeder Bohrung: Der Drillholder brauchte offscreen
#: unter Fremdlast 904 s für 23 von 29 Bohrungen.
BORE_CASE_TIMEOUT = 3600.0

#: Wie oft ein Zwischenstand geschrieben wird, bevor der Fall abbricht.
WRITE_ATTEMPTS = 20

#: Wie lange ein einzelner Schritt im Fenster warten darf (Sekunden).
STEP_TIMEOUT = 180.0

#: Das Messprofil des Audits: kein Materialurteil, nur ein fester Rahmen.
PRINTER = "centauri-carbon-2"
MATERIAL = "petg"

STEPS: tuple[str, ...] = (
    "01-import",
    "02-selection",
    "03-preview",
    "04-applied",
    "05-undo",
    "06-redo",
)


@dataclass(frozen=True, slots=True)
class Case:
    """Ein Fall der Abnahme: eine Datei oder ein Archivmitglied."""

    number: int
    relative: str
    path: str
    suffix: str
    bores: bool = False


# --- Bestand -----------------------------------------------------------------


def outside_the_repository(out: Path) -> Path:
    """Der Ausgabeordner — nie im Arbeitsbaum: Bilder und Profile reisen nicht mit."""
    resolved = out.resolve()
    if resolved == ROOT or ROOT in resolved.parents:
        raise SystemExit(
            f"Der Ausgabeordner liegt im Repository: {resolved}. Wählen Sie einen Ordner außerhalb."
        )
    return resolved


def is_bore_case(relative: str) -> bool:
    """Ob an diesem Fall jede Bohrung einzeln abgenommen wird."""
    name = Path(relative.replace(" :: ", "/")).name.lower()
    return any(marker in name for marker in BORE_CASES)


def cases_from_source(source: Path, out: Path) -> list[Case]:
    """Der Bestand eines Ordners in der Zählweise des Audits.

    Modelle und Projekte direkt, Archivmitglieder ausgepackt (``archive-models``
    im Ausgabeordner), Sicherungen ``.vor-reparatur`` als Projektkopie — die
    Originale bleiben unberührt. Nummeriert wird in der Reihenfolge der Pfade,
    Archivmitglieder hinter allen Dateien.
    """
    direct: list[Case] = []
    members: list[tuple[str, bytes, str]] = []
    copies = out / "archive-models"
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        relative = str(path.relative_to(source))
        suffix = path.suffix.lower()
        if suffix in MODEL_SUFFIXES:
            direct.append(Case(0, relative, str(path), suffix, is_bore_case(relative)))
        elif suffix == ".vor-reparatur":
            copies.mkdir(parents=True, exist_ok=True)
            target = copies / f"backup-{len(direct) + 1}.p3d"
            shutil.copyfile(path, target)
            direct.append(Case(0, relative, str(target), ".p3d"))
        elif suffix == ".zip" and zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as archive:
                for info in archive.infolist():
                    inner = Path(info.filename).suffix.lower()
                    if not info.is_dir() and inner in MODEL_SUFFIXES:
                        members.append(
                            (f"{relative} :: {info.filename}", archive.read(info), inner)
                        )
    numbered = [
        Case(number, case.relative, case.path, case.suffix, case.bores)
        for number, case in enumerate(direct, 1)
    ]
    for offset, (relative, payload, suffix) in enumerate(members):
        copies.mkdir(parents=True, exist_ok=True)
        number = len(numbered) + 1
        target = copies / f"{number}-{offset}{suffix}"
        target.write_bytes(payload)
        numbered.append(Case(number, relative, str(target), suffix, is_bore_case(relative)))
    return numbered


def cases_from_manifest(manifest: Path) -> list[Case]:
    """Die Fälle eines Audit-Manifests — dieselben Nummern, dieselben Dateien.

    Gezählt wird wie im Audit: Modelle, Projekte, ausgepackte Archivmitglieder
    und Sicherungen mit eigener Prüfkopie (``audit_path``).
    """
    entries = json.loads(manifest.read_text(encoding="utf-8"))
    found: list[Case] = []
    for entry in entries:
        if entry.get("suffix") not in MODEL_SUFFIXES and "audit_path" not in entry:
            continue
        path = str(entry.get("audit_path", entry["path"]))
        suffix = Path(path).suffix.lower()
        found.append(
            Case(
                int(entry["id"]),
                str(entry["relative"]),
                path,
                suffix,
                is_bore_case(str(entry["relative"])),
            )
        )
    return found


def write_json(path: Path, data: object, attempts: int = WRITE_ATTEMPTS) -> None:
    """Schreibt über eine Nebendatei und ersetzt dann — mit Wiederholung.

    Windows sperrt eine gerade gelesene Datei kurz (Virenprüfer, Indexdienst):
    Am Drillholder brach ein Fall nach 23 von 29 Bohrungen mit
    ``OSError: [Errno 22]`` beim Zwischenstand ab. Ersetzt wird erst, wenn die
    Nebendatei vollständig ist; ein Leser sieht nie eine halbe Datei.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=1, default=str).encode("utf-8")
    temporary = path.with_name(path.name + ".tmp")
    for attempt in range(attempts):
        try:
            temporary.write_bytes(payload)
            temporary.replace(path)
            return
        except OSError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.2 * (attempt + 1))


def read_cases(out: Path) -> list[Case]:
    return [Case(**entry) for entry in json.loads((out / "cases.json").read_text(encoding="utf-8"))]


# --- Wahl und Abgleich ----------------------------------------------------------


def group_anchors(groups: Sequence[str]) -> set[str]:
    """Die Böden von Kammer, Nut und Kanal aus den Gruppenzeilen der Erkennung.

    Eine Zeile heißt ``art/variante:anker`` (:meth:`WindowFlow._recognition`);
    ein Anschluss mit Durchgang hat kein Innenmaß und zählt nicht.
    """
    found: set[str] = set()
    for line in groups:
        kind, _slash, rest = line.partition("/")
        variant, _colon, anchor = rest.partition(":")
        if kind in ("chamber", "channel") and variant != "passage" and anchor:
            found.add(anchor)
    return found


def ranked_features(
    objects: Mapping[str, Mapping[str, str]],
    anchors: Mapping[str, set[str]] | None = None,
) -> list[tuple[str, str]]:
    """Die Merkmale für die Maßänderung in der Folge, in der sie versucht werden.

    ``objects`` nennt je Körper seine Merkmale mit Art (``{"obj_1": {"hole_6":
    "hole"}}``), ``anchors`` je Körper die Böden seiner Kammern und Kanäle —
    sie stehen als ``group`` in :data:`FEATURE_PRIORITY`: Am 1x1-bin trägt
    keine Fläche ein Längenfeld, die Kammer schon. Zuerst die Art, bei
    gleicher Art der Körper, dann die Nummer — so trifft jeder Lauf dieselben
    Merkmale. Je Art höchstens :data:`MOST_TRIES_PER_KIND`, damit jede Art an
    die Reihe kommt.
    """
    ranked: list[tuple[int, str, int, str]] = []
    for object_id, features in objects.items():
        floors = (anchors or {}).get(object_id, set())
        for feature_id, own in features.items():
            kind = "group" if feature_id in floors else own
            if kind not in FEATURE_PRIORITY:
                continue
            number = feature_id.rpartition("_")[2]
            ranked.append(
                (
                    FEATURE_PRIORITY.index(kind),
                    object_id,
                    int(number) if number.isdigit() else 0,
                    feature_id,
                )
            )
    chosen: list[tuple[str, str]] = []
    per_kind: dict[int, int] = {}
    for rank, object_id, _number, feature_id in sorted(ranked):
        if per_kind.get(rank, 0) < MOST_TRIES_PER_KIND:
            per_kind[rank] = per_kind.get(rank, 0) + 1
            chosen.append((object_id, feature_id))
    return chosen


def choose_feature(objects: Mapping[str, Mapping[str, str]]) -> tuple[str, str] | None:
    """Das erste Merkmal aus :func:`ranked_features` — oder keines."""
    ranked = ranked_features(objects)
    return ranked[0] if ranked else None


def first_with_a_length_field(
    candidates: Sequence[tuple[str, str]],
    cycle: Callable[[tuple[str, str]], dict[str, Any]],
    tries: int = MOST_FEATURE_TRIES,
) -> tuple[list[str], dict[str, Any] | None]:
    """Der erste Durchgang an einem Merkmal mit Längenfeld, und wer davor versucht wurde.

    **Ein Merkmal ohne Längenfeld ist kein Fall der Maßänderung**: Am 1x1-bin
    stand vorn ein Kegel, dessen Merkmalfenster nur einen Winkel trägt. Ebenso
    wenig eines, an dem die Vorschau jede versuchte Zahl absagt (:data:`REFUSED`).
    Versucht wird das nächste, höchstens ``tries`` Merkmale; trägt keines,
    bleibt der letzte Durchgang mit seinem Vermerk stehen.
    """
    tried: list[str] = []
    record: dict[str, Any] | None = None
    for chosen in candidates[:tries]:
        record = cycle(chosen)
        tried.append(chosen[1])
        if record.get("note") not in (NO_LENGTH_FIELD, REFUSED):
            break
    return tried, record


def bore_ids(features: Mapping[str, str]) -> list[str]:
    """Alle Bohrungen eines Körpers, nach ihrer Nummer."""

    def number(feature_id: str) -> int:
        tail = feature_id.rpartition("_")[2]
        return int(tail) if tail.isdigit() else 0

    return sorted((name for name, kind in features.items() if kind == "hole"), key=number)


def changed_value(value: float) -> float:
    """Die neue Zahl einer Maßänderung: ein Zehntel mehr, mindestens ein halber Millimeter.

    Eine Null (ein Versatz) wird ein Millimeter. Gerundet auf zwei Stellen,
    wie das Feld sie zeigt — sonst stünde im Bericht eine Zahl, die niemand
    getippt haben kann.
    """
    if abs(value) < 1e-9:
        return 1.0
    step = max(abs(value) * 0.1, 0.5)
    return round(value + step, 2)


def size_field_first(names: Sequence[str]) -> int:
    """Welches Längenfeld die Maßänderung nimmt: das erste, das keine Lage nennt.

    Ein Feld heißt „<Handlung> — <Feld>“ (``accessibleName``, :data:`POSITION_TITLES`);
    trägt das Merkmalfenster nur Lagen, bleibt es beim ersten.
    """
    for index, name in enumerate(names):
        if name.rpartition(" — ")[2].strip() not in POSITION_TITLES:
            return index
    return 0


def values_to_try(value: float) -> tuple[float, ...]:
    """Die Zahlen einer Maßänderung, in der Folge, in der sie versucht werden.

    Zuerst mehr (:func:`changed_value`), dann ebenso viel weniger — eine
    größere Kammer bricht durch eine dünne Wand, eine kleinere nie. Weniger
    nur, solange die Zahl positiv bleibt.
    """
    larger = changed_value(value)
    if abs(value) < 1e-9:
        return (larger,)
    smaller = round(value - max(abs(value) * 0.1, 0.5), 2)
    return (larger, smaller) if smaller > 0.0 else (larger,)


def mesh_digest(vertices: Any, faces: Any) -> str:
    """Der Abdruck eines Netzes: SHA-256 über Ecken und Dreiecke, wie im Audit."""
    import numpy as np

    return hashlib.sha256(
        np.ascontiguousarray(vertices).tobytes() + np.ascontiguousarray(faces).tobytes()
    ).hexdigest()


def body_digest(mesh: Any) -> str:
    """Der Abdruck eines Körpers — ein exakter über seine Vernetzung.

    Die Vernetzung ist im selben Prozess für denselben Körper dieselbe; über
    Prozesse hinweg wird nicht verglichen. Ein Körper, der sich nicht vernetzen
    lässt, hat keinen Abdruck (leere Zeichenkette) — der Abgleich nennt ihn
    dann ungleich, statt ihn zu übergehen.
    """
    from app.core.errors import AppError
    from app.core.geom.mesh import as_mesh_data

    try:
        data = as_mesh_data(mesh)
    except AppError:
        return ""
    return mesh_digest(data.raw.vertices, data.raw.faces)


def compared(
    states: Mapping[str, Mapping[str, str]], preview: Mapping[str, str] | None
) -> dict[str, bool | None]:
    """Was die Abdrücke über die Schritte sagen — ``None`` heißt: nicht prüfbar.

    ``states`` nennt je Schritt (:data:`STEPS`) die Abdrücke je Körper.
    """

    def same(first: str, second: str) -> bool | None:
        if first not in states or second not in states:
            return None
        return dict(states[first]) == dict(states[second])

    changed = same("01-import", "04-applied")
    preview_matches: bool | None = None
    if preview is not None and "04-applied" in states:
        applied = states["04-applied"]
        shown = {key: value for key, value in preview.items() if key in applied}
        preview_matches = bool(shown) and all(applied[key] == value for key, value in shown.items())
    return {
        "changed": None if changed is None else not changed,
        "undo_restores_import": same("01-import", "05-undo"),
        "redo_restores_applied": same("04-applied", "06-redo"),
        "preview_shows_result": preview_matches,
    }


def passed(checks: Mapping[str, bool | None]) -> bool:
    """Bestanden: jede prüfbare Aussage stimmt, Rückgängig und Wiederholen sind geprüft."""
    if checks.get("undo_restores_import") is None or checks.get("redo_restores_applied") is None:
        return False
    return all(value is not False for value in checks.values())


def case_stage(record: Mapping[str, Any]) -> str:
    """Die Stufe eines Falls nach seinem letzten Durchgang.

    ``done`` oder ``abweichung`` nur, wenn eine Änderung übernommen und geprüft
    wurde; trägt der letzte Durchgang einen Vermerk (kein Längenfeld, jede Zahl
    abgesagt), hat sich kein Merkmal ändern lassen (:data:`UNCHANGEABLE`). Am
    1x1-tray hieß das „abweichung“, obwohl kein Schritt etwas geprüft hatte.
    """
    if record.get("note"):
        return UNCHANGEABLE
    return "done" if passed(record.get("checks", {})) else "abweichung"


# --- Bericht ----------------------------------------------------------------------


def summary(out: Path, cases: Sequence[Case]) -> dict[str, Any]:
    """Alle Fälle in einer Übersicht — geschrieben als ``summary.json`` und ``summary.md``."""
    rows: list[dict[str, Any]] = []
    for case in cases:
        folder = out / "cases" / f"{case.number:03d}"
        result = _read(folder / "result.json")
        process = _read(folder / "process.json")
        row = {
            "number": case.number,
            "relative": case.relative,
            "stage": result.get("stage", "nicht gelaufen"),
            "exit_code": process.get("exit_code"),
            "timeout": process.get("timeout"),
            "seconds": process.get("wall_s"),
            "objects": len(result.get("objects", [])),
            "features": sum(len(entry.get("features", {})) for entry in result.get("objects", [])),
            "groups": sum(len(entry.get("groups", [])) for entry in result.get("objects", [])),
            "feature": result.get("selection", {}).get("feature"),
            "checks": result.get("checks", {}),
            "passed": bool(result.get("checks")) and passed(result.get("checks", {})),
            "bores": [
                {"feature": bore.get("feature"), "passed": passed(bore.get("checks", {}))}
                for bore in result.get("bores", [])
            ],
            "errors": result.get("errors", [])
            + ([result["harness_exception"]] if "harness_exception" in result else []),
        }
        rows.append(row)
    data = {
        "cases": len(rows),
        "ran": sum(1 for row in rows if row["exit_code"] is not None),
        "passed": sum(1 for row in rows if row["passed"]),
        "bores": sum(len(row["bores"]) for row in rows),
        "bores_passed": sum(1 for row in rows for bore in row["bores"] if bore["passed"]),
        "rows": rows,
    }
    write_json(out / "summary.json", data)
    (out / "summary.md").write_text(markdown(data), encoding="utf-8")
    return data


def _read(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def markdown(data: Mapping[str, Any]) -> str:
    """Der Bericht als Tabelle, ein Fall je Zeile."""
    lines = [
        "# Native Einzeldateiabnahme",
        "",
        f"Fälle: {data['cases']} · gelaufen: {data['ran']} · bestanden: {data['passed']}"
        f" · Bohrungen: {data['bores_passed']} von {data['bores']}",
        "",
        "| Nr. | Datei | Stufe | Exit | Sekunden | Körper | Merkmale | Gruppen | Merkmal"
        " | Geändert | Undo | Redo | Vorschau | Bestanden |",
        "|---:|---|---|---:|---:|---:|---:|---:|---|---|---|---|---|---|",
    ]

    def mark(value: object) -> str:
        return "ja" if value is True else "nein" if value is False else "-"

    for row in data["rows"]:
        checks = row.get("checks", {})
        seconds = row.get("seconds")
        cells = [
            row["number"],
            str(row["relative"]).replace("|", "/"),
            row["stage"],
            "-" if row["exit_code"] is None else row["exit_code"],
            "-" if seconds is None else f"{float(seconds):.1f}",
            row["objects"],
            row["features"],
            row["groups"],
            row["feature"] or "-",
            mark(checks.get("changed")),
            mark(checks.get("undo_restores_import")),
            mark(checks.get("redo_restores_applied")),
            mark(checks.get("preview_shows_result")),
            mark(row["passed"]),
        ]
        lines.append("| " + " | ".join(str(cell) for cell in cells) + " |")
    bores = [(row, bore) for row in data["rows"] for bore in row["bores"]]
    if bores:
        lines += ["", "## Jede Bohrung", "", "| Nr. | Bohrung | Bestanden |", "|---:|---|---|"]
        lines += [
            f"| {row['number']} | {bore['feature']} | {mark(bore['passed'])} |"
            for row, bore in bores
        ]
    failures = [row for row in data["rows"] if row["errors"]]
    if failures:
        lines += ["", "## Fehler", ""]
        for row in failures:
            first = str(row["errors"][0]).strip().splitlines()
            lines.append(f"- {row['number']} {row['relative']}: {first[-1] if first else ''}")
    return "\n".join(lines) + "\n"


# --- Lauf --------------------------------------------------------------------------


def run(out: Path, first: int, last: int, again: bool, timeout: float) -> int:
    """Je Fall ein frischer Prozess mit eigenem Profil — wie im Audit."""
    cases = read_cases(out)
    failures = 0
    for case in cases:
        if not first <= case.number <= last:
            continue
        folder = out / "cases" / f"{case.number:03d}"
        status = folder / "process.json"
        if status.exists() and not again:
            continue
        folder.mkdir(parents=True, exist_ok=True)
        print(f"START [{case.number:03d}] {case.relative}", flush=True)
        began = time.perf_counter()
        with (
            (folder / "stdout.log").open("w", encoding="utf-8") as stdout,
            (folder / "stderr.log").open("w", encoding="utf-8") as stderr,
        ):
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "child",
                    "--out",
                    str(out),
                    "--case",
                    str(case.number),
                ],
                stdout=stdout,
                stderr=stderr,
                cwd=ROOT,
                env={**os.environ, "PYTHONUTF8": "1"},
            )
            try:
                code = process.wait(
                    timeout=max(timeout, BORE_CASE_TIMEOUT) if case.bores else timeout
                )
                timed_out = False
            except subprocess.TimeoutExpired:
                process.kill()
                code = process.wait()
                timed_out = True
        write_json(
            status,
            {
                "exit_code": code,
                "timeout": timed_out,
                "wall_s": time.perf_counter() - began,
                "pid": process.pid,
            },
        )
        failures += int(code != 0 or timed_out)
        wall = time.perf_counter() - began
        print(f"END [{case.number:03d}] exit={code} timeout={timed_out} {wall:.1f}s", flush=True)
    summary(out, cases)
    return 1 if failures else 0


def child(out: Path, number: int) -> int:
    """Ein Fall im echten Fenster: Import, Erkennung, Änderung, Vorschau, Übernehmen, Undo, Redo."""
    case = next(entry for entry in read_cases(out) if entry.number == number)
    folder = out / "cases" / f"{number:03d}"
    folder.mkdir(parents=True, exist_ok=True)
    for key in ("APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
        os.environ[key] = str(folder / "profile")
    sys.path.insert(0, str(ROOT))
    import faulthandler

    faulthandler.enable()
    data: dict[str, Any] = {
        "case": asdict(case),
        "stage": "start",
        "errors": [],
        "questions": [],
        "dialogs": [],
        "states": {},
    }

    def persist() -> None:
        write_json(folder / "result.json", data)

    persist()
    # Erst nach dem Umbiegen der Nutzerordner: Die Anwendung liest sie beim Import.
    # Das Register füllt sonst ``main`` vor dem Fenster — wie im Audit hier.
    from app.core.bootstrap import load_operations
    from app.ui.app import build_application
    from tools.window_bench import shutdown_window

    load_operations()
    application, window = build_application([])
    session = window.session
    flow = WindowFlow(application, window, session, folder, data, persist)
    exit_code = 0
    try:
        flow.prepare()
        flow.run(case)
    except Exception:
        data["harness_exception"] = traceback.format_exc()
        persist()
        exit_code = 1
    finally:
        session.forget_changes()
        shutdown_window(window, application)
        data["shutdown_complete"] = True
        persist()
    return exit_code


class WindowFlow:
    """Die Schritte eines Falls am Fenster; jeder schreibt sein Bild und seine Abdrücke."""

    def __init__(
        self,
        application: Any,
        window: Any,
        session: Any,
        folder: Path,
        data: dict[str, Any],
        persist: Callable[[], None],
    ) -> None:
        self.application = application
        self.window = window
        self.session = session
        self.folder = folder
        self.data = data
        self.persist = persist

    # Warten und Aufnehmen ---------------------------------------------------------

    def pump(self, seconds: float = 0.3) -> None:
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            self.application.processEvents()
            time.sleep(0.01)

    def wait_for(self, done: Callable[[], bool], label: str, timeout: float = STEP_TIMEOUT) -> None:
        began = time.perf_counter()
        while time.perf_counter() - began < timeout:
            self.application.processEvents()
            self._sweep()
            if done():
                self.pump()
                self.data.setdefault("events", []).append(
                    {"step": label, "seconds": time.perf_counter() - began}
                )
                self.persist()
                return
            if self.data["errors"]:
                raise RuntimeError(f"{label}: {self.data['errors'][-1]}")
            time.sleep(0.01)
        raise TimeoutError(label)

    def new_result(self, previous: Any, label: str) -> None:
        self.wait_for(
            lambda: (
                self.session.last_result is not None
                and self.session.last_result is not previous
                and not self.session.busy
            ),
            label,
        )

    def _sweep(self) -> None:
        from PySide6.QtWidgets import QDialog, QLabel, QPushButton

        modal = self.application.activeModalWidget()
        if modal is None:
            return
        self.data["dialogs"].append(
            {
                "title": modal.windowTitle(),
                "text": [label.text() for label in modal.findChildren(QLabel)],
                "buttons": [button.text() for button in modal.findChildren(QPushButton)],
            }
        )
        if isinstance(modal, QDialog):
            modal.reject()
        else:
            modal.close()

    def shot(self, label: str) -> dict[str, str]:
        """Bild des Fensters und Abdruck je Körper für diesen Schritt."""
        self.pump()
        picture = self.window.screen().grabWindow(int(self.window.winId()))
        picture.save(str(self.folder / f"{label}.png"))
        result = self.session.last_result
        digests = {
            object_id: body_digest(entry.mesh) for object_id, entry in result.scene.objects.items()
        }
        self.data["states"][label] = digests
        self.persist()
        return digests

    # Die Schritte -----------------------------------------------------------------

    def prepare(self) -> None:
        self.session.failed.connect(
            lambda error: self.data["errors"].append(str(error)), self.window
        )
        self.session.importFailed.connect(
            lambda error: self.data["errors"].append(str(error)), self.window
        )
        self.session.askRequested.disconnect(self.window._on_ask)

        def answer(request: Any) -> None:
            choices = list(request.choices)
            selected = "mm" if "mm" in choices else (choices[0] if choices else "")
            self.data["questions"].append(
                {"question": str(request.question), "choices": choices, "answer": selected}
            )
            request.reply(selected)

        self.session.askRequested.connect(answer, self.window)
        # **Ein Zeitgeber räumt modale Fenster ab**, wie im Audit: Ein
        # ``exec()`` aus einem Ereignis heraus läuft in einer eigenen Schleife,
        # und die Warteschleife hier käme erst nach seinem Ende wieder dran.
        from PySide6.QtCore import QTimer

        self.sweeper = QTimer(self.window)
        self.sweeper.timeout.connect(self._sweep)
        self.sweeper.start(250)
        self.window.showMaximized()
        self.pump()
        self.session.start_new(PRINTER, MATERIAL)
        self.window._show_start_screen(False)
        self.new_result(None, "Neues Projekt")
        self.session.forget_changes()

    def run(self, case: Case) -> None:
        previous = self.session.last_result
        self.data["stage"] = "import"
        self.persist()
        began = time.perf_counter()
        self.window.open_path(Path(case.path))
        self.new_result(previous, "Import")
        self.data["import_s"] = time.perf_counter() - began
        self.window.viewport.reset_camera(follow_selection=False)
        self.shot("01-import")
        self.data["stage"] = "recognition"
        self.data["objects"] = self._recognition()
        self.persist()
        objects = {entry["id"]: entry["features"] for entry in self.data["objects"]}
        anchors = {entry["id"]: group_anchors(entry["groups"]) for entry in self.data["objects"]}
        if case.bores:
            self.data["bores"] = []
            for object_id, features in sorted(objects.items()):
                for feature_id in bore_ids(features):
                    prefix = f"bore-{feature_id}-"
                    try:
                        record = self._cycle(object_id, feature_id, prefix, restore=True)
                    except (TimeoutError, RuntimeError) as problem:
                        # Die Bohrung, an der der Fall hängen blieb, steht im
                        # Bericht — nicht nur die, die vorher bestanden.
                        self.data["bores"].append(
                            {"object": object_id, "feature": feature_id, "error": str(problem)}
                        )
                        self.persist()
                        raise
                    self.data["bores"].append(record)
                    self.persist()
        # Die Absagen aller versuchten Merkmale, nicht nur die des letzten.
        refusals: list[dict[str, Any]] = []

        def attempt(chosen: tuple[str, str]) -> dict[str, Any]:
            record = self._cycle(*chosen, "", restore=False)
            refusals.extend({"feature": chosen[1], **entry} for entry in record.get("refusals", []))
            return record

        tried, cycle = first_with_a_length_field(ranked_features(objects, anchors), attempt)
        if cycle is None:
            self.data["stage"] = "kein Merkmal"
            self.persist()
            return
        self.data["tried"] = tried
        self.data["selection"] = cycle["selection"]
        self.data["refusals"] = refusals
        self.data["checks"] = cycle["checks"]
        self.data["stage"] = case_stage(cycle)
        self.persist()

    def _recognition(self) -> list[dict[str, Any]]:
        from app.core.geom.mesh import as_mesh_data
        from app.core.perceive.groups import functional_groups

        found = []
        for object_id, entry in self.session.last_result.scene.objects.items():
            groups = (
                functional_groups(entry.features, as_mesh_data(entry.mesh))
                if entry.features
                else ()
            )
            found.append(
                {
                    "id": object_id,
                    "name": str(entry.name),
                    "triangles": entry.mesh.triangle_count,
                    "watertight": entry.mesh.is_watertight,
                    "features": {
                        feature_id: feature.kind for feature_id, feature in entry.features.items()
                    },
                    "groups": [f"{group.kind}/{group.variant}:{group.anchor}" for group in groups],
                }
            )
        return found

    def _cycle(
        self, object_id: str, feature_id: str, prefix: str, *, restore: bool
    ) -> dict[str, Any]:
        """Auswahl, Maßänderung, Vorschau, Übernehmen, Rückgängig, Wiederholen an einem Merkmal."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        from app.ui.labels import LengthSpin

        record: dict[str, Any] = {"object": object_id, "feature": feature_id}
        states: dict[str, dict[str, str]] = {}
        states["01-import"] = self.shot(f"{prefix}01-import")
        self.window.object_tree.select_feature(object_id, feature_id)
        self.pump()
        tree = self.window.object_tree.tree
        current = tree.currentItem()
        if current is not None:
            QTest.mouseClick(
                tree.viewport(),
                Qt.MouseButton.LeftButton,
                pos=tree.visualItemRect(current).center(),
            )
        self.pump(0.5)
        states["02-selection"] = self.shot(f"{prefix}02-selection")
        fields = [
            spin
            for spin in self.window.feature_panel.findChildren(LengthSpin)
            if spin.isVisible() and spin.isEnabled()
        ]
        record["selection"] = {
            "object": object_id,
            "feature": feature_id,
            "fields": [
                {"name": spin.accessibleName(), "value": spin.value_mm()} for spin in fields
            ],
        }
        if not fields:
            record["checks"] = {
                "changed": None,
                "undo_restores_import": None,
                "redo_restores_applied": None,
                "preview_shows_result": None,
            }
            record["note"] = NO_LENGTH_FIELD
            return record
        spin = fields[size_field_first([spin.accessibleName() for spin in fields])]
        before = spin.value_mm()
        preview: dict[str, str] | None = None
        taken: float | None = None
        refusals: list[dict[str, Any]] = []
        for after in values_to_try(before):
            spin.setFocus()
            outcome, detail = self._previewed(spin, after, f"{prefix}Vorschau {after}")
            if outcome == "shown":
                taken, preview = after, detail
                break
            refusals.append({"value": after, "reason": detail})
        record["selection"]["changed"] = {
            "name": spin.accessibleName(),
            "before": before,
            "after": taken,
        }
        if refusals:
            record["refusals"] = refusals
        if taken is None:
            # Keine Zahl trägt: zurück zum gemessenen Wert, und das nächste
            # Merkmal ist dran (:func:`first_with_a_length_field`).
            spin.set_value_mm(before)
            self.pump(0.5)
            record["checks"] = {
                "changed": None,
                "undo_restores_import": None,
                "redo_restores_applied": None,
                "preview_shows_result": None,
            }
            record["note"] = REFUSED
            return record
        states["03-preview"] = self.shot(f"{prefix}03-preview")
        previous = self.session.last_result
        QTest.mouseClick(self.window.feature_panel._apply, Qt.MouseButton.LeftButton)
        self.new_result(previous, f"{prefix}Übernehmen")
        states["04-applied"] = self.shot(f"{prefix}04-applied")
        previous = self.session.last_result
        self.window.action_undo()
        self.new_result(previous, f"{prefix}Rückgängig")
        states["05-undo"] = self.shot(f"{prefix}05-undo")
        previous = self.session.last_result
        self.window.action_redo()
        self.new_result(previous, f"{prefix}Wiederholen")
        states["06-redo"] = self.shot(f"{prefix}06-redo")
        record["states"] = states
        record["preview"] = preview
        record["checks"] = compared(states, preview)
        if restore:
            previous = self.session.last_result
            self.window.action_undo()
            self.new_result(previous, f"{prefix}zurück zum Import")
        return record

    def _previewed(self, spin: Any, value: float, label: str) -> tuple[str, Any]:
        """Eine Zahl ins Feld und warten, bis die Vorschau sie zeigt oder absagt.

        ``("shown", Abdrücke)`` mit einem neuen Bild ohne Problem,
        ``("refused", Satz)`` mit dem Satz, den die Freigabe trägt
        (``MainWindow._preview_approval.problem``), ``("none", …)`` ohne beides
        bis :data:`STEP_TIMEOUT`. Gewartet wird auf eine **neue** Freigabe:
        Die Absage der vorigen Zahl gilt nicht für diese.
        """
        viewport = self.window.viewport
        shown = viewport.difference
        before = getattr(self.window, "_preview_approval", None)
        heard: dict[str, str] = {}

        def settled() -> bool:
            approval = getattr(self.window, "_preview_approval", None)
            fresh = approval is not None and approval is not before
            problem = str(getattr(approval, "problem", "") or "") if fresh else ""
            if fresh and problem and not getattr(approval, "computing", False):
                heard["refused"] = problem
                return True
            difference = viewport.difference
            return (
                difference is not None
                and difference is not shown
                and not viewport._difference_pending
                and not problem
            )

        spin.set_value_mm(value)
        try:
            self.wait_for(settled, label, STEP_TIMEOUT)
        except TimeoutError:
            return "none", "keine Vorschau"
        if "refused" in heard:
            return "refused", heard["refused"]
        difference = viewport.difference
        return "shown", {
            key: body_digest(entry.result.mesh)
            for key, entry in difference.entries.items()
            if entry.result is not None
        }


# --- Einstieg -------------------------------------------------------------------------


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    commands = parser.add_subparsers(dest="command", required=True)
    inventory = commands.add_parser("inventory")
    inventory.add_argument("--out", required=True, type=Path)
    origin = inventory.add_mutually_exclusive_group(required=True)
    origin.add_argument("--manifest", type=Path)
    origin.add_argument("--source", type=Path)
    running = commands.add_parser("run")
    running.add_argument("--out", required=True, type=Path)
    running.add_argument("--first", type=int, default=1)
    running.add_argument("--last", type=int, default=10**6)
    running.add_argument("--again", action="store_true")
    running.add_argument("--timeout", type=float, default=CASE_TIMEOUT)
    one = commands.add_parser("child")
    one.add_argument("--out", required=True, type=Path)
    one.add_argument("--case", required=True, type=int)
    reporting = commands.add_parser("report")
    reporting.add_argument("--out", required=True, type=Path)
    arguments = parser.parse_args(list(argv) if argv is not None else None)
    out = outside_the_repository(arguments.out)
    if arguments.command == "inventory":
        # **Ein leerer Bestand ist keine Abnahme**: Mit ``--source`` auf
        # ``audit.py`` statt auf einen Ordner zählte der Bestand null Fälle und
        # endete mit 0 — ein Lauf darüber hätte nichts geprüft und nichts gesagt.
        if arguments.source is not None and not arguments.source.is_dir():
            print(
                f"{arguments.source} ist kein Ordner: --source nimmt einen Bestand wie"
                " F:\\3D Dateien, --manifest das Manifest des Dateiaudits.",
                file=sys.stderr,
                flush=True,
            )
            return 2
        cases = (
            cases_from_manifest(arguments.manifest)
            if arguments.manifest
            else cases_from_source(arguments.source, out)
        )
        if not cases:
            print("Kein Fall gefunden — der Bestand ist leer.", file=sys.stderr, flush=True)
            return 1
        write_json(out / "cases.json", [asdict(case) for case in cases])
        print(
            f"{len(cases)} Fälle, davon {sum(case.bores for case in cases)} mit jeder Bohrung",
            flush=True,
        )
        return 0
    if arguments.command == "run":
        return run(out, arguments.first, arguments.last, arguments.again, arguments.timeout)
    if arguments.command == "child":
        return child(out, arguments.case)
    data = summary(out, read_cases(out))
    print(f"{data['passed']} von {data['cases']} Fällen bestanden", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
