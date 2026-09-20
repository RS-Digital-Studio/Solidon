"""Der B-Rep-Körper und sein Weg ins Netz (Bauplan §30, §9).

Ein :class:`Solid` erfüllt dasselbe ``Mesh``-Protokoll wie alles andere —
Viewport, Prüfbericht, Schichtanalyse und Export arbeiten also weiter mit
einem B-Rep-Objekt, ohne zu wissen, dass es eines ist. Was er *nicht* tut, ist
aus der Tessellation zu antworten, wo er exakt antworten kann: Volumen und
Fläche kommen aus dem Kern, nicht aus den Dreiecken, und der Unterschied ist
an einem verrundeten Teil nicht akademisch.

Die Tessellation wird einmal gemacht und aufgehoben. Sie ist eine Sicht auf
den Körper, nie der Körper — jede Operation arbeitet auf der Form, und die
Dreiecke werden danach neu gerechnet. Die andere Richtung, Netz zurück zu
B-Rep, gibt es hier nicht: die Kanten sind fort, und eine „Rekonstruktion"
erfände sie (§30).

OpenCASCADE ist optional. Ohne es sagt jeder Einstiegspunkt das in einem Satz,
und der Rest der Anwendung bleibt unberührt (§36).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from numbers import Integral
from operator import index as integer_index
from typing import Any, cast

from app.core.errors import CANCEL, INSTALL_MISSING, AppError, InternalError, ValidationError
from app.core.geom.mesh import MeshData
from app.core.log import get_logger
from app.core.types import MAX_SLOTS, BoundingBox, CancelToken
from app.core.units import MAX_FACET_ANGLE, MAX_FACET_SAG, is_close
from app.i18n import TranslatableText, _

_log = get_logger(__name__)

#: Wie weit die Tessellation von der echten Oberfläche abweichen darf, in mm —
#: der Name, unter dem OpenCASCADE danach fragt. Die Zahl steht in
#: :data:`app.core.units.MAX_FACET_SAG`, weil der Mesh-Kern dieselbe braucht:
#: Er baut seine Rundungen aus Sehnen, und die sollen so fein sein wie die
#: Flächen, die von hier kommen.
DEFLECTION = MAX_FACET_SAG

#: Winkelabweichung im Bogenmaß, aus demselben Grund und aus derselben Quelle.
ANGULAR_DEFLECTION = MAX_FACET_ANGLE

#: Zu welcher exakten Fläche jedes Dreieck der Anzeigetessellation gehört.
#: Das Attribut bleibt am ``trimesh``-Körper, bis ``features_of`` daraus die
#: öffentlichen ``Feature.face_indices`` macht. Ein gewöhnlicher Flächenindex
#: ist **kein** Dreiecksindex — genau diese Verwechslung färbte an einer
#: Bohrung ein einzelnes, fremdes Dreieck der Außenwand.
_FACE_ATTRIBUTE = "solidon_brep_face"

# Begrenzte Anzahl nativer Trägerhüllen, keine geometrische Toleranz.
_MAX_SURFACE_WRAPPERS = 64


class BRepUnavailable(AppError):
    """Der B-Rep-Kern ist nicht installiert."""

    default_title = _("Die Werkzeuge für bearbeitbare Flächen und Kanten fehlen.")
    # **Ohne diese Zeile bat Solidon um einen Fehlerbericht.** Die Klasse
    # nannte keine Vorschläge, ``AppError`` fällt dann auf „Abbrechen" zurück,
    # und für einen Dialog, dem sonst nichts bleibt, tritt der Bericht ein
    # (``dialogs.offered_actions``). Wer eine Verrundung ohne OpenCASCADE
    # versuchte, wurde also gebeten, einen Fehler zu melden — bei einer
    # Komponente, die zwei Klicks entfernt zu installieren ist.
    default_suggestions = (INSTALL_MISSING, CANCEL)

    def __init__(self, detail: str = "") -> None:
        super().__init__(
            detail=detail
            or _(
                "Fasen, Verrundungen und STEP brauchen das Zusatzpaket OpenCASCADE. "
                "Alles andere in Solidon funktioniert ohne."
            )
        )


def _same_point(a: tuple[float, float, float], b: tuple[float, float, float]) -> bool:
    """Ob zwei Knoten praktisch zusammenfallen — für den Degeneriert-Test.

    Millimeter gegen ``EPS_GEOM``: identische Koordinaten liegen erst recht
    darunter, der Bestand bleibt also unverändert grün.
    """
    return is_close(a[0], b[0]) and is_close(a[1], b[1]) and is_close(a[2], b[2])


def box_limits(box: Any) -> tuple[float, float, float, float, float, float]:
    """Die sechs Grenzen eines ``Bnd_Box``, über seine beiden Eckpunkte.

    ``Bnd_Box.Get`` gibt seit OpenCASCADE 8 eine ``Limits``-Struktur zurück,
    die OCP nicht bindet — der Aufruf endet in einem ``TypeError``. Die
    Eckpunkte gibt es in jeder Fassung, und sie sagen dasselbe.
    """
    low = box.CornerMin()
    high = box.CornerMax()
    return (
        float(low.X()),
        float(low.Y()),
        float(low.Z()),
        float(high.X()),
        float(high.Y()),
        float(high.Z()),
    )


def untrimmed_surface(surface: Any, *, cancelled: CancelToken | None = None) -> Any | None:
    """Liest unter rechteckigen Trägerhüllen, ohne Form oder Parametrisierung zu ändern.

    Die wirklichen Trimmgrenzen bleiben beim ursprünglichen Face/Adaptor.
    Der zurückgegebene Handle ist eine lesende Auskunft, keine Arbeitskopie.
    Bei zu tiefer Verschachtelung bleibt die Auskunft ausdrücklich offen.
    """
    from OCP.Geom import Geom_RectangularTrimmedSurface

    for depth in range(_MAX_SURFACE_WRAPPERS + 1):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if not isinstance(surface, Geom_RectangularTrimmedSurface):
            return surface
        if depth == _MAX_SURFACE_WRAPPERS:
            return None
        surface = surface.BasisSurface()
    return None


def available() -> bool:
    """Ist der Kern da? Wird gefragt, bevor sich eine Handlung anbietet (§36)."""
    try:
        import OCP.BRepPrimAPI  # noqa: F401
    except Exception:  # eine kompilierte Erweiterung scheitert auf mehr Arten als mit ImportError
        return False
    return True


def require() -> None:
    """Wirft den einen klaren Fehler statt eines Import-Stapelabzugs aus
    einer Bindung.
    """
    if not available():
        raise BRepUnavailable()
    _quieten()


def _quieten() -> None:
    """Nimmt OpenCASCADEs eigenen Drucker von der Konsole.

    Der STEP-Schreiber meldet seinen Fortschritt auf der Standardausgabe, und
    die landet auf der Kommandozeile mitten in dem, was gerade geschrieben
    wird, und in der paketierten Anwendung nirgendwo Nützlichem. Solidon
    protokolliert (§33.2); der Kern bekommt keinen eigenen Kanal.
    """
    global _quiet
    if _quiet:
        return
    try:
        from OCP.Message import Message, Message_PrinterOStream

        Message.DefaultMessenger_s().RemovePrinters(Message_PrinterOStream.get_type_descriptor_s())
    except Exception as problem:  # eine Bindung ohne die Printer-API ist in Ordnung
        _log.debug("could not silence the kernel messenger: %s", problem)
    _quiet = True


_quiet = False


def copy_shape(shape: Any) -> tuple[Any, tuple[int, ...], tuple[int, ...]]:
    """Eigene Geometrie und die belegte Zuordnung ihrer nativen Quellflächen
    und Quellkanten.

    Eine Kopierprimitive, kein zweiter Kopierweg: Eine Kante hat wie eine
    Fläche keinen Namen, der eine Kopie überlebt, und wer eine am Original
    gewählte Kante an der Arbeitskopie bearbeiten will, braucht die Abbildung
    aus demselben ``ModifiedShape`` — nicht eine angenommene
    Besuchsreihenfolge. Die Reihenfolge der Kanten ist die von
    :meth:`Solid.edges`, die der Flächen die von :meth:`Solid.faces`.
    """
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE

    builder = BRepBuilderAPI_Copy(shape, True, False)
    copied = builder.Shape()
    return (
        copied,
        _copied_mapping(builder, shape, copied, TopAbs_FACE, "face"),
        _copied_mapping(builder, shape, copied, TopAbs_EDGE, "edge"),
    )


def _copied_mapping(builder: Any, shape: Any, copied: Any, kind: Any, name: str) -> tuple[int, ...]:
    """Quellindex → Zielindex einer Kopie, für Flächen wie für Kanten bijektiv belegt."""
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
    from OCP.TopExp import TopExp

    source, target = ShapeMap(), ShapeMap()
    TopExp.MapShapes_s(shape, kind, source)
    TopExp.MapShapes_s(copied, kind, target)
    mapping = tuple(
        int(target.FindIndex(builder.ModifiedShape(source.FindKey(index)))) - 1
        for index in range(1, source.Extent() + 1)
    )
    if sorted(mapping) != list(range(target.Extent())):
        raise InternalError(
            detail=f"copy_shape returned an incomplete native {name} mapping",
            values={f"source_{name}s": source.Extent(), f"target_{name}s": target.Extent()},
        )
    return mapping


def boolean_builder(kind: str, first: Any, second: Any, *, tolerance: float | None = None) -> Any:
    """Konfiguriert vor dem ersten Build den Schutz beider Eingabeformen.

    Der Zwei-Shape-Konstruktor führt bereits Build aus. Optionen nach diesem
    Konstruktor kämen für die erste Bearbeitung deshalb zu spät.
    """
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
    from OCP.collections import List_TopoDS_Shape

    maker = {
        "union": BRepAlgoAPI_Fuse,
        "difference": BRepAlgoAPI_Cut,
        "intersection": BRepAlgoAPI_Common,
    }[kind]
    operation = maker()
    operation.SetNonDestructive(True)
    if tolerance is not None:
        operation.SetFuzzyValue(tolerance)
    arguments = List_TopoDS_Shape()
    arguments.Append(first)
    tools = List_TopoDS_Shape()
    tools.Append(second)
    operation.SetArguments(arguments)
    operation.SetTools(tools)
    return operation


def carried_face_slots(
    shape: Any,
    sources: Sequence[tuple[Any, tuple[int, ...]]],
    *,
    history: Any = None,
    cancelled: CancelToken | None = None,
) -> tuple[int, ...]:
    """Belegte alte Flächen behalten Filamente; neue Schnittflächen erhalten Slot null.

    Native Identität und Builder-Herkunft sind die einzigen Belege. Bei mehreren
    Körpern gewinnt wie im Netzweg die erste passende Quelle mit Attributen. Eine vom Builder
    zusammengefasste mehrfarbige Fläche braucht dagegen ihre Teilungsgrenze.
    """
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    if not any(slots for _source, slots in sources):
        return ()
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp

    targets = ShapeMap()
    TopExp.MapShapes_s(shape, TopAbs_FACE, targets)
    values = [0] * targets.Extent()
    assigned: set[int] = set()
    for source, slots in sources:
        if not slots:
            continue
        native = ShapeMap()
        TopExp.MapShapes_s(source, TopAbs_FACE, native)
        if len(slots) != native.Extent():
            raise InternalError(detail="incomplete native source face slots")
        claims: dict[int, int] = {}
        for index in range(1, native.Extent() + 1):
            if cancelled is not None:
                cancelled.raise_if_cancelled()
            face = native.FindKey(index)
            changed = [face]
            if history is not None:
                if hasattr(history, "Modified"):
                    changed.extend(history.Modified(face))
                else:
                    # ShapeFix liefert seine echte Ersetzung über ShapeBuild_ReShape.
                    modified = history.Apply(face)
                    if not modified.IsNull():
                        changed.append(modified)
                # GTransform veröffentlicht seine verkettete NURBS-Zuordnung
                # ausschließlich über ModifiedShape, nicht über Modified.
                if hasattr(history, "ModifiedShape"):
                    modified = history.ModifiedShape(face)
                    if not modified.IsNull():
                        changed.append(modified)
            slot = slots[index - 1]
            for modified in changed:
                if modified.IsNull():
                    continue
                fragments = ShapeMap()
                TopExp.MapShapes_s(modified, TopAbs_FACE, fragments)
                for number in range(1, fragments.Extent() + 1):
                    target = int(targets.FindIndex(fragments.FindKey(number))) - 1
                    if target < 0:
                        continue
                    if target in claims and claims[target] != slot:
                        raise ValidationError(
                            detail=_(
                                "Diese Änderung würde unterschiedlich zugewiesene Filamentflächen "
                                "zusammenfassen. Behalten Sie ihre Teilungsgrenze oder weisen Sie "
                                "ihnen zuerst dasselbe Filament zu."
                            )
                        )
                    claims[target] = slot
        for target, slot in claims.items():
            if target not in assigned:
                values[target] = slot
                assigned.add(target)
    return tuple(values)


def keep_filament_boundaries(solid: Solid, builder: Any) -> None:
    """Eine Flächenvereinigung darf Grenzen verschiedener Filamente nicht entfernen."""
    if not solid.face_slots:
        return
    from OCP.collections import (
        IndexedDataMap_TopoDS_Shape_List_TopoDS_Shape_TopTools_ShapeMapHasher as NeighbourMap,
    )
    from OCP.collections import (
        IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap,
    )
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopExp import TopExp

    faces, neighbours = ShapeMap(), NeighbourMap()
    TopExp.MapShapes_s(solid.shape, TopAbs_FACE, faces)
    TopExp.MapShapesAndAncestors_s(solid.shape, TopAbs_EDGE, TopAbs_FACE, neighbours)
    for index in range(1, neighbours.Extent() + 1):
        slots = {
            solid.face_slots[int(faces.FindIndex(face)) - 1]
            for face in neighbours.FindFromIndex(index)
        }
        if len(slots) > 1:
            builder.KeepShape(neighbours.FindKey(index))


@dataclass(frozen=True, slots=True)
class Solid:
    """Ein B-Rep-Körper. Erfüllt das ``Mesh``-Protokoll, indem er sich selbst
    tesselliert.
    """

    shape: Any
    """``TopoDS_Shape``. Absichtlich lose typisiert — die Anbindung ist optional."""
    deflection: float = DEFLECTION
    face_slots: tuple[int, ...] = ()
    """Filament je nativer Fläche; leer bedeutet überall den neutralen Slot null."""
    _cache: dict[str, Any] = field(default_factory=dict, init=False, compare=False, repr=False)
    _copied_faces: tuple[int, ...] = field(init=False, compare=False, repr=False)
    _copied_edges: tuple[int, ...] = field(init=False, compare=False, repr=False)

    def __post_init__(self) -> None:
        """Übernimmt eine eigene Form; die übergebene bleibt Eigentum des Aufrufers."""
        shape, mapping, edges = copy_shape(self.shape)
        object.__setattr__(self, "shape", shape)
        object.__setattr__(self, "_copied_faces", mapping)
        object.__setattr__(self, "_copied_edges", edges)
        if self.face_slots:
            if len(self.face_slots) != len(mapping) or any(
                type(slot) is not int or not 0 <= slot < MAX_SLOTS for slot in self.face_slots
            ):
                raise InternalError(detail="incomplete or invalid native face slots")
            slots = [0] * len(mapping)
            for source, target in enumerate(mapping):
                slots[target] = self.face_slots[source]
            object.__setattr__(self, "face_slots", tuple(slots))

    # --- die exakten Antworten --------------------------------------------------

    @property
    def volume(self) -> float:
        """Aus dem Kern, nicht aus den Dreiecken — das ist der ganze Punkt."""
        return float(self._properties("volume").mass)

    @property
    def area(self) -> float:
        return float(self._properties("surface").mass)

    @property
    def is_closed(self) -> bool:
        """Ob die Hülle geschlossen ist — gefragt an der Form, nicht an den
        Dreiecken.

        **Der Unterschied ist kein feiner.** :attr:`is_watertight` unten
        beantwortet dieselbe Frage über das vertesselte Netz, also über eine
        Näherung, die je nach Plattform anders ausfällt. Ein Gewindebolzen kam
        auf dem macOS-Runner mit richtigem Volumen und als ein Stück heraus
        und galt trotzdem als undicht: Die Vernetzung der Gewindeflanke ritzte
        dort, der Körper war tadellos. Die Operation sagte darauf „Aus diesem
        Durchmesser und dieser Steigung entsteht kein geschlossener Bolzen" —
        eine Absage über etwas, das gelungen war.

        Wer wissen will, ob ein Körper trägt (Export nach STEP, weitere
        Operationen), fragt hier. Wer wissen will, ob die **Dreiecke** dicht
        sind (STL, Schichtanalyse), fragt :attr:`is_watertight` — beides sind
        richtige Fragen, nur zu verschiedenen Dingen.
        """
        from OCP.ShapeAnalysis import ShapeAnalysis_Shell

        checker = ShapeAnalysis_Shell()
        checker.LoadShells(self.shape)
        checker.CheckOrientedShells(self.shape)
        return not checker.HasFreeEdges()

    @property
    def solid_count(self) -> int:
        """Wie viele Körper die Form trägt — topologisch gezählt.

        Das Gegenstück zu :attr:`component_count`, das die Dreiecke zählt.
        Zwei Körper, die sich berühren, ohne sich zu durchdringen, sind hier
        zwei — und im Netz je nach Vernetzung eines.
        """
        from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
        from OCP.TopAbs import TopAbs_SOLID
        from OCP.TopExp import TopExp

        found = ShapeMap()
        TopExp.MapShapes_s(self.shape, TopAbs_SOLID, found)
        return int(found.Extent())

    @property
    def face_count(self) -> int:
        return len(self.faces())

    @property
    def edge_count(self) -> int:
        return len(self.edges())

    def faces(self) -> list[Any]:
        """Jede Fläche, einmal. Benannte Entitäten — das ist es, was §30 einbringt."""
        return self._explore("face")

    def edges(self) -> list[Any]:
        return self._explore("edge")

    def checked_face_indices(
        self, indices: Sequence[int], *, cancelled: CancelToken | None = None
    ) -> tuple[int, ...]:
        """Prüft eine nichtleere Menge aktueller nativer Indizes ohne Tessellierung.

        Der Aufrufer belegt zuvor den aktuellen Eigentümer und gegebenenfalls
        die vollständige Dreiecksabdeckung. Die Länge der geprüften bijektiven
        Kopierabbildung ist zugleich die Anzahl unserer nativen Flächen.
        """
        return self._checked_indices(
            indices,
            len(self._copied_faces),
            _("Wähle vollständige Flächen aus und wiederhole die Änderung."),
            cancelled=cancelled,
        )

    def checked_edge_indices(
        self, indices: Sequence[int], *, cancelled: CancelToken | None = None
    ) -> tuple[int, ...]:
        """Dasselbe für native Kanten — der Indexraum ist :meth:`edges`."""
        return self._checked_indices(
            indices,
            len(self._copied_edges),
            _("Wähle die Kante am Körper neu und wiederhole die Änderung."),
            cancelled=cancelled,
        )

    def _checked_indices(
        self,
        indices: Sequence[int],
        count: int,
        rejection: TranslatableText,
        *,
        cancelled: CancelToken | None,
    ) -> tuple[int, ...]:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        selected: set[int] = set()
        for value in cast(Sequence[object], indices):
            if cancelled is not None:
                cancelled.raise_if_cancelled()
            if (
                isinstance(value, bool)
                or not isinstance(value, Integral)
                or not 0 <= int(value) < count
            ):
                raise ValidationError(detail=rejection)
            selected.add(int(value))
        if not selected:
            raise ValidationError(detail=rejection)
        result = tuple(sorted(selected))
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        return result

    # --- die tessellierten Antworten --------------------------------------------

    @property
    def mesh(self) -> MeshData:
        """Die Dreiecke. Einmal gemacht, und nie in die Form zurückgespeist."""
        cached = self._cache.get("mesh")
        if cached is None:
            cached = self._tessellated(self.deflection)
            self._cache["mesh"] = cached
        return cast(MeshData, cached)

    def to_mesh(self, *, deflection: float | None = None) -> MeshData:
        """Die Einbahntür aus §30. Ausdrücklich, denn der Rückweg ist zu."""
        return self.mesh if deflection is None else self._tessellated(deflection)

    def _tessellated(self, deflection: float) -> MeshData:
        """Jede neue Vernetzung liest ihre Filamente aus den exakten Trägerflächen."""
        import numpy as np

        mesh = tessellate(self.shape, deflection)
        if not self.face_slots:
            return mesh
        source = np.asarray(mesh.raw.face_attributes.get(_FACE_ATTRIBUTE, ()), dtype=np.int64)
        if len(source) != mesh.triangle_count or any(
            index < 0 or index >= len(self.face_slots) for index in source
        ):
            raise InternalError(detail="the tessellation has no complete native face mapping")
        return replace(mesh, slots=tuple(self.face_slots[index] for index in source))

    def with_triangle_slots(
        self, slots: tuple[int, ...], *, cancelled: CancelToken | None = None
    ) -> Solid:
        """Bindet reine Attribute an Flächen und erhält die gegenwärtigen Merkmalsdreiecke."""
        import numpy as np

        if cancelled is not None:
            cancelled.raise_if_cancelled()
        mesh = self.mesh
        if slots and (
            len(slots) != mesh.triangle_count
            or any(type(slot) is not int or not 0 <= slot < MAX_SLOTS for slot in slots)
        ):
            raise InternalError(detail="incomplete or invalid triangle slots")
        source = np.asarray(mesh.raw.face_attributes.get(_FACE_ATTRIBUTE, ()), dtype=np.int64)
        if (
            len(source) != mesh.triangle_count
            or np.any(source < 0)
            or np.any(source >= self.face_count)
        ):
            raise InternalError(detail="the tessellation has no complete native face mapping")
        face_slots = list(self.face_slots or (0,) * self.face_count) if slots else []
        if slots:
            values = np.asarray(slots, dtype=np.int64)
            low = np.full(self.face_count, MAX_SLOTS, dtype=np.int64)
            high = np.full(self.face_count, -1, dtype=np.int64)
            np.minimum.at(low, source, values)
            np.maximum.at(high, source, values)
            covered = high >= 0
            if np.any(low[covered] != high[covered]):
                raise ValidationError(
                    detail=_("Wähle vollständige Flächen aus und wiederhole die Änderung.")
                )
            for face in np.flatnonzero(covered):
                face_slots[face] = int(low[face])
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        result = replace(self, face_slots=tuple(face_slots))
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        # Die Kopie besitzt andere native Flächen. Die schon angezeigten Dreiecke
        # behalten ihre Reihenfolge; nur ihr belegter Weg zur Topologie ändert sich.
        raw = mesh.raw.copy()
        raw.face_attributes[_FACE_ATTRIBUTE] = np.asarray(result._copied_faces, dtype=np.int64)[
            source
        ]
        result._cache["mesh"] = replace(mesh, raw=raw, slots=slots)
        return result

    def complete_faces_of_triangles(self, indices: Sequence[int]) -> tuple[int, ...]:
        """Eine Auswahl muss vollständige exakte Flächen enthalten, auch bei Slot null."""
        import numpy as np

        faces = self.faces_of_triangles(indices)
        source = np.asarray(self.raw.face_attributes.get(_FACE_ATTRIBUTE, ()), dtype=np.int64)
        complete = set(np.flatnonzero(np.isin(source, faces)))
        if set(indices) != complete:
            raise ValidationError(
                detail=_("Wähle vollständige Flächen aus und wiederhole die Änderung.")
            )
        return faces

    def triangles_of_face(self, face_index: int) -> tuple[int, ...]:
        """Die Dreiecke der Tessellation, die zu einer exakten Fläche gehören.

        ``face_index`` zählt die Topologieflächen aus :meth:`faces`, die
        Rückgabe die Dreiecke aus :attr:`raw`. Beide Zahlenräume sind
        verschieden: Ein Zylindermantel ist eine einzige exakte Fläche, aber
        viele Dutzend Dreiecke im Viewport.
        """
        import numpy as np

        source = np.asarray(self.raw.face_attributes.get(_FACE_ATTRIBUTE, ()), dtype=np.int64)
        if len(source) != self.triangle_count:
            return ()
        return tuple(int(index) for index in np.flatnonzero(source == face_index))

    def faces_of_triangles(self, indices: Sequence[int]) -> tuple[int, ...]:
        """Eindeutige native Flächen einer gültigen Dreiecksauswahl, aufsteigend."""
        import numpy as np

        try:
            selected = tuple(integer_index(value) for value in indices)
        except TypeError as problem:
            raise ValidationError(
                detail=_("Die Dreiecksauswahl ist ungültig. Wählen Sie die Fläche erneut.")
            ) from problem
        if not selected:
            return ()
        source = np.asarray(self.raw.face_attributes.get(_FACE_ATTRIBUTE, ()), dtype=np.int64)
        if any(index < 0 or index >= self.triangle_count for index in selected):
            raise ValidationError(
                detail=_("Die Dreiecksauswahl ist ungültig. Wählen Sie die Fläche erneut.")
            )
        if len(source) != self.triangle_count:
            raise InternalError(
                detail="the tessellation has no complete native face mapping",
                values={"mapped_triangles": len(source), "triangles": self.triangle_count},
            )
        return tuple(int(index) for index in np.unique(source[list(selected)]))

    @property
    def vertex_count(self) -> int:
        return self.mesh.vertex_count

    @property
    def triangle_count(self) -> int:
        return self.mesh.triangle_count

    @property
    def bounds(self) -> BoundingBox:
        """Aus der Form, nicht aus den Dreiecken — wie Volumen und Fläche.

        Er kam aus der Tessellation und war damit konstant rund 0,025 mm zu
        klein: die halbe Abweichung, die das Anzeigenetz haben darf. Bei Ø 50
        stand 49,9755 mm, wo Fusion denselben Körper mit 25,00 mm Radius misst,
        und bei Ø 6 fehlten dieselben 0,017 mm — der Fehler ist absolut, also
        umso schlimmer, je kleiner das Maß.

        Das war kein Anzeigefehler. An dieser Zahl hängen die Maße im
        Objektbaum, die Bauraumprüfung, das Anordnen, der Haftungsrand und
        jede Passungsprüfung; Regel 6 sagt, dass der Kern in doppelter
        Genauigkeit rechnet und nur die Anzeige rundet.

        ``AddOptimal_s`` statt ``Add_s``: das eine misst die Flächen, das
        andere nimmt die Triangulation, wo es eine gibt — und die ist hier
        genau das Problem.
        """
        from OCP.Bnd import Bnd_Box
        from OCP.BRepBndLib import BRepBndLib

        box = Bnd_Box()
        # Ohne diese Zeile legt OpenCASCADE eine Sicherheitstoleranz um den
        # Quader; ein Würfel von 40 mm hätte dann 40,00002.
        box.SetGap(0.0)
        BRepBndLib.AddOptimal_s(self.shape, box, False, False)
        if box.IsVoid():
            return self.mesh.bounds
        low_x, low_y, low_z, high_x, high_y, high_z = box_limits(box)
        return BoundingBox(
            (float(low_x), float(low_y), float(low_z)),
            (float(high_x), float(high_y), float(high_z)),
        )

    @property
    def is_watertight(self) -> bool:
        return self.mesh.is_watertight

    @property
    def component_count(self) -> int:
        return self.mesh.component_count

    @property
    def slot_indices(self) -> tuple[int, ...]:
        return tuple(self.mesh.slot_indices)

    @property
    def raw(self) -> Any:
        """Die Dreiecke, für die Oberflächen, die sie zeichnen."""
        return self.mesh.raw

    def to_stl(self) -> bytes:
        return self.mesh.to_stl()

    def replacing(
        self,
        shape: Any,
        *,
        history: Any = None,
        others: Sequence[Solid] = (),
        cancelled: CancelToken | None = None,
    ) -> Solid:
        """Ein neuer Körper um eine geänderte Form, in derselben
        Tessellationsqualität.
        """
        slots = carried_face_slots(
            shape,
            [(self.shape, self.face_slots), *((other.shape, other.face_slots) for other in others)],
            history=history,
            cancelled=cancelled,
        )
        return Solid(shape=shape, deflection=self.deflection, face_slots=slots)

    # --- inside ------------------------------------------------------------------

    def _properties(self, kind: str, *, cancelled: CancelToken | None = None) -> Any:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        cached = self._cache.get(kind)
        if cached is not None:
            return cached
        from app.core.brep.properties import properties

        props = properties(
            self.shape, "volume" if kind == "volume" else "surface", cancelled=cancelled
        )
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        self._cache[kind] = props
        return props

    def _explore(self, kind: str) -> list[Any]:
        """Topologie-Entitäten, entdoppelt — ein Explorer besucht Kanten je Fläche."""
        cached = self._cache.get(f"list:{kind}")
        if cached is not None:
            return list(cached)
        from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
        from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
        from OCP.TopExp import TopExp
        from OCP.TopoDS import TopoDS

        found = ShapeMap()
        TopExp.MapShapes_s(self.shape, TopAbs_FACE if kind == "face" else TopAbs_EDGE, found)
        # Die Karte gibt nackte Formen zurück; alles danach will den echten
        # Typ, und ein falscher Cast hier scheitert erst viel weiter weg.
        as_typed = TopoDS.Face if kind == "face" else TopoDS.Edge
        entities = [as_typed(found.FindKey(index)) for index in range(1, found.Extent() + 1)]
        self._cache[f"list:{kind}"] = entities
        return list(entities)


def tessellate(shape: Any, deflection: float = DEFLECTION) -> MeshData:
    """Vernetzt eine private Kopie und behält die Flächenkennungen der Eingabe."""
    import numpy as np
    import trimesh
    from OCP.BRep import BRep_Tool
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
    from OCP.TopExp import TopExp
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS

    copied = BRepBuilderAPI_Copy(shape, True, False)
    BRepMesh_IncrementalMesh(copied.Shape(), deflection, False, ANGULAR_DEFLECTION, True)

    points: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    source_faces = ShapeMap()
    TopExp.MapShapes_s(shape, TopAbs_FACE, source_faces)
    face_sources: list[int] = []
    for face_index in range(source_faces.Extent()):
        # Die Kopie muss nicht dieselbe Besuchsreihenfolge haben. Der Builder
        # benennt die Kopie jeder Originalfläche; derselbe Indexraum wie faces().
        source_face = source_faces.FindKey(face_index + 1)
        face = TopoDS.Face(copied.ModifiedShape(source_face))
        location = TopLoc_Location()
        triangulation = BRep_Tool.Triangulation_s(face, location)
        if triangulation is None:
            continue

        transform = location.Transformation()
        offset = len(points)
        for index in range(1, triangulation.NbNodes() + 1):
            node = triangulation.Node(index).Transformed(transform)
            points.append((node.X(), node.Y(), node.Z()))

        # ModifiedShape liefert die Unterform ohne die im Körper komponierte
        # Orientierung. Der Umlaufsinn stammt deshalb aus der Originalfläche.
        reversed_face = source_face.Orientation() == TopAbs_REVERSED
        for index in range(1, triangulation.NbTriangles() + 1):
            first, second, third = triangulation.Triangle(index).Get()
            # **Ein Dreieck mit doppeltem Knoten ist keines.** Am Pol einer
            # Kugelfläche fällt eine ganze Parameterlinie auf einen Punkt
            # zusammen — Längen- und Breitengrad treffen sich dort —, und
            # ``BRepMesh`` erzeugt daraus ein Dreieck, dessen zwei Ecken
            # derselbe Knoten sind. Es hat die Fläche null, trägt zum Volumen
            # nichts bei und wandert trotzdem bis in die exportierte STL.
            #
            # Gemessen am 23.08.2026 an einem Quader mit Verrundungen an allen
            # Kanten: acht Eckverrundungen, acht Pole, acht solche Dreiecke.
            # Die Oberfläche ist dabei geschlossen (Euler-Zahl 2, Volumen
            # unverändert) — **aber ``is_watertight`` meldet „nein"**, weil
            # trimesh die acht degenerierten Kanten als offen zählt. Das ist
            # die Prüfung, die viele Werkzeuge fahren, unsere eigenen Tests
            # eingeschlossen.
            #
            # **Geprüft wird über die Koordinaten und nicht über die
            # Knotennummern** — gemessen am 23.08.2026, weil die naheliegende
            # Fassung nicht greift: OCCT vergibt am Pol *zwei* Knotennummern
            # für denselben Ort, und erst trimesh führt sie beim Einlesen
            # zusammen. Wer die Nummern vergleicht, sieht drei verschiedene
            # und lässt das Dreieck durch.
            # Eine umgekehrte Fläche heißt, dass der Umlaufsinn zu drehen ist —
            # sonst kommt der Körper umgestülpt heraus und jedes Volumen ist
            # negativ.
            corners = (third, second, first) if reversed_face else (first, second, third)
            corner_points = (
                points[corners[0] - 1 + offset],
                points[corners[1] - 1 + offset],
                points[corners[2] - 1 + offset],
            )
            # Über den Abstand, nicht bitgleich (Regel 6): Nach einer echten
            # Transformation (STEP-Baugruppe mit Location) fallen zwei
            # Polknoten nicht mehr bitgleich zusammen, und das degenerierte
            # Dreieck wanderte wieder in die STL.
            if (
                _same_point(corner_points[0], corner_points[1])
                or _same_point(corner_points[1], corner_points[2])
                or _same_point(corner_points[0], corner_points[2])
            ):
                continue
            faces.append(
                (corners[0] - 1 + offset, corners[1] - 1 + offset, corners[2] - 1 + offset)
            )
            face_sources.append(face_index)
    if not faces:
        return MeshData.of(trimesh.Trimesh())
    body = trimesh.Trimesh(
        vertices=np.asarray(points, dtype=float),
        faces=np.asarray(faces, dtype=np.int64),
        face_attributes={_FACE_ATTRIBUTE: np.asarray(face_sources, dtype=np.int64)},
        process=True,
    )
    _log.info("tessellated a B-Rep body into %d triangles", len(body.faces))
    return _stitched(MeshData.of(body))


def _stitched(mesh: MeshData) -> MeshData:
    """Ein Netz, das aus einer geschlossenen Form kommt, soll geschlossen sein.

    **Der Fall ist macOS, und der Weg dorthin war eine Sackgasse.** Ein
    Gewindebolzen ist dort als *Form* in Ordnung — geschlossen, ein Stück,
    richtiges Volumen, STEP trägt ihn —, aber seine Vernetzung ritzt an der
    Flanke: M6 mit einem Millimeter Steigung blieb undicht, auch nachdem
    ``_finely_meshed`` die Feinheit dreimal halbiert hatte. Unter Windows und
    Linux war jede Größe dicht. Der Registereintrag sagte deshalb, es warte
    auf eine neue OCCT-Version.

    Das stimmte für den eingeschlagenen Weg und nicht für alle: Versucht wurde
    ausschließlich, **feiner** zu vernetzen. Repariert wurde nie — obwohl
    genau dieser Defekt seit dem Eiffelturm-Fund einen eigenen Namen hat.

    **Vernäht, nicht gefüllt.** Ein Riss an einer Flanke ist keine fehlende
    Wand, sondern eine T-Kreuzung: Zwei Flächen stoßen an derselben Kante
    zusammen und werden verschieden fein unterteilt; ein Punkt sitzt dann auf
    einer Kante, die nichts von ihm weiß. ``trimesh.repair.fill_holes`` lehnt
    das zu Recht ab — gemessen an einem M6-Netz mit einem echten Loch bleibt
    es offen und rührt kein Dreieck an. ``stitch_t_junctions`` gibt der
    Nachbarfläche den fehlenden Punkt: keine neue Geometrie, keine verschobene
    Oberfläche.

    **Der Normalfall kostet 0,1 ms.** So teuer ist die Frage
    ``is_watertight`` an einem Netz mit 13 744 Dreiecken; das Vernähen selbst
    (2,6 ms) läuft nur, wenn die Antwort nein lautet. Ein dichtes Netz geht
    unverändert durch — auch das ist gemessen und keine Annahme.

    Bleibt es danach offen, kommt es trotzdem heraus. Der Körper ist gut, und
    ein Befund über ein grobes Netz ist besser als eine Absage über einen
    gelungenen Körper (§30).
    """
    if mesh.is_watertight:
        return mesh
    # Der Import steht hier und nicht oben: ``geom.repair`` zieht trimesh und
    # scipy, und der B-Rep-Kern wird auch von Wegen berührt, die kein Netz
    # anfassen.
    from app.core.geom.repair import open_edge_count, stitch_t_junctions

    before = open_edge_count(mesh)
    stitched, seams = stitch_t_junctions(mesh)
    if not seams:
        return mesh

    # **Übernommen wird nur, was besser ist.** Das Vernähen sucht Punkte, die
    # auf fremden Kanten sitzen, und teilt die Nachbarfläche daran — an einem
    # Netz, dessen Ränder gar keine T-Kreuzungen sind, entstehen dabei mehr
    # offene Kanten statt weniger. Gemessen an einem absichtlich zerlegten
    # Würfel: 15 offene Kanten hinein, 18 heraus, drei „Nähte". Die Zahl der
    # Nähte allein sagt also nicht, dass es geholfen hat.
    #
    # **Dieselbe Regel steht in der Eingangsstufe**, dort für das Verschweißen
    # (``ingest/loader.py``, „eine Reparatur, die etwas kaputt macht, wird
    # nicht angewendet"). Sie ist unabhängig zweimal gefunden worden — hier
    # steht der Verweis, damit die dritte Stelle sie nicht ein drittes Mal
    # finden muss.
    after = open_edge_count(stitched)
    if after >= before:
        _log.info("stitching would not close this mesh (%d -> %d edges), keeping it", before, after)
        return mesh
    _log.info(
        "tessellation left %d T-junction seams, stitched them (%d -> %d open edges)",
        seams,
        before,
        after,
    )
    return stitched
