"""Szene, Parameter, Passungen, Op-DAG, Auswertung, Projektdatei, Migrationen (§12-§16).

Die Namen werden erst beim Zugriff geladen — warum, steht in
:mod:`app.core.lazy`. Für Aufrufer ändert sich nichts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from app.core.lazy import install

if TYPE_CHECKING:
    from app.core.scene.cache import (
        CachedResult,
        DiskCache,
        MeshCodec,
        ResultCache,
        disk_backed_cache,
        drop_other_versions,
    )
    from app.core.scene.cancel import CancelSignal, NeverCancelled
    from app.core.scene.evaluate import EvaluationResult, evaluate
    from app.core.scene.history import History, OperationDraft
    from app.core.scene.migrations import FORMAT_VERSION
    from app.core.scene.placement import (
        advises_on_bores,
        bore_advice,
        values_for,
        values_for_object,
    )
    from app.core.scene.project import Project, new_project
    from app.core.scene.variants import VariantSet
    from app.core.scene.variants import build as build_variants

#: Welcher Name in welchem Untermodul steht, und wie er dort heißt. Der zweite
#: Eintrag ist der Name **im Untermodul** — er weicht nur bei ``build_variants``
#: ab, das dort schlicht ``build`` heißt.
_EXPORTS: Final[dict[str, tuple[str, str]]] = {
    "CachedResult": ("cache", "CachedResult"),
    "DiskCache": ("cache", "DiskCache"),
    "MeshCodec": ("cache", "MeshCodec"),
    "ResultCache": ("cache", "ResultCache"),
    "disk_backed_cache": ("cache", "disk_backed_cache"),
    "drop_other_versions": ("cache", "drop_other_versions"),
    "CancelSignal": ("cancel", "CancelSignal"),
    "NeverCancelled": ("cancel", "NeverCancelled"),
    "EvaluationResult": ("evaluate", "EvaluationResult"),
    "evaluate": ("evaluate", "evaluate"),
    "History": ("history", "History"),
    "OperationDraft": ("history", "OperationDraft"),
    "FORMAT_VERSION": ("migrations", "FORMAT_VERSION"),
    "advises_on_bores": ("placement", "advises_on_bores"),
    "bore_advice": ("placement", "bore_advice"),
    "values_for": ("placement", "values_for"),
    "values_for_object": ("placement", "values_for_object"),
    "Project": ("project", "Project"),
    "new_project": ("project", "new_project"),
    "VariantSet": ("variants", "VariantSet"),
    "build_variants": ("variants", "build"),
}


install(__name__, _EXPORTS)


__all__ = [
    "FORMAT_VERSION",
    "CachedResult",
    "CancelSignal",
    "DiskCache",
    "EvaluationResult",
    "History",
    "MeshCodec",
    "NeverCancelled",
    "OperationDraft",
    "Project",
    "ResultCache",
    "VariantSet",
    "advises_on_bores",
    "bore_advice",
    "build_variants",
    "disk_backed_cache",
    "drop_other_versions",
    "evaluate",
    "new_project",
    "values_for",
    "values_for_object",
]
