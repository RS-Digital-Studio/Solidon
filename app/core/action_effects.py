"""Was eine angebotene Handlung außer ihrem Zweck verändert (Produktkompass 4.3, RM-090).

Die Befundkarte beantwortet als fünfte Frage, welche Handlung passt **und
was sie zusätzlich verändern kann**. Die Antwort gehört dem Kern, nicht dem
Fenster: Er weiß, dass *Auf dem Bett anordnen* jeden Körper bewegt und
*Dreiecke verringern* feine Rundungen kantiger macht. Die Oberfläche liest
nur ``side_effect``; eine zweite Liste dort liefe auseinander.

Jede Kennung, die der Kern als Handlung anbietet, steht hier — mit einem Satz
zu ihrer Nebenfolge oder ausdrücklich mit „ändert nichts am Modell“.
``tests/test_action_effects.py`` sucht die Kennungen im Kern und verlangt den
Eintrag in beide Richtungen.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from app.i18n import TranslatableText, _

#: Ansehen, Zeigen, Suchen, Konto und Dateien des Rechners — das Modell bleibt.
NOTHING: Final = _("Ändert nichts am Modell.")

#: Ein Weg in eine Eingabe, die erst beim Übernehmen etwas ändert.
WHEN_APPLIED: Final = _(
    "Öffnet die Eingabe dazu; geändert wird erst beim Übernehmen, mit Vorschau und Strg+Z."
)

_REPAIR: Final = _(
    "Schließt Löcher und richtet die Flächen aus; an den Rändern der Löcher kann sich "
    "die Form leicht ändern. Strg+Z nimmt es zurück."
)
_FEWER_TRIANGLES: Final = _(
    "Weniger Dreiecke: Feine Rundungen und Schrift werden kantiger, die Maße bleiben."
)
_STEP_CHANGES: Final = _("Ändert den Schritt; alle Schritte danach rechnen neu.")
_PRINT_TARGET: Final = _(
    "Wechselt das Druckziel; alle Druckprüfungen werden für den neuen Drucker neu bewertet."
)

SIDE_EFFECTS: Final[Mapping[str, TranslatableText]] = {
    # Ansehen und Zeigen
    "show_details": NOTHING,
    "show_feature": NOTHING,
    "show_history": NOTHING,
    "show_layers": NOTHING,
    "show_location": NOTHING,
    "show_locations": NOTHING,
    "show_output": NOTHING,
    "show_step_values": NOTHING,
    "show_support_need": NOTHING,
    "sketch.check_position": NOTHING,
    "pick_feature": NOTHING,
    "pick_in_tree": NOTHING,
    "texture.pick_cylinder": NOTHING,
    "sketch.pick_face": NOTHING,
    "sketch.pick_round_feature": NOTHING,
    "pick_elsewhere": NOTHING,
    "enlarge_radius": NOTHING,
    "shrink_radius": NOTHING,
    "recognize_local": _(
        "Sucht Merkmale an einer Stelle; übernommen wird erst, was Sie bestätigen."
    ),
    "recognize_fully": _(
        "Ändert keine Geometrie; die vollständige Erkennung kann einige Minuten rechnen."
    ),
    # Programm, Konto, Dateien des Rechners
    "cancel": NOTHING,
    "cancel_split": NOTHING,
    "retry": NOTHING,
    "retry_send": NOTHING,
    "reload": NOTHING,
    "restore_backup": _("Ändert nichts am Modell; das Filamentlager bekommt den älteren Stand."),
    "set_aside_file": _("Ändert nichts am Modell; das Filamentlager beginnt leer."),
    "save_elsewhere": NOTHING,
    "save_report": NOTHING,
    "send_by_mail": NOTHING,
    "report_error": NOTHING,
    "check_updates": NOTHING,
    "open_download_page": NOTHING,
    "open_in_browser": NOTHING,
    "install": NOTHING,
    "open_settings": NOTHING,
    "check_profile": NOTHING,
    "choose_slicer": NOTHING,
    "export_only": NOTHING,
    "export_as_mesh": _("Ändert nichts am Modell; die Datei trägt Dreiecke statt Flächen."),
    "split_filament_files": _("Ändert nichts am Modell; je Filament entsteht eine eigene Datei."),
    "repack_file": NOTHING,
    "choose_another_file": NOTHING,
    "buy_licence": NOTHING,
    "enter_licence_key": NOTHING,
    "activate_online": NOTHING,
    "activate_offline": NOTHING,
    "deactivate_device": NOTHING,
    "adopt_printer": _(
        "Ändert nichts am Modell; der Drucker steht danach auch in anderen Projekten."
    ),
    # Wege in eine Eingabe
    "choose": WHEN_APPLIED,
    "correct_input": WHEN_APPLIED,
    "change_step": WHEN_APPLIED,
    "change_selection": WHEN_APPLIED,
    "open_sketch": WHEN_APPLIED,
    "open_print_settings": WHEN_APPLIED,
    "calibrate_material": WHEN_APPLIED,
    "sketch.pick_plane": WHEN_APPLIED,
    # Rat an einen Schritt, eingelöst in seinem Dialog (``dialogs.unhandled_advice``)
    "check_input": NOTHING,
    "write_target": WHEN_APPLIED,
    "coarser_pitch": WHEN_APPLIED,
    "smaller_diameter": WHEN_APPLIED,
    "use_parts": WHEN_APPLIED,
    "fewer_iterations": WHEN_APPLIED,
    "fix_parent": WHEN_APPLIED,
    "pick_face": WHEN_APPLIED,
    "pick_image": WHEN_APPLIED,
    "use_planar": WHEN_APPLIED,
    "use_texture": WHEN_APPLIED,
    "use_reachable": WHEN_APPLIED,
    "smaller_bodies": WHEN_APPLIED,
    "texture.wrap_flat": WHEN_APPLIED,
    "sketch.enter_height": WHEN_APPLIED,
    "sketch.flip_plane": WHEN_APPLIED,
    "sketch.use_all_regions": WHEN_APPLIED,
    "use_suggested_name": _("Ändert nur den Namen; Form und Verweise bleiben."),
    # Druckziel
    "choose_printer": _PRINT_TARGET,
    # Lage
    "place_on_bed": _("Senkt den Körper bis auf das Bett; seitlich bleibt er, wo er ist."),
    "arrange_on_bed": _(
        "Verschiebt und verteilt alle Körper der Szene, auch die, die schon gut lagen."
    ),
    "orient_for_print": _(
        "Dreht den Körper; Überhänge, Stützen und die sichtbare Unterseite ändern sich."
    ),
    "scale_to_fit": _("Verkleinert alle Maße gleichmäßig, auch Bohrungen und Passungen."),
    # Teilen und Zerlegen
    "split_model": _("Aus einem Körper werden mehrere Stücke mit Schnittflächen und Verbindern."),
    "split_along_line": _("Aus einem Körper werden mehrere, geteilt an der gezeichneten Linie."),
    "split_bodies": _(
        "Aus einem Körper werden mehrere; jedes Teil kann eigenes Material und eigene Lage "
        "bekommen."
    ),
    "split_and_retry": _(
        "Zerlegt den Körper vor dem Schritt in seine Teile und rechnet den Schritt neu."
    ),
    "release_protection": _(
        "Hebt die Sperre auf; Schnitte dürfen danach auch durch die geschützten Flächen gehen."
    ),
    # Netz
    "repair_and_retry": _REPAIR,
    "repair_before_and_retry": _REPAIR,
    "repair_mesh": _REPAIR,
    "resolve_intersections": _(
        "Vereinigt die sich durchdringenden Teile; innen liegende Flächen fallen weg."
    ),
    "leave_open": _("Nimmt die geschlossene Öffnung zurück; der Körper ist danach offen."),
    "give_thickness": _("Macht aus der Fläche eine Wand mit der Mindestdicke des Materials."),
    "remove_small_parts": _("Entfernt die kleinen Einzelteile aus dem Körper."),
    "decimate_mesh": _FEWER_TRIANGLES,
    "decimate_and_retry": _FEWER_TRIANGLES,
    "remesh_and_retry": _("Teilt die Dreiecke feiner; die Form bleibt, das Netz wird größer."),
    "mesh_and_retry": _(
        "Macht aus dem Körper ein Dreiecksmodell; Rundungen bestehen danach aus geraden "
        "Teilstücken."
    ),
    "mesh_to_exact": _(
        "Macht aus dem Netz einen Körper mit Flächen und Kanten; was keine erkannte Form "
        "hat, bleibt aus ebenen Dreiecken."
    ),
    "use_voxel_stage": _("Rechnet auf einem Raster; Maße und Kanten werden gerundet."),
    "recount_and_retry": _STEP_CHANGES,
    # Schritte
    "resize_the_widening": _("Ändert die Senkung im selben Verhältnis wie die Bohrung."),
    "change_creating_step": WHEN_APPLIED,
    "reactivate_step": _("Schaltet den Schritt wieder ein; die Schritte danach rechnen neu."),
    "suppress_step": _("Schaltet den Schritt aus; was auf ihm aufbaut, ruht mit."),
    "suppress_along": _(
        "Schaltet auch diesen Schritt aus; er rechnet erst wieder, wenn Sie ihn einschalten."
    ),
    "stop_inserting": _("Ändert nichts am Modell; neue Schritte kommen wieder ans Ende."),
    "take_back_stroke": _("Nimmt diesen Formzug aus der Sitzung; die übrigen Züge bleiben."),
    "keep_saved_parts": _(
        "Rechnet eigene Bausteine so, wie das Projekt gespeichert wurde; Ihre neuere "
        "Version bleibt im Bausteinordner."
    ),
    "sketch.clear_axis_feature": _STEP_CHANGES,
    "sketch.clear_up_to": _STEP_CHANGES,
    "sketch.use_global_plane": _STEP_CHANGES,
}


def side_effect(action_id: str) -> TranslatableText | None:
    """Der Satz zur Nebenfolge einer Handlung, ``None`` für eine unbekannte Kennung."""
    return SIDE_EFFECTS.get(action_id)


def effect_worth_showing(action_id: str) -> bool:
    """Ob die Nebenfolge mehr sagt als „ändert nichts“ oder „erst beim Übernehmen“.

    Nur dann steht sie sichtbar unter dem Hauptknopf (RM-508): Die beiden
    Floskeln :data:`NOTHING` und :data:`WHEN_APPLIED` standen unter der Mehrzahl
    aller Handlungen und verdrängten im Bericht die nächste Zeile. Sie bleiben
    in Kurzhilfe und Beschreibung des Knopfes.
    """
    effect = SIDE_EFFECTS.get(action_id)
    return effect is not None and effect not in (NOTHING, WHEN_APPLIED)
