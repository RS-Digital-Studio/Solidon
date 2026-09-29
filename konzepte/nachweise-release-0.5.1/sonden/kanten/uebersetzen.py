"""Trägt die zwei neuen Texte von RM-279 in die fünf Kataloge ein (einmalig)."""

import io
import json
import sys

TREE = sys.argv[1]
TITLE = "Runde Ränder nach ihrer Lage"
DOC = (
    "Ein runder Rand wie die Mündung einer Bohrung zählt so, wie er steht: senkrecht "
    "an einer Seitenwand, waagerecht oben oder unten. Ohne Haken zählt jeder runde Rand "
    "als waagerecht, wie in Schritten aus älteren Versionen."
)
TEXTS = {
    "en": (
        "Round rims by how they stand",
        "A round rim, such as the mouth of a hole, counts the way it stands: vertical on a "
        "side wall, horizontal on the top or bottom. Unticked, every round rim counts as "
        "horizontal, as in steps from older versions.",
    ),
    "es": (
        "Bordes redondos según su posición",
        "Un borde redondo, como la boca de un agujero, cuenta según está: vertical en una "
        "pared lateral, horizontal arriba o abajo. Sin marcar, todo borde redondo cuenta "
        "como horizontal, como en los pasos de versiones anteriores.",
    ),
    "fr": (
        "Bords ronds selon leur position",
        "Un bord rond, comme l’embouchure d’un trou, compte selon sa position : vertical sur "
        "une paroi latérale, horizontal en haut ou en bas. Sans coche, tout bord rond compte "
        "comme horizontal, comme dans les étapes des versions précédentes.",
    ),
    "it": (
        "Bordi rotondi secondo la posizione",
        "Un bordo rotondo, come l’imboccatura di un foro, conta come sta: verticale su una "
        "parete laterale, orizzontale sopra o sotto. Senza spunta, ogni bordo rotondo conta "
        "come orizzontale, come nei passi delle versioni precedenti.",
    ),
    "pt": (
        "Bordas redondas pela posição",
        "Uma borda redonda, como a boca de um furo, conta conforme está: vertical numa parede "
        "lateral, horizontal em cima ou em baixo. Sem visto, toda borda redonda conta como "
        "horizontal, como nos passos de versões anteriores.",
    ),
}
for language, (title, doc) in TEXTS.items():
    path = f"{TREE}/app/i18n/locales/{language}.json"
    raw = io.open(path, encoding="utf-8", newline="").read()
    data = json.loads(raw)
    assert data.get(TITLE) == "" and data.get(DOC) == "", (language, data.get(TITLE), data.get(DOC))
    for key, value in ((TITLE, title), (DOC, doc)):
        old = "  " + json.dumps(key, ensure_ascii=False) + ': ""'
        assert raw.count(old) == 1, (language, key)
        raw = raw.replace(old, "  " + json.dumps(key, ensure_ascii=False) + ": " + json.dumps(value, ensure_ascii=False))
    json.loads(raw)
    io.open(path, "w", encoding="utf-8", newline="").write(raw)
    print(language, "ok")
