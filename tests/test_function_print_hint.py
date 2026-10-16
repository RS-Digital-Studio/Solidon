"""Der einmalige Druckhinweis im Profil der Funktionsfälle (Paket F8, FD-121).

Der Hinweis zu den Druckeinstellungen erscheint einmal, vor den ersten
Druckeinstellungen. Im unbestätigten Profil lag er in jedem Fall über der
Zielfläche: An *Drucker wählen* und *Druckeinstellungen öffnen* maß der
Prüfstand den Hinweis (258 px, 27 Wörter) statt der Fläche (Lauf 043, d08 N20).
Jetzt gilt er im Profil als gesehen; nur der Fall seiner eigenen Zeile
verlangt ihn mit der Vorbedingung ``druckhinweis = "offen"``.
"""

from __future__ import annotations

from tools import function_setup


def test_the_prepared_profile_has_seen_the_print_hint() -> None:
    """Ohne Angabe ist der Hinweis gesehen — der Fall misst die Zielfläche."""
    from app.ui.print_disclosure import (
        PrintDisclosureResult,
        disclosure_is_current,
        ensure_print_disclosure,
    )
    from app.ui.settings import load_settings

    function_setup.write_profile(function_setup.Variant())
    settings = load_settings()
    assert disclosure_is_current(settings)
    assert ensure_print_disclosure(settings, None) is PrintDisclosureResult.ALREADY_SEEN
    assert settings.ai_disclosure_version == "", "der KI-Hinweis bleibt Teil des Kundenwegs"


def test_the_row_of_the_hint_keeps_it_open() -> None:
    """Die Zeile ``dialog:print_disclosure_dialog`` misst den Hinweis selbst."""
    from app.ui.print_disclosure import disclosure_is_current

    open_hint = function_setup.Variant(preconditions={function_setup.PRINT_HINT: "offen"})
    assert not disclosure_is_current(function_setup.profile_settings(open_hint))
    seen = function_setup.Variant(preconditions={function_setup.PRINT_HINT: "gesehen"})
    assert disclosure_is_current(function_setup.profile_settings(seen))


def test_the_hint_is_a_state_of_the_profile_without_a_counter_run() -> None:
    """Die Vorbedingung stellt das Profil her, nicht die Maschine — und hat keinen Gegenlauf.

    Gesehen gäbe es die Zeile des Hinweises nicht; ein Gegenlauf in diesem
    Zustand wäre ein Fall ohne Fläche.
    """
    applied = function_setup.apply_preconditions({function_setup.PRINT_HINT: "offen"})
    assert applied == {function_setup.PRINT_HINT: "offen"}
    _base, others = function_setup.spec_variants(
        {"preconditions": {function_setup.PRINT_HINT: "offen"}}
    )
    assert others == []


def test_two_profiles_of_the_same_variant_are_the_same() -> None:
    """Der Zeitpunkt des Hinweises ist fest: zwei Läufe schreiben dasselbe Profil."""
    first = function_setup.profile_settings(function_setup.Variant())
    second = function_setup.profile_settings(function_setup.Variant())
    assert first.print_disclosure_at_utc == second.print_disclosure_at_utc
    assert first.print_disclosure_at_utc == function_setup.PROFILE_MOMENT
