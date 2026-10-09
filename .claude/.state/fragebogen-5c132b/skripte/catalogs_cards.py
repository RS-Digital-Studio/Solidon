"""Kataloge für die verschiebbaren Karten — nur neue Schlüssel.

Aufruf: python catalogs_cards.py <arbeitsbaum|ordner-mit-json>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, r"F:\3D Druck")

from app.i18n.catalog import read_catalog, write_catalog  # noqa: E402

KEYS = "Pfeiltasten schieben die Karte, die Eingabetaste nennt die Plätze."

T: dict[str, dict[str, str]] = {
    "Neben der anderen Karte ist hier kein Platz. Doppelklick auf den Griff legt die Karte zurück.": {
        "en": "There is no room here beside the other panel. Double-click the handle to put the panel back.",
        "es": "Aquí no hay sitio junto al otro panel. Un doble clic en el tirador devuelve el panel a su sitio.",
        "fr": "Il n'y a pas de place ici à côté de l'autre panneau. Un double-clic sur la poignée remet le panneau en place.",
        "it": "Qui non c'è spazio accanto all'altro pannello. Un doppio clic sulla maniglia rimette il pannello al suo posto.",
        "pt": "Aqui não há espaço ao lado do outro painel. Um duplo clique na pega devolve o painel ao seu lugar.",
    },
    "Beide Karten liegen an ihrem Platz.": {
        "en": "Both panels are in their place.",
        "es": "Los dos paneles están en su sitio.",
        "fr": "Les deux panneaux sont à leur place.",
        "it": "Entrambi i pannelli sono al loro posto.",
        "pt": "Os dois painéis estão no seu lugar.",
    },
    "Loslassen legt die Karte an den linken Rand.": {
        "en": "Releasing puts the panel at the left edge.",
        "es": "Al soltar, el panel se coloca en el borde izquierdo.",
        "fr": "Relâcher place le panneau contre le bord gauche.",
        "it": "Rilasciando, il pannello va al bordo sinistro.",
        "pt": "Ao largar, o painel fica na margem esquerda.",
    },
    "Loslassen legt die Karte an den rechten Rand.": {
        "en": "Releasing puts the panel at the right edge.",
        "es": "Al soltar, el panel se coloca en el borde derecho.",
        "fr": "Relâcher place le panneau contre le bord droit.",
        "it": "Rilasciando, il pannello va al bordo destro.",
        "pt": "Ao largar, o painel fica na margem direita.",
    },
    "Loslassen lässt die Karte hier schweben.": {
        "en": "Releasing leaves the panel floating here.",
        "es": "Al soltar, el panel queda flotando aquí.",
        "fr": "Relâcher laisse le panneau flotter ici.",
        "it": "Rilasciando, il pannello resta sospeso qui.",
        "pt": "Ao largar, o painel fica a flutuar aqui.",
    },
    "Die Karte liegt wieder an ihrem Platz.": {
        "en": "The panel is back in its place.",
        "es": "El panel vuelve a estar en su sitio.",
        "fr": "Le panneau est de nouveau à sa place.",
        "it": "Il pannello è di nuovo al suo posto.",
        "pt": "O painel voltou ao seu lugar.",
    },
    "Die Karte liegt jetzt links. Doppelklick auf den Griff legt sie zurück.": {
        "en": "The panel is now on the left. Double-click the handle to put it back.",
        "es": "El panel está ahora a la izquierda. Un doble clic en el tirador lo devuelve a su sitio.",
        "fr": "Le panneau est maintenant à gauche. Un double-clic sur la poignée le remet en place.",
        "it": "Il pannello ora è a sinistra. Un doppio clic sulla maniglia lo rimette al suo posto.",
        "pt": "O painel está agora à esquerda. Um duplo clique na pega devolve-o ao seu lugar.",
    },
    "Die Karte liegt jetzt rechts. Doppelklick auf den Griff legt sie zurück.": {
        "en": "The panel is now on the right. Double-click the handle to put it back.",
        "es": "El panel está ahora a la derecha. Un doble clic en el tirador lo devuelve a su sitio.",
        "fr": "Le panneau est maintenant à droite. Un double-clic sur la poignée le remet en place.",
        "it": "Il pannello ora è a destra. Un doppio clic sulla maniglia lo rimette al suo posto.",
        "pt": "O painel está agora à direita. Um duplo clique na pega devolve-o ao seu lugar.",
    },
    "Die Karte schwebt jetzt über der Ansicht. Doppelklick auf den Griff legt sie zurück.": {
        "en": "The panel now floats over the view. Double-click the handle to put it back.",
        "es": "El panel flota ahora sobre la vista. Un doble clic en el tirador lo devuelve a su sitio.",
        "fr": "Le panneau flotte maintenant au-dessus de la vue. Un double-clic sur la poignée le remet en place.",
        "it": "Il pannello ora è sospeso sopra la vista. Un doppio clic sulla maniglia lo rimette al suo posto.",
        "pt": "O painel flutua agora sobre a vista. Um duplo clique na pega devolve-o ao seu lugar.",
    },
    "Karte verschieben. Doppelklick legt sie zurück.": {
        "en": "Move the panel. Double-click puts it back.",
        "es": "Mover el panel. Un doble clic lo devuelve a su sitio.",
        "fr": "Déplacer le panneau. Un double-clic le remet en place.",
        "it": "Sposta il pannello. Un doppio clic lo rimette al suo posto.",
        "pt": "Mover o painel. Um duplo clique devolve-o ao seu lugar.",
    },
    "Liegt links an. " + KEYS: {
        "en": "Docked on the left. The arrow keys move the panel, Enter lists the places.",
        "es": "Acoplado a la izquierda. Las teclas de flecha mueven el panel, Intro muestra los sitios.",
        "fr": "Ancré à gauche. Les flèches déplacent le panneau, Entrée liste les emplacements.",
        "it": "Agganciato a sinistra. I tasti freccia spostano il pannello, Invio elenca le posizioni.",
        "pt": "Encostado à esquerda. As teclas de seta movem o painel, Enter mostra os lugares.",
    },
    "Liegt rechts an. " + KEYS: {
        "en": "Docked on the right. The arrow keys move the panel, Enter lists the places.",
        "es": "Acoplado a la derecha. Las teclas de flecha mueven el panel, Intro muestra los sitios.",
        "fr": "Ancré à droite. Les flèches déplacent le panneau, Entrée liste les emplacements.",
        "it": "Agganciato a destra. I tasti freccia spostano il pannello, Invio elenca le posizioni.",
        "pt": "Encostado à direita. As teclas de seta movem o painel, Enter mostra os lugares.",
    },
    "Schwebt über der Ansicht. " + KEYS: {
        "en": "Floats over the view. The arrow keys move the panel, Enter lists the places.",
        "es": "Flota sobre la vista. Las teclas de flecha mueven el panel, Intro muestra los sitios.",
        "fr": "Flotte au-dessus de la vue. Les flèches déplacent le panneau, Entrée liste les emplacements.",
        "it": "Sospeso sopra la vista. I tasti freccia spostano il pannello, Invio elenca le posizioni.",
        "pt": "Flutua sobre a vista. As teclas de seta movem o painel, Enter mostra os lugares.",
    },
    "An den linken Rand": {
        "en": "To the left edge",
        "es": "Al borde izquierdo",
        "fr": "Contre le bord gauche",
        "it": "Al bordo sinistro",
        "pt": "Para a margem esquerda",
    },
    "An den rechten Rand": {
        "en": "To the right edge",
        "es": "Al borde derecho",
        "fr": "Contre le bord droit",
        "it": "Al bordo destro",
        "pt": "Para a margem direita",
    },
    "An ihren Platz": {
        "en": "Back to its place",
        "es": "A su sitio",
        "fr": "À sa place",
        "it": "Al suo posto",
        "pt": "Para o seu lugar",
    },
    "Karte Objekte verschieben": {
        "en": "Move the Objects panel",
        "es": "Mover el panel Objetos",
        "fr": "Déplacer le panneau Objets",
        "it": "Sposta il pannello Oggetti",
        "pt": "Mover o painel Objetos",
    },
    "Karte Auswahl verschieben": {
        "en": "Move the Selection panel",
        "es": "Mover el panel Selección",
        "fr": "Déplacer le panneau Sélection",
        "it": "Sposta il pannello Selezione",
        "pt": "Mover o painel Seleção",
    },
    "Karten an ihren Platz": {
        "en": "Panels back to their place",
        "es": "Paneles a su sitio",
        "fr": "Panneaux à leur place",
        "it": "Pannelli al loro posto",
        "pt": "Painéis para o seu lugar",
    },
    "Legt verschobene Karten zurück an den Rand, an dem sie anfangs lagen.": {
        "en": "Puts moved panels back at the edge where they started.",
        "es": "Devuelve los paneles movidos al borde donde estaban al principio.",
        "fr": "Remet les panneaux déplacés contre le bord où ils se trouvaient au départ.",
        "it": "Riporta i pannelli spostati al bordo in cui si trovavano all'inizio.",
        "pt": "Devolve os painéis movidos à margem onde estavam no início.",
    },
}


def main() -> None:
    target = sys.argv[1]
    for lang in ("en", "es", "fr", "it", "pt"):
        if target == "arbeitsbaum":
            catalog = read_catalog(lang)
        else:
            catalog = json.loads(Path(target, f"{lang}.json").read_text(encoding="utf-8"))
        for key, by_lang in T.items():
            catalog[key] = by_lang[lang]
        if target == "arbeitsbaum":
            write_catalog(lang, catalog)
        else:
            import app.i18n.catalog as module

            original = module.LOCALES_DIR
            module.LOCALES_DIR = Path(target)
            try:
                write_catalog(lang, catalog)
            finally:
                module.LOCALES_DIR = original
        print(lang, "ok")


if __name__ == "__main__":
    main()
