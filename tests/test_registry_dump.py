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
from app.core.registry.registry import REGISTRY, OperationSpec
from app.i18n import Figure, _, extract
from tools import registry_dump

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def live() -> tuple[tuple[OperationSpec, ...], tuple[PartSpec, ...]]:
    """Das gefüllte Register in der Reihenfolge der Registrierung."""
    load_operations()
    return REGISTRY.in_registration_order(), PARTS.in_registration_order()


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
            # Plan 2.3: der Typ als Text, je Datenfeld des Parametersatzes.
            typed = {f"params.{field.name}.type" for field in spec.params.fields()}
            assert typed <= keys, spec.name


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


def test_the_dump_of_the_registry_follows_its_registration_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``registered()`` liest ``in_registration_order()`` (CS-17), nicht ``all()``.

    Die Methode selbst prüft ``test_registry.py``; hier geht es darum, dass der
    Abzug sie benutzt. Die Texte bleiben draußen, sie kosten Sekunden und
    tragen zur Folge nichts bei.
    """
    load_operations()
    monkeypatch.setattr(extract, "message_ids", lambda: ())

    found = registry_dump.sections(registry_dump.registered())
    names = [name for name in found if name.startswith("op:")]

    assert names == [f"op:{spec.name}" for spec in REGISTRY.in_registration_order()]
    assert names != [f"op:{spec.name}" for spec in REGISTRY.all()]
    assert [name for name in found if name.startswith("part:")] == [
        f"part:{spec.name}" for spec in PARTS.in_registration_order()
    ]


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
    # Werte eines Textes gehören zu ihm; im heutigen Register trägt keiner welche.
    assert registry_dump.render(_("{n} Stück", n=3)) == "_('{n} Stück', values={'n': 3})"
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


def test_compare_holds_bytes_and_stops_on_what_it_cannot_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Byte-gleich heißt Bytes: Eine CRLF-Kopie weicht ab (Exit 1); eine fehlende oder
    nicht als UTF-8 lesbare Datei ist nicht verglichen (Exit 2), nie „weicht ab“
    (Durchsicht W13, Fund 8)."""
    text = "# Registerabzug\n\n[op:x]\nname = 'x'\n"
    monkeypatch.setattr(registry_dump, "registered", lambda: text)
    earlier = tmp_path / "abzug.txt"

    earlier.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    assert registry_dump.main(["--compare", str(earlier)]) == 1
    assert "Zeilenenden" in capsys.readouterr().out

    assert registry_dump.main(["--compare", str(tmp_path / "fehlt.txt")]) == 2
    assert "nicht verglichen" in capsys.readouterr().err

    earlier.write_bytes(b"\xff\xfe")
    assert registry_dump.main(["--compare", str(earlier)]) == 2
    assert "nicht verglichen" in capsys.readouterr().err


def test_two_fresh_processes_write_the_same_dump_byte_for_byte(
    tmp_path: Path, live: tuple[tuple[OperationSpec, ...], tuple[PartSpec, ...]]
) -> None:
    """Determinismus: zwei Prozesse mit verschiedenem Hash-Startwert, derselbe Abzug.

    Ein verschiedener Startwert ordnet jede Menge anders — eine, die ungeordnet
    in den Abzug käme, risse hier. Beide laufen zugleich, und während sie
    rechnen, sammelt dieser Prozess die ``tr()``-Schlüssel, gegen die
    ``[messages]`` steht (Durchsicht W13, Funde 5 und 9).
    """
    targets = [tmp_path / f"abzug-{seed}.txt" for seed in ("1", "2")]
    running = [
        subprocess.Popen(
            [sys.executable, str(ROOT / "tools" / "registry_dump.py"), "--out", str(target)],
            cwd=ROOT,
            env={**os.environ, "PYTHONHASHSEED": seed},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )
        for seed, target in zip(("1", "2"), targets, strict=True)
    ]
    expected = [repr(message) for message in sorted(extract.message_ids())]
    for process in running:
        _, errors = process.communicate(timeout=300)
        assert process.returncode == 0, errors
    written = [target.read_bytes() for target in targets]

    assert written[0] == written[1]
    found = registry_dump.sections(written[0].decode("utf-8"))
    operations, parts = live
    assert sum(name.startswith("op:") for name in found) == len(operations)
    assert sum(name.startswith("part:") for name in found) == len(parts)
    assert found["messages"] == expected
