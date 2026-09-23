"""Aufeinanderfolgende gleichartige Züge werden ein Verlaufsschritt (§15.5).

Wer ein Teil an seinen Platz schiebt, zieht selten einmal. Er zieht, sieht
nach, zieht nach, sieht wieder nach — und hatte dafür bisher drei Einträge im
Verlauf, für eine einzige Absicht. Ein Strg+Z nahm dann ein Drittel zurück.

**Gebündelt wird eng.** Nur was dieselbe Operation auf denselben Eingängen mit
demselben Anker ist, und nur wo eine Kumulationsregel steht — das ist der
Punkt: Bündeln ist **opt-in je Operation**, nicht die Voreinstellung. Wer eine
neue Operation baut, bekommt kein Bündeln geschenkt, und das ist richtig, denn
die Regel dafür ist jedes Mal eine eigene Überlegung:

* Zwei Verschiebungen sind eine Vektorsumme.
* Zwei Drehungen sind eine Winkelsumme — **nur um dieselbe Achse und nur um
  einen festen Punkt.** Zwei Drehungen um verschiedene Achsen lassen sich
  nicht zu einer zusammenfassen; wer es doch tut, baut einen stillen
  Geometriefehler, den erst der Druck zeigt. Und die Mitte eines Körpers ist
  kein fester Punkt (siehe :func:`_rotate`).
* Zwei Skalierungen wären ein Produkt. Sie bündeln trotzdem **nicht**: Der
  Kundenfall ist „dreimal nachgeschoben", die gefährliche Kante bleibt in
  Ruhe, und was hier fehlt, kann jederzeit dazukommen. Umgekehrt wäre es ein
  Rückbau (Entscheidung d5/Robert, 30.08.2026).

Das Bündel endet mit **jeder anderen Handlung** — einer anderen Operation,
einer anderen Auswahl, einem Werkzeugwechsel. Keine Zeitpause: Eine geratene
Zahl wäre die fragilste Bauart, und sie stünde in jeder Fehlersuche als
Verdächtige.

**Und es endet, wo die Auswertung nachgeführt hat** (:func:`stays_exact`).
Ein Zug am Griff trägt ``keep_on_bed``: Wer über den Rand zieht, bekommt den
Körper zurückgeschoben. Eine Summe zweier Wege weiß davon nichts — sie rechnet
den zweiten Zug vom gezogenen Platz aus, nicht vom zurückgeschobenen, und der
Körper sprang nach dem Loslassen woanders hin, als die Vorschau zeigte.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    import numpy as np

    from app.core.types import Operation, Scene

#: Wie nah zwei Fließkommazahlen sein müssen, um als derselbe Anker zu gelten.
#: Der Anker kommt aus der Hüllquadermitte einer Auswahl und wird bei jedem Zug
#: neu gerechnet; identisch ist er deshalb nie, gleich schon.
_ANCHOR_TOLERANCE = 1e-9


#: Welche Werte eine Regel summiert. Alle übrigen müssen gleich sein.
_SUMMED: Final = {
    "translate_object": frozenset({"dx", "dy", "dz"}),
    "rotate_object": frozenset({"angle"}),
}


def _alike_apart_from_the_sum(op: str, older: Mapping[str, Any], newer: Mapping[str, Any]) -> bool:
    """Ob beide Züge bis auf die summierten Werte gleich sind.

    **Nicht nur der Anker.** Bis zur Durchsicht 0.5.0 verglich diese Stelle
    ``about`` und den genannten Punkt und sonst nichts; die Summe übernahm
    alle übrigen Werte vom **älteren** Zug. Ein Schritt ohne *Auf dem Bett
    halten* und ein Zug mit dem Haken wurden so einer ohne — der Haken des
    zweiten ging still verloren. Was nicht summiert wird, muss also gleich
    sein, und fehlt ein Wert, gilt die Vorgabe aus dem Parameterschema:
    ``keep_on_bed`` weggelassen ist dasselbe wie ``False``.

    Gleich genannt heißt dabei noch nicht gleich gelegen: ``centre`` und
    ``bed`` meinen einen Punkt **am Körper**, und der wandert mit ihm. Ob zwei
    Drehungen darum zusammengehen, entscheidet :func:`_rotate`.
    """
    from app.core.registry import REGISTRY

    defaults = (
        {spec.name: spec.default for spec in REGISTRY.get(op).params.spec()}
        if REGISTRY.has(op)
        else {}
    )
    for key in (set(older) | set(newer)) - _SUMMED.get(op, frozenset()):
        one, other = older.get(key, defaults.get(key)), newer.get(key, defaults.get(key))
        if isinstance(one, bool) or isinstance(other, bool):
            if one is not other:
                return False
        elif isinstance(one, (int, float)) and isinstance(other, (int, float)):
            if abs(float(one) - float(other)) > _ANCHOR_TOLERANCE:
                return False
        elif one != other:
            return False
    return True


def _number(value: Any) -> float | None:
    """Der Wert als Zahl — oder ``None``, wenn er keine ist.

    Ein Parameter darf ein **Ausdruck** sein (§13): ``=@dx`` steht dann als
    Text im Zug und wird erst beim Rechnen der Szene zur Zahl. ``float()``
    warf darüber einen rohen ``ValueError`` — ohne Handlungsvorschlag, aus
    ``History.apply`` heraus, für eine Eingabe, die ausdrücklich erlaubt ist.

    Zwei Ausdrücke ließen sich auch nicht summieren: ``=@dx`` plus ``=@dx``
    ist keine Zahl, und eine Zeichenkette daraus zu bauen hieße, im Stapel
    einen Ausdruck zu erfinden, den niemand geschrieben hat.
    """
    return float(value) if isinstance(value, (int, float)) else None


def _translate(older: Mapping[str, Any], newer: Mapping[str, Any]) -> dict[str, Any] | None:
    """Zwei Verschiebungen sind ihre Summe."""
    merged = dict(older)
    for axis in ("dx", "dy", "dz"):
        one, other = _number(older.get(axis, 0.0)), _number(newer.get(axis, 0.0))
        if one is None or other is None:
            return None
        merged[axis] = one + other
    return merged


#: Anker, die einen Punkt am Körper meinen statt einen festen Punkt im Raum.
_BODY_ANCHORS: Final = frozenset({"centre", "bed"})


def _rotate(older: Mapping[str, Any], newer: Mapping[str, Any]) -> dict[str, Any] | None:
    """Zwei Drehungen um **dieselbe** Achse und denselben festen Punkt sind
    ihre Winkelsumme.

    Um verschiedene Achsen gibt es keine gemeinsame Drehung, und der Versuch
    wäre schlimmer als zwei Einträge im Verlauf.

    **Und um die eigene Mitte auch nicht.** ``centre`` ist die Mitte des
    Hüllquaders (:func:`app.core.geom.transform.anchor_point`), und die dreht
    sich nicht mit: Nach 30° um Z liegt die Mitte eines unsymmetrischen Teils
    woanders, und der zweite Zug dreht um diesen neuen Punkt. Eine Summe dreht
    dagegen beide Male um den alten. Gemessen am Keil ``Wedge-Lock (Base)``:
    30° und 15° hintereinander gegen 45° auf einmal — die Mitten lagen danach
    1,3 mm auseinander, und das Teil sprang nach dem Loslassen des zweiten
    Zugs von der Stelle, die die Vorschau gezeigt hatte (Durchsicht 0.5.0).
    Bündeln darf nur, wo das Ergebnis dasselbe bleibt; bei einem Punkt am
    Körper weiß das diese Stelle nicht, also wird es ein eigener Schritt.
    Ein genannter Punkt (``point``) und der Nullpunkt bleiben liegen.
    """
    if older.get("axis") != newer.get("axis"):
        return None
    if older.get("about", "centre") in _BODY_ANCHORS:
        return None
    one, other = _number(older.get("angle", 0.0)), _number(newer.get("angle", 0.0))
    if one is None or other is None:
        return None
    merged = dict(older)
    merged["angle"] = one + other
    return merged


#: Welche Operationen bündeln — und wie. Wer hier nicht steht, bündelt nicht.
_RULES = {
    "translate_object": _translate,
    "rotate_object": _rotate,
}


def bundles(op: str) -> bool:
    """Ob diese Operation überhaupt bündelt."""
    return op in _RULES


def merge_params(
    op: str, older: Mapping[str, Any], newer: Mapping[str, Any]
) -> dict[str, Any] | None:
    """Die Werte zweier gleichartiger Züge zu einem — oder ``None``.

    ``None`` heißt: Diese beiden gehören nicht zusammen. Der Aufrufer legt
    dann einen eigenen Schritt an, und das ist der sichere Ausgang — ein
    Bündel zu viel verfälscht Geometrie, ein Bündel zu wenig kostet einen
    Eintrag im Verlauf.

    **Und jeder Ausgang läuft über dieses ``None``**, auch ein Wert, der keine
    Zahl ist: Ein Ausdruck (§13) ist eine erlaubte Eingabe und kein Fehler,
    also wird er hier nicht zur Ausnahme, sondern zum eigenen Schritt.
    """
    rule = _RULES.get(op)
    if rule is None or not _alike_apart_from_the_sum(op, older, newer):
        return None
    return rule(older, newer)


#: Befunde, mit denen eine Bewegung sagt, dass die Auswertung sie nachgeführt
#: hat: Der Körper steht nicht dort, wohin der Weg allein geführt hätte.
BROUGHT_BACK: Final = frozenset({"transform.nudged_onto_bed", "transform.rearranged_on_bed"})


def stays_exact(ops: Sequence[Operation], scene: Scene) -> bool:
    """Ob ein weiterer Zug in diese Schritte aufgehen darf, ohne das Ergebnis zu ändern.

    ``ops`` sind die Schritte des offenen Bündels, ``scene`` ist die Szene,
    die **nach** ihnen gerechnet wurde — der Aufrufer sorgt dafür, dass sie
    aktuell ist. Die Summenregeln oben stimmen nur, solange die Auswertung
    genau den gezogenen Weg gegangen ist. ``keep_on_bed`` kann davon abweichen,
    und zwar auf zwei Arten:

    * **Es hat zurückgeschoben.** Dann steht der Körper woanders, als die
      Summe annimmt. Gemessen an einem Quader, 300 mm nach rechts gezogen und
      50 mm zurück: einzeln 68 mm, gebündelt 118 mm — die Summe von 250 mm
      wurde noch einmal zurückgeschoben, und der zweite Zug ging vom falschen
      Platz aus.
    * **Die Lage zum Bett hat gewechselt.** ``keep_on_bed`` hält nur, wer vor
      dem Zug auf der Fläche stand (``geom.ops._held_on_bed``). Stand der
      Körper vor dem Bündel daneben und nach dem ersten Zug darauf — oder
      umgekehrt —, fragt die Summe am falschen Eingang.

    Beides erkennt diese Prüfung am Ergebnis, ohne etwas nachzurechnen: am
    Befund und an der Lage vor und nach dem Schritt. Die Lage davor ergibt
    sich rückwärts aus dem gezogenen Weg, denn ohne Nachführung ist der
    Schritt genau dieser Weg.

    **Nicht erfasst** ist ein Zug an mehreren Körpern, bei dem ein anderer
    gewählter Körper gerade dort stünde, wohin der eine zurückgeschoben
    würde: Die Summe sieht die Gefährten an ihrem alten Platz. Das setzt einen
    Zug über den Rand voraus, dessen kürzester Rückweg auf einem Gefährten
    endet — danach meldet der Schritt ``transform.nudged_onto_bed`` oder
    ``transform.rearranged_on_bed``, und das Bündel endet beim nächsten Zug.
    """
    import numpy as np

    from app.core.build_area import fits_xy, printable_area
    from app.core.geom.mesh import as_mesh_data
    from app.core.geom.transform import apply

    ids = {entry.id for entry in ops}
    if any(
        finding.op_id in ids and finding.code in BROUGHT_BACK for finding in scene.report.findings
    ):
        return False
    printer = getattr(scene.profile, "printer", None)
    if printer is None:
        return True
    area = None
    for entry in ops:
        if not entry.params.get("keep_on_bed"):
            continue
        drawn = _drawn_matrix(entry.op, entry.params)
        if drawn is None:
            return False
        area = area if area is not None else printable_area(printer)
        back = np.linalg.inv(drawn)
        for object_id in entry.outputs:
            body = scene.objects.get(object_id)
            if body is None:
                return False
            after = as_mesh_data(body.mesh)
            if fits_xy(apply(after, back), area) != fits_xy(after, area):
                return False
    return True


def _vector(
    params: Mapping[str, Any], keys: tuple[str, str, str]
) -> tuple[float, float, float] | None:
    """Drei Werte als Punkt — oder ``None``, wenn einer keine Zahl ist."""
    values = [_number(params.get(key, 0.0)) for key in keys]
    if values[0] is None or values[1] is None or values[2] is None:
        return None
    return (values[0], values[1], values[2])


def _drawn_matrix(op: str, params: Mapping[str, Any]) -> np.ndarray | None:
    """Die Bewegung, die der Zug angibt — ohne Nachführung, oder ``None``.

    ``None`` heißt: Aus den Parametern allein lässt sie sich nicht bilden —
    ein Ausdruck statt einer Zahl, ein Anker am Körper, eine Operation ohne
    Regel. Der Aufrufer schließt dann das Bündel; das ist der sichere Ausgang.
    """
    from app.core.geom.transform import rotation, translation

    if op == "translate_object":
        offset = _vector(params, ("dx", "dy", "dz"))
        return translation(offset) if offset is not None else None
    if op != "rotate_object":
        return None
    angle = _number(params.get("angle", 90.0))
    axis = params.get("axis", "z")
    about = params.get("about", "centre")
    if angle is None or axis not in ("x", "y", "z"):
        return None
    if about == "origin":
        return rotation(axis, angle)
    if about == "point":
        pivot = _vector(params, ("pivot_x", "pivot_y", "pivot_z"))
        return rotation(axis, angle, pivot) if pivot is not None else None
    return None
