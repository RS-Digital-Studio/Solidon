"""Ein gesperrter Knopf nennt seinen Grund — über alle Dialoge, nicht über einen.

`oberflaeche.md` sagt es für Zeilen eines Dialogs: „Ist eine Zeile gesperrt,
tragen beide Hälften den *Grund* statt des Satzes." Für Knöpfe gilt dasselbe,
und bis zum 03.09.2026 stand die Zusage an genau einem Fenster
(`test_no_locked_button_in_this_dialog_stays_silent` in
`test_print_settings_ui.py`). Dort hat sie beim ersten Lauf **drei** stumme
Knöpfe gefunden, wo die Handmessung einen gesehen hatte — zwei davon im
häufigsten Fall überhaupt, einem Rechner ohne eingerichteten Slicer.

Ein Test je Dialog fängt den nächsten Dialog nicht. Deshalb hier eine Liste,
und wer einen Dialog dazunimmt, trägt ihn ein.

**Warum am gebauten Fenster und nicht am Quelltext:** Der schlimmste der drei
Funde stand im Quelltext richtig da — `self.slice_button.setToolTip(reason)`,
direkt unter dem `setEnabled`. Nur war `reason` in dem Zweig leer, der den
häufigsten Fall trifft. Eine Textsuche hätte ihn abgenickt.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QDialog, QPushButton

from app.core import updates
from app.ui.changes_dialog import ChangesDialog
from app.ui.comfy_dialog import ComfySetupDialog
from app.ui.dialogs import (
    AboutDialog,
    ActivationDialog,
    DonationDialog,
    KeyDialog,
    OfflineActivationDialog,
)
from app.ui.filament_picker import NewFilamentDialog, SlicerFilamentDialog
from app.ui.first_run import FirstRunDialog
from app.ui.install_dialog import InstallDialog
from app.ui.print_disclosure import PrintDisclosureDialog
from app.ui.session import Session
from app.ui.settings import UiSettings
from app.ui.support_dialog import SupportDialog
from app.ui.update_dialog import UpdateDialog
from app.ui.variants_dialog import VariantsDialog

MESHES = Path(__file__).parent / "data" / "meshes"


def _release() -> updates.Release:
    """Eine Fassung, wie sie der Update-Weg vom Server bekommt."""
    return updates.Release(
        version="9.9.9",
        url="https://solidon3d.de/dl/Solidon3D-9.9.9.exe",
        notes="Der erste Punkt.\nDer zweite Punkt.",
    )


#: Wie jeder Dialog gebaut wird. Die Bauanleitungen stammen aus den Tests, die
#: es zu den einzelnen Fenstern schon gibt — zwei Aufbauten desselben Dialogs
#: laufen auseinander, sobald jemand an einem davon etwas ändert.
BUILDERS: dict[str, Callable[[Session], QDialog]] = {
    "SupportDialog": lambda _session: SupportDialog(
        message="Der Deckel sitzt schief.", error=ValueError("kaputt")
    ),
    "UpdateDialog": lambda _session: UpdateDialog(_release()),
    "ChangesDialog": lambda _session: ChangesDialog(),
    "AboutDialog": lambda _session: AboutDialog(),
    "DonationDialog": lambda _session: DonationDialog(),
    "NewFilamentDialog": lambda _session: NewFilamentDialog(
        name="Werkstattrolle", colour="#123456", material_type="PETG"
    ),
    "VariantsDialog": lambda session: VariantsDialog(session),
    "KeyDialog": lambda _session: KeyDialog(settings=UiSettings()),
    "PrintDisclosureDialog": lambda _session: PrintDisclosureDialog(share=True, parent=None),
    # **Mit leerer Liste, und das ist der Fall und nicht die Ausnahme.** Ein
    # Rechner ohne installierten Slicer bringt keine Filamentprofile mit; wer
    # den Dialog nur mit Bestand prüft, prüft den selteneren Zustand.
    "SlicerFilamentDialog": lambda _session: SlicerFilamentDialog(None, []),
    # **Die Freischaltung, und sie ist der Fall mit den meisten Sperren:** vier
    # von fünf Knöpfen sind im Ausgangszustand zu, weil weder Schlüssel noch
    # Lizenz eingetragen sind. Genau die Lage, in der ein neuer Kunde den
    # Dialog zum ersten Mal sieht.
    "ActivationDialog": lambda _session: ActivationDialog(),
    "OfflineActivationDialog": lambda _session: OfflineActivationDialog(UiSettings()),
    "FirstRunDialog": lambda _session: FirstRunDialog(settings=UiSettings()),
    "InstallDialog": lambda _session: InstallDialog(),
    "ComfySetupDialog": lambda _session: ComfySetupDialog(),
}


@pytest.fixture
def session(qt_app: QApplication) -> Session:
    """Eine Sitzung mit einem Körper — ohne ihn hat mancher Dialog nichts zu zeigen."""
    made = Session()
    made.import_model(MESHES / "cube_clean.stl", raise_on_error=True)
    made.evaluate_now()
    return made


@pytest.mark.parametrize("name", sorted(BUILDERS))
def test_no_locked_button_stays_silent(name: str, session: Session, qt_app: QApplication) -> None:
    """Jeder gesperrte, sichtbare Knopf nennt seinen Grund — an allen drei Kanälen.

    Tooltip für die Maus, Statuszeile für den Blick nach unten, zugängliche
    Beschreibung für den Bildschirmleser: Ein Grund, den nur die Maus findet,
    ist für einen Bildschirmleser keiner (Regel 18).

    **Gezeigt, nicht nur gebaut.** Vor dem ``show()`` steht ein Dialog auf
    halbem Weg — Suchläufe sind nicht angelaufen, Zustände nicht gesetzt, und
    ein Test davor prüfte einen Zustand, den ein Kunde nie sieht.
    """
    dialog = BUILDERS[name](session)
    try:
        dialog.show()
        for _ in range(10):
            qt_app.processEvents()

        silent = [
            button.text()
            for button in dialog.findChildren(QPushButton)
            if button.isVisibleTo(dialog)
            and button.text()
            and not button.isEnabled()
            and not (button.toolTip() and button.statusTip() and button.accessibleDescription())
        ]
        assert not silent, f"{name}: gesperrt und ohne Grund: {silent}"
    finally:
        dialog.close()
