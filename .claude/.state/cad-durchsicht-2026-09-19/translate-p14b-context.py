"""Körper und Folgen der Nichtfortführung in jeder Fragesprache benennen."""

import json
from pathlib import Path

rows = {
    "Körper „{object}“: {question}": (
        "Body “{object}”: {question}", "Cuerpo «{object}»: {question}",
        "Corps « {object} » : {question}", "Corpo «{object}»: {question}",
        "Corpo «{object}»: {question}",
    ),
    "Bei „Nicht weiterführen“ bleiben Verweise auf dieses Merkmal ungeklärt. Ordne sie in den betroffenen Folgeschritten neu zu.": (
        "Choosing “Do not carry forward” leaves references to this feature unresolved. Reassign them in the affected following steps.",
        "Al elegir «No conservar», las referencias a esta característica quedan sin resolver. Volver a asignarlas en los pasos posteriores afectados.",
        "Le choix « Ne pas conserver » laisse les références à cette caractéristique non résolues. Les réattribuer dans les étapes suivantes concernées.",
        "Scegliendo «Non mantenere», i riferimenti a questa caratteristica rimangono irrisolti. Riassegnali nei passaggi successivi interessati.",
        "Ao escolher «Não manter», as referências a esta característica ficam por resolver. Voltar a associá-las nos passos seguintes afetados.",
    ),
}
root = Path(__file__).resolve().parents[3]
for index, language in enumerate(("en", "es", "fr", "it", "pt")):
    path = root / "app/i18n/locales" / f"{language}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for source, translations in rows.items():
        assert data[source] in ("", translations[index])
        data[source] = translations[index]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"{language}: {len(rows)} Texte ergänzt")
