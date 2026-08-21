"""Jede Ausnahme trägt mindestens einen Handlungsvorschlag (Bauplan §33.1,
§2.7).

Ein Fehler, der mit „fehlgeschlagen" endet, ist unfertig. Die Prüfung läuft die
ganze Hierarchie ab — eine neue Ausnahmeklasse kann also nicht ohne einen
durchrutschen.
"""

from __future__ import annotations

import ast
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


def all_error_classes() -> list[type[AppError]]:
    found: list[type[AppError]] = []
    stack = [AppError]
    while stack:
        current = stack.pop()
        found.append(current)
        stack.extend(current.__subclasses__())
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

    for constraint in ("minimum", "maximum", "range"):
        error = ValidationError(field="wall", constraint=constraint, detail="Zu dünn.")
        assert "Bereichs" in str(error.title), f"{constraint} ist eine Spanne"

    for constraint in ("empty", "type", "unknown_object", "required", ""):
        error = ValidationError(field="source", constraint=constraint, detail="Keine STEP-Datei.")
        assert str(error.title) == str(UserError.default_title), (
            f"{constraint!r} ist keine Spanne — der Titel darf keine behaupten"
        )

    # Ein selbst gesetzter Titel bleibt unberührt: acht Stellen nennen ihren
    # eigenen, und der ist immer genauer als beide Vorgaben.
    own = ValidationError(title="Dieses Profil gibt es nicht.", detail="…")
    assert str(own.title) == "Dieses Profil gibt es nicht."


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
    melden. ``ScadUnavailable`` schlug ``install`` vor, und weil das Fenster
    dafür keinen Handler führte, wurde daraus ein grauer Satz statt eines
    Knopfs.

    Geprüft wird beides an derselben Stelle: die Kennung am Fehler und der
    Handler im Fenster. Ein Vorschlag ohne Gegenstück ist kein Vorschlag.
    """
    from app.core.backends.openscad import ScadUnavailable
    from app.core.brep.kernel import BRepUnavailable
    from app.core.errors import INSTALL_MISSING, ExternalToolError

    for problem in (BRepUnavailable(), ScadUnavailable(), ExternalToolError(tool="ComfyUI")):
        ids = {action.id for action in problem.suggestions}
        assert INSTALL_MISSING.id in ids, (
            f"{type(problem).__name__}: der Weg zur Installation fehlt"
        )
        assert "report_error" not in ids, "fehlende Software ist kein Fehlerbericht"
