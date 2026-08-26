"""Jede Ausnahme trägt mindestens einen Handlungsvorschlag (Bauplan §33.1,
§2.7).

Ein Fehler, der mit „fehlgeschlagen" endet, ist unfertig. Die Prüfung läuft die
ganze Hierarchie ab — eine neue Ausnahmeklasse kann also nicht ohne einen
durchrutschen.
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
import re
from pathlib import Path

import pytest

from app.core import errors
from app.core.errors import (
    AmbiguityError,
    AppError,
    BooleanFailedError,
    GeometryError,
    InternalError,
    UnitUnknownError,
    UserError,
    ValidationError,
)


def _import_every_core_module() -> None:
    """Zieht jedes Modul unter ``app.core`` einmal herein.

    ``AppError.__subclasses__()`` kennt nur die Klassen, deren Modul schon
    importiert ist — und das war beim Sammeln dieser Datei nur ein Teil. Etliche
    Ausnahmen leben in Modulen, die erst der Betrieb lädt (``LicenceKeyError``,
    ``BackendUnavailable`` und die anderen Backend-Fehler): Sie liefen nie durch
    die Prüfung auf einen Handlungsvorschlag, und ob sie *dieser* Lauf zufällig
    doch sah, hing an der Importreihenfolge der übrigen Testdateien — ein
    stiller Erfolg, kein zugesicherter.
    """
    import app.core

    for module in pkgutil.walk_packages(app.core.__path__, "app.core."):
        importlib.import_module(module.name)


def all_error_classes() -> list[type[AppError]]:
    _import_every_core_module()
    found: list[type[AppError]] = []
    seen: set[type[AppError]] = set()
    stack = [AppError]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        found.append(current)
        stack.extend(current.__subclasses__())
    # Erhobene Menge (Ladevorgang): Bleibt ein Modul stumm liegen, schrumpft sie,
    # ohne dass ein Test rot wird — parametrisiert über eine kürzere Liste ist
    # jeder Einzelfall weiter grün. Die Bodenzusicherung fängt genau das. Sie
    # steht bewusst *unter* der wahren Zahl (rund zwei Dutzend), nicht auf ihr:
    # ein unvollständiger Import kollabiert auf die ~15 eager geladenen Klassen,
    # das fängt die 20 — ein legitimes Hinzufügen oder Entfernen einer Klasse
    # (etwa der OpenSCAD-Fehler mit ihrem Backend) bricht sie dagegen nicht. Eine
    # Zahl auf dem Ist-Stand wäre bei jeder Registeränderung rot.
    assert len(found) >= 20, (
        f"zu wenige Fehlerklassen gesammelt ({len(found)}) — Import unvollständig?"
    )
    return found


def core_sources() -> list[Path]:
    return sorted((Path(__file__).resolve().parent.parent / "app" / "core").rglob("*.py"))


@pytest.mark.parametrize("path", core_sources(), ids=lambda entry: entry.name)
def test_no_error_text_carries_a_placeholder_nobody_fills(path: Path) -> None:
    """Ein ``{platzhalter}`` in einem Fehlertext bleibt wörtlich stehen.

    Anderswo ist er richtig: die Oberfläche setzt ihre Texte mit ``.format``
    zusammen, und ``tr("{grams} g").format(...)`` ist der übliche Weg. Einen
    Fehler formatiert dagegen niemand nach — ``show_details`` zeigt
    ``str(error.detail)``, wie es ist, und hängt die ``values`` als eigene
    Zeilen darunter. Wer den Wert in den Satz schreibt, zeigt dem Nutzer
    geschweifte Klammern.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    placeholder = re.compile(r"\{[a-z_]+\}")
    offenders: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg not in ("detail", "title"):
                continue
            for text in ast.walk(keyword.value):
                if (
                    isinstance(text, ast.Constant)
                    and isinstance(text.value, str)
                    and placeholder.search(text.value)
                ):
                    offenders.append(f"{path.name}:{text.lineno} {text.value[:60]}")

    assert not offenders, "Fehlertexte mit unersetztem Platzhalter:\n" + "\n".join(offenders)


@pytest.mark.parametrize("error_class", all_error_classes(), ids=lambda cls: cls.__name__)
def test_every_error_can_be_raised_bare(error_class: type[AppError]) -> None:
    error = error_class()
    assert str(error.title), "an error needs a title saying what did not work"
    assert error.suggestions, "an error without a suggestion is unfinished"


@pytest.mark.parametrize("error_class", all_error_classes(), ids=lambda cls: cls.__name__)
def test_every_error_serialises(error_class: type[AppError]) -> None:
    data = error_class().as_dict()
    assert data["type"] == error_class.__name__
    assert data["suggestions"]


def test_hierarchy_matches_the_plan() -> None:
    assert issubclass(UserError, AppError)
    assert issubclass(ValidationError, UserError)
    assert issubclass(AmbiguityError, UserError)
    assert issubclass(UnitUnknownError, UserError)
    assert issubclass(GeometryError, AppError)
    assert issubclass(errors.NotManifoldError, GeometryError)
    assert issubclass(BooleanFailedError, GeometryError)
    assert issubclass(errors.OutOfBuildVolume, GeometryError)
    assert issubclass(errors.ExternalToolError, AppError)
    assert issubclass(InternalError, AppError)


def test_a_programming_error_is_not_a_user_error() -> None:
    assert not issubclass(InternalError, UserError)
    assert not issubclass(ValidationError, InternalError)


def test_ambiguity_offers_the_candidates() -> None:
    error = AmbiguityError(candidates=("hole_3", "hole_4"))
    ids = [action.id for action in error.suggestions]
    assert "choose:hole_3" in ids
    assert "choose:hole_4" in ids


def test_unit_question_offers_the_units() -> None:
    error = UnitUnknownError()
    ids = [action.id for action in error.suggestions]
    assert ids[:3] == ["unit:mm", "unit:cm", "unit:in"]


def test_boolean_failure_keeps_stages_and_seed() -> None:
    error = BooleanFailedError(attempted=("direct", "welded"), seed=20260727)
    assert error.attempted == ("direct", "welded")
    assert error.as_dict()["values"]["seed"] == 20260727


def test_the_boolean_failure_says_which_stages_really_ran() -> None:
    """„Auf allen Stufen" war beim Arbeiten im Fenster nie wahr (§17.2, §31).

    Dort läuft die kurze Kette — direkt und verschweißt —, die vollen vier
    Stufen laufen beim Export. Der Titel behauptete trotzdem, es sei alles
    versucht, und daneben stand als einziger Rat *Voxelstufe erzwingen*: also
    genau die Stufe, die noch offen war. Zwei Sätze, die sich widersprechen.

    Jetzt sagt der Titel, was gilt — und wo die Voxelstufe wirklich dran war,
    fällt der Rat weg, statt eine Wiederholung anzubieten.
    """
    entwurf = BooleanFailedError(attempted=("direct", "welded"))
    assert "Entwurf" in str(entwurf.title)
    assert errors.USE_VOXEL_STAGE in entwurf.suggestions, "hier ist die Stufe noch offen"

    voll = BooleanFailedError(attempted=("direct", "welded", "jittered", "voxel"))
    assert "allen Stufen" in str(voll.title)
    assert errors.USE_VOXEL_STAGE not in voll.suggestions, (
        "die Voxelstufe war dran — sie zu erzwingen wäre eine Wiederholung"
    )
    assert voll.suggestions, "without a suggestion the error ends in a dead end"


def test_cancelling_is_not_an_error() -> None:
    assert not issubclass(errors.OperationCancelled, AppError)


def test_the_title_follows_the_constraint_not_the_class() -> None:
    """„Ein Wert liegt außerhalb des zulässigen Bereichs." stand über allem.

    Auch über „Diese Datei ist keine STEP-Datei." und über einem fehlenden
    Parameternamen hinter dem @. Die Oberfläche zeichnet den Titel groß und das
    Detail klein: Wer hinsieht, liest zuerst einen Satz, der nicht stimmt, und
    sucht dann bei den Zahlen.

    Von rund 170 Stellen, die diese Ausnahme werfen, betreffen acht eine
    Zahlenspanne. Drei eigene Klassen sind aus genau diesem Missverhältnis
    entstanden; hier steht die Ursache statt des nächsten Einzelfalls.
    """
    from app.core.errors import UserError, ValidationError

    for constraint in ("minimum", "maximum", "range", "positive"):
        error = ValidationError(field="wall", constraint=constraint, detail="Zu dünn.")
        assert "Bereichs" in str(error.title), f"{constraint} ist eine Spanne"

    # ``positive`` steht hier seit dem 24.08.2026 und stand vorher in keiner der
    # beiden Listen -- eine Lücke, keine Entscheidung. Die nach unten offene
    # Spanne ist eine Spanne, und mit sechzehn Aufrufern über
    # ``require_positive`` ist sie die häufigste von allen. Gegenprobe über den
    # echten Weg, nicht über den Konstruktor: Sonst prüft der Test die Liste,
    # die er selbst aufzählt.
    with pytest.raises(ValidationError) as gemessen:
        errors.require_positive("wall", 0.0)
    assert "Bereichs" in str(gemessen.value.title), (
        "require_positive muss den Bereichstitel tragen, nicht den allgemeinen"
    )
    assert gemessen.value.constraint == "positive"

    for constraint in ("empty", "type", "unknown_object", "required", ""):
        error = ValidationError(field="source", constraint=constraint, detail="Keine STEP-Datei.")
        assert str(error.title) == str(UserError.default_title), (
            f"{constraint!r} ist keine Spanne — der Titel darf keine behaupten"
        )

    # Ein selbst gesetzter Titel bleibt unberührt: acht Stellen nennen ihren
    # eigenen, und der ist immer genauer als beide Vorgaben.
    own = ValidationError(title="Dieses Profil gibt es nicht.", detail="…")
    assert str(own.title) == "Dieses Profil gibt es nicht."


#: Beschränkungen, die bewusst **keine** Zahlenspanne sind.
#:
#: Das Gegenstück zu ``errors._RANGE_CONSTRAINTS``, und beide zusammen müssen
#: alles abdecken, was ``app/core`` wirklich setzt — dafür sorgt der Test
#: darunter. Getrennt geführt, weil die Frage nicht maschinell zu beantworten
#: ist: „zu wenige Punkte" und „zwischen drei und vierundsechzig Ecken" sehen im
#: Quelltext gleich aus, und nur beim zweiten steht eine Zahl in einem Feld, die
#: der Kunde ändern kann.
_NOT_A_RANGE = frozenset(
    {
        "absolute_path", "already_solid", "ambiguous_reference", "broken_scheme", "checksum",
        "choices",
        # „#RRGGBB" ist ein Format und keine Spanne: Eine Filamentfarbe kann
        # nicht „zu groß" sein, sie ist lesbar oder nicht.
        "colour",
        "consumes", "count_in_use", "cycle", "damaged", "damaged_sketch", "degenerate_normal",
        "empty", "exists", "file_too_large", "format", "grammar", "history_moved", "host",
        "inverted",
        "known_pattern",
        "known_structure", "missing_file", "missing_gathered", "missing_link", "missing_payload",
        "needs_diameter", "no_area", "no_base_dir", "no_cavity", "no_direction", "no_face",
        "no_geometry", "no_migration", "no_normal", "no_outline", "no_profile", "no_section",
        "no_shapes", "no_sources", "no_split", "not_a_face", "not_a_number", "not_a_project",
        "not_a_twin", "not_outline", "not_step", "not_upright", "one_body", "point_count",
        "required",
        "scheme", "sweep_needs_xy", "target_behind", "target_count", "target_parallel", "toml",
        "too_many_triangles", "too_new", "type", "undo_with_changes", "unknown",
        "unknown_feature", "unknown_format", "unknown_object", "unknown_parameter",
        "unknown_placeholder", "unknown_region", "unknown_shape", "unknown_source",
        "unknown_target",
        "unknown_transaction", "unreadable", "unsupported_compression", "unsupported_format",
        "unwritable",
        "value_not_allowed", "web_page",
    }
)  # fmt: skip


def constraints_in_core() -> tuple[dict[str, str], list[str]]:
    """Jede ``constraint``-Angabe aus ``app/core`` — feste Werte und dynamische.

    Zurück kommt einmal ``{wert: erste Fundstelle}`` und einmal die Liste der
    Stellen, an denen kein fester Wert steht.
    """
    fest: dict[str, str] = {}
    beweglich: list[str] = []
    for path in core_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if keyword.arg != "constraint":
                    continue
                wert = keyword.value
                if isinstance(wert, ast.Constant) and isinstance(wert.value, str):
                    if wert.value:
                        fest.setdefault(wert.value, f"{path.name}:{node.lineno}")
                elif path.name != "errors.py":
                    # In ``errors.py`` reicht der Konstruktor sein eigenes
                    # Argument weiter — das ist die Definition, kein Aufruf.
                    beweglich.append(f"{path.name}:{node.lineno}")
    return fest, beweglich


def test_every_constraint_is_sorted_into_range_or_not() -> None:
    """Keine Beschränkung darf unbemerkt an beiden Listen vorbeilaufen.

    **Der Vorgänger konnte diese Lücke nicht finden.** Er zählte vier Spannen
    und fünf Gegenbeispiele auf, beide von Hand — und prüfte nie, was der Code
    tatsächlich setzt. ``corner_count`` („zwischen drei und vierundsechzig
    Ecken"), ``negative``, ``too_short`` und ``minimum_wall`` standen in keiner
    der beiden Listen und trugen deshalb den vagen Titel; für den Test gab es
    sie nicht. Ein Test, der nur seine eigene Aufzählung bestätigt, misst sich
    selbst.

    Hier kommt der **Ist-Zustand aus dem Quelltext** und der **Soll-Zustand aus
    den beiden kuratierten Listen**. Wer eine neue Beschränkung einführt, ordnet
    sie ein — oder der Lauf ist rot und sagt, welche fehlt.
    """
    fest, beweglich = constraints_in_core()

    assert not beweglich, (
        "Eine Beschränkung aus einer Variablen lässt sich nicht einordnen. "
        f"Stellen: {beweglich}. In ``solver.py`` stand dort einmal die Elementart "
        "(„circle“), und der Titel richtete sich danach."
    )

    unsortiert = {
        wert: ort
        for wert, ort in fest.items()
        if wert not in errors._RANGE_CONSTRAINTS and wert not in _NOT_A_RANGE
    }
    assert not unsortiert, (
        "Diese Beschränkungen kennt keine der beiden Listen — trägt sie in "
        "``errors._RANGE_CONSTRAINTS`` ein, wenn eine Zahl in einem Feld eine "
        f"Grenze verletzt, sonst in ``_NOT_A_RANGE``: {unsortiert}"
    )

    doppelt = errors._RANGE_CONSTRAINTS & _NOT_A_RANGE
    assert not doppelt, f"in beiden Listen, also ohne Antwort: {sorted(doppelt)}"

    verwaist = (errors._RANGE_CONSTRAINTS | _NOT_A_RANGE) - set(fest)
    assert not verwaist, (
        f"Diese Beschränkungen setzt der Kern nicht mehr: {sorted(verwaist)}. "
        "Eine Karteileiche in der Liste deckt beim nächsten Mal einen echten Fehler."
    )


def test_a_range_constraint_really_reads_like_one() -> None:
    """Stichprobe über den echten Weg, nicht über den Konstruktor.

    Die vier aus dem Befund vom 24.08.2026: Jede nennt in ihrem Detailtext eine
    Grenze, und über jeder stand „Die Eingabe war so nicht verwendbar."
    """
    from app.core.sketch.shapes import polygon

    with pytest.raises(ValidationError) as ecke:
        polygon(corners=2, diameter=10.0)
    assert ecke.value.constraint == "corner_count"
    assert "Bereichs" in str(ecke.value.title), (
        "„zwischen drei und vierundsechzig Ecken“ nennt beide Grenzen — "
        "der Titel darf nicht vager sein als das Detail"
    )


def test_a_suggestion_has_to_fit_the_error() -> None:
    """„Reparieren und erneut versuchen" stand an Fehlern, wo es nichts zu
    reparieren gibt.

    ``GeometryError`` führt als Vorgabe „Reparieren und erneut versuchen" und
    „Stellen zeigen". Beide haben einen Handler, erscheinen also als Knopf — und
    an zwei Stellen taten beide nichts: Der Verrundungsradius steckt an einem
    exakten B-Rep-Körper, an dem es nichts zu reparieren gibt, und „Diese
    Operation arbeitet nur auf Netzen" wird durch Netzreparatur nicht wahr.
    Regel 17 war damit optisch erfüllt und in der Sache verletzt.

    Geprüft wird die Aussage und nicht die Stelle: Wo im Text vom Radius die
    Rede ist, gehört „Eingabe korrigieren" dazu und nicht die Reparatur.
    """
    import pathlib

    from app.core.brep import edit as brep_edit
    from app.core.errors import CANCEL, CORRECT_INPUT, REPAIR_AND_RETRY
    from app.core.geom import mesh as mesh_module

    for module, needle in ((brep_edit, "Radius"), (mesh_module, "nur auf Netzen")):
        source = pathlib.Path(module.__file__).read_text(encoding="utf-8")
        assert needle in source, f"{module.__name__}: der Fehlertext ist fort"

    # Der Radiusfehler, geworfen wie im Betrieb.
    problem = GeometryError(
        detail="Der Radius ist für diese Kanten zu groß.",
        suggestions=(CORRECT_INPUT, CANCEL),
        values={"size_mm": 4.0, "edges": 12},
    )
    ids = {action.id for action in problem.suggestions}
    assert "correct_input" in ids, "die Antwort auf einen zu großen Radius ist ein kleinerer"
    assert REPAIR_AND_RETRY.id not in ids, "an einem exakten Körper gibt es nichts zu reparieren"
    assert "show_locations" not in ids, "und dieser Fehler nennt keine Stellen"


def test_missing_software_offers_the_install_list_and_not_a_bug_report() -> None:
    """Eine fehlende Zusatzkomponente ist kein Fehler, den man melden könnte.

    ``BRepUnavailable`` nannte keine Vorschläge. ``AppError`` fällt dann auf
    „Abbrechen" zurück, und einem Dialog, dem sonst nichts bleibt, legt
    ``dialogs.offered_actions`` den Fehlerbericht bei — wer also eine
    Verrundung ohne OpenCASCADE versuchte, wurde gebeten, einen Fehler zu
    melden. Eine fehlende Zusatzkomponente schlägt stattdessen ``install`` vor.

    Geprüft an mehreren, damit es nicht an einer Klasse hängt: OpenCASCADE, ein
    Slicer, ComfyUI. Die Kennung am Fehler sagt „installieren", nicht „melden" —
    ein Vorschlag ohne Gegenstück ist keiner.
    """
    from app.core.brep.kernel import BRepUnavailable
    from app.core.errors import INSTALL_MISSING, ExternalToolError

    for problem in (
        BRepUnavailable(),
        ExternalToolError(tool="PrusaSlicer"),
        ExternalToolError(tool="ComfyUI"),
    ):
        ids = {action.id for action in problem.suggestions}
        assert INSTALL_MISSING.id in ids, (
            f"{type(problem).__name__}: der Weg zur Installation fehlt"
        )
        assert "report_error" not in ids, "fehlende Software ist kein Fehlerbericht"
