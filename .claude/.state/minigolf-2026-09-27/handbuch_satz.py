"""Einmalig: den Handbuchsatz zur Überhanggrenze nachziehen und die Kataloge umschlüsseln.

Der Abschnitt „Material, Toleranzen, Passungen" ist ein einziger Katalogeintrag.
Geändert wird ein Satz; jede Sprache behält ihre Übersetzung und bekommt nur
diesen Satz neu. Aufruf im Arbeitsbaum: python handbuch_satz.py <arbeitsbaum>
"""

import ast
import json
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
OLD = "wirklich Stützen braucht — statt der Faustregel 45 Grad."
NEW = (
    "wirklich Stützen braucht. Bis dahin gilt der Winkel aus dem Profil seines "
    "Herstellers, bei einem allgemeinen Drucker die Faustregel 45 Grad."
)
OLD_LINE = '            "wirklich Stützen braucht — statt der Faustregel 45 Grad.\\n\\n"'
NEW_LINES = (
    '            "wirklich Stützen braucht. Bis dahin gilt der Winkel aus dem Profil "\n'
    '            "seines Herstellers, bei einem allgemeinen Drucker die Faustregel 45 "\n'
    '            "Grad.\\n\\n"'
)

# Je Sprache: der alte Satzteil und sein Ersatz, wörtlich aus der vorhandenen
# Übersetzung abgelesen (``--zeigen``) und nur dort geändert.
TRANSLATIONS: dict[str, tuple[str, str]] = {
    "en": (
        "really needs supports — instead of the rule of thumb of 45 degrees.",
        "really needs supports. Until then, the angle from its manufacturer's profile "
        "applies; for a generic printer, the rule of thumb of 45 degrees.",
    ),
    "es": (
        "necesita soportes de verdad — en lugar de la regla empírica de los 45 grados.",
        "necesita soportes de verdad. Hasta entonces vale el ángulo del perfil de su "
        "fabricante; en una impresora genérica, la regla empírica de los 45 grados.",
    ),
    "fr": (
        "a vraiment besoin de supports — au lieu de la règle empirique des 45 degrés.",
        "a vraiment besoin de supports. D'ici là, c'est l'angle du profil de son "
        "fabricant qui s'applique ; pour une imprimante générique, la règle empirique "
        "des 45 degrés.",
    ),
    "it": (
        "ha davvero bisogno di supporti — invece della regola empirica dei 45 gradi.",
        "ha davvero bisogno di supporti. Fino ad allora vale l'angolo del profilo del suo "
        "produttore; per una stampante generica, la regola empirica dei 45 gradi.",
    ),
    "pt": (
        "precisa mesmo de suportes — em vez da regra empírica dos 45 graus.",
        "precisa mesmo de suportes. Até lá vale o ângulo do perfil do seu fabricante; "
        "numa impressora genérica, a regra empírica dos 45 graus.",
    ),
}


def main() -> int:
    manual = ROOT / "app" / "core" / "manual.py"
    source = manual.read_text(encoding="utf-8")
    old_key = None
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Call)
            and getattr(node.func, "id", None) == "_"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
            and OLD in node.args[0].value
        ):
            old_key = node.args[0].value
    if old_key is None:
        print("Satz nicht gefunden")
        return 1
    new_key = old_key.replace(OLD, NEW)
    if "--zeigen" in sys.argv:
        for lang in ("en", "es", "fr", "it", "pt"):
            data = json.loads((ROOT / f"app/i18n/locales/{lang}.json").read_text(encoding="utf-8"))
            text = data[old_key]
            at = text.find("45")
            print(lang, "|", text[max(0, at - 300) : at + 60].replace("\n", " / "))
        return 0
    if source.count(OLD_LINE) != 1:
        print("Zeile nicht eindeutig:", source.count(OLD_LINE))
        return 1
    manual.write_text(source.replace(OLD_LINE, NEW_LINES), encoding="utf-8", newline="\n")
    for lang, (old_part, new_part) in TRANSLATIONS.items():
        path = ROOT / f"app/i18n/locales/{lang}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        text = data.pop(old_key)
        if text.count(old_part) != 1:
            print(lang, "Satzteil nicht eindeutig")
            return 1
        data[new_key] = text.replace(old_part, new_part)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
