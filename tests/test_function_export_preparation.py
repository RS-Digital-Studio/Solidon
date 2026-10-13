"""Die Exportvorbereitung muss den Umfang nach einer früheren Auswahl neu herstellen."""

from types import SimpleNamespace

import pytest

from tests.bench_fakes import FakeTimer, run_machine
from tools import function_bench, function_setup, function_surface
from tools.function_machine import Step


@pytest.mark.parametrize("previous_selection", [[], ["obj_1"]])
@pytest.mark.parametrize("escape_works", [True, False])
def test_export_preparation_does_not_reuse_the_previous_scene_selection(
    tmp_path, previous_selection, escape_works
):
    """Nach decimate_mesh heißt obj_1 im nächsten Projekt etwas anderes."""
    selection = list(previous_selection)
    exported = []
    typed = []
    flow = object.__new__(function_bench.FunctionFlow)
    flow.setup = function_setup.scene_setup("export_gemischt")
    flow.folder = tmp_path
    flow.window = SimpleNamespace(
        object_tree=SimpleNamespace(selected_objects=lambda: tuple(selection)),
        session=SimpleNamespace(
            last_result=SimpleNamespace(scene=SimpleNamespace(objects={"obj_1": 1, "obj_2": 2}))
        ),
    )

    def keys(sequence):
        typed.append(sequence.toString() if hasattr(sequence, "toString") else sequence)
        if typed[-1] == "Esc" and escape_works:
            selection.clear()

    def step(target, button="left"):
        return Step(target, lambda machine: exported.append(tuple(selection)))

    flow.ports = SimpleNamespace(keys=keys)
    flow.walker = SimpleNamespace(step=step, record=lambda entry: None)
    steps = flow.preparation_steps()
    end = next(index for index, item in enumerate(steps) if item.name == "command:file.export")
    machine = run_machine(FakeTimer(), steps[: end + 1])
    if previous_selection and not escape_works:
        assert machine.error and "Export" in machine.error
        assert not exported
    else:
        assert machine.error is None
        assert exported == [()]
    assert typed == ["Esc"]


@pytest.mark.parametrize("selected", [(), ("obj_1", "obj_2"), ("obj_1",), ("gone",)])
def test_export_scope_rejects_only_an_unproven_subset(selected):
    """Keine oder alle ausgewählt heißt ganze Szene; Teilmenge und fremde Kennung halten an."""
    window = SimpleNamespace(
        object_tree=SimpleNamespace(selected_objects=lambda: selected),
        session=SimpleNamespace(
            last_result=SimpleNamespace(scene=SimpleNamespace(objects={"obj_1": 1, "obj_2": 2}))
        ),
    )
    if selected and set(selected) != {"obj_1", "obj_2"}:
        with pytest.raises(RuntimeError, match="Export"):
            function_surface.require_full_export_scope(window)
    else:
        function_surface.require_full_export_scope(window)
