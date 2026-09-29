"""Der Bereichstest in der Anwendung (§24.3, §24.5 — Konzept E3).

§24.3 sagt: „Ein Baustein ohne diesen Test gilt als nicht vorhanden", und
§24.5 verlangt für eigene Bausteine denselben Test, mit Warnhinweis im
Katalog, wenn er nicht bestanden ist. Für die mitgelieferten Bausteine läuft
er in der Suite (``tests/test_parts.py``); ein Kunde hat keine Suite — sein
Rezept wird deshalb **beim Anlegen** geprüft, mit Fortschritt und Abbruch,
und das Ergebnis bleibt am Baustein.

Die Ecken sind dieselben wie im Test, und das ist der Punkt: eine Regel, ein
Ort. Das kartesische Produkt ist Absicht — erst die Kombination zweier Grenzen
ist oft die Stelle, an der eine Geometrie zusammenfällt.
"""

from __future__ import annotations

import gc
import itertools
import math
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

from app.core.errors import OperationCancelled, ValidationError
from app.core.knowledge.parts.ops import PLAY_FIELD
from app.core.knowledge.parts.registry import FeatureRequirement, PartSpec, WallRequirement
from app.core.types import BaseParams, CancelToken, PartResult, Profile, ProgressFn
from app.core.units import EPS_DISPLAY, EPS_GEOM
from app.i18n import _


def _corner_values(params: type[BaseParams]) -> list[tuple[str, list[Any]]]:
    """Die unterschiedlichen Randwerte je Feld, noch ohne ihr kartesisches Produkt."""
    lists: list[tuple[str, list[Any]]] = []
    for entry in params.spec():
        values: list[Any] = []
        if entry.kind == "enum":
            values = list(entry.choices)
        elif entry.kind == "bool":
            values = [True, False]
        elif entry.kind in ("float", "int"):
            values = [entry.minimum, entry.maximum]
        values = list(dict.fromkeys(value for value in values if value is not None))
        if values:
            lists.append((entry.name, values))
    return lists


#: Vollständige Kombinationen pro Lauf. Deckt die mitgelieferte Bibliothek
#: (höchstens 320 Ecken je Baustein) ab und begrenzt fremde Parameterprodukte.
MAX_CORNERS: Final = 512


def _collect_on_main_thread() -> None:
    """Kernzyklen sammeln, ohne im Arbeiter fremde GUI-Objekte zu finalisieren."""
    if threading.current_thread() is threading.main_thread():
        gc.collect()


def corner_count(params: type[BaseParams]) -> int:
    """Zählt den ganzen Bereich, ohne eine einzige Kombination anzulegen."""
    return math.prod(len(values) for _name, values in _corner_values(params))


def require_range_size(count: int) -> None:
    """Weist zu große Bereiche vor dem Rechnen ab; niemals nur teilweise prüfen."""
    if count > MAX_CORNERS:
        raise ValidationError(
            field="exposed",
            constraint="maximum",
            values={"count": count, "limit": MAX_CORNERS},
            detail=_(
                "Der Bereichstest umfasst {count} Kombinationen; höchstens {limit} "
                "sind möglich. Geben Sie weniger Maße frei.",
                count=count,
                limit=MAX_CORNERS,
            ),
        )


def corners(params: type[BaseParams]) -> list[dict[str, Any]]:
    """Der Parameterbereich als die Werte, die ein Baustein überstehen muss.

    Der kleinste und der größte Wert jeder Zahl, jede Wahl jedes Enums und
    beide Zustände jedes Schalters — als vollständiges kartesisches Produkt.
    Die Vorgabe ist keine Grenze; sie wird im Reproduzierbarkeitstest gefahren.

    Die vorherige zyklische Fassung prüfte jeden Einzelwert, aber nicht sein
    Zusammenspiel: 124 Zeilen sahen nach Abdeckung aus, obwohl die Bibliothek
    2.114 Grenzkombinationen hat. Gemessen am 31.08.2026 brauchen ihre reinen
    Builds 73,2 Sekunden. Das ist ein sichtbarer, abbrechbarer Arbeitslauf und
    kein Grund, die zugesagte Menge still zu verkürzen.
    """
    lists = _corner_values(params)
    require_range_size(math.prod(len(values) for _name, values in lists))
    if not lists:
        return [{}]
    return [
        dict(zip((name for name, _values in lists), combination, strict=True))
        for combination in itertools.product(*(values for _name, values in lists))
    ]


DEFAULT_WALL_REQUIREMENT: Final = WallRequirement()


def _is_cancelled(token: CancelToken) -> bool:
    """Fragt erneut; der Zustand darf sich während einer Phase ändern."""
    return token.is_cancelled


@dataclass(frozen=True, slots=True)
class RangeFailure:
    """Eine Ecke, die nicht hielt — mit den Werten, bei denen es geschah."""

    values: dict[str, Any]
    reason: str


@dataclass(frozen=True, slots=True)
class RangeExclusion:
    """Eine Ecke, die der Baustein selbst als nicht baubar erklärt hat."""

    values: dict[str, Any]
    reason: str


@dataclass(frozen=True, slots=True)
class RangeReport:
    """Was der Bereichstest ergeben hat. Hängt am Baustein, nicht im Hash.

    Der Hash ist die Version des Rezepts (§24.4) — stünde der Bericht darin,
    machte das **Prüfen** aus dem Rezept ein anderes, und jedes Projekt
    meldete beim Öffnen eine Änderung, die keine ist.

    ``excluded`` sind die Ecken, die :attr:`PartSpec.feasible` vorher als
    nicht baubar erklärt hat und an denen der Baustein wie erklärt ablehnt.
    Sie zählen nicht als Fehler — ein erklärter Ausschluss ist Teil des
    Vertrags; ein **unerklärter** Abbruch bleibt einer.
    """

    checked: int = 0
    failures: tuple[RangeFailure, ...] = ()
    excluded: tuple[RangeExclusion, ...] = ()

    @property
    def passed(self) -> bool:
        return self.checked > 0 and not self.failures


@dataclass(slots=True)
class _Silent:
    @property
    def is_cancelled(self) -> bool:
        return False

    def raise_if_cancelled(self) -> None:
        return None


#: Zwei Flächen bilden eine Wand, wenn ihre Normalen höchstens rund 18 Grad
#: von der Gegenrichtung abweichen. Eine Fase oder Keilspitze ist damit kein
#: vermeintlich dünnes Wandstück; eine facettierte Rundung bleibt eines.
OPPOSING_NORMAL: Final = -0.95


def local_wall_thickness(mesh: Any, cancelled: CancelToken | None = None) -> float | None:
    """Die kleinste lokale Wand zwischen wirklich gegenläufigen Flächen.

    Von **jedem** Dreiecksmittelpunkt läuft ein Strahl nach innen bis zum
    ersten Austritt. Dessen Fläche muss gegenläufig sein: Nur dann ist der
    Abstand eine Wandstärke. So werden eine Fase, ein scharfer Keil und das
    Ende eines Zylinders nicht mit einer dünnen Wand verwechselt. Ist der
    nächste Austritt nicht gegenläufig, zählt dieser Strahl nicht — es wird
    nicht am selben Punkt nach einem zweiten, weiter entfernten Austritt
    gesucht.

    Gerechnet wird in ``geom.mesh.ray_hits_batch``: Möller-Trumbore gegen die
    Dreiecke, die ein räumlicher Index je Strahl vorauswählt (RM-050 — Ersatz
    für VTKs ``vtkStaticCellLocator``, plattformgleich wie jeder andere
    Strahl im Kern; RM-214 — ein Baum aus Hüllquadern, auch an Vollkörpern
    fast linear; die Auswahl ändert den Aufwand, den Treffer nur an fast
    streifenden Rändern, die auch der Vollvergleich nur gerundet kennt —
    Grenze und Kosten stehen an ``ray_hits_batch``). Es gibt keine
    Stichprobe: auch ein kleines Detail mit einem
    einzigen Dreieck wird vermessen. ``None`` bedeutet, dass der Körper keine
    zwei gegenläufigen Flächen trägt, oder dass der Lauf abgebrochen wurde;
    der Aufrufer unterscheidet beides am Token.
    """
    import numpy as np

    from app.core.geom.mesh import ray_hits_batch

    body = mesh.raw
    if not len(body.faces):
        return None
    vertices = np.asarray(body.vertices, dtype=np.float64)
    faces = np.asarray(body.faces, dtype=np.int64)
    centres = np.asarray(body.triangles_center, dtype=float)
    normals = np.asarray(body.face_normals, dtype=float)

    travel, hit_face = ray_hits_batch(
        vertices[faces],
        centres,
        -normals,
        edge_margin=EPS_GEOM,
        # Das Dreieck unter dem Startpunkt liegt exakt auf der Strahlachse
        # (der Strahl steht senkrecht auf ihm) und wäre sonst sein eigener
        # erster Treffer bei t≈0 — dieselbe Schwelle wie in
        # ``geom.measure.ray_distances``.
        minimum_travel=EPS_GEOM * 100.0,
        cancelled=cancelled,
    )
    if cancelled is not None and cancelled.is_cancelled:
        return None
    hit = hit_face >= 0
    if not np.any(hit):
        return None
    opposite = normals[hit_face[hit]]
    dotted = np.sum(normals[hit] * opposite, axis=1)
    opposing = np.zeros(len(hit), dtype=bool)
    opposing[hit] = dotted <= OPPOSING_NORMAL
    if not np.any(opposing):
        return None
    return float(travel[opposing].min())


def has_self_intersections(mesh: Any, cancelled: CancelToken | None = None) -> bool:
    """Ob nicht benachbarte Dreiecke einander schneiden.

    Ein wasserdichtes Netz kann aus zwei geschlossenen Hüllen bestehen, die
    durcheinanderlaufen, und zwei Bausteinflächen können an einer Ecke des
    Parameterbereichs deckungsgleich aufeinanderfallen. Topologieflags sehen
    beides nicht. Gerechnet wird in ``geom.intersections`` — dieselbe
    vollständige Rechnung, die auch die Netzfehlerkarte fragt, als Feld statt
    als Schleife über Dreieckspaare (RM-206: am Schraubenloch 1,5 s je Ecke
    zuvor).

    Ein Abbruch gibt ``False`` zurück; der Aufrufer unterscheidet ihn am Token.
    """
    from app.core.geom.intersections import intersects

    if cancelled is not None and cancelled.is_cancelled:
        return False
    body = mesh.raw
    try:
        return intersects(body.vertices, body.faces, cancelled)
    except OperationCancelled:
        return False


def printable_gap(mesh: Any, *, cancelled: CancelToken | None = None) -> float | None:
    """Kleinster Flächenabstand aller Komponenten, unabhängig von ihrer Reihenfolge."""
    from app.core.geom.measure import surface_gap
    from app.core.geom.mesh import MeshData

    pieces = mesh.raw.split(only_watertight=False)
    if len(pieces) < 2:
        return None
    closest = float(mesh.bounds.diagonal)
    for index, first in enumerate(pieces):
        for second in pieces[index + 1 :]:
            if cancelled is not None and cancelled.is_cancelled:
                return None
            measured = surface_gap(MeshData.of(first), MeshData.of(second), closest)
            if measured is None:
                return None
            closest = min(closest, measured)
            if closest <= EPS_GEOM:
                return 0.0
    return closest


def check(
    params: type[BaseParams],
    build: Any,
    profile: Profile,
    *,
    progress: ProgressFn | None = None,
    cancelled: CancelToken | None = None,
    joined_by_host: bool = False,
    bodies: int = 1,
    wall: WallRequirement = DEFAULT_WALL_REQUIREMENT,
    features: tuple[FeatureRequirement, ...] = (),
    feasible: Callable[[BaseParams], Any] | None = None,
) -> RangeReport:
    """Fährt die Ecken und sagt je Ecke, was nicht hielt.

    ``feasible`` ist die erklärte Bedingung des Bausteins zwischen seinen
    Parametern (:attr:`PartSpec.feasible`): Nennt sie für eine Ecke einen
    Grund, muss der Bau dort mit ``ValidationError`` ablehnen — dann ist die
    Ecke ein erklärter Ausschluss. Baut er trotzdem, ist die Erklärung falsch
    und die Ecke ein Fehler; bricht er anders ab, ebenso.

    ``joined_by_host`` nimmt die Prüfung auf **eine** Komponente heraus — für
    Bausteine, deren Teile erst der Träger verbindet. Der Lochwand-Einhänger
    setzt ohne Rückplatte je Haken einen Zapfen; zwei Zapfen sind zwei Körper,
    und an dem Teil, an das sie kommen, sind sie einer. Ohne diesen Schalter
    trüge sein Katalogeintrag eine Warnung über einen Baustein, der im Einsatz
    tadellos ist (§24.5 verlangt, dass ein gebrochener Bericht dort steht).
    Die übrigen drei Prüfungen gelten unverändert: Ein Baustein darf auch
    mehrteilig weder undicht noch leer noch zu dünn sein.

    ``bodies`` ist der **andere** mehrteilige Fall (§24.3, Entscheidung Robert
    vom 25.08.2026): print-in-place — ein Scharnier, das schon beim Drucken
    beweglich ist. Hier hält kein Träger die Teile zusammen, sie sollen
    getrennt bleiben. Geprüft wird deshalb nicht *ob* der Baustein zerfällt,
    sondern **ob er in so viele Teile zerfällt, wie er erklärt hat**: Zwei
    statt zwei ist die Zusage, drei statt zwei ist ein Fehler wie jeder andere.
    Unerklärtes Zerfallen bleibt damit rot — die Prüfung wird nicht schwächer,
    sondern genauer.

    ``wall`` macht die Mindestwand zum Vertrag statt zur Namenssonderregel:
    Profilgrenze, benannter Geometrieparameter oder eine fachlich begründete
    Nichtanwendbarkeit. ``features`` nennt ebenso, welches Merkmal in welcher
    Parameterstellung vorkommen muss. Ohne diese Deklaration werden vorhandene
    Merkmale weiterhin auf ID, Herkunft und Maße geprüft.

    ``build`` ist, was aus Werten einen Körper macht — für ein Rezept die
    Auswertung, für eine ``.py`` ihre Funktion. Ein Fehlschlag bricht nicht ab:
    Der Kunde soll **alle** brechenden Ecken sehen, nicht je Lauf eine.

    Abbruch ist Abbruch (§15.6): Was bis dahin geprüft ist, kommt zurück,
    und ``checked`` sagt ehrlich, wie weit es kam — ein abgebrochener Lauf
    sieht nie wie ein bestandener aus, denn ``passed`` verlangt Fehlerfreiheit
    **über alle** Ecken, und die Zahl steht daneben.
    """
    from app.core.geom.mesh import as_mesh_data

    token = cancelled or _Silent()
    plan = corners(params)
    failures: list[RangeFailure] = []
    excluded: list[RangeExclusion] = []
    checked = 0

    def announce(index: int, phase: int) -> None:
        if progress is None:
            return
        progress(
            (index * 4 + phase) / (len(plan) * 4),
            str(_("Bereichstest, Ecke {n} von {total}")).format(n=index + 1, total=len(plan)),
        )

    def add(values: dict[str, Any], reason: str) -> None:
        failures.append(RangeFailure(dict(values), reason[:200]))

    for index, values in enumerate(plan):
        if _is_cancelled(token):
            break
        announce(index, 0)
        # **Das Spiel kommt aus dem Profil, wie im Einsatz.** Ein Baustein
        # deklariert ``play`` und lässt es auf null; ``insert_part`` setzt dort
        # ``profile.material.clearance`` ein (``ops.py``, Regel 7). Der
        # Bereichstest tat das nicht und fuhr damit einen Zustand, den es nie
        # gibt: beim Bolzenscharnier ein Gelenk mit einer Hundertstel Spalt,
        # das beim Drucken verschweißt. Geprüft wurde eine Geometrie, die
        # niemand bekommt.
        entered = dict(values)
        if PLAY_FIELD in entered and not entered[PLAY_FIELD]:
            entered[PLAY_FIELD] = profile.material.clearance
        try:
            instance = params(**entered)
            declared = str(feasible(instance) or "") if feasible is not None else ""
            try:
                result: PartResult = build(instance)
            except ValidationError:
                if not declared:
                    raise
                excluded.append(RangeExclusion(dict(entered), declared[:200]))
                checked += 1
                announce(index, 4)
                if checked % 16 == 0:
                    _collect_on_main_thread()
                continue
            if declared:
                add(
                    entered,
                    str(_("als nicht baubar erklärt, baut aber: {reason}")).format(reason=declared),
                )
            announce(index, 1)
            if _is_cancelled(token):
                break

            mesh = as_mesh_data(result.mesh)
            if not mesh.is_watertight:
                add(entered, str(_("nicht geschlossen")))
            if mesh.volume <= 0.0:
                add(entered, str(_("kein Volumen")))
            if not joined_by_host and mesh.component_count != max(bodies, 1):
                # **Die erklärte Zahl, nicht die Eins.** Wer nichts deklariert,
                # bekommt ``bodies=1`` und damit genau die alte Prüfung; wer zwei
                # erklärt, muss zwei bauen — auch das ist eine Zusage, die brechen
                # kann, und ein Scharnier, das in drei Teile fällt, ist genauso
                # kaputt wie eine Rastnase, die in zwei fällt.
                add(
                    entered,
                    str(_("zerfällt in {found} Teile statt {declared}")).format(
                        found=mesh.component_count, declared=max(bodies, 1)
                    ),
                )

            minimum = wall.minimum(entered, profile)
            measured = local_wall_thickness(mesh, token) if minimum is not None else None
            if _is_cancelled(token):
                break
            if minimum is not None:
                if measured is None:
                    add(entered, str(_("Wandstärke nicht messbar")))
                elif measured < minimum - EPS_GEOM:
                    add(
                        entered,
                        f"{_('dünner als druckbar')!s}: {measured:.3f} mm < {minimum:.3f} mm",
                    )
            announce(index, 2)
            if _is_cancelled(token):
                break

            if mesh.is_watertight and mesh.volume > 0.0 and has_self_intersections(mesh, token):
                add(entered, str(_("Selbstdurchdringung")))
            if _is_cancelled(token):
                break
            announce(index, 3)

            gap = printable_gap(mesh, cancelled=token) if bodies > 1 else None
            if _is_cancelled(token):
                break
            if bodies > 1 and gap is None and mesh.component_count > 1:
                add(
                    entered,
                    str(
                        _(
                            "Der Abstand zwischen den Teilkörpern ist nicht messbar. "
                            "Die Geometrie reparieren und erneut prüfen."
                        )
                    ),
                )
            if (
                gap is not None
                # **``EPS_DISPLAY`` und nicht ``EPS_GEOM``**: Das hier ist eine
                # Fertigungsfrage, kein Rechenvergleich. Der gemessene Spalt fällt
                # um Bruchteile kleiner aus als der eingestellte, weil ein
                # facettierter Zylinder seine Sehne zeigt und nicht den Bogen —
                # gemessen 0,2499 bei eingestellten 0,25, und mit dem
                # Rechenepsilon meldete die Prüfung ein Scharnier, das genau
                # richtig gebaut war. Ein Hundertstel Millimeter liegt unter jeder
                # Druckauflösung; was darunter liegt, ist kein Spalt und kein
                # Fehler.
                and (gap < profile.material.clearance - EPS_DISPLAY)
            ):
                # **Der Spalt ist bei einem print-in-place-Teil die ganze Sache.**
                # Zu eng verschweißt beim Drucken, und aus zwei Körpern wird einer
                # — der Bereichstest sähe davon nichts, weil er die Geometrie vor
                # dem Drucker prüft und nicht danach. Gemessen wird gegen das
                # kalibrierte Material und nie gegen eine Zahl im Code (Regel 7).
                add(
                    entered,
                    str(_("Spalt {gap} mm — der Drucker legt {least} mm")).format(
                        gap=round(gap, 2), least=round(profile.material.clearance, 2)
                    ),
                )

            generated_features = getattr(result, "features", {})
            names = tuple(generated_features)
            for name, feature in generated_features.items():
                if feature.id != name:
                    add(
                        entered,
                        str(_("Merkmal {name}: ID {found} statt {expected}")).format(
                            name=name, found=feature.id, expected=name
                        ),
                    )
                if feature.provenance != "generated":
                    add(
                        entered,
                        str(_("Merkmal {name}: Herkunft {found} statt generated")).format(
                            name=name, found=feature.provenance
                        ),
                    )
                if not feature.params:
                    add(entered, str(_("Merkmal {name}: ohne Maße")).format(name=name))
                if features and not any(
                    requirement.applies(entered)
                    and (name == requirement.name or name.startswith(f"{requirement.name}_"))
                    for requirement in features
                ):
                    add(entered, str(_("Merkmal {name}: nicht deklariert")).format(name=name))
            for requirement in features:
                if requirement.applies(entered) and not any(
                    name == requirement.name or name.startswith(f"{requirement.name}_")
                    for name in names
                ):
                    add(
                        entered,
                        str(_("Merkmal {name}: fehlt")).format(name=requirement.name),
                    )

        except OperationCancelled:
            break
        except Exception as problem:  # Jede Prüfphase gehört zur betroffenen Ecke.
            if _is_cancelled(token):
                break
            add(entered, str(problem))

        checked += 1
        announce(index, 4)
        # VTK-Wrapper und native Manifold-Netze bilden Referenzzyklen. Ohne
        # periodischen Lauf sammelte die vollständige Bibliothek vor dem
        # ersten Gewinde bereits über ein Gigabyte an und wurde durch Paging
        # zwanzigmal langsamer. Die Paar- und Grenzmenge bleibt unverändert.
        # Nur im Hauptthread erzwingen: Der globale Sammler könnte sonst
        # auch GUI-Objekte aus fremden Referenzzyklen im Arbeiter zerstören.
        if checked % 16 == 0:
            _collect_on_main_thread()
    if checked < len(plan):
        add(
            {},
            str(
                _(
                    "Bereichstest abgebrochen: {checked} von {total} Kombinationen geprüft. "
                    "Starten Sie die Prüfung erneut, um den Rest zu prüfen.",
                    checked=checked,
                    total=len(plan),
                )
            ),
        )
    if progress is not None and checked == len(plan):
        progress(1.0, str(_("Bereichstest abgeschlossen")))
    report = RangeReport(checked=checked, failures=tuple(failures), excluded=tuple(excluded))
    _collect_on_main_thread()
    return report


def check_part(
    spec: PartSpec,
    profile: Profile,
    *,
    progress: ProgressFn | None = None,
    cancelled: CancelToken | None = None,
) -> RangeReport:
    """Prüft einen Registerbaustein ausschließlich nach seiner Deklaration."""
    return check(
        spec.params,
        spec.fn,
        profile,
        progress=progress,
        cancelled=cancelled,
        joined_by_host=spec.joined_by_host,
        bodies=spec.bodies,
        wall=spec.wall,
        features=spec.feature_requirements,
        feasible=spec.feasible,
    )
