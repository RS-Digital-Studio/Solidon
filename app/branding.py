"""Product identity in exactly one place (Bauplan §37.1).

Everything that needs the name reads it from here, so a rename stays a one-line
change — including the distribution name and the environment variables.
"""

from __future__ import annotations

from typing import Final

#: Product name. Decided 2026-07-27.
APP_NAME: Final = "Formwerk"

#: Distribution name on PyPI and in the package metadata.
DISTRIBUTION_NAME: Final = "formwerk"

#: Rights holder, as it appears in LICENSE and the about dialog.
APP_VENDOR: Final = "RS Digital"

#: Reverse-domain identifier for keyring entries and platform integration.
APP_ID: Final = "de.rsdigital.formwerk"

#: Prefix for environment variables that belong to this application.
ENVIRONMENT_PREFIX: Final = "FORMWERK"

#: Project container extension (Bauplan §16.1).
PROJECT_SUFFIX: Final = ".p3d"

#: Application version, mirrored into every project file as ``app_version``.
APP_VERSION: Final = "0.0.1"

#: Copyright line for LICENSE, about dialog and installers.
COPYRIGHT: Final = f"Copyright (c) 2026 {APP_VENDOR}"
