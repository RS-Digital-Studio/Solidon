"""Ein Feld auf dem Weg, das erst eine Eingabe freigibt: tippen statt nur klicken (FD-175).

*Erzeugen* in *Modell erzeugen* bleibt grau, bis eine Beschreibung dasteht. Der
Weg der Zeile *Nicht übernommene Versuche* kam deshalb nie über *Erzeugen*
hinaus: „nach 60 s ist generate.start noch grau“. Ein Schritt mit ``text`` ist
jetzt ein Feld, in das der Kunde tippt — hinklicken, alles markieren, tippen.
"""

from __future__ import annotations

from dataclasses import asdict
from types import SimpleNamespace
from typing import Any

import pytest

from tools import function_list as fl
from tools import function_scenes as fscenes
from tools.function_bench import FunctionFlow
from tools.function_setup import route_of, route_texts, walk_target

ROW_ID = "meldung:confirm_generation_loss"


@pytest.fixture(scope="module")
def row() -> dict[str, Any]:
    return next(asdict(entry) for entry in fl.rows() if entry.id == ROW_ID)


def test_each_step_of_the_way_says_what_is_typed(row: dict[str, Any]) -> None:
    route = route_of(row)
    texts = route_texts(row)
    assert len(texts) == len(route)
    typed = [(name, text) for (name, _button), text in zip(route, texts, strict=True) if text]
    assert typed == [("generate.prompt", "Würfel")]
    assert route[-1][0] == walk_target(row) and texts[-1] == ""


def test_a_field_on_the_way_is_typed_into_and_the_rest_is_clicked(row: dict[str, Any]) -> None:
    done: list[tuple[str, ...]] = []
    flow = SimpleNamespace(
        row=row,
        walker=SimpleNamespace(step=lambda name, *args, **named: done.append(("klick", name))),
        typed_steps=lambda name, text, number: [done.append(("tippen", name, text))],
        action_step=lambda name: done.append(("handlung", name)),
    )
    steps = FunctionFlow.path_steps(flow)  # type: ignore[arg-type]
    names = [name for name, _button in route_of(row)]
    assert len(steps) == len(names)
    assert done == [
        ("tippen", name, "Würfel") if name == "generate.prompt" else ("klick", name)
        for name in names
    ]


def test_text_on_the_way_is_text() -> None:
    spec = {
        "start_scene": "leer",
        "route": [{"target": "menu:menubar.ueber_solidon", "text": 3}],
    }
    entries = {"dialog:about_dialog": fl.SpecEntry("D12", "d12.toml", spec)}
    issues = fl.validate_specs(fl.rows(), entries, fscenes.load_scenes())
    assert any("ist kein Text" in issue for issue in issues), issues
