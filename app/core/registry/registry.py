"""Das Register der Operationen (Bauplan §10).

Eine Operation wird genau einmal deklariert; Menü, Kontextmenü, Palette,
Kommandozeile, Agenten-Werkzeugschema und Dokumentation entstehen aus dieser
Deklaration (§1, Leitprinzip 3). Eine unvollständige Registrierung scheitert
hier, beim Import, nicht später in einer Oberfläche.
"""

from __future__ import annotations

import functools
import importlib.util
import re
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final, get_args

from app.core.errors import InternalError
from app.core.types import BaseParams, FeatureKind, OpFn
from app.i18n import TranslatableText, _, sort_key

FEATURE_KINDS: Final[tuple[str, ...]] = get_args(FeatureKind)

#: Zustände, die eine Operation vom Körper verlangen kann (``requires_body``).
#: ``open`` heißt nicht wasserdicht, ``parts`` mehr als ein zusammenhängendes
#: Stück, ``cavity`` ein Hohlraum — als Merkmal ``void`` erkannt oder von
#: *Aushöhlen* eingetragen. Was hier nicht steht, prüft die Operation selbst
#: beim Rechnen; die Oberfläche fragt nur nach diesen dreien, weil sie sich
#: ohne Rechnung beantworten lassen.
BODY_REQUIREMENTS: Final[tuple[str, ...]] = ("open", "parts", "cavity")

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
    # **Nicht mehr „Bohrungen“.** Unter dieser Kategorie stehen seit dem
    # 03.09.2026 auch *Merkmal verschieben* und *Merkmal entfernen*, und die
    # gelten ebenso für einen Zapfen. Wer einen Zapfen versetzen will, sucht
    # nicht unter „Bohrungen“ — der Name war zu eng, der Ort ist richtig:
    # Alle Einträge darunter handeln von einem erkannten Merkmal.
    #
    # Der Schlüssel bleibt ``holes``. Ihn umzubenennen wäre eine Migration in
    # jeder bestehenden Projektdatei wert, und der sichtbare Titel löst den
    # Fall vollständig (Vorschlag 3d-druck-d4, gemessen: neun Zeilen statt
    # zwölf, damit drei unter der Grenze aus ``test_interface_limits``).
    "holes": _("Merkmale"),
    "parts": _("Bausteine"),
    # Nicht „Druckvorbereitung": Diese Kategorie steht als Untermenü unter der
    # Gruppe *Vorbereiten*, und zwei Ebenen, die fast dasselbe Wort tragen,
    # sagen zusammen weniger als eine. Der Name nennt jetzt, wofür man
    # hierherkommt — teilen, aushöhlen, ein Maß anpassen.
    "prepare": _("Teilen und Anpassen"),
    "import": _("Import"),
    "export": _("Export"),
    "colour": _("Filament"),
    "label": _("Beschriftung"),
    "surface": _("Oberfläche"),
    # „Netz" allein ist für den Kunden ohne CAD-Kenntnisse kein Wort; der
    # Name sagt, was die meisten Einträge darunter tun (Review 02.09.2026).
    # Dazu stehen hier die zwei Umwandlungen zwischen Netz und echten Flächen:
    # *Flächenbearbeitung beenden* und *In Flächen und Kanten umwandeln* (P4.0).
    "mesh": _("Netz glätten und vereinfachen"),
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
#:
#: **Seit dem 11.09.2026 ist eine Gruppe nicht mehr zwingend ein Menü.** Die
#: Handlungen an einer Auswahl stehen rechts im Fenster (Konzept „Ein Ort für
#: die Auswahl"), und dieselben Einträge noch einmal in der Leiste waren die
#: Liste zum Absuchen, die §2.6 nicht will (Robert: „da wir die operationen
#: rechts im auswahlpanel haben brauchen wir es nicht auch noch zusätzlich
#: oben in der menüleiste"). Welche Gruppen dort wohnen, sagt
#: :data:`PANEL_CATEGORIES`; die Gruppe bleibt als **Einteilung** — Panel,
#: Kontextmenü und der Wegweiser des Chats gliedern weiter nach ihr.
#:
#: Die Bausteine haben kein eigenes Menü mehr: Die Kacheln stehen im Katalog,
#: und was von der Kategorie übrig war — zwei Operationen, die einen Deckel
#: bauen —, gehört zum Erzeugen. Dort steht auch der Katalog selbst.
MENU_GROUPS: Final[tuple[tuple[TranslatableText, tuple[str, ...]], ...]] = (
    (_("Objekt"), ("scene",)),
    (_("Erzeugen"), ("primitive", "import", "sketch", "label", "parts")),
    (_("Ändern"), ("boolean", "transform", "shaping", "holes", "surface", "mesh", "repair")),
    (_("Vorbereiten"), ("prepare", "colour")),
)

#: Die Kategorien, deren Handlungen **rechts im Fenster** stehen und nicht in
#: der Menüleiste: alles, was einer Auswahl gilt. Eine Gruppe aus
#: :data:`MENU_GROUPS`, deren Kategorien alle hier stehen, bekommt kein Menü;
#: ihre Aktionen bleiben am Fenster, damit Kürzel und Befehlspalette weiter
#: greifen. Was hier **nicht** steht, braucht keine Auswahl — Grundkörper,
#: Skizzen, Importe, Beschriftungen — oder ist ein Baustein und steht damit
#: unter *Erzeugen*.
PANEL_CATEGORIES: Final[frozenset[str]] = frozenset(
    {
        "scene",
        "boolean",
        "transform",
        "shaping",
        "holes",
        "surface",
        "mesh",
        "repair",
        "prepare",
        "colour",
    }
)


def in_the_menu_bar(category: str) -> bool:
    """Ob die Gruppe dieser Kategorie ein Menü in der Leiste hat.

    Eine Gruppe steht in der Leiste, solange **eine** ihrer Kategorien nicht
    im Panel wohnt; eine Kategorie, die :data:`MENU_GROUPS` nicht kennt,
    bekommt ihr eigenes Menü — sie soll auftauchen und nicht verschwinden.
    """
    for _title, categories in MENU_GROUPS:
        if category in categories:
            return any(name not in PANEL_CATEGORIES for name in categories)
    return True


def needed_inputs(spec: OperationSpec) -> int:
    """Wie viele Objekte diese Operation mindestens braucht.

    Oberfläche, Agentenschema, Verlauf und Auswertung lesen denselben Vertrag.
    Bei fester Stelligkeit ist es ``consumes``; bei ``VARIABLE`` die
    ausdrückliche Untergrenze.
    """
    return spec.minimum_inputs if spec.consumes == VARIABLE else spec.consumes


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


#: Was die Probe (:func:`probe_exact_kernel`) ergeben hat — oder noch nichts.
_KERNEL_PROBED: bool | None = None


def probe_exact_kernel() -> bool:
    """Den exakten Kern wirklich laden und die Antwort merken.

    Dieselbe Frage wie ``brep.kernel.available`` — und absichtlich nicht
    dessen Aufruf: Eine Kante ``registry → brep``, auch träge, schließt für
    mypy den Kreis über ``scene.history`` (gemessen am 21.09.2026: „Cannot
    determine type of REGISTRY" an drei Stellen). Der Weg, die zwei Proben
    zu einer zu machen, führt andersherum — ``brep`` importiert das Register
    ohnehin, ``kernel.available`` kann hierher zeigen (``zwillinge.md``).
    Eine kompilierte Erweiterung scheitert auf mehr Arten als mit
    ``ImportError``.

    Gerufen vom Ladebildschirm hinter dem Fenster (``app.ui.app._KernelProbe``)
    — im Arbeiter, denn OpenCASCADE sind 30 native Module und 0,4 s.
    """
    global _KERNEL_PROBED
    if not _kernel_is_installed():
        _KERNEL_PROBED = False
        return False
    try:
        import OCP.BRepPrimAPI  # noqa: F401
    except Exception:
        _KERNEL_PROBED = False
        return False
    _KERNEL_PROBED = True
    return True


def _kernel_is_installed() -> bool:
    """Ob das Paket ``OCP`` auf dem Suchpfad liegt — ohne es zu laden.

    Ein Finder auf ``sys.meta_path`` darf auf die Frage auch mit einer
    Ausnahme antworten statt mit ``None`` (ein eingefrorenes Paket, eine
    kaputte ``.pth``, die Sperre eines Tests) — und die Frage „ist der Kern
    da?" hat darauf nur eine richtige Antwort: nein.
    """
    try:
        return importlib.util.find_spec("OCP") is not None
    except Exception:
        return False


def exact_kernel_present() -> bool:
    """Ist der exakte Kern auf dieser Maschine da? Gefragt beim Bau der Menüs.

    **Ohne Import, wo es geht.** Bis zum 21.09.2026 importierte die Frage
    OpenCASCADE selbst — 0,42 s in jedem ``MainWindow()``, auch in jedem
    Fenstertest (Review Fenster #7, Leistung B5). Die Antwort kommt jetzt in
    dieser Reihenfolge: Ist der Kern schon geladen, ja; hat die Probe des
    Ladebildschirms geantwortet, ihre Antwort; sonst genügt, dass
    ``find_spec`` das **Paket** findet (0,4 ms — die Suche nach einem
    Untermodul lüde das Paket und mit ihm 364 ms native Bibliotheken).
    Geladen wird es bei der ersten exakten Operation, und scheitert es dort,
    sagt ``kernel.require`` den einen klaren Satz statt eines
    Import-Stapelabzugs.
    """
    if "OCP.BRepPrimAPI" in sys.modules:
        return True
    if _KERNEL_PROBED is not None:
        return _KERNEL_PROBED
    return _kernel_is_installed()


#: Die sechs Grundkörper, je als Netz und exakt — dieselbe Handlung in zwei Rechenkernen.
PRIMITIVE_TWINS: Final[tuple[tuple[str, str], ...]] = (
    ("create_box", "create_brep_box"),
    ("create_cylinder", "create_brep_cylinder"),
    ("create_cone", "create_brep_cone"),
    ("create_sphere", "create_brep_sphere"),
    ("create_torus", "create_brep_torus"),
    ("create_tube", "create_brep_tube"),
)


@functools.cache
def menu_twins() -> dict[str, str]:
    """Wer von einem Paar versteckt ist, hängt an der Maschine (P2.8).

    **Neue Grundkörper entstehen exakt** (Konzept §10.1, Entscheidung 4 vom
    17.09.2026: die vier Kernwahl-Haken fallen): Sichtbar ist der exakte
    Erzeuger, versteckt der Netz-Zwilling — erreichbar über die Befehlspalette
    und über den Verlauf, und gespeicherte Schritte behalten ihren Namen. Ohne
    den exakten Kern bleibt der Netz-Erzeuger sichtbar: ein erklärter
    verfügbarer Weg, kein stilles Scheitern. **Bearbeitungen** haben keinen
    Haken mehr, sondern eine Weiche: *Bohrung setzen* und *Aushöhlen* fragen
    die Körperart ihres Eingangs (``prepare_ops.drill_hole``,
    ``hollow_object``); ihre exakten Zwillinge bleiben für alte Projekte und
    den Verlauf registriert und versteckt.
    """
    exact = exact_kernel_present()
    twins = {(mesh if exact else brep): (brep if exact else mesh) for mesh, brep in PRIMITIVE_TWINS}
    twins["drill_brep_hole"] = "drill_hole"
    # „Aushöhlen" und „Exakt aushöhlen" standen nebeneinander im Menü — und
    # zwar in **zwei verschiedenen** (``prepare`` gegen ``shaping``). Dort
    # liest „exakt" wie eine Qualitätsstufe („das andere ist also ungenau?"),
    # obwohl es den Rechenkern meint.
    twins["shell_exact"] = "hollow_object"
    return twins


if TYPE_CHECKING:
    #: Zusammengelegte Menü-Zwillinge: dieselbe Handlung in zwei Rechenkernen.
    #:
    #: Zwei technische Rechenwege waren zwei Menüeinträge für einen Quader —
    #: gegen das Hausprinzip „eine Operation je Handlung, nicht je Variante".
    #: Die Ops bleiben im Register getrennt (Verlauf und Provenienz brauchen
    #: das); zusammengelegt ist nur die Bedienung. Schlüssel ist der versteckte
    #: Zwilling, Wert der sichtbare Eintrag — welcher das ist, sagt
    #: :func:`menu_twins`. Erreichbar bleiben beide — über die Befehlspalette
    #: und über den Verlauf (``History.change_kernel``).
    #:
    #: **Faul, weil die Antwort OpenCASCADE lädt** (Review, 21.09.2026): 334
    #: Module und 0,43 s bei jedem Import des Registers — Kommandozeile,
    #: Werkzeuge, jeder Testprozess. Gebraucht wird sie erst am Menü; das
    #: Modul liefert den Namen deshalb über ``__getattr__`` beim ersten Zugriff.
    MENU_TWINS: dict[str, str]


def __getattr__(name: str) -> Any:
    if name == "MENU_TWINS":
        return menu_twins()
    raise AttributeError(name)


def exact_names() -> frozenset[str]:
    """Die Namen der Zwillinge, die im exakten Kern rechnen — eine Antwort für Verlauf,
    Fenster und Verlaufssatz (``zwillinge.md``: dreimal gebildet war dreimal anders)."""
    found = {brep for _mesh, brep in PRIMITIVE_TWINS}
    for pair in menu_twins().items():
        found.update(
            name
            for name in pair
            if REGISTRY.has(name) and REGISTRY.get(name).requires_kind == "brep"
        )
    return frozenset(found)


#: Der Weg zum versteckten Zwilling, je Paar — für Menüweg, Handbuch und Agent.
#:
#: **Die Haken sind gefallen** (P2.8, Konzept §10.1). Bis dahin stand im
#: Dialog des sichtbaren Zwillings ein Umschalter „Flächen und Kanten später
#: bearbeiten“ mit einer Erklärung je Paar (``TWIN_TOGGLES``). Ein Erzeuger
#: entsteht heute exakt, wo der Kern da ist; sein Netz-Zwilling wird über das
#: Kontextmenü des Verlaufsschritts gewählt. Eine Bearbeitung fragt die
#: Körperart ihres Eingangs; ihr
#: Zwilling ist über denselben Dialog erreichbar, weil der Körper entscheidet.
#: Und im Verlauf stellt ``History.change_kernel`` einen Schritt weiterhin auf
#: seinen Zwilling um — über das Kontextmenü des Schritts, nicht über einen
#: Haken im Dialog.
TWIN_WAYS: Final[dict[str, TranslatableText]] = {
    "primitive": _("über das Kontextmenü des Verlaufsschritts"),
    "edit": _("im selben Dialog — der Körper entscheidet"),
}


def kernel_twin_of(name: str) -> str | None:
    """Der Zwilling im anderen Rechenkern — in beide Richtungen, oder ``None``."""
    twins = menu_twins()
    if name in twins:
        return twins[name]
    return next((hidden for hidden, shown in twins.items() if shown == name), None)


def kernel_switch_label(name: str) -> TranslatableText | None:
    """Der Satz im Kontextmenü des Verlaufs, der den Schritt in den anderen Kern stellt.

    Genannt wird der Nutzen, nie der Rechenkern (``test_wording``): Wer am
    Netz steht, bekommt „Mit echten Flächen und Kanten rechnen“, wer exakt
    steht, „Als Dreiecksmodell rechnen“.

    **Nur an einem Grundkörper.** Bohren und Aushöhlen entscheidet der Körper
    selbst (die Weiche in ``prepare_ops``); ein Wechsel am Schritt liefe dort
    ins Leere — gemessen im Review vom 21.09.2026: *Aushöhlen* am Netz auf
    „exakt“ gestellt hielt die Kette an, eine gespeicherte exakte Bohrung
    „als Dreiecksmodell“ blieb exakt. Und in den exakten Kern nur, wenn er
    auf dieser Maschine da ist — sonst kein Eintrag statt einer Absage nach
    dem Klick (Regel 19).
    """
    primitives = {name for pair in PRIMITIVE_TWINS for name in pair}
    if name not in primitives:
        return None
    twin = kernel_twin_of(name)
    if twin is None:
        return None
    if twin in exact_names():
        if not exact_kernel_present():
            return None
        return _("Mit echten Flächen und Kanten rechnen")
    return _("Als Dreiecksmodell rechnen")


def twin_way(hidden: str) -> TranslatableText:
    """Wie der versteckte Zwilling erreicht wird: Erzeuger über die Palette, Bearbeitung
    über den Körper."""
    names = {mesh for mesh, _brep in PRIMITIVE_TWINS} | {brep for _mesh, brep in PRIMITIVE_TWINS}
    return TWIN_WAYS["primitive" if hidden in names else "edit"]


def shown_of_twins(specs: Iterable[OperationSpec]) -> tuple[OperationSpec, ...]:
    """Eine Menge auf ihre sichtbaren Vertreter — **die Menge ist der Bezug**.

    Ein Zwillingspaar aus :data:`MENU_TWINS` ist dieselbe Handlung in zwei
    Rechenkernen; sichtbar ist der eine, der andere steht über den Umschalter
    in dessen Dialog. Wo eine Oberfläche eine Auswahl anbietet, gehört deshalb
    nur der sichtbare hinein.

    **Weggelassen wird nur, wenn der Partner tatsächlich dabei ist.** Ein
    Zwilling, dessen Partner in *dieser* Menge gar nicht vorkommt, wäre sonst
    spurlos weg statt zusammengelegt — die Handlung fehlte dann ganz, statt
    unter einem Titel zu stehen.

    **Warum es diese Funktion gibt.** Die Regel stand am 07.09.2026 dreimal in
    zwei Fassungen: bedingt in ``ObjectTree.operations_for_feature``, unbedingt
    (``spec.name not in MENU_TWINS``) in ``operations_for_object`` und in
    ``selection_operations``. Zwei der drei Stellen lagen in derselben Datei,
    neununddreißig Zeilen auseinander, und die bedingte trug die Begründung,
    warum die andere falsch sein kann, im eigenen Docstring. Dass heute keine
    Handlung verschwindet, ist gemessen und nicht gebaut: Bei
    ``create_brep_box`` und ``create_brep_cylinder`` fehlen *beide* Seiten in
    einer Auswahlmenge, weil Erzeuger ``consumes = 0`` haben; bei
    ``drill_brep_hole`` und ``shell_exact`` ist der sichtbare Partner in
    derselben Klasse und damit dabei. Ein fünftes Paar mit Eingang, dessen
    sichtbarer Partner in der jeweiligen Menge fehlt, fiele in den unbedingten
    Fassungen ohne Spur heraus.

    Der Kern gibt weiterhin die Rohmenge und entscheidet nichts über die
    Darstellung (``registry.surfaces.context_menu``); diese Funktion ist das
    Werkzeug dafür und wohnt bei der Tabelle, über die sie eine Aussage macht.
    """
    offered = tuple(specs)
    names = {spec.name for spec in offered}
    twins = menu_twins()
    return tuple(spec for spec in offered if twins.get(spec.name) not in names)


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
            "entlangführen, zwischen zwei Größen überblenden — oder mit "
            "denselben Werkzeugen aus einem vorhandenen Körper schneiden: als "
            "Tasche, Ringnut, Kanal oder Übergang. Die Art steht im Dialog, "
            "die Grundform ist für alle dieselbe."
        ),
        choice=_("Art"),
        # **``sketch_pocket`` gehört dazu, seit dem 03.09.2026.** Der
        # Umschalter kannte vier Arten und das Abziehen nicht — wer hochgezogen
        # hatte und eine Tasche wollte, fand im Dialog keinen Weg dorthin und
        # musste zurück zur Auswahl (Robert: „man zeichnet zieht kann unten
        # aber nicht mehr abziehen wählen").
        #
        # Sie war die erste der Gruppe mit einem **Eingang**: `consumes=1`,
        # `applies_to=("face",)`. Ein Umschalter, dessen Ziel eine Bedingung
        # hat, fragt sie vorher — sonst führt er in eine Auswertung, die
        # anhält (`grenzen.md`, „Ein Zwilling, der eine Bedingung hat, fragt
        # sie — vorher"). Der Dialog sperrt den Eintrag deshalb, solange kein
        # Körper gewählt ist, und nennt den Grund.
        #
        # **Und die drei Schnitte mit Werkzeug gehören seit P6.5 dazu**, je
        # direkt hinter ihrem Erzeuger (Konzept §10: „Revolve-Cut wird kein
        # zweiter Eintrag, sondern ein Feld im Dialog"). Sie haben einen
        # Eingang wie die Tasche und werden ohne Körper gleich gesperrt.
        #
        # **``sketch_join`` steht neben dem Hochziehen** (23.09.2026,
        # Bedienabnahme Zeichnen E4): dieselbe Handlung mit dem gewählten
        # Körper als Ziel. Wie die Tasche hat es einen Eingang und fragt ihn im
        # Umschalter vorher.
        members=(
            "sketch_extrude",
            "sketch_join",
            "sketch_pocket",
            "sketch_revolve",
            "sketch_revolve_cut",
            "sketch_sweep",
            "sketch_sweep_cut",
            "sketch_loft",
            "sketch_loft_cut",
        ),
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
    "void": _("Lufteinschluss"),
    "slot": _("Langloch"),
    "curved_face": _("Gerundete Seite"),
    "pattern": _("Muster"),
    # Kuppel oder Pfanne, je nach Richtung — in der Faktenzeile steht die
    # Art, und die heißt in den Absagen des Auswahlfensters genauso.
    "sphere": _("Kugelfläche"),
    # Wulst oder Kehle, je nach Richtung, wie bei der Kugel. Fehlte bis zur
    # Durchsicht 0.5.0, und die Ortsangabe für den Agenten schrieb
    # „…, torus, …" in einen deutschen Satz.
    "torus": _("Ringfläche"),
}

_NAME_PATTERN: Final = re.compile(r"^[a-z][a-z0-9_]*$")

#: ``produces=VARIABLE``: so viele Objekte heraus wie hinein.
VARIABLE: Final = -1

#: Was eine Operation ändert, wenn sie die Geometrie **nicht** anfasst (§18.7).
#:
#: Die Live-Vorschau sagt über einer leeren Differenz „am Volumen ändert sich
#: nichts". Das ist wahr und für eine Prüfung ein Füllsatz: *Überschneidungen
#: prüfen* ändert **nie** etwas, ihr Ergebnis steht im Prüfbericht — der Satz
#: beschreibt dann nicht die Operation, sondern nur, was in der Differenz
#: fehlt. Dasselbe beim Umbenennen: Da ändert sich sehr wohl etwas, nur eben
#: nicht die Form.
#:
#: Die Werte sind Lagen, keine Sätze. Der Satz gehört in die Oberfläche, wo
#: ``tr()`` steht; hier steht nur, welche Lage gilt — so bekommt auch der
#: Agent die Auskunft, und eine Lage ohne Eintrag fällt auf den allgemeinen
#: Satz zurück.
#:
#: ``report``
#:     Sie sieht nur nach. Eingänge kommen unverändert wieder heraus, das
#:     Ergebnis sind die Befunde. Ein drittes Prüfwerkzeug ist eine Zeile.
#: ``name``
#:     Sie ändert den Namen und sonst nichts.
#:
#: **Hier und nicht am ``@register_op``**, aus demselben Grund wie
#: :data:`MENU_TWINS`: Die Zuordnung gilt der *Bedienung* und nicht der
#: Rechnung — sie sagt, was die Oberfläche über eine leere Differenz sagen
#: soll. Gelesen wird sie über :attr:`OperationSpec.unchanged_effect`, also
#: wie jede andere Angabe der Deklaration; wandert sie eines Tages an den
#: Dekorator, ändert sich an den Lesern nichts.
UNCHANGED_EFFECT: Final[dict[str, str]] = {
    "check_collisions": "report",
    "check_join_path": "report",
    "rename_object": "name",
}


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
    """Feste Eingangszahl, null für Erzeuger, ``VARIABLE`` für variable Eingänge."""
    minimum_inputs: int = 0
    """Wie viele Objekte mindestens nötig sind, wenn ``consumes`` variabel ist.

    ``consumes=VARIABLE`` heißt „so viele, wie gewählt sind" — die Booleschen
    Operationen nehmen seit dem 06.09.2026 alle Körper auf einmal. Nur ist
    „alle" nicht „beliebig viele": Eine Vereinigung braucht zwei. Ohne diese
    Zahl wüsste das Menü nicht, wann es den Eintrag freigeben darf, und der
    Nutzer bekäme die Absage erst nach dem Klick (Regel 19).
    """
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
    result_kind: str = ""
    """Bauart, die das Ergebnis am **exakten** Eingang hat — ``"mesh"``, wenn
    die Operation aus einem exakten Körper ein Dreiecksmodell macht, sonst
    leer: Das Ergebnis behält die Bauart seines Eingangs.

    Neunzehn Operationen rechnen nur am Netz und vernetzen einen
    exakten Eingang dafür — Glätten, Reduzieren, Formen, Teilen, die
    Prägung, der Prüfkörper (*Text aufbringen* bleibt seit dem 22.09.2026
    exakt, ``brep.lettering``; *Drehdeckel erzeugen* seit dem 23.09.2026,
    ``geom.lid.exact_screw_neck``). Bis zum 22.09.2026 stand diese Auskunft an zwei
    Orten, die sich nicht kannten: in der Paritätstabelle von
    ``tests/test_exact_body_parity.py`` (``MESH``) und im Hauptfenster als
    „exakter Eingang vorhanden". Das Fenster braucht sie **vor** der
    Rechnung — nur eine Handlung, die den Körper umwandeln kann, muss mit
    Vorschau und Rückweg gezeigt werden (Regel 19, CAD-Konzept); eine, die ihn
    exakt lässt, läuft ohne Dialog. Deklariert, damit Fenster, Agent und
    Tabelle dieselbe Antwort lesen (§10, Leitprinzip 3);
    ``test_the_table_promises_no_more_and_no_less_than_the_register`` hält
    Register und Tabelle zusammen."""
    requires_body: str = ""
    """Was der Körper mitbringen muss, damit die Operation überhaupt etwas
    tun kann — einer der Werte aus :data:`BODY_REQUIREMENTS`, oder leer.

    Die Schwester von ``requires_kind``, eine Frage weiter: Nicht die Bauart
    (Netz oder exakt), sondern der Zustand. *Offene Fläche schließen* braucht
    eine offene Fläche, *In Einzelteile zerlegen* mehrere Teile, *Gitter
    füllen* einen Hohlraum. Gemessen am 13.09.2026 über alle Dialoge: Ohne
    die Angabe öffneten die drei an einem sauberen Quader einen Dialog,
    dessen Vorschau nur „Keine Vorschau: …" sagen konnte — die Sackgasse aus
    Regel 19, ein Fenster später. Mit ihr steht der Eintrag ausgegraut da,
    mit demselben Satz, den die Operation beim Übernehmen sagte."""
    whole_scene: bool = False
    """Arbeitet auf allen Objekten zugleich — siehe :attr:`takes_whole_scene`."""
    reads_other_bodies: bool = False
    """Liest an den eigenen Eingängen vorbei die übrigen Körper der Szene.

    ``orient_for_print`` tut das: Es dreht seine Eingänge und muss sie danach
    neu anordnen, ohne dabei in einen fremden Körper zu legen — der steht in
    ``ctx.scene``, und lesen darf es ihn (Regel 3). Über die Oberfläche
    bekommt es die ganze Szene und liest dann nichts Fremdes; ein
    **gespeicherter** Auftrag trägt aber die Teilmenge von damals, und für den
    gilt die Zeile. **Der
    Cache-Schlüssel weiß davon nichts**, denn ``operation_hash`` deckt die
    Hashes der *Eingänge*, und ein fremder Körper ist keiner: Verschiebt
    jemand ihn, bleibt der Schlüssel derselbe und das alte Ergebnis gilt
    weiter — der gedrehte Körper weicht einem Nachbarn aus, der längst
    woanders steht.

    Wer die Eigenschaft setzt, bekommt die Hashes **aller** Objekte in den
    Schlüssel gemischt (``evaluate._with_nested_context``). Dieselbe Pflicht
    wie bei den drei benannten Lesarten daneben, nur ohne Parameter, an dem
    sie hinge — hier wird nicht ein bestimmter Träger gelesen, sondern die
    Szene als Ganzes."""
    reads_process: bool = True
    """Liest Prozesswerte des Profils: Schichthöhe, Bahnbreite, Überhanggrenze
    oder was daraus folgt — Mindestwand, Überhangwinkel, kleinstes druckbares
    Volumen, kleinste Aufstandsfläche, Exporttoleranz, Schichtanalyse
    (``hashing._profile_parts``).

    Der Druckdialog setzt diese Werte (``profiles.for_process``), und mit
    ihnen im Schlüssel rechnete nach „Im Slicer öffnen" der ganze Verlauf neu —
    am Minigolf-Satz auch Einlesen und Kopieren, die keinen davon lesen
    (28.09.2026). ``False`` nimmt sie aus dem Schlüssel dieses Schritts.

    **Die Vorgabe ist sicher**: Ein falscher Treffer gäbe eine veraltete
    Geometrie zurück, und das ist schlimmer als eine langsame Rechnung.
    ``False`` steht nur, wo die Operation und alles, was sie aufruft,
    belegt keinen Prozesswert liest; ``tests/test_cache.py`` führt die Liste
    mit Beleg und lässt jede davon an einem Profil laufen, das beim Lesen
    eines Prozesswerts abbricht."""
    also_on_body: bool = False
    """Gilt auch ohne gewähltes Merkmal, am ganzen Körper.

    Eine Operation mit :attr:`applies_to` steht in der Auswahlkarte nur an
    einem Merkmal ihrer Art. Die *Formschräge* gilt beidem: an gewählten
    Flächen (P6.4) und, ohne Auswahl, an allen Wänden in Entformungsrichtung
    wie seit je. Ohne das Feld verschwände das Anstellen des ganzen Körpers
    aus der Karte, sobald die Flächenwahl dazukommt."""
    edges_on_mesh: bool = False
    """Die Operation liest ihre Kanten (``kind="edges"``) immer am **Netz**,
    auch an einem exakten Körper.

    *Wulst anlegen* tut das: Es vereinigt am tessellierten Körper und löst
    seine Schlüssel deshalb an dessen Zügen auf, nicht an der Topologie.
    Die Auswertung bindet ausdrücklich gewählte Kanten **vor** dem Cache am
    aktuellen Eingang (``scene.edge_binding``), und sie muss dafür dieselben
    Kanten sehen wie die Operation — sonst fragte sie nach Kanten, die die
    Operation nie bekommt. Ohne das Flag entscheidet die Bauart des Körpers:
    exakt an der Topologie, Netz an den Zügen."""
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
    leaves_inputs_unchanged: bool = False
    """Die Operation reicht ihre Eingänge unverändert durch und legt nur Neues daneben.

    *Stift für Bohrung* gibt den Träger zurück, wie er kam, *Objekt
    duplizieren* das Original. Eine fortgesetzte Kennung (:attr:`keeps_inputs`)
    sagt das nicht: *Vereinigen* setzt seinen ersten Eingang ebenfalls fort und
    baut ihn dabei um. Gelesen von ``history.discarded``: Wird alles Neue eines
    solchen Schritts später entfernt, wirkt er nicht mehr, auch wenn der Träger
    bleibt (S-20261006-2a0261)."""
    shapes_with_other_inputs: bool = False
    """Die Operation formt einen Körper, den sie unter seiner Kennung zurückgibt, mit einem anderen.

    *Gegenform einlassen* schneidet die Teile als Taschen in den Einsatz und
    gibt alle unter ihrer Kennung zurück. Gelesen von ``history.discarded``:
    Wird ein Teil danach entfernt, lebt es in der Tasche weiter, und was es
    gebaut hat, wirkt. Ohne das Feld gibt ein Schritt über mehrere Körper jeden
    für sich weiter (*Auf dem Bett anordnen*, gemeinsam verschieben,
    *Überschneidungen prüfen*): Ein Eingang lebt, solange sein gleichnamiger
    Ausgang lebt. **Lage ist keine Form** — dass ein entfernter Stift beim
    Anordnen Platz brauchte, lässt seine Schritte nicht weiterwirken."""
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
    leaves_separate_parts: bool = False
    """Die Operation legt gewollt ein eigenes, loses Teil neben ihren Träger.

    Gesetzt von den Baustein-Einsätzen, deren Baustein ``separate_from_host``
    trägt — gedruckte Schraube, gedruckte Mutter, separate Dichtung. Das ist
    die eine Quelle; hier wird sie nur durchgereicht, damit Auswertung und
    Assistentenprüfung die Operation fragen und keine Namensliste führen.

    Gelesen von ``scene.evaluate`` und ``agent.checks``: Nach so einem Schritt
    hat der Körper mehr Teile, und das ist kein Zerfall. Ob der **Träger**
    zerfallen ist — eine Senkung, die einen schmalen Streifen durchschneidet
    —, sagt die Operation selbst, denn nur sie weiß, welche Dreiecke Träger
    und welche Baustein sind (``knowledge.parts.ops``, ``feature.body_split``).
    """
    retriangulates: bool = False
    """Die Operation verteilt die Dreiecke neu und lässt die Form stehen — bis auf
    eine Abweichung, die sie selbst misst und meldet oder zusagt.

    *Kanten verfeinern* verschiebt keinen Punkt, *Dreiecke angleichen* bleibt
    in seiner zugesagten Schranke, *Dreiecke verringern* misst, wie weit die
    Fläche gewandert ist. Die Vorschau zeigt an ihnen das neue Netz und keine
    Volumendifferenz (``geom.difference.compare_scenes``, ``retriangulated``):
    Davor und danach sind zwei fast deckungsgleiche Häute, der schlimmste Fall
    jedes Booleschen Kerns, und die Antwort ist bekannt, bevor er rechnet.
    Gemessen in der Durchsicht 0.5.1 (RESTVERLAUF-04) am Spielwürfel aus
    ``F:\\3D Dateien``: *Kanten verfeinern* auf 0,05 mm stand über zehn
    Minuten in dieser Differenz, *Dreiecke verringern* auf 60 000 genau
    gerechnet 69 s — für eine Differenz von 0,4 mm³."""
    expected_triangles: Callable[[Any, Any], Any] | None = None
    """Die Vorabzählung der Operation: ``(Netz, Parameter)`` → wie viele
    Dreiecke herauskommen (``mesh_ops.TriangleEstimate``) — oder die Absage,
    die die Operation selbst gäbe, als ``ValidationError``.

    Gesetzt, wo das Ergebnis an der Dreieckszahl des Eingangs hängt: die drei
    teilenden Netzoperationen und *Dreiecke verringern*. Die grobe Vorschau
    rechnet auf einer verkleinerten Kopie, und deren Zahl ist nicht die des
    Kunden — am Spielbrett aus ``F:\\3D Dateien`` zählte das Original bei 1 mm
    11,97 Mio. Dreiecke (zu fein), die Kopie 7,8 Mio.: Die Vorschau rechnete,
    *Übernehmen* hielt danach an. Die Vorschau fragt deshalb diese Zählung am
    Original, bevor sie irgendetwas verkleinert. Dieselbe Funktion prüft in
    der Operation vor dem ersten Schnitt; eine Absage klingt an beiden Orten
    gleich und trägt dieselben Handlungen."""
    deterministic: bool = True
    cache_version: str = ""
    """Identität der geladenen Umsetzung, insbesondere des verwendeten Bausteinrezepts."""
    material_params: tuple[str, ...] = ()
    """Materialfelder, deren zusätzliche Profile Geometrie oder Befunde beeinflussen.

    Die Auswertung nimmt deren Kalibrierung mit dem aktuellen Druckprozess
    in den Cache-Schlüssel auf. Ein leeres Feld verwendet das Projektprofil.
    """
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
    def unchanged_effect(self) -> str:
        """Was sich ändert, wenn die Geometrie es nicht tut — sonst leer.

        Siehe :data:`UNCHANGED_EFFECT`. Die Live-Vorschau hängt daran ihren
        Satz auf: Eine Prüfung soll nicht sagen, dass sich am Volumen nichts
        ändert, sondern wo ihr Ergebnis steht.
        """
        return UNCHANGED_EFFECT.get(self.name, "")

    @property
    def takes_whole_scene(self) -> bool:
        """Arbeitet diese Operation auf allen Objekten zugleich?

        Anordnen, die Kollisionsprüfung und das druckoptimale Ausrichten tun
        das: Sie nehmen kein bestimmtes Objekt und geben alle zurück. Jede
        Oberfläche muss ihnen die ganze Szene hineingeben — eine Operation
        dieser Art ohne Eingaben läuft auf nichts und sieht kaputt aus, und
        genau so sah sie aus, bevor es diese Eigenschaft gab.

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
        material_fields = {entry.name for entry in spec.params.spec() if entry.kind == "material"}
        if len(set(spec.material_params)) != len(spec.material_params) or any(
            name not in material_fields for name in spec.material_params
        ):
            raise InternalError(
                detail=f"{spec.name!r} declares duplicate or unknown material profile parameters",
                values={"op": spec.name, "fields": spec.material_params},
            )
        unknown = [kind for kind in spec.applies_to if kind not in FEATURE_KINDS]
        unknown += [
            kind
            for entry in spec.params.spec()
            for kind in entry.feature_kinds
            if kind not in FEATURE_KINDS
        ]
        if unknown:
            raise InternalError(
                detail=f"{spec.name!r} applies to unknown feature kinds {unknown}",
                values={"op": spec.name, "known": list(FEATURE_KINDS)},
            )
        if spec.requires_body and spec.requires_body not in BODY_REQUIREMENTS:
            raise InternalError(
                detail=f"{spec.name!r} requires an unknown body state {spec.requires_body!r}",
                values={"op": spec.name, "known": list(BODY_REQUIREMENTS)},
            )
        if spec.consumes < VARIABLE or spec.produces < VARIABLE or spec.minimum_inputs < 0:
            raise InternalError(
                detail=f"{spec.name!r} declares a negative object count",
                values={"op": spec.name},
            )
        if spec.consumes != VARIABLE and spec.minimum_inputs:
            raise InternalError(
                detail=f"{spec.name!r} declares a minimum for a fixed input count",
                values={"op": spec.name},
            )
        # Beide Angaben sprechen über **den** Körper, den die Operation nimmt und
        # als denselben zurückgibt — ein Netz vorher, eines nachher.
        if (spec.retriangulates or spec.expected_triangles is not None) and (
            spec.consumes != 1 or spec.produces != 1
        ):
            raise InternalError(
                detail=f"{spec.name!r} counts or retriangulates without one body in and out",
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

    def replace_state(self, prepared: Registry) -> None:
        """Aktiviert einen vollständig vorbereiteten Registerstand.

        Der Zustand wurde bereits in einem isolierten Register validiert.
        Die Referenzübernahme ist der nicht erneut fehlbare Commit-Schritt für
        Rezeptdateien, nachdem deren vollständige Datei veröffentlicht ist.
        """

        self._ops = prepared._ops

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
    minimum_inputs: int = 0,
    produces: int = 1,
    applies_to: Iterable[str] = (),
    requires_kind: str = "",
    result_kind: str = "",
    requires_body: str = "",
    whole_scene: bool = False,
    reads_other_bodies: bool = False,
    reads_process: bool = True,
    also_on_body: bool = False,
    edges_on_mesh: bool = False,
    produces_from: str | None = None,
    keeps_inputs: int = 0,
    leaves_inputs_unchanged: bool = False,
    shapes_with_other_inputs: bool = False,
    touches_features: bool = False,
    leaves_separate_parts: bool = False,
    retriangulates: bool = False,
    expected_triangles: Callable[[Any, Any], Any] | None = None,
    deterministic: bool = True,
    cache_version: str = "",
    material_params: Iterable[str] = (),
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
                minimum_inputs=minimum_inputs,
                produces=produces,
                applies_to=tuple(applies_to),
                requires_kind=requires_kind,
                result_kind=result_kind,
                requires_body=requires_body,
                whole_scene=whole_scene,
                reads_other_bodies=reads_other_bodies,
                reads_process=reads_process,
                also_on_body=also_on_body,
                edges_on_mesh=edges_on_mesh,
                produces_from=produces_from,
                keeps_inputs=keeps_inputs,
                leaves_inputs_unchanged=leaves_inputs_unchanged,
                shapes_with_other_inputs=shapes_with_other_inputs,
                touches_features=touches_features,
                leaves_separate_parts=leaves_separate_parts,
                retriangulates=retriangulates,
                expected_triangles=expected_triangles,
                deterministic=deterministic,
                cache_version=cache_version,
                material_params=tuple(material_params),
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
