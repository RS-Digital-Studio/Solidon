"""Was eine andere Angabe bestimmt, steht vor ihr — im Register und im Dialog.

Robert, 29.09.2026, über die Druckeinstellungen: „der Slicer unten und den
Drucker oben, obwohl der Drucker vom Slicer abhängig ist, ist nicht gut — an so
etwas auch bei allen denken, Zusammenhänge". Die Fenster prüfen ihre Folge je
Dialog (``test_print_settings_ui``); hier steht die Zusage für alles, was aus
dem Register entsteht — Operationsdialog, Handbuchtabelle, Werkzeugschema.
"""

from __future__ import annotations

from app.core.bootstrap import load_operations
from app.core.registry import REGISTRY


def test_a_switch_stands_before_the_fields_it_governs() -> None:
    """Ein Umschalter steht vor den Feldern, die er ein- oder ausschaltet.

    Und ein Vorderfeld hängt an keinem Umschalter hinter der Klappe: Dort
    stand *Durchgehend*, während die *Tiefe*, die es ausschaltet, vorn stand —
    wer durchschneiden wollte, fand den Haken nicht und tippte eine große Tiefe
    ein. *Gezeichnete Bahn* stand hinten, obwohl die Wahl „gezeichnet" vorn
    sie verlangt; der Zwilling ohne Schnitt hatte sie vorn.
    """
    load_operations()
    found: list[str] = []
    checked = 0
    for spec in REGISTRY.all():
        entries = list(spec.params.spec())
        position = {entry.name: index for index, entry in enumerate(entries)}
        for entry in entries:
            if entry.depends_on is None or entry.depends_on[0] not in position:
                continue
            switch = entry.depends_on[0]
            checked += 1
            governing = entries[position[switch]]
            if position[switch] > position[entry.name]:
                found.append(f"{spec.name}.{entry.name} steht vor {switch}")
            if entry.placement == "front" and governing.placement != "front":
                found.append(f"{spec.name}.{entry.name} steht vorn, {switch} dahinter")
    assert checked > 50, f"nur {checked} Bedingungen gefunden — ist das Register geladen?"
    assert not found, "\n".join(found)
