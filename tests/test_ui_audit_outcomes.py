"""Der Fensterprüfstand darf übersprungene Arbeit nicht als Erfolg melden."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.run_ui_audit import Outcome, export_round, report


@pytest.mark.parametrize("objects,exported,error", [(0, 0, ""), (1, 0, ""), (1, 1, "Fehler")])
def test_incomplete_runs_fail_the_report(objects: int, exported: int, error: str) -> None:
    outcome = Outcome("Körper", "Modell", objects=objects, exported=exported, error=error)
    assert report({"Modelle": [outcome]}, []) == 1


def test_a_successful_export_may_report_model_findings() -> None:
    outcome = Outcome("Körper", "Modell", objects=1, exported=1, findings=["warning:mesh.open"])
    assert report({"Modelle": [outcome]}, []) == 0


@pytest.mark.parametrize("state", ["aborted", "empty", "missing"])
def test_export_requires_a_completed_nonempty_result(tmp_path: Path, state: str) -> None:
    result = (
        None
        if state == "missing"
        else SimpleNamespace(
            complete=state != "aborted",
            stopped_at=7,
            scene=SimpleNamespace(objects={} if state == "empty" else {"one": object()}),
        )
    )
    with pytest.raises(RuntimeError):
        export_round(SimpleNamespace(last_result=result), tmp_path, "Körper")


@pytest.mark.parametrize("failure", ["exception", "missing", "empty", "partial"])
def test_export_failure_reaches_the_audit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    """Ein fertiges Rechenergebnis ersetzt keine erfolgreich geschriebene Datei."""
    from app.core.export import writer

    session = SimpleNamespace(
        last_result=SimpleNamespace(complete=True, scene=SimpleNamespace(objects={"a": object()})),
        profile=object(),
        project=SimpleNamespace(document=SimpleNamespace(sources={})),
    )
    monkeypatch.setattr(
        writer, "plan_export", lambda *_args, **_kwargs: SimpleNamespace(findings=[])
    )

    def write(*_args: object) -> list[Path]:
        if failure == "exception":
            raise OSError("Datenträger voll")
        first = tmp_path / "one.3mf"
        if failure != "missing":
            first.write_bytes(b"" if failure == "empty" else b"fertig")
        return [first, tmp_path / "two.3mf"] if failure == "partial" else [first]

    monkeypatch.setattr(writer, "write_plan", write)
    with pytest.raises((OSError, RuntimeError)):
        export_round(session, tmp_path, "Körper")
