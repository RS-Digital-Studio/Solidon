"""Ein Wert, den die Liste eines Feldes nicht führt — mit Namen statt Kennung (FD-187, FD-189).

Ein Auswahlfeld zeigt einen Wert, den seine Liste nicht kennt, statt ihn still
zu ersetzen: Ein gespeicherter Schritt darf beim Öffnen nicht zu einem anderen
werden. Gezeigt wurde dabei die Kennung des Kerns — „face_1“ im Feld *Kammer*
nach *Anderes Merkmal wählen*, „fillet_1“ unter *Andere Flächen wählen*,
„e:-20.00,-15.00,10.00:0.000,0.000,1.000“ unter *Einzelne Kanten* an einem
angehaltenen Netzschritt. Die Absageknöpfe führen genau auf diese Felder.

Hier steht, wie ein solcher Wert heißt: ein Merkmal nach Art und Nummer wie die
Einträge der Liste, mit dem Hinweis, dass es hier nicht passt; ein Objekt, eine
Datei, ein Bild nach Art und Nummer, mit dem Hinweis, dass es im Projekt fehlt;
eine Kante nach Lage und Ort wie eine markierte (:func:`edge_lie_word`,
:func:`edge_place` — dieselben Wörter wie ``labels.edge_label``). Der Wert selbst
reist unverändert weiter.
"""

from __future__ import annotations

import math
from types import SimpleNamespace
from typing import Final, Literal

from app.core.types import Vec3
from app.i18n import TranslatableText, _, tr

#: Wofür ein Feld einen Wert hält, den seine Liste nicht führt.
UnlistedKind = Literal["feature", "edges", "object", "source", "image"]

#: Wie ein Objekt, eine Datei und ein Bild ohne Namen heißen.
_WORDS: Final[dict[str, TranslatableText]] = {
    "object": _("Objekt"),
    "source": _("Datei"),
    "image": _("Bild"),
}


def edge_lie_word(entry: object) -> str:
    """„Senkrecht“, „Waagerecht“ oder „Schräg“ — wie eine Kante liegt (``geom.edges``)."""
    from app.core.geom.edges import edge_lie_of

    shown = edge_lie_of(entry)
    if shown == "upright":
        return tr("Senkrecht")
    if shown == "flat":
        return tr("Waagerecht")
    return tr("Schräg")


def edge_place(middle: Vec3) -> str:
    """„x -20,00, y -15,00“ — wo eine Kante steht, in der Anzeigeeinheit."""
    from app.ui.labels import length

    x, y, _z = middle
    return f"x {length(x, with_unit=False)}, y {length(y, with_unit=False)}"


def _edge_text(key: str) -> str:
    """Eine Kante aus ihrem Schlüssel: Lage und Ort, ein Ring mit Durchmesser.

    Der Schlüssel (``geom.edges.edge_key``) trägt Mitte und Richtung, ein
    geschlossener Ring statt der Richtung seinen Radius; die Länge trägt er
    nicht, deshalb fehlt sie hier.
    """
    from app.ui.labels import length

    parts = key.split(":")
    try:
        middle = tuple(float(value) for value in parts[1].split(","))
        direction = tuple(float(value) for value in parts[2].split(","))
    except IndexError, ValueError:
        return tr("Kante")
    if parts[0] != "e" or len(middle) != 3 or len(direction) != 3:
        return tr("Kante")
    place = edge_place((middle[0], middle[1], middle[2]))
    if math.hypot(*direction) > 0.0:
        lie = edge_lie_word(SimpleNamespace(direction=direction))
        return f"{lie} · {place}"
    try:
        radius = float(parts[4]) if parts[3] == "r" else 0.0
    except IndexError, ValueError:
        radius = 0.0
    ring = tr("Ring")
    return f"{ring} · Ø{length(2.0 * radius)} · {place}" if radius > 0.0 else f"{ring} · {place}"


def _number(identifier: str) -> str:
    """Die Nummer einer Kennung — „3“ aus „face_3“, „1.2“ aus „pattern_1.2“; sonst leer."""
    numbers = [part.rsplit("_", 1)[-1] for part in identifier.split(".")]
    return ".".join(numbers) if all(number.isdigit() for number in numbers) else ""


def unlisted_text(identifier: str, kind: UnlistedKind) -> str:
    """Wie ein Wert heißt, den die Liste des Feldes nicht führt — nie seine Kennung."""
    if kind == "edges":
        return _edge_text(identifier)
    number = _number(identifier)
    if kind == "feature":
        # Eine Quelle mit den Meldungen (``registry.feature_title_of``, FD-186):
        # „obj_2:face_9“ an einem Zielfeld heißt „Fläche 9“ (D3).
        from app.core.registry.registry import feature_title_of

        named = feature_title_of(identifier)
        name = named if named != identifier and named[-1:].isdigit() else tr("Merkmal")
        return tr("{name} · passt hier nicht", name=name)
    word = str(_WORDS[kind])
    name = f"{word} {number}" if number else word
    return tr("{name} · nicht im Projekt", name=name)


__all__ = ["UnlistedKind", "edge_lie_word", "edge_place", "unlisted_text"]
