"""Was ein gedruckter Federarm aushält.

Ein Schnapphaken, eine Klemmzunge, ein Filmscharnier — alle drei sind
eingespannte Blattfedern, und für alle drei ist dieselbe Frage die
entscheidende: **Kommt der Arm zurück, oder bricht er beim ersten Mal?**

Die Bausteinbibliothek beantwortet sie bisher über eine Verhältnisregel: Die
Armstärke ist ein Zehntel der Armlänge (``insert_snap_fit``,
``insert_snap_connector``). Das ist eine gute Faustregel und trägt, solange
der Federweg im üblichen Rahmen bleibt — sie kennt aber weder den Weg noch
das Material. Ein Arm nach der Regel aus TPU ist etwas völlig anderes als
derselbe Arm aus PETG-CF, und einer, der sich um zwei Millimeter aufbiegen
muss, etwas anderes als einer mit zwei Zehnteln.

Der Anlass war ein Adapter für eine Auffangrinne (08.09.2026): Zwei
Millimeter Wangendicke — die Stärke, die jede Wand dort hat — ergaben 51,9
MPa gegen eine Streckgrenze von 50. Die Wange wäre beim ersten Fügen
gebrochen, und die Verhältnisregel hätte nichts dazu gesagt, weil sie
eingehalten war. Mit 1,2 mm sind es 17,1 MPa. Diese Rechnung stand in einem
Kommentar in einem Druckskript; hier steht sie, wo sie jede Operation fragen
kann.

**Was hier nicht steht:** Ermüdung. Diese Rechnung sagt, ob ein Arm **einmal**
sicher federt. Wie oft er es aushält, hängt an Kerben, Schichthaftung und
Lastwechseln, und dafür gibt kein Datenblatt eines Filaments etwas her.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.types import MaterialProfile

#: Ab welcher Sicherheit ein Federarm als tragfähig gilt. [S]
#:
#: Eins wäre die Streckgrenze selbst — dort verformt sich der Arm bleibend.
#: Anderthalb lässt Raum für das, was diese Rechnung nicht kennt: Kerben an
#: der Armwurzel, Schwankungen der Bahnbreite, ein Kunde, der beim Fügen
#: kräftiger drückt als nötig.
SAFE_FACTOR = 1.5


@dataclass(frozen=True, slots=True)
class SpringLoad:
    """Was aus einer Blattfederrechnung herauskommt."""

    stress: float
    """Biegespannung an der Einspannung in MPa."""
    limit: float
    """Die Streckgrenze, gegen die sie gehalten wird — mit Lagenabschlag."""
    safety: float
    """Grenze durch Spannung. Unter 1 verformt sich der Arm bleibend."""

    @property
    def holds(self) -> bool:
        """Trägt der Arm mit Reserve?"""
        return self.safety >= SAFE_FACTOR


def cantilever_stress(length: float, thickness: float, deflection: float, modulus: float) -> float:
    """Die Biegespannung einer einseitig eingespannten Blattfeder, in MPa.

    ``sigma = 3 · E · t · delta / (2 · L²)`` — die Spannung an der
    Einspannung, wo ein Federarm bricht, wenn er bricht.

    Alle Längen in Millimetern, ``modulus`` in MPa. Die Formel ist in ihren
    Einheiten geschlossen: MPa mal mm mal mm durch mm² gibt wieder MPa.

    **Die Dicke geht linear ein, die Länge quadratisch.** Das ist der Grund,
    aus dem ein zu kurzer Arm nicht durch mehr Material zu retten ist:
    Verdoppeln der Länge viertelt die Spannung, Halbieren der Dicke halbiert
    sie nur.
    """
    if length <= 0.0 or thickness <= 0.0 or modulus <= 0.0:
        return 0.0
    return 3.0 * modulus * thickness * abs(deflection) / (2.0 * length * length)


def spring_load(
    material: MaterialProfile,
    *,
    length: float,
    thickness: float,
    deflection: float,
    across_layers: bool = True,
) -> SpringLoad | None:
    """Was der Arm aushält — oder ``None``, wenn das Material es nicht sagt.

    ``across_layers`` beschreibt, wie das Teil **liegt**: Biegt sich der Arm
    über seine Schichtfugen, trägt er den Anteil ``material.layer_bond_ratio``
    der Streckgrenze. Die Lage entscheidet, ob der Abschlag gilt; das Material,
    wie groß er ist.
    Liegt er lang in der Druckebene und federt quer dazu, trägt er voll.
    Ohne ausdrücklich bekannte Lage gilt die vorsichtige Querbelastung.

    **``None`` ist eine Antwort und keine Panne.** Ein Materialprofil ohne
    mechanische Kennwerte — ein selbst angelegtes, ein fremdes — kann diese
    Frage nicht beantworten, und eine Zahl aus einem geratenen E-Modul sähe
    genauso aus wie eine gerechnete (Regel 21).
    """
    if material.youngs_modulus <= 0.0 or material.yield_strength <= 0.0:
        return None
    stress = cantilever_stress(length, thickness, deflection, material.youngs_modulus)
    limit = _yield_limit(material, across_layers)
    if limit is None:
        return None
    if stress <= 0.0:
        return SpringLoad(stress=0.0, limit=limit, safety=float("inf"))
    return SpringLoad(stress=stress, limit=limit, safety=limit / stress)


def safe_thickness(
    material: MaterialProfile,
    *,
    length: float,
    deflection: float,
    across_layers: bool = True,
    factor: float = SAFE_FACTOR,
) -> float | None:
    """Wie dick der Arm höchstens sein darf, damit er die Sicherheit hält.

    Die Umkehrung von :func:`cantilever_stress` nach ``t``. Sie beantwortet
    die Frage, die beim Entwerfen wirklich ansteht — nicht „hält meine
    Dicke?", sondern „welche darf ich nehmen?".

    **Höchstens, nicht mindestens**: Bei einer Blattfeder macht mehr Material
    den Arm nicht sicherer, sondern steifer, und die Spannung steigt mit ihm.
    Wer einen Arm verstärken will, verlängert ihn.
    Wie bei :func:`spring_load` gilt ohne bekannte Lage die Querbelastung.
    """
    if material.youngs_modulus <= 0.0 or material.yield_strength <= 0.0:
        return None
    if length <= 0.0 or abs(deflection) <= 0.0 or factor <= 0.0:
        return None
    limit = _yield_limit(material, across_layers)
    if limit is None:
        return None
    return (
        2.0 * length * length * limit / (3.0 * material.youngs_modulus * abs(deflection) * factor)
    )


def _yield_limit(material: MaterialProfile, across_layers: bool) -> float | None:
    """Die richtungsabhängige Grenze, ohne eine unbekannte Schichthaftung zu ergänzen."""
    if not across_layers:
        return material.yield_strength
    ratio = material.layer_bond_ratio
    if not 0.0 < ratio <= 1.0:
        return None
    return material.yield_strength * ratio
