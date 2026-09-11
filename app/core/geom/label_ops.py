"""Text und Logos auf einer Fläche (Bauplan §25, Kategorie „Beschriftung").

Ein Teil mit seiner Größe darauf, ein Deckel mit dem, was in die Box gehört,
eine Halterung mit dem Datum ihres Drucks: der häufigste Grund, warum Leute
ein Modellierprogramm verlassen und ein zweites öffnen. Es braucht kein
zweites.

Die Buchstaben kommen als Umrisse aus der Schrift, nicht als nachgezeichnetes
Bild — die Kanten bleiben also in jeder Größe sauber, und ein erhabener
Buchstabe hat eine ebene Oberseite statt einer Treppe. Alles danach ist
dieselbe Vereinigung oder Differenz, die jeder andere Baustein auch
benutzt (§24.1).

Die andere Hälfte ist ein Logo, und das kommt als SVG durch dieselbe Tür: Ein
Umriss ist ein Umriss, ob ihn eine Schrift gezeichnet hat oder Inkscape.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final, Literal, cast

import numpy as np

from app.core.deferred import trimesh
from app.core.errors import ValidationError
from app.core.geom.attributes import with_slot
from app.core.geom.boolean import (
    BOOLEAN_OVERLAP,
    BooleanKind,
    boolean,
    fell_apart,
    without_effect,
)
from app.core.geom.mesh import MeshData, as_mesh_data, concatenated
from app.core.geom.transform import apply, rotation, translation
from app.core.log import get_logger
from app.core.registry import NAME_DOC, op_params, param, register_op
from app.core.types import (
    MAX_SLOTS,
    BaseParams,
    Finding,
    MaterialSlot,
    OpContext,
    OpResult,
    Profile,
    SceneObject,
    Vec3,
)
from app.core.units import DEGREE_UNIT, EPS_GEOM, format_length, format_volume
from app.i18n import _

_log = get_logger(__name__)

Placement = Literal["raised", "engraved"]

#: Ab welchem Anteil der Buchstaben, der **nicht** über der Fläche steht, die
#: Schrift als versenkt gilt. Die Hälfte: Eine Schrift, die halb im Körper
#: steckt, ist keine Beschriftung mehr — und eine, die zu einem Zehntel
#: eintaucht, kann eine gewollte Prägung auf schräger Fläche sein.
LABEL_BURIED_SHARE: Final = 0.5

#: Die Schriften, die immer da sind. matplotlib bringt DejaVu selbst mit, eine
#: Beschriftung sieht also auf jedem Rechner gleich aus — eine Systemschrift,
#: die es auf einem Rechner gibt und auf dem nächsten nicht, ist ein Projekt,
#: das sich unterschiedlich öffnet.
FONTS: tuple[str, ...] = (
    "DejaVu Sans",
    "DejaVu Serif",
    "DejaVu Sans Mono",
    "Liberation Sans",
    "Liberation Serif",
    "Liberation Mono",
    "Comfortaa",
    "Dancing Script",
)

#: Welche Familie welche Schnitte wirklich hat — und was ohne diese Tabelle
#: passiert wäre.
#:
#: Comfortaa und Dancing Script kommen als **variable** Schriften: eine Datei
#: mit einer Gewichtsachse, aus der sich jeder Schnitt rechnen ließe. Nur kann
#: matplotlib das nicht; es nimmt die Standardinstanz und meldet „Failed to
#: find font weight bold, now using 400" auf die Fehlerausgabe. Gemessen am
#: 10.09.2026 an „ABCabc 123" auf 10 mm: Bei den sechs statischen Familien
#: wächst die mittlere Strichbreite von 0,61 bis 0,84 mm auf 0,92 bis 1,44 mm, bei
#: diesen beiden bleibt sie auf 0,70 beziehungsweise 0,48 — vier Einträge im
#: Dialog, ein Ergebnis.
#:
#: **Der Riegel in** :func:`font_properties` **hätte das nicht gefangen**: Er
#: prüfte die Familie, und die ist ja da. Ein Schnitt, den es nicht gibt, ist
#: dieselbe stille Lüge eine Ebene tiefer.
FONT_STYLES_AVAILABLE: Final[dict[str, tuple[str, ...]]] = {
    "Comfortaa": ("regular",),
    "Dancing Script": ("regular",),
}

#: Die Familien, bei denen das Feld *Schnitt* etwas bewirkt.
#:
#: Aus :data:`FONTS` abzüglich derer, die nur einen Schnitt mitbringen — der
#: Dialog graut das Feld damit aus, statt eine Wahl anzubieten, die
#: :func:`font_properties` gleich danach ablehnt. Eine neue variable Schrift
#: braucht nur ihren Eintrag in :data:`FONT_STYLES_AVAILABLE`; hier fällt sie
#: von selbst heraus.
FONTS_WITH_ALL_STYLES: Final[tuple[str, ...]] = tuple(
    font for font in FONTS if font not in FONT_STYLES_AVAILABLE
)

#: Wo die mitgelieferten Schriften liegen, die matplotlib nicht selbst kennt.
#:
#: **Liberation, und zwar aus einem Grund, der nichts mit Geschmack zu tun
#: hat:** Die drei Familien sind metrisch kompatibel zu Arial, Times New Roman
#: und Courier New — dieselben Zeichenbreiten, dieselbe Zeilenlänge. Wer eine
#: Beschriftung „in Arial" erwartet, bekommt sie, ohne dass eine Schrift ins
#: Paket muss, die niemand weitergeben darf.
#:
#: **Comfortaa und Dancing Script aus dem entgegengesetzten Grund:** Die sechs
#: übrigen Familien haben eckige Ecken und gerade Striche, weil sie für
#: Fließtext auf einem Bildschirm gezeichnet sind. Eine runde und eine
#: geschriebene daneben decken ab, wofür sonst jemand das Programm verlässt.
#:
#: Vierzehn Dateien und gut viereinhalb Megabyte: zwölf für Liberation, weil
#: jede der drei Familien ihre vier Schnitte mitbringt, und je eine für die
#: beiden variablen. Drei Regular allein wären billiger und wären eine Falle:
#: Der Schnitt stünde dann bei DejaVu zur Wahl und bei Liberation nicht, ohne
#: dass es jemand sähe — matplotlib fällt still zurück
#: (:func:`font_properties`).
#:
#: Alle drei stehen unter der SIL Open Font License 1.1; welcher Text zu
#: welcher Sippe gehört, sagt :data:`BUNDLED_FONT_LICENCES`.
BUNDLED_FONTS: Final[Path] = Path(__file__).parent / "data" / "fonts"

#: Welche mitgelieferte Schriftsippe unter welchem Lizenztext steht.
#:
#: **Eine Tabelle und kein Namensraten.** Der erste Anlauf las die Sippe aus
#: dem Dateinamen — ``LiberationMono-Bold.ttf`` vor dem ersten Bindestrich
#: ergibt ``LiberationMono``, und danach suchte der Wächter einen Lizenztext,
#: den es unter diesem Namen nicht gibt. Die Zuordnung ist eine Aussage, keine
#: Zeichenkettenoperation: Wer eine Schrift dazulegt, trägt sie hier ein, und
#: ``tests/test_licences.py`` verlangt beides — den Eintrag und die Datei.
#:
#: **Die Fassung im Dateinamen ist eine Zusage.** Sie stand zweimal daneben —
#: Comfortaa liegt als 3.105 bei und hieß 3.101, Dancing Script als 2.001 und
#: hieß 2.104 —, und niemandem wäre es aufgefallen: Der Name einer Textdatei
#: wird von nichts gelesen. ``tests/test_licences.py`` hält ihn seit dem
#: 10.09.2026 gegen den Versionseintrag in der Schriftdatei selbst.
BUNDLED_FONT_LICENCES: Final[dict[str, str]] = {
    "Liberation": "Liberation-2.1.5-OFL-1.1.txt",
    "Comfortaa": "Comfortaa-3.105-OFL-1.1.txt",
    "DancingScript": "DancingScript-2.001-OFL-1.1.txt",
}

_registered = False


def _register_bundled_fonts() -> None:
    """Die mitgelieferten Schriften einmal je Prozess bei matplotlib anmelden.

    Ohne das findet ``findfont`` sie nicht: Es sucht in den Systemordnern und
    im eigenen Datenverzeichnis, und ein Ordner in der Anwendung ist beides
    nicht. ``addfont`` trägt eine Datei in den laufenden Fontmanager ein, ohne
    seinen Zwischenspeicher auf der Platte anzufassen.

    **Einmal je Prozess**, denn ``addfont`` liest jede Datei und legt sie in
    die Liste — vierzehn Dateien bei jedem Aufruf von :func:`outlines` wären
    vierzehn Dateizugriffe je Buchstabengruppe.
    """
    global _registered
    if _registered:
        return
    from matplotlib import font_manager

    for entry in sorted(BUNDLED_FONTS.glob("*.ttf")):
        font_manager.fontManager.addfont(str(entry))
    _registered = True


#: Die Schnitte, die jede dieser Familien mitbringt — und die bis zum
#: 10.09.2026 niemand anbieten konnte.
#:
#: Sie liegen längst im Paket: matplotlib führt zu jeder statischen Familie
#: vier Dateien (regular, bold, oblique, bold-oblique), und ``FONTS`` nannte
#: nur die erste. Aus sechs Familien werden damit vierundzwanzig Kombinationen,
#: ohne ein Byte mehr; die beiden variablen bleiben bei je einer
#: (:data:`FONT_STYLES_AVAILABLE`).
#:
#: **Fett ist dabei kein Geschmack, sondern eine Drucksache.** Die
#: Untergrenze von :data:`MIN_SIZE` steht bei drei Millimetern, weil dünne
#: Striche unter einer Düsenbreite verschmieren; ein fetter Schnitt hält
#: dieselbe Höhe mit dickeren Strichen aus und bleibt lesbar, wo der normale
#: schon zerfällt.
#:
#: Als **zweiter Parameter** und nicht als sechsundzwanzig Einträge in einer
#: Liste: Der Kunde wählt eine Schrift und danach, wie sie aussehen soll — zwei
#: kurze Listen statt einer langen, und mit jeder weiteren Familie wächst nur
#: die erste. Der Schlüssel ist englisch, weil er in der Projektdatei steht.
FONT_STYLES: Final[tuple[str, ...]] = ("regular", "bold", "italic", "bold_italic")

#: Was ein Schnitt für ``FontProperties`` bedeutet: Gewicht und Neigung.
_STYLE_PROPERTIES: Final[dict[str, tuple[str, str]]] = {
    "regular": ("normal", "normal"),
    "bold": ("bold", "normal"),
    # ``oblique`` und nicht ``italic``: DejaVu führt geneigte Schnitte, keine
    # echten kursiven. Wer hier ``italic`` verlangt, bekommt von matplotlib
    # den geneigten — aber über einen Rückfall, und ein Rückfall, der zufällig
    # das Richtige trifft, ist keine Zusage.
    "italic": ("normal", "oblique"),
    "bold_italic": ("bold", "oblique"),
}

#: Erklärungen, die beide Beschriftungs-Operationen teilen.
_WHERE = _("Wo die Schrift sitzt. Eine angeklickte Fläche trägt Ort und Richtung selbst ein.")
_WHERE_MORE = _("Weitere Achse des Orts — siehe Position X.")
_FACING = _(
    "Richtung, in die die Schrift zeigt. Aus einer angeklickten Fläche kommt sie "
    "von selbst; von Hand ist 0/0/1 nach oben."
)
_FACING_MORE = _("Weitere Achse der Richtung — siehe Normale X.")
_SIZE = _("Höhe der Großbuchstaben. Unter drei Millimetern verliert der Druck die Form.")
_FONT = _("Alle acht liegen bei, damit ein Projekt auf jedem Rechner gleich aussieht.")
_STYLE = _(
    "Fett trägt bei kleinen Buchstaben dickere Striche und bleibt lesbar, wo der "
    "normale Schnitt schon verschmiert."
)

#: Darunter lohnt die Beschriftung auf keiner Maschine mehr.
#:
#: **Eine Zahl für jeden Drucker, und deshalb keine Aussage über den Druck.**
#: Ein Parameterschema kennt das Profil nicht; seine Grenze muss für die feinste
#: und die gröbste Düse zugleich gelten und ist damit für beide falsch. Gemessen
#: am 10.09.2026 an „SOLIDON3D": Drei Millimeter trägt eine 0,25er Düse bei
#: sechs der acht Familien; mit der üblichen 0,4er trägt dort kein normaler
#: Schnitt mehr, sondern nur noch fette — und auch die nicht alle.
#:
#: Die Auskunft, auf die es ankommt, gibt darum nicht diese Zahl, sondern
#: :func:`too_thin_to_print`: Sie kennt Schrift, Schnitt, Höhe und Düse und
#: nennt die Höhe, ab der es trägt. Gesperrt wird deswegen nichts — wer ein
#: Schild nur ansehen will, darf es klein haben.
MIN_SIZE = 3.0


def stroke_width(shapes: Sequence[Any]) -> float:
    """Wie breit die Striche dieses Textes im Mittel sind, in Millimetern.

    Doppelte Fläche durch Umfang — für einen langen Streifen ist das genau
    seine Breite, und ein Buchstabe ist nichts anderes als ein paar gebogene
    Streifen. Die Zahl skaliert linear mit der Schrifthöhe.

    **Am gesetzten Text gemessen und nicht je Familie hinterlegt.** Eine
    Tabelle hätte an einem Beispielwort gehangen („ABCabc 123"), und der Kunde
    schreibt ein anderes: Dieselbe Familie kommt auf 0,84 mm für dieses Wort
    und auf 0,90 mm für „SOLIDON3D", weil Versalien dickere Striche haben als
    Gemeine. Sie hätte außerdem den Schnitt verschwiegen — fett ist rund
    anderthalbmal so breit wie normal (gemessen am 10.09.2026 über alle sechs
    statischen Familien) —, und genau das ist die Auskunft, auf die es
    ankommt.

    **Das Mittel und nicht die dünnste Stelle**, und das ist eine
    Entscheidung: Eine Antiqua hat Haarstriche neben Stämmen. Gemessen an
    „ABCabc 123" auf 10 mm, über die Öffnung mit wachsendem Radius: Bei
    Liberation Serif verlieren schon bei einer Bahn von 0,40 mm die ersten fünf
    Prozent der Fläche ihre Spur, während das Mittel derselben Zeile bei
    0,61 mm liegt. Wer die dünnste Stelle nähme, meldete jede Serifenschrift
    bei jeder üblichen Größe. Gefragt ist, ob das Schriftbild hält, nicht ob
    der erste Haarstrich breiter gedruckt wird als gezeichnet.
    """
    from shapely.ops import unary_union

    whole = unary_union(list(shapes))
    around = float(whole.length)
    if around <= EPS_GEOM:
        return 0.0
    return 2.0 * float(whole.area) / around


def narrowest_bead(profile: Profile) -> float:
    """Die schmalste Bahn, die dieser Drucker legt, in Millimetern.

    Nicht der Düsendurchmesser: Ein Slicer quetscht eine Bahn bis auf
    ``NARROW_LINE_SHARE`` seiner Düse zusammen, darunter reißt die Spur ab,
    statt dünner zu werden. Die Zahl steht in :mod:`app.core.slice.advise` und
    wird von dort geholt, weil zwei Schwellen für dieselbe Frage dazwischen
    einen Bereich ließen, in dem beide Antworten falsch sind — der Kommentar
    dort sagt es für die andere Seite mit denselben Worten.
    """
    from app.core.slice.advise import NARROW_LINE_SHARE

    return NARROW_LINE_SHARE * profile.printer.nozzle_diameter


def too_thin_to_print(shapes: Sequence[Any], size: float, line_width: float) -> float | None:
    """Ab welcher Höhe dieser Text eine Bahn trägt — ``None``, wenn er es tut.

    **Die Grenze gehört der Düse und nicht der Schrift.** Dieselbe
    Schreibschrift, die mit einer 0,25er Düse sauber kommt, läuft mit einer
    0,8er zu; eine feste Mindesthöhe je Familie wäre auf der einen Maschine zu
    streng und auf der anderen zu milde. Gerechnet wird deshalb aus der
    gemessenen Strichbreite (linear in der Höhe) gegen die schmalste Bahn, die
    dieser Drucker wirklich legt (:func:`narrowest_bead`).

    Gemessen am 10.09.2026 an „SOLIDON3D": „Dancing Script" hat bei 10 mm eine
    mittlere Strichbreite von 0,51 mm. Auf einer 0,4er Düse — schmalste Bahn
    0,34 mm — trägt sie ab **6,6 mm**; auf einer 0,25er ab 4,1 mm, auf einer
    0,8er erst ab 13,2 mm. Dieselbe Schrift, drei Antworten.

    Zurück kommt die nötige Höhe, damit der Aufrufer sie nennen kann; ein Satz
    „zu dünn" ohne Zahl schickt den Kunden ins Raten (Regel 17).
    """
    stroke = stroke_width(shapes)
    if stroke <= EPS_GEOM or line_width <= EPS_GEOM or stroke >= line_width:
        return None
    return size * line_width / stroke


def font_properties(font: str, style: str = FONT_STYLES[0]) -> Any:
    """Familie und Schnitt als ``FontProperties`` — und die Zusage, dass es sie gibt.

    **matplotlib fällt still zurück.** Wer eine Schrift verlangt, die auf dem
    Rechner fehlt, bekommt keine Ausnahme, sondern DejaVu Sans und eine Zeile
    auf der Fehlerausgabe. Gemessen am 10.09.2026: ``family="Liberation Sans"``
    löst auf einem Rechner ohne Liberation nach ``DejaVuSans.ttf`` auf, und
    ``family="Arial"`` findet auf Windows Arial und sonst nirgends — genau das
    Projekt, „das sich unterschiedlich öffnet", vor dem der Kommentar an
    :data:`FONTS` warnt.

    Solange nur mitgelieferte Familien zur Wahl stehen, kann das nicht
    eintreten. Es bleibt trotzdem eine Zusage, die niemand einlöste — und eine
    mitgelieferte Schrift, die es aus einem Paketfehler nicht ins Paket
    schafft, fiele lautlos auf DejaVu zurück (Regel 21).
    """
    from matplotlib.font_manager import FontProperties, findfont, get_font

    _register_bundled_fonts()
    # **Und der Schnitt gehört zur selben Frage.** Eine variable Schrift bringt
    # nur ihre Standardinstanz mit; „fett" liefert dieselben Umrisse, und
    # matplotlib sagt es auf einer Fehlerausgabe, die niemand liest.
    offered = FONT_STYLES_AVAILABLE.get(font)
    if offered is not None and style not in offered:
        raise ValidationError(
            field="style",
            detail=_(
                "„{font}“ gibt es nur in einem Schnitt. Wählen Sie „Normal“, oder "
                "nehmen Sie eine Schrift, die fett und kursiv mitbringt.",
                font=font,
            ),
            value=style,
            constraint="missing_style",
        )
    weight, slant = _STYLE_PROPERTIES.get(style, _STYLE_PROPERTIES[FONT_STYLES[0]])
    # ``slant`` stammt aus :data:`_STYLE_PROPERTIES` und ist dort immer einer
    # der drei Werte, die matplotlib kennt; der Parameter selbst kommt als
    # ``str`` aus dem Schema, und diese Kenntnis hat mypy nicht.
    prop = FontProperties(
        family=font, weight=weight, style=cast(Literal["normal", "italic", "oblique"], slant)
    )
    # **Die Datei wird nach ihrer Familie gefragt, nicht nach ihrem Namen.**
    # Der erste Anlauf verglich das erste Wort mit dem Dateinamen — „DejaVu
    # Serif" fand „dejavu" in ``DejaVuSans.ttf`` und war zufrieden, also fing
    # der Riegel genau den Fall nicht, für den er gebaut ist: den Rückfall
    # innerhalb derselben Sippe. ``get_font`` liest den Familiennamen aus dem
    # ``name``-Table der gefundenen Datei und beantwortet damit die gestellte
    # Frage; nebenbei fällt jede Vermutung über Dateinamen weg, die auf einer
    # fremden Distribution ohnehin anders lauten dürfen.
    found = get_font(findfont(prop)).family_name
    if found.casefold() != font.casefold():
        raise ValidationError(
            field="font",
            detail=_(
                "Die Schrift „{font}“ ist auf diesem Rechner nicht zu finden. "
                "Wählen Sie eine der mitgelieferten — dann sieht das Projekt "
                "überall gleich aus.",
                font=font,
            ),
            value=font,
            constraint="missing_font",
        )
    return prop


def outlines(
    text: str, size: float, font: str = FONTS[0], style: str = FONT_STYLES[0]
) -> list[Any]:
    """Die Buchstaben als Polygone, in Millimetern, auf dem Ursprung sitzend."""
    from matplotlib.textpath import TextPath
    from shapely.geometry import Polygon as ShapelyPolygon
    from shapely.ops import unary_union

    path = TextPath((0.0, 0.0), text, size=size, prop=font_properties(font, style))
    rings = [np.asarray(entry, dtype=float) for entry in path.to_polygons()]
    rings = [entry for entry in rings if len(entry) >= 4]
    if not rings:
        return []

    # Ein Buchstabe wie „o" kommt als zwei Ringe, und welcher das Loch ist,
    # folgt aus der Enthaltung, nicht aus der Reihenfolge des Zeichnens.
    shapes = [ShapelyPolygon(entry).buffer(0) for entry in rings]
    solid = None
    for shape in sorted(shapes, key=lambda entry: -entry.area):
        solid = shape if solid is None else solid.symmetric_difference(shape)
    merged = unary_union([solid]) if solid is not None else None
    if merged is None or merged.is_empty:
        return []
    return [entry for entry in getattr(merged, "geoms", [merged]) if entry.area > EPS_GEOM]


def label_solid(shapes: list[Any], depth: float) -> MeshData | None:
    """Ein Körper aus den Umrissen, stehend auf Z = 0."""
    parts = [
        trimesh.creation.extrude_polygon(shape, height=depth)
        for shape in shapes
        if shape.area > EPS_GEOM
    ]
    if not parts:
        return None
    return MeshData.of(concatenated(parts))


def local_text_body(
    text: str,
    size: float,
    font: str,
    depth: float,
    *,
    style: str = FONT_STYLES[0],
    mode: Literal["raised", "engraved", "body"] = "body",
    angle: float = 0.0,
) -> MeshData:
    """Dieselben zentrierten Buchstaben für Operation und Platzierungsvorschau."""
    if not text.strip():
        raise ValidationError(
            field="text", detail=_("Ohne Text gibt es nichts aufzubringen."), constraint="empty"
        )
    shapes = outlines(text, size, font, style)
    height = depth + (BOOLEAN_OVERLAP if mode != "body" else 0.0)
    body = label_solid(shapes, height) if shapes else None
    if body is None:
        raise ValidationError(
            field="text",
            detail=_("Aus diesem Text ließ sich keine Form bilden."),
            value=text,
            constraint="no_outline",
        )
    middle = body.bounds.centre
    lift = -BOOLEAN_OVERLAP if mode == "raised" else -depth if mode == "engraved" else 0.0
    result = apply(body, translation((-middle[0], -middle[1], lift)))
    return apply(result, rotation("z", angle)) if angle else result


def place(body: MeshData, position: Vec3, normal: Vec3, angle: float = 0.0) -> MeshData:
    """Legt eine Beschriftung, die auf +Z steht, auf eine Fläche mit der
    gegebenen Normalen — **aufrecht, wie man sie liest.**

    Bis zum 02.09.2026 richtete allein ``align_vectors`` die Normale aus und
    ließ die Drehung *um* sie dem Zufall der gewählten Rotation: Auf der
    Vorderseite der Beispieldose lag „SOLIDON3D" quer, die Leserichtung auf
    der Welt-z-Achse (gemessen: 4,5 mm breit, 35 mm hoch). Wer eine
    Seitenwand beschriftet, hätte jedes Mal den Winkel nachgedreht.

    Auf einer Fläche, die nicht Decke oder Boden ist, steht der Text jetzt so,
    dass seine Zeile waagerecht liegt und sein Oben nach oben zeigt — für
    einen Betrachter, der von außen auf die Fläche sieht, liest er von links
    nach rechts. Decke und Boden behalten ihre Lage: Dort gibt es kein
    „oben", und ``angle`` ist der Weg, den Text zu drehen.
    """
    placed = body
    if angle:
        placed = apply(placed, rotation("z", angle))

    direction = np.asarray(normal, dtype=float)
    length = float(np.linalg.norm(direction))
    if length > EPS_GEOM:
        from app.core.sketch.planes import frame_of

        outward = direction / length
        frame = frame_of((float(outward[0]), float(outward[1]), float(outward[2])), position)
        matrix = np.eye(4)
        matrix[:3, :3] = np.column_stack((frame.x_axis, frame.y_axis, frame.normal))
        turned = placed.raw.copy()
        turned.apply_transform(matrix)
        placed = placed.replacing(turned)
    return apply(placed, translation(position))


@op_params
class LabelParams(BaseParams):
    text: str = param(
        title=_("Text"),
        # **Kein Vorgabewert, und das ist die Aussage.** Mit ``default=""``
        # meldete das Schema den Parameter als *freiwillig* — an drei
        # Oberflächen zugleich: Der Agent durfte die Operation ohne Text
        # vorschlagen, die Kommandozeile ihn weglassen, und der Dialog bot
        # Übernehmen an, um danach abzulehnen (Regel 19). Ohne Vorgabe steht
        # die Pflicht im Schema, wo alle drei sie lesen. Der Satz der
        # Operation bleibt die zweite Hürde: Der Dialog übergibt jedes Feld,
        # auch das leere, also greift er wie bisher.
        doc=_("Was daraufstehen soll."),
    )
    size: float = param(
        title=_("Schriftgröße"),
        default=8.0,
        unit="mm",
        minimum=MIN_SIZE,
        maximum=200.0,
        doc=_SIZE,
    )
    depth: float = param(
        title=_("Tiefe"),
        default=0.6,
        unit="mm",
        minimum=0.1,
        maximum=10.0,
        # **Drei Schichten sind der Wert, der stimmt.** 0,6 mm bei 0,2 mm
        # Schichthöhe deckt erhaben wie vertieft; wer daran dreht, tut es
        # einmal für einen Sonderfall. §2.4 will vorn „die zwei bis drei Werte,
        # die man tatsächlich ändert" — und das sind hier der Text, die Größe
        # und die Art.
        placement="advanced",
        doc=_("Wie weit erhaben oder wie tief eingelassen."),
    )
    mode: str = param(
        title=_("Art"),
        default="raised",
        choices=("raised", "engraved"),
        # **Er sagt die Richtung, und die braucht mehr als die Boolesche
        # Operation.** Die Tiefenstufe der Flächenplatzierung fragt hier,
        # ob ein Zug nach unten überhaupt etwas abträgt; bei ``raised``
        # vergrößerte sie sonst einen Wert, der nach außen geht.
        subtractive_on=("engraved",),
        doc=_("Erhaben druckt sich besser, vertieft bleibt beim Schleifen erhalten."),
    )
    slot: int = param(
        title=_("Filament"),
        default=0,
        minimum=0,
        maximum=MAX_SLOTS - 1,
        # Ein Farbwechsel setzt einen zweiten Filamentstrang voraus. Wer ihn
        # hat, sucht ihn gezielt; wer einfarbig druckt — das ist die Mehrheit —
        # hat hier ein Feld ohne Wirkung vor sich (§2.4).
        placement="advanced",
        kind="filament",
        doc=_(
            "Legt die Schrift in einen eigenen Slot — der 3MF-Export macht daraus "
            "den Farbwechsel, ohne zweite Datei."
        ),
    )
    font: str = param(
        title=_("Schrift"),
        default=FONTS[0],
        choices=FONTS,
        placement="advanced",
        doc=_FONT,
    )
    style: str = param(
        title=_("Schnitt"),
        default=FONT_STYLES[0],
        choices=FONT_STYLES,
        placement="advanced",
        doc=_STYLE,
        depends_on=("font", FONTS_WITH_ALL_STYLES),
    )
    x: float = param(
        title=_("Position X"), default=0.0, unit="mm", doc=_WHERE, placement="advanced"
    )
    y: float = param(
        title=_("Position Y"), default=0.0, unit="mm", doc=_WHERE_MORE, placement="advanced"
    )
    z: float = param(
        title=_("Position Z"), default=0.0, unit="mm", doc=_WHERE_MORE, placement="advanced"
    )
    nx: float = param(title=_("Normale X"), default=0.0, placement="advanced", doc=_FACING)
    ny: float = param(title=_("Normale Y"), default=0.0, placement="advanced", doc=_FACING_MORE)
    nz: float = param(title=_("Normale Z"), default=1.0, placement="advanced", doc=_FACING_MORE)
    angle: float = param(
        title=_("Drehung"),
        default=0.0,
        unit=DEGREE_UNIT,
        minimum=-360.0,
        maximum=360.0,
        placement="advanced",
        doc=_("Dreht die Schrift in der Fläche, auf der sie liegt."),
    )


def _fell_apart(before: Any, after: Any, mode: str) -> Finding | None:
    """Ist die Schrift neben dem Körper liegengeblieben? (Regel 17)

    **Der Fall, den der Kommentar an der Aufrufstelle seit jeher beschreibt**
    und den niemand prüfte: „Erhaben ist es schlimmer als graviert: die
    Buchstaben stehen dann als eigene Komponente neben dem Teil und reisen bis
    in den Export mit." Gemessen am 31.08.2026 an einer Platte 40 auf 30 mit
    einer Beschriftung 200 mm daneben: **drei Komponenten**, wo eine war —
    Platte und zwei Lettern, wasserdicht, mit plausiblem Volumen, und kein
    Befund dazu.

    :func:`without_effect` fängt das **nicht**, und das ist kein Versehen,
    sondern seine Bauart: Es misst, ob sich das Volumen geändert hat. Bei
    erhabener Schrift ändert es sich — die Buchstaben kommen ja hinzu, nur eben
    daneben. Die Volumenfrage ist damit beantwortet und die falsche gestellt.

    **Die Teilezahl lügt nicht.** Dieselbe Bauart wie
    ``texture_ops._fell_apart`` und ``parts._hanging_loose``, samt derselben
    Ausnahme: Ein graviertes Muster schneidet, und Schneiden darf teilen.
    """
    # Der Satz ist parallel zu dem der Textur gebaut: Der Kunde erkennt die
    # Familie am Wortlaut, nicht am Befundcode — den sieht er nie.
    return fell_apart(
        before,
        after,
        applies=mode == "raised",
        code="label.fell_apart",
        message=lambda loose: _(
            "Die Schrift hängt nicht am Körper: Sie liegt in {loose} losen Stücken "
            "daneben und würde einzeln gedruckt. Meist steht sie neben der Fläche, "
            "auf die sie soll — klicken Sie die Fläche an, dann trägt sie Ort und "
            "Richtung selbst ein.",
            loose=loose,
        ),
    )


def _buried(letters: Any, before: Any, after: Any, mode: str) -> Finding | None:
    """Steckt die Schrift im Körper, statt auf ihm zu stehen? (Regel 17)

    **Der dritte Fall derselben Auskunft**, gemessen am 02.09.2026 am
    Beispiel „Dose mit Deckel": Die Beschriftung stand ohne Ort und Richtung
    in der Operation, also bei (0, 0, 0) mit der Vorgabe-Normalen nach oben —
    und das ist der Boden einer Dose, die auf dem Bett steht. Die Buchstaben
    wurden erhaben nach **oben** gebaut, also ins Material hinein, die
    Vereinigung änderte nichts Sichtbares, und übrig blieb die Überlappung
    von einem Hundertstel unter dem Boden: Die Dose war 40,01 statt 40,00
    hoch, das Teil stand auf einer unsichtbaren Schrift, und kein Befund
    sagte es. :func:`without_effect` schwieg, weil das Volumen sich änderte
    (um die Überlappung), :func:`_fell_apart` schwieg, weil nichts danebenlag.

    Gemessen wird deshalb, wie viel von den Buchstaben **über der Fläche**
    ankommt: die Volumenzunahme gegen das Volumen der gesetzten Schrift. Bleibt
    weniger als :data:`LABEL_BURIED_SHARE`, steckt sie im Körper. Nur erhaben —
    graviert nimmt Material weg, und dort ist im Körper genau der richtige Ort.
    """
    if mode != "raised":
        return None
    expected = float(letters.volume)
    if expected <= EPS_GEOM:
        return None
    shown = max(float(after.volume) - float(before.volume), 0.0)
    if shown >= LABEL_BURIED_SHARE * expected:
        return None
    return Finding(
        code="label.buried",
        severity="warning",
        message=_(
            "Die Schrift steckt im Körper: Von {expected} Buchstaben stehen nur {shown} "
            "über der Fläche, der Rest liegt im Material und ist unsichtbar. Meist zeigt "
            "die Richtung in den Körper hinein oder der Punkt liegt in ihm — klicken Sie "
            "die Fläche an, dann trägt sie Ort und Richtung selbst ein.",
            expected=format_volume(expected),
            shown=format_volume(shown),
        ),
        values={
            "expected": format_volume(expected),
            "shown": format_volume(shown),
        },
    )


def _too_fine(
    text: str, size: float, font: str, style: str, profile: Profile | None
) -> Finding | None:
    """Trägt diese Schrift bei dieser Höhe überhaupt eine Bahn? (Regel 17)

    Die Untergrenze von :data:`MIN_SIZE` gilt allen Schriften gleich; die
    Strichbreite tut das nicht. Gemessen wird deshalb am gesetzten Text, mit
    dem gewählten Schnitt — ein fetter trägt rund anderthalbmal so breite
    Striche und braucht darum weniger Höhe.

    **Und die Auskunft gilt beiden Arten.** Erhaben werden die Striche breiter
    gedruckt, als sie gezeichnet sind; graviert wachsen die Rillen zu. In
    beiden Fällen läuft die Schrift zu, und in beiden hilft dasselbe.

    Gemeldet und nicht gesperrt: Wer eine Beschriftung nur ansehen oder als STL
    weitergeben will, darf sie klein haben. Was der Kunde braucht, ist die
    **Zahl** — ab welcher Höhe es trägt —, nicht ein „zu dünn".
    """
    if profile is None:
        return None
    shapes = outlines(text, size, font, style)
    if not shapes:
        return None
    bead = narrowest_bead(profile)
    needed = too_thin_to_print(shapes, size, bead)
    if needed is None:
        return None
    # **Der Rat muss es an dieser Schrift geben.** „Nehmen Sie den fetten
    # Schnitt" ist bei Comfortaa und Dancing Script kein Ausweg, sondern der
    # nächste Fehler — sie bringen nur einen Schnitt mit, und die Operation
    # lehnt jeden anderen ab (:func:`font_properties`).
    bolder = style not in ("bold", "bold_italic") and font in FONTS_WITH_ALL_STYLES
    message = (
        _(
            "Bei {size} sind die Striche dieser Schrift im Mittel schmaler als die "
            "schmalste Bahn Ihrer Düse ({bead}) — gedruckt läuft die Schrift zu. Ab "
            "{needed} trägt sie; darunter hilft der fette Schnitt, der dieselbe Höhe "
            "mit dickeren Strichen trägt.",
            size=format_length(size),
            bead=format_length(bead),
            needed=format_length(needed),
        )
        if bolder
        else _(
            "Bei {size} sind die Striche dieser Schrift im Mittel schmaler als die "
            "schmalste Bahn Ihrer Düse ({bead}) — gedruckt läuft die Schrift zu. Ab "
            "{needed} trägt sie; darunter hilft eine Schrift mit dickeren Strichen "
            "oder eine feinere Düse.",
            size=format_length(size),
            bead=format_length(bead),
            needed=format_length(needed),
        )
    )
    return Finding(
        code="label.too_fine",
        severity="warning",
        message=message,
        values={"font": font, "needed": format_length(needed)},
    )


@register_op(
    name="label_text",
    title=_("Text aufbringen"),
    category="label",
    params=LabelParams,
    consumes=1,
    produces=1,
    applies_to=["face"],
    doc=_(
        "Setzt Text erhaben oder vertieft auf eine Fläche. Die Schrift wird als "
        "Umriss verarbeitet, nicht als Bild — die Kanten bleiben in jeder Größe sauber."
    ),
)
def label_text(ctx: OpContext) -> OpResult:
    params = cast(LabelParams, ctx.params)
    source = ctx.inputs[0]
    if not params.text.strip():
        raise ValidationError(
            field="text",
            detail=_("Ohne Text gibt es nichts aufzubringen."),
            constraint="empty",
        )

    mode = cast(Placement, params.mode)

    # Zentriert auf dem angeklickten Punkt, nicht dort beginnend: eine
    # Beschriftung wächst um ihren Ort herum, und genau das erwartet, wer eine
    # anbringt.
    #
    # Wohin sie reicht, hängt an der Art. Erhaben: die Tiefe steht über der
    # Fläche, nur die Überlappung reicht hinein. Graviert: die Tiefe reicht
    # hinein, nur die Überlappung steht über — sonst nimmt der Schnitt die
    # Überlappung weg und lässt die Buchstaben als Kratzer zurück.
    body = local_text_body(
        params.text, params.size, params.font, params.depth, style=params.style, mode=mode
    )

    placed = place(
        body, (params.x, params.y, params.z), (params.nx, params.ny, params.nz), params.angle
    )
    body_mesh = as_mesh_data(source.mesh)
    slots = list(source.material_slots)
    if params.slot and mode == "raised":
        # §20: die Buchstaben tragen einen eigenen Slot in die Vereinigung,
        # und die Attributübertragung der Booleschen Op bringt ihn auf der
        # anderen Seite wieder heraus. Das macht aus einer zweifarbigen
        # Beschriftung eine Datei statt zwei.
        placed = with_slot(placed, params.slot)
        if not body_mesh.slots:
            body_mesh = with_slot(body_mesh, 0)
        slots = _with_slot_named(slots, params.slot)

    kind: BooleanKind = "union" if mode == "raised" else "difference"
    outcome = boolean(
        kind,
        [body_mesh, placed],
        quality=ctx.quality,
        cut_slot=0,
        cancelled=ctx.cancelled,
    )

    # Eine Beschriftung, die den Körper nicht erreicht hat, sagt das (§2.7).
    #
    # Die Auskunft gab es überall sonst — beim Bohren, beim Stopfen, bei jedem
    # Baustein, bei der Skizzentasche —, und hier nicht: gemessen an einem
    # Rahmen, dessen Hüllquader in der Mitte hohl ist, kam „BASIS" graviert mit
    # unverändertem Volumen und unveränderter Dreieckszahl zurück, und der
    # Prüfbericht hatte dazu keine Zeile. Erhaben ist es schlimmer als
    # graviert: die Buchstaben stehen dann als eigene Komponente neben dem
    # Teil und reisen bis in den Export mit.
    nothing = without_effect(body_mesh, outcome.mesh, kind, ctx.profile)
    # **Und die zweite Hälfte derselben Auskunft.** ``without_effect`` fragt
    # nach dem Volumen und schweigt deshalb genau dann, wenn die Schrift
    # danebenfällt statt zu fehlen — dort ist Volumen dazugekommen.
    apart = _fell_apart(body_mesh, outcome.mesh, mode)
    # **Und die dritte Hälfte.** Weder danebengefallen noch wirkungslos, sondern
    # im Körper verschwunden — die Volumenfrage, aber gegen die Schrift gehalten.
    buried = _buried(placed, body_mesh, outcome.mesh, mode)

    _log.info("labelled with %r, %s", params.text, mode)
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=outcome.mesh, features={}, material_slots=slots)],
        solver=outcome.solver,
        findings=[
            *outcome.findings,
            *([nothing] if nothing is not None else []),
            *([apart] if apart is not None else []),
            *([buried] if buried is not None else []),
            *(
                [fine]
                if (
                    fine := _too_fine(
                        params.text, params.size, params.font, params.style, ctx.profile
                    )
                )
                else []
            ),
        ],
    )


@op_params
class LabelBodyParams(BaseParams):
    text: str = param(title=_("Text"), doc=_("Was der Körper sagen soll."))
    size: float = param(
        title=_("Schriftgröße"),
        default=8.0,
        unit="mm",
        minimum=MIN_SIZE,
        maximum=200.0,
        doc=_SIZE,
    )
    depth: float = param(
        title=_("Dicke"),
        default=0.6,
        unit="mm",
        minimum=0.1,
        maximum=50.0,
        doc=_("Wie dick die Buchstaben werden. Zum Aufkleben reichen wenige Zehntel."),
    )
    font: str = param(
        title=_("Schrift"),
        default=FONTS[0],
        choices=FONTS,
        placement="advanced",
        doc=_FONT,
    )
    style: str = param(
        title=_("Schnitt"),
        default=FONT_STYLES[0],
        choices=FONT_STYLES,
        placement="advanced",
        doc=_STYLE,
        depends_on=("font", FONTS_WITH_ALL_STYLES),
    )
    x: float = param(
        title=_("Position X"), default=0.0, unit="mm", doc=_WHERE, placement="advanced"
    )
    y: float = param(
        title=_("Position Y"), default=0.0, unit="mm", doc=_WHERE_MORE, placement="advanced"
    )
    z: float = param(
        title=_("Position Z"), default=0.0, unit="mm", doc=_WHERE_MORE, placement="advanced"
    )
    nx: float = param(title=_("Normale X"), default=0.0, placement="advanced", doc=_FACING)
    ny: float = param(title=_("Normale Y"), default=0.0, placement="advanced", doc=_FACING_MORE)
    nz: float = param(title=_("Normale Z"), default=0.0, placement="advanced", doc=_FACING_MORE)
    angle: float = param(
        title=_("Drehung"),
        default=0.0,
        unit=DEGREE_UNIT,
        placement="advanced",
        doc=_("Dreht die Schrift in ihrer Fläche um den gewählten Punkt."),
    )
    name: str = param(
        title=_("Name"),
        default="",
        placement="advanced",
        doc=NAME_DOC,
    )


@register_op(
    name="create_label",
    title=_("Schriftzug als Körper"),
    category="label",
    params=LabelBodyParams,
    consumes=0,
    produces=1,
    doc=_(
        "Legt einen Schriftzug als eigenes Objekt an — für den Zweifarbendruck "
        "mit zwei Dateien und für Buchstaben, die aufgeklebt werden."
    ),
)
def create_label(ctx: OpContext) -> OpResult:
    """§25: dieselben Umrisse, für sich stehend statt auf einem Teil.

    Zwei Farben gibt es auf beiden Wegen: dieser hier als zweite Datei für
    einen Drucker, der das Filament von Hand wechselt, und ``label_text`` mit
    einem Slot für eine Maschine, die die Gruppen aus einer 3MF liest (§20).
    Was besser ist, hängt am Drucker — darum gibt es beides.
    """
    params = cast(LabelBodyParams, ctx.params)
    if not params.text.strip():
        raise ValidationError(
            field="text",
            detail=_("Ohne Text gibt es nichts anzulegen."),
            constraint="empty",
        )

    body = local_text_body(
        params.text,
        params.size,
        params.font,
        params.depth,
        style=params.style,
        angle=params.angle,
    )
    placed = place(body, (params.x, params.y, params.z), (params.nx, params.ny, params.nz))
    # Dieselbe Frage wie bei ``label_text``, und hier wiegt sie schwerer: Ein
    # Schild steht für sich, es hängt nicht an einem Körper, der es hielte.
    # Wer es dünner setzt, als seine Düse legen kann, druckt einen Klumpen.
    fine = _too_fine(params.text, params.size, params.font, params.style, ctx.profile)
    return OpResult(
        outputs=[SceneObject(id="", name=params.name or params.text.strip()[:20], mesh=placed)],
        findings=[fine] if fine is not None else [],
    )


def _with_slot_named(slots: list[MaterialSlot], index: int) -> list[MaterialSlot]:
    """Fügt den Slot an, in den die Schrift kommt; ein schon benannter bleibt."""
    known = {entry.index: entry for entry in slots}
    known.setdefault(0, MaterialSlot(index=0, name=str(_("Körper"))))
    known.setdefault(index, MaterialSlot(index=index, name=str(_("Schrift"))))
    return [known[key] for key in sorted(known)]
