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

from typing import Any, ClassVar, Final

from app.core.types import Action as Action
from app.core.types import ObjectId, OpId, SolverStage, Vec3
from app.core.units import UNIT_NAMES
from app.i18n import TranslatableText, _

# --- Handlungen ------------------------------------------------------------------


CANCEL = Action("cancel", _("Abbrechen"))
RETRY = Action("retry", _("Erneut versuchen"), primary=True)
SHOW_DETAILS = Action("show_details", _("Details anzeigen"))
CORRECT_INPUT = Action("correct_input", _("Eingabe korrigieren"), primary=True)
USE_SUGGESTED_NAME = Action("use_suggested_name", _("Freien Namen verwenden"), primary=True)
#: Für einen Schritt, den diese Fassung nicht rechnen kann (§16.2).
#:
#: **Regel 17 verlangt eine Handlung, und lange gab es hier keine ehrliche.**
#: ``CORRECT_INPUT`` ist falsch — es gibt keine Eingabe zu korrigieren, der
#: Schritt selbst ist unbekannt. Der Verlauf bietet inzwischen ein
#: rücknehmbares Löschen aus der Mitte (§15.4), doch damit sind die erhaltenen
#: Werte nicht lesbar. Und ``CANCEL`` ist ausdrücklich kein Rat.
#:
#: Was bleibt, ist das, was wirklich da ist: **die Werte des Schritts.** Ein
#: Projekt aus einer früheren Fassung trägt sie unverändert weiter — bei einer
#: Datei aus 0.1.3 ist das der OpenSCAD-Quelltext, den jemand geschrieben hat.
#: Den herauszuholen ist eine echte Handlung: Er lässt sich anderswo benutzen
#: oder mit den Skizzen-Ops nachbauen. Der Name nennt die **Werte** und nicht
#: den Quelltext, weil derselbe Fall auch einen fehlenden Rezept-Baustein
#: trifft, und der hat Parameter ohne Quelltext.
SHOW_STEP_VALUES = Action("show_step_values", _("Werte ansehen"), primary=True)
CHOOSE = Action("choose", _("Auswählen"), primary=True)
#: Andere Objekte für einen Schritt wählen — im Objektbaum, nicht im Dialog.
#:
#: **Der zweite Fall von „Eingabe korrigieren", und er braucht eine eigene
#: Handlung.** Wo ein Parameter nicht geht, öffnet der Dialog des Schritts;
#: wo die *Auswahl* nicht geht, gibt es nichts aufzuklappen — ``field="in"``
#: ist keine Zeile im Formular. Ein Knopf, der den Dialog öffnete, zeigte auf
#: ein Feld, das es nicht gibt.
CHANGE_SELECTION = Action("change_selection", _("Andere Objekte wählen"), primary=True)
REPAIR_AND_RETRY = Action("repair_and_retry", _("Reparieren und erneut versuchen"), primary=True)
SHOW_LOCATIONS = Action("show_locations", _("Stellen zeigen"))
#: Die Senkung über einer geänderten Bohrung im selben Verhältnis mitziehen.
#:
#: **Regel 17 verlangt eine Handlung, und „ändern Sie die Senkung auch"
#: wäre keine** — der Kunde müsste den Faktor selbst ausrechnen. Die
#: Handlung nennt deshalb das Ergebnis und nicht die Arbeit.
RESIZE_THE_WIDENING = Action("resize_the_widening", _("Senkung mitziehen"), primary=True)
SHOW_HISTORY = Action("show_history", _("Verlauf zeigen"))
#: Die laufende Teilungssuche anhalten und verwerfen.
#:
#: **Sie hieß ``cancel_evaluation`` und meinte die Teilung.** Ein zweiter
#: Start der Suche wirft „Die Teilung läuft schon", und der einzige Vorschlag
#: dazu trug den Namen der *Auswertung* — eine andere Sache, die daneben
#: ebenfalls abbrechbar ist. Verdrahtet war er nirgends, also wurde er über
#: ``unhandled_advice`` zu einem Satz zum Lesen: Der Kunde bekam den Rat, die
#: Teilung abzubrechen, und keinen Weg, es zu tun.
CANCEL_SPLIT = Action("cancel_split", _("Die laufende Teilung abbrechen"), primary=True)
USE_VOXEL_STAGE = Action("use_voxel_stage", _("Gröber rechnen — Maße werden gerundet"))
SCALE_TO_FIT = Action("scale_to_fit", _("Auf den Bauraum verkleinern"))
#: Der Ausweg aus „dieses Format braucht einen exakten Körper": dasselbe
#: Teil in ein Format schreiben, das Dreiecke kennt. 3MF und nicht STL,
#: weil es Materialslots und Baugruppenstruktur mitnimmt — also genau
#: das, wofür der Kunde eine Datei mit mehr als Geometrie wollte.
EXPORT_AS_MESH = Action("export_as_mesh", _("Als 3MF speichern"), primary=True)
SPLIT_MODEL = Action("split_model", _("Modell teilen"), primary=True)
SPLIT_ALONG_LINE = Action("split_along_line", _("An gezeichneter Linie trennen"), primary=True)
PLACE_ON_BED = Action("place_on_bed", _("Auf das Bett setzen"), primary=True)
ARRANGE_ON_BED = Action("arrange_on_bed", _("Auf dem Bett anordnen"), primary=True)
CHOOSE_PRINTER = Action("choose_printer", _("Anderes Druckerprofil wählen"))
OPEN_SETTINGS = Action("open_settings", _("Einstellungen öffnen"), primary=True)
#: Der Weg zu den zusätzlichen Programmen — wo sie liegen, und ein Knopf, der
#: sie holt. Nicht ``OPEN_SETTINGS``: Ein fehlender Slicer und ein stilles
#: ComfyUI wurden beide mit „Einstellungen öffnen" beantwortet, und geöffnet
#: wurde jedes Mal die Liste der externen Programme.
#: Der Knopf trägt jetzt den Namen des Menüeintrags, unter dem er landet.
INSTALL_MISSING = Action("install", _("Zusätzliche Programme …"), primary=True)
#: Der Ausweg, wenn der Slicer nicht kann oder nicht da ist: Solidon schreibt
#: die Datei, geslict wird von Hand. Sechsmal in der Übergabe gebaut, und
#: einmal davon als „Nur exportieren." — derselbe Knopf mit einer zweiten
#: Beschriftung, die sich in fünf Sprachen unabhängig weiterentwickelt hätte.
#: Der Satz nennt beide Hälften, weil die erste allein nicht sagt, was danach
#: zu tun ist.
EXPORT_ONLY = Action("export_only", _("Nur exportieren und selbst slicen"))
#: Die drei Geschwister von ``EXPORT_ONLY``, ein Mal übersehen: Als die sechs
#: inline gebauten ``export_only`` zur Konstante wurden, blieben diese drei
#: als ``Action(id=…)`` in der Übergabe zurück — Schlüsselwort-Aufrufe, die
#: der Wächter in ``test_ui.py`` nicht sah. Gesetzt waren sie überall,
#: verdrahtet nirgends: Der Kunde las „Einen anderen Slicer auswählen." als
#: Satz über dem einzigen Knopf „Nur exportieren und selbst slicen."
SHOW_SLICER_OUTPUT = Action("show_output", _("Ausgabe des Slicers ansehen"))
CHECK_SLICER_PROFILE = Action("check_profile", _("Maschinenprofil prüfen"))
#: Vorne, weil er der häufigste richtige nächste Schritt ist: Scheitert der
#: eingestellte Slicer, stehen auf vielen Rechnern zwei weitere daneben —
#: und die Absage bot bisher keinen Weg zu ihnen an (§29, §2.1).
CHOOSE_SLICER = Action("choose_slicer", _("Einen anderen Slicer auswählen"), primary=True)
#: Zwei verschenkte Klickwege, gefunden beim Release-Durchgang am 30.08.2026 —
#: und zwar in der Ausnahmemenge des Wächters, die eine Stunde zuvor pauschal
#: befüllt worden war. Beide standen als **Satz** da, was ehrlich ist
#: (``dialogs.unhandled_advice``), aber an diesen zwei Stellen zu wenig: Der
#: naheliegendste Rat soll ein Knopf sein, wo die Anwendung ihn einlösen kann.
#:
#: ``decimate_mesh`` ist der Hauptvorschlag zu „Für eine Analysekarte ist
#: dieses Modell zu groß" — und die Operation gleichen Namens liegt im
#: Register. ``open_in_browser`` nennt eine Adresse, die in ``values["url"]``
#: mitreist, und ``QDesktopServices`` öffnet sie.
DECIMATE_MESH = Action("decimate_mesh", _("Dreiecke verringern"), primary=True)
OPEN_IN_BROWSER = Action("open_in_browser", _("Seite im Browser öffnen"))
#: Die kleinen Einzelteile wegwerfen, die beim Einlesen aufgefallen sind.
#:
#: **Eigene Handlung und nicht ``REPAIR_AND_RETRY``**, obwohl beide
#: dieselbe Operation rufen: Der bestehende Reparatur-Handler ruft
#: ``repair`` ohne Parameter, und ``small_components`` steht dort auf
#: ``False`` (``geom/repair.py``). Der Knopf wäre durchgelaufen, hätte
#: Erfolg gemeldet und die Teile stehen gelassen — ein Knopf ohne Wirkung
#: ist schlimmer als keiner, und ein Klickweg-Test hätte es nicht
#: gefangen: Die Operation läuft ja.
REMOVE_SMALL_PARTS = Action("remove_small_parts", _("Kleine Teile entfernen"), primary=True)
REPORT_ERROR = Action("report_error", _("Fehlerbericht erstellen"), primary=True)
CHECK_UPDATES = Action("check_updates", _("Nach einer neuen Version sehen"), primary=True)
#: Der Ausweg, wenn das Paket nicht kommt oder sich nicht starten lässt: der
#: Weg, den es vor dem Update in der Anwendung als einzigen gab (§37.2).
OPEN_DOWNLOAD_PAGE = Action("open_download_page", _("Download-Seite öffnen"), primary=True)
SAVE_ELSEWHERE = Action("save_elsewhere", _("Anderen Ort wählen"))
#: **Der Ausweg, wenn die Datei selbst nicht geht.** Eine Absage beim
#: Einlesen trägt sonst nur *Abbrechen*: ``correct_input`` fällt weg, weil
#: es einen Schritt braucht, den es vor der Operation nicht gibt
#: (``dialogs.NEEDS_OP``). Was hilft, ist der Dateidialog — und den gibt es.
CHOOSE_ANOTHER_FILE = Action("choose_another_file", _("Andere Datei wählen"), primary=True)
ENTER_LICENCE_KEY = Action("enter_licence_key", _("Lizenzschlüssel eintragen"), primary=True)
BUY_LICENCE = Action("buy_licence", _("Solidon kaufen"))
ACTIVATE_ONLINE = Action("activate_online", _("Online aktivieren"), primary=True)
ACTIVATE_OFFLINE = Action("activate_offline", _("Offline aktivieren …"), primary=True)
DEACTIVATE_DEVICE = Action("deactivate_device", _("Diesen Rechner deaktivieren"), primary=True)


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
    #: Was gilt, wenn der Aufrufer keinen Grund nennt — für Fehler, deren
    #: Ursache je Klasse dieselbe ist und deren Ausweg sich in einen Satz
    #: fassen lässt. Die meisten Klassen lassen es leer: Ihr Grund steht erst
    #: beim Aufrufer fest.
    default_detail: ClassVar[TranslatableText | None] = None

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
        self.detail = detail if detail is not None else self.default_detail
        self.suggestions = suggestions or self.default_suggestions or AppError.default_suggestions
        self.values: dict[str, Any] = values or {}
        self.object_id = object_id
        self.op_id = op_id
        # Titel *und* Detail. Der Titel nennt die Art des Fehlers und ist
        # darum je Klasse gleich — „Ein Wert liegt außerhalb des zulässigen
        # Bereichs" steht über jedem ValidationError, ob es um eine Wandstärke
        # geht oder um ein fehlendes @ vor einem Parameternamen. Wer nur ihn
        # sieht, weiß nichts. Die Oberfläche liest beide Felder einzeln und
        # merkt davon nichts; Protokoll und Traceback zeigen bisher allein
        # diesen Text, und dort ist der Unterschied der ganze Inhalt.
        super().__init__(f"{self.title}: {self.detail}" if self.detail else str(self.title))

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


#: Die Beschränkungen, für die „außerhalb des zulässigen Bereichs" zutrifft.
#:
#: **Das Kriterium ist eine Zahl in einem Eingabefeld.** Eine Spanne liegt vor,
#: wenn der Nutzer einen Wert eingegeben hat, es dafür eine Grenze gibt — fest
#: oder aus anderen Werten gerechnet —, und die Zahl in die richtige Richtung zu
#: ändern den Fehler behebt. Danach ist ``hole_fits`` eine Spanne (die Löcher
#: sind größer als ihr Teilkreis, ``hole_diameter`` verkleinern hilft) und
#: ``file_too_large`` keine: Dort ist die Datei zu groß, es gibt kein Feld, in
#: dem eine Zahl stünde, und der Titel zeigte auf eine Eingabe, die es nicht gibt.
#:
#: Alles Übrige ist keine Zahlenspanne: leer, unlesbar, falscher Typ, fehlend,
#: kein Umriss, kein Profil, unbekanntes Objekt.
#:
#: ``positive`` kam am 24.08.2026 dazu — mit sechzehn Aufrufern der häufigste
#: von allen, weil :func:`require_positive` sie bündelt. Er stand vorher nicht
#: hier, und das war eine Lücke, keine Entscheidung: „Dieses Maß muss größer als
#: null sein" **ist** eine verletzte Spanne, nämlich die nach unten offene. Der
#: Nutzer las darüber „Die Eingabe war so nicht verwendbar." — wahr, aber vage,
#: und die Oberfläche zeichnet den Titel groß und das Detail klein. Genau die
#: Beschwerde, aus der dieser Satz überhaupt entstanden ist, nur mit umgekehrtem
#: Vorzeichen: Dort behauptete der Titel eine Zahlenspanne, wo keine war; hier
#: verschwieg er eine, die es gibt.
#:
#: **Am selben Tag kamen die übrigen fünfzehn dazu, und zwar aus demselben
#: Grund.** ``positive`` allein einzutragen hieß, denselben Fehler an fünfzehn
#: weiteren Stellen stehenzulassen: ``corner_count`` sagt „zwischen drei und
#: vierundsechzig Ecken" und nennt damit beide Grenzen wörtlich, ``negative``
#: ist der unmittelbare Gegenpart zu ``positive``, ``too_short`` verlangt
#: „mindestens zwei Gänge". Über allen dreien stand der vage Satz. Die Liste ist
#: seitdem **vollständig gegen den Code geprüft**, nicht nach Gefühl gefüllt:
#: ``test_errors`` sammelt jeden ``constraint``, den ``app/core`` wirklich setzt,
#: und besteht darauf, dass er hier oder in der Gegenliste des Tests steht. Ein
#: neuer Wert, den niemand einordnet, ist ab dann ein roter Lauf und kein
#: stiller Titel.
_RANGE_CONSTRAINTS: Final = frozenset(
    {
        # Die Grenzen des Parameterschemas selbst (§10).
        "minimum",
        "maximum",
        "range",
        # Vorzeichen.
        "positive",
        "negative",
        # Anzahlen mit Unter- oder Obergrenze.
        "corner_count",
        "pattern_count",
        "build_volume",
        # Längen und Dicken gegen eine gerechnete Grenze.
        "too_short",
        "too_coarse",
        "minimum_wall",
        "nozzle_width",
        "layer_height",
        "cell_size",
        "no_core",
        "kinks_inside",
        "crosses_axis",
        # Ein Maß, das gegen ein anderes Maß desselben Dialogs verstößt.
        "slot_proportion",
        "hole_fits",
        "cavity_too_small",
    }
)


class ValidationError(UserError):
    """Ein Parameter hat sein Schema verletzt (§10).

    **Der Titel folgt der Beschränkung, nicht der Klasse.** „Ein Wert liegt
    außerhalb des zulässigen Bereichs." stand über *jeder* dieser Ausnahmen —
    auch über „Diese Datei ist keine STEP-Datei." und „Der Parametername fehlt
    hinter dem @". Die Oberfläche zeichnet den Titel groß und das Detail klein:
    Wer hinsieht, liest zuerst einen Satz, der nicht stimmt, und sucht dann bei
    den Zahlen.

    Drei Klassen sind genau deswegen entstanden — :class:`NeedsSolidError`,
    :class:`SketchConflictError`, :class:`UnitUnknownError` —, jede mit
    demselben Vermerk im Docstring. Sie bleiben, denn sie tragen eigene
    Vorschläge; was hier dazukommt, ist die Ursache statt des nächsten
    Einzelfalls: Wo keine Spanne verletzt wurde, gilt der Satz der Oberklasse,
    „Die Eingabe war so nicht verwendbar." Er ist allgemein, aber er lügt
    nicht — und das Detail daneben sagt weiter, was gemeint ist.
    """

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
        if kwargs.get("title") is None and constraint not in _RANGE_CONSTRAINTS:
            kwargs["title"] = UserError.default_title
        super().__init__(detail=detail, **_with_values(kwargs, field=field, constraint=constraint))
        self.field = field
        self.value = value
        self.constraint = constraint


def require_positive(field: str, value: float) -> None:
    """Hält an, wenn ein Maß nicht größer als null ist.

    Sechzehn Stellen im Kern prüfen dasselbe, und bis zum 24.08.2026 taten es
    zwei Sorten: elf über eine private Hilfe in ``sketch.shapes``, fünf
    ausgeschrieben — und die fünf ließen ``constraint`` leer. Das Feld ist
    maschinenlesbar und wird an zwei Dutzend Stellen abgefragt; ein Fehler ohne
    Kennung ist für jeden Leser ein anderer Fehler als derselbe mit.

    Zwei der fünf prüften mehrere Maße in einer Bedingung und nannten dann
    immer das erste. Wer bei einem Gitter ``wall`` auf null setzte, bekam
    ``cell`` markiert — die Oberfläche zeigte auf das falsche Eingabefeld.
    Einzeln geprüft nennt jeder Fehler das Maß, das ihn ausgelöst hat.
    """
    if value <= 0.0:
        raise ValidationError(
            field,
            _("Dieses Maß muss größer als null sein."),
            value=value,
            constraint="positive",
        )


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
        "Dieses Werkzeug braucht einzeln bearbeitbare Flächen und Kanten."
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
        # Auf dem Knopf steht der Name, in der Kennung der Wert: „in" allein
        # ist auf Deutsch ein Verhältniswort und keine Antwort (`units`).
        self.suggestions = (
            *(
                Action(f"unit:{unit}", UNIT_NAMES.get(unit, unit), primary=unit == "mm")
                for unit in candidates
            ),
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
        "Die Körper ließen sich auf keinem Weg verknüpfen."
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
        # **„Auf allen Stufen" war beim Arbeiten im Fenster nie wahr.** Dort
        # läuft die kurze Kette (``DRAFT_CHAIN``: direkt, verschweißt), die
        # vollen vier Stufen laufen beim Export (§17.2). Der Titel behauptete
        # trotzdem, es sei alles versucht — und daneben stand als einziger Rat
        # *Voxelstufe erzwingen*, also genau die Stufe, die noch offen war.
        # Zwei Sätze, die sich widersprechen, und keiner davon anklickbar.
        #
        # Jetzt sagt der Titel, was gilt: War die Voxelstufe dran, ist sie
        # ausgereizt und der Rat fällt weg. War sie es nicht, sagt der Titel es
        # und der Rat bleibt — mit einem Handler dahinter, der einmal mit der
        # vollen Kette rechnet.
        if attempted and "voxel" not in attempted:
            kwargs.setdefault(
                "title", _("Die Körper ließen sich in der schnellen Vorschau nicht verknüpfen.")
            )
        elif "voxel" in attempted and kwargs.get("suggestions") is None:
            kwargs["suggestions"] = tuple(
                action for action in self.default_suggestions if action is not USE_VOXEL_STAGE
            )
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
    """Der Slicer, ComfyUI oder ein LLM hat nicht wie erwartet geantwortet
    (§27, §28)."""

    default_title: ClassVar[TranslatableText] = _("Ein externes Programm hat nicht geantwortet.")
    default_suggestions: ClassVar[tuple[Action, ...]] = (INSTALL_MISSING, RETRY, CANCEL)

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


class FileWriteError(AppError):
    """Eine Datei ließ sich nicht schreiben — Rechte, Pfad, volle Platte.

    **Es gab sie nicht, und deshalb lief der Fehler bis oben durch.** Der
    Schreiber im Kern ließ jeden ``OSError`` weiterlaufen: In der
    Kommandozeile endete ein Export in ein Zielverzeichnis, das eine Datei ist,
    mit einem Stapelabzug (`FileExistsError [WinError 183]`) — verboten im
    Nutzerdialog, und ohne jeden Hinweis, was jetzt hilft. Im Fenster war es
    stiller und schlimmer: Der Export-Arbeiter fängt ``AppError``, ein
    ``OSError`` riss den Thread ab, und im Fenster geschah gar nichts mehr.

    Der Grund vom Betriebssystem steht im Detail. Er ist nicht übersetzt und
    darf es nicht sein: „Zugriff verweigert" gegen „Datei nicht gefunden" ist
    die eigentliche Auskunft, und sie kommt von dort, wo sie entsteht.
    """

    default_title: ClassVar[TranslatableText] = _("Die Datei ließ sich nicht schreiben.")
    #: **Zwei Wege, und beide sind der Fall, der wirklich vorkommt.** Die Datei
    #: liegt im Slicer offen oder das Laufwerk ist voll: dann hilft es, sie
    #: freizugeben und *erneut* zu schreiben — oder einen *anderen Ort* zu
    #: nehmen. „Eingabe korrigieren" stand hier vorn und meinte nichts: An einem
    #: Schreibfehler gibt es keine Eingabe (er trägt keine ``op_id``, und
    #: ``dialogs.NEEDS_OP`` blendet ihn deshalb aus).
    default_suggestions: ClassVar[tuple[Action, ...]] = (
        RETRY,
        SAVE_ELSEWHERE,
        CORRECT_INPUT,
        CANCEL,
    )

    def __init__(
        self,
        target: str = "",
        detail: TranslatableText | str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(detail=detail, **_with_values(kwargs, target=target))
        self.target = target


# --- Freischaltung ---------------------------------------------------------------


class LicenceRequired(AppError):
    """Diese Handlung braucht einen Schlüssel und die Gerätefreigabe.

    Kein Bedienfehler — es gibt nichts zu korrigieren — und kein
    Programmfehler. Ein Zustand, wie ``ExternalToolError`` einer ist, mit
    demselben Bau: sagen, was jetzt möglich ist. Die beiden Wege heißen
    Schlüssel eintragen und kaufen, und mehr Wege gibt es nicht.

    Der Vorgabetitel ist absichtlich neutral: Die Verkaufsversion vom
    01.11.2026 bietet zunächst keinen Testzeitraum an. Nur der Kern kennt den
    wirklichen Zustand und setzt beim tatsächlich abgelaufenen Test einen
    genaueren Titel.

    **Was liest, wirft das nie.** Öffnen, Ansehen, Messen, Prüfbericht,
    Schichtanalyse, Speichern und Undo laufen nach Ablauf weiter — eine
    Testversion, die gespeicherte Arbeit einschließt, erzeugt einen
    verärgerten Nicht-Käufer statt eines späteren.
    """

    default_title: ClassVar[TranslatableText] = _(
        "Dafür braucht Solidon einen Lizenzschlüssel und die einmalige "
        "Geräteaktivierung (Hilfe → Solidon freischalten …)."
    )
    default_suggestions: ClassVar[tuple[Action, ...]] = (ENTER_LICENCE_KEY, BUY_LICENCE, CANCEL)

    def __init__(
        self,
        action: str = "",
        detail: TranslatableText | str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(detail=detail, **_with_values(kwargs, action=action))
        self.action = action
        """Was versucht wurde — ``change``, ``export``, ``slicer`` oder
        ``chat``. Geht ins Protokoll, damit sich später sagen lässt, an welcher
        Grenze Leute tatsächlich anstoßen."""


class DeviceActivationRequired(AppError):
    """Der Kaufcode gilt, aber diesem Rechner fehlt sein signiertes Zertifikat."""

    default_title: ClassVar[TranslatableText] = _(
        "Dieser Rechner ist für den Lizenzschlüssel noch nicht aktiviert."
    )
    default_suggestions: ClassVar[tuple[Action, ...]] = (
        ACTIVATE_ONLINE,
        ACTIVATE_OFFLINE,
        CANCEL,
    )
    default_detail: ClassVar[TranslatableText | None] = _(
        "Aktivieren Sie diesen Rechner einmal online oder über die "
        "Anfrage- und Antwortdatei. Danach bleibt Solidon offline nutzbar."
    )

    def __init__(
        self,
        action: str = "",
        detail: TranslatableText | str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(detail=detail, **_with_values(kwargs, action=action))
        self.action = action


class DeviceDeactivationPending(AppError):
    """Die lokale Sperre steht, die Serverbestätigung aber noch aus."""

    default_title: ClassVar[TranslatableText] = _(
        "Die Deaktivierung dieses Rechners ist noch nicht bestätigt."
    )
    default_suggestions: ClassVar[tuple[Action, ...]] = (
        DEACTIVATE_DEVICE,
        REPORT_ERROR,
        CANCEL,
    )
    default_detail: ClassVar[TranslatableText | None] = _(
        "Solidon bleibt auf diesem Rechner sicher gesperrt. Senden Sie die "
        "Deaktivierung erneut, damit der Geräteplatz zuverlässig frei wird."
    )

    def __init__(
        self,
        action: str = "",
        detail: TranslatableText | str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(detail=detail, **_with_values(kwargs, action=action))
        self.action = action


class ActiveLicenceCannotBeReplaced(AppError):
    """Eine bestehende Gerätebindung muss vor einem Schlüsselwechsel weg."""

    default_title: ClassVar[TranslatableText] = _(
        "Der aktive Lizenzschlüssel kann nicht überschrieben werden."
    )
    default_suggestions: ClassVar[tuple[Action, ...]] = (DEACTIVATE_DEVICE, CANCEL)


class InstallationDamaged(AppError):
    """Eine Programmdatei stimmt nicht mit der signierten Auslieferung überein.

    **Der Unterschied zu :class:`LicenceRequired` ist der Unterschied zwischen
    zwei Kunden.** Bricht das Manifest (H4), ist die schreibende Seite zu — das
    bleibt so, denn eine veränderte Grenzdatei nimmt der Freischaltung die
    Grundlage. Gemeldet wurde dabei aber „Der Testzeitraum ist abgelaufen" mit
    dem Vorschlag *Solidon kaufen*, und das bekam auch, wer längst bezahlt
    hatte: Sein gültiger Schlüssel wurde gar nicht erst gelesen. Ein
    Virenscanner in Quarantäne, ein halbes Update oder ein Plattenfehler
    reichen dafür — der Satz war dann in beide Richtungen falsch, und der
    einzige angebotene Weg führte in den Verkauf statt zur Reparatur.

    Also ein eigener Zustand mit eigenen Wegen: neu installieren, oder den
    Support fragen. Beide sind verdrahtet (``open_download_page``,
    ``report_error``) — ein Rat ohne Knopf wäre hier besonders bitter, weil
    niemand von selbst darauf käme, dass die Dateien und nicht die Lizenz das
    Problem sind.
    """

    default_title: ClassVar[TranslatableText] = _("Die Installation von Solidon ist beschädigt.")
    default_suggestions: ClassVar[tuple[Action, ...]] = (
        OPEN_DOWNLOAD_PAGE,
        REPORT_ERROR,
        CANCEL,
    )

    def __init__(
        self,
        action: str = "",
        detail: TranslatableText | str | None = None,
        **kwargs: Any,
    ) -> None:
        if detail is None:
            detail = _(
                "Eine Programmdatei stimmt nicht mit der Auslieferung überein. "
                "Installieren Sie Solidon neu; hilft das nicht, wenden Sie sich an den Support."
            )
        super().__init__(detail=detail, **_with_values(kwargs, action=action))
        self.action = action
        """Was versucht wurde — dieselben vier Namen wie bei
        :class:`LicenceRequired`, damit das Protokoll beide Fälle nebeneinander
        auswerten kann."""


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
