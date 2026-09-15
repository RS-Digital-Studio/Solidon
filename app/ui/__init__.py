"""PySide6-Oberfläche. Darf ``app.core`` benutzen; die Gegenrichtung ist
verboten (§8)."""

import os

# **PySide legt seine Typen erst beim ersten Zugriff an — und das reißt den
# Prozess.** Mit dieser Vorgabe (PySide 6.11.2) stand ``QSpinBox`` nach
# ``import PySide6.QtWidgets`` nicht im Modul, sondern entstand, wenn ein
# Modul den Namen las; welche Typen wann entstehen, hing damit an der
# Importreihenfolge der Oberfläche. Zwei Risse gehen darauf zurück, beide
# ``0xc0000374`` (Heap) im ``gc.collect`` nach dem Abbau eines Fensters,
# beide deterministisch in ``tests/test_filament_picker.py``: am 14.09.2026
# ein ungenutztes ``QMouseEvent`` in ``labels.py``, am 15.09.2026 ``QSpinBox``
# in ``panels.py`` — derselbe Import, über ``QtWidgets.QSpinBox`` geschrieben,
# war grün. Mit ``PYSIDE6_OPTION_LAZY=0`` laufen beide Stände durch; gemessen
# am 15.09.2026, Preis 60 ms beim PySide-Import und 6 MB. Die Variable muss
# stehen, **bevor** ``PySide6`` zum ersten Mal geladen wird — deshalb hier,
# beim Betreten des Pakets, und in ``app.py`` als erster Import, weil das
# gebaute Paket diese Datei als Skript startet und das Paket sonst erst hinter
# ``PySide6`` an der Reihe wäre. ``tests/test_language_rules.py`` hält beides.
os.environ.setdefault("PYSIDE6_OPTION_LAZY", "0")
