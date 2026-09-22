"""Die zwei neuen Gruppentexte in den bereits extrahierten Katalogen ergänzen."""

import json
from pathlib import Path

title = "Gemeinsam auf das Bett setzen"
description = "Setzt die ausgewählten Körper gemeinsam auf das Druckbett und erhält ihre relative Lage."
translations = {
    "en": ("Place on the bed together", "Places the selected bodies on the print bed together, preserving their relative positions."),
    "es": ("Colocar juntos en la placa", "Coloca los cuerpos seleccionados juntos en la placa de impresión y conserva sus posiciones relativas."),
    "fr": ("Poser ensemble sur le plateau", "Pose les corps sélectionnés ensemble sur le plateau d’impression en conservant leurs positions relatives."),
    "it": ("Posiziona insieme sul piano", "Posiziona i corpi selezionati insieme sul piano di stampa, mantenendo le loro posizioni relative."),
    "pt": ("Colocar juntos na placa", "Coloca os corpos selecionados juntos na placa de impressão e mantém as suas posições relativas."),
}
for language, (translated_title, translated_description) in translations.items():
    path = Path("app/i18n/locales") / f"{language}.json"
    catalog = json.loads(path.read_text(encoding="utf-8"))
    assert title in catalog and description in catalog
    catalog[title] = translated_title
    catalog[description] = translated_description
    path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
