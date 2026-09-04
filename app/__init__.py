"""Das Wurzelpaket der Anwendung.

Schichtenregel (Bauplan §8): ``app.core`` importiert nie aus ``app.ui``.
``app.ui`` und ``app.cli`` sind Einstiege oben auf dem Kern.
"""

import sys

if getattr(sys, "frozen", False):
    # Im ausgelieferten Paket reisen die vier Grenzdateien aus Konzept §2 C als
    # **Quelltext** (``module_collection_mode`` in der PyInstaller-Spec), damit
    # ``activation.integrity`` genau die Datei hashen kann, aus der Python sie
    # lädt. Diese Zusage hält nur, solange daneben kein ``__pycache__`` liegt:
    # CPython führt eine ``.pyc`` aus, sobald deren Kopf zu Änderungszeit und
    # Größe der Quelle passt — und beide Felder kann jeder setzen, der die
    # Installation erreicht. Die Prüfung sähe dann die unveränderte Quelle,
    # während fremder Bytecode läuft (Sicherheitsdurchsicht 04.09.2026).
    #
    # **Hier und nicht im Einstiegsmodul:** Dieses ``__init__`` läuft vor jedem
    # ``app.core``-Import, also auch vor dem ersten Laden einer Grenzdatei. In
    # ``app/ui/app.py`` wäre es zu spät — die Importzeilen dort ziehen den Kern
    # schon mit.
    #
    # In der Entwicklung bleibt der Zwischenspeicher erlaubt: Dort ist er
    # Geschwindigkeit, und ``intact()`` sucht die ``.pyc`` ebenfalls nur im
    # gefrorenen Zustand.
    sys.dont_write_bytecode = True
