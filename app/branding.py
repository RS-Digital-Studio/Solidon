"""Die Produktidentität an genau einer Stelle (Bauplan §37.1).

Alles, was den Namen braucht, liest ihn hier — eine Umbenennung bleibt so eine
Ein-Zeilen-Änderung, samt Distributionsname und Umgebungsvariablen.
"""

from __future__ import annotations

from datetime import date
from typing import Final

#: Produktname. Entschieden am 27.07.2026 als „Formwerk", geändert am
#: 07.08.2026 — siehe ``konzepte/namensentscheidung-solidon.md``: eine
#: Wort-/Bildmarke „3D FORMWERK" ist seit dem 03.08.2026 für „Entwurf von
#: 3D-Modellen für den 3D-Druck" bestandskräftig, also für genau das, was
#: diese Anwendung tut.
#:
#: Der volle Name steht auf Fenstertitel, Website, Installer und
#: Lizenzschlüssel. In Fließtext und Docstrings heißt es kurz „Solidon".
APP_NAME: Final = "Solidon3D"

#: Distributionsname auf PyPI und in den Paket-Metadaten.
DISTRIBUTION_NAME: Final = "solidon3d"

#: Rechteinhaber, wie er in LICENSE und im Über-Dialog steht.
APP_VENDOR: Final = "RS Digital"

#: Reverse-Domain-Kennung für Schlüsselbund-Einträge und Plattform-Integration.
APP_ID: Final = "de.rsdigital.solidon3d"

#: Präfix der Umgebungsvariablen, die zu dieser Anwendung gehören.
ENVIRONMENT_PREFIX: Final = "SOLIDON3D"

#: Wohin sich Kunden wenden — Fehlerberichte, Fragen, Interesse vor dem
#: Erscheinen. Ein Kanal, eine Adresse; sie steht im Über-Dialog, im
#: Fehlerbericht und auf der Website.
#:
#: Sie liegt auf derselben Domain wie :data:`WEBSITE_URL`, entschieden am
#: 08.08.2026. Wer eine Setup-Datei von der einen Adresse lädt und im Programm
#: eine Support-Adresse einer anderen findet, hat zwei Namen vor sich und
#: keinen Grund zu glauben, dass sie zusammengehören. ``rs-digital.org`` bleibt
#: Firmendomain und trägt die Geschäftspost, aber nicht mehr den Produktkanal.
SUPPORT_ADDRESS: Final = "support@solidon3d.de"

#: Bis zu diesem Tag werden Solidon 1 und seine 1.x-Aktualisierungen
#: mindestens mit Sicherheitskorrekturen unterstützt. Die eine semantische
#: Quelle wird in Oberfläche, öffentlicher Sicherheitszusage und CRA-Prüfung
#: gelesen; eine abgeschriebene Datumszeichenkette könnte unbemerkt abweichen.
SECURITY_SUPPORT_UNTIL: Final = date(2031, 10, 31)

#: Die Produktseite: Download, Handbuch, Kauf. Von hier lesen der Installer
#: (``tools/make_installer.py``), der Update-Hinweis und der Knopf „Solidon
#: kaufen" — sie stand vorher an zwei Stellen getrennt.
WEBSITE_URL: Final = "https://solidon3d.de/"

#: Der freiwillige Förderweg. Er führt direkt zum von PayPal gehosteten
#: Zahlungsdialog; die Produktseite liegt nicht dazwischen.
DONATION_URL: Final = "https://www.paypal.com/donate/?hosted_button_id=D7T4A9VYU9MX4"

#: Endung des Projektcontainers (Bauplan §16.1).
PROJECT_SUFFIX: Final = ".p3d"

#: Endung und MIME-Typ einer austauschbaren Bausteindatei. Die Datei enthält
#: ausschließlich das geprüfte JSON-Rezept; ``.json`` selbst wird auf keiner
#: Plattform Solidon zugeordnet.
PART_FILE_SUFFIX: Final = ".solidon-part"
PART_FILE_MIME_TYPE: Final = "application/vnd.solidon.part+json"

#: Anwendungsversion, gespiegelt in jede Projektdatei als ``app_version``.
#:
#: **Die 0.x-Reihe sind die öffentlichen Demos** (Demo-Konzept §2 D), nicht
#: die Verkaufsversion. Die Null vorn ist keine Bescheidenheit, sondern Mechanik:
#: `key.current_major()` liest die Hauptversion, und ein Kaufschlüssel für 1.x
#: greift damit in einer Demo nicht — wer kauft, lädt die Verkaufsversion, die
#: keinen Stichtag trägt. Zugleich zeigt der Update-Hinweis jeder laufenden
#: Demo auf die 1.0, sobald `version.json` sie nennt.
#:
#: **Wie weitergezählt wird:** die letzte Stelle steigt mit jedem Bau derselben
#: Demo-Fassung; die mittlere nur für einen benannten Funktionsstand. Die
#: Hauptversion 1 ist die Verkaufsversion. Wer hier dreht, zieht
#: `pyproject.toml` mit — die Zahl steht an beiden Orten. Vergessen kann man es nicht mehr:
#: `test_the_version_is_the_same_in_both_places_that_carry_it` hält sie
#: zusammen.
APP_VERSION: Final = "0.3.0"

#: Copyright-Zeile für LICENSE, Über-Dialog und Installer.
COPYRIGHT: Final = f"Copyright © 2026 {APP_VENDOR}"
