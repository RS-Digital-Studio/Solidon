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
    "drill_brep_hole": "drill_hole",
    # „Aushöhlen" und „Exakt aushöhlen" standen nebeneinander im Menü — und
    # zwar in **zwei verschiedenen** (``prepare`` gegen ``shaping``). Dort
    # liest „exakt" wie eine Qualitätsstufe („das andere ist also ungenau?"),
    # obwohl es den Rechenkern meint. Der Umschaltertext von ``create_box``
    # versprach exaktes Aushöhlen ohnehin schon, während es als eigener
    # Eintrag daneben stand.
    "shell_exact": "hollow_object",
}

#: Der Umschalter der beiden Rechenkerne. Einmal geschrieben und zweimal
#: eingetragen: Zwei wörtliche Kopien wären zwei Stellen, an denen derselbe
#: Satz beim nächsten Nachbessern auseinanderläuft.
_EXACT_TOGGLE: Final[tuple[TranslatableText, TranslatableText]] = (
    _("Exakter Körper (B-Rep) — echte Flächen und Kanten"),
    # Der Satz nannte den STEP-Export und „spätere Verrundungen"; die anderen
    # fünf Werkzeuge, die daran hängen, standen nirgends. Wer eine Tasche
    # schneiden wollte, hatte keinen Anlass, den Haken zu setzen — und fand
    # sie später grau, ohne Weg zurück. Sie werden deshalb aufgezählt: die
    # Entscheidung fällt hier, und was sie kostet, muss hier stehen.
    _(
        "Rechnet im exakten Kern statt als Netz. Nur damit lassen sich später "
        "Fase, Verrundung, Formschräge, Fläche versetzen, exaktes Aushöhlen "
        "und Tasche schneiden anwenden, und nur damit geht der STEP-Export. "
        "Netz-Feinheiten wie Verankerung oder Segmentzahl entfallen."
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
#: Wer hier fehlt, hat keinen eigenen Umschalter, und dann muss es einen
#: anderen Weg zu ihm geben: einen Wert im Dialog des Partners, der dasselbe
#: bewirkt. Gibt es den nicht, gehört das Paar nicht in diese Tabelle,
#: sondern in eine Migration — so ist es ``split_plane`` ergangen, das
#: *Teilen* mit null Stiften war und in Formatversion 11 darin aufgegangen
#: ist. Ein versteckter Zwilling ohne Umschalter wäre sonst eine zweite Zeile
#: in der Befehlspalette, die dasselbe tut wie die erste.
#: Der Umschalter des Aushöhlens — **ein eigener Text, und zwar zwingend.**
#:
#: ``_EXACT_TOGGLE`` zählt auf, was nur im exakten Kern geht, und nennt darin
#: „exaktes Aushöhlen". Am Haken des Aushöhlens gelesen ist das ein Verweis auf
#: sich selbst: Der Haken, der exakt aushöhlt, versprach, dass man damit später
#: exakt aushöhlen könne. Bei den drei Grundform-Zwillingen ist derselbe Satz
#: richtig — dort ist exaktes Aushöhlen eine **Folge**operation, die der Haken
#: erst möglich macht.
#:
#: Der Titel ist derselbe wie dort, und das ist Absicht: gleicher Satz,
#: gleicher Katalogschlüssel, eine Übersetzung. Nur die Erklärung ist eigen.
_HOLLOW_TOGGLE: Final[tuple[TranslatableText, TranslatableText]] = (
    _EXACT_TOGGLE[0],
    _(
        "Höhlt im exakten Kern aus und lässt den Körper exakt — Fase, "
        "Verrundung, Formschräge und der STEP-Export bleiben danach möglich. "
        "Verlangt einen exakten Eingangskörper: an einem Netz ist der Haken "
        "gesperrt und nennt den Grund. Ohne ihn wird als Netz gerechnet, und "
        "der Körper ist danach ein Netz."
    ),
)

TWIN_TOGGLES: Final[dict[str, tuple[TranslatableText, TranslatableText]]] = {
    "create_brep_box": _EXACT_TOGGLE,
    "create_brep_cylinder": _EXACT_TOGGLE,
    "drill_brep_hole": _EXACT_TOGGLE,
    "shell_exact": _HOLLOW_TOGGLE,
}


@dataclass(frozen=True)
class VariantGroup:
    """Ein Menüeintrag, der mehrere Operationen zu **einer Handlung**
    zusammenfasst — die Art wählt der Dialog.

    **Der Unterschied zu ``MENU_TWINS``, und warum es beides gibt.** Ein
    Zwillingspaar ist dieselbe Handlung in zwei Rechenkernen: „Quader anlegen"
    heißt der Eintrag, und der Haken entscheidet nur, wie gerechnet wird. Der
    sichtbare Zwilling *ist* die Handlung, sein Titel stimmt für beide.

    Hier stimmt kein Mitgliedstitel für die Gruppe. Vier Wege, aus einer
    Grundform einen Körper zu machen — Extrudieren, Rotieren, Sweep, Loft —
    sind vier Handlungen mit gemeinsamem Anfang; „Extrudieren" über alle vier
    zu schreiben wäre falsch, und die anderen drei darunter zu verstecken
    wäre es auch. Der Gruppentitel gehört deshalb **keiner** Operation, und
    genau das trägt ``MENU_TWINS`` nicht.

    **Im Verlauf steht weiter die Operation**, nicht die Gruppe: Wer
    extrudiert hat, liest „Extrudieren". Der Gruppentitel ist ein Weg zum
    Dialog und kein Name für ein Ergebnis — dieselbe Trennung, die
    ``MENU_TWINS`` zwischen Bedienung und Register zieht.

    Das Vorbild für einen Menüeintrag ohne eigene Operation steht daneben:
    *Automatisch teilen* ist ein Ablauf über mehreren Operationen und hat
    schon heute keinen Registereintrag.
    """

    title: TranslatableText
    """Was im Menü steht. Mit Auslassungspunkten, weil ein Dialog folgt."""

    doc: TranslatableText
    """Der Satz für Statuszeile und Tooltip — er muss die Gruppe erklären,
    nicht eine ihrer Arten."""

    choice: TranslatableText
    """Die Beschriftung der Auswahl im Dialog."""

    members: tuple[str, ...]
    """Die Operationen, in der Reihenfolge der Auswahl. Die erste ist die
    Vorgabe und bestimmt, welcher Dialog zuerst steht."""


#: Die zusammengefassten Handlungen. Ihre Mitglieder bekommen **keinen**
#: eigenen Menüeintrag — erreichbar bleiben sie über Befehlspalette und
#: Verlauf, wie die versteckten Zwillinge auch.
VARIANT_GROUPS: Final[tuple[VariantGroup, ...]] = (
    VariantGroup(
        title=_("Aus Skizze erzeugen …"),
        doc=_(
            "Aus einer Grundform oder einer gezeichneten Skizze einen Körper "
            "machen — hochziehen, um eine Achse drehen, an einem Bogen "
            "entlangführen oder zwischen zwei Größen überblenden. Die Art "
            "steht im Dialog, die Grundform ist für alle dieselbe."
        ),
        choice=_("Art"),
        members=("sketch_extrude", "sketch_revolve", "sketch_sweep", "sketch_loft"),
    ),
)


def variant_members() -> frozenset[str]:
    """Jede Operation, die in einer Variantengruppe steckt.

    Der Menüaufbau überspringt sie — dieselbe Rolle, die ``MENU_TWINS`` für
    die versteckten Zwillinge spielt.
    """
    return frozenset(name for group in VARIANT_GROUPS for name in group.members)


def group_for_variant(name: str) -> VariantGroup | None:
    """Die Gruppe, zu der diese Operation gehört — oder ``None``."""
    for group in VARIANT_GROUPS:
        if name in group.members:
            return group
    return None


#: Wie eine Merkmalsart heißt, wenn sie jemand liest. Im erzeugten
#: Referenzteil stand „Features: face, hole" — die Schlüssel, mit denen
#: ``applies_to`` rechnet, in einem deutschen Handbuch.
FEATURE_TITLES: Final[dict[str, TranslatableText]] = {
    "hole": _("Bohrung"),
    "face": _("Fläche"),
    "edge_loop": _("Offene Kante"),
    "pin": _("Zapfen"),
    "cone": _("Kegel"),
    "thread": _("Gewinde"),
    "fillet": _("Verrundung"),
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
    """Wie viele Objekte die Operation nimmt. Null heißt beliebig viele."""
    produces: int = 1
    """Wie viele sie zurückgibt. ``VARIABLE`` heißt so viele wie hineingegeben —
    für Operationen wie das Anordnen, die jedes Objekt ändern und keines
    erzeugen."""
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
    """Arbeitet auf allen Objekten zugleich — siehe :attr:`takes_whole_scene`."""
    produces_from: str | None = None
    """Der Parameter, der bei veränderlicher Anzahl sagt, wie viele Objekte
    herauskommen.

    Der Stapel vergibt Objekt-IDs, bevor irgendetwas läuft (§11), also muss
    eine Operation, die eine Anzahl von Körpern erzeugt, sagen, wo diese Zahl
    steht. Duplizieren nennt seinen ``count``; alles andere lässt dieses Feld
    leer, und die Anzahl folgt aus :attr:`produces`."""
    keeps_inputs: int = 0
    """Wie viele der ersten Ausgänge **dieselben Körper** sind wie die ersten
    Eingänge — Fortsetzungen, keine Neuschöpfungen.

    Der Stapel vergibt Kennungen, bevor etwas läuft, und für eine Operation
    mit festem :attr:`produces` weiß er nichts über die Zuordnung: Er vergab
    für jeden Ausgang eine frische. Bei *Vereinigen* heißt das, dass der
    Körper, den der Nutzer zuerst angeklickt hat, unter neuer Kennung
    weiterlebt — obwohl der Registertext ihm zusagt, er bleibe „mit seinem
    Namen und Material".

    **Die Folge war nicht nur eine tote Auswahl, sondern ein Datenfehler.**
    ``evaluate`` reicht die Merkmale des Vorgängers an seiner *Eingangs*-
    kennung weiter; bei frischer Ausgabekennung greift das ins Leere, und die
    Namen werden neu vergeben. Dieselbe physische Änderung ließ ``hole_1``
    danach auf ein **anderes Loch** zeigen — eine Senkung oder ein Gewinde,
    das daran hängt, sitzt am falschen Ort, ohne dass jemand etwas meldet
    (§21.2).

    Deklariert und nicht erraten, denn beides kommt vor: *Vereinigen*,
    *Abziehen*, *Schneiden*, *Verschmelzen* und die beiden Deckel setzen ihren
    ersten Eingang fort (``keeps_inputs=1``); *Teilen* zerlegt ihn in zwei
    neue Hälften und lässt die Null stehen. Am Ergebnis erkennbar ist es
    daran, dass der Ausgang Namen und Material des Eingangs trägt — geprüft
    von ``tests/test_registry_consistency.py``."""
    touches_features: bool = False
    """Ob diese Operation Merkmale **einführt** — nicht nur weiterreicht.

    Gesetzt von den Baustein-Einsätzen, den Vorbereitungs-Ops und dem B-Rep-
    Kern: den drei Stellen, an denen Geometrie entsteht, die die Erkennung
    hinterher als neue Bohrung, Fläche oder Verrundung findet.

    Gelesen von ``scene.evaluate._with_features``: Nur dort bekommt ein neu
    erkanntes Merkmal den Schritt eingetragen, aus dem es stammt (§21.2). Für
    ``load`` oder *Dreiecke verringern* gilt das ausdrücklich nicht — dort ist
    „neu erkannt" kein Beleg dafür, dass etwas entstanden ist.
    """
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
        """Zufallsprozeduren führen einen gespeicherten Startwert (§11.3)."""
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

    def remove(self, name: str) -> None:
        """Nimmt eine Operation zurück — für das Ersetzen eines Rezepts.

        ``register_one`` bindet den ``PartSpec`` als Vorgabewert seiner
        ``run``-Funktion; ein neuer Katalogeintrag allein ändert die Rechnung
        also nicht (gemessen am 26.08.2026: ein ersetzter Spec rechnete mit
        dem alten Stand weiter). Wer einen Baustein ersetzt, meldet die
        Operation ab und registriert sie neu. Ein unbekannter Name ist kein
        Fehler — zurücknehmen ist idempotent.
        """
        self._ops.pop(name, None)

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
        Kugel", weil ``create_box``, ``create_brep_box``, … in dieser
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
    keeps_inputs: int = 0,
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
                keeps_inputs=keeps_inputs,
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
