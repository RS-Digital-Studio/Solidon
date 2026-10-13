"""Gemeinsame Kern-Testhilfen für die Auswertung mit vollständiger Rückfallkette."""

from __future__ import annotations

from typing import Any

import pytest

from app.core.scene import evaluate
from app.core.types import Document, Profile


def short_chain_finds_nothing(monkeypatch: pytest.MonkeyPatch, *, nor_the_full: bool) -> list[str]:
    """Die verlustfreien Stufen liefern nichts, wie am Kundenteil (RM-534).

    Mit ``nor_the_full`` auch die übrigen — die volle Kette bestätigt den
    Halt. Zurück kommt die Liste der gerufenen Stufen.
    """
    import trimesh

    from app.core.geom import boolean as boolean_module
    from app.core.geom.mesh import MeshData

    real = boolean_module._run_stage
    called: list[str] = []

    def stage(kind: Any, meshes: Any, name: str, seed: Any, cancelled: Any = None) -> Any:
        called.append(name)
        if nor_the_full or name in boolean_module.DRAFT_CHAIN:
            return MeshData.of(trimesh.Trimesh())
        return real(kind, meshes, name, seed, cancelled)

    monkeypatch.setattr(boolean_module, "_run_stage", stage)
    return called


def window_evaluation(document: Document, profile: Profile, **options: Any) -> Any:
    """Wie Fensterlauf, Verlaufsumbau und Agent: Entwurf, und wo nur die kurze Kette ausgeht, fein.

    Vorschauen rechnen ohne ``full_chain_when_stuck`` (RM-534, §17.2).
    """
    return evaluate(document, profile, quality="draft", full_chain_when_stuck=True, **options)
