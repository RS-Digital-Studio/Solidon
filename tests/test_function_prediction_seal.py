"""Das Urteil an V4 prüft die versiegelte Vorhersage selbst (RC-1, FD-168).

Das Tor im Fallprozess bindet eine Vorhersage vor dem Klick; ``report`` nahm
danach jedes *gut* an V4, dessen ``prediction_bound`` als Zeichenkette unter
den Bindungen der Protokolle stand. Eine andere Vorhersage im Urteil, eine nach
dem Lauf überschriebene Siegeldatei und eine erfundene Rundenkennung gingen
durch. Jetzt liest ``report`` die Datei am Pfad der Bindung, rechnet ihren
SHA256 nach und vergleicht ihre Vorhersage mit der des Urteils; eine
Rundenkennung braucht ihren ``[[run]]``, und die Bindung gilt gegen dessen
Protokolle. Ohne Fenster, durch ``function_report.write`` wie ``report``.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from tests.bench_fakes import ROWS
from tools import function_verdict_rules as rules
from tools.function_report import write
from tools.function_samples import _verdict, sample_context, sample_protocol

SEALED = "cases/1/v4/prediction-before-click.json"
HONEST = "Übernehmen vergrößert nur Bohrung 1 auf 8 mm."
SEAL = f"seal.json {'e' * 64}"


def _run(folder: Path, text: str = HONEST) -> str:
    """Ein Lauf mit einem Fall, dessen Tor ``text`` freigab; die Bindung des Protokolls."""
    raw = json.dumps({"prediction": text}, ensure_ascii=False).encode("utf-8")
    sealed = folder / SEALED
    sealed.parent.mkdir(parents=True)
    sealed.write_bytes(raw)
    bound = f"{SEALED} {hashlib.sha256(raw).hexdigest()}"
    protocol = copy.deepcopy(sample_protocol())
    protocol["prediction"] = {**protocol["prediction"], "bound": bound, "path": SEALED}
    (folder / "cases" / "1" / "function.json").write_text(
        json.dumps(protocol, ensure_ascii=False), encoding="utf-8"
    )
    (folder / "rows.json").write_text(json.dumps([ROWS[1]]), encoding="utf-8")
    return bound


def _verdict_file(path: Path, entry: dict[str, Any], *, rounds: dict[str, str]) -> None:
    lines = [f'[[run]]\nname = "lauf"\nhead = "a280ee8f5"\nseal = "{SEAL}"\n']
    lines += [
        f'[[run]]\nkey = "{key}"\nname = "{name}"\nhead = "a280ee8f5"\nseal = "{SEAL}"\n'
        for key, name in rounds.items()
    ]
    lines.append("[[verdict]]")
    lines += [f"{key} = {json.dumps(value, ensure_ascii=False)}" for key, value in entry.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _reasons(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    entry: dict[str, Any],
    *,
    rounds: dict[str, str] | None = None,
    runs: Path | None = None,
) -> list[str]:
    """Die Gründe, aus denen ``report`` das Urteil an V4 abweist — leer, wenn es zählt."""
    state = tmp_path / "state"
    state.mkdir(exist_ok=True)
    _verdict_file(state / "urteile-d04.toml", entry, rounds=rounds or {})
    capsys.readouterr()
    write(
        tmp_path / "lauf",
        state=state,
        date="2026-10-16",
        context=sample_context(),
        solutions={},
        common_goals={},
        **({"runs": runs} if runs is not None else {}),
    )
    marker = "ungültig: D4 drill_hole V4: "
    return [
        line.removeprefix(marker)
        for line in capsys.readouterr().out.splitlines()
        if line.startswith(marker)
    ]


def _v4(bound: str, text: str = HONEST) -> dict[str, Any]:
    return _verdict(criterion="V4", prediction=text, prediction_bound=bound)


def test_the_sealed_prediction_of_this_run_carries_v4(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bound = _run(tmp_path / "lauf")
    assert _reasons(tmp_path, capsys, _v4(bound)) == []
    # Leerraum zählt nicht: Die Vorhersage steht im Urteil umbrochen.
    assert _reasons(tmp_path, capsys, _v4(bound, HONEST.replace(" ", "\n  ", 2))) == []


def test_a_different_prediction_than_the_sealed_one_is_rejected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bound = _run(tmp_path / "lauf")
    reasons = _reasons(tmp_path, capsys, _v4(bound, "Übernehmen setzt Bohrung 1 auf 6 mm."))
    assert any(rules.PREDICTION_DIFFERS in reason for reason in reasons), reasons


def test_a_seal_overwritten_after_the_run_is_rejected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bound = _run(tmp_path / "lauf")
    (tmp_path / "lauf" / SEALED).write_text('{"prediction": "nachher geschrieben"}', "utf-8")
    reasons = _reasons(tmp_path, capsys, _v4(bound))
    assert any(rules.SEAL_CHANGED in reason for reason in reasons), reasons


def test_a_missing_seal_is_rejected(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Eine bildlose Kopie ohne ``v4`` belegt nichts; ``--runs`` nennt den Lauf selbst."""
    bound = _run(tmp_path / "lauf")
    (tmp_path / "lauf" / SEALED).unlink()
    reasons = _reasons(tmp_path, capsys, _v4(bound))
    assert any(rules.SEAL_MISSING in reason for reason in reasons), reasons


def test_an_invented_round_is_rejected(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _run(tmp_path / "lauf")
    invented = f"zz:cases/999/v4/prediction-before-click.json {'0' * 64}"
    reasons = _reasons(tmp_path, capsys, _v4(invented))
    assert any(rules.UNKNOWN_ROUND in reason for reason in reasons), reasons


def test_a_round_binding_holds_against_the_protocols_and_seal_of_its_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``v4:`` mit ``[[run]]``: Ordner aus der Ablage der Läufe, Bindung aus dessen Protokollen."""
    _run(tmp_path / "lauf", "Eine ältere Vorhersage.")
    store = tmp_path / "ablage"
    bound = _run(store / "runde" / "v4")
    rounds = {"v4": "runde/v4"}
    assert _reasons(tmp_path, capsys, _v4(f"v4:{bound}"), rounds=rounds, runs=store) == []
    # Ohne Ablage findet ``report`` den Lauf der Runde nicht — kein Beleg, kein „gut“.
    missing = _reasons(tmp_path, capsys, _v4(f"v4:{bound}"), rounds=rounds)
    assert any(rules.SEAL_MISSING in reason for reason in missing), missing
    # Eine Bindung, die das Tor jenes Laufs nicht freigab, trägt auch mit Kennung nicht.
    other = f"v4:{SEALED} {'0' * 64}"
    reasons = _reasons(tmp_path, capsys, _v4(other), rounds=rounds, runs=store)
    assert rules.UNRELEASED_PREDICTION in reasons, reasons
