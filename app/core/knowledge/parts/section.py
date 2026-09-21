"""Ein Querschnitt mit zwei Auswertern — die 2D-Seite der Formbeschreibung (P2.7).

Die Profilklemmen und ihre Einlagen entstehen aus **Querschnitten**: ein
gezeichneter Sitz, sein Normalversatz um die Wand, die Differenz der beiden,
zwei Ohren als Rechtecke, eine Hälfte davon — und erst zum Schluss ein Prisma
über die Klemmtiefe. Bis P2.7 war das ein ``manifold3d.CrossSection``; das
bleibt der eine Auswerter. Der zweite ist eine ebene Fläche des exakten Kerns:
Der Versatz eines Kreises bleibt dort ein Kreis, die Halbierung eine
Schnittkante, das Prisma ein Körper mit Zylinderflächen (Bericht P2.7,
Abschnitt 4.3).

Ein :class:`Section` trägt **immer** den Netzquerschnitt und unter
``shapes.building("brep")`` zusätzlich die exakte Fläche: Die Prüfungen —
Bounds, ein Materialintervall je Schnitt, keine Löcher, ein Stück — fragen den
Querschnitt, die Geometrie kommt aus der Fläche. Beide werden mit jedem
Schritt gemeinsam weitergerechnet, damit kein Aufrufer zwischen ihnen wählen
muss.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.core.errors import ValidationError
from app.core.geom.contours import offset_section as normal_offset
from app.core.geom.contours import polygons_of
from app.core.geom.contours import section_of as profile_section
from app.core.geom.mesh import MeshData
from app.core.knowledge.parts.shapes import Form, building_exact
from app.core.units import EPS_GEOM, MAX_FACET_SAG
from app.i18n import TranslatableText, _

if TYPE_CHECKING:
    from shapely.geometry import Polygon

    from app.core.brep.kernel import Solid
    from app.core.sketch.profile import Profile

#: Die Kontur und ihre aufeinander folgenden Versätze teilen sich das
#: Auflösungsbudget des Netzkerns. Das ist Sehnenauflösung, kein Fertigungsspiel.
CONTOUR_SAG = MAX_FACET_SAG / 8.0


def invalid(detail: TranslatableText, field: str = "sketch") -> ValidationError:
    """Die Korrektur gehört zu demselben gezeichneten Profil und seinen Maßen."""
    return ValidationError(field=field, constraint="profile_clamp", detail=detail)


def _faces() -> Any:
    from app.core.brep import profiles

    return profiles


@dataclass(frozen=True, slots=True)
class Section:
    """Ein gefüllter Querschnitt in der XY-Ebene, je Kern ausgewertet.

    ``cross`` ist der Netzquerschnitt (``manifold3d.CrossSection``) und immer
    da; ``face`` die exakte Fläche, nur unter dem exakten Kern. Jede Operation
    gibt einen neuen Querschnitt zurück und lässt beide Eingaben unberührt.
    """

    cross: Any
    face: Any = None

    @classmethod
    def of(cls, profile: Profile, *, check_cancelled: Callable[[], None] | None = None) -> Section:
        """Aus einem Skizzenumriss — Bögen bleiben exakt Bögen."""
        return cls(
            profile_section(profile, max_sag=CONTOUR_SAG, check_cancelled=check_cancelled),
            _faces().face_of(profile) if building_exact() else None,
        )

    @classmethod
    def from_points(cls, points: Sequence[Sequence[float]]) -> Section:
        """Aus einem Vieleck — so, wie eine Bindung ihre Konturen aufbewahrt."""
        from app.core.sketch.profile import Profile, ProfileSegment

        corners = [(float(point[0]), float(point[1])) for point in points]
        profile = Profile(
            segments=tuple(
                ProfileSegment("line", corner, corners[(index + 1) % len(corners)])
                for index, corner in enumerate(corners)
            )
        )
        return cls.of(profile)

    @classmethod
    def rectangle(cls, x0: float, x1: float, y0: float, y1: float) -> Section:
        import manifold3d

        cross = manifold3d.CrossSection.square((x1 - x0, y1 - y0)).translate((x0, y0))
        face = _faces().rectangle_face(x0, x1, y0, y1) if building_exact() else None
        return cls(cross, face)

    def _paired(self, cross: Any, face: Callable[[], Any]) -> Section:
        return Section(cross, face() if self.face is not None else None)

    def offset(
        self, distance: float, *, check_cancelled: Callable[[], None] | None = None
    ) -> Section:
        """Echter Normalversatz; positiv wächst Material und verkleinert Innenlöcher."""
        if abs(distance) <= EPS_GEOM:
            return self
        cross = normal_offset(
            self.cross, distance, max_sag=CONTOUR_SAG, check_cancelled=check_cancelled
        )
        return self._paired(cross, lambda: _faces().offset_face(self.face, distance))

    def minus(self, other: Section) -> Section:
        return self._paired(
            self.cross - other.cross,
            lambda: _faces().face_boolean("difference", self.face, other.face),
        )

    def plus(self, other: Section) -> Section:
        return self._paired(
            self.cross + other.cross, lambda: _faces().face_boolean("union", self.face, other.face)
        )

    def clipped(self, other: Section) -> Section:
        return self._paired(
            self.cross ^ other.cross,
            lambda: _faces().face_boolean("intersection", self.face, other.face),
        )

    def rotated(self, degrees: float) -> Section:
        if not degrees:
            return self
        return self._paired(
            self.cross.rotate(degrees), lambda: _faces().face_rotated(self.face, degrees)
        )

    def bounds(self) -> tuple[float, float, float, float]:
        """links, unten, rechts, oben — exakt aus der Fläche, sonst aus dem Querschnitt.

        Die Ohren einer Klemme setzen an diesen Hüllen an; am Netz liegen sie
        um den Sehnen-Sag innerhalb des Kreises, exakt genau auf ihm.
        """
        if self.face is not None:
            return _faces().face_bounds(self.face)  # type: ignore[no-any-return]
        left, low, right, high = self.cross.bounds()
        return float(left), float(low), float(right), float(high)

    def pieces(self) -> int:
        return len(self.cross.decompose())

    def area(self) -> float:
        return float(self.cross.area())

    def polygon(self) -> Polygon:
        """Ein gefüllter zusammenhängender Querschnitt, ohne versteckte weitere Konturen."""
        polygons = polygons_of(self.cross)
        if len(polygons) != 1:
            raise invalid(
                _(
                    "Der Konturversatz zerfällt in mehrere Teile. "
                    "Ändern Sie Kontur oder Einlagenstärke."
                )
            )
        polygon = polygons[0]
        if polygon.interiors:
            raise invalid(
                _(
                    "Der Konturversatz lässt keinen gültigen Sitz. "
                    "Ändern Sie die Kontur oder das Spiel."
                )
            )
        return polygon

    def extrude(self, depth: float, *, bottom: float = 0.0) -> Form:
        """Das Prisma über ``depth``, mit dem Boden auf ``bottom`` — je Kern.

        Beide Kerne prüfen dasselbe: geschlossen und ein Stück. Ein Querschnitt,
        der das nicht hergibt, ist eine Sache der Zeichnung, nicht des Kerns.
        """
        if self.face is not None:
            solid: Solid = _faces().prism(self.face, depth, bottom=bottom)
            if not solid.is_closed or solid.solid_count != 1:
                raise invalid(_HALF_NOT_ONE)
            return solid
        return _meshed(self.cross.extrude(depth).translate((0.0, 0.0, bottom)))


_HALF_NOT_ONE = _(
    "Die Teilung erzeugt keine geschlossene einzelne Hälfte. Ändern Sie die Trennebene."
)


def _meshed(solid: Any) -> MeshData:
    """Eine eigene Manifold-Konstruktion ohne Genauigkeitsverlust übernehmen."""
    import numpy as np

    from app.core.deferred import trimesh

    raw = solid.to_mesh64()
    mesh = MeshData.of(
        trimesh.Trimesh(
            vertices=np.array(raw.vert_properties[:, :3], copy=True),
            faces=np.array(raw.tri_verts, copy=True),
            process=False,
        )
    )
    if (
        not mesh.is_watertight
        or mesh.component_count != 1
        or not mesh.raw.nondegenerate_faces().all()
    ):
        raise invalid(_HALF_NOT_ONE)
    return mesh
