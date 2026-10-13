"""Der Registerabzug (W3, Konzept Codestruktur 4.1) sieht jede Änderung am Register, sonst nichts.

`tools/registry_dump.py` schreibt jedes Feld jedes Registereintrags außer der
Funktion. Ein Kernschritt gilt als „nur verschoben“, wenn der Abzug vorher und
nachher byte-gleich ist — das trägt nur, wenn der Abzug jede Änderung sieht und
ohne Änderung in jedem Prozess derselbe ist. Geprüft wird beides: die
Gegenproben aus Plan 2.3 an echten Einträgen (Feld geändert, Reihenfolge
getauscht, nur die Funktion getauscht) und zwei frische Prozesse mit
verschiedenem Hash-Startwert, Byte für Byte.
"""

from __future__ import annotations

import dataclasses
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.core.bootstrap import _OPERATION_MODULES, load_operations
from app.core.knowledge.parts.registry import PARTS, PartSpec
from app.core.registry.registry import REGISTRY, OperationSpec, Registry
from app.i18n import Figure, _
from tools import registry_dump

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def live() -> tuple[tuple[OperationSpec, ...], tuple[PartSpec, ...]]:
    """Das gefüllte Register in der Reihenfolge der Registrierung."""
    load_operations()
    return registry_dump.operations_in_order(REGISTRY), registry_dump.parts_in_order(PARTS)


def _estimate(mesh: object, params: object) -> int:
    """Eine Vorabzählung, wie ``expected_triangles`` sie trägt."""
    return 0


def test_every_operation_and_part_stands_in_registration_order(
    live: tuple[tuple[OperationSpec, ...], tuple[PartSpec, ...]],
) -> None:
    """Jede Op (Zahl = ``len(REGISTRY.all())``) und jeder Baustein, in Registrierungsfolge."""
    operations, parts = live
    names = list(registry_dump.sections(registry_dump.dump(operations, parts, ())))

    # Grundmenge: Jedes Modul aus ``_OPERATION_MODULES`` registriert mindestens eine Op (Plan S16).
    assert len(operations) == len(REGISTRY.all()) >= len(_OPERATION_MODULES)
    assert len(parts) == len(PARTS.all()) > 0
    assert names == [
        *(f"op:{spec.name}" for spec in operations),
        *(f"part:{spec.name}" for spec in parts),
        "messages",
    ]
    # ``Registry.all()`` sortiert nach Namen — die Folge der Registrierung ist eine andere.
    assert [spec.name for spec in operations] != [spec.name for spec in REGISTRY.all()]


def test_every_field_but_the_function_is_written(
    live: tuple[tuple[OperationSpec, ...], tuple[PartSpec, ...]],
) -> None:
    """Jedes Feld von ``OperationSpec`` und ``PartSpec`` außer ``fn`` steht in jedem Abschnitt."""
    operations, parts = live
    found = registry_dump.sections(registry_dump.dump(operations, parts, ()))

    for kind, specs, spec_type in (("op", operations, OperationSpec), ("part", parts, PartSpec)):
        expected = {field.name for field in dataclasses.fields(spec_type)} - {"fn"}
        for spec in specs:
            keys = {line.split(" = ", 1)[0] for line in found[f"{kind}:{spec.name}"]}
            assert {key for key in keys if "." not in key} == expected, spec.name
            assert {f"params.{entry.name}" for entry in spec.params.spec()} <= keys, spec.name


def test_a_changed_field_changes_the_dump_and_names_its_section(
    live: tuple[tuple[OperationSpec, ...], tuple[PartSpec, ...]],
) -> None:
    """Gegenprobe: ein Feld anders → anderer Abzug; der Vergleich nennt genau diesen Abschnitt."""
    operations, parts = live
    before = registry_dump.dump(operations, parts, ())
    first = operations[0]
    changed = dataclasses.replace(first, doc=_("Ein anderer Satz."))

    after = registry_dump.dump((changed, *operations[1:]), parts, ())

    assert after != before
    assert registry_dump.differences(before, after)[0] == f"geändert: [op:{first.name}]"


def test_a_swapped_order_changes_the_dump(
    live: tuple[tuple[OperationSpec, ...], tuple[PartSpec, ...]],
) -> None:
    """Gegenprobe: zwei Einträge getauscht → anderer Abzug, der Vergleich nennt die Folge."""
    operations, parts = live
    swapped = (operations[1], operations[0], *operations[2:])
    before = registry_dump.dump(operations, parts, ())

    found = registry_dump.differences(before, registry_dump.dump(swapped, parts, ()))

    assert found == [
        f"Reihenfolge: [op:{operations[1].name}] steht, wo vorher [op:{operations[0].name}] stand"
    ]


def test_a_registry_hands_out_its_registration_order() -> None:
    """Die Folge kommt aus der Registrierung, nicht aus dem Namen wie bei ``Registry.all()``."""
    load_operations()
    renamed, deleted = REGISTRY.get("rename_object"), REGISTRY.get("delete_object")
    registry = Registry()
    registry.register(renamed)
    registry.register(deleted)

    assert registry_dump.operations_in_order(registry) == (renamed, deleted)
    assert registry.all() == (deleted, renamed)


def test_only_a_changed_function_leaves_the_dump_alone(
    live: tuple[tuple[OperationSpec, ...], tuple[PartSpec, ...]],
) -> None:
    """Gegenprobe: ``fn`` getauscht → derselbe Abzug, an einer Op und an einem Baustein."""
    operations, parts = live
    before = registry_dump.dump(operations, parts, ())
    swapped_op = dataclasses.replace(operations[0], fn=lambda context, inputs, params: None)
    swapped_part = dataclasses.replace(parts[0], fn=lambda params, quality="fine": None)

    assert registry_dump.dump((swapped_op, *operations[1:]), parts, ()) == before
    assert registry_dump.dump(operations, (swapped_part, *parts[1:]), ()) == before
    assert (
        registry_dump.dump(operations, (dataclasses.replace(parts[0], version="0"), *parts[1:]), ())
        != before
    )


def test_a_changed_parameter_default_changes_the_dump(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gegenprobe am Schema: eine Vorgabe anders → anderer Abzug in genau dieser Zeile."""
    load_operations()
    spec = REGISTRY.get("create_box")
    schema = spec.params.spec()
    before = registry_dump.dump((spec,), (), ())
    changed = (dataclasses.replace(schema[0], default=123.5), *schema[1:])
    monkeypatch.setattr(spec.params, "__param_spec__", changed)

    found = registry_dump.differences(before, registry_dump.dump((spec,), (), ()))

    assert found[0] == "geändert: [op:create_box]"
    assert any(line.startswith(f"  +params.{schema[0].name} = ") for line in found)
    assert "default=123.5" in "".join(found)


def test_values_render_the_same_in_every_process() -> None:
    """Fälle mit bekanntem Ausgang: Menge sortiert, ``repr`` der Zahl, Text als Message-ID,
    Aufrufbares ohne Modul, Unterklasse mit Typ — und eine Adresse hält an."""
    assert registry_dump.render(frozenset({"b", "c", "a"})) == "{'a', 'b', 'c'}"
    # Kleine Zahlen hasht Python auf sich selbst, die Menge läuft 9, 10 —
    # sortiert wird nach dem Text, auch wo der Startwert nichts verschiebt.
    assert registry_dump.render(frozenset({9, 10})) == "{10, 9}"
    assert registry_dump.render(0.1) == "0.1"
    assert registry_dump.render((1,)) == "(1,)"
    assert registry_dump.render(_("Quader", "Grundform")) == "_('Quader', context='Grundform')"
    assert registry_dump.render(Figure("1.5")) == "Figure('1.5')"
    assert registry_dump.render(_estimate) == "_estimate"
    assert __name__ not in registry_dump.render(_estimate)
    with pytest.raises(registry_dump.DumpError, match="stabile"):
        registry_dump.render(object())


def test_the_messages_are_the_sorted_translation_keys() -> None:
    """``[messages]`` hält die Schlüssel sortiert, den Kontext mit ``\\x04`` sichtbar."""
    text = registry_dump.dump((), (), ["b", "Kontext\x04a"])

    assert registry_dump.sections(text)["messages"] == ["'Kontext\\x04a'", "'b'"]


def test_compare_names_what_differs_and_exits_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--compare`` endet mit 0 bei Gleichheit und mit 1 samt Abschnitt bei Abweichung."""
    text = "# Registerabzug\n\n[op:x]\nname = 'x'\n\n[messages]\n'a'\n"
    monkeypatch.setattr(registry_dump, "registered", lambda: text)
    earlier = tmp_path / "abzug.txt"
    earlier.write_text(text, encoding="utf-8", newline="\n")

    assert registry_dump.main(["--compare", str(earlier)]) == 0
    assert "byte-gleich" in capsys.readouterr().out

    earlier.write_text(text.replace("name = 'x'", "name = 'y'"), encoding="utf-8", newline="\n")
    assert registry_dump.main(["--compare", str(earlier)]) == 1
    assert "geändert: [op:x]" in capsys.readouterr().out


def test_two_fresh_processes_write_the_same_dump_byte_for_byte(
    tmp_path: Path, live: tuple[tuple[OperationSpec, ...], tuple[PartSpec, ...]]
) -> None:
    """Determinismus: zwei Prozesse mit verschiedenem Hash-Startwert, derselbe Abzug.

    Ein verschiedener Startwert ordnet jede Menge anders — eine, die ungeordnet
    in den Abzug käme, risse hier.
    """
    written = []
    for seed in ("1", "2"):
        target = tmp_path / f"abzug-{seed}.txt"
        finished = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "registry_dump.py"), "--out", str(target)],
            cwd=ROOT,
            env={**os.environ, "PYTHONHASHSEED": seed},
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        assert finished.returncode == 0, finished.stderr
        written.append(target.read_bytes())

    assert written[0] == written[1]
    found = registry_dump.sections(written[0].decode("utf-8"))
    operations, parts = live
    assert sum(name.startswith("op:") for name in found) == len(operations)
    assert sum(name.startswith("part:") for name in found) == len(parts)
    assert len(found["messages"]) > 1000
