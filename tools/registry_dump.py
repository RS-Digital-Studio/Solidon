"""Registerabzug (W3, Konzept Codestruktur 4.1): jedes Feld jedes Registereintrags als Text.

Ein Verschiebeschritt darf am Register nichts ändern. Der Abzug macht das
prüfbar: In Registerreihenfolge je Operation ein Abschnitt ``[op:<name>]`` mit
jedem Feld von ``OperationSpec`` außer ``fn``, danach je Baustein
``[part:<name>]`` mit jedem Feld von ``PartSpec`` außer ``fn``, zuletzt
``[messages]`` mit den sortierten ``tr()``-Schlüsseln, wie ``app.i18n.extract``
sie einsammelt. Vor und nach jedem Kernschritt ist er byte-gleich (Konzept
4.5); beim Release zeigt er dem Funktionsdurchgang je Operation, was sich seit
dem letzten Tag geändert hat (``konzept-funktionsdurchgang-2026-10.md``, §8).

    python tools/registry_dump.py                       # nach stdout
    python tools/registry_dump.py --out abzug.txt       # in eine Datei
    python tools/registry_dump.py --compare abzug.txt   # Exit 1 und die Abschnitte, die abweichen

``--compare`` vergleicht Bytes; Exit 2 heißt nicht verglichen (Datei fehlt oder
ist kein UTF-8), nie „weicht ab“.

Das Parameterschema steht je Feld in einer Zeile ``params.<feld>`` mit jedem
Eintrag von ``ParamSpec`` (Typ, Vorgabe, Grenzen, Einheit, Vorder- oder
Rückseite …) und ``params.<feld>.type`` mit der Annotation als Text. Titel,
Beschreibungen und Vorbehalte erscheinen als Message-ID, nie übersetzt.

**Deterministisch, damit Gleichheit etwas heißt:** Gleitkommazahlen als
``repr``, Mengen sortiert, Aufrufbares als ``__qualname__`` ohne Modul — ein
verschobener Helfer ändert den Abzug nicht, ein umbenannter schon. Ein Wert,
dessen Darstellung eine Speicheradresse trüge, hält den Lauf an, statt einen
Abzug zu schreiben, der in jedem Prozess anders aussieht. Gelesen wird mit
eigenem leerem Profil (§38): Der Abzug hängt nicht an der Maschine.

**Registerreihenfolge heißt Reihenfolge der Registrierung**
(``in_registration_order()`` beider Register). ``all()`` sortiert nach Namen
und sähe nicht, dass ein Schnitt die Importfolge aus
``bootstrap._OPERATION_MODULES`` verschoben hat.
"""

from __future__ import annotations

import argparse
import dataclasses
import difflib
import enum
import functools
import inspect
import os
import sys
import tempfile
from collections.abc import Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from app.core.knowledge.parts.registry import PartSpec
    from app.core.registry.registry import OperationSpec
    from app.core.types import BaseParams

ROOT: Final = Path(__file__).resolve().parent.parent

#: Felder, die der Abzug auslässt: nur die Funktion selbst (Konzept 4.1, W3).
SKIPPED: Final = frozenset({"fn"})


class DumpError(Exception):
    """Der Abzug wäre nicht deterministisch oder käme aus dem falschen Baum; die Meldung hilft."""


def render(value: object) -> str:
    """Ein Wert als Text, der in jedem Prozess und auf jeder Maschine gleich ist."""
    from app.i18n import TranslatableText

    if isinstance(value, TranslatableText):
        parts = [repr(value.msgid)]
        if value.context is not None:
            parts.append(f"context={value.context!r}")
        if value.values:
            parts.append(f"values={render(dict(value.values))}")
        return f"_({', '.join(parts)})"
    if value is None or type(value) in {bool, int, float, str, bytes}:
        return repr(value)
    if isinstance(value, enum.Enum):
        return f"{type(value).__qualname__}.{value.name}"
    for base in (str, float, int):
        # Eine Unterklasse wie ``i18n.Figure`` rechnet wie ihr Grundtyp und
        # verhält sich doch anders — der Typ gehört in den Abzug.
        if isinstance(value, base):
            return f"{type(value).__qualname__}({base.__repr__(value)})"
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        fields = ", ".join(
            f"{field.name}={render(getattr(value, field.name))}"
            for field in dataclasses.fields(value)
        )
        return f"{type(value).__qualname__}({fields})"
    if isinstance(value, type):
        return value.__qualname__
    if isinstance(value, set | frozenset):
        return "{" + ", ".join(sorted(render(item) for item in value)) + "}"
    if isinstance(value, Mapping):
        return (
            "{" + ", ".join(f"{render(key)}: {render(item)}" for key, item in value.items()) + "}"
        )
    if isinstance(value, tuple) and hasattr(value, "_fields"):
        named = ", ".join(
            f"{name}={render(item)}" for name, item in zip(value._fields, value, strict=True)
        )
        return f"{type(value).__qualname__}({named})"
    if isinstance(value, tuple):
        return (
            "(" + ", ".join(render(item) for item in value) + ("," if len(value) == 1 else "") + ")"
        )
    if isinstance(value, list):
        return "[" + ", ".join(render(item) for item in value) + "]"
    if isinstance(value, functools.partial):
        arguments = [
            render(value.func),
            *(render(item) for item in value.args),
            *(f"{key}={render(item)}" for key, item in value.keywords.items()),
        ]
        return f"partial({', '.join(arguments)})"
    qualname = getattr(value, "__qualname__", None)
    if callable(value) and isinstance(qualname, str):
        return qualname
    text = repr(value)
    if " at 0x" in text:
        raise DumpError(
            f"{type(value).__qualname__} hat keine stabile Darstellung ({text}) — "
            "render() braucht einen Zweig für diesen Typ, sonst ist der Abzug je Prozess anders"
        )
    return text


def annotation_text(annotation: object) -> str:
    """Die Annotation eines Parameterfelds als Text; unter ``from __future__ import
    annotations`` steht sie schon so da."""
    return annotation if isinstance(annotation, str) else inspect.formatannotation(annotation)


def schema_lines(params: type[BaseParams]) -> list[str]:
    """Das Parameterschema: der Satz, dann je Feld der Eintrag und sein Typ als Text."""
    annotations = {field.name: field.type for field in params.fields()}
    lines = [f"params = {params.__qualname__}"]
    for entry in params.spec():
        lines.append(f"params.{entry.name} = {render(entry)}")
        if entry.name in annotations:
            lines.append(f"params.{entry.name}.type = {annotation_text(annotations[entry.name])!r}")
    return lines


def spec_lines(spec: OperationSpec | PartSpec) -> list[str]:
    """Jedes Feld eines Registereintrags außer der Funktion, in Feldreihenfolge."""
    lines: list[str] = []
    for field in dataclasses.fields(spec):
        if field.name in SKIPPED:
            continue
        value = getattr(spec, field.name)
        if field.name == "params":
            lines.extend(schema_lines(value))
        else:
            lines.append(f"{field.name} = {render(value)}")
    return lines


def dump(
    operations: Iterable[OperationSpec], parts: Iterable[PartSpec], messages: Iterable[str]
) -> str:
    """Der Abzug aus Einträgen in der gegebenen Reihenfolge und den ``tr()``-Schlüsseln."""
    operations = tuple(operations)
    parts = tuple(parts)
    messages = sorted(messages)
    lines = [
        f"# Registerabzug (W3, tools/registry_dump.py): {len(operations)} Operationen, "
        f"{len(parts)} Bausteine, {len(messages)} Texte"
    ]
    for spec in operations:
        lines.extend(("", f"[op:{spec.name}]", *spec_lines(spec)))
    for part in parts:
        lines.extend(("", f"[part:{part.name}]", *spec_lines(part)))
    lines.extend(("", "[messages]", *(repr(message) for message in messages)))
    return "\n".join(lines) + "\n"


def registered() -> str:
    """Der Abzug des Registers, wie ``bootstrap.load_operations`` es füllt."""
    from app.core.bootstrap import load_operations
    from app.core.knowledge.parts.registry import PARTS
    from app.core.registry.registry import REGISTRY
    from app.i18n.extract import message_ids

    load_operations()
    return dump(REGISTRY.in_registration_order(), PARTS.in_registration_order(), message_ids())


def sections(text: str) -> dict[str, list[str]]:
    """Ein Abzug in seine Abschnitte zerlegt, in ihrer Reihenfolge."""
    found: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in text.splitlines():
        if line.startswith("[") and line.endswith("]"):
            current = found.setdefault(line[1:-1], [])
        elif current is not None and line:
            current.append(line)
    return found


def differences(before: str, after: str) -> list[str]:
    """Was zwei Abzüge unterscheidet, je Abschnitt; leer heißt byte-gleich."""
    if before == after:
        return []
    old, new = sections(before), sections(after)
    lines = [f"fehlt: [{name}]" for name in old if name not in new]
    lines += [f"neu: [{name}]" for name in new if name not in old]
    common_old = [name for name in old if name in new]
    common_new = [name for name in new if name in old]
    if common_old != common_new:
        moved = next(
            (first, second)
            for first, second in zip(common_old, common_new, strict=True)
            if first != second
        )
        lines.append(f"Reihenfolge: [{moved[1]}] steht, wo vorher [{moved[0]}] stand")
    for name in common_old:
        if old[name] != new[name]:
            lines.append(f"geändert: [{name}]")
            lines.extend(
                f"  {row}"
                for row in difflib.unified_diff(old[name], new[name], lineterm="", n=0)
                if not row.startswith(("---", "+++", "@@"))
            )
    return lines or [
        "Die Abzüge unterscheiden sich außerhalb der Abschnitte (Kopfzeile oder Zeilenenden)."
    ]


def _this_tree() -> None:
    """``app`` aus dem Baum dieses Werkzeugs, nicht aus der Editierinstallation des Hauptklons."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import app

    if not Path(app.__file__).resolve().is_relative_to(ROOT):
        raise DumpError(
            f"app kommt aus {Path(app.__file__).parent}, nicht aus {ROOT} — "
            "das Werkzeug aus dem Baum starten, dessen Register es lesen soll"
        )


@contextmanager
def _own_profile() -> Iterator[None]:
    """Leere Nutzerordner für die Dauer des Abzugs (§38), danach wie vorher."""
    from app.core.paths import PROFILE_VARIABLES, isolate_secrets

    # Danach wie vorher, samt Schlüsselbund und Chat-Schlüssel (RC2-10).
    before = dict(os.environ)
    with tempfile.TemporaryDirectory(
        prefix="solidon-registry-dump-", ignore_cleanup_errors=True
    ) as folder:
        try:
            isolate_secrets(os.environ).update(dict.fromkeys(PROFILE_VARIABLES, folder))
            yield
        finally:
            os.environ.clear()
            os.environ.update(before)


def main(argv: Sequence[str] | None = None) -> int:
    """Schreibt den Abzug oder vergleicht ihn mit einem früheren; Exit 1 bei Abweichung."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--out", type=Path, metavar="DATEI", help="in diese Datei schreiben")
    target.add_argument(
        "--compare", type=Path, metavar="DATEI", help="gegen diesen früheren Abzug vergleichen"
    )
    args = parser.parse_args(argv)
    earlier = b""
    if args.compare is not None:
        # Zuerst und als Bytes gelesen: „byte-gleich“ heißt Bytes, und eine Datei,
        # die fehlt oder kein UTF-8 ist, ist nicht verglichen — Exit 2, nie
        # „weicht ab“.
        try:
            earlier = args.compare.read_bytes()
            earlier.decode("utf-8")
        except (OSError, UnicodeDecodeError) as error:
            print(
                f"registry_dump: {args.compare}: {error} — nicht verglichen (Exit 2); einen "
                "Abzug angeben, den `--out` geschrieben hat",
                file=sys.stderr,
            )
            return 2
    try:
        _this_tree()
        with _own_profile():
            text = registered()
    except DumpError as error:
        print(f"registry_dump: {error}", file=sys.stderr)
        return 2
    if args.out is not None:
        try:
            args.out.write_text(text, encoding="utf-8", newline="\n")
        except OSError as error:
            print(
                f"registry_dump: {args.out}: {error} — nicht geschrieben (Exit 2)", file=sys.stderr
            )
            return 2
        print(text.splitlines()[0].removeprefix("# "))
        return 0
    if args.compare is not None:
        same = earlier == text.encode("utf-8")
        found = [] if same else differences(earlier.decode("utf-8"), text)
        for line in found:
            print(line)
        print("W3: byte-gleich" if same else f"W3: weicht ab von {args.compare}")
        return 0 if same else 1
    sys.stdout.buffer.write(text.encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
