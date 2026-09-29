"""Trägt die zwei geänderten Texte von RM-279 (Weg B) in die fünf Kataloge ein (einmalig)."""

import io
import json
import sys

TREE = sys.argv[1]
OLD_CHOICE = "Welche Kanten gemeint sind — senkrechte, waagerechte, oben, unten, alle oder einzeln gewählte."
CHOICE = (
    OLD_CHOICE
    + " Ein runder Rand gehört nur dazu, wenn er waagerecht liegt; eine Bohrung in "
    "einer Seitenwand wählen Sie einzeln."
)
RINGS = (
    "Ein runder Rand wie die Mündung einer Bohrung zählt nur zu waagerecht, oben oder "
    "unten, wenn er waagerecht liegt. In einer Seitenwand heißt er „Senkrecht“, gehört "
    "aber zu keiner Gruppe — wählen Sie ihn dann einzeln. Ohne Haken zählt jeder runde "
    "Rand als waagerecht, wie in Schritten aus älteren Versionen."
)
ADD = {
    "en": (
        " A round rim only belongs if it lies flat; pick a hole in a side wall on its own.",
        "A round rim, such as the mouth of a hole, only counts as horizontal, top or bottom "
        "when it lies flat. In a side wall it is labelled “Vertical” but belongs to no group — "
        "pick it on its own. Unticked, every round rim counts as horizontal, as in steps from "
        "older versions.",
    ),
    "es": (
        " Un borde redondo solo cuenta si está horizontal; un agujero en una pared lateral "
        "se elige por separado.",
        "Un borde redondo, como la boca de un agujero, solo cuenta como horizontal, arriba o "
        "abajo si está horizontal. En una pared lateral se llama «Vertical», pero no pertenece "
        "a ningún grupo: elíjalo por separado. Sin marcar, todo borde redondo cuenta como "
        "horizontal, como en los pasos de versiones anteriores.",
    ),
    "fr": (
        " Un bord rond n’en fait partie que s’il est à plat ; choisissez à part un trou dans "
        "une paroi latérale.",
        "Un bord rond, comme l’embouchure d’un trou, ne compte comme horizontal, en haut ou en "
        "bas que s’il est à plat. Dans une paroi latérale, il s’appelle « Vertical » mais "
        "n’appartient à aucun groupe — choisissez-le à part. Sans coche, tout bord rond compte "
        "comme horizontal, comme dans les étapes des versions précédentes.",
    ),
    "it": (
        " Un bordo rotondo ne fa parte solo se è orizzontale; un foro in una parete laterale "
        "si sceglie da solo.",
        "Un bordo rotondo, come l’imboccatura di un foro, conta come orizzontale, sopra o "
        "sotto solo se è orizzontale. In una parete laterale si chiama «Verticale», ma non "
        "appartiene a nessun gruppo: sceglilo da solo. Senza spunta, ogni bordo rotondo conta "
        "come orizzontale, come nei passi delle versioni precedenti.",
    ),
    "pt": (
        " Uma borda redonda só conta se estiver na horizontal; um furo numa parede lateral "
        "escolhe-se à parte.",
        "Uma borda redonda, como a boca de um furo, só conta como horizontal, em cima ou em "
        "baixo se estiver na horizontal. Numa parede lateral chama-se «Vertical», mas não "
        "pertence a nenhum grupo — escolha-a à parte. Sem visto, toda borda redonda conta como "
        "horizontal, como nos passos de versões anteriores.",
    ),
}
for language, (tail, rings) in ADD.items():
    path = f"{TREE}/app/i18n/locales/{language}.json"
    raw = io.open(path, encoding="utf-8", newline="").read()
    data = json.loads(raw)
    assert data.get(CHOICE) == "" and data.get(RINGS) == "", language
    import subprocess

    head = subprocess.run(
        ["git", "show", f"HEAD:app/i18n/locales/{language}.json"],
        cwd=TREE, capture_output=True, check=True,
    ).stdout.decode("utf-8")
    first = json.loads(head)[OLD_CHOICE]
    for key, value in ((CHOICE, first + tail), (RINGS, rings)):
        old = "  " + json.dumps(key, ensure_ascii=False) + ': ""'
        assert raw.count(old) == 1, (language, key[:40])
        raw = raw.replace(
            old, "  " + json.dumps(key, ensure_ascii=False) + ": " + json.dumps(value, ensure_ascii=False)
        )
    json.loads(raw)
    io.open(path, "w", encoding="utf-8", newline="").write(raw)
    print(language, "ok")
