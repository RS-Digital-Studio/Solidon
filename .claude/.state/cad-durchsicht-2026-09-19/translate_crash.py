"""Die Diagnosebeschriftungen ergänzen, ohne bestehende Katalogwerte zu ersetzen."""

import json
from pathlib import Path

translations = {
    "Das Absturzprotokoll wurde auf die letzten Einträge gekürzt.": {
        "en": "The crash log was shortened to its most recent entries.",
        "es": "El registro de fallos se ha reducido a las entradas más recientes.",
        "fr": "Le journal de plantage a été limité aux entrées les plus récentes.",
        "it": "Il registro degli arresti anomali è stato ridotto alle voci più recenti.",
        "pt": "O registo de falhas foi reduzido às entradas mais recentes.",
    },
    "Vorhandene Absturzprotokolle werden ebenfalls angezeigt und angehängt.": {
        "en": "Existing crash logs are also displayed and attached.",
        "es": "Los registros de fallos existentes también se muestran y se adjuntan.",
        "fr": "Les journaux de plantage existants sont également affichés et joints.",
        "it": "Anche i registri degli arresti anomali esistenti vengono visualizzati e allegati.",
        "pt": "Os registos de falhas existentes também são apresentados e anexados.",
    },
    "Lokale Absturzprotokolle ohne lokale Variablen oder Projektgeometrie": {
        "en": "Local crash logs without local variables or project geometry",
        "es": "Registros de fallos locales sin variables locales ni geometría del proyecto",
        "fr": "Journaux de plantage locaux sans variables locales ni géométrie du projet",
        "it": "Registri locali degli arresti anomali senza variabili locali né geometria del progetto",
        "pt": "Registos locais de falhas sem variáveis locais nem geometria do projeto",
    },
}
for path in Path("app/i18n/locales").glob("*.json"):
    catalog = json.loads(path.read_text(encoding="utf-8"))
    for key, languages in translations.items():
        if key in catalog:
            catalog[key] = languages[path.stem]
    path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
