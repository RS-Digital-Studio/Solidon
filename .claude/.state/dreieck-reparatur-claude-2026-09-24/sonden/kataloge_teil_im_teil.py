"""Einmalig: die zwei Sätze zu ``repair.part_inside`` in alle Kataloge (24.09.2026)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from app.i18n.catalog import read_catalog, write_catalog  # noqa: E402

LANGS = ("en", "es", "fr", "it", "pt")

T: dict[str, tuple[str, str, str, str, str]] = {
    "Ein Teil liegt ganz in einem anderen. Slicer drucken es je nach Einstellung hohl oder voll.": (
        "One part lies entirely inside another. Depending on their settings, slicers print "
        "it hollow or solid.",
        "Una pieza está completamente dentro de otra. Según su configuración, los slicers la "
        "imprimen hueca o maciza.",
        "Une pièce se trouve entièrement dans une autre. Selon leurs réglages, les slicers "
        "l’impriment creuse ou pleine.",
        "Un pezzo si trova interamente dentro un altro. A seconda delle impostazioni, gli "
        "slicer lo stampano cavo o pieno.",
        "Uma peça está totalmente dentro de outra. Conforme a configuração, os slicers "
        "imprimem-na oca ou maciça.",
    ),
    "{parts} Teile liegen ganz in einem anderen. Slicer drucken sie je nach Einstellung hohl "
    "oder voll.": (
        "{parts} parts lie entirely inside another. Depending on their settings, slicers "
        "print them hollow or solid.",
        "{parts} piezas están completamente dentro de otra. Según su configuración, los "
        "slicers las imprimen huecas o macizas.",
        "{parts} pièces se trouvent entièrement dans une autre. Selon leurs réglages, les "
        "slicers les impriment creuses ou pleines.",
        "{parts} pezzi si trovano interamente dentro un altro. A seconda delle impostazioni, "
        "gli slicer li stampano cavi o pieni.",
        "{parts} peças estão totalmente dentro de outra. Conforme a configuração, os slicers "
        "imprimem-nas ocas ou maciças.",
    ),
}

gaps = json.loads(
    Path(".claude/.state/dreieck-reparatur-claude-2026-09-24/katalog_luecken.json").read_text(
        encoding="utf-8"
    )
)
for position, language in enumerate(LANGS):
    missing = set(gaps[language]["missing"])
    assert missing == set(T), (language, sorted(missing ^ set(T)))
    catalog = read_catalog(language)
    for key, texts in T.items():
        catalog[key] = texts[position]
    write_catalog(language, catalog)
    print(language, "geschrieben:", len(T), "neu")
