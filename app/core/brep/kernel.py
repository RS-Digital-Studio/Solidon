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

from dataclasses import dataclass, field
from typing import Any, cast

from app.core.errors import CANCEL, INSTALL_MISSING, AppError
from app.core.geom.mesh import MeshData
from app.core.log import get_logger
from app.core.types import BoundingBox
from app.core.units import EPS_GEOM
from app.i18n import _

_log = get_logger(__name__)

#: Wie weit die Tessellation von der echten Oberfläche abweichen darf, in mm.
#: Fein genug, dass eine Verrundung auf dem Bildschirm rund aussieht, grob
#: genug, dass eine STEP-Baugruppe nicht als Million Dreiecke ankommt (§31).
DEFLECTION = 0.05

#: Winkelabweichung im Bogenmaß, aus demselben Grund.
ANGULAR_DEFLECTION = 0.3


class BRepUnavailable(AppError):
    """Der B-Rep-Kern ist nicht installiert."""

    default_title = _("Der B-Rep-Kern ist auf diesem Rechner nicht installiert.")
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
                "Fasen, Verrundungen und STEP brauchen OpenCASCADE. "
                "Alles andere in Solidon funktioniert ohne."
            )
        )


def _same_point(a: tuple[float, float, float], b: tuple[float, float, float]) -> bool:
    """Ob zwei Knoten praktisch zusammenfallen — für den Degeneriert-Test.

    Millimeter gegen ``EPS_GEOM``: identische Koordinaten liegen erst recht
    darunter, der Bestand bleibt also unverändert grün.
    """
    return (
        abs(a[0] - b[0]) <= EPS_GEOM
        and abs(a[1] - b[1]) <= EPS_GEOM
        and abs(a[2] - b[2]) <= EPS_GEOM
    )


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


@dataclass(frozen=True, slots=True)
class Solid:
    """Ein B-Rep-Körper. Erfüllt das ``Mesh``-Protokoll, indem er sich selbst
    tesselliert.
    """

    shape: Any
    """``TopoDS_Shape``. Absichtlich lose typisiert — die Anbindung ist optional."""
    deflection: float = DEFLECTION
    _cache: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    # --- die exakten Antworten --------------------------------------------------

    @property
    def volume(self) -> float:
        """Aus dem Kern, nicht aus den Dreiecken — das ist der ganze Punkt."""
        return float(self._properties("volume").Mass())

    @property
    def area(self) -> float:
        return float(self._properties("surface").Mass())

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
        from OCP.TopAbs import TopAbs_SOLID
        from OCP.TopExp import TopExp
        from OCP.TopTools import TopTools_IndexedMapOfShape

        found = TopTools_IndexedMapOfShape()
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

    # --- die tessellierten Antworten --------------------------------------------

    @property
    def mesh(self) -> MeshData:
        """Die Dreiecke. Einmal gemacht, und nie in die Form zurückgespeist."""
        cached = self._cache.get("mesh")
        if cached is None:
            cached = tessellate(self.shape, self.deflection)
            self._cache["mesh"] = cached
        return cast(MeshData, cached)

    def to_mesh(self) -> MeshData:
        """Die Einbahntür aus §30. Ausdrücklich, denn der Rückweg ist zu."""
        return self.mesh

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
        low_x, low_y, low_z, high_x, high_y, high_z = box.Get()
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

    def replacing(self, shape: Any) -> Solid:
        """Ein neuer Körper um eine geänderte Form, in derselben
        Tessellationsqualität.
        """
        return Solid(shape=shape, deflection=self.deflection)

    # --- inside ------------------------------------------------------------------

    def _properties(self, kind: str) -> Any:
        cached = self._cache.get(kind)
        if cached is not None:
            return cached
        from OCP.BRepGProp import BRepGProp
        from OCP.GProp import GProp_GProps

        props = GProp_GProps()
        if kind == "volume":
            BRepGProp.VolumeProperties_s(self.shape, props)
        else:
            BRepGProp.SurfaceProperties_s(self.shape, props)
        self._cache[kind] = props
        return props

    def _explore(self, kind: str) -> list[Any]:
        """Topologie-Entitäten, entdoppelt — ein Explorer besucht Kanten je Fläche."""
        cached = self._cache.get(f"list:{kind}")
        if cached is not None:
            return list(cached)
        from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
        from OCP.TopExp import TopExp
        from OCP.TopoDS import TopoDS
        from OCP.TopTools import TopTools_IndexedMapOfShape

        found = TopTools_IndexedMapOfShape()
        TopExp.MapShapes_s(self.shape, TopAbs_FACE if kind == "face" else TopAbs_EDGE, found)
        # Die Karte gibt nackte Formen zurück; alles danach will den echten
        # Typ, und ein falscher Cast hier scheitert erst viel weiter weg.
        as_typed = TopoDS.Face_s if kind == "face" else TopoDS.Edge_s
        entities = [as_typed(found.FindKey(index)) for index in range(1, found.Extent() + 1)]
        self._cache[f"list:{kind}"] = entities
        return list(entities)


def tessellate(shape: Any, deflection: float = DEFLECTION) -> MeshData:
    """Dreiecke für eine Form, fein genug, dass eine Verrundung rund wirkt."""
    import numpy as np
    import trimesh
    from OCP.BRep import BRep_Tool
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS

    BRepMesh_IncrementalMesh(shape, deflection, False, ANGULAR_DEFLECTION, True)

    points: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        face = TopoDS.Face_s(explorer.Current())
        location = TopLoc_Location()
        triangulation = BRep_Tool.Triangulation_s(face, location)
        explorer.Next()
        if triangulation is None:
            continue

        transform = location.Transformation()
        offset = len(points)
        for index in range(1, triangulation.NbNodes() + 1):
            node = triangulation.Node(index).Transformed(transform)
            points.append((node.X(), node.Y(), node.Z()))

        reversed_face = face.Orientation() == TopAbs_REVERSED
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

    if not faces:
        return MeshData.of(trimesh.Trimesh())
    body = trimesh.Trimesh(
        vertices=np.asarray(points, dtype=float),
        faces=np.asarray(faces, dtype=np.int64),
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
