"""Ob gerade geändert werden darf — die eine Auskunft für jeden Zugang (FD-5).

Die Hürde liegt im Kern (``activation.require``, ``kern.md`` „Die
Lizenzgrenze“); die Oberfläche graut vorher aus und nennt den Grund. Menü,
Suche und Karte der Handlungen fragten den Freischaltzustand je für sich ab,
Prüfbericht, Merkmalfenster und Kontextmenüs gar nicht: In der Demo und ohne
Geräteaktivierung stand *Auf das Bett setzen* bedienbar da, und der Klick
endete im Meldungsfenster. Jeder Zugang, der eine ändernde Handlung anbietet,
fragt deshalb hier.

Nur Lesendes läuft weiter (Konzept §2 C). Was eine Handlung des Kerns ist
(``app.core.errors``), gilt als ändernd, solange sie nicht in
:data:`READING_ACTIONS` steht — eine neue Handlung ist im gesperrten Zustand
lieber grau als eine Sackgasse.
"""

from __future__ import annotations

from typing import Final

from app.core import activation
from app.ui.dialogs import licence_lock_line

#: Handlungen des Kerns, die nichts ändern und nichts herausgeben: zeigen,
#: erklären, einen Dialog zum Ansehen öffnen, freischalten, Hilfe holen. Sie
#: bleiben im gesperrten Zustand bedienbar; jede andere graut aus.
READING_ACTIONS: Final[frozenset[str]] = frozenset(
    {
        "activate_offline",
        "activate_online",
        "adopt_printer",
        "buy_licence",
        "cancel",
        "cancel_split",
        "check_profile",
        "check_updates",
        "choose_printer",
        "choose_slicer",
        "deactivate_device",
        "enter_licence_key",
        "install",
        "open_download_page",
        "open_in_browser",
        "open_print_settings",
        "open_settings",
        "report_error",
        "set_up_chat",
        "show_details",
        "show_feature",
        "show_history",
        "show_layers",
        "show_location",
        "show_locations",
        "show_output",
        "show_step_values",
        "show_support_need",
        "stop_inserting",
        "try_key_again",
        "use_voxel_stage",
    }
)


def change_refusal() -> str:
    """Warum gerade nichts geändert werden darf — leer, wenn es geht.

    Der Satz kommt aus :func:`~app.ui.dialogs.licence_lock_line`, derselben
    Quelle wie Statuszeile und Freischaltdialog; er nennt je Zustand den
    nächsten Schritt (Schlüssel, Geräteaktivierung, Neuinstallation).
    """
    state = activation.state()
    return "" if state.unlocked else licence_lock_line(state)


def action_refusal(action_id: str) -> str:
    """Warum diese Handlung eines Befunds oder Fehlers gerade nicht geht — oder leer."""
    return "" if action_id in READING_ACTIONS else change_refusal()
