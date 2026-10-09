"""RM-003: Den Weg-3-Absatz des Handbuchs in allen Katalogen berichtigen.

Ersetzt genau einen Schlüssel (Seite „generating“): alter Text raus, neuer
rein; in der Übersetzung wird nur der vierte Absatz neu gesetzt, der Rest
bleibt wörtlich. Idempotent. ``--basis HEAD`` baut die Fassung aus HEAD
(für den Index) und schreibt sie nach ``<ordner>/<sprache>.json``.

    python katalog_rm003.py                       # Arbeitskopie
    python katalog_rm003.py --basis HEAD <ordner> # Index-Fassung
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from app.i18n.catalog import read_catalog, write_catalog  # noqa: E402

OLD_DE = (
    "**Der mitgelieferte Ablauf setzt auf TripoSG**, Quelltext und Modellkarte unter "
    "MIT-Lizenz. Die vollständige Lizenzkette der Gewichte und eingebundenen Modelle "
    "wird noch geprüft. Andere Modelle haben eigene Bedingungen, die für die "
    "eingesetzte Version zu prüfen sind."
)
NEW_DE = (
    "**Der mitgelieferte Ablauf setzt auf TripoSG.** Quelltext und Modellkarte nennen "
    "die MIT-Lizenz, ein Teil des Quelltexts steht aber unter Lizenzen von Tencent, die "
    "die Europäische Union ausnehmen. Das wird gerade geklärt. Andere Modelle haben "
    "eigene Bedingungen, die für die eingesetzte Version zu prüfen sind."
)
NEW = {
    "en": "**The supplied workflow relies on TripoSG.** Its source code and model card name the MIT licence, but part of the source code is under Tencent licences that exclude the European Union. This is being clarified. Other models have their own terms, which must be checked for the version in use.",
    "es": "**El flujo incluido usa TripoSG.** Su código fuente y su ficha del modelo indican la licencia MIT, pero una parte del código está bajo licencias de Tencent que excluyen la Unión Europea. Se está aclarando. Otros modelos tienen sus propias condiciones, que hay que comprobar para la versión que se use.",
    "fr": "**Le flux fourni s'appuie sur TripoSG.** Son code source et sa fiche du modèle indiquent la licence MIT, mais une partie du code relève de licences de Tencent qui excluent l'Union européenne. C'est en cours de clarification. D'autres modèles ont leurs propres conditions, à vérifier pour la version utilisée.",
    "it": "**Il flusso fornito si basa su TripoSG.** Il codice sorgente e la scheda del modello indicano la licenza MIT, ma una parte del codice è sotto licenze di Tencent che escludono l'Unione europea. È in corso di chiarimento. Altri modelli hanno condizioni proprie, da verificare per la versione usata.",
    "pt": "**O fluxo incluído assenta no TripoSG.** O código-fonte e a ficha do modelo indicam a licença MIT, mas uma parte do código está sob licenças da Tencent que excluem a União Europeia. Está a ser esclarecido. Outros modelos têm condições próprias, a verificar para a versão usada.",
}


def page_key(text: str) -> str:
    """Der ganze Schlüssel der Seite, aus der Quelle gelesen."""
    import ast

    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "Page":
            keywords = {k.arg: k.value for k in node.keywords}
            key = keywords.get("key")
            if isinstance(key, ast.Constant) and key.value == "generating":
                return keywords["body"].args[0].value
    raise SystemExit("Seite generating nicht gefunden")


def changed(catalog: dict[str, str], old_key: str, new_key: str, language: str) -> dict[str, str]:
    if new_key in catalog and old_key not in catalog:
        return catalog  # schon umgestellt
    assert old_key in catalog, f"{language}: alter Schlüssel fehlt"
    assert new_key not in catalog, f"{language}: neuer Schlüssel stünde schon da"
    paragraphs = catalog[old_key].split("\n\n")
    assert len(paragraphs) == 6 and "TripoSG" in paragraphs[3], (language, len(paragraphs))
    paragraphs[3] = NEW[language]
    result = {key: value for key, value in catalog.items() if key != old_key}
    result[new_key] = "\n\n".join(paragraphs)
    return result


source_now = (ROOT / "app/core/manual.py").read_text(encoding="utf-8")
new_key = page_key(source_now)
assert NEW_DE in new_key, "manual.py trägt den neuen Absatz noch nicht"
old_key = new_key.replace(NEW_DE, OLD_DE)
assert old_key != new_key

if len(sys.argv) > 2 and sys.argv[1] == "--basis":
    target = Path(sys.argv[3])
    target.mkdir(parents=True, exist_ok=True)
    for language in NEW:
        head = json.loads(
            subprocess.run(
                ["git", "-C", str(ROOT), "show", f"{sys.argv[2]}:app/i18n/locales/{language}.json"],
                capture_output=True, encoding="utf-8", check=True,
            ).stdout
        )
        (target / f"{language}.json").write_text(
            json.dumps(changed(head, old_key, new_key, language), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    print("Index-Fassungen in", target)
else:
    for language in NEW:
        write_catalog(language, changed(read_catalog(language), old_key, new_key, language))
    print("Arbeitskopie umgestellt")
