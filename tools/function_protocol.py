"""Das Messprotokoll eines Funktionsfalls und was hineingeht (D0-P, RM-737).

**Das Schema gehört D0-U** (``tools/function_checks.PROTOCOL_SCHEMA``):
Feldnamen, Wertebereiche und Phasen kommen von dort, :func:`empty_protocol`
legt jedes Feld an, und ``validate_protocol`` prüft, was geschrieben wird.
Hier steht, was der Prüfstand roh misst — der Szenenabdruck aus Dokument und
Körpern (:func:`scene_print`, :func:`compare_prints`), die Kennzahlen eines
Ergebnisses (:func:`result_metrics`), die Kommandozeile zum Vergleich
(:func:`cli_arguments`), Ziehzeiten und Abbruchdauer roh
(:func:`drag_frames`, :func:`abort_entry`). Geurteilt wird bei D0-U.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, Final

from tools.function_checks import (
    PROTOCOL_SCHEMA,
)


def _digest(data: object) -> str:
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def scene_print(
    document: Any,
    scene: Any | None,
    *,
    selection: Sequence[str] = (),
    camera: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Der Abdruck einer Szene (Konzept §4 „Szenenabdruck“, Plan D0, Abschnitt 2.7).

    ``ops`` nennt die Operationen in ihrer Folge — U liest daran, ob der Verlauf
    gewachsen ist —, ``params`` je Schritt den Abdruck seiner Werte,
    ``project_params`` und ``fits`` die Projektparameter und Passungen über die
    Schreibweise der Projektdatei (``scene.serialise``), ``bodies`` je Körper
    sein Netz (``file_acceptance.body_digest``). Auswahl und Kamera stehen
    getrennt: Nach einem Rückgängig ist eine andere Auswahl ein Vermerk, kein
    Fehler (Prüfpunkt 5).
    """
    from app.core.scene.serialise import fit_to_data, operation_to_data, parameter_to_data
    from tools.file_acceptance import body_digest

    operations = [operation_to_data(entry) for entry in document.ops]
    parameters = {
        str(name): parameter_to_data(parameter) for name, parameter in document.parameters.items()
    }
    bodies = (
        {str(key): body_digest(entry.mesh) for key, entry in scene.objects.items()}
        if scene is not None
        else {}
    )
    position, focal, up, scale = (list(camera) + [None] * 4)[:4] if camera else (None,) * 4
    return {
        "ops": [entry.op for entry in document.ops],
        "params": [_digest(entry.get("params")) for entry in operations],
        "project_params": _digest(parameters),
        "fits": _digest([fit_to_data(fit) for fit in document.fits]),
        "bodies": bodies,
        "selection": list(selection),
        "camera": {
            "position": _rounded(position),
            "focal": _rounded(focal),
            "up": _rounded(up),
            "scale": None if scale is None else round(float(scale), 4),
        },
    }


def _rounded(vector: Any) -> list[float] | None:
    return None if vector is None else [round(float(value), 4) for value in vector]


#: Die Teile eines Abdrucks, die zum Dokument gehören; Auswahl und Kamera nicht.
DOCUMENT_PARTS: Final[tuple[str, ...]] = ("ops", "params", "project_params", "fits", "bodies")


def compare_prints(
    first: Mapping[str, Any] | None, second: Mapping[str, Any] | None
) -> dict[str, Any]:
    """Was zwei Abdrücke sagen — ``None`` heißt: nicht vergleichbar, weil einer fehlt."""
    if first is None or second is None:
        return {"same": None, "differs": [], "selection_same": None, "camera_same": None}
    differs = [part for part in DOCUMENT_PARTS if first.get(part) != second.get(part)]
    return {
        "same": not differs,
        "differs": differs,
        "selection_same": first.get("selection") == second.get("selection"),
        "camera_same": first.get("camera") == second.get("camera"),
    }


def protocol_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Die Zeile, wie das Protokoll sie trägt: nur die Schlüssel des Schemas.

    Das sind die Felder von L's ``Row`` (``function_checks.ROW_KEYS``), samt dem
    Auswahlweg ``route``; geklickt steht er zusätzlich in ``steps``.
    """
    keys = PROTOCOL_SCHEMA["row"].keys or frozenset()
    data = {key: row[key] for key in sorted(keys) if key in row}
    if "spec" in data:
        data["spec"] = dict(data["spec"] or {})
    if "covers" in data:
        data["covers"] = list(data["covers"] or ())
    return data


def protocol_spec(spec: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Die Spezifikation im Protokoll: nur die Schlüssel des Schemas, ohne Lesevermerke.

    ``function_list`` hängt an jede gelesene Spezifikation, aus welcher Datei und
    welchem Paket sie stammt (``file``, ``package``); das Protokoll trägt das Paket
    oben und die Datei nicht.
    """
    if not spec:
        return None
    keys = PROTOCOL_SCHEMA["spec"].keys or frozenset(spec)
    return {key: spec[key] for key in spec if key in keys}


def empty_protocol(
    row: Mapping[str, Any], variant: Mapping[str, Any], version: Mapping[str, str]
) -> dict[str, Any]:
    """Das Gerüst eines Messprotokolls nach ``function_checks.PROTOCOL_SCHEMA``.

    Jedes Feld des Schemas steht da; ungemessen heißt ``None``, und
    ``unmeasured`` nennt den Grund — fehlende ``steps`` ergeben bei U „nicht
    gemessen“, nie „gut“. ``variant`` ist schon die Form des Protokolls
    (:meth:`Variant.protocol`), mit der Fenstergröße des Falls. ``scrollbars``
    ist immer eine Liste, auch leer: U urteilt Z6 je Zeile über alle ihre Fälle
    und braucht dafür jede Größe (D0-U, ``ccbb4df12``).
    """
    data: dict[str, Any] = dict.fromkeys(PROTOCOL_SCHEMA)
    data.update(
        {
            "row": protocol_row(row),
            "kind": str(row.get("kind") or ""),
            "package": str(row.get("package") or ""),
            "spec": protocol_spec(row.get("spec")),
            "variant": dict(variant),
            "version": {
                "commit": str(version.get("commit", "")),
                "app": str(version.get("app", "")),
            },
            "steps": [],
            "states": {},
            "scrollbars": [],
            "findings": [],
            "closed_by_escape": [],
            "unmeasured": {},
            "images": [],
            "errors": [],
        }
    )
    return data


def unmeasured(data: dict[str, Any], name: str, reason: str) -> None:
    """Vermerkt, warum ein Feld leer bleibt — der erste Grund gilt."""
    data["unmeasured"].setdefault(name, reason)


def drag_frames(latencies: Sequence[float | None], factor: float) -> dict[str, Any]:
    """Z1 fürs Protokoll: die Ziehzeiten roh und der Referenzfaktor des Laufs (Review M3).

    Umgerechnet wird einmal, bei D0-U (``max(raw_drag_ms) * reference_factor``);
    schriebe der Prüfstand schon umgerechnete Zeiten, wirkte der Faktor doppelt.
    """
    return {
        "raw_drag_ms": [None if value is None else round(value, 1) for value in latencies],
        "reference_factor": factor,
    }


def abort_entry(data: dict[str, Any], shown: float | None, clicked: bool) -> dict[str, Any]:
    """Prüfpunkt 14 fürs Protokoll: wie lange die abgebrochene Rechnung ohne Abbruch dauert.

    Die Dauer kommt aus dem Hauptweg an derselben Szene (``timing.total_s``, roh),
    nicht aus der Ladezeit der Startszene (Review M4). Lief der Hauptweg nicht
    durch, ist sie ungemessen.
    """
    total = (data.get("timing") or {}).get("total_s")
    if total is None:
        unmeasured(data, "abort.eval_s", "der Hauptweg ohne Abbruch lief nicht durch")
    return {"eval_s": total, "cancel_shown_s": shown, "clicked": clicked}


def result_metrics(scene: Any, document: Any, selected: tuple[str, str] | None) -> dict[str, Any]:
    """Kennzahlen des Ergebnisses, benannt wie die Erwartungen der Spezifikation.

    ``volume`` und ``extent`` über alle Körper, ``bounds.<achse>_<min|max>``,
    ``<art>.<wert>`` am gewählten Merkmal (``hole.diameter``; ohne Auswahl das
    erste seiner Art) und ``parameter.<name>`` aus den Projektparametern — die
    Namen, die ``tests/data/function_rows`` verwendet (Bericht D0-L).
    """
    from app.core.errors import AppError
    from app.core.geom.mesh import as_mesh_data

    metrics: dict[str, Any] = {}
    volume = 0.0
    lows: list[Any] = []
    highs: list[Any] = []
    for key, entry in scene.objects.items():
        try:
            raw = as_mesh_data(entry.mesh).raw
        except AppError:
            # Nicht still (Review L15): Volumen und Maße gelten dann für weniger Körper.
            metrics.setdefault("bodies_without_mesh", []).append(str(key))
            continue
        volume += float(raw.volume)
        low, high = raw.bounds
        lows.append(low)
        highs.append(high)
    if lows:
        low = [min(float(point[axis]) for point in lows) for axis in range(3)]
        high = [max(float(point[axis]) for point in highs) for axis in range(3)]
        metrics["volume"] = round(volume, 4)
        metrics["extent"] = [round(b - a, 4) for a, b in zip(low, high, strict=True)]
        for axis, name in enumerate("xyz"):
            metrics[f"bounds.{name}_min"] = round(low[axis], 4)
            metrics[f"bounds.{name}_max"] = round(high[axis], 4)
    seen: set[str] = set()
    ordered = []
    if selected is not None and selected[0] in scene.objects:
        chosen = scene.objects[selected[0]].features.get(selected[1])
        if chosen is not None:
            ordered.append(chosen)
    ordered += [feature for entry in scene.objects.values() for feature in entry.features.values()]
    for feature in ordered:
        if feature.kind in seen:
            continue
        seen.add(feature.kind)
        for key, value in feature.params.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                metrics[f"{feature.kind}.{key}"] = round(float(value), 4)
    for name, parameter in document.parameters.items():
        value = getattr(parameter, "value", None)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            metrics[f"parameter.{name}"] = round(float(value), 4)
    return metrics


def cli_arguments(operation: Mapping[str, Any]) -> list[str] | None:
    """Die Werte eines Schritts (``serialise.operation_to_data``) für ``app.cli.main run``.

    Nur Zahlen, Texte und Wahrheitswerte haben dort ein Feld; ein Schritt mit
    anderen Werten (Listen, Bezüge) ist über die Kommandozeile nicht derselbe —
    dann ``None``, und Prüfpunkt 4 vermerkt den Vergleich als nicht gemessen.
    """
    arguments = [str(operation["op"])]
    inputs = [str(name) for name in operation.get("in", ())]
    if inputs:
        arguments += ["--on", *inputs]
    for name, value in (operation.get("params") or {}).items():
        flag = "--" + str(name).replace("_", "-")
        if isinstance(value, bool):
            arguments.append(flag if value else "--no-" + str(name).replace("_", "-"))
        elif isinstance(value, (int, float, str)):
            arguments += [flag, str(value)]
        else:
            return None
    return arguments


def bodies_digest(bodies: Mapping[str, str]) -> str:
    """Ein Abdruck über die Abdrücke aller Körper — ``result.digest``, ``cli.digest``."""
    return _digest(dict(sorted(bodies.items())))


def safe_name(text: str) -> str:
    """Ein eindeutiger Dateiname aus einer Kennung: lesbarer Anfang und ein Kurzabdruck.

    ``Datei/Speichern unter …`` und ``Datei/Speichern unter`` ergaben vorher
    denselben Namen, und eine Fläche überschrieb die andere oder galt als
    erledigt (Review L4). Der Abdruck hängt an der ganzen Kennung.
    """
    cleaned = "".join(
        character if character.isalnum() or character in "._-" else "_" for character in text
    )
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    return f"{cleaned.strip('_')[:100] or 'zeile'}-{digest}"
