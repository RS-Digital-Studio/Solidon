"""Die Gegenprobe nach dem Schreiben: die fertige Datei erneut einlesen (§29).

Ein gelungener Schreibvorgang sagt nur, dass Bytes auf der Platte liegen. Ob
darin steht, was hinausgehen sollte, sagt erst das erneute Lesen derselben
Datei (Produktkompass 4.5, RM-090): Wie viele Körper, wie viele Dreiecke,
welches Volumen und welche Außenmaße kommen zurück?

Verglichen wird, was eine Lage nicht ändert. Ein Slicer bekommt die Teile in
Bettkoordinaten und im Plattenraster, eine GLB steht in Metern mit Y oben —
Volumen, Dreieckszahl und die **sortierten** Außenmaße überstehen beides,
eine verlorene, verdoppelte oder verzerrte Fläche nicht.

Die Grenzen kommen aus den benannten Toleranzen: Außenmaße gelten als gleich,
wenn die Anzeige sie gleich zeigt (``EPS_DISPLAY``), das Volumen, wenn es
höchstens um eine solche Verschiebung der ganzen Oberfläche abweicht
(Fläche mal ``EPS_DISPLAY``). STL rundet auf einfache Genauigkeit; beides
liegt weit darüber und weit unter einem echten Fehler.

Nichts hier schreibt oder ändert eine Datei; gelesen wird mit denselben
Lesern wie beim Import, ohne dessen Aufbereitung (§17.1).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

from app.core.errors import AppError
from app.core.geom.mesh import MeshData
from app.core.types import CancelToken, Profile
from app.core.units import EPS_DISPLAY
from app.i18n import TranslatableText, _

if TYPE_CHECKING:
    from app.core.export.writer import ExportPlan

ReadbackState = Literal["matched", "deviated", "not_performed"]

#: glTF rechnet in Metern; die Gegenprobe rechnet zurück in Millimeter
#: (``writer.GLB_METRES_PER_MM``, hier als Kehrwert, ohne Import des Schreibers).
_MM_PER_GLTF_UNIT: Final = 1000.0

#: Was sich als Dreiecksnetz zurücklesen lässt, je Endung.
_MESH_SUFFIXES: Final = frozenset({".stl", ".obj", ".ply", ".glb", ".3mf"})


@dataclass(frozen=True, slots=True)
class BodyFigures:
    """Was von einem Körper eine Lage übersteht — und woran ein Fehler auffällt."""

    name: str
    volume: float
    area: float
    extents: tuple[float, float, float] | None
    """Die Außenmaße, aufsteigend sortiert: Eine Drehung um eine Achse vertauscht
    sie nur. ``None`` für mehrere Körper in einem Netz, deren Abstände der
    Slicer beim Anordnen neu setzt."""
    triangles: int | None = None
    """``None`` bei einem exakten Körper — STEP trägt Flächen, keine Dreiecke."""

    @classmethod
    def of_mesh(cls, name: str, mesh: MeshData, *, scale: float = 1.0) -> BodyFigures:
        """Die Kennzahlen eines Netzes, auf Millimeter umgerechnet."""
        size = mesh.bounds.size
        ordered = sorted(float(value) * scale for value in size)
        return cls(
            name=name,
            volume=mesh.volume * scale * scale * scale,
            area=mesh.area * scale * scale,
            extents=(ordered[0], ordered[1], ordered[2]),
            triangles=mesh.triangle_count,
        )

    def agrees_with(self, other: BodyFigures) -> bool:
        """Dieselbe Form in der Grenze der Anzeige, gleich wo sie liegt."""
        if (
            self.triangles is not None
            and other.triangles is not None
            and self.triangles != other.triangles
        ):
            return False
        if (
            self.extents is not None
            and other.extents is not None
            and any(
                abs(a - b) > EPS_DISPLAY for a, b in zip(self.extents, other.extents, strict=True)
            )
        ):
            return False
        allowed = max(self.area, other.area) * EPS_DISPLAY
        return abs(self.volume - other.volume) <= allowed


@dataclass(frozen=True, slots=True)
class Readback:
    """Ergebnis der Gegenprobe: geprüft und gleich, geprüft und abweichend, oder nicht."""

    state: ReadbackState
    files: tuple[str, ...] = ()
    """Die Dateinamen, die tatsächlich erneut gelesen wurden."""
    expected: int = 0
    found: int = 0
    notes: tuple[TranslatableText, ...] = field(default_factory=tuple)
    """Abweichungen oder der Grund, warum nicht geprüft wurde."""

    def summary(self) -> TranslatableText:
        """Der eine Satz für den Übergabebeleg."""
        if self.state == "matched":
            return _(
                "Gegenprobe: {files} erneut eingelesen; {found} von {expected} Körpern "
                "mit gleicher Dreieckszahl, gleichem Volumen und gleichen Außenmaßen.",
                files=", ".join(self.files),
                found=self.found,
                expected=self.expected,
            )
        if self.state == "deviated":
            return _(
                "Gegenprobe: {files} erneut eingelesen; die Datei weicht vom Auftrag ab.",
                files=", ".join(self.files),
            )
        return _(
            "Gegenprobe nicht durchgeführt: {reason}",
            reason=self.notes[0] if self.notes else _("kein Grund gemeldet"),
        )


def expected_body(name: str, body: object, profile: Profile) -> BodyFigures:
    """Was von einem Szenenkörper in einer Netzdatei stehen sollte.

    Dieselben Dreiecke wie der Schreiber: ``writer.mesh_for_export`` vernetzt
    einen exakten Körper so fein, wie der Drucker es braucht.
    """
    from app.core.export.writer import mesh_for_export

    return BodyFigures.of_mesh(name, mesh_for_export(body, profile))  # type: ignore[arg-type]


def expected_in_file(
    path: Path, bodies: Sequence[tuple[str, object]], profile: Profile
) -> list[BodyFigures]:
    """Was eine Übergabedatei mit diesen Körpern tragen sollte.

    Eine 3MF hält jeden Körper einzeln. Ein einzelnes Netz (STL für ein
    Programm ohne Baugruppe) trägt alle als ein Netz; dort zählen Dreiecke
    und Volumen, die Außenmaße hängen an der Anordnung des Slicers.
    """
    figures = [expected_body(name, body, profile) for name, body in bodies]
    if path.suffix.lower() == ".3mf" or len(figures) < 2:
        return figures
    return [
        BodyFigures(
            name=", ".join(figure.name for figure in figures),
            volume=sum(figure.volume for figure in figures),
            area=sum(figure.area for figure in figures),
            extents=None,
            triangles=sum(figure.triangles or 0 for figure in figures),
        )
    ]


def read_back_bodies(
    files: Sequence[tuple[Path, Sequence[tuple[str, object]]]],
    profile: Profile,
    *,
    cancelled: CancelToken | None = None,
) -> Readback:
    """Die Gegenprobe einer Übergabe: je Datei die Szenenkörper, die darin stehen."""
    try:
        expected = [(path, expected_in_file(path, bodies, profile)) for path, bodies in files]
    except AppError:
        # Ohne Sollwerte keine Gegenprobe — gesagt, nicht verschwiegen.
        return not_performed(_("Die Kennzahlen der übergebenen Körper ließen sich nicht lesen."))
    return read_back(expected, cancelled=cancelled)


def expected_solid(name: str, body: object) -> BodyFigures:
    """Was von einem exakten Körper in einer STEP-Datei stehen sollte."""
    size = sorted(float(value) for value in body.bounds.size)  # type: ignore[attr-defined]
    return BodyFigures(
        name=name,
        volume=float(body.volume),  # type: ignore[attr-defined]
        area=float(body.area),  # type: ignore[attr-defined]
        extents=(size[0], size[1], size[2]),
    )


def expected_for_plan(
    plan: ExportPlan, written: Sequence[Path], export_format: str
) -> list[tuple[Path, list[BodyFigures]]]:
    """Je geschriebener Datei eines Plans der Körper, der darin steht.

    ``write_plan`` lässt bei STEP Körper ohne Flächen aus; zugeordnet wird
    deshalb über den Dateinamen, nicht über die Reihenfolge.
    """
    by_name = {entry.filename: entry for entry in plan.entries}
    pairs: list[tuple[Path, list[BodyFigures]]] = []
    for path in written:
        entry = by_name.get(path.name)
        if entry is None:
            continue
        if export_format == "step" and entry.body is not None:
            pairs.append((path, [expected_solid(entry.name, entry.body)]))
        else:
            pairs.append((path, [BodyFigures.of_mesh(entry.name, entry.mesh)]))
    return pairs


def not_performed(reason: TranslatableText) -> Readback:
    """Ausdrücklich nicht geprüft, mit Grund — nie still ausgelassen."""
    return Readback("not_performed", notes=(reason,))


def read_back(
    expected: Sequence[tuple[Path, Sequence[BodyFigures]]],
    *,
    cancelled: CancelToken | None = None,
) -> Readback:
    """Liest jede geschriebene Datei erneut und vergleicht sie mit ihrem Auftrag.

    ``expected`` nennt je Datei die Körper, die darin stehen sollten. Eine
    Datei, die sich nicht lesen lässt, ist eine Abweichung, keine
    ausgelassene Prüfung: Genau das soll die Gegenprobe finden.
    """
    if not expected:
        return not_performed(_("Es wurde keine Datei geschrieben."))
    files: list[str] = []
    notes: list[TranslatableText] = []
    wanted = 0
    found = 0
    for path, bodies in expected:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        files.append(path.name)
        wanted += len(bodies)
        suffix = path.suffix.lower()
        if suffix not in _MESH_SUFFIXES and suffix not in (".step", ".stp"):
            return not_performed(
                _(
                    "Dateien im Format {format} liest Solidon nicht zurück.",
                    format=suffix.lstrip(".").upper(),
                )
            )
        try:
            read = _figures_in(path)
        except AppError:
            read = []
        except OSError:
            notes.append(_("„{file}“ ließ sich nicht wieder öffnen.", file=path.name))
            continue
        if read == []:
            # Eine geschriebene Datei trägt immer mindestens einen Körper.
            notes.append(_("„{file}“ ließ sich nicht wieder einlesen.", file=path.name))
            continue
        if read is None:
            return not_performed(_("Für STEP fehlt der Rechenkern mit echten Flächen und Kanten."))
        found += len(read)
        notes.extend(_compared(path.name, bodies, read))
    return Readback(
        "deviated" if notes else "matched",
        files=tuple(files),
        expected=wanted,
        found=found,
        notes=tuple(notes),
    )


def _figures_in(path: Path) -> list[BodyFigures] | None:
    """Die Körper einer Datei, gelesen wie beim Import; ``None`` ohne STEP-Kern."""
    payload = path.read_bytes()
    suffix = path.suffix.lower()
    if suffix in (".step", ".stp"):
        from app.core.brep import available

        if not available():
            return None
        from app.core.brep import step

        solid = step.read(payload)
        size = sorted(float(value) for value in solid.bounds.size)
        return [
            BodyFigures(
                name=path.stem,
                volume=float(solid.volume),
                area=float(solid.area),
                extents=(size[0], size[1], size[2]),
            )
        ]
    if suffix == ".3mf":
        from app.core.ingest import threemf

        # Eine leere Liste heißt beim Leser „keine lesbare 3MF“; der Import
        # fiele dann auf trimesh zurück, die Gegenprobe meldet sie.
        parts = threemf.read_objects(payload, printable_only=True)
        return [BodyFigures.of_mesh(part.name, part.mesh) for part in parts]
    from app.core.geom.mesh import read_mesh

    scale = _MM_PER_GLTF_UNIT if suffix == ".glb" else 1.0
    return [BodyFigures.of_mesh(path.stem, read_mesh(payload, suffix), scale=scale)]


def _compared(
    file: str, wanted: Sequence[BodyFigures], read: Sequence[BodyFigures]
) -> list[TranslatableText]:
    """Ordnet jedem erwarteten Körper einen gelesenen zu; was übrig bleibt, weicht ab."""
    left = list(read)
    notes: list[TranslatableText] = []
    for body in wanted:
        partner = next((index for index, other in enumerate(left) if body.agrees_with(other)), None)
        if partner is None:
            notes.append(
                _(
                    "„{name}“ steht in „{file}“ nicht so, wie er geschrieben werden sollte.",
                    name=body.name,
                    file=file,
                )
            )
            continue
        left.pop(partner)
    extra = len(read) - len(wanted)
    if extra > 0:
        notes.append(
            _(
                "„{file}“ enthält {count} Körper mehr als der Auftrag.",
                file=file,
                count=extra,
            )
        )
    return notes
