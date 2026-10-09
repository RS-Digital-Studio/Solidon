"""Das Wurzelpaket der Anwendung.

Schichtenregel (Bauplan §8): ``app.core`` importiert nie aus ``app.ui``.
``app.ui`` und ``app.cli`` sind Einstiege oben auf dem Kern.
"""

import os
import sys

# **Ein BLAS-Faden, bevor NumPy lädt** (RM-567). OpenBLAS legt beim Laden für
# jeden Rechenkern einen Puffer an, einmal für ``numpy`` und einmal für
# ``scipy``: gemessen 1 522 MB Zusage an 32 Kernen schon nach dem Import, mit
# einem Faden 44 MB — auf einem Kundenrechner mit 16 Fäden rund 1 GB, die
# nichts tun. Die Rechnungen werden davon nicht langsamer: Einlesen, Erkennen,
# Schneiden und Orientieren brauchten am Laptop-Riser mit einem, vier und
# allen Fäden dieselbe CPU-Zeit (08.10.2026, ``paket-l.md``). Und es ist der
# Stand, an dem Suite und CI ihre Sollwerte rechnen (``tests.md``). Hier, weil
# dieses ``__init__`` vor jedem anderen Modul der Anwendung läuft; ein gesetzter
# Wert gilt weiter, und den Hilfsprozess des Netzkerns startet
# ``kernel_process.HELPER_ENVIRONMENT`` ohnehin mit einem.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

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
