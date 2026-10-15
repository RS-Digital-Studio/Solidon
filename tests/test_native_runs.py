"""Bindung, Siegel, Argumente und Abbau der nativen Läufer — ohne Fenster (FD-164).

``tools/native_runs.py`` startet die nativen Anschlüsse am echten Schirm; das
ist Releasearbeit. Was davor und danach geschieht, prüft diese Datei: Eine
Bindung entsteht nur an einem sauberen Baum, eine geänderte Läuferdatei
verweigert den Start — im Aufseher wie im Kind, bevor Qt lädt —, ohne
``--native`` startet nichts, das Kind bekommt ein eigenes Profil, und der
Aufseher baut jeden eigenen Prozess ab, auch einen verwaisten Enkel. Die
Gegenproben laufen an einer Kopie der Läufer in einem eigenen Git-Baum, denn
der Arbeitsbaum der Suite ist nicht immer sauber.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from tools import native_binding, native_runs
from tools.native_binding import RUNNER_FILES, SealError
from tools.native_runs import (
    CARD_ROWS,
    ProcessRow,
    StartRefusedError,
    affinity_of,
    card_rows,
    copy_inputs,
    documented_skip,
    fresh_out,
    judge_case,
    licence_protocol_only,
    own_tree,
    profile_environment,
    started,
    stat_only,
    still_running,
    unchanged_inputs,
)

REPOSITORY = Path(__file__).resolve().parent.parent


def git(root: Path, *arguments: str) -> str:
    finished = subprocess.run(
        ["git", "-c", "core.hooksPath=unused-hooks", "-c", "commit.gpgsign=false", *arguments],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return finished.stdout


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """Ein eigener Git-Baum mit Kopien der drei Läufer, einem kleinen ``app`` und ``tests``."""
    root = tmp_path / "baum"
    for relative in RUNNER_FILES:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPOSITORY / relative, target)
    (root / "app" / "ui").mkdir(parents=True)
    (root / "app" / "__init__.py").write_text('"""Kleine Anwendung."""\n', encoding="utf-8")
    # Wie der echte Paketeinstieg: PySide lädt erst nach dieser Zeile (app/ui/__init__.py).
    (root / "app" / "ui" / "__init__.py").write_text(
        'import os\n\nos.environ.setdefault("PYSIDE6_OPTION_LAZY", "0")\n', encoding="utf-8"
    )
    (root / "app" / "data.json").write_text("{}\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_x.py").write_text("X = 1\n", encoding="utf-8")
    git(root, "init", "-q")
    git(root, "config", "user.name", "Test")
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "add", ".")
    git(root, "commit", "-qm", "Ausgangsstand")
    return root


# --- Bindung und Siegel --------------------------------------------------------


def test_a_binding_pins_head_tree_every_file_and_the_runners(tree: Path) -> None:
    """Kopf und Baum aus Git, je Datei unter app/ und tools/ ein Hash, die Läufer als Siegel."""
    binding = native_binding.make_binding(tree)
    assert binding["head"] == git(tree, "rev-parse", "HEAD").strip()
    assert binding["tree"] == git(tree, "rev-parse", "HEAD^{tree}").strip()
    assert set(binding["files"]) == {
        "app/__init__.py",
        "app/data.json",
        "app/ui/__init__.py",
        *RUNNER_FILES,
    }
    assert "tests/test_x.py" not in binding["files"]
    assert binding["runner"] == {
        path: native_binding.sha256_of(tree / path) for path in RUNNER_FILES
    }
    assert binding["files_digest"] == native_binding.digest(binding["files"])
    assert native_binding.form_problems(binding) == []
    assert native_binding.verify(binding, tree) == binding["files"]


@pytest.mark.parametrize("runner", RUNNER_FILES)
def test_a_changed_runner_breaks_the_seal(tree: Path, runner: str) -> None:
    """Gegenprobe: Eine geänderte Läuferdatei verweigert den Start — mit Datei und Ausweg."""
    binding = native_binding.make_binding(tree)
    with (tree / runner).open("a", encoding="utf-8") as stream:
        stream.write("# ungesiegelte Ergänzung\n")
    with pytest.raises(SealError) as refused:
        native_binding.verify(binding, tree)
    assert "Siegel gebrochen" in refused.value.problem
    assert runner in refused.value.problem
    assert "binden Sie neu" in refused.value.suggestion


@pytest.mark.parametrize(
    "change, expected",
    [
        ("product", "Ungesicherte Änderungen"),
        ("new_module", "Ungesicherte Änderungen"),
        ("commit", "head ist"),
    ],
)
def test_every_other_drift_refuses_as_well(tree: Path, change: str, expected: str) -> None:
    """Geändertes Produkt, eine neue Datei, die ein Import träfe, oder ein neuer Commit."""
    binding = native_binding.make_binding(tree)
    if change == "product":
        (tree / "app" / "data.json").write_text('{"neu": 1}\n', encoding="utf-8")
    elif change == "new_module":
        (tree / "tools" / "native_extra.py").write_text("X = 1\n", encoding="utf-8")
    else:
        (tree / "app" / "data.json").write_text('{"neu": 1}\n', encoding="utf-8")
        git(tree, "commit", "-qam", "Weiter")
    with pytest.raises(SealError) as refused:
        native_binding.verify(binding, tree)
    assert expected in refused.value.problem
    assert refused.value.suggestion


def test_a_binding_belongs_to_its_tree_and_interpreter(tree: Path, tmp_path: Path) -> None:
    """Ein Läufer aus einem anderen Baum oder mit anderem Interpreter startet nicht."""
    binding = native_binding.make_binding(tree)
    with pytest.raises(SealError, match="gehört zu"):
        native_binding.verify({**binding, "root": str(tmp_path / "anderswo")}, tree)
    with pytest.raises(SealError, match="Interpreter"):
        native_binding.verify({**binding, "python": str(tmp_path / "python.exe")}, tree)


def test_only_a_clean_tree_can_be_bound(tree: Path, tmp_path: Path) -> None:
    """Was nicht committet ist, lässt sich nicht binden — also läuft es auch nie."""
    (tree / "tools" / "native_runs.py").write_text("# Entwurf\n", encoding="utf-8")
    with pytest.raises(SealError, match="Ungesicherte Änderungen"):
        native_binding.make_binding(tree)
    git(tree, "commit", "-qam", "Entwurf")
    target = tmp_path / "bindung.json"
    native_binding.write_binding(target, tree)
    with pytest.raises(SealError, match="liegt schon"):
        native_binding.write_binding(target, tree)
    with pytest.raises(SealError, match="im Repository"):
        native_binding.write_binding(tree / "bindung.json", tree)


def test_a_binding_must_have_its_form(tree: Path, tmp_path: Path) -> None:
    """Eine Bindung der alten Sitzungswerkzeuge oder eine nachträglich geänderte gilt nicht."""
    binding = native_binding.make_binding(tree)
    old = {"schema": 1, "after_fd66": True, "head": binding["head"], "files": []}
    tampered = {**binding, "files": {**binding["files"], "app/data.json": "0" * 64}}
    for name, content in (("alt.json", old), ("verändert.json", tampered)):
        path = tmp_path / name
        path.write_text(json.dumps(content), encoding="utf-8")
        with pytest.raises(SealError, match="erwartete Form"):
            native_binding.read_binding(path)
    assert native_binding.form_problems(tampered) == ["files_digest"]
    assert native_binding.form_problems(old) == ["schema"]


# --- Die Gegenprobe am echten Einstieg -------------------------------------------


def run_tool(tree: Path, *arguments: str, env: dict[str, str] | None = None) -> Any:
    """Der kopierte Einstieg als eigener Prozess, wie der Koordinator ihn aufruft."""
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    environment["PYTHONUTF8"] = "1"
    environment.update(env or {})
    return subprocess.run(
        [sys.executable, "-B", str(tree / "tools" / "native_runs.py"), *arguments],
        cwd=tree,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )


def inventory(folder: Path) -> Path:
    """Ein kleines Inventar wie aus ``file_acceptance.py inventory --functions``."""
    (folder / "scenes").mkdir(parents=True)
    (folder / "scenes" / "leer.p3d").write_bytes(b"szene")
    case = {"number": 7, "relative": "x", "path": "", "suffix": "", "kind": "function"}
    (folder / "cases.json").write_text(json.dumps([{**case, "row": "r"}]), encoding="utf-8")
    rows = [{"id": name} for name in ("anderes", *reversed(CARD_ROWS))]
    (folder / "rows.json").write_text(json.dumps(rows), encoding="utf-8")
    return folder


def test_the_start_refuses_a_changed_runner(tree: Path, tmp_path: Path) -> None:
    """Gebunden und geprüft startbereit; nach einer Änderung am Läufer verweigert, Ausgang 2."""
    binding = tmp_path / "bindung.json"
    made = run_tool(tree, "bind", "--out", str(binding))
    assert made.returncode == 0, made.stderr
    source = inventory(tmp_path / "inventar")
    out = tmp_path / "lauf"
    common = ["--binding", str(binding), "--inventory", str(source), "--case", "7"]
    common += ["--screen", "MSI MAG271CQR", "--out", str(out)]
    ready = run_tool(tree, "case", *common, "--check")
    assert ready.returncode == 0, ready.stderr
    assert json.loads(ready.stdout)["ready"] is True
    assert not out.exists(), "--check legt nichts an"
    unasked = run_tool(tree, "case", *common)
    assert unasked.returncode == 2
    assert "--native" in unasked.stderr and "Handlungsvorschlag" in unasked.stderr
    with (tree / "tools" / "native_measure_card.py").open("a", encoding="utf-8") as stream:
        stream.write("# spätere, ungesiegelte Ergänzung\n")
    for mode in ("--check", "--native"):
        refused = run_tool(tree, "case", *common, mode)
        assert refused.returncode == 2, refused.stderr
        assert "Siegel gebrochen" in refused.stderr
        assert "tools/native_measure_card.py" in refused.stderr
        assert "Handlungsvorschlag" in refused.stderr
        assert not out.exists()


def child_arguments(binding: Path, evidence: Path, tmp_path: Path) -> list[str]:
    rows = tmp_path / "zeilen.json"
    rows.write_text("[]", encoding="utf-8")
    return [
        "card-child",
        "--binding",
        str(binding),
        "--evidence",
        str(evidence),
        "--language",
        "de",
        "--rows",
        str(rows),
        "--scenes",
        str(tmp_path),
        "--screen",
        "MSI MAG271CQR",
        "--deadline",
        "60",
    ]


def test_the_child_checks_seal_and_profile_before_qt(tree: Path, tmp_path: Path) -> None:
    """Das Kind prüft selbst: Siegel, alle acht Nutzerordner, Paketeinstieg — vor PySide6."""
    binding = tmp_path / "bindung.json"
    assert run_tool(tree, "bind", "--out", str(binding)).returncode == 0
    evidence = tmp_path / "de"
    profile = {
        name: str(evidence / "profile" / name.lower()) for name in native_binding.PROFILE_VARIABLES
    }
    # Gegenprobe Profil: Ein Nutzerordner zeigt woanders hin — kein Start, kein Beleg.
    stray = run_tool(
        tree,
        *child_arguments(binding, evidence, tmp_path),
        env={**profile, "TEMP": str(tmp_path / "fremd")},
    )
    assert stray.returncode == 2, stray.stderr
    assert "TEMP zeigt nicht auf das Fallprofil" in stray.stderr
    assert not (evidence / "seal-enter.json").exists()
    # Mit Profil: Siegel und Einstieg tragen; dann scheitert erst der Weg an der
    # kleinen Anwendung — und das Siegel wird beim Abbau trotzdem geprüft.
    entered = run_tool(tree, *child_arguments(binding, evidence, tmp_path), env=profile)
    assert entered.returncode == 1, entered.stderr
    record = json.loads((evidence / "seal-enter.json").read_text(encoding="utf-8"))
    assert record["pyside_imported"] is False
    assert record["pyside_lazy"] == "0"
    assert record["head"] == git(tree, "rev-parse", "HEAD").strip()
    assert record["environment"] == profile
    left = json.loads((evidence / "seal-leave.json").read_text(encoding="utf-8"))
    assert left["same"] is True
    observation = json.loads((evidence / "observation.json").read_text(encoding="utf-8"))
    assert observation["source_pins_unchanged"] is True
    assert observation["execution_complete"] is False
    # Gegenprobe Siegel im Kind: geänderter Läufer, gleiches Profil — Abbruch vor Qt.
    shutil.rmtree(evidence)
    with (tree / "tools" / "native_binding.py").open("a", encoding="utf-8") as stream:
        stream.write("# geändert\n")
    broken = run_tool(tree, *child_arguments(binding, evidence, tmp_path), env=profile)
    assert broken.returncode == 2
    assert "Siegel gebrochen" in broken.stderr
    assert not (evidence / "seal-enter.json").exists()


# --- Argumente, Profil, Eingaben ----------------------------------------------------


def test_the_affinity_is_a_hexadecimal_mask() -> None:
    assert affinity_of("FFFFF0FF") == 0xFFFFF0FF
    assert affinity_of(None) is None
    for wrong in ("xyz", "0", "-1"):
        with pytest.raises(StartRefusedError, match="keine Kernmaske"):
            affinity_of(wrong)


def test_nothing_starts_without_the_switch() -> None:
    """Ohne ``--native`` kein Fenster; ``--check`` meldet nur; ein leerer Schirm gilt nicht."""
    plan = {"out": "x"}
    asked = argparse.Namespace(screen="MSI MAG271CQR", check=True, native=False)
    assert started(asked, plan) is False
    with pytest.raises(StartRefusedError, match="--native"):
        started(argparse.Namespace(screen="MSI MAG271CQR", check=False, native=False), plan)
    with pytest.raises(StartRefusedError, match="--screen ist leer"):
        started(argparse.Namespace(screen=" ", check=False, native=True), plan)


def test_check_and_native_exclude_each_other() -> None:
    common = ["--binding", "b", "--inventory", "i", "--screen", "s", "--out", "o"]
    with pytest.raises(SystemExit):
        native_runs.parser().parse_args(["measure-card", *common, "--check", "--native"])
    parsed = native_runs.parser().parse_args(["case", *common, "--case", "3", "--native"])
    assert parsed.native and not parsed.check and parsed.case == 3


def test_the_child_gets_its_own_profile_and_platform(tmp_path: Path) -> None:
    """Alle acht Nutzerordner ins Fallprofil, nie HOME; Bewegung und Ladeart fallen weg."""
    base = {
        "HOME": "H",
        "APPDATA": "echt",
        "SOLIDON3D_MOTION": "aus",
        "PYSIDE6_OPTION_LAZY": "1",
        "PATH": "P",
    }
    env = profile_environment(base, tmp_path / "profil")
    for name in native_binding.PROFILE_VARIABLES:
        assert env[name] == str(tmp_path / "profil" / name.lower())
    assert env["HOME"] == "H" and env["PATH"] == "P"
    assert "SOLIDON3D_MOTION" not in env and "PYSIDE6_OPTION_LAZY" not in env
    assert env["PYTHONPATH"] == str(native_runs.ROOT)
    assert env["QT_QPA_PLATFORM"] == "windows" and env["QT_SCALE_FACTOR"] == "1"
    assert all(env[name] == "1" for name in native_runs.THREAD_VARIABLES)


def test_the_watched_profile_files_are_the_applications() -> None:
    """Die Namen, die nur per stat verglichen werden, sind die der Anwendung."""
    from app.core.activation.store import STATE_FILE, TRIAL_FILE
    from app.ui.settings import SETTINGS_FILE

    assert set(native_runs.WATCHED_FILES) == {SETTINGS_FILE, TRIAL_FILE, STATE_FILE}


def test_stat_only_reports_size_and_time_or_nothing(tmp_path: Path) -> None:
    present = tmp_path / "da.json"
    present.write_text("{}", encoding="utf-8")
    found = stat_only([present, tmp_path / "fehlt.json"])
    assert found[str(present)] == [present.stat().st_size, present.stat().st_mtime_ns]
    assert found[str(tmp_path / "fehlt.json")] is None


def test_outputs_stay_outside_and_new(tmp_path: Path) -> None:
    with pytest.raises(StartRefusedError, match="im Repository"):
        fresh_out(REPOSITORY / "lauf")
    (tmp_path / "alt").mkdir()
    with pytest.raises(StartRefusedError, match="liegt schon"):
        fresh_out(tmp_path / "alt")
    assert fresh_out(tmp_path / "neu") == (tmp_path / "neu").resolve()


def test_inputs_are_copied_hashed_and_rechecked(tmp_path: Path) -> None:
    """Die Kopie trägt ihre Hashes; eine Änderung am Inventar während des Laufs fällt auf."""
    source = inventory(tmp_path / "inventar")
    out = tmp_path / "lauf"
    out.mkdir()
    copied = copy_inputs(source, out, ("cases.json", "rows.json", "menubar.json"))
    assert set(copied) == {"cases.json", "rows.json", "scenes/leer.p3d"}
    assert (out / "scenes" / "leer.p3d").read_bytes() == b"szene"
    assert unchanged_inputs(source, copied)
    (source / "scenes" / "leer.p3d").write_bytes(b"anders")
    assert not unchanged_inputs(source, copied)


def test_the_card_rows_come_in_their_order(tmp_path: Path) -> None:
    source = inventory(tmp_path / "inventar")
    assert [row["id"] for row in card_rows(source)] == list(CARD_ROWS)
    (source / "rows.json").write_text(json.dumps([{"id": "resize_hole"}]), encoding="utf-8")
    with pytest.raises(StartRefusedError) as refused:
        card_rows(source)
    assert "--rows resize_hole,move_feature" in str(refused.value)


# --- Prozessbaum ---------------------------------------------------------------------


def test_the_own_tree_takes_descendants_and_no_strangers() -> None:
    """Kinder und Enkel zählen, ein Waise des beendeten Kindes auch; wiederverwendete PIDs nicht."""
    created = {10: 100, 11: 110, 12: 120, 13: 90, 14: 130, 20: 140, 21: 150}
    rows = [
        ProcessRow(11, 10, "kind.exe"),
        ProcessRow(12, 11, "enkel.exe"),
        ProcessRow(13, 10, "älter.exe"),  # vor der Wurzel entstanden: fremd
        ProcessRow(14, 99, "fremd.exe"),
        ProcessRow(20, 12, "waise.exe"),
        ProcessRow(21, 14, "kind-des-fremden.exe"),
    ]
    known = {10: ProcessRow(10, 1, "wurzel.exe", 100)}
    tree = own_tree(rows, known, created.get)
    assert set(tree) == {10, 11, 12, 20}
    assert tree[12].created == 120
    # Die PID 11 lebt wieder, aber als ein anderer Prozess: Ihre Kinder gehören nicht dazu.
    reused = {**created, 11: 999}
    late = [*rows, ProcessRow(30, 11, "neu.exe")]
    assert 30 not in own_tree(late, tree, {**reused, 30: 1000}.get)
    alive = still_running(tree, rows, reused.get)
    assert {member.pid for member in alive} == {12, 20}


def alive(pid: int) -> bool:
    output = subprocess.check_output(
        ["tasklist.exe", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
        text=True,
        encoding="oem",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        timeout=10,
    )
    return any(len(row) > 1 and row[1] == str(pid) for row in csv.reader(output.splitlines()))


HELPER = """import subprocess, sys, time
from pathlib import Path
mode, out = sys.argv[1], Path(sys.argv[2])
if mode == "leaf":
    time.sleep(60)
elif mode == "orphan":
    leaf = subprocess.Popen([sys.executable, __file__, "leaf", str(out)],
                            creationflags=subprocess.CREATE_NO_WINDOW)
    (out / "leaf.txt").write_text(str(leaf.pid))
    time.sleep(1.5)
elif mode == "hang":
    leaf = subprocess.Popen([sys.executable, __file__, "leaf", str(out)],
                            creationflags=subprocess.CREATE_NO_WINDOW)
    (out / "leaf.txt").write_text(str(leaf.pid))
    time.sleep(60)
sys.exit(0)
"""


@pytest.mark.skipif(sys.platform != "win32", reason="Prozessaufnahme und Abbau nur unter Windows")
@pytest.mark.parametrize("mode", ["normal", "orphan", "hang"])
def test_the_supervisor_ends_every_own_process(tmp_path: Path, mode: str) -> None:
    """Regulär sauber; ein verwaister Enkel wird gefunden, beendet und macht den Lauf rot."""
    script = tmp_path / "helfer.py"
    script.write_text(HELPER, encoding="utf-8")
    folder = tmp_path / "fall"
    began = time.monotonic()
    record = native_runs.supervise(
        [sys.executable, str(script), mode, str(tmp_path)],
        cwd=tmp_path,
        env=dict(os.environ),
        deadline_s=4.0 if mode == "hang" else 30.0,
        folder=folder,
        poll_s=0.2,
    )
    assert time.monotonic() - began < 40
    written = json.loads((folder / "child-tree.json").read_text(encoding="utf-8"))
    assert written["clean_end"] is record["clean_end"]
    if mode == "normal":
        assert record["exit_code"] == 0 and record["clean_end"] is True
        assert not record["stopped"] and not record["remaining"]
        return
    leaf = int((tmp_path / "leaf.txt").read_text(encoding="utf-8"))
    assert leaf in {row["pid"] for row in record["own_process_tree"]}
    assert not alive(leaf)
    assert record["clean_end"] is False
    assert not record["remaining"]
    if mode == "orphan":
        # Der Enkel und, unter einer venv, der Interpreter hinter seinem Starter.
        assert record["exit_code"] == 0 and not record["timeout"]
        stopped = {row["pid"] for row in record["stopped"]}
        assert leaf in stopped
        assert not any(alive(pid) for pid in stopped)
    else:
        assert record["timeout"] is True and record["exit_code"] != 0


# --- Urteil eines Einzelfalls ----------------------------------------------------------

SCREEN = "MSI MAG271CQR"
HEAD = "a" * 40
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 16


def language_case(folder: Path, **protocol: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """Ein gelaufener Sprachfall: zwei Flächen, ein Bild, wie ``file_acceptance`` ihn lässt."""
    case = {"number": 32, "kind": "language", "row": "D10", "variant": {"language": "en"}}
    (folder / "surfaces").mkdir(parents=True)
    (folder / "bench.json").write_text(
        json.dumps({"case": case, "stage": "done", "shutdown_complete": True}), encoding="utf-8"
    )
    surface = {
        "errors": [],
        "variant": {"placed": {"screen": SCREEN}},
        "version": {"commit": HEAD},
        **protocol,
    }
    for name in ("a", "b"):
        (folder / "surfaces" / f"{name}.json").write_text(json.dumps(surface), encoding="utf-8")
    (folder / "flaeche-en-a.png").write_bytes(PNG)
    return case, {"exit_code": 0, "timeout": False, "clean_end": True}


def test_a_regular_case_is_measured_and_waits_for_its_images(tmp_path: Path) -> None:
    case, record = language_case(tmp_path)
    verdict = judge_case(tmp_path, case, record, head=HEAD, screen=SCREEN)
    assert verdict == {"status": "measured_needs_review", "images": 1, "surfaces": 2}


@pytest.mark.parametrize(
    "spoil, message",
    [
        ("exit", "endete mit 1"),
        ("rest", "liefen nach dem Fall weiter"),
        ("screen", "nicht auf dem Schirm"),
        ("head", "gebundenen Kopf"),
        ("errors", "trägt Fehler"),
        ("stage", "nicht regulär"),
        ("image", "Bilder fehlen"),
    ],
)
def test_every_broken_part_of_a_case_is_red(tmp_path: Path, spoil: str, message: str) -> None:
    """Prozess, Abbau, Schirm, Kopf, Protokoll, Stufe und Bild — jedes für sich macht rot."""
    case, record = language_case(
        tmp_path,
        **{
            "screen": {"variant": {"placed": {"screen": "anderer"}}},
            "head": {"version": {"commit": "b" * 40}},
            "errors": {"errors": ["kaputt"]},
        }.get(spoil, {}),
    )
    if spoil == "exit":
        record["exit_code"] = 1
    if spoil == "rest":
        record["clean_end"] = False
    if spoil == "stage":
        bench = json.loads((tmp_path / "bench.json").read_text(encoding="utf-8"))
        (tmp_path / "bench.json").write_text(json.dumps({**bench, "stage": "start"}), "utf-8")
    if spoil == "image":
        (tmp_path / "flaeche-en-a.png").unlink()
    with pytest.raises(native_runs.CaseRunError, match=message):
        judge_case(tmp_path, case, record, head=HEAD, screen=SCREEN)


def test_only_the_documented_reasons_go_without_images() -> None:
    """Bildlos nur der Skalierungsrückweg mit beiden Gründen und der vollständige Lizenzlauf."""
    case = {"kind": "function", "variant": {"set": "skalierung", "scale": 2.0}}
    protocol = {
        "variant": {"set": "skalierung", "scale": 2.0, "placed": {"screen": SCREEN}},
        "unmeasured": {"scrollbars": "zu klein", "icons": "zu klein"},
        "steps": [],
        "images": [],
        "scene": None,
        "result": None,
        "errors": [],
    }
    assert documented_skip(case, protocol, "zu klein", SCREEN)
    assert not documented_skip(case, protocol, "", SCREEN)
    assert not documented_skip(case, {**protocol, "unmeasured": {"icons": "x"}}, "zu klein", SCREEN)
    assert not documented_skip(case, protocol, "zu klein", "anderer Schirm")
    licence = {"kind": "function", "row": "r", "variant": {"set": "lizenz", "licence": "trial"}}
    measured = {
        "variant": {"set": "lizenz", "licence": "trial", "placed": {"screen": SCREEN}},
        "row": {"id": "r"},
        "licence_runs": {"trial": {"writes": False, "state": "grau", "reason": "Demo"}},
        "unmeasured": {},
        "errors": [],
        "images": [],
        "steps": [],
    }
    contract = {
        "phases": {"lizenz": ("licence",)},
        "licence_states": ("trial", "licensed"),
        "run_states": ("angeboten", "grau", "fehlt"),
        "screen": SCREEN,
    }
    assert licence_protocol_only(licence, measured, **contract)
    broken = {**measured, "licence_runs": {"trial": {"writes": "nein", "state": "grau"}}}
    assert not licence_protocol_only(licence, broken, **contract)
    assert not licence_protocol_only(licence, {**measured, "errors": ["x"]}, **contract)
