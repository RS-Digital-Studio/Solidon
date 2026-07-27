"""Product identity in exactly one place (Bauplan §37.1).

The product name is not decided yet. Until it is, every part of the code that
needs a name reads it from here, so the decision stays a one-line change.
"""

from __future__ import annotations

from typing import Final

#: Working title. Candidates in Bauplan §37.1: Formwerk, Passform, Werkbank.
APP_NAME: Final = "3D-Agent"

#: Vendor / organisation shown in the about dialog and used for user data paths.
APP_VENDOR: Final = "RS Digital"

#: Reverse-domain identifier for keyring entries and platform integration.
APP_ID: Final = "de.rsdigital.threedagent"

#: Project container extension (Bauplan §16.1). Independent of the final name.
PROJECT_SUFFIX: Final = ".p3d"

#: Application version, mirrored into every project file as ``app_version``.
APP_VERSION: Final = "0.0.1"
