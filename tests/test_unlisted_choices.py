"""Ein Wert, den die Liste eines Feldes nicht führt, steht mit Kundennamen da (FD-187, FD-189).

Nach *Anderes Merkmal wählen* stand im Feld *Kammer* „face_1“, nach *Andere
Flächen wählen* „fillet_1“, und ein angehaltener Netzschritt zeigte unter
*Einzelne Kanten* „e:-20.00,-15.00,10.00:0.000,0.000,1.000“ — die Kennung, mit
der der Kern rechnet. Die neuen Absageknöpfe führen genau auf diese Felder.
Jetzt nennt eine Quelle (``app.ui.unlisted_choice``) den Wert so, wie die
Einträge der Liste heißen: Art und Nummer, an einer Kante Lage und Ort. Der
Wert selbst reist unverändert weiter.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication, QComboBox, QListWidget, QWidget

from app.core import bootstrap
from app.core.registry import REGISTRY
from app.core.registry.registry import FEATURE_TITLES
from app.i18n import set_language, tr
from app.i18n.catalog import available_languages, install_language
from app.ui.labels import length

#: Was nie im Feld stehen darf: eine Kennung des Kerns.
RAW = re.compile(r"\b(?:face|fillet|hole|obj|src)_\d|\be:-?\d")

#: Die Kante aus dem Lauf: senkrecht, Mitte bei x -20, y -15.
EDGE = "e:-20.00,-15.00,10.00:0.000,0.000,1.000"

#: Ein geschlossener Ring vom Radius 2,5 mm um x 0, y 0.
RING = "e:0.00,0.00,5.00:0.000,0.000,0.000:r:2.50"


@contextmanager
def _spoken(language: str) -> Iterator[None]:
    install_language(language)
    set_language(language)
    try:
        yield
    finally:
        install_language("de")
        set_language("de")


@pytest.mark.parametrize("language", available_languages())
def test_every_feature_kind_is_named_like_the_list(language: str) -> None:
    from app.ui.unlisted_choice import unlisted_text

    with _spoken(language):
        for kind, title in FEATURE_TITLES.items():
            said = unlisted_text(f"{kind}_3", "feature")
            assert said.startswith(f"{title} 3"), (kind, said)
            assert not RAW.search(said) and f"{kind}_" not in said, said
            assert said != f"{kind}_3"


@pytest.mark.parametrize("language", available_languages())
def test_objects_sources_and_images_are_named_too(language: str) -> None:
    from app.ui.unlisted_choice import unlisted_text

    with _spoken(language):
        for identifier, kind, word in (
            ("obj_12", "object", "Objekt"),
            ("src_3", "source", "Datei"),
            ("src_4", "image", "Bild"),
        ):
            said = unlisted_text(identifier, kind)
            assert said.startswith(f"{tr(word)} {identifier.rsplit('_', 1)[1]}"), said
            assert not RAW.search(said), said


@pytest.mark.parametrize("language", available_languages())
def test_an_edge_key_is_named_by_its_lie_and_place(language: str) -> None:
    """Dieselben Wörter und derselbe Ort wie eine markierte Kante (``labels.edge_label``)."""
    from app.ui.unlisted_choice import unlisted_text

    with _spoken(language):
        said = unlisted_text(EDGE, "edges")
        place = f"x {length(-20.0, with_unit=False)}, y {length(-15.0, with_unit=False)}"
        assert said == f"{tr('Senkrecht')} · {place}", said
        ring = unlisted_text(RING, "edges")
        assert tr("Ring") in ring and length(5.0) in ring, ring
        assert not RAW.search(said) and not RAW.search(ring)


def test_a_marked_edge_and_a_key_share_their_words(qt_app: QApplication) -> None:
    """Eine Quelle für beide: ``labels.edge_label`` und die Schlüsselbeschriftung."""
    from types import SimpleNamespace

    from app.ui.labels import edge_label
    from app.ui.unlisted_choice import unlisted_text

    marked = edge_label(
        SimpleNamespace(direction=(0.0, 0.0, 1.0), middle=(-20.0, -15.0, 10.0), length=20.0)
    )
    lie, size, place = marked.split(" · ")
    assert size == length(20.0)
    assert unlisted_text(EDGE, "edges") == f"{lie} · {place}"


def test_an_unknown_identifier_never_breaks_the_field() -> None:
    from app.ui.unlisted_choice import unlisted_text

    for identifier, kind in (("seltsam", "feature"), ("e:kaputt", "edges"), ("", "object")):
        said = unlisted_text(identifier, kind)
        assert said and not RAW.search(said), said


@contextmanager
def _dialog(operation: str, values: dict[str, Any], **extra: Any) -> Iterator[Any]:
    from app.ui.op_dialog import OperationDialog

    bootstrap.load_operations()
    dialog = OperationDialog(
        REGISTRY.get(operation), {"obj_1": "Quader"}, None, values=values, **extra
    )
    try:
        dialog.show()
        yield dialog
    finally:
        dialog.reject()
        dialog.deleteLater()


def _visible_texts(dialog: QWidget) -> list[str]:
    texts = [combo.currentText() for combo in dialog.findChildren(QComboBox)]
    for listing in dialog.findChildren(QListWidget):
        texts += [listing.item(row).text() for row in range(listing.count())]
    return texts


def test_the_chamber_field_names_the_refused_face(qt_app: QApplication) -> None:
    """Der Weg *Anderes Merkmal wählen* endet im Feld *Kammer* — mit „Fläche 1“."""
    from app.ui.unlisted_choice import unlisted_text

    with _dialog(
        "resize_chamber", {"at_feature": "face_1"}, features={"hole_1": "Bohrung 1"}
    ) as dialog:
        qt_app.processEvents()
        combo = dialog._editors["at_feature"]
        assert combo.currentText() == unlisted_text("face_1", "feature")
        assert combo.currentData() == "face_1"
        assert dialog.values()["at_feature"] == "face_1"
        assert not [text for text in _visible_texts(dialog) if RAW.search(text)]


def test_a_feature_list_names_a_value_it_does_not_offer(qt_app: QApplication) -> None:
    from app.ui.unlisted_choice import unlisted_text

    with _dialog(
        "pattern_feature", {"at_features": ["fillet_1"]}, features={"hole_1": "Bohrung 1"}
    ) as dialog:
        qt_app.processEvents()
        texts = _visible_texts(dialog)
        assert unlisted_text("fillet_1", "feature") in texts, texts
        assert not [text for text in texts if RAW.search(text)]
        assert dialog.values()["at_features"] == ["fillet_1"]


def test_single_edges_name_a_kept_key(qt_app: QApplication) -> None:
    """*Verrunden* an einem Netz: Die gespeicherte Kante steht mit Lage und Ort da."""
    from app.ui.unlisted_choice import unlisted_text

    with _dialog("fillet_edges", {"edges": "named", "edge_keys": EDGE}, edges={}) as dialog:
        qt_app.processEvents()
        texts = _visible_texts(dialog)
        assert unlisted_text(EDGE, "edges") in texts, texts
        assert not [text for text in texts if RAW.search(text)]
        assert dialog.values()["edge_keys"] == EDGE


def test_a_source_and_an_image_field_name_a_missing_value(qt_app: QApplication) -> None:
    from app.ui.unlisted_choice import unlisted_text

    bootstrap.load_operations()
    image_ops = [
        spec
        for spec in REGISTRY.all()
        if any(entry.kind == "image" for entry in spec.params.spec())
    ]
    # Ohne Dateiwähler steht eine Quelle in derselben Auswahl wie ein Objekt.
    source_ops = [
        spec
        for spec in REGISTRY.all()
        if any(entry.kind == "source" and not entry.internal for entry in spec.params.spec())
    ]
    assert image_ops and source_ops
    # Das Hauptfenster gibt dem Quellenfeld immer seinen Dateiwähler mit
    # (``pick_source``); dann ist es ein Bildwähler, der „Datei“ sagen muss,
    # nicht „Bild“ (Review 2 F2a/D, D4 zu FD-187).
    for spec, kind, identifier, extra in (
        (image_ops[0], "image", "src_4", {}),
        (source_ops[0], "source", "src_3", {}),
        (source_ops[0], "source", "src_3", {"pick_source": lambda: None}),
    ):
        name = next(entry.name for entry in spec.params.spec() if entry.kind == kind)
        with _dialog(spec.name, {name: identifier}, images={}, **extra) as dialog:
            qt_app.processEvents()
            texts = _visible_texts(dialog)
            assert unlisted_text(identifier, kind) in texts, (spec.name, texts)
            assert dialog.values()[name] == identifier
