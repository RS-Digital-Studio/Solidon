"""Kataloge für Fragebogen S-20261006-5c132b: nur die eigenen Schlüssel.

Aufruf: python catalogs.py <arbeitsbaum|head> [<ausgabeordner>]
- arbeitsbaum: schreibt die Kataloge im Arbeitsbaum um.
- head: liest die Kataloge aus HEAD, wendet dieselben Änderungen an und legt
  das Ergebnis in <ausgabeordner> ab (zum Stagen ohne fremde Änderungen).
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, r"F:\3D Druck")

from app.i18n.catalog import read_catalog, write_catalog  # noqa: E402

LANGS = ("en", "es", "fr", "it", "pt")


def source_strings(path: str, rev: str | None) -> list[str]:
    if rev is None:
        text = Path(r"F:\3D Druck", path).read_text(encoding="utf-8")
    else:
        text = subprocess.run(
            ["git", "show", f"{rev}:{path}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=r"F:\3D Druck",
            check=True,
        ).stdout
    return [
        node.value
        for node in ast.walk(ast.parse(text))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


OLD_A = "Wählen Sie dafür {count} Objekte aus — im Bild oder im Objektbaum."
OLD_B = "Klicken Sie zweimal auf die Oberseite: erst ist das Teil gewählt, dann die Fläche."
NEW_B = (
    "Klicken Sie auf die Oberseite. Der neue Quader ist schon gewählt, "
    "also wählt der Klick die Fläche."
)
OLD_C = (
    "Legen Sie wie in [Das erste eigene Teil](manual:first-part) "
    "einen Quader an und klicken Sie darauf."
)
NEW_C = (
    "Legen Sie wie in [Das erste eigene Teil](manual:first-part) "
    "einen Quader an. Danach ist er schon gewählt."
)

old_manual = source_strings("app/core/manual.py", "HEAD")
new_manual = source_strings("app/core/manual.py", None)
OLD_D = next(s for s in old_manual if s.startswith("**Auswählen geht in zwei Stufen.**"))
NEW_D = next(s for s in new_manual if s.startswith("**Auswählen geht in zwei Stufen.**"))
OLD_E = next(s for s in old_manual if "**Entf trifft das Merkmal, nicht den Körper.**" in s)
NEW_E = next(s for s in new_manual if "**Entf trifft das Merkmal, nicht den Körper.**" in s)
assert OLD_D != NEW_D and OLD_E != NEW_E
assert OLD_E.replace(
    "ohne gewähltes Merkmal löscht sie das Objekt.",
    "ohne gewähltes Merkmal löscht sie alle markierten Objekte.",
) == NEW_E, "der große Absatz ändert sich nur in diesem Satz"

TRANSLATIONS: dict[str, dict[str, str]] = {
    NEW_B: {
        "en": "Click the top face. The new box is already selected, so the click selects the face.",
        "es": (
            "Haga clic en la cara superior. La caja nueva ya está seleccionada, "
            "así que el clic selecciona la cara."
        ),
        "fr": (
            "Cliquez sur la face supérieure. Le nouveau pavé est déjà sélectionné, "
            "le clic sélectionne donc la face."
        ),
        "it": (
            "Fai clic sul lato superiore. Il nuovo parallelepipedo è già selezionato, "
            "quindi il clic seleziona la faccia."
        ),
        "pt": (
            "Clique na face superior. O novo paralelepípedo já está selecionado, "
            "por isso o clique seleciona a face."
        ),
    },
    NEW_C: {
        "en": "Add a box as in [Your first part](manual:first-part). It is selected right away.",
        "es": (
            "Añada una caja como en [Su primera pieza propia](manual:first-part). "
            "Queda seleccionada de inmediato."
        ),
        "fr": (
            "Ajoutez un pavé comme dans [Votre première pièce](manual:first-part). "
            "Il est aussitôt sélectionné."
        ),
        "it": (
            "Crea un parallelepipedo come in [Il tuo primo pezzo](manual:first-part). "
            "Risulta subito selezionato."
        ),
        "pt": (
            "Crie um paralelepípedo como em [A sua primeira peça](manual:first-part). "
            "Fica logo selecionado."
        ),
    },
    NEW_D: {
        "en": (
            "**Selecting works in two stages.** The first click selects the whole part, "
            "the second the face within it; `Esc` steps back one stage. A part you have "
            "just added is already selected, so there the first click selects the face. "
            "Add another part by holding Shift or `Ctrl`, on a Mac `⌘`. On the right "
            "under *Selection* you then find the actions that fit. A right-click shows "
            "the step the spot comes from, drawing on the face, hiding, *Remove object* "
            "and, with several parts, *Unite*."
        ),
        "es": (
            "**La selección va en dos pasos.** El primer clic selecciona la pieza entera, "
            "el segundo la cara dentro de ella; `Esc` vuelve un paso atrás. Una pieza "
            "recién creada ya está seleccionada, y ahí el primer clic selecciona la cara. "
            "Otra pieza se añade manteniendo pulsada la tecla Mayús o `Ctrl`, en el Mac "
            "`⌘`. A la derecha, bajo *Selección*, aparecen entonces las acciones que le "
            "corresponden. El clic derecho muestra el paso del que procede el punto, el "
            "dibujo sobre la cara, la ocultación, *Quitar objeto* y, con varias piezas, "
            "*Unir*."
        ),
        "fr": (
            "**La sélection se fait en deux temps.** Le premier clic sélectionne la pièce "
            "entière, le second la face qu'elle porte ; `Échap` revient d'un cran. Une "
            "pièce que vous venez de créer est déjà sélectionnée, le premier clic y "
            "sélectionne donc la face. Une autre pièce s'ajoute en maintenant Maj ou "
            "`Ctrl`, sur Mac `⌘`. À droite, sous *Sélection*, se trouvent alors les "
            "actions qui conviennent. Le clic droit montre l'étape dont provient "
            "l'endroit, le dessin sur la face, le masquage, *Retirer l'objet* et, avec "
            "plusieurs pièces, *Réunir*."
        ),
        "it": (
            "**La selezione avviene in due passi.** Il primo clic seleziona il pezzo "
            "intero, il secondo la faccia al suo interno; `Esc` torna indietro di un "
            "passo. Un pezzo appena creato è già selezionato, lì il primo clic seleziona "
            "la faccia. Un altro pezzo si aggiunge tenendo premuto Maiusc o `Ctrl`, sul "
            "Mac `⌘`. A destra, sotto *Selezione*, trovi poi le azioni adatte. Il clic "
            "destro mostra il passaggio da cui proviene il punto, il disegno sulla "
            "faccia, il nascondere, *Rimuovi oggetto* e, con più pezzi, *Unisci*."
        ),
        "pt": (
            "**A seleção faz-se em duas etapas.** O primeiro clique seleciona a peça "
            "inteira, o segundo a face dentro dela; `Esc` volta uma etapa atrás. Uma "
            "peça acabada de criar já está selecionada, e aí o primeiro clique seleciona "
            "a face. Outra peça junta-se mantendo premida a tecla Shift ou `Ctrl`, no Mac "
            "`⌘`. À direita, em *Seleção*, ficam então as ações que lhe correspondem. O "
            "clique direito mostra o passo de que provém o sítio, o desenho na face, a "
            "ocultação, *Remover objeto* e, com várias peças, *Unir*."
        ),
    },
}

#: Der große Absatz: derselbe Text, nur der eine Satz neu — je Sprache ersetzt.
E_SENTENCE = {
    "en": (
        "with no feature selected, it deletes the object.",
        "with no feature selected, it deletes every marked object.",
    ),
    "es": (
        "sin característica seleccionada, borra el objeto.",
        "sin característica seleccionada, borra todos los objetos marcados.",
    ),
    "fr": (
        "sans caractéristique sélectionnée, elle supprime l'objet.",
        "sans caractéristique sélectionnée, elle supprime tous les objets marqués.",
    ),
    "it": (
        "senza caratteristica selezionata elimina l'oggetto.",
        "senza caratteristica selezionata elimina tutti gli oggetti contrassegnati.",
    ),
    "pt": (
        "sem característica escolhida, apaga o objeto.",
        "sem característica escolhida, apaga todos os objetos marcados.",
    ),
}


def changed(catalog: dict[str, str], lang: str, reference: dict[str, str]) -> dict[str, str]:
    """Die Änderungen an einem Katalog; ``reference`` liefert den alten großen Absatz."""
    result = dict(catalog)
    for old in (OLD_A, OLD_B, OLD_C, OLD_D, OLD_E):
        result.pop(old, None)
    for key, by_lang in TRANSLATIONS.items():
        result[key] = by_lang[lang]
    old_e = reference[OLD_E]
    before, after = E_SENTENCE[lang]
    assert old_e.count(before) == 1, (lang, before)
    result[NEW_E] = old_e.replace(before, after)
    return result


def main() -> None:
    mode = sys.argv[1]
    for lang in LANGS:
        if mode == "arbeitsbaum":
            catalog = read_catalog(lang)
            reference = catalog if OLD_E in catalog else head_catalog(lang)
            write_catalog(lang, changed(catalog, lang, reference))
            print(lang, "umgeschrieben")
        else:
            out = Path(sys.argv[2])
            out.mkdir(parents=True, exist_ok=True)
            catalog = head_catalog(lang)
            target = out / f"{lang}.json"
            write_to(target, changed(catalog, lang, catalog))
            print(lang, "->", target)


def head_catalog(lang: str) -> dict[str, str]:
    text = subprocess.run(
        ["git", "show", f"HEAD:app/i18n/locales/{lang}.json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=r"F:\3D Druck",
        check=True,
    ).stdout
    return json.loads(text)


def write_to(target: Path, catalog: dict[str, str]) -> None:
    """Wie ``write_catalog``, aber an einen anderen Ort — über dieselbe Funktion."""
    import app.i18n.catalog as module

    original = module.LOCALES_DIR if hasattr(module, "LOCALES_DIR") else None
    if original is None:
        raise SystemExit("catalog.LOCALES_DIR fehlt — Ablageort unbekannt")
    module.LOCALES_DIR = target.parent
    try:
        write_catalog(target.stem, catalog)
    finally:
        module.LOCALES_DIR = original


if __name__ == "__main__":
    main()
