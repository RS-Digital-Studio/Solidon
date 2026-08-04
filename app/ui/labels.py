"""Kurze Texte, auf die sich mehrere Teile der Oberfläche einigen müssen.

Ein Merkmal wird in der Viewport-Überlagerung, im Objektbaum und in der
Statusleiste gleich geschrieben — ``hole_3 · ⌀4.2``. Ein Ort dafür heißt: der
Name, den der Nutzer liest, ist der Name, den der Agent benutzt (§18.5,
Leitprinzip 5).
"""

from __future__ import annotations

from PySide6.QtCore import QLocale

from app.core.errors import AppError
from app.core.types import Feature, FeatureId
from app.core.units import LengthUnit, format_length, format_volume
from app.i18n import tr


def localised(text: str) -> str:
    """Setzt das Dezimaltrennzeichen der Anzeigesprache ein.

    Der Kern rechnet und schreibt mit Punkt — das ist richtig, dort ist eine
    Zahl ein Wert und keine Anzeige. Nur kam sie so auch beim Nutzer an: im
    Objektbaum standen die Maße mit Punkt, vierzig Pixel neben einem
    Eingabefeld mit Komma. Zwei Schreibweisen derselben Zahl im selben Blick.

    Gefragt wird ``QLocale`` und nicht die Sprache selbst, weil die
    Eingabefelder es ebenso tun — eine Quelle, oder das Problem kommt an der
    nächsten Stelle wieder.
    """
    separator = QLocale().decimalPoint()
    return text.replace(".", separator) if separator != "." else text


def length(value_mm: float, unit: LengthUnit = "mm", with_unit: bool = True) -> str:
    """Eine Länge, wie die Oberfläche sie schreibt."""
    return localised(format_length(value_mm, unit, with_unit))


def volume(value_mm3: float, unit: LengthUnit = "mm") -> str:
    """Ein Volumen, wie die Oberfläche es schreibt."""
    return localised(format_volume(value_mm3, unit))


def choice_label(value: str) -> str:
    """Ein Auswahlwert, wie der Nutzer ihn lesen kann.

    Normteilschlüssel sind englisch und kurz, weil sie Schlüssel sind — im
    Dialog standen sie aber als Beschriftung: „cable-5", „ptfe-4x2". Das tippt
    niemand ab und niemand erkennt es, ohne die Tabelle danebenzulegen.

    Erzeugt aus den Maßen und nicht als zweite Liste gepflegt: sonst hätte ein
    neues Normteil einen Namen an einer Stelle und keinen an der anderen. Was
    die Tabelle nicht kennt — „M4", „PLA", „z" —, bleibt, wie es ist; diese
    Werte sind selbst schon der Name.
    """
    from app.core.knowledge import standards

    try:
        tube = standards.tube(value)
    except AppError:
        return value
    if tube.inner > 0.0:
        return f"{tr('Schlauch')} {length(tube.outer, with_unit=False)} × {length(tube.inner)}"
    return f"{tr('Rundkabel')} Ø{length(tube.outer)}"


def feature_label(feature_id: FeatureId, feature: Feature) -> str:
    """``hole_3 · ⌀4,2`` — die Beschriftung, die §18.5 verlangt, Name zuerst."""
    params = feature.params
    if feature.kind == "hole":
        return f"{feature_id} · Ø{length(float(params.get('diameter', 0.0)))}"
    if feature.kind == "face":
        return f"{feature_id} · {float(params.get('area', 0.0)):.0f} mm²"
    if feature.kind == "edge_loop":
        return f"{feature_id} · {params.get('open_edges', 0)} {tr('offene Kanten')}"
    return feature_id
