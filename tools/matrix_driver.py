"""Verteilt ``matrix_unit.py`` über die Modelle — ein Prozess je Modell, mehrere nebeneinander.

Aufruf: python tools/matrix_driver.py <code-wurzel> <ausgabeordner> <plan> [--arbeiter N]

Pläne:

``drucker``  die drei Modelle der Abnahme (Minigolf-Platte, Wedge-Lock,
             Waschschüssel) über jede Kombination aus Slicer und Drucker
``modelle``  jedes Modell aus ``F:\\3D Dateien`` (ohne „3D Drucker“, Dubletten
             nach Prüfsumme gestrichen) über die Heimkombinationen, klein zuerst
``probe``    die drei Modelle von ``drucker`` über die Heimkombinationen —
             der Probelauf des Werkzeugs vor einem Gesamtlauf

Wieder aufnehmbar: Ein Modell, dessen Ergebnis ``done`` trägt, läuft nicht
noch einmal; ein halbes setzt bei der nächsten Kombination fort. Liegt die
Datei ``PAUSE`` im Ausgabeordner, startet nichts Neues, und laufende Einheiten
halten vor ihrer nächsten Kombination an — für die Leistungsprüfung der
Release-Sitzung.
"""
# ruff: noqa: E501

from __future__ import annotations

import hashlib
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.matrix_config import HOME, SLICERS

HERE = Path(__file__).resolve().parent
ROOT = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
PLAN = sys.argv[3]
WORKERS = int(sys.argv[sys.argv.index("--arbeiter") + 1]) if "--arbeiter" in sys.argv else 2
PYTHON = Path(sys.executable)
CORPUS = Path(r"F:\3D Dateien")
#: Quelldaten, die das Ergebnis der Übergabe bestimmen.
FINGERPRINT_SUFFIXES = {".py", ".json", ".toml", ".txt", ".ini", ".cfg", ".xml", ".csv"}
MODEL_DIGESTS: dict[Path, str] = {}
RUN_IDENTITY: dict[str, object] | None = None
#: Je Arbeiter eigene Kerne, damit zwei Slicer sich nicht gegenseitig bremsen.
#: Die Kerne 8 bis 11 rechnen auf dieser Maschine zeitweise falsch (RM-272)
#: und bleiben aus; 0 bis 7 bleiben für Tor und Messungen frei.
MASKS = ["FF0000", "FF000000", "F000"]

PRINTER_PLAN = [
    # Die Druckplatte der Matrix: acht Teile aus Roberts Minigolf-Projekt ``x.p3d``
    # als eine 3MF-Baugruppe, neben ihrer Quelle im Korpus und nicht im
    # örtlichen ``output/``, wo die frühere ``solidon-0936.3mf`` verloren ging
    # (RM-525). Neu gebaut wird sie mit ``platte_bauen.py`` daneben.
    CORPUS / "Mini+Golf+All+Set-P1S_stls" / "minigolf-platte.3mf",
    CORPUS / "Wedge-Lock (Set).stl",
    CORPUS / "HydroBowl+–+Smart+Fruit+&+Veggie+Washer (1)" / "washing bowl v1.stl",  # noqa: RUF001
]
MODEL_SUFFIXES = {".stl", ".3mf", ".step", ".stp", ".obj", ".glb", ".ply"}


def corpus() -> list[Path]:
    seen: dict[str, tuple[Path, str]] = {}
    for path in sorted(CORPUS.rglob("*")):
        if (
            "3D Drucker" in path.parts
            or path.suffix.lower() not in MODEL_SUFFIXES
            or not path.is_file()
        ):
            continue
        digest = _file_digest(path)
        # Von zwei gleichen Dateien die ohne „(1)“ im Namen.
        current = seen.get(digest)
        if current is None or ("(1)" in current[0].name and "(1)" not in path.name):
            seen[digest] = (path.resolve(), digest)
    selected = sorted(
        (path for path, _digest in seen.values()), key=lambda path: path.stat().st_size
    )
    MODEL_DIGESTS.update(dict(seen.values()))
    return selected


def units() -> list[tuple[Path, str]]:
    if PLAN == "drucker":
        return [(model, "alle") for model in PRINTER_PLAN]
    if PLAN == "probe":
        # Die drei Modelle der Abnahme über die sieben Heimkombinationen: der
        # Probelauf, bevor ein Gesamtlauf Stunden kostet.
        return [(model, "heim") for model in PRINTER_PLAN]
    if PLAN == "modelle":
        return [(model, "heim") for model in corpus()]
    raise SystemExit(f"unbekannter Plan: {PLAN}")


def result_key(model: Path) -> str:
    """Trennt gleichnamige Modelle aus verschiedenen Dateiformaten oder Ordnern."""
    safe = re.sub(r"[^\w.-]+", "_", model.stem)[:80]
    fingerprint = hashlib.sha256(str(model.resolve()).casefold().encode("utf-8")).hexdigest()[:8]
    return f"{safe}-{fingerprint}"


def result_of(model: Path) -> Path:
    name = re.sub(r"[^\w.-]+", "_", model.stem)[:80]
    return OUT / result_key(model) / f"{name}.json"


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _profile_files(root: Path) -> list[Path]:
    """Dateien, die der Profileinleser einer Slicerfamilie tatsächlich nutzt."""
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and (
            path.suffix.lower() in {".json", ".ini", ".cfg"}
            or path.name.lower().endswith(".xml.fdm_material")
        )
    )


def _code_digest(root: Path) -> str:
    """Bindet den Lauf an den Quell- und Konfigurationsstand, den er lädt."""
    candidates = {
        f"app/{path.relative_to(root).as_posix()}": path
        for path in (root / "app").rglob("*")
        if path.is_file() and path.suffix.lower() in FINGERPRINT_SUFFIXES
    }
    for name in ("pyproject.toml", "constraints.txt"):
        path = root / name
        if path.is_file():
            candidates[f"root/{name}"] = path
    for name in ("matrix_driver.py", "matrix_unit.py", "matrix_config.py", "matrix_gcode.py"):
        path = HERE / name
        if path.is_file():
            candidates[f"matrix/{name}"] = path
    digest = hashlib.sha256()
    for name, path in sorted(candidates.items()):
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1 << 20), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def _identity_hash(identity: dict[str, object]) -> str:
    encoded = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _expected_combos(spec: str) -> list[tuple[str, str]]:
    if spec == "heim":
        return list(HOME.items())
    if spec != "alle":
        raise ValueError(f"unbekannte Kombination: {spec}")
    root = str(ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    from app.core.knowledge import profiles

    printers = [
        key for key, value in profiles.printer_profiles().items() if value.technology != "resin"
    ]
    return [(slicer, printer) for slicer in SLICERS for printer in printers]


def _slicer_identity() -> dict[str, object]:
    """Bindet den Lauf an Slicerprogramme und die gelesenen Profilbestände."""
    root = str(ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    from app.core.export import slicer_profiles
    from tools.matrix_config import SLICER_FLAVOURS

    result: dict[str, object] = {}
    for name, configured in SLICERS.items():
        executable = Path(configured).resolve()
        record: dict[str, object] = {"executable": str(executable), "exists": executable.is_file()}
        if executable.is_file():
            record.update(size=executable.stat().st_size, sha256=_file_digest(executable))
            flavour = SLICER_FLAVOURS[name]
            profile_roots = slicer_profiles.profile_roots(flavour, executable)
            profile_digest = hashlib.sha256()
            profile_count = 0
            for profile_root in profile_roots:
                profile_digest.update(str(profile_root).casefold().encode("utf-8"))
                profile_digest.update(b"\0")
                if not profile_root.is_dir():
                    continue
                files = _profile_files(profile_root)
                for path in files:
                    profile_digest.update(path.relative_to(profile_root).as_posix().encode("utf-8"))
                    profile_digest.update(b"\0")
                    profile_digest.update(_file_digest(path).encode("ascii"))
                    profile_digest.update(b"\0")
                    profile_count += 1
            record["profile_files"] = profile_count
            record["profiles_sha256"] = profile_digest.hexdigest()
        result[name] = record
    return result


def _run_identity(planned: list[tuple[Path, str]]) -> dict[str, object]:
    expected = {
        spec: [list(pair) for pair in sorted(_expected_combos(spec))]
        for spec in sorted({spec for _model, spec in planned})
    }
    return {
        "schema": 2,
        "code_root": str(ROOT),
        "plan": PLAN,
        "workers": WORKERS,
        "code_sha256": _code_digest(ROOT),
        "python": sys.version,
        "expected_combos": expected,
        "models": [
            {
                "path": str(model.resolve()),
                "sha256": MODEL_DIGESTS[model.resolve()],
                "spec": spec,
            }
            for model, spec in sorted(
                planned, key=lambda pair: (str(pair[0].resolve()).casefold(), pair[1])
            )
        ],
        "slicers": _slicer_identity(),
        "orient": os.environ.get("GESAMT_AUSRICHTEN", "1"),
        "slice_timeout": os.environ.get("GESAMT_ZEITLIMIT", str(45 * 60)),
        "keep_files": bool(os.environ.get("GESAMT_BEHALTEN")),
    }


def _bind_output(identity: dict[str, object]) -> None:
    """Verhindert, dass ein Ausgabeordner Ergebnisse verschiedener Läufe mischt."""
    path = OUT / ".matrix-identity"
    if path.exists():
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise SystemExit(
                f"Laufkennung in {path} ist unlesbar; wähle für die Matrix einen neuen Ausgabeordner."
            ) from error
        if previous != identity:
            raise SystemExit(
                f"{OUT} gehört zu einem anderen Code- oder Planstand; "
                "wähle für die Matrix einen neuen Ausgabeordner."
            )
        return
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(identity, ensure_ascii=False, indent=1), encoding="utf-8")
    temporary.replace(path)


def _write_status(identity: dict[str, object], status: str) -> None:
    path = OUT / ".matrix-status"
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    payload = {"run_sha256": _identity_hash(identity), "status": status}
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    temporary.replace(path)


def _result_identity(model: Path, spec: str) -> dict[str, str]:
    if RUN_IDENTITY is None:
        raise RuntimeError("Die Matrix-Laufkennung wurde noch nicht gesetzt")
    return {
        "run_sha256": _identity_hash(RUN_IDENTITY),
        "code_sha256": str(RUN_IDENTITY["code_sha256"]),
        "plan": PLAN,
        "spec": spec,
        "model": str(model.resolve()),
        "model_sha256": MODEL_DIGESTS[model.resolve()],
    }


def _has_terminal_state(entry: dict[str, object]) -> bool:
    return any(
        isinstance(entry.get(key), str) and bool(entry[key].strip()) for key in ("skip", "error")
    ) or (
        isinstance(entry.get("variants"), dict)
        and isinstance(entry["variants"].get("standard"), list)
    )


def _seal_result(model: Path, spec: str) -> bool:
    """Kennzeichnet nur vollständig gemessene Ergebnisse mit ihren Eingaben."""
    path = result_of(model)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return False
    if not isinstance(data, dict):
        return False
    if (
        data.get("done") is not True
        or data.get("load_error")
        or data.get("code") != str(ROOT)
        or data.get("model") != str(model.resolve())
        or data.get("spec") != spec
        or data.get("_matrix_run") != _result_identity(model, spec)
        or not _has_complete_combos(data, spec)
    ):
        return False
    try:
        if _file_digest(model) != MODEL_DIGESTS[model.resolve()]:
            return False
    except OSError:
        return False
    data["_matrix_run"] = _result_identity(model, spec)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    temporary.replace(path)
    return True


def done(model: Path, spec: str) -> bool:
    path = result_of(model)
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return False
    if not isinstance(data, dict):
        return False
    return (
        data.get("done") is True
        and not data.get("load_error")
        and data.get("code") == str(ROOT)
        and data.get("model") == str(model.resolve())
        and data.get("spec") == spec
        and data.get("_matrix_run") == _result_identity(model, spec)
        and _has_complete_combos(data, spec)
    )


def _has_complete_combos(data: dict[str, object], spec: str) -> bool:
    rows = data.get("combos")
    if not isinstance(rows, list):
        return False
    expected = set(_expected_combos(spec))
    found: set[tuple[str, str]] = set()
    for row in rows:
        if not isinstance(row, dict):
            return False
        pair = (row.get("slicer"), row.get("printer"))
        if (
            not all(isinstance(value, str) for value in pair)
            or pair not in expected
            or pair in found
            or row.get("complete") is not True
        ):
            return False
        if not _has_terminal_state(row):
            return False
        found.add(pair)
    return found == expected


def log(text: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}"
    with (OUT / "treiber.log").open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    print(line, flush=True)


def worker(
    number: int,
    tasks: queue.Queue[tuple[int, Path, str]],
    failures: queue.SimpleQueue[str],
    total: int,
) -> None:
    mask = MASKS[number % len(MASKS)]
    while True:
        try:
            index, model, spec = tasks.get_nowait()
        except queue.Empty:
            return
        while (OUT / "PAUSE").exists():
            time.sleep(30)
        started = time.perf_counter()
        log(f"[{index}/{total}] Arbeiter {number} ({mask}) beginnt {model.name}")
        environment = {
            **os.environ,
            "PYTHONUTF8": "1",
            "GESAMT_KERNE": mask,
            "GESAMT_PAUSE": str(OUT / "PAUSE"),
            "GESAMT_MATRIX_IDENTITAET": json.dumps(
                _result_identity(model, spec), ensure_ascii=False, sort_keys=True
            ),
            "GESAMT_AUSRICHTEN": str(RUN_IDENTITY["orient"]),
            "GESAMT_ZEITLIMIT": str(RUN_IDENTITY["slice_timeout"]),
            "GESAMT_BEHALTEN": "1" if RUN_IDENTITY["keep_files"] else "",
        }
        safe = result_key(model)
        model_out = OUT / safe
        with (OUT / "logs" / f"{safe}.log").open("a", encoding="utf-8") as output:
            try:
                completed = subprocess.run(
                    [
                        str(PYTHON),
                        "-u",
                        str(HERE / "matrix_unit.py"),
                        str(ROOT),
                        str(model),
                        str(model_out),
                        spec,
                    ],
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    env=environment,
                    timeout=8 * 3600,
                )
                code: object = completed.returncode
            except subprocess.TimeoutExpired:
                code = "Zeitlimit"
            except OSError as error:
                code = f"Startfehler: {error}"
        sealed = code == 0 and _seal_result(model, spec)
        if code != 0 or not sealed:
            failures.put(f"{model.name}: Exit {code}; versiegelt={sealed}")
            log(
                f"[{index}/{total}] Ergebnis für {model.name} bleibt offen: Exit {code}; versiegelt={sealed}"
            )
        log(
            f"[{index}/{total}] Arbeiter {number} fertig mit {model.name}: {code} nach {time.perf_counter() - started:.0f} s"
        )


def main() -> int:
    global RUN_IDENTITY
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "logs").mkdir(exist_ok=True)
    planned = units()
    for model, _spec in planned:
        resolved = model.resolve()
        if resolved not in MODEL_DIGESTS:
            MODEL_DIGESTS[resolved] = _file_digest(resolved)
    result_paths = [result_of(model) for model, _ in planned]
    if len(result_paths) != len(set(result_paths)):
        raise RuntimeError("Modelle kollidieren im Ergebnisnamen; Matrix wird nicht gestartet")
    RUN_IDENTITY = _run_identity(planned)
    _bind_output(RUN_IDENTITY)
    _write_status(RUN_IDENTITY, "running")
    tasks: queue.Queue[tuple[int, Path, str]] = queue.Queue()
    for index, (model, spec) in enumerate(planned, start=1):
        if not done(model, spec):
            tasks.put((index, model, spec))
    log(
        f"Plan {PLAN}: {len(planned)} Modelle, offen {tasks.qsize()}, Code {ROOT}, {WORKERS} Arbeiter"
    )
    failures: queue.SimpleQueue[str] = queue.SimpleQueue()
    threads = [
        threading.Thread(target=worker, args=(number, tasks, failures, len(planned)))
        for number in range(WORKERS)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    failure_messages: list[str] = []
    while True:
        try:
            failure_messages.append(failures.get_nowait())
        except queue.Empty:
            break
    if failure_messages:
        for message in failure_messages:
            log(f"FEHLER: {message}")
        _write_status(RUN_IDENTITY, "failed")
        return 1
    changed_models = []
    for model, _spec in planned:
        try:
            if _file_digest(model) != MODEL_DIGESTS[model.resolve()]:
                changed_models.append(model.name)
        except OSError:
            changed_models.append(model.name)
    if changed_models:
        log("Modelldateien änderten sich während der Matrix: " + ", ".join(changed_models))
        _write_status(RUN_IDENTITY, "failed")
        return 1
    if _run_identity(planned) != RUN_IDENTITY:
        log("Quellstand änderte sich während der Matrix; Ergebnisse nicht als vollständig bewerten")
        _write_status(RUN_IDENTITY, "failed")
        return 1
    if any(not done(model, spec) for model, spec in planned):
        log("Mindestens ein Ergebnis hat keine vollständige, gültige Kombinationsabdeckung")
        _write_status(RUN_IDENTITY, "failed")
        return 1
    _write_status(RUN_IDENTITY, "complete")
    log(f"Plan {PLAN} beendet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
