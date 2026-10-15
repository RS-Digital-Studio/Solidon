"""Bettbeschreibung und zusammengefasste Handlungen bleiben in der Anzeigesprache."""

import pytest

from app.core.action_effects import side_effect
from app.core.perceive.actions import FeatureAction
from app.i18n import _, set_language
from app.i18n.catalog import available_languages, install_language
from app.ui.panels import _folded

BED_WORDS = {
    "de": ("Setzt", "Seitlich bleibt er, wo er ist."),
    "en": ("Places", "Sideways it stays where it is."),
    "es": ("Coloca", "Lateralmente se queda donde está."),
    "fr": ("Pose", "Latéralement, il reste où il est."),
    "it": ("Posiziona", "Lateralmente resta dov'è."),
    "pt": ("Coloca", "Lateralmente fica onde está."),
}
FOLDED_TITLES = {
    "de": ("Merkmal verschieben und drehen", "Merkmal verschieben, drehen und verdoppeln"),
    "en": ("Move feature and Turn feature", "Move feature, Turn feature and Duplicate feature"),
    "es": (
        "Mover característica y Girar característica",
        "Mover característica, Girar característica y Duplicar característica",
    ),
    "fr": (
        "Déplacer la caractéristique et Faire pivoter la caractéristique",
        "Déplacer la caractéristique, Faire pivoter la caractéristique "
        "et Dupliquer la caractéristique",
    ),
    "it": (
        "Sposta caratteristica e Ruota caratteristica",
        "Sposta caratteristica, Ruota caratteristica e Duplica caratteristica",
    ),
    "pt": (
        "Mover característica e Rodar característica",
        "Mover característica, Rodar característica e Duplicar característica",
    ),
}


@pytest.mark.parametrize("language", available_languages())
def test_bed_description_does_not_assume_a_downward_move(language: str) -> None:
    """Der gleiche gespeicherte Satz gilt auch für einen Körper unter dem Bett."""
    effect = side_effect("place_on_bed")
    assert effect is not None
    install_language(language)
    set_language(language)
    verb, lateral_position = BED_WORDS[language]
    assert str(effect).startswith(verb + " ")
    assert str(effect).endswith(lateral_position)


@pytest.mark.parametrize("language", available_languages())
@pytest.mark.parametrize("count", (2, 3))
def test_folded_actions_translate_titles_and_connector_after_language_switch(
    language: str, count: int
) -> None:
    """Zwei oder drei echte Handlungstitel teilen den Grund, nicht ihre Sprache."""
    reason = "Eine Fläche gehört zur Oberfläche des Körpers."
    actions = [
        FeatureAction(title=_(title), op=None, reason=reason)
        for title in ("Merkmal verschieben", "Merkmal drehen", "Merkmal verdoppeln")
    ]
    assert str(actions[0].title) == "Merkmal verschieben"
    install_language(language)
    set_language(language)
    folded = _folded(actions[:count])
    assert len(folded) == 1
    assert str(folded[0].title) == FOLDED_TITLES[language][count - 2]
    assert str(folded[0].reason) == reason


@pytest.mark.parametrize("language", available_languages())
def test_other_reasons_and_enabled_actions_keep_their_own_rows(language: str) -> None:
    """Die Sprachkorrektur verschluckt keine andere Absage oder ausführbare Handlung."""
    actions = [
        FeatureAction(title=_("Merkmal verschieben"), op="move_feature"),
        FeatureAction(title=_("Merkmal drehen"), op=None, reason="Erster Grund"),
        FeatureAction(title=_("Merkmal verdoppeln"), op=None, reason="Zweiter Grund"),
    ]
    install_language(language)
    set_language(language)
    assert _folded(actions) == actions
