"""Die Produktidentität an genau einer Stelle (Bauplan §37.1).

Alles, was den Namen braucht, liest ihn hier — eine Umbenennung bleibt so eine
Ein-Zeilen-Änderung, samt Distributionsname und Umgebungsvariablen.
"""

from __future__ import annotations

from typing import Final

#: Produktname. Entschieden am 27.07.2026.
APP_NAME: Final = "Formwerk"

#: Distributionsname auf PyPI und in den Paket-Metadaten.
DISTRIBUTION_NAME: Final = "formwerk"

#: Rechteinhaber, wie er in LICENSE und im Über-Dialog steht.
APP_VENDOR: Final = "RS Digital"

#: Reverse-Domain-Kennung für Schlüsselbund-Einträge und Plattform-Integration.
APP_ID: Final = "de.rsdigital.formwerk"

#: Präfix der Umgebungsvariablen, die zu dieser Anwendung gehören.
ENVIRONMENT_PREFIX: Final = "FORMWERK"

#: Wohin sich Kunden wenden — Fehlerberichte, Fragen, Interesse vor dem
#: Erscheinen. Ein Kanal, eine Adresse; sie steht im Über-Dialog, im
#: Fehlerbericht und auf der Website.
SUPPORT_ADDRESS: Final = "admin@rs-digital.org"

#: Endung des Projektcontainers (Bauplan §16.1).
PROJECT_SUFFIX: Final = ".p3d"

#: Anwendungsversion, gespiegelt in jede Projektdatei als ``app_version``.
APP_VERSION: Final = "0.0.1"

#: Copyright-Zeile für LICENSE, Über-Dialog und Installer.
COPYRIGHT: Final = f"Copyright (c) 2026 {APP_VENDOR}"
