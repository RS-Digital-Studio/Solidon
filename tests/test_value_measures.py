"""Eine Länge unter einer Absage steht mit Einheit da (FD-188).

Absagen und Befunde legen ihre Zahlen in ``values`` ab, und die Anzeige liest
die Einheit aus der Endung des Schlüssels (``_mm``, ``_mm2``, ``_deg``). Gut
zwanzig Absagen trugen Längen unter Schlüsseln ohne Endung — ``reachable``,
``pitch``, ``diameter``, ``minimum`` —, und unter der Absage stand
„Erreichbar: 0,58“: ohne Einheit, in Zoll falsch. Umbenennen geht nicht, Agent
und Handler lesen die Schlüssel (``main_window`` liest ``reachable``,
``previous`` und ``diameter``, ``bore_pin`` liest ``diameter`` und ``pitch``).

Festgelegt ist es deshalb an einer Stelle: ``labels._BARE_MEASURES`` nennt die
Schlüssel ohne Endung, die überall ein Maß tragen, ``labels._MEASURE_TEXTS``
die, die nur als Text „12.00 mm“ eines tragen, und ein Grenzwert
(``minimum``, ``maximum``, ``value``) bringt seine Einheit in
``values["unit"]`` mit. Der Wächter unten liest jeden ``values``-Eintrag aus
``app/core`` und wird rot, wenn ein Maß ohne eine dieser Kennzeichnungen
dasteht.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QLocale

from app.core.errors import AppError
from app.ui import labels
from app.ui.labels import value_line

CORE = Path(__file__).resolve().parents[1] / "app" / "core"

#: Endungen, die die Anzeige als Einheit liest (``labels._VALUE_UNITS``).
SUFFIXES = ("_mm3", "_mm2", "_cm3", "_percent", "_deg", "_mm")


@pytest.fixture
def german() -> Iterator[None]:
    """Komma als Dezimalzeichen, Millimeter als Anzeigeeinheit — danach wie vorher."""
    before = QLocale()
    QLocale.setDefault(QLocale("de"))
    labels.set_display_unit("mm")
    try:
        yield
    finally:
        labels.set_display_unit("mm")
        QLocale.setDefault(before)


def _spoken(error: AppError) -> list[str]:
    from app.ui.dialogs import spoken_values

    return spoken_values(error)


def _remesh_refusal() -> AppError:
    """Die Vorabzählung von *Kanten verfeinern* (``mesh_ops._too_fine``) am Würfel.

    Die Zählung ist so gewählt, dass 0,575 mm noch unter die Decke passt; der
    Vorschlag rundet auf Hundertstel auf: 0,58 mm.
    """
    import trimesh

    from app.core.geom import mesh_ops
    from app.core.geom.mesh import MeshData

    cube = MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, 10.0)))

    def count(edge: float) -> int:
        return int(mesh_ops.MAX_REMESH_TRIANGLES * (0.575 / edge) ** 2)

    return mesh_ops._too_fine(cube, 0.5, count(0.5), count, reserve=1.0)


def test_the_reachable_edge_says_its_unit(german: None) -> None:
    """Der Fund im Operationsdialog: „Erreichbar: 0,58“ — jetzt mit Einheit, auch in Zoll."""
    error = _remesh_refusal()
    assert error.values["reachable"] == pytest.approx(0.58), "der Wert bleibt eine Zahl in mm"
    assert "Erreichbar: 0,58 mm" in _spoken(error)
    labels.set_display_unit("in")
    assert "Erreichbar: 0,0228 in" in _spoken(error)


def test_the_reachable_grid_says_its_unit(german: None) -> None:
    """Der Zwilling beim Verschmelzen: die erreichbare Rasterweite."""
    from app.core.geom import blend

    error = blend._too_fine(blend.MAX_SAMPLES * 8, 0.5)
    assert isinstance(error.values["reachable"], float)
    assert "Erreichbar: 1,00 mm" in _spoken(error)
    labels.set_display_unit("in")
    assert "Erreichbar: 0,0394 in" in _spoken(error)


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        # Feiner als die feinste Steigung: Untergrenze und Steigung.
        ((10.0, 0.05, 0.2), ["Mindestwert: 0,25 mm", "Steigung: 0,05 mm"]),
        # Gröber als die gröbste: Obergrenze und Steigung.
        ((60.0, 30.0, 0.2), ["Höchstwert: 20,00 mm", "Steigung: 30,00 mm"]),
        # Ohne tragenden Kern: Obergrenze, Steigung und Spiel.
        ((2.0, 1.6, 0.2), ["Steigung: 1,60 mm", "Spiel: 0,20 mm"]),
    ],
)
def test_every_thread_refusal_says_its_unit(
    german: None, arguments: tuple[float, float, float], expected: list[str]
) -> None:
    """``thread_problem`` — die eine Regel für Bau, Erklärung und Gegenstück."""
    from app.core.knowledge.parts.fasteners import thread_problem

    error = thread_problem(*arguments)
    assert error is not None
    lines = _spoken(error)
    for line in expected:
        assert line in lines, lines
    numbers = [line for line in lines if re.search(r"\d", line)]
    assert numbers
    assert all(line.endswith(" mm") for line in numbers), lines


def test_a_thread_too_fine_for_its_size_says_every_unit(german: None) -> None:
    from app.core.knowledge.parts.fasteners import thread_problem

    error = thread_problem(200.0, 0.25, 0.2, length=2000.0)
    assert error is not None
    labels.set_display_unit("in")
    lines = _spoken(error)
    measured = [
        line for line in lines if line.split(":")[0] in {"Steigung", "Länge", "Durchmesser"}
    ]
    assert len(measured) == 3, lines
    assert all(line.endswith(" in") for line in measured), lines


@pytest.mark.parametrize("language", ["de", "en", "es", "fr", "it", "pt"])
def test_the_unit_stands_in_every_language(german: None, language: str) -> None:
    """Die Einheit hängt an der Zahl, nicht am Katalog: in jeder Sprache dieselbe."""
    from app.i18n import set_language
    from app.i18n.catalog import install_language

    install_language(language)
    set_language(language)
    try:
        line = value_line("reachable", 0.58)
        assert line.endswith("0,58 mm"), line
        assert not line.startswith("reachable"), "die Beschriftung ist übersetzt"
        labels.set_display_unit("in")
        assert value_line("pitch", 1.27).endswith("0,0500 in")
    finally:
        install_language("de")
        set_language("de")


def test_every_bare_measure_key_reads_with_its_unit(german: None) -> None:
    from app.ui.labels import _BARE_MEASURES

    shown = {"_mm": " mm", "_mm2": " mm²", "_deg": "°"}
    for key, suffix in _BARE_MEASURES.items():
        assert value_line(key, 2.5).endswith(shown[suffix]), key
        assert value_line(key, "2.5").endswith(shown[suffix]), f"{key} als Zahlentext"


def test_a_list_of_lengths_reads_as_lengths(german: None) -> None:
    """Eine Ecke aus drei Koordinaten (``faces.py``: „Ecke: [1.0, 2.0, 3.0]“)."""
    assert value_line("corner", [1.0, 2.5, -3.0]) == "Ecke: 1,00 mm, 2,50 mm, -3,00 mm"


def test_a_measure_written_as_text_follows_the_unit(german: None) -> None:
    """Fertiger Text „12.00 mm“ aus ``format_length`` folgte dem Wechsel auf Zoll nicht."""
    assert value_line("diameter", "12.70 mm") == "Durchmesser: 12,70 mm"
    labels.set_display_unit("in")
    assert value_line("diameter", "12.70 mm") == "Durchmesser: 0,5000 in"
    assert value_line("shortest", "25.40 mm") == "Mindestlänge: 1,0000 in"
    assert value_line("actual", "2.54 mm") == "Tatsächlich: 0,1000 in"
    assert value_line("gap", "0.20 mm").endswith(" in")


def test_what_is_no_measure_stays_as_it_is(german: None) -> None:
    """Unter einem Maßschlüssel kann auch Text stehen — der bekommt keine Einheit."""
    # Die Mindestversion von ComfyUI steht unter ``needed``.
    assert value_line("needed", "0.35.0") == "Nötig: 0.35.0"
    # ``actual`` und ``expected`` sind als Zahl eine Anzahl, keine Länge.
    assert value_line("expected", 3) == "Erwartet: 3"
    # Ein Name, der wie ein Maß aussieht, bleibt ein Name.
    assert value_line("object", "5 mm") == "Objekt: 5 mm"


def test_a_slicer_setting_keeps_the_unit_of_its_field(german: None) -> None:
    """``gap`` und ``layer_height`` aus der Druckprüfung stehen wie im Druckdialog."""
    from app.core.knowledge.print_fields import shown_value

    labels.set_display_unit("in")
    gap = value_line("gap", 0.2)
    assert gap == f"Spalt: {shown_value('support.z_gap', 0.2, localise=labels.localised)}"
    assert gap.endswith(" mm")
    assert value_line("layer_height", 0.3).endswith(" mm")


# --- Der Wächter -------------------------------------------------------------

#: Wortteile eines Bezeichners, die ein Maß verraten: Steht einer davon im
#: Ausdruck eines Werts, ist der Wert ein Maß und braucht seine Kennzeichnung.
MEASURE_WORDS = frozenset(
    {
        "angle",
        "area",
        "clearance",
        "deepest",
        "depth",
        "diameter",
        "distance",
        "drop",
        "edge",
        "excess",
        "footprint",
        "gap",
        "grid",
        "grip",
        "hanging",
        "height",
        "length",
        "longest",
        "margin",
        "nominal",
        "offset",
        "overhang",
        "pitch",
        "play",
        "radius",
        "reach",
        "reachable",
        "ring",
        "room",
        "seat",
        "shortest",
        "thickness",
        "tube",
        "wall",
        "width",
    }
)

#: Der Schlüssel, unter dem ein Grenzwert seine Einheit mitbringt.
UNIT_KEY = re.compile(r"[\"']unit[\"']")

#: Was ein Maß als Text schreibt.
MEASURE_CALLS = frozenset(
    {"format_length", "format_length_bound", "format_area", "written_measure"}
)

#: Was sicher kein Maß ist, auch wenn ein Wort darin danach klingt.
NO_MEASURE_CALLS = frozenset({"len", "str", "repr", "sorted", "list", "_direction_name"})

#: Einträge, die nach Maß aussehen und keines sind — je mit Grund.
NOT_A_MEASURE: dict[tuple[str, str], str] = {
    ("loader.py", "open_edges"): "eine Anzahl offener Kanten",
    ("step_ops.py", "open_edges"): "eine Anzahl offener Kanten",
    ("counterpart.py", "tpi"): "Gänge je Zoll, eine Anzahl",
    ("profile_clamp_ops.py", "size"): "die Schraubengröße als Name (M5)",
    ("advise.py", "possible"): "eine Düsentemperatur",
    ("advise.py", "wanted"): "eine Düsentemperatur",
    ("prepare_ops.py", "bore"): "die Kennung eines Merkmals",
    ("prepare_ops.py", "widening"): "die Kennung eines Merkmals",
    ("lid_hinge.py", "bore"): "der Parameter eines Merkmals, kein Befundwert",
    ("placement.py", "diameter"): "Parameter eines Schritts, kein Befundwert",
    ("seals.py", "area"): "Kenngrößen eines Merkmals, kein Befundwert",
    ("seals.py", "centre"): "Kenngrößen eines Merkmals, kein Befundwert",
    ("prepare_ops.py", "centre"): "Kenngrößen eines Merkmals, kein Befundwert",
    ("edit.py", "middle"): "interne Absage, die Koordinate ist eine Diagnose",
    ("support.py", "limit"): "die Länge einer Nachricht in Zeichen",
}


def _measure_in(value: ast.expr) -> str:
    """Warum ``value`` ein Maß ist — leer, wenn nichts darauf deutet."""
    if isinstance(value, ast.Call):
        callee = getattr(value.func, "id", "") or getattr(value.func, "attr", "")
        if callee in NO_MEASURE_CALLS:
            return ""
    if isinstance(value, ast.Attribute) and value.attr in {"id", "name", "title"}:
        return ""
    for inner in ast.walk(value):
        if isinstance(inner, ast.Call):
            callee = getattr(inner.func, "id", "") or getattr(inner.func, "attr", "")
            if callee in MEASURE_CALLS:
                return callee
        words: list[str] = []
        if isinstance(inner, ast.Name):
            words = inner.id.lower().split("_")
        elif isinstance(inner, ast.Attribute):
            words = inner.attr.lower().split("_")
        elif isinstance(inner, ast.Subscript) and isinstance(inner.slice, ast.Constant):
            words = str(inner.slice.value).lower().split("_")
        found = MEASURE_WORDS.intersection(words)
        if found:
            return min(found)
    return ""


def _value_entries(source: str) -> Iterator[tuple[str, int, ast.expr, bool]]:
    """Jeder ``values``-Eintrag: Schlüssel, Zeile, Ausdruck, ob ``"unit"`` dabei ist.

    Dieselben Formen wie ``test_value_labels.keys_in_source``: ``values=`` in
    einem Aufruf, eine Zuweisung an ``values`` und ``values["…"] = …``. Ob die
    Einheit dabei ist, entscheidet die Funktion drumherum.
    """
    tree = ast.parse(source)
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    def unit_near(node: ast.AST) -> bool:
        while node in parents:
            node = parents[node]
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                break
        return UNIT_KEY.search(ast.get_source_segment(source, node) or "") is not None

    def entries(node: ast.Dict) -> Iterator[tuple[str, int, ast.expr, bool]]:
        for inner in ast.walk(node):
            if isinstance(inner, ast.Dict):
                for key, value in zip(inner.keys, inner.values, strict=True):
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        yield key.value, key.lineno, value, unit_near(inner)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg == "values" and isinstance(keyword.value, ast.Dict):
                    yield from entries(keyword.value)
        elif isinstance(node, ast.AnnAssign):
            if (
                isinstance(node.target, ast.Name)
                and node.target.id == "values"
                and isinstance(node.value, ast.Dict)
            ):
                yield from entries(node.value)
        elif isinstance(node, ast.Assign):
            names = [entry.id for entry in node.targets if isinstance(entry, ast.Name)]
            if "values" in names and isinstance(node.value, ast.Dict):
                yield from entries(node.value)
            for target in node.targets:
                if (
                    isinstance(target, ast.Subscript)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "values"
                    and isinstance(target.slice, ast.Constant)
                    and isinstance(target.slice.value, str)
                ):
                    yield target.slice.value, node.lineno, node.value, unit_near(node)


def _unmarked(source: str, file: str) -> list[str]:
    """Die Einträge aus ``source``, die ein Maß tragen und es nicht sagen."""
    from app.ui.labels import _BARE_MEASURES, _MEASURE_TEXTS, _SETTING_PATHS, UNIT_VALUES

    marked = set(_BARE_MEASURES) | set(_MEASURE_TEXTS) | set(_SETTING_PATHS)
    found = []
    for key, line, value, with_unit in _value_entries(source):
        if key.endswith(SUFFIXES) or key in marked or (file, key) in NOT_A_MEASURE:
            continue
        if key in UNIT_VALUES and with_unit:
            continue
        why = _measure_in(value)
        if why:
            found.append(f"{file}:{line} {key} ({why})")
    return found


def test_no_measure_reaches_a_value_without_its_unit() -> None:
    """Jede Absage und jeder Befund mit einem Maß kennzeichnet es.

    Rot heißt: Ein ``values``-Eintrag trägt etwas, das nach Länge, Fläche oder
    Winkel aussieht, und die Anzeige erführe es nicht. Wege, in dieser
    Reihenfolge: ein Schlüssel mit Endung (``_mm``, ``_mm2``, ``_deg``) ohne
    Leser; bei einem Grenzwert ``"unit": "mm"`` daneben; ein Schlüssel, den
    Agent oder Handler lesen und der überall ein Maß ist, in
    ``labels._BARE_MEASURES``. Ist es keines, hier in ``NOT_A_MEASURE`` mit
    Grund.
    """
    found = []
    for path in sorted(CORE.rglob("*.py")):
        found.extend(_unmarked(path.read_text(encoding="utf-8"), path.name))
    assert not found, (
        "Maß ohne Einheit in values — Endung _mm/_mm2/_deg, bei einer Grenze "
        '"unit": "mm", ein gelesener Schlüssel in labels._BARE_MEASURES, sonst '
        "NOT_A_MEASURE mit Grund:\n" + "\n".join(found)
    )


def test_the_guard_sees_a_bare_length() -> None:
    """Gegenprobe: Der Wächter schlägt an, wo er soll, und schweigt, wo es stimmt."""
    bare = (
        "def refuse(params):\n"
        "    raise ValidationError('x', 'y', values={'deepest': params.wall_thickness})\n"
    )
    assert _unmarked(bare, "neu.py") == ["neu.py:2 deepest (thickness)"]
    marked = "def refuse(params):\n    values = {'deepest_mm': params.wall_thickness}\n"
    assert not _unmarked(marked, "neu.py")
    bound = (
        "def refuse(width):\n"
        "    raise ValidationError('x', 'y', values={'minimum': width, 'unit': 'mm'})\n"
    )
    assert not _unmarked(bound, "neu.py")
    assert _unmarked(bound.replace(", 'unit': 'mm'", ""), "neu.py") == ["neu.py:2 minimum (width)"]
    text = "def say(room):\n    values['least'] = format_length(room)\n"
    assert not _unmarked(text, "neu.py"), "least ist ein Maßschlüssel"
    assert _unmarked(text.replace("least", "spare"), "neu.py") == ["neu.py:2 spare (format_length)"]


def test_a_bare_measure_key_never_carries_a_count_or_an_identifier() -> None:
    """Die Tabelle gilt je Schlüssel überall — also darf er nirgends etwas anderes sein."""
    from app.ui.labels import _BARE_MEASURES

    wrong = []
    for path in sorted(CORE.rglob("*.py")):
        for key, line, value, _unit in _value_entries(path.read_text(encoding="utf-8")):
            if key not in _BARE_MEASURES or (path.name, key) in NOT_A_MEASURE:
                continue
            callee = ""
            if isinstance(value, ast.Call):
                callee = getattr(value.func, "id", "") or getattr(value.func, "attr", "")
            identifier = isinstance(value, ast.Attribute) and value.attr in {"id", "name"}
            if callee in {"len", "int"} or identifier:
                wrong.append(f"{path.name}:{line} {key}")
    assert not wrong, wrong


#: Stellen, deren Maß der Wächter am Ausdruck nicht erkennt (``value``,
#: ``limit``, ``position``, ``size`` tragen anderswo eine Anzahl oder einen
#: Namen): Datei unter ``app/core``, Funktion, Schlüssel. Ein Schlüssel mit Endung muss dort
#: stehen, ein Grenzwert mit ``"unit"`` daneben.
PINNED: tuple[tuple[str, str, str], ...] = (
    ("scene/variants.py", "build", "value"),
    ("scene/variants.py", "_place", "value"),
    ("scene/parameter_usage.py", "_beyond", "minimum"),
    ("scene/parameter_usage.py", "_beyond", "maximum"),
    ("export/writer.py", "_lowered_foot_findings", "value"),
    ("geom/edges.py", "_check_corner_region", "size_mm"),
    ("geom/autosplit.py", "split_to_fit", "position_mm"),
    ("sketch/edit.py", "fillet", "most_mm"),
    ("sketch/edit.py", "chamfer", "most_mm"),
)


@pytest.mark.parametrize(("file", "function", "key"), PINNED)
def test_a_measure_the_guard_cannot_see_keeps_its_unit(file: str, function: str, key: str) -> None:
    path = CORE / file
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    (node,) = [
        entry
        for entry in ast.walk(tree)
        if isinstance(entry, ast.FunctionDef | ast.AsyncFunctionDef) and entry.name == function
    ]
    inside = ast.get_source_segment(source, node) or ""
    found = [(name, with_unit) for name, _line, _value, with_unit in _value_entries(inside)]
    assert found, f"{file}:{function} legt keine Werte mehr ab"
    assert key in [name for name, _unit in found], found
    if not key.endswith(SUFFIXES):
        assert all(with_unit for name, with_unit in found if name == key), found
