"""Bausteine überstehen Verschieben, Skalieren und Strecken ihrer Merkmale.

Eigene Datei, weil ``test_matching.py`` unter der Sperrklinke steht (Regel 6
der Codestruktur): Der Fall kam mit der Kundenmeldung zu 0.6.0
(S-20261015-f1a9b8) und gehört zur Merkmalszuordnung.
"""

from __future__ import annotations

import numpy as np


def test_every_part_moves_scales_and_stretches_its_features_without_a_halt() -> None:
    """Kein Baustein legt einen Namen in ein Feld, das das Nachführen streckt.

    Eine Kundenmeldung zu 0.6.0 (die gedruckte M20-Schraube, Fall in
    ``test_matching.py``) hielt
    beim Verschieben mit „could not convert string to float: 'M'“ an: Das
    Gewinde trug seine Tabellengröße als ``size``. Am Stand 0.6.0 traf das vier
    Bausteine — gedruckte Mutter, Schraube, Gewinde und Gewindestange. Dieser
    Fall fährt jeden Baustein mit seinen Vorgaben durch Verschieben,
    gleichmäßiges und achsweises Skalieren, damit der nächste Baustein mit
    einem Text in einem Maßfeld hier rot wird und nicht beim Kunden.
    """
    from app.core.geom.ops import as_transform
    from app.core.knowledge.parts import PARTS
    from app.core.perceive.matching import transformed_features

    matrices = {
        "verschieben": np.array(
            [
                [1.0, 0.0, 0.0, 14.0],
                [0.0, 1.0, 0.0, -4.9],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ]
        ),
        "skalieren": np.diag([2.0, 2.0, 2.0, 1.0]),
        "strecken": np.diag([2.0, 1.0, 1.0, 1.0]),
    }
    specs = PARTS.all()
    assert len(specs) >= 40, len(specs)
    halts: list[str] = []
    threaded: set[str] = set()
    for spec in specs:
        features = spec.fn(spec.params()).features
        if any(feature.kind == "thread" for feature in features.values()):
            threaded.add(spec.name)
        for label, matrix in matrices.items():
            try:
                transformed_features(features, as_transform(matrix))
            except Exception as error:
                halts.append(f"{spec.name} {label}: {type(error).__name__}: {error}")
    # Der Fall, dessen Ausgang bekannt ist: Ohne die vier Gewinde von 0.6.0
    # prüfte der Wächter nichts, was je angehalten hat.
    assert {"printed_nut", "printed_screw", "printed_thread", "threaded_rod"} <= threaded, threaded
    assert not halts, halts
