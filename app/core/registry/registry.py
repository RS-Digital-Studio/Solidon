"""Das Register der Operationen (Bauplan §10).

Eine Operation wird genau einmal deklariert; Menü, Kontextmenü, Palette,
Kommandozeile, Agenten-Werkzeugschema und Dokumentation entstehen aus dieser
Deklaration (§1, Leitprinzip 3). Eine unvollständige Registrierung scheitert
hier, beim Import, nicht später in einer Oberfläche.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Final, get_args

from app.core.errors import InternalError
from app.core.types import BaseParams, FeatureKind, OpFn
from app.i18n import TranslatableText, _, sort_key

FEATURE_KINDS: Final[tuple[str, ...]] = get_args(FeatureKind)

#: Kategorien aus dem Operationskatalog (§25). Sie ordnen das Menü.
#: Der Katalog aus §25, in der Reihenfolge, in der er im Menü erscheint. Vier
#: davon halten keine Operationen und werden es auch nicht: Parameter und
#: Passungen leben im Dokument und werden über ihre Panels und den Agenten
#: geändert (§13, §14); Export und Variantengenerator sind Abläufe, die *um*
#: eine Auswertung herum laufen statt in ihr — ein Variantensatz wertet den
#: ganzen Stapel neu aus, und das kann eine Operation innerhalb dieser
#: Auswertung nicht (§15.1). Leere Kategorien erreichen nie ein Menü, sie
#: kosten also nichts außer diesem Absatz.
CATEGORIES: Final[dict[str, TranslatableText]] = {
    "scene": _("Szene"),
    "parameters": _("Parameter"),
    "fits": _("Passungen"),
    "repair": _("Reparatur"),
    "transform": _("Transformation"),
    "primitive": _("Grundformen"),
    # Nicht „Boolesch". Der Begriff ist richtig und in jedem CAD-Programm
    # üblich — und er ist genau die Sorte Wort, an der jemand hängen bleibt,
    # der zum ersten Mal zwei Körper zusammenfügen will. Was darunter steht,
    # sind Vereinigen, Abziehen, Schnittmenge und Weich verschmelzen; zwei
    # davon nennt der Titel, und die anderen beiden erklären sich, wenn man
    # erst einmal am richtigen Menü ist.
    "boolean": _("Verbinden und Abziehen"),
    "sketch": _("Skizze"),
    "shaping": _("Formgebung"),
    "holes": _("Bohrungen"),
    "parts": _("Bausteine"),
    # Nicht „Druckvorbereitung": Diese Kategorie steht als Untermenü unter der
    # Gruppe *Vorbereiten*, und zwei Ebenen, die fast dasselbe Wort tragen,
    # sagen zusammen weniger als eine. Der Name nennt jetzt, wofür man
    # hierherkommt — teilen, aushöhlen, ein Maß anpassen.
    "prepare": _("Teilen und Anpassen"),
    "import": _("Import"),
    "export": _("Export"),
    "colour": _("Farbe"),
    "label": _("Beschriftung"),
    "surface": _("Oberfläche"),
    "mesh": _("Netz"),
    "variants": _("Varianten"),
}

#: Wie die Kategorien des Registers auf Menüs der Leiste fallen (§2.5).
#:
#: Vier eigene Menüs plus dreizehn aus dem Register waren siebzehn — bei 1280
#: Pixeln Fensterbreite läuft das über. Die Kategorie im Register bleibt, wie
#: Bauplan §25 sie festlegt; hier liegt nur eine Zuordnung darüber. Eine
#: Gruppe mit einer einzigen Kategorie steht flach, sonst bekommt jede
#: Kategorie ihr Untermenü.
#:
#: Die Titel sind mit ``_()`` markiert, nicht mit ``tr()``: der Abgleich der
#: Sprachdateien liest literale Aufrufe, und ``tr(variable)`` sieht er nicht —
#: die Gruppen wären auf Deutsch stehen geblieben (Regel 20).
#:
#: Sie stand in der Oberfläche und lebt seit der Agent-Vertiefung (4.3) hier,
#: weil drei Stellen sie brauchen und eine der Kern ist: Menüleiste,
#: Kontextmenü am Körper — und die Werkzeugbeschreibungen des Agenten, die
#: den Menüort nennen, damit der Chat als Suchfeld taugt (§2.6).
MENU_GROUPS: Final[tuple[tuple[TranslatableText, tuple[str, ...]], ...]] = (
    (_("Objekt"), ("scene",)),
    (_("Erzeugen"), ("primitive", "import", "sketch", "label")),
    (_("Ändern"), ("boolean", "transform", "shaping", "holes", "surface", "mesh", "repair")),
    (_("Bausteine"), ("parts",)),
    (_("Vorbereiten"), ("prepare", "colour")),
)


def group_title(category: str) -> str:
    """Der Menütitel, unter dem diese Kategorie steht.

    Kennt die Tabelle sie nicht, ist der Kategoriename die ehrlichste Antwort
    — eine neue Kategorie soll auftauchen und nicht verschwinden, so hält es
    auch die Menüleiste.
    """
    for title, categories in MENU_GROUPS:
        if category in categories:
            return str(title)
    return category


#: Zusammengelegte Menü-Zwillinge: dieselbe Handlung in zwei Rechenkernen.
#:
#: „Quader anlegen" und „Exakten Quader anlegen" waren zwei Menüeinträge für
#: einen Quader — gegen das Hausprinzip „eine Operation je Handlung, nicht je
#: Variante". Die Ops bleiben im Register getrennt (Verlauf und Provenienz
#: brauchen das); zusammengelegt ist nur die Bedienung: der Eintrag des
#: Mesh-Zwillings trägt einen Umschalter „Exakt (B-Rep)", und der Dialog
#: wählt die Op. Schlüssel ist der versteckte B-Rep-Zwilling, Wert der
#: sichtbare Eintrag. Erreichbar bleiben beide — über die Befehlspalette und
#: über den Verlauf.
MENU_TWINS: Final[dict[str, str]] = {
    "create_brep_box": "create_box",
    "create_brep_cylinder": "create_cylinder",
    # *An Ebene teilen* ist *Teilen* mit ``pins = 0``. Zwei Menüzeilen, die
    # sich in einer Zahl unterscheiden und beide „teilen" heißen — der
    # Umschalter dafür stand schon im Dialog, es war das Feld *Passstifte*.
    "split_plane": "split_pinned",
}

#: Der Umschalter der beiden Rechenkerne. Einmal geschrieben und zweimal
#: eingetragen: Zwei wörtliche Kopien wären zwei Stellen, an denen derselbe
#: Satz beim nächsten Nachbessern auseinanderläuft.
_EXACT_TOGGLE: Final[tuple[TranslatableText, TranslatableText]] = (
    _("Exakter Körper (B-Rep) — echte Flächen und Kanten"),
    _(
        "Rechnet im exakten Kern statt als Netz: STEP-Export und spätere "
        "Verrundungen bleiben möglich. Netz-Feinheiten wie Verankerung oder "
        "Segmentzahl entfallen."
    ),
)

#: Der Umschalter, mit dem der Dialog des sichtbaren Zwillings auf den
#: versteckten wechselt — und die Erklärung dazu.
#:
#: **Nicht jedes Paar braucht einen.** Die Tabelle stand lange nicht hier,
#: sondern als fest eingebaute Zeichenkette „Exakter Körper (B-Rep)" in der
#: Oberfläche und als „(Umschalter „Exakt")" im Menüweg. Damit ließ sich
#: `MENU_TWINS` für nichts anderes benutzen als für die zwei Rechenkerne: Ein
#: drittes Paar hätte einen Haken bekommen, der von einem exakten Körper
#: spricht, den es nicht gibt.
#:
#: Wer hier fehlt, hat keinen eigenen Umschalter. Sein Weg ist ein Wert im
#: Dialog des Partners — bei ``split_plane`` die Null im Feld *Passstifte* —,
#: und erreichbar bleibt er über Befehlspalette und Verlauf.
TWIN_TOGGLES: Final[dict[str, tuple[TranslatableText, TranslatableText]]] = {
    "create_brep_box": _EXACT_TOGGLE,
    "create_brep_cylinder": _EXACT_TOGGLE,
}


#: Wie eine Merkmalsart heißt, wenn sie jemand liest. Im erzeugten
#: Referenzteil stand „Features: face, hole" — die Schlüssel, mit denen
#: ``applies_to`` rechnet, in einem deutschen Handbuch.
FEATURE_TITLES: Final[dict[str, TranslatableText]] = {
    "hole": _("Bohrung"),
    "face": _("Fläche"),
    "edge_loop": _("Offene Kante"),
    "pin": _("Zapfen"),
    "thread": _("Gewinde"),
}

_NAME_PATTERN: Final = re.compile(r"^[a-z][a-z0-9_]*$")

#: ``produces=VARIABLE``: so viele Objekte heraus wie hinein.
VARIABLE: Final = -1


@dataclass(frozen=True, slots=True)
class OperationSpec:
    """Alles, was über eine Operation bekannt ist. Die eine Quelle für alle
    Oberflächen.
    """

    name: str
    title: TranslatableText | str
    category: str
    params: type[BaseParams]
    fn: OpFn
    reversible: bool = True
    consumes: int = 1
    """How many objects the operation takes. Zero means any number."""
    produces: int = 1
    """How many it returns. ``VARIABLE`` means as many as it took — for
    operations like arranging, which change every object and create none."""
    applies_to: tuple[str, ...] = ()
    """Merkmalsarten, für die sich diese Operation anbietet — steuert das Kontextmenü."""
    requires_kind: str = ""
    """Bauart, die die Eingabe haben muss — ``"brep"`` oder leer für beides.

    Die fünf Operationen des exakten Kerns können mit einem Netz nichts
    anfangen und sagen das seit je in einem guten Satz. Nur kam er zu spät:
    das Menü fragte allein, *wie viele* Objekte gewählt sind, nie welcher Art
    sie sind — also war „Verrunden" bei einem Netz anklickbar, und der Nutzer
    erfuhr erst nach dem ausgefüllten Dialog, dass es hier nie ging.

    Deklariert statt in der Oberfläche aufgezählt, denn eine Liste in der
    Oberfläche wäre beim nächsten Zuwachs des exakten Kerns unvollständig —
    und dieselbe Auskunft braucht auch der Agent (§10, Leitprinzip 3)."""
    whole_scene: bool = False
    """Works on every object at once — see :attr:`takes_whole_scene`."""
    produces_from: str | None = None
    """The parameter that says how many objects come out, for a variable count.

    The stack hands out object ids before anything runs (§11), so an operation
    that makes a number of bodies has to say where that number is written down.
    Duplicating names its ``count``; everything else leaves this empty and the
    count follows from :attr:`produces`."""
    touches_features: bool = False
    deterministic: bool = True
    shortcut: str | None = None
    icon: str = ""
    """Name des Symbols, unter dem die Oberfläche es findet (``app/ui/icons.py``).

    Leer heißt: noch keines. Der Konsistenztest führt dazu eine Ausnahmeliste,
    die mit P15 leer wird — bis dahin ist ein Menüeintrag ohne Symbol reiner
    Text, und reiner Text ist bei einundsiebzig Einträgen schwer zu finden."""
    doc: TranslatableText | str = ""
    caveat: TranslatableText | str = ""
    """Wann man diese Operation *nicht* nehmen sollte — und was stattdessen.

    Getrennt von ``doc``, weil beides Verschiedenes tut: ``doc`` sagt, was
    passiert, ``caveat`` sagt, wann es die falsche Wahl ist. In einen Satz
    gepackt liest sich die Einschränkung wie ein Nachtrag und wird überlesen.

    Nur dort, wo es eine echte Grenze gibt. Ein Vorbehalt an jeder Operation
    wäre keiner mehr — dann steht neben jedem Menüeintrag eine Warnung, und
    die erste, die zählt, geht darin unter."""

    @property
    def requires_seed(self) -> bool:
        """Randomised procedures carry a stored seed (§11.3)."""
        return not self.deterministic

    @property
    def takes_whole_scene(self) -> bool:
        """Arbeitet diese Operation auf allen Objekten zugleich?

        Anordnen und die Kollisionsprüfung tun das: sie nehmen kein bestimmtes
        Objekt und geben alle zurück. Jede Oberfläche muss ihnen die ganze
        Szene hineingeben — eine Operation dieser Art ohne Eingaben läuft auf
        nichts und sieht kaputt aus, und genau so sah sie aus, bevor es diese
        Eigenschaft gab.

        Deklariert statt aus ``consumes == 0 and produces == VARIABLE``
        hergeleitet, was sie früher war: eine Baugruppe zu laden nimmt auch
        kein Objekt und gibt beliebig viele zurück — und will die Szene
        ungefähr so dringend hineingereicht bekommen wie das Wetter.
        """
        return self.whole_scene


class Registry:
    """Hält die Deklarationen. Eine Vorgabe-Instanz; Tests bauen ihre eigene."""

    def __init__(self) -> None:
        self._ops: dict[str, OperationSpec] = {}

    def register(self, spec: OperationSpec) -> OperationSpec:
        self._check(spec)
        self._ops[spec.name] = spec
        return spec

    def _check(self, spec: OperationSpec) -> None:
        if not _NAME_PATTERN.match(spec.name):
            raise InternalError(
                detail=f"operation name {spec.name!r} is not lower_snake_case",
                values={"op": spec.name},
            )
        if spec.name in self._ops:
            raise InternalError(
                detail=f"operation {spec.name!r} is registered twice",
                values={"op": spec.name},
            )
        if spec.category not in CATEGORIES:
            raise InternalError(
                detail=f"unknown category {spec.category!r}",
                values={"op": spec.name, "known": sorted(CATEGORIES)},
            )
        if not (isinstance(spec.params, type) and issubclass(spec.params, BaseParams)):
            raise InternalError(
                detail=f"{spec.name!r} needs a parameter set derived from BaseParams",
                values={"op": spec.name},
            )
        unknown = [kind for kind in spec.applies_to if kind not in FEATURE_KINDS]
        if unknown:
            raise InternalError(
                detail=f"{spec.name!r} applies to unknown feature kinds {unknown}",
                values={"op": spec.name, "known": list(FEATURE_KINDS)},
            )
        if spec.consumes < 0 or spec.produces < VARIABLE:
            raise InternalError(
                detail=f"{spec.name!r} declares a negative object count",
                values={"op": spec.name},
            )
        if spec.shortcut:
            taken = self.by_shortcut(spec.shortcut)
            if taken is not None:
                raise InternalError(
                    detail=f"shortcut {spec.shortcut!r} is already used by {taken.name!r}",
                    values={"op": spec.name, "shortcut": spec.shortcut},
                )

    def get(self, name: str) -> OperationSpec:
        if name not in self._ops:
            raise InternalError(
                detail=f"unknown operation {name!r}",
                values={"requested": name, "known": sorted(self._ops)},
            )
        return self._ops[name]

    def has(self, name: str) -> bool:
        return name in self._ops

    def all(self) -> tuple[OperationSpec, ...]:
        return tuple(self._ops[name] for name in sorted(self._ops))

    def by_category(self) -> dict[str, tuple[OperationSpec, ...]]:
        """Nach Kategorien gruppiert, **innerhalb nach dem Titel sortiert**.

        Leere Kategorien fallen weg. Sortiert wird nach dem, was auf dem
        Menüeintrag steht, nicht nach dem internen Namen: unter *Grundformen*
        stand sonst „Quader, Exakter Quader, Exakter Zylinder, Zylinder,
        OpenSCAD, Kugel", weil ``create_box``, ``create_brep_box``, … in dieser
        Reihenfolge stehen. Wer ein Menü aufklappt, sucht in den Titeln.
        """
        grouped: dict[str, list[OperationSpec]] = {name: [] for name in CATEGORIES}
        for spec in self.all():
            grouped[spec.category].append(spec)
        return {
            name: tuple(sorted(entries, key=lambda spec: sort_key(spec.title)))
            for name, entries in grouped.items()
            if entries
        }

    def for_feature(self, kind: str) -> tuple[OperationSpec, ...]:
        """Was das Kontextmenü an einem Merkmal anbietet (§18.5)."""
        return tuple(spec for spec in self.all() if kind in spec.applies_to)

    def by_shortcut(self, shortcut: str) -> OperationSpec | None:
        wanted = shortcut.casefold()
        for spec in self._ops.values():
            if spec.shortcut and spec.shortcut.casefold() == wanted:
                return spec
        return None

    def clear(self) -> None:
        self._ops.clear()


#: Das Register, das die Anwendung benutzt.
REGISTRY: Final = Registry()


def register_op(
    *,
    name: str,
    title: TranslatableText | str,
    category: str,
    params: type[BaseParams],
    reversible: bool = True,
    consumes: int = 1,
    produces: int = 1,
    applies_to: Iterable[str] = (),
    requires_kind: str = "",
    whole_scene: bool = False,
    produces_from: str | None = None,
    touches_features: bool = False,
    deterministic: bool = True,
    shortcut: str | None = None,
    icon: str = "",
    doc: TranslatableText | str = "",
    caveat: TranslatableText | str = "",
    registry: Registry | None = None,
) -> Callable[[OpFn], OpFn]:
    """Deklariert eine Operation. Die dekorierte Funktion bleibt aufrufbar
    wie zuvor.
    """

    def decorate(fn: OpFn) -> OpFn:
        (registry or REGISTRY).register(
            OperationSpec(
                name=name,
                title=title,
                category=category,
                params=params,
                fn=fn,
                reversible=reversible,
                consumes=consumes,
                produces=produces,
                applies_to=tuple(applies_to),
                requires_kind=requires_kind,
                whole_scene=whole_scene,
                produces_from=produces_from,
                touches_features=touches_features,
                deterministic=deterministic,
                shortcut=shortcut,
                icon=icon,
                doc=doc,
                caveat=caveat,
            )
        )
        return fn

    return decorate


@dataclass(frozen=True, slots=True)
class MenuSection:
    """Ein Menüabschnitt, abgeleitet aus einer Kategorie (§10)."""

    category: str
    title: TranslatableText | str
    entries: tuple[OperationSpec, ...] = field(default_factory=tuple)
