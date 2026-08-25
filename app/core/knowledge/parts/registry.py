"""Das Bausteinregister (Bauplan §24.1, §24.4).

Einmal deklariert, wie eine Operation: aus einer Deklaration kommen der
Katalogeintrag, der Parameterdialog, das ``find_part`` des Agenten und die
Dokumentation. Was hier fehlt, scheitert beim Import, nicht später in einer
Oberfläche.

Zwei Dinge trägt ein Baustein, die eine Operation nicht hat:

* **eine Version und einen Änderungsverlauf** (§24.4). Die Bibliothek ist Teil
  der Art, wie ein Projekt gerechnet wurde — eine Korrektur an ``heatset_m4``
  darf alte Projekte also nicht still anders nachrechnen; Leitprinzip 4 wäre
  gebrochen.
* **ob er Material hinzufügt oder wegnimmt**. Ein Schraubenloch ist eine Form
  zum Abziehen, eine Rippe eine zum Hinzufügen, und ``insert_part`` muss das
  wissen, ohne zu fragen.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from app.core.errors import InternalError
from app.core.types import BaseParams, HoleValues, PartFn, PartResult, Profile
from app.i18n import TranslatableText, _

BuildWithProfile = Callable[[BaseParams, Profile | None], PartResult]
"""Der profilbewusste Bauweg eines Rezepts — siehe ``PartSpec.build_with_profile``."""

_NAME_PATTERN: Final = re.compile(r"^[a-z][a-z0-9_]*$")

#: Kürzestes Wort, das die Suche ernst nimmt.
MIN_SEARCH_WORD: Final = 4

#: Wörter, die in fast jeder Beschreibung vorkommen und darum nichts sagen.
STOP_WORDS: Final[frozenset[str]] = frozenset(
    {
        "auch",
        "eine",
        "einen",
        "einem",
        "eines",
        "damit",
        "dass",
        "durch",
        "haben",
        "kann",
        "nach",
        "nicht",
        "oder",
        "sich",
        "sind",
        "über",
        "wenn",
        "wird",
        "zwei",
    }
)

#: Gruppen des Katalogs (§24.3). Sie ordnen, was der Nutzer sieht.
GROUPS: Final[dict[str, TranslatableText]] = {
    "fasteners": _("Verbindungen"),
    "mechanics": _("Mechanik"),
    "mounting": _("Befestigung"),
    "structure": _("Struktur"),
    "routing": _("Kabel und Schläuche"),
    "calibration": _("Kalibrierung"),
}


@dataclass(frozen=True, slots=True)
class PartChange:
    """Ein Eintrag des Änderungsverlaufs, den §24.4 verlangt, je Baustein."""

    version: str
    date: str
    reason: str
    effect: str = ""
    """Was sie an den Maßen ändert — das, worauf es für alte Projekte ankommt."""


@dataclass(frozen=True, slots=True)
class PartSpec:
    """Alles, was über einen Baustein bekannt ist."""

    name: str
    title: TranslatableText | str
    group: str
    params: type[BaseParams]
    fn: PartFn
    version: str = "1"
    subtractive: bool = False
    """Wahr für eine Form, die abgezogen wird: Bohrung, Tasche, Mutternfalle."""
    at_hole_values: HoleValues | None = None
    """Was eine Bohrung dieses Durchmessers für diesen Baustein vorschlägt.

    **Die Regel ist je Baustein eine andere, und darum steht sie hier statt im
    Kern.** Eine Einpressbuchse braucht die kleinste Größe, deren Bohrung die
    vorhandene *aufweitet*; ein Gewinde die größte, deren Kernloch noch
    *hineinpasst*. Wer beides über eine einheitliche Formel bedient, hat in
    einem der beiden Fälle unrecht — gemessen am 23.08.2026: An einer
    Ø 5,19-Bohrung schlug die Einpressbuchse M3 vor, deren Bohrung 4,00 mm
    misst. Der Schnitt lag vollständig innerhalb der vorhandenen Bohrung und
    trug nichts ab. Der Kunde klickte, füllte den Dialog aus, bestätigte,
    bekam einen Schritt im Verlauf und eine unveränderte Geometrie.

    Gibt ein leeres Ergebnis zurück, wo keine Größe passt. **Kein Rateschluss
    auf die nächstbeste** (Regel 21): Eine 40-mm-Bohrung bekommt keinen
    M8-Vorschlag, sondern gar keinen, und die Vorgabe bleibt stehen.
    """
    at_hole: bool = False
    """Wahr für einen Baustein, der in eine **vorhandene** Bohrung gesetzt wird.

    Der Unterschied ist der zwischen „macht ein Loch" und „arbeitet in einem".
    Ein Schraubenloch, ein Passstift und eine Kabeldurchführung bringen ihre
    Bohrung mit; sie gehören an eine Fläche. Gewinde, Mutternfalle und
    Einpressbuchse setzen eine voraus — wer eine Bohrung anklickt, will genau
    diese drei angeboten bekommen und nicht achtzehn.

    Gesetzt wird das ausdrücklich und nicht geraten: Ob ein Baustein Material
    abträgt, sagt nichts darüber, ob er in ein Loch gehört. Gemessen am
    23.08.2026 wirkten auch Passungsleiter, Wandleiter und Überhangfächer an
    einer Bohrung — sie ergeben dort nur keinen Sinn.
    """
    joined_by_host: bool = False
    """Wahr, wenn der **Träger** die Teile dieses Bausteins zusammenhält.

    Der Lochwand-Einhänger setzt ohne Rückplatte je Haken einen Zapfen, und
    zwei Zapfen sind zwei Körper. Am Teil, an das sie kommen, sind sie einer —
    genau dafür sind sie da.

    **§24.3 verlangt das nicht.** Der Bauplan nennt vier Dinge: wasserdicht,
    Mindestwandstärke, keine Selbstdurchdringung an den Grenzen, Merkmale
    korrekt benannt. Die Einteiligkeit hat der Bereichstest hinzugefügt, und
    zwar aus gutem Anlass: Die Rastnase zerfiel, weil sie die Fläche nur
    berührte (§39). Gemeint war „zerfällt nicht **versehentlich**"; was der
    Test prüft, ist „ist nicht mehrteilig".

    Dieses Feld trennt die beiden Fälle, statt eine Ausnahme in den Test zu
    schreiben. Wer es setzt, sagt: Die Teile gehören an einen Träger, und dort
    werden sie eins — geprüft wird das dann dort und nicht am Baustein allein
    (``test_a_part_held_by_its_host_becomes_one_with_it``).

    Es ist **nicht** die print-in-place-Frage aus dem Register: Dort geht es um
    Teile, die sich gegeneinander bewegen sollen, und die hält kein Träger
    zusammen.
    """

    keeps_up: bool = False
    """Wahr für einen Baustein, der ein **Oben** hat, das die Schwerkraft meint.

    Ein Lochwand-Einhänger hängt: Sein Zapfen sitzt oben im Schlitz, seine Nase
    greift unten hinter die Platte. Ein Schlüsselloch ebenso — der Kopf geht
    unten durch, die Schraube sitzt oben. Verkehrt herum gesetzt hält keiner
    von beiden. Fast
    alle anderen Bausteine haben das Problem nicht — eine Bohrung ist
    drehsymmetrisch, ein Fuß auch, und eine Rippe darf liegen, wie die Fläche
    es vorgibt.

    **Warum das Setzen es sonst nicht weiß.** An eine Fläche gesetzt wird ein
    Baustein über ``rotation_between``, und das nimmt die *kürzeste* Drehung
    von seinem +Z auf die Flächennormale. Um die Normale herum rollt er dabei
    frei, und wohin, ist eine Eigenschaft der Formel und nicht der Absicht:
    Gemessen am 25.08.2026 stand die Schlitzlänge des Einhängers an einer
    ±Y-Wand senkrecht und an einer ±X-Wand **waagerecht** — dort passte er in
    keinen Schlitz. Eine von vier Wandrichtungen war richtig, und das sieht man
    dem Baustein nicht an: Er wird in seinem eigenen System gebaut und erfährt
    nie, wohin man ihn dreht.

    Ist das Feld gesetzt, dreht ``_place`` ihn zusätzlich um die Flächennormale,
    bis sein **-Y** so weit nach oben zeigt, wie die Fläche es zulässt. Bei
    einer waagerechten Fläche gibt es in deren Ebene kein Oben; dort bleibt es
    bei der kürzesten Drehung.

    **Warum -Y und nicht +Y:** Weil der zweite Weg, einen Baustein umzulegen,
    es so hält. ``axis="y"`` dreht mit ``rotation("x", -90)`` das eigene +Y
    nach Welt-unten, und das Schlüsselloch baut seit je danach. Wer hier +Y
    aufrichtete, hätte zwei Konventionen im selben Register — und am
    25.08.2026 war das für einen Nachmittag auch so.

    Die Vorgabe ist falsch und nicht wahr: Wer sie setzt, ändert die Lage
    seines Bausteins, und das darf keinem bestehenden von selbst geschehen.
    """

    at_face: bool = True
    """Wahr für einen Baustein, den man an eine **Fläche** setzt.

    Das ist der Normalfall, und deshalb ist es die Vorgabe: Ein Baustein ist
    ein Anbauteil, es gibt ihm eine Fläche, auf der er sitzt oder in die er
    schneidet. Die Ausnahme sind die Prüfkörper — Passungsleiter,
    Wandstärkenleiter, Überhangfächer —, die für sich stehen und an nichts
    angebaut werden.

    **Vorher wurde es geraten, und die Regel war die falsche.**
    ``_applies_to`` bot eine Fläche nur an, wenn der Baustein Material
    *abträgt*. Damit standen Wandhalter, Nutfeder, Rippe, Rastnase,
    Schnappverbindung und Filmscharnier in keinem Kontextmenü einer Fläche —
    sechs von achtzehn, gemessen am 24.08.2026. Wer auf die Rückseite eines
    Modells zeigte, um einen Wandhalter zu setzen, fand dort alles außer dem
    Wandhalter, und §18.5 nennt dieses Menü „die wichtigste Einzelfunktion".

    Ob ein Baustein abträgt, sagt nichts darüber, ob er an eine Fläche gehört
    — dieselbe Einsicht, die über ``at_hole`` steht, nur für die andere Seite.
    """
    features: tuple[str, ...] = ()
    """Provenienz-Merkmale, die der Baustein zu benennen verspricht (§24.1)."""
    doc: TranslatableText | str = ""
    caveat: TranslatableText | str = ""
    """Wo dieser Baustein die falsche Wahl ist (§24).

    **Bis zum 23.08.2026 konnte ein Baustein keinen tragen**, und deshalb hatte
    keiner der zwanzig einen — nicht aus Nachlässigkeit, sondern weil
    ``register_part`` das Feld nicht kannte und ``_register_one`` es folglich
    nicht weiterreichen konnte. Zwölf Operationen außerhalb der Bibliothek
    hatten längst einen; die Bausteine fielen durch eine Lücke in der
    Schnittstelle.

    Gerade bei einem Baustein ist die Auskunft viel wert: Er sieht aus wie eine
    fertige Lösung, und die Frage „wann ist er die falsche?" beantwortet sonst
    niemand — ein gedrucktes Gewinde etwa hält da nicht, wo eine Metallschraube
    greifen soll.
    """
    changes: tuple[PartChange, ...] = ()
    source: str = "shipped"
    """``shipped``, ``user`` oder ``recipe`` — der Katalog weist die Herkunft
    aus (§24.5). ``user`` heißt weiter: eine ``.py`` aus dem Nutzerordner; ein
    Rezept ist Daten und reist mit (Regel 13 in der Fassung vom 24.08.2026)."""
    range_passed: bool | None = None
    """Ob der Bereichstest bestanden ist — ``None`` heißt: nie gefahren.

    Für die mitgelieferten Bausteine läuft er in der Suite, und dieses Feld
    bleibt ``None``; für ein Rezept läuft er beim Anlegen, und §24.5 verlangt
    den **Warnhinweis im Katalog**, wenn er fehlt oder nicht bestanden ist —
    dieses Feld ist die Auskunft dafür."""
    build_with_profile: BuildWithProfile | None = None
    """Bauen mit dem Profil des Dokuments — nur Rezepte tragen es.

    ``fn`` bleibt der Vertrag (§24.1: Parameter hinein, Körper heraus) und
    rechnet ohne Profil; ein Rezept aber darf ``auto:``-Toleranzen enthalten,
    und die gehören mit dem Material des **Kunden** aufgelöst, nicht mit
    unserem Standard. ``ops.insert`` bevorzugt diesen Weg, wo er da ist; für
    Vorschau und Bereichstest, wo kein Dokument im Spiel ist, gilt ``fn``."""
    recipe_data: Mapping[str, Any] | None = None
    """Die Daten des Rezepts, aus dem dieser Eintrag entstand — für die Reise.

    Ein Rezept reist in jeder Projektdatei mit, die es benutzt (Entscheidung
    Robert, 24.08.2026; Konzept Befestigungssysteme §17.1). Das Speichern
    muss dafür an die Daten kommen, ohne die Datei im Nutzerordner erneut zu
    lesen — ein mitgereistes Rezept hat dort gar keine. ``None`` für alles,
    was kein Rezept ist."""

    @property
    def own(self) -> bool:
        """Gehört dem Kunden — Katalog und Detailspalte kennzeichnen das (§24.5).

        Eigene gibt es in zwei Gestalten: als ``.py`` aus dem Nutzerordner
        (``user``) und als Rezept (``recipe``). Solange hier nur ``user``
        stand, trug ein Rezept keine Kennzeichnung — gefunden am 25.08.2026
        im echten Fenster. Wer nur die ``.py``-Gestalt meint (Dateiabdruck,
        Reisewarnung), fragt nach ``source``, nicht hierher.
        """
        return self.source in ("user", "recipe")


class PartRegistry:
    """Hält die Deklarationen. Eine Vorgabe-Instanz; Tests bauen ihre eigene."""

    def __init__(self) -> None:
        self._parts: dict[str, PartSpec] = {}

    def register(self, spec: PartSpec) -> PartSpec:
        self._check(spec)
        self._parts[spec.name] = spec
        return spec

    def remove(self, name: str) -> None:
        """Nimmt einen Eintrag zurück — für den halben Registrierlauf.

        Ein Rezept wird an zwei Stellen registriert, Katalog und
        Operationsregister. Scheitert die zweite, muss die erste zurück:
        Ein Katalogeintrag ohne Operation ist ein Knopf, dessen Klick in
        einem ``InternalError`` endet. Ein unbekannter Name ist hier kein
        Fehler — zurücknehmen ist idempotent.
        """
        self._parts.pop(name, None)

    def _check(self, spec: PartSpec) -> None:
        if not _NAME_PATTERN.match(spec.name):
            raise InternalError(
                detail=f"part name {spec.name!r} is not lower_snake_case",
                values={"part": spec.name},
            )
        if spec.name in self._parts:
            raise InternalError(
                detail=f"part {spec.name!r} is registered twice",
                values={"part": spec.name},
            )
        if spec.group not in GROUPS:
            raise InternalError(
                detail=f"unknown group {spec.group!r}",
                values={"part": spec.name, "known": sorted(GROUPS)},
            )
        if not (isinstance(spec.params, type) and issubclass(spec.params, BaseParams)):
            raise InternalError(
                detail=f"{spec.name!r} needs a parameter set derived from BaseParams",
                values={"part": spec.name},
            )
        if not spec.features:
            raise InternalError(
                detail=f"{spec.name!r} names no provenance features (§24.1)",
                values={"part": spec.name},
            )

    def get(self, name: str) -> PartSpec:
        if name not in self._parts:
            raise InternalError(
                detail=f"unknown part {name!r}",
                values={"requested": name, "known": sorted(self._parts)},
            )
        return self._parts[name]

    def has(self, name: str) -> bool:
        return name in self._parts

    def all(self) -> tuple[PartSpec, ...]:
        return tuple(self._parts[name] for name in sorted(self._parts))

    def by_group(self) -> dict[str, tuple[PartSpec, ...]]:
        grouped: dict[str, list[PartSpec]] = {name: [] for name in GROUPS}
        for spec in self.all():
            grouped[spec.group].append(spec)
        return {name: tuple(entries) for name, entries in grouped.items() if entries}

    def search(self, text: str) -> tuple[PartSpec, ...]:
        """Womit ``find_part`` antwortet (§26.2). Schlichter Wortvergleich — eine
        Bausteinbibliothek aus ein paar Dutzend Einträgen braucht keinen Index,
        und ein falscher Treffer aus einer klugen Rangfolge wäre schlimmer als
        ein ehrlicher Fehlschlag.

        Kurze und häufige Wörter fallen weg: „eine Mutter mit Gewinde" träfe
        sonst jeden Baustein, dessen Beschreibung „mit" enthält — und eine
        Bibliothek, die auf alles antwortet, ist so nutzlos wie eine, die auf
        nichts antwortet.
        """
        words = [
            word
            for word in re.split(r"\W+", text.casefold())
            if len(word) >= MIN_SEARCH_WORD and word not in STOP_WORDS
        ]
        if not words:
            return ()
        found = []
        for spec in self.all():
            haystack = f"{spec.name} {spec.title} {spec.doc}".casefold()
            if any(word in haystack for word in words):
                found.append(spec)
        return tuple(found)

    def versions(self) -> dict[str, str]:
        """Jeder Baustein mit seiner eigenen Version — der Vergleich, auf dem
        §24.4 läuft.
        """
        return {spec.name: spec.version for spec in self.all()}

    def mark_source(self, name: str, source: str) -> PartSpec:
        """Hält fest, woher ein Baustein kam — der Katalog kennzeichnet die
        eigenen (§24.5).
        """
        import dataclasses

        spec = dataclasses.replace(self.get(name), source=source)
        self._parts[name] = spec
        return spec

    def clear(self) -> None:
        self._parts.clear()


#: Das Register, das die Anwendung benutzt.
PARTS: Final = PartRegistry()


def register_part(
    *,
    name: str,
    title: TranslatableText | str,
    group: str,
    params: type[BaseParams],
    version: str = "1",
    subtractive: bool = False,
    at_hole: bool = False,
    at_hole_values: HoleValues | None = None,
    at_face: bool = True,
    keeps_up: bool = False,
    joined_by_host: bool = False,
    features: Iterable[str] = (),
    doc: TranslatableText | str = "",
    caveat: TranslatableText | str = "",
    changes: Sequence[PartChange] = (),
    source: str = "shipped",
    registry: PartRegistry | None = None,
) -> Callable[[PartFn], PartFn]:
    """Deklariert einen Baustein. Die dekorierte Funktion bleibt aufrufbar
    wie zuvor.
    """

    def decorate(fn: PartFn) -> PartFn:
        (registry or PARTS).register(
            PartSpec(
                name=name,
                title=title,
                group=group,
                params=params,
                fn=fn,
                # **Der Stand kommt aus dem Verlauf, nicht daneben.** Beides
                # von Hand zu pflegen hieß, achtzehn Bausteine und ihre
                # Einträge im Gleichschritt zu halten — und beim ersten
                # gemeinsamen Eintrag lief es auseinander: Der Verlauf sagte
                # 4, das Feld stand auf 1, und der Test aus §24.4 fing es.
                # Wer eine Version will, schreibt einen Änderungseintrag; das
                # ist ohnehin Pflicht, und der Eintrag sagt außerdem, *was*
                # sich geändert hat.
                version=changes[-1].version if changes else version,
                subtractive=subtractive,
                at_hole=at_hole,
                at_hole_values=at_hole_values,
                at_face=at_face,
                keeps_up=keeps_up,
                joined_by_host=joined_by_host,
                features=tuple(features),
                doc=doc,
                caveat=caveat,
                changes=tuple(changes),
                source=source,
            )
        )
        return fn

    return decorate


#: Version der Bibliothek als Ganzes. Geht in jede Projektdatei (§16.2) und
#: wird erhöht, sobald ein Baustein sich auf eine Art ändert, die Maße
#: verschiebt. Version 3: das Spiel von Mutternfalle und Gewinde kommt aus
#: dem Materialprofil statt aus einer festen Vorgabe (``PLAY_FROM_PROFILE``
#: in ``fasteners.py``). Version 4: die angeklickte Fläche bestimmt die
#: Richtung des Bausteins (``FACE_GIVES_DIRECTION``). Version 7: das Kopfspiel
#: des Schlüssellochs wird wieder zum Durchgangsmaß addiert statt dagegen
#: ausgetauscht, und das Merkmal des Einhängers liegt auf einer Fläche, die es
#: gibt. Version 8: der Lochwand-Einhänger bekommt eine federnde Rastzunge
#: (alles ``mounting.py``, 25.08.2026).
LIBRARY_VERSION: Final = "8"

#: Version 2 hat eine einzige Ursache, und die betrifft drei Bausteine: sie
#: bauten über ihrem Ursprung statt darunter. Der Eintrag steht hier statt
#: dreimal in den Bausteindateien — es ist dieselbe Änderung, nicht drei.
MOUTH_AT_ORIGIN: Final = PartChange(
    version="2",
    date="2026-08-05",
    reason="Der Ursprung ist die Mündung, das Werkzeug geht nach unten ins Material (§24.1).",
    effect="Der Baustein liegt um seine eigene Tiefe tiefer. Alte Projekte "
    "bekommen ihn an der Stelle, an der er vorher wirkungslos in der Luft "
    "stand — die Position ist zu prüfen.",
)


#: Version 4 hat ebenfalls eine einzige Ursache, und sie betrifft jeden
#: Baustein, den man an ein Merkmal setzen kann: Die angeklickte Fläche
#: bestimmt jetzt auch die **Richtung**, nicht nur den Ort.
FACE_GIVES_DIRECTION: Final = PartChange(
    version="4",
    date="2026-08-23",
    reason="Eine Fläche schaut entlang ihrer Normalen, und darauf steht der "
    "Baustein — vorher stand er entlang der Vorgabe Z (§25, §18.5).",
    effect="An einer Deckfläche ändert sich nichts. An einer Seitenwand oder "
    "einer geneigten Fläche steht der Baustein jetzt senkrecht auf ihr statt "
    "senkrecht nach oben; wer das alte Verhalten nachbaut, hat unter *Achse* "
    "eine Richtung gewählt, die nun aus der Fläche kommt.",
)


def changed_since(before: dict[str, str], registry: PartRegistry | None = None) -> tuple[str, ...]:
    """Bausteine, deren Version sich bewegt hat, seit ein Projekt gespeichert
    wurde (§24.4).

    Nur die, die das Projekt wirklich benutzt hat, sind ein Wort wert — der
    Aufrufer übergibt also genau diese, mit der Version, mit der jeder
    gerechnet wurde.
    """
    current = (registry or PARTS).versions()
    return tuple(
        name
        for name, version in sorted(before.items())
        if name in current and current[name] != version
    )


def changed_since_library(
    version: str, used: Iterable[str], registry: PartRegistry | None = None
) -> tuple[str, ...]:
    """Benutzte Bausteine, die sich geändert haben, seit ein Projekt
    gerechnet wurde (§24.4).

    Eine Projektdatei hält die Bibliotheksversion fest, keine Version je
    Baustein — der Vergleich läuft also über die Änderungsverläufe: wer einen
    Eintrag neuer als diese Version hat, hat sich bewegt, und nur die
    Bausteine, die das Projekt wirklich benutzt hat, sind ein Wort wert.
    """
    source = registry or PARTS
    since = _as_number(version)
    return tuple(
        name
        for name in sorted(set(used))
        if source.has(name)
        and any(_as_number(change.version) > since for change in source.get(name).changes)
    )


def _as_number(version: str) -> int:
    try:
        return int(version)
    except ValueError:
        return 0


def used_parts(operations: Iterable[Any]) -> tuple[str, ...]:
    """Welche Bausteine ein Stapel benutzt, abgelesen an den
    Operationsnamen (§24.4).
    """
    prefix = "insert_"
    return tuple(
        sorted(
            {
                str(entry.op)[len(prefix) :]
                for entry in operations
                if str(entry.op).startswith(prefix)
            }
        )
    )


def missing_parts(before: dict[str, str], registry: PartRegistry | None = None) -> tuple[str, ...]:
    """Bausteine, die ein Projekt benutzt hat und die diese Installation
    nicht hat (§24.5).

    Ein eigener Baustein von der Maschine eines anderen landet hier, und die
    Auswertung muss anhalten, statt etwas anderes zu rechnen (§15.2).
    """
    current = (registry or PARTS).versions()
    return tuple(name for name in sorted(before) if name not in current)
