"""Was der Agent tun kann (Bauplan §26.2).

Jede Operation aus dem Register, plus die Zusatzwerkzeuge, die über Geometrie
hinausreichen: fragen, zurücknehmen, Parameter, Passungen, der Prüfbericht,
die Bausteinbibliothek, der Steckbrief mitten im Zug und die Normteiltabelle.

Die Operationen stehen auch hier nicht ausgeschrieben — sie kommen aus dem
Register, wie Menü und Kommandozeile (§10). Eine Operation, die heute
deklariert wird, ist morgen ein Werkzeug, ohne dass jemand diese Datei
anfasst.

``ask_user`` ist keine Höflichkeit, sondern Pflicht (Leitprinzip 6, §26.2):
die Suite enthält absichtlich mehrdeutige Anfragen und misst, ob es benutzt
wurde.
"""

from __future__ import annotations

from typing import Any, Final

from app.core.registry import REGISTRY, Registry, menu_path
from app.core.registry import tool_schemas as op_schemas
from app.i18n import _, tr

#: Name der Zusatz-Eigenschaft, die jedes Operationswerkzeug trägt: auf welche
#: Objekte es wirkt. Das Parameterschema weiß nichts von der Szene, also kommt
#: sie hier dazu statt in jede Deklaration.
OBJECTS_FIELD: Final = "objects"

ASK_USER: Final = "ask_user"
UNDO_TRANSACTION: Final = "undo_transaction"
ADD_PARAMETER: Final = "add_parameter"
SET_PARAMETER: Final = "set_parameter"
ADD_FIT: Final = "add_fit"
READ_REPORT: Final = "read_report"
FIND_PART: Final = "find_part"
READ_DIGEST: Final = "read_digest"
READ_STANDARD: Final = "read_standard"
READ_ANALYSIS: Final = "read_analysis"
SET_PRINT_TARGET: Final = "set_print_target"

#: Welche Tabellen der Normteilkatalog kennt (§24.2) — das Enum im Schema und
#: die Prüfung in der Sitzung lesen dieselbe Liste.
STANDARD_KINDS: Final[tuple[str, ...]] = (
    "screw",
    "nut",
    "washer",
    "insert",
    "magnet",
    "bearing",
    "profile",
    "tube",
)

EXTRA_TOOLS: Final[tuple[str, ...]] = (
    ASK_USER,
    UNDO_TRANSACTION,
    ADD_PARAMETER,
    SET_PARAMETER,
    ADD_FIT,
    READ_REPORT,
    FIND_PART,
    READ_DIGEST,
    READ_STANDARD,
    READ_ANALYSIS,
    SET_PRINT_TARGET,
)


def tool_schemas(
    registry: Registry | None = None, *, compact: bool = False
) -> tuple[dict[str, Any], ...]:
    """Alles, was das Modell aufrufen darf — die Operationen zuerst.

    ``compact`` kürzt die Beschreibungen, **ohne ein Werkzeug wegzulassen**.
    Das ist der Unterschied, auf den es ankommt: eine Auswahl, die Operationen
    aussortiert, wäre eine Betriebsart mit anderem Namen (§2.6) — der Agent
    käme an sie nicht mehr heran, ohne dass ihm jemand sagt, dass es sie gibt.
    Gekürzt wird die Prosa: die Parametertexte, der doc-Satz und der Menüort
    machen zusammen die Hälfte der 110 KB aus, und ein lokales Modell mit
    kleinem Kontextfenster verliert daran mehr, als es gewinnt.
    """
    return (*operation_tools(registry, compact=compact), *extra_tools())


def operation_tools(
    registry: Registry | None = None, *, compact: bool = False
) -> tuple[dict[str, Any], ...]:
    """Das Register als Werkzeuge, jedes mit den Objekten, auf denen es
    arbeitet.
    """
    source = registry or REGISTRY
    schemas = []
    for schema in op_schemas(source):
        spec = source.get(str(schema["name"]))
        parameters = dict(schema["input_schema"])
        properties = dict(parameters.get("properties", {}))
        if spec.consumes:
            properties[OBJECTS_FIELD] = {
                "type": "array",
                "items": {"type": "string"},
                "description": str(
                    _("Objekte, auf die die Operation angewendet wird, zum Beispiel obj_1.")
                ),
            }
            required = [*parameters.get("required", []), OBJECTS_FIELD]
            parameters["required"] = required
        parameters["properties"] = properties
        # §2.6: der Chat ist auch ein Suchfeld. Der Menüort steht in der
        # Beschreibung, damit das Modell bei einer Wie-Frage sagen kann, wo
        # die Funktion im Fenster liegt — es hat sonst keine Quelle dafür.
        # ``menu_path`` staffelt wie die Leiste; nur Gruppe und Titel zu
        # nennen traf für 72 von 77 Ops den falschen Ort.
        description = str(schema["description"])
        if compact:
            # Auch die Parametertexte: sie sind mit 40 KB der größte einzelne
            # Posten im Schema. Gekürzt auf den ersten Satz bleibt stehen, was
            # der Wert bedeutet; weg fällt, warum er so heißt und was bei
            # Randfällen passiert.
            for name, field in properties.items():
                text = str(field.get("description", ""))
                if ". " in text:
                    properties[name] = {**field, "description": text.split(". ")[0] + "."}
            parameters["properties"] = properties
            # Der erste Satz sagt, was die Operation tut; der Rest erklärt
            # Randfälle, die ein Modell mit kleinem Fenster nicht liest.
            description = description.split(". ")[0].rstrip(".") + "."
        else:
            description = f"{description} {tr('Menü')}: {menu_path(spec, source)}."
        schemas.append(
            {
                "name": schema["name"],
                "description": description,
                "input_schema": parameters,
            }
        )
    return tuple(schemas)


def extra_tools() -> tuple[dict[str, Any], ...]:
    """Die Zusatzwerkzeuge aus der Tabelle in §26.2."""
    return (
        {
            "name": ASK_USER,
            "description": str(
                _(
                    "Frage den Nutzer, wenn die Anfrage mehrdeutig ist. "
                    "Lieber einmal fragen als einmal falsch raten."
                )
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": str(_("Die Frage."))},
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": str(_("Antwortmöglichkeiten zur Auswahl.")),
                    },
                },
                "required": ["question"],
            },
        },
        {
            "name": UNDO_TRANSACTION,
            "description": str(_("Nimm eine Transaktion aus dem Verlauf zurück.")),
            "input_schema": {
                "type": "object",
                "properties": {
                    "transaction": {
                        "type": "string",
                        "description": str(_("Kennung aus dem Verlauf, zum Beispiel t3.")),
                    }
                },
                "required": ["transaction"],
            },
        },
        {
            "name": ADD_PARAMETER,
            "description": str(
                _("Lege ein Hauptmaß als Projektparameter an, statt es als Zahl zu setzen.")
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "value": {"type": "number"},
                    "unit": {"type": "string", "description": str(_("Standard ist mm."))},
                    "title": {"type": "string"},
                },
                "required": ["name", "value"],
            },
        },
        {
            "name": SET_PARAMETER,
            "description": str(_("Ändere den Wert eines bestehenden Projektparameters.")),
            "input_schema": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "value": {"type": "number"}},
                "required": ["name", "value"],
            },
        },
        {
            "name": ADD_FIT,
            "description": str(
                _("Lege ein Passungspaar an. Die Toleranz kommt aus dem Materialprofil.")
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "a": {
                        "type": "string",
                        "description": str(_("Erstes Merkmal als obj_1:hole_2.")),
                    },
                    "b": {
                        "type": "string",
                        "description": str(_("Zweites Merkmal als obj_2:pin_1.")),
                    },
                    "kind": {
                        "type": "string",
                        "enum": ["clearance", "press", "thread"],
                    },
                },
                "required": ["name", "a", "b"],
            },
        },
        {
            "name": READ_REPORT,
            "description": str(_("Lies den Prüfbericht, wahlweise nur ab einer Schwere.")),
            "input_schema": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["info", "warning", "error"]}
                },
            },
        },
        {
            "name": FIND_PART,
            "description": str(
                _("Suche einen passenden Baustein, bevor du Geometrie selbst zusammensetzt.")
            ),
            "input_schema": {
                "type": "object",
                "properties": {"description": {"type": "string"}},
                "required": ["description"],
            },
        },
        {
            "name": READ_DIGEST,
            "description": str(
                _(
                    "Lies den Steckbrief der Szene neu — mit den Merkmalen und "
                    "IDs, die deine bisherigen Schritte erzeugt haben."
                )
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    OBJECTS_FIELD: {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": str(
                            _("Nur diese Objekte zeigen; ohne Angabe die ganze Szene.")
                        ),
                    }
                },
            },
        },
        {
            "name": READ_STANDARD,
            "description": str(
                _(
                    "Schlage Normteilmaße nach: Kernloch, Durchgangsloch, "
                    "Schlüsselweite und mehr — statt sie zu raten."
                )
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": list(STANDARD_KINDS)},
                    "size": {
                        "type": "string",
                        "description": str(_("Die Größe, zum Beispiel M4 oder 6x3.")),
                    },
                },
                "required": ["kind", "size"],
            },
        },
        {
            "name": READ_ANALYSIS,
            "description": str(
                _(
                    "Lies eine Analyse: Druckbarkeit (Überhang, Inseln, Brücken), "
                    "Zeit- und Materialschätzung, Einstellungsrat oder "
                    "Orientierungssuche. Nur lesend, Herkunft wird ausgewiesen."
                )
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["printability", "estimate", "advice", "orientation"],
                    },
                    OBJECTS_FIELD: {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": str(
                            _("Nur diese Objekte rechnen; ohne Angabe die ganze Szene.")
                        ),
                    },
                },
                "required": ["kind"],
            },
        },
        {
            "name": SET_PRINT_TARGET,
            "description": str(
                _(
                    "Wechsle Drucker oder Material des Projekts. Toleranzen sind "
                    "Verweise ins Materialprofil und rechnen sich mit um."
                )
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "printer": {"type": "string"},
                    "material": {"type": "string"},
                },
            },
        },
    )


def names(registry: Registry | None = None) -> tuple[str, ...]:
    return tuple(str(schema["name"]) for schema in tool_schemas(registry))
