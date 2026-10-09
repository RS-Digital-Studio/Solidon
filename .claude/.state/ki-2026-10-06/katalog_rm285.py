"""RM-285: Feste Doppelpunkte der Agenten- und Steckbrieftexte in die Kataloge holen.

Jeder neue Schlüssel ist ein vollständiger Rahmen aus Teilen, die schon
übersetzt sind: Die Übersetzung entsteht, indem jeder alte Teil durch seine
vorhandene Übersetzung ersetzt wird; im Französischen bekommt jeder
Doppelpunkt sein Leerzeichen davor (``.claude/rules/uebersetzung.md``). Alte
Schlüssel fallen nur, wenn der Extraktor sie nirgends mehr findet. Idempotent;
bricht ab, bevor es eine vorhandene Übersetzung überschreiben würde.

    python katalog_rm285.py                       # Arbeitskopie
    python katalog_rm285.py --basis HEAD <ordner> # zeilengenau aus HEAD (Index)
"""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from app.i18n.catalog import read_catalog, write_catalog  # noqa: E402
from app.i18n.extract import message_ids  # noqa: E402

LANGUAGES = ("en", "es", "fr", "it", "pt")

#: Neuer Schlüssel → die alten Teile, aus denen er besteht.
FRAMES: dict[str, tuple[str, ...]] = {
    "Diese Analyse gibt es nicht: {kind} ({known})": ("Diese Analyse gibt es nicht",),
    "{count} Inseln (ab mm): {heights}": ("Inseln (ab mm)",),
    "Vorschlag: {summary}": ("Vorschlag",),
    "Szene und Verlauf:": ("Szene und Verlauf",),
    "Prüfbericht:": ("Prüfbericht",),
    "Ort: {place}.": ("Ort",),
    "Diese Objekte gibt es nicht: {missing}. Vorhanden: {known}": (
        "Diese Objekte gibt es nicht",
        "Vorhanden",
    ),
    "Ungültige Werte: {error}": ("Ungültige Werte",),
    "Antwort: {answer}": ("Antwort",),
    "Diese Transaktion gibt es nicht: {transaction}": ("Diese Transaktion gibt es nicht",),
    "Dieser Vorschlag nimmt schon eine Transaktion zurück: {transaction}.": (
        "Dieser Vorschlag nimmt schon eine Transaktion zurück",
    ),
    "Zum Zurücknehmen vorgemerkt: {transaction}.": ("Zum Zurücknehmen vorgemerkt",),
    "Zum Zurücknehmen vorgemerkt: {transaction}": ("Zum Zurücknehmen vorgemerkt",),
    "Diesen Parameter gibt es nicht: {name}": ("Diesen Parameter gibt es nicht",),
    "Parameter gesetzt: {name} = {value} {unit}": ("Parameter gesetzt",),
    "Druckziel geändert: {printer} / {material}": ("Druckziel geändert",),
    "Diese Tabelle gibt es nicht: {kind} ({known})": ("Diese Tabelle gibt es nicht",),
    "Passung angelegt: {name} ({kind}, {tolerance})": ("Passung angelegt",),
    "Dieses Werkzeug gibt es nicht: {tool}": ("Dieses Werkzeug gibt es nicht",),
    "Nicht anwendbar: {error}": ("Nicht anwendbar",),
    "Die Kette hält an: {findings}": ("Die Kette hält an",),
    "Ausgeführt: {operation}.": ("Ausgeführt",),
    "Dieser Wert ist keine Zahl: {value}": ("Dieser Wert ist keine Zahl",),
    "Dieser Wert ist keine endliche Zahl: {value}": ("Dieser Wert ist keine endliche Zahl",),
    "Diese Passungsart gibt es nicht: {kind} ({known})": ("Diese Passungsart gibt es nicht",),
    "Diese Größe steht nicht in der Normteiltabelle: {size}.": (
        "Diese Größe steht nicht in der Normteiltabelle",
    ),
    "Sie liegt nicht zuoberst — der Verlauf kennt keine Verzweigungen, also gehen alle jüngeren mit zurück: {transactions}.": (
        "Sie liegt nicht zuoberst — der Verlauf kennt keine Verzweigungen, also gehen alle jüngeren mit zurück",
    ),
    "Parameter: {values}": ("Parameter",),
    "Auswahl: {selection}": ("Auswahl",),
    "Passungen: {fits}": ("Passungen",),
    "Quellen: {sources}": ("Quellen",),
    "liegt: {spans} mm": ("liegt",),
    "Verlauf: {transactions}": ("Verlauf",),
    "Neues Objekt: {object} {name}": ("Neues Objekt",),
    "Neues Merkmal: {feature}": ("Neues Merkmal",),
    "{object}: übersprungen — das Netz ist zu groß für den Zug, die Analysekarte im Fenster kann es.": (
        "übersprungen — das Netz ist zu groß für den Zug, die Analysekarte im Fenster kann es.",
    ),
    "{object}: die aktuelle Lage ist schon gut.": ("die aktuelle Lage ist schon gut.",),
}


#: Neue eigenständige Sätze (Review RM-014, M4), nicht aus Teilen gebaut.
EXTRA: dict[str, dict[str, str]] = {
    "Einzelne Kanten wählt der Nutzer im Bild — nimm, was das Werkzeug sonst anbietet (Gruppe, Fläche, Achse), oder beschreibe ihm, welche Kanten.": {
        "en": "Single edges are picked by the user in the view — use what the tool offers instead (group, face, axis) or tell them which edges.",
        "es": "Las aristas sueltas las elige el usuario en la vista — usa lo que ofrece la herramienta (grupo, cara, eje) o dile cuáles.",
        "fr": "Les arêtes isolées, c'est l'utilisateur qui les choisit dans la vue — utilise ce que l'outil propose d'autre (groupe, face, axe) ou indique-lui lesquelles.",
        "it": "I singoli spigoli li sceglie l'utente nella vista — usa ciò che lo strumento offre (gruppo, faccia, asse) o digli quali.",
        "pt": "As arestas soltas é o próprio utilizador que as escolhe na vista — utiliza o que a ferramenta oferece (grupo, face, eixo) ou diz-lhe quais."
    },
    "Punkte im Raum klickt der Nutzer im Bild an — nimm eine Fläche oder Achse als Bezug oder beschreibe ihm die Stelle.": {
        "en": "Points in space are clicked by the user in the view — use a face or an axis as reference or describe the spot to them.",
        "es": "Los puntos en el espacio los marca el usuario en la vista — usa una cara o un eje como referencia o descríbele el lugar.",
        "fr": "Les points dans l'espace, c'est l'utilisateur qui les désigne dans la vue — prends une face ou un axe comme référence ou décris-lui l'endroit.",
        "it": "I punti nello spazio li clicca l'utente nella vista — usa una faccia o un asse come riferimento o descrivigli il punto.",
        "pt": "Os pontos no espaço é o próprio utilizador que os clica na vista — utiliza uma face ou um eixo como referência ou descreve-lhe o sítio."
    },
    # Review RM-285, N4: ganze Zeilen statt großgeschriebener Bruchstücke.
    "Druckeinstellungen: {title} ({quality}), {walls} Wände × {width} mm = {thickness} mm Wand": {
        "en": "Print settings: {title} ({quality}), {walls} walls × {width} mm = {thickness} mm wall",
        "es": "Ajustes de impresión: {title} ({quality}), {walls} paredes × {width} mm = {thickness} mm de pared",
        "fr": "Réglages d'impression : {title} ({quality}), {walls} parois × {width} mm = {thickness} mm de paroi",
        "it": "Impostazioni di stampa: {title} ({quality}), {walls} pareti × {width} mm = {thickness} mm di parete",
        "pt": "Definições de impressão: {title} ({quality}), {walls} paredes × {width} mm = {thickness} mm de parede",
    },
    "Szene: {count} Objekte, Drucker {printer}, Material {material}{state}": {
        "en": "Scene: {count} objects, printer {printer}, material {material}{state}",
        "es": "Escena: {count} objetos, impresora {printer}, material {material}{state}",
        "fr": "Scène : {count} objets, imprimante {printer}, matériau {material}{state}",
        "it": "Scena: {count} oggetti, stampante {printer}, materiale {material}{state}",
        "pt": "Cena: {count} objetos, impressora {printer}, material {material}{state}",
    },
    "Szene: {count} Objekte, {plates} Platten, Drucker {printer}, Material {material}{state}": {
        "en": "Scene: {count} objects, {plates} plates, printer {printer}, material {material}{state}",
        "es": "Escena: {count} objetos, {plates} placas, impresora {printer}, material {material}{state}",
        "fr": "Scène : {count} objets, {plates} plateaux, imprimante {printer}, matériau {material}{state}",
        "it": "Scena: {count} oggetti, {plates} piatti, stampante {printer}, materiale {material}{state}",
        "pt": "Cena: {count} objetos, {plates} placas, impressora {printer}, material {material}{state}",
    },
    "{object}: Die aktuelle Lage passt nicht in den Druckbereich. Eine passende Lage wurde gefunden. (Richtung ({direction}), {count} Kandidaten).": {
        "en": "{object}: The current orientation does not fit the printable area. A fitting orientation was found. (direction ({direction}), {count} candidates).",
        "es": "{object}: La orientación actual no cabe en el área imprimible. Se ha encontrado una orientación que cabe. (dirección ({direction}), {count} candidatos).",
        "fr": "{object} : L'orientation actuelle ne tient pas dans la zone imprimable. Une orientation adaptée a été trouvée. (direction ({direction}), {count} candidats).",
        "it": "{object}: L'orientamento attuale non rientra nell'area stampabile. È stato trovato un orientamento adatto. (direzione ({direction}), {count} candidati).",
        "pt": "{object}: A orientação atual não cabe na área imprimível. Foi encontrada uma orientação adequada. (direção ({direction}), {count} candidatos).",
    },
    "{object}: bessere Lage gefunden — Stützvolumen {better} cm³ statt {current} cm³ (Richtung ({direction}), {count} Kandidaten).": {
        "en": "{object}: better orientation found — support volume {better} cm³ instead of {current} cm³ (direction ({direction}), {count} candidates).",
        "es": "{object}: se ha encontrado una orientación mejor — volumen de soporte {better} cm³ en lugar de {current} cm³ (dirección ({direction}), {count} candidatos).",
        "fr": "{object} : meilleure orientation trouvée — volume de support {better} cm³ au lieu de {current} cm³ (direction ({direction}), {count} candidats).",
        "it": "{object}: trovato un orientamento migliore — volume dei supporti {better} cm³ invece di {current} cm³ (direzione ({direction}), {count} candidati).",
        "pt": "{object}: encontrada uma orientação melhor — volume de suporte {better} cm³ em vez de {current} cm³ (direção ({direction}), {count} candidatos).",
    },
}


#: Rahmen, deren Zusammensetzung aus den Teilen nicht trägt (Review RM-285):
#: „Ort“ heißt wie in der Befehlspalette („Ort: {place}“), „Vorhanden:“ ist
#: ein Listenkopf und steht in der Mehrzahl.
OVERRIDES: dict[str, dict[str, str]] = {
    "Ort: {place}.": {
        "en": "Place: {place}.",
        "es": "Ubicación: {place}.",
        "fr": "Emplacement : {place}.",
        "it": "Posizione: {place}.",
        "pt": "Local: {place}.",
    },
    "Diese Objekte gibt es nicht: {missing}. Vorhanden: {known}": {
        "en": "There are no such objects: {missing}. Available: {known}",
        "es": "Esos objetos no existen: {missing}. Existentes: {known}",
        "fr": "Ces objets n'existent pas : {missing}. Existants : {known}",
        "it": "Questi oggetti non esistono: {missing}. Esistenti: {known}",
        "pt": "Estes objetos não existem: {missing}. Existentes: {known}",
    },
}


#: Teile, die als Einzelwort großgeschrieben übersetzt sind und im Rahmen mitten
#: im Satz stehen.
MID_SENTENCE = frozenset({"Objekte"})


def translated(new_key: str, catalog: dict[str, str], language: str) -> str:
    """Den Rahmen aus den vorhandenen Übersetzungen seiner Teile bauen."""
    text = new_key
    # Längere Teile zuerst, sonst träfe „Objekte“ in „Diese Objekte …“.
    for old in sorted(FRAMES[new_key], key=len, reverse=True):
        value = catalog.get(old)
        assert value, f"{language}: keine Übersetzung für {old!r}"
        if old in MID_SENTENCE:
            value = value[0].lower() + value[1:]
        assert text.count(old) == 1, (new_key, old)
        text = text.replace(old, "\0" + value + "\0", 1)
    text = text.replace("\0", "")
    if language == "fr":
        text = re.sub(r"(?<! ):", " :", text)
    return text


def updated(catalog: dict[str, str], language: str, unused: set[str]) -> dict[str, str]:
    result = dict(catalog)
    for new_key in FRAMES:
        if new_key in OVERRIDES:
            result[new_key] = OVERRIDES[new_key][language]
            continue
        if new_key in result and any(old not in catalog for old in FRAMES[new_key]):
            continue  # schon umgestellt, die Teile sind fort
        value = translated(new_key, catalog, language)
        if new_key in result:
            assert result[new_key] == value, f"{language}: {new_key!r} stünde schon anders da"
        result[new_key] = value
    for key, values in EXTRA.items():
        result[key] = values[language]
    for old in unused:
        result.pop(old, None)
    return result


used = message_ids()
missing = [key for key in FRAMES if key not in used]
assert not missing, f"im Code nicht gefunden: {missing}"
old_parts = {old for parts in FRAMES.values() for old in parts}
unused = {old for old in old_parts if old not in used}
REMOVED = {
    "Dieser Parameter entsteht aus Gesten des Nutzers und wird nicht ferngesteuert — Skizze, Pinsel und Skelett gehören ins Fenster.",
    # Review RM-285, N4: die Halbrahmen und Einzelwörter der ganzen Zeilen.
    "Druckeinstellungen: {title} ({quality}),",
    "Szene: {count} Objekte",
    "{object}: bessere Lage gefunden",
    "{object}: Die aktuelle Lage passt nicht in den Druckbereich. Eine passende Lage wurde gefunden.",
    "Druckeinstellungen", "Szene", "Objekte", "Wände", "Wand", "Platten", "Drucker",
    "Material", "Richtung", "Kandidaten", "Stützvolumen", "statt", "bessere Lage gefunden",
    "Die aktuelle Lage passt nicht in den Druckbereich. Eine passende Lage wurde gefunden.",
    # N2: die eigenen Sätze der Fernsteuerung.
    "Diese Tabelle gibt es nicht: {kinds}",
    "Diese Analyse gibt es nicht: {kinds}",
    "Parameter gesetzt: {name} = {value}",
}
unused |= {key for key in REMOVED if key not in used}
print("fallen weg:", sorted(unused))

if len(sys.argv) > 2 and sys.argv[1] == "--basis":
    target = Path(sys.argv[3])
    for language in LANGUAGES:
        head_text = subprocess.run(
            ["git", "-C", str(ROOT), "show", f"{sys.argv[2]}:app/i18n/locales/{language}.json"],
            capture_output=True, encoding="utf-8", check=True,
        ).stdout
        head = json.loads(head_text)
        wanted = updated(head, language, unused)
        lines = head_text.rstrip("\n").split("\n")
        assert lines[0] == "{" and lines[-1] == "}"
        body = [line.rstrip(",") for line in lines[1:-1]]
        entries = {json.loads("{" + line + "}").popitem()[0]: line for line in body}
        for old in unused:
            entries.pop(old, None)
        for new_key in FRAMES:
            if new_key not in entries or new_key in OVERRIDES:
                entries[new_key] = "  " + json.dumps(new_key, ensure_ascii=False) + ": " + json.dumps(wanted[new_key], ensure_ascii=False)
        for key in EXTRA:
            if key not in entries:
                entries[key] = "  " + json.dumps(key, ensure_ascii=False) + ": " + json.dumps(wanted[key], ensure_ascii=False)
        # Neue Zeilen an ihren sortierten Platz, die übrigen in HEAD-Folge.
        order = [key for key in (json.loads("{" + line + "}").popitem()[0] for line in body) if key in entries]
        for new_key in sorted(key for key in (*FRAMES, *EXTRA) if key not in head):
            position = next((i for i, key in enumerate(order) if key > new_key), len(order))
            order.insert(position, new_key)
        out = "{\n" + ",\n".join(entries[key] for key in order) + "\n}\n"
        assert json.loads(out) == wanted, language
        (target / f"{language}.json").write_text(out, encoding="utf-8", newline="\n")
    print("Index-Fassungen in", target)
else:
    for language in LANGUAGES:
        write_catalog(language, updated(read_catalog(language), language, unused))
    print("Arbeitskopie umgestellt")
