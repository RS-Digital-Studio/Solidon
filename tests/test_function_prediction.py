"""Das Vorhersagetor: V4 bindet eine Vorhersage vor dem Handlungsklick (FD-168, FD-148).

Bis hierher hielt kein Fallprozess vor dem Klick an; die Fälle 29, 36 und 37
schrieben ihre Vorhersage nach dem Lauf, und ``report`` weist jedes V4 ohne
``prediction_bound`` ab. Jetzt hält ein Fall mit ``Variant.predict`` vor dem
Klick an, legt Bild und Texte vor, prüft die Vorhersage gegen das Bild,
versiegelt sie und gibt erst dann den Klick frei — im Hauptweg vor dem
Übernehmen, im Sprachfall vor der Soforthandlung. Ohne Fenster: nachgestellter
Zeitgeber, ein Bild als Datei, echte Schrittfolge.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests.bench_fakes import FakeTimer, run_machine
from tools import (
    function_bench,
    function_machine,
    function_prediction,
    function_setup,
    function_surface,
)
from tools.function_machine import PHASE_TIMEOUT_S, Step
from tools.function_prediction import PredictionGate
from tools.function_verdict_rules import UNRELEASED_PREDICTION, release_problems, releases_of


def _gate(tmp_path: Path, timer: FakeTimer, *, wait_s: float = 60.0) -> PredictionGate:
    out = tmp_path
    folder = out / "cases" / "001"
    folder.mkdir(parents=True)
    data: dict[str, Any] = {"images": [], "steps": [], "version": {"commit": "abc123"}}

    def picture(label: str) -> None:
        path = folder / f"{label}.png"
        path.write_bytes(f"Bild {label}".encode())
        data["images"].append(path.relative_to(out).as_posix())

    return PredictionGate(
        folder / "v4",
        out,
        data,
        row="resize_hole",
        target="measure.apply",
        picture=picture,
        texts=lambda: ["Bohrung ändern", "Vorschau — noch nicht übernommen"],
        clock=timer.clock,
        wait_s=wait_s,
    )


def _prediction(ready: dict[str, Any], **changed: Any) -> dict[str, Any]:
    return {
        **{key: ready[key] for key in function_prediction.BINDING_KEYS},
        "title": "Bohrung ändern",
        "first_sentence": "Ausgangswert: eingepasst.",
        "preview": "Heller Umriss an Bohrung 1.",
        "prediction": "Übernehmen vergrößert nur Bohrung 1 auf 8 mm.",
        **changed,
    }


def _run(timer: FakeTimer, gate: PredictionGate, write_at: list[tuple[float, Any]]) -> list[str]:
    """Tor, Klick, Bild danach im echten Automaten; ``write_at`` legt Dateien zur Uhrzeit ab."""
    events: list[str] = []

    def click(machine: Any) -> None:
        events.append(f"klick gebunden={gate.record['bound'] is not None}")

    for moment, write in write_at:
        timer.schedule(int(moment * 1000), lambda write=write: write(gate))
    steps = [*gate.before_steps(), Step("klick", click), *gate.after_steps()]
    machine = run_machine(timer, steps, timeout_s=600.0)
    assert machine.error is None, machine.error
    return events


def _write(text: Any) -> Any:
    def write(gate: PredictionGate) -> None:
        ready = json.loads((gate.folder / "ready.json").read_text(encoding="utf-8"))
        value = text(ready) if callable(text) else text
        raw = value if isinstance(value, bytes) else json.dumps(value).encode("utf-8")
        (gate.folder / "prediction.json").write_bytes(raw)

    return write


def test_the_click_waits_until_a_prediction_that_belongs_to_the_picture_is_sealed(
    tmp_path: Path,
) -> None:
    timer = FakeTimer()
    gate = _gate(tmp_path, timer)
    events = _run(timer, gate, [(5.0, _write(_prediction))])
    assert events == ["klick gebunden=True"]
    ready = json.loads((gate.folder / "ready.json").read_text(encoding="utf-8"))
    assert ready["row"] == "resize_hole" and ready["commit"] == "abc123"
    assert ready["texts"] == ["Bohrung ändern", "Vorschau — noch nicht übernommen"]
    images = ready["images"]
    assert list(images) == ["cases/001/v4-vorher.png"]
    assert images["cases/001/v4-vorher.png"] == hashlib.sha256(b"Bild v4-vorher").hexdigest()
    raw = (gate.folder / "prediction.json").read_bytes()
    sealed = gate.folder / "prediction-before-click.json"
    assert sealed.read_bytes() == raw
    sha = hashlib.sha256(raw).hexdigest()
    release = json.loads((gate.folder / "release.json").read_text(encoding="utf-8"))
    assert release["prediction_sha256"] == sha and release["target"] == "measure.apply"
    record = gate.data["prediction"]
    assert record["bound"] == f"cases/001/v4/prediction-before-click.json {sha}"
    assert record["ready"] == "cases/001/v4/ready.json"
    assert record["after"] == ["cases/001/v4-nachher.png"]
    after = json.loads((gate.folder / "after.json").read_text(encoding="utf-8"))
    assert list(after["images"]) == ["cases/001/v4-nachher.png"]


@pytest.mark.parametrize(
    ("wrong", "problem"),
    [
        ({"nonce": "falsch"}, "nonce gehört nicht zu diesem Bild"),
        ({"before_sha256": "0" * 64}, "before_sha256 gehört nicht zu diesem Bild"),
        ({"prediction": " "}, "prediction ist leer"),
    ],
)
def test_a_prediction_that_does_not_belong_is_rejected_and_the_gate_keeps_waiting(
    tmp_path: Path, wrong: dict[str, Any], problem: str
) -> None:
    timer = FakeTimer()
    gate = _gate(tmp_path, timer)
    events = _run(
        timer,
        gate,
        [
            (2.0, _write(lambda ready: _prediction(ready, **wrong))),
            (6.0, _write(_prediction)),
        ],
    )
    assert events == ["klick gebunden=True"]
    rejected = gate.data["prediction"]["rejected"]
    assert len(rejected) == 1 and problem in rejected[0]["problems"]


def test_without_a_prediction_the_click_falls_after_the_wait_and_v4_stays_unbound(
    tmp_path: Path,
) -> None:
    timer = FakeTimer()
    gate = _gate(tmp_path, timer, wait_s=3.0)
    events = _run(timer, gate, [])
    assert events == ["klick gebunden=False"]
    record = gate.data["prediction"]
    assert record["bound"] is None and "keine gültige Vorhersage binnen 3 s" in record["reason"]
    assert not (gate.folder / "prediction-before-click.json").exists()
    assert timer.now >= 3.0


def test_an_unreadable_prediction_is_rejected_not_fatal(tmp_path: Path) -> None:
    timer = FakeTimer()
    gate = _gate(tmp_path, timer, wait_s=4.0)
    _run(timer, gate, [(1.0, _write(b"{kaputt"))])
    assert "nicht lesbar" in gate.data["prediction"]["rejected"][0]["problems"][0]
    assert gate.data["prediction"]["bound"] is None


def test_a_gate_of_an_earlier_run_stays_beside_the_new_one(tmp_path: Path) -> None:
    """Mit ``--again``: Die alte Vorhersage wird nie wiederverwendet, aber auch nicht gelöscht."""
    timer = FakeTimer()
    gate = _gate(tmp_path, timer)
    gate.folder.mkdir(parents=True)
    (gate.folder / "prediction-before-click.json").write_text("alt", encoding="utf-8")
    _run(timer, gate, [(1.0, _write(_prediction))])
    earlier = [path for path in gate.folder.parent.iterdir() if path.name.startswith("v4-")]
    assert [path for path in earlier if path.is_dir()], earlier
    assert gate.data["prediction"]["bound"] is not None


# --- Anschluss an Hauptweg und Sprachfall --------------------------------------------


def _main_flow(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, variant: Any) -> list[str]:
    """``phase_main`` mit nachgebauten Teilen; gibt die Namen der Schritte des Hauptwegs zurück."""
    flow = object.__new__(function_bench.FunctionFlow)
    flow.row = {"id": "resize_hole", "target": "feature:resize_hole"}
    flow.spec = {"inputs": {"feature.field:resize_hole.diameter": 8.0}}
    flow.variant = variant
    flow.apply_target = "feature.apply"
    flow.folder, flow.out = tmp_path / "cases" / "001", tmp_path
    flow.data = {"images": [], "steps": [], "unmeasured": {}, "version": {}}
    flow.window = object()
    flow.walker = SimpleNamespace(before_target=None)
    flow.snapshot = lambda label: {}
    flow.picture = lambda label: None
    flow.path_steps = lambda: [Step("weg", lambda machine: None)]
    flow.input_steps = lambda inputs: [Step("eingabe", lambda machine: None)]
    flow.preview_steps = lambda: [Step("vorschau", lambda machine: None)]
    flow.still_step = lambda name, root: Step(name, lambda machine: None)
    flow.surface = lambda: None
    flow.apply_step = lambda: Step("übernehmen", lambda machine: None)
    flow.apply_steps = lambda acting: ([Step("uhr", lambda machine: None), acting], lambda: None)
    seen: list[str] = []

    def run_steps(label: str, steps: list[Step], timeout_s: float | None = None) -> bool:
        seen.extend(step.name for step in steps)
        return True

    flow.run_steps = run_steps
    flow.phase_main()
    return seen


def test_the_main_way_binds_before_the_click_that_applies(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    variant = function_setup.Variant.of({"set": "vorhersage", "predict": True})
    names = _main_flow(monkeypatch, tmp_path, variant)
    assert names[names.index("vor dem übernehmen") + 1 :] == [
        "vorhersage anfragen",
        "vorhersage binden",
        "uhr",
        "übernehmen",
        "vorhersage: bild danach",
    ]


def test_without_the_variant_the_main_way_has_no_gate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    names = _main_flow(monkeypatch, tmp_path, function_setup.Variant())
    assert not [name for name in names if name.startswith("vorhersage")]


@pytest.mark.parametrize("predict", [True, False])
def test_a_phase_with_the_gate_may_wait_its_term_longer(
    monkeypatch: pytest.MonkeyPatch, predict: bool
) -> None:
    """Die Frist der Phase umfasst die des Tors — sonst bräche der Automat beim Warten ab."""
    flow = object.__new__(function_bench.FunctionFlow)
    flow.variant = function_setup.Variant.of({"predict": predict})
    flow.walker = SimpleNamespace(phase="")
    flow.data = {"findings": [], "errors": [], "closed_by_escape": []}
    flow.persist = lambda: None
    flow.pump = lambda: None
    terms: list[float] = []
    monkeypatch.setattr(
        function_bench, "drive", lambda machine, steps, pump, clock, timeout: terms.append(timeout)
    )
    assert flow.run_steps("weg", [])
    assert terms == [
        PHASE_TIMEOUT_S + (function_prediction.extra_s(flow.variant) if predict else 0)
    ]
    assert function_prediction.extra_s(flow.variant) == (
        function_prediction.PREDICTION_WAIT_S + function_machine.STEP_TIMEOUT_S if predict else 0.0
    )


def test_the_language_pass_binds_before_the_click_of_an_action_that_acts_at_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Auch im Sprachfall (FD-168): vor der Soforthandlung, im Ordner der Zeile."""
    target = "finding.action:place_on_bed"
    flow = object.__new__(function_bench.FunctionFlow)
    flow.row = {"id": target, "target": target}
    flow.variant = function_setup.Variant.of({"set": "sprachen", "language": "fr", "predict": True})
    flow.folder, flow.out = tmp_path / "cases" / "040", tmp_path
    flow.data = {"images": [], "steps": [], "unmeasured": {}}
    flow.window = object()
    flow.surface = lambda: None
    flow.claim_surface = lambda root: None
    flow.capture_surface = lambda root: None
    flow.picture = lambda label: None
    flow.still_step = lambda name, root: Step(name, lambda machine: None)

    def step(name: str, button: str = "left", *, stop_before_target: Any = False) -> Step:
        return Step(f"klick {name}", lambda machine: stop_before_target and stop_before_target())

    flow.walker = SimpleNamespace(step=step)
    flow.path_steps = lambda: [step(target)]
    monkeypatch.setattr(function_surface, "acts_at_once", lambda window, name: True)
    monkeypatch.setattr(function_bench, "route_of", lambda row: [(target, "left")])
    inserted: list[str] = []
    machine = SimpleNamespace(insert=lambda steps: inserted.extend(s.name for s in steps))

    def run_steps(label: str, steps: list[Step], timeout_s: float | None = None) -> bool:
        for one in steps:
            one.act(machine)
        return True

    flow.run_steps = run_steps
    flow.phase_surface()
    assert inserted == [
        "vorhersage anfragen",
        "vorhersage binden",
        f"klick {target}",
        "geöffnete fläche steht still",
        "geöffnete fläche aufnehmen",
        "vorhersage: bild danach",
    ]


def test_the_variant_set_and_the_language_cases_carry_the_gate() -> None:
    from tests.bench_fakes import ROWS
    from tools.file_acceptance import function_cases
    from tools.function_cases import prediction_wait_s

    cases = function_cases(
        ROWS, packages=["D4"], variant_sets=["vorhersage", "sprachen"], languages=("de",)
    )
    function = [case for case in cases if case.kind == "function"]
    language = [case for case in cases if case.kind == "language"]
    assert function and all(case.variant["set"] == "vorhersage" for case in function)
    assert all(case.variant["predict"] for case in [*function, *language])
    assert function_setup.PHASES["vorhersage"] == ("main",)
    assert prediction_wait_s(function[0], ROWS) == function_prediction.PREDICTION_WAIT_S
    plain = function_cases(ROWS, packages=["D4"], variant_sets=["basis"])
    assert prediction_wait_s(plain[0], ROWS) == 0.0
    assert not plain[0].variant["predict"]


# --- Urteil: die Bindung ist die des Laufs -------------------------------------------


def _bound(sha: str = "a" * 64) -> str:
    return f"cases/001/v4/prediction-before-click.json {sha}"


def test_a_bound_prediction_must_be_one_the_gate_of_this_run_released() -> None:
    protocols = [
        {"row": {"id": "resize_hole"}, "prediction": {"bound": _bound()}},
        {"row": {"id": "report"}, "prediction": {"bound": None, "reason": "keine"}},
        {"row": {"id": "drill_hole"}},
    ]
    releases = releases_of(protocols)
    assert releases == {"resize_hole": frozenset({_bound()})}
    entry = {"row": "resize_hole", "criterion": "V4", "prediction_bound": _bound()}
    assert release_problems(entry, "V4", releases) == []
    other = {**entry, "prediction_bound": _bound("b" * 64)}
    assert release_problems(other, "V4", releases) == [UNRELEASED_PREDICTION]
    elsewhere = {**entry, "row": "report"}
    assert release_problems(elsewhere, "V4", releases) == [UNRELEASED_PREDICTION]
    # Eine Bindung an eine andere Runde prüft hier nur ihre Form.
    rounded = {**other, "prediction_bound": f"v4:{_bound('c' * 64)}"}
    assert release_problems(rounded, "V4", releases) == []
    assert release_problems(other, "V4", None) == []


def test_report_takes_a_good_v4_only_with_the_binding_the_gate_released() -> None:
    """Durch ``check_verdicts``: die Bindung aus dem Protokoll angenommen, eine andere nicht."""
    import copy

    from tools.function_points import judge_case
    from tools.function_report import check_verdicts
    from tools.function_samples import _verdict, sample_context, sample_protocol

    protocol = copy.deepcopy(sample_protocol())
    case = judge_case(protocol, sample_context())
    released = releases_of([protocol])
    bound = protocol["prediction"]["bound"]
    good = _verdict(
        criterion="V4",
        point=None,
        prediction="Übernehmen vergrößert nur Bohrung 1.",
        prediction_bound=bound,
    )
    checked = check_verdicts([good], outcomes={case.row_id: case}, releases=released)
    assert checked.rejected == (), checked.rejected
    other = {**good, "prediction_bound": _bound("d" * 64)}
    checked = check_verdicts([other], outcomes={case.row_id: case}, releases=released)
    assert [reasons for _entry, reasons in checked.rejected] == [(UNRELEASED_PREDICTION,)]


def test_v4_names_the_binding_of_the_gate() -> None:
    import copy

    from tools.function_points import judge_case
    from tools.function_samples import sample_context, sample_protocol

    protocol = copy.deepcopy(sample_protocol())
    protocol["prediction"] = None
    assert judge_case(protocol, sample_context()).criteria["V4"].summary == "Vorhersage im Urteil"
    protocol["prediction"] = {"bound": _bound(), "path": "cases/001/v4/x.json", "after": []}
    outcome = judge_case(protocol, sample_context()).criteria["V4"]
    assert outcome.verdict == "stufe_b" and outcome.measurement["bound"] == _bound()
    protocol["prediction"] = {"bound": None, "reason": "keine gültige Vorhersage binnen 600 s"}
    outcome = judge_case(protocol, sample_context()).criteria["V4"]
    assert "binnen 600 s" in outcome.summary and outcome.measurement["bound"] is None
