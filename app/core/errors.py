"""Die Ausnahmen-Hierarchie (Bauplan §33.1).

Ein Fehler endet nie mit „fehlgeschlagen". Er nennt, in dieser Reihenfolge:
was nicht ging, warum, und was jetzt möglich ist — als anklickbare Handlungen,
nicht als Prosa (§2.7).

Darum trägt jede Ausnahme ``suggestions``. Eine Ausnahme ohne Vorschlag ist
unfertig, und ``tests/test_errors.py`` sagt das auch.

Ein Programmierfehler darf nie wie ein Bedienfehler aussehen, und umgekehrt:
``UserError`` und ``GeometryError`` erscheinen als Vorschlag, ``InternalError``
öffnet den Fehlerbericht, ``ExternalToolError`` zeigt auf die Einstellung.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Final

from app.core.types import ObjectId, OpId, SolverStage, Vec3
from app.i18n import TranslatableText, _

# --- Handlungen ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Action:
    """Ein anklickbarer Ausweg. An ``id`` bindet eine Oberfläche ihren Handler."""

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
    """Der Nutzer hat abgebrochen. Kein Fehler, und nie als einer
    gezeigt (§15.6)."""


def _with_values(kwargs: dict[str, Any], **extra: Any) -> dict[str, Any]:
    """Vereint die Werte, die eine Unterklasse kennt, mit denen des Aufrufers."""
    kwargs["values"] = {**extra, **(kwargs.pop("values", None) or {})}
    return kwargs


# --- Basis ---------------------------------------------------------------------


class AppError(Exception):
    """Die Basis jedes meldbaren Fehlers: Titel, Ursache, Vorschläge."""

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
        """Serialisierbare Form für Protokoll, Prüfbericht und
        Fehlercontainer (§16.2, §33.2)."""
        return {
            "type": type(self).__name__,
            "title": str(self.title),
            "detail": str(self.detail) if self.detail is not None else None,
            "suggestions": [action.id for action in self.suggestions],
            "values": dict(self.values),
            "object_id": self.object_id,
            "op_id": self.op_id,
        }


# --- Bedienfehler: die Eingabe war so nicht zulässig — korrigierbar ------------


class UserError(AppError):
    default_title: ClassVar[TranslatableText] = _("Die Eingabe war so nicht verwendbar.")
    default_suggestions: ClassVar[tuple[Action, ...]] = (CORRECT_INPUT, CANCEL)


class ValidationError(UserError):
    """Ein Parameter hat sein Schema verletzt (§10)."""

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


class NeedsSolidError(UserError):
    """Die Operation braucht einen exakten Körper, bekommt aber ein Netz (§30).

    Vorher war das eine :class:`ValidationError`, und die heißt „Ein Wert liegt
    außerhalb des zulässigen Bereichs" — für einen Winkel von 2°, der
    einwandfrei war. Der richtige Satz stand im ``detail`` und kam nie an;
    gesucht hätte man danach am falschen Ende, nämlich bei den Zahlen.

    Der Vorschlag ist bewusst schmal: einen Rückweg vom Netz zum exakten Körper
    gibt es nicht (er stünde sonst hier), und einen Knopf anzubieten, der nichts
    tut, wäre schlimmer als keiner. Was hilft, sagt der Satz.
    """

    default_title: ClassVar[TranslatableText] = _(
        "Diese Operation arbeitet nur auf einem exakten Körper."
    )
    default_suggestions: ClassVar[tuple[Action, ...]] = (CANCEL,)


class SketchConflictError(UserError):
    """Zwei Bedingungen einer Skizze vertragen sich nicht (§30.1).

    Überbestimmt oder widersprüchlich — beides hält an und nennt das Paar,
    damit der nächste Klick es lösen kann (Regel 17). ``first`` und ``second``
    sind Indizes in ``sketch.constraints``."""

    default_title: ClassVar[TranslatableText] = _("Zwei Bedingungen widersprechen sich.")

    def __init__(
        self,
        first: int = 0,
        second: int = 0,
        detail: TranslatableText | str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(detail=detail, **_with_values(kwargs, first=first, second=second))
        self.first = first
        self.second = second
        self.suggestions = (
            Action(f"remove_constraint:{first}", _("Erste Bedingung entfernen"), primary=True),
            Action(f"remove_constraint:{second}", _("Zweite Bedingung entfernen")),
            CANCEL,
        )


class AmbiguityError(UserError):
    """Mehrere Kandidaten passen — fragen statt raten (Leitprinzip 6)."""

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
    """STL trägt keine Einheit, und die Heuristik war sich nicht sicher
    genug (§17.1)."""

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


# --- Geometriefehler: die Geometrie ließ es nicht zu — mit Vorschlag -----------


class GeometryError(AppError):
    default_title: ClassVar[TranslatableText] = _("Die Geometrie ließ die Operation nicht zu.")
    default_suggestions: ClassVar[tuple[Action, ...]] = (REPAIR_AND_RETRY, SHOW_LOCATIONS, CANCEL)


class NotManifoldError(GeometryError):
    """Offene Kanten oder nicht-mannigfaltige Geometrie, wo ein Volumenkörper
    gebraucht wurde."""

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
    """Der Rückfallkette sind die Stufen ausgegangen (§17.2)."""

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
    """Das Objekt passt nicht in den eingestellten Bauraum (§18.6)."""

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


# --- Externe Programme -----------------------------------------------------------


class ExternalToolError(AppError):
    """OpenSCAD, Slicer, ComfyUI oder ein LLM hat nicht wie erwartet
    geantwortet (§27, §28)."""

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


# --- Intern --------------------------------------------------------------------


class InternalError(AppError):
    """Ein Programmierfehler. Den Bericht anbieten, nicht dem Nutzer die
    Schuld geben (§33.1)."""

    default_title: ClassVar[TranslatableText] = _(
        "Im Programm ist ein unerwarteter Fehler aufgetreten."
    )
    default_suggestions: ClassVar[tuple[Action, ...]] = (REPORT_ERROR, SHOW_DETAILS, CANCEL)


#: Ausnahmearten, die bedeuten: der *Code* ist falsch, nicht die Welt.
#:
#: Ein Kern, der eine Boolesche Op nicht löst, ein Modul, das nicht installiert
#: ist, ein Netz, das nicht antwortet: das sind Antworten, und die Stellen, die
#: sie erwarten, fangen breit und machen weiter. Der Preis des breiten Fangens
#: ist, dass ein falscher Aufruf genauso aussieht — und das ist keine Theorie.
#: Die konvexe Zerlegung aus §22.3 übergab einen Parameter, den dieses V-HACD
#: nicht hat; der ``TypeError`` landete in einem Handler für „das Modul ist
#: optional", die Funktion gab eine leere Liste zurück, ihr Test übersprang
#: sich aus demselben Grund, und der Hinweispfad der Trennebenensuche war zwei
#: Phasen lang tot — hinter einer grünen Suite.
#:
#: Darum lässt jeder Handler, der einen Aufruf mit Argumenten von hier
#: umschließt, diese drei durch::
#:
#:     try:
#:         ...
#:     except PROGRAMMING_ERRORS:
#:         raise
#:     except Exception as problem:
#:         ...
#:
#: Keine Stilregel: es ist der Unterschied zwischen einem Fehler, der beim
#: ersten Lauf auffällt, und einem, der zwei Phasen später auffällt.
PROGRAMMING_ERRORS: Final = (TypeError, AttributeError, NameError)
