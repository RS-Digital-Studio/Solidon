"""Exception hierarchy (Bauplan §33.1).

An error never ends with "failed". It states, in this order: what did not work,
why, and what is possible now — as clickable actions, not prose (§2.7).

Therefore every exception carries ``suggestions``. An exception without a
suggestion is unfinished, and ``tests/test_errors.py`` says so.

A programming error must never look like a user error, and the other way round:
``UserError`` and ``GeometryError`` are shown as a suggestion, ``InternalError``
opens the error report, ``ExternalToolError`` points at the setting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Final

from app.core.types import ObjectId, OpId, SolverStage, Vec3
from app.i18n import TranslatableText, _

# --- Actions -------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Action:
    """A clickable way out. ``id`` is what a surface binds its handler to."""

    id: str
    label: TranslatableText | str
    primary: bool = False


CANCEL = Action("cancel", _("Abbrechen"))
RETRY = Action("retry", _("Erneut versuchen"), primary=True)
SHOW_DETAILS = Action("show_details", _("Details anzeigen"))
CORRECT_INPUT = Action("correct_input", _("Eingabe korrigieren"), primary=True)
CHOOSE = Action("choose", _("Auswählen"), primary=True)
REPAIR_AND_RETRY = Action("repair_and_retry", _("Reparieren und erneut versuchen"), primary=True)
SHOW_LOCATIONS = Action("show_locations", _("Stellen zeigen"))
USE_VOXEL_STAGE = Action("use_voxel_stage", _("Voxelstufe erzwingen"))
SCALE_TO_FIT = Action("scale_to_fit", _("Auf den Bauraum verkleinern"))
SPLIT_MODEL = Action("split_model", _("Modell teilen"), primary=True)
CHOOSE_PRINTER = Action("choose_printer", _("Anderes Druckerprofil wählen"))
OPEN_SETTINGS = Action("open_settings", _("Einstellungen öffnen"), primary=True)
REPORT_ERROR = Action("report_error", _("Fehlerbericht erstellen"), primary=True)


class OperationCancelled(Exception):
    """The user cancelled. Not an error, and never shown as one (§15.6)."""


def _with_values(kwargs: dict[str, Any], **extra: Any) -> dict[str, Any]:
    """Merge the values a subclass knows with whatever the caller passed."""
    kwargs["values"] = {**extra, **(kwargs.pop("values", None) or {})}
    return kwargs


# --- Base ----------------------------------------------------------------------


class AppError(Exception):
    """Base of every reportable error: title, cause, suggestions."""

    default_title: ClassVar[TranslatableText] = _("Der Vorgang ist nicht durchgelaufen.")
    default_suggestions: ClassVar[tuple[Action, ...]] = (CANCEL,)

    def __init__(
        self,
        title: TranslatableText | str | None = None,
        detail: TranslatableText | str | None = None,
        *,
        suggestions: tuple[Action, ...] = (),
        values: dict[str, Any] | None = None,
        object_id: ObjectId | None = None,
        op_id: OpId | None = None,
    ) -> None:
        self.title = title if title is not None else self.default_title
        self.detail = detail
        self.suggestions = suggestions or self.default_suggestions or AppError.default_suggestions
        self.values: dict[str, Any] = values or {}
        self.object_id = object_id
        self.op_id = op_id
        super().__init__(str(self.title))

    def as_dict(self) -> dict[str, Any]:
        """Serialisable form for log, report and error container (§16.2, §33.2)."""
        return {
            "type": type(self).__name__,
            "title": str(self.title),
            "detail": str(self.detail) if self.detail is not None else None,
            "suggestions": [action.id for action in self.suggestions],
            "values": dict(self.values),
            "object_id": self.object_id,
            "op_id": self.op_id,
        }


# --- User errors: the input was not allowed — correctable ----------------------


class UserError(AppError):
    default_title: ClassVar[TranslatableText] = _("Die Eingabe war so nicht verwendbar.")
    default_suggestions: ClassVar[tuple[Action, ...]] = (CORRECT_INPUT, CANCEL)


class ValidationError(UserError):
    """A parameter violated its schema (§10)."""

    default_title: ClassVar[TranslatableText] = _(
        "Ein Wert liegt außerhalb des zulässigen Bereichs."
    )

    def __init__(
        self,
        field: str = "",
        detail: TranslatableText | str | None = None,
        *,
        value: Any = None,
        constraint: str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(detail=detail, **_with_values(kwargs, field=field, constraint=constraint))
        self.field = field
        self.value = value
        self.constraint = constraint


class AmbiguityError(UserError):
    """Several candidates fit — ask instead of guessing (Leitprinzip 6)."""

    default_title: ClassVar[TranslatableText] = _("Die Angabe ist nicht eindeutig.")
    default_suggestions: ClassVar[tuple[Action, ...]] = (CHOOSE, CANCEL)

    def __init__(
        self,
        question: TranslatableText | str | None = None,
        candidates: tuple[str, ...] = (),
        **kwargs: Any,
    ) -> None:
        super().__init__(detail=question, **_with_values(kwargs, candidates=list(candidates)))
        self.candidates = candidates
        if candidates:
            self.suggestions = (
                *(Action(f"choose:{name}", name) for name in candidates),
                CANCEL,
            )


class UnitUnknownError(UserError):
    """STL carries no unit and the heuristic was not sure enough (§17.1)."""

    default_title: ClassVar[TranslatableText] = _(
        "Die Einheit der Datei ließ sich nicht bestimmen."
    )

    def __init__(
        self,
        detail: TranslatableText | str | None = None,
        candidates: tuple[str, ...] = ("mm", "cm", "in"),
        **kwargs: Any,
    ) -> None:
        super().__init__(detail=detail, **_with_values(kwargs, candidates=list(candidates)))
        self.candidates = candidates
        self.suggestions = (
            *(Action(f"unit:{unit}", unit, primary=unit == "mm") for unit in candidates),
            CANCEL,
        )


# --- Geometry errors: the geometry did not allow it — with a suggestion --------


class GeometryError(AppError):
    default_title: ClassVar[TranslatableText] = _("Die Geometrie ließ die Operation nicht zu.")
    default_suggestions: ClassVar[tuple[Action, ...]] = (REPAIR_AND_RETRY, SHOW_LOCATIONS, CANCEL)


class NotManifoldError(GeometryError):
    """Open edges or non-manifold geometry where a solid was needed."""

    default_title: ClassVar[TranslatableText] = _("Das Modell ist an mehreren Stellen offen.")

    def __init__(
        self,
        detail: TranslatableText | str | None = None,
        *,
        open_edges: int = 0,
        locations: tuple[Vec3, ...] = (),
        **kwargs: Any,
    ) -> None:
        super().__init__(detail=detail, **_with_values(kwargs, open_edges=open_edges))
        self.open_edges = open_edges
        self.locations = locations


class BooleanFailedError(GeometryError):
    """The fallback chain ran out of stages (§17.2)."""

    default_title: ClassVar[TranslatableText] = _(
        "Die boolesche Operation ist auf allen Stufen gescheitert."
    )
    default_suggestions: ClassVar[tuple[Action, ...]] = (
        REPAIR_AND_RETRY,
        USE_VOXEL_STAGE,
        SHOW_LOCATIONS,
        CANCEL,
    )

    def __init__(
        self,
        detail: TranslatableText | str | None = None,
        *,
        attempted: tuple[SolverStage, ...] = (),
        seed: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            detail=detail, **_with_values(kwargs, attempted=list(attempted), seed=seed)
        )
        self.attempted = attempted
        self.seed = seed


class OutOfBuildVolume(GeometryError):
    """The object does not fit the configured build volume (§18.6)."""

    default_title: ClassVar[TranslatableText] = _("Das Objekt passt nicht in den Bauraum.")
    default_suggestions: ClassVar[tuple[Action, ...]] = (
        SPLIT_MODEL,
        SCALE_TO_FIT,
        CHOOSE_PRINTER,
        CANCEL,
    )

    def __init__(
        self,
        detail: TranslatableText | str | None = None,
        *,
        overshoot: Vec3 = (0.0, 0.0, 0.0),
        printer: str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            detail=detail, **_with_values(kwargs, overshoot=list(overshoot), printer=printer)
        )
        self.overshoot = overshoot
        self.printer = printer


# --- External tools ------------------------------------------------------------


class ExternalToolError(AppError):
    """OpenSCAD, slicer, ComfyUI or an LLM did not answer as expected (§27, §28)."""

    default_title: ClassVar[TranslatableText] = _("Ein externes Programm hat nicht geantwortet.")
    default_suggestions: ClassVar[tuple[Action, ...]] = (OPEN_SETTINGS, RETRY, CANCEL)

    def __init__(
        self,
        tool: str = "",
        detail: TranslatableText | str | None = None,
        *,
        exit_code: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(detail=detail, **_with_values(kwargs, tool=tool, exit_code=exit_code))
        self.tool = tool
        self.exit_code = exit_code


# --- Internal ------------------------------------------------------------------


class InternalError(AppError):
    """A programming error. Offer the report, do not blame the user (§33.1)."""

    default_title: ClassVar[TranslatableText] = _(
        "Im Programm ist ein unerwarteter Fehler aufgetreten."
    )
    default_suggestions: ClassVar[tuple[Action, ...]] = (REPORT_ERROR, SHOW_DETAILS, CANCEL)


#: Exception types that mean the *code* is wrong, not the world.
#:
#: A kernel that cannot solve a boolean, a module that is not installed, a
#: network that is down: those are answers, and the places that expect them
#: catch broadly and carry on. The cost of catching broadly is that a wrong call
#: looks exactly the same — and that is not a theory. The convex decomposition of
#: §22.3 passed a parameter this V-HACD does not have; the ``TypeError`` landed
#: in a handler meant for "the module is optional", the function returned an
#: empty list, its test skipped itself for the same reason, and the hint path of
#: the parting plane search was dead for two phases behind a green suite.
#:
#: So every handler that wraps a call whose arguments come from here lets these
#: three through::
#:
#:     try:
#:         ...
#:     except PROGRAMMING_ERRORS:
#:         raise
#:     except Exception as problem:
#:         ...
#:
#: Not a style rule: it is the difference between a bug that shows up on the
#: first run and one that shows up two phases later.
PROGRAMMING_ERRORS: Final = (TypeError, AttributeError, NameError)
