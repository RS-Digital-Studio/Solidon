"""Prozess- und Temp-Isolation des Bereichsläufers, ohne Geometrie auszuwerten."""

from __future__ import annotations

import json
import os
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import check_part_ranges as runner

VARIABLES = (
    "APPDATA",
    "LOCALAPPDATA",
    "HOME",
    "XDG_DATA_HOME",
    "XDG_CONFIG_HOME",
    "XDG_CACHE_HOME",
)


def _pid_report(
    name: str, _temporary: Path | None = None, _window: tuple[int, int] | None = None
) -> dict[str, object]:
    """Ein günstiger echter Prozessauftrag; die Kennung reist als Fingerabdruck zurück."""
    return {
        "name": name,
        "version": "1",
        "fingerprint": str(os.getpid()),
        "corners": 1,
        "checked": 1,
        "excluded": 0,
        "failures": [],
        "passed": True,
        "seconds": 0.0,
    }


def _crashing_report(_name: str, temporary: Path, _window: object = None) -> None:
    """Der eigene Prüfprozess endet absichtlich ohne Aufräumen; der Elternlauf bleibt zuständig."""
    with runner._isolate(temporary) as folder:
        (folder / "unfinished.txt").write_text("nur Testdaten", encoding="utf-8")
        os._exit(7)


@pytest.fixture
def isolated_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str | None]:
    """Nur eigene Tempdaten; gesetzte und fehlende Umgebungswerte müssen zurückkommen."""
    monkeypatch.setattr(runner.tempfile, "tempdir", str(tmp_path))
    for variable in VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path / "original"))
    return {variable: os.environ.get(variable) for variable in VARIABLES}


@pytest.fixture
def prepared_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, isolated_environment: dict[str, str | None]
) -> Path:
    """Der echte Läufer erhält drei harmlose Einträge und schreibt nur einen temporären Beleg."""
    from app.core.knowledge.parts import range_check, range_proof

    specs = [SimpleNamespace(name=f"part_{index}", source="shipped") for index in range(3)]
    monkeypatch.setattr(range_check, "part_corner_count", lambda _spec: 1)
    target = tmp_path / "proofs.toml"
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "_registry", lambda: SimpleNamespace(all=lambda: specs))
    monkeypatch.setattr(range_proof, "reference_profile", lambda: None)
    monkeypatch.setattr(range_proof, "load", dict)
    monkeypatch.setattr(range_proof, "status", lambda *_args: "missing")
    monkeypatch.setattr(range_proof, "PROOF_FILE", target)
    monkeypatch.setattr(
        range_proof,
        "render",
        lambda entries, _profile: json.dumps(
            {name: entry.fingerprint for name, entry in entries.items()}
        ),
    )
    return target


def test_each_part_runs_in_its_own_process(
    prepared_run: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auch ein einzelner Arbeiterplatz darf seinen Prozess nicht für den nächsten Teil behalten."""
    monkeypatch.setattr(runner, "_run_one", _pid_report)

    assert runner.main(["--all", "--jobs", "1"]) == 0
    identities = json.loads(prepared_run.read_text(encoding="utf-8"))
    assert len(identities) == 3
    assert len(set(identities.values())) == 3


def test_a_crashed_worker_leaves_neither_a_profile_nor_a_proof(
    prepared_run: Path,
    monkeypatch: pytest.MonkeyPatch,
    isolated_environment: dict[str, str | None],
) -> None:
    """Ein echter Prozessabbruch läuft durch den Elternabbau, ohne einen Nachweis zu erzeugen."""
    monkeypatch.setattr(runner, "_run_one", _crashing_report)

    with pytest.raises(BrokenProcessPool):
        runner.main(["--all", "--jobs", "1"])

    assert not prepared_run.exists()
    assert not list(prepared_run.parent.glob("solidon-part-ranges-*"))
    assert {variable: os.environ.get(variable) for variable in VARIABLES} == isolated_environment


@pytest.mark.parametrize("fails", [False, True])
@pytest.mark.parametrize("entry", ["main", "worker"])
def test_each_entry_restores_the_environment_and_removes_its_temporary_profile(
    monkeypatch: pytest.MonkeyPatch,
    isolated_environment: dict[str, str | None],
    entry: str,
    fails: bool,
) -> None:
    """Erfolg und Ausnahme räumen dieselben eigenen Dateien, bevor die Funktion zurückkehrt."""
    from app.core.knowledge.parts import range_check, range_proof

    folders: list[Path] = []

    def registry() -> SimpleNamespace:
        values = {os.environ[variable] for variable in VARIABLES}
        assert len(values) == 1
        folder = Path(values.pop())
        folders.append(folder)
        (folder / "probe.txt").write_text("nur Testdaten", encoding="utf-8")
        if fails:
            raise RuntimeError("isolated failure")
        spec = SimpleNamespace(version="1", params={})
        return SimpleNamespace(all=list, get=lambda _name: spec)

    monkeypatch.setattr(runner, "_registry", registry)
    monkeypatch.setattr(range_proof, "reference_profile", lambda: None)
    monkeypatch.setattr(range_proof, "load", dict)
    monkeypatch.setattr(range_proof, "fingerprint", lambda *_args: "fingerprint")
    monkeypatch.setattr(range_check, "part_corner_count", lambda _spec: 1)
    monkeypatch.setattr(
        range_check,
        "check_part",
        lambda *_args, **_kwargs: SimpleNamespace(checked=1, excluded=[], failures=[], passed=True),
    )

    def run() -> object:
        return runner.main(["--check"]) if entry == "main" else runner._run_one("part")

    if fails:
        with pytest.raises(RuntimeError, match="isolated failure"):
            run()
    else:
        run()

    assert folders and all(not folder.exists() for folder in folders)
    assert {variable: os.environ.get(variable) for variable in VARIABLES} == isolated_environment


def test_a_large_part_runs_in_windows_and_counts_them_together() -> None:
    """RM-544: Ein Baustein mit mehr Ecken als ein Ausschnitt läuft in mehreren Prozessen.

    Die Ausschnitte decken jede Ecke genau einmal, und bestanden ist er nur,
    wenn alle zusammen jede Ecke gefahren haben und keine gebrochen ist.
    """
    windows = runner._windows(2 * runner.SHARD_CORNERS + 5)
    assert windows[0] == (0, runner.SHARD_CORNERS)
    covered = [index for window in windows if window for index in range(*window)]
    assert covered[: 2 * runner.SHARD_CORNERS + 5] == list(range(2 * runner.SHARD_CORNERS + 5))
    assert runner._windows(runner.SHARD_CORNERS) == [None], "ein kleiner läuft am Stück"

    def piece(checked: int, failures: list[object]) -> dict[str, object]:
        return {
            "name": "part",
            "version": "1",
            "fingerprint": "f",
            "corners": 10,
            "checked": checked,
            "excluded": 1,
            "failures": failures,
            "passed": not failures,
            "seconds": 1.0,
        }

    whole = runner._merged([piece(6, []), piece(4, [])])
    assert whole["checked"] == 10 and whole["excluded"] == 2 and whole["passed"] is True
    assert runner._merged([piece(6, []), piece(3, [])])["passed"] is False, "eine Ecke fehlt"
    broken = runner._merged([piece(6, []), piece(4, [({}, "nicht geschlossen")])])
    assert broken["passed"] is False and len(broken["failures"]) == 1
