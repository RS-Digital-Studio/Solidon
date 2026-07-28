"""What the agent can do (Bauplan §26.2).

Every operation from the registry, plus seven tools that reach past geometry:
asking, undoing, parameters, fits, the report, and the part library.

The operations are not written out here either — they come from the registry
like the menu and the command line do (§10). An operation declared today is a
tool tomorrow without anyone touching this file.

``ask_user`` is not politeness but a duty (Leitprinzip 6, §26.2): the suite
deliberately contains ambiguous requests and measures whether it was used.
"""

from __future__ import annotations

from typing import Any, Final

from app.core.registry import REGISTRY, Registry
from app.core.registry import tool_schemas as op_schemas
from app.i18n import _

#: Name of the extra property every operation tool carries: which objects it
#: applies to. The parameter schema knows nothing about the scene, so this is
#: added here rather than in every declaration.
OBJECTS_FIELD: Final = "objects"

ASK_USER: Final = "ask_user"
UNDO_TRANSACTION: Final = "undo_transaction"
ADD_PARAMETER: Final = "add_parameter"
SET_PARAMETER: Final = "set_parameter"
ADD_FIT: Final = "add_fit"
READ_REPORT: Final = "read_report"
FIND_PART: Final = "find_part"

EXTRA_TOOLS: Final[tuple[str, ...]] = (
    ASK_USER,
    UNDO_TRANSACTION,
    ADD_PARAMETER,
    SET_PARAMETER,
    ADD_FIT,
    READ_REPORT,
    FIND_PART,
)


def tool_schemas(registry: Registry | None = None) -> tuple[dict[str, Any], ...]:
    """Everything the model may call, operations first."""
    return (*operation_tools(registry), *extra_tools())


def operation_tools(registry: Registry | None = None) -> tuple[dict[str, Any], ...]:
    """The registry as tools, each with the objects it works on."""
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
        schemas.append(
            {
                "name": schema["name"],
                "description": schema["description"],
                "input_schema": parameters,
            }
        )
    return tuple(schemas)


def extra_tools() -> tuple[dict[str, Any], ...]:
    """The seven from the table in §26.2."""
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
    )


def names(registry: Registry | None = None) -> tuple[str, ...]:
    return tuple(str(schema["name"]) for schema in tool_schemas(registry))
