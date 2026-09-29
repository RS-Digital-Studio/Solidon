"""Fährt den Pappus-Test mit abgeschaltetem ``_swept_tool`` — der Stand vor (i).

Aufruf aus der Wurzel des Arbeitsbaums: python rot_ohne_i.py.
"""

import os
import sys

sys.path.insert(0, os.getcwd())
import pytest  # noqa: E402

from app.core.geom import edges  # noqa: E402

edges._swept_tool = lambda *args, **kwargs: None
sys.exit(
    pytest.main(
        [
            "-q",
            "-p",
            "no:cacheprovider",
            "tests/test_mesh_edges.py::test_the_mouth_of_a_bore_is_rounded_as_deep_as_pappus_says",
            "tests/test_mesh_edges.py::test_a_radius_law_around_the_mouth_of_a_bore_is_not_too_flat",
        ]
    )
)
