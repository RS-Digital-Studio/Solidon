"""Einmalig: die Wörter der Netzfehlerkarte wie im Prüfbericht (24.09.2026).

Nur die eigenen Schlüssel — die Texte der Nachbarsitzung (Großnetz-Erkennung)
bleiben, wie sie sind.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from app.i18n.catalog import read_catalog, write_catalog  # noqa: E402

LANGS = ("en", "es", "fr", "it", "pt")

NEW: dict[str, tuple[str, str, str, str, str]] = {
    "Loch": ("hole", "agujero", "trou", "foro", "furo"),
    "überzählige Fläche": (
        "surplus face",
        "cara sobrante",
        "face en trop",
        "faccia in eccesso",
        "face excedente",
    ),
    "Keine Netzfehler gefunden.": (
        "No mesh defects found.",
        "No se han encontrado defectos de malla.",
        "Aucun défaut de maillage trouvé.",
        "Nessun difetto della mesh trovato.",
        "Não foram encontrados defeitos de malha.",
    ),
    "Die Suche nach Überschneidungen ist unvollständig. Markierte Fehler sind bestätigt; "
    "weitere sind möglich.": (
        "The search for overlaps is incomplete. Highlighted defects are confirmed; others "
        "may remain.",
        "La búsqueda de solapamientos está incompleta. Los defectos marcados están "
        "confirmados; puede haber otros.",
        "La recherche de recouvrements est incomplète. Les défauts signalés sont confirmés ; "
        "d’autres peuvent subsister.",
        "La ricerca delle sovrapposizioni è incompleta. I difetti evidenziati sono "
        "confermati; potrebbero essercene altri.",
        "A procura de sobreposições está incompleta. Os defeitos assinalados estão "
        "confirmados; podem existir outros.",
    ),
    "Überschneidungen nicht vollständig geprüft": (
        "Overlaps not fully checked",
        "Solapamientos no comprobados por completo",
        "Recouvrements non entièrement vérifiés",
        "Sovrapposizioni non verificate completamente",
        "Sobreposições não verificadas por completo",
    ),
    "Zeigt Löcher, überzählige Flächen, Überschneidungen und Außenseiten, die gegeneinander "
    "zeigen.": (
        "Shows holes, surplus faces, overlaps and outer sides that face each other.",
        "Muestra agujeros, caras sobrantes, solapamientos y lados exteriores opuestos.",
        "Montre les trous, les faces en trop, les recouvrements et les faces extérieures "
        "opposées.",
        "Mostra fori, facce in eccesso, sovrapposizioni e lati esterni contrapposti.",
        "Mostra furos, faces excedentes, sobreposições e lados exteriores opostos.",
    ),
}

GONE = (
    "Die Suche nach Durchdringungen ist unvollständig. Markierte Fehler sind bestätigt; "
    "weitere sind möglich.",
    "Durchdringungen nicht vollständig geprüft",
    "Zeigt Löcher, doppelte Flächen und Stellen, an denen das Netz nicht dicht ist.",
    "offene Kante",
    "verzweigte Kante",
)

for position, language in enumerate(LANGS):
    catalog = read_catalog(language)
    for key in GONE:
        assert key in catalog, (language, key)
        catalog.pop(key)
    for key, texts in NEW.items():
        assert not catalog.get(key), (language, key)
        catalog[key] = texts[position]
    write_catalog(language, catalog)
    print(language, "geschrieben:", len(NEW), "neu,", len(GONE), "entfernt")
