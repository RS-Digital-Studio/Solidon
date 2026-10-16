"""Ein Wert, den die Liste nicht führt, heißt wie in den Meldungen (D3) und ohne Genus (D6).

Review 2 F2a/D: ``unlisted_choice`` und ``registry.feature_title_of`` machten
aus derselben Kennung verschiedene Namen — „obj_2:face_9“ an einem Zielfeld war
nur „Merkmal“, „hole_1.2“ in den Meldungen nur „Bohrung“. Und die Sätze
dahinter hingen im Italienischen und Französischen am Geschlecht des Namens
(„Faccia 1 · qui non è adatto“, „Image 4 · absent du projet“).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.core.registry.registry import feature_title_of
from app.i18n import set_language
from app.i18n.catalog import install_language
from app.ui.unlisted_choice import unlisted_text


@pytest.fixture
def german() -> Iterator[None]:
    install_language("de")
    set_language("de")
    yield


@pytest.mark.parametrize(
    ("identifier", "name"),
    [
        ("obj_2:face_9", "Fläche 9"),
        ("obj_2:hole_1", "Bohrung 1"),
        ("hole_1.2", "Bohrung 1.2"),
        ("face_3", "Fläche 3"),
    ],
)
def test_the_field_and_the_messages_name_an_identifier_alike(
    german: None, identifier: str, name: str
) -> None:
    assert feature_title_of(identifier) == name
    assert unlisted_text(identifier, "feature") == f"{name} · passt hier nicht"


def test_an_unknown_kind_stays_a_feature(german: None) -> None:
    assert unlisted_text("whatever", "feature") == "Merkmal · passt hier nicht"


@pytest.mark.parametrize(
    ("language", "identifier", "kind", "forbidden"),
    [
        ("it", "face_1", "feature", ("adatto", "adatta")),
        ("fr", "image_4", "image", ("absent", "absente")),
    ],
)
def test_the_sentence_does_not_depend_on_the_gender_of_the_name(
    language: str, identifier: str, kind: str, forbidden: tuple[str, ...]
) -> None:
    install_language(language)
    set_language(language)
    try:
        text = unlisted_text(identifier, kind)  # type: ignore[arg-type]
        assert not any(word in text for word in forbidden), text
    finally:
        install_language("de")
        set_language("de")
