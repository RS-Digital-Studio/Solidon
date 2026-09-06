"""Reine Datenauswertung: Ablaufabschluss, Zusagen und Prüfgrenzen getrennt halten."""

from __future__ import annotations

import hashlib
import json

PROMISES = {
    "passed",
    "same",
    "restored",
    "selected",
    "checked",
    "document_unchanged",
    "transaction_unchanged",
    "exact_scene_equal",
    "operation_count_equal",
    "transaction_count_equal",
    "baseline_restored",
    "undo_redo_undo",
    "scene_unchanged",
    "geometry_changed",
    "viewport_layer_cleared",
    "slider_changed",
    "matched",
}
FEATURE_PROMISES = {
    "resize_feature": ("diameter_matches",),
    "resize_hole": ("diameter_matches",),
    "move_feature": ("position_matches",),
    "remove_feature": ("original_id_removed",),
    "duplicate_feature": ("original_kept", "copy_has_own_id"),
}
GESTURE_LABELS = ("Freier Körperzug mit Merkmalen", "Freier Körperzug: gehaltene Vorschau")


def leaves(value, path=""):
    """Auch verschachtelte Einzelvergleiche mit ihrer Fundstelle bewahren."""
    if isinstance(value, dict):
        for key, child in value.items():
            yield from leaves(child, f"{path}.{key}" if path else key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from leaves(child, f"{path}[{index}]")
    else:
        yield path, value


def observations(data):
    """Falsche Zusagen sind Nachprüfungen; nicht geprüfte Wege bleiben Grenzen."""
    found = []
    for index, row in enumerate(data.get("checks", [])):
        label = row.get("label", "")
        failures, limits = [], []
        for path, value in leaves(row):
            key = path.rsplit(".", 1)[-1]
            if value is False and (
                key in PROMISES
                or key.endswith(("_matches", "_match", "_unchanged", "_equal"))
                or path.startswith("semantic_checks.")
                or (
                    label in GESTURE_LABELS
                    and (
                        path.startswith(("checks.", "held_checks."))
                        or key == "undo_restored_original_geometry"
                    )
                )
                or (
                    key == "changed"
                    and label in ("Kamera durch Mauszug", "Merkmalshandlung Ergebnis")
                )
            ):
                failures.append(path)
            if key == "skipped" and value:
                limits.append(f"{path}: {value}")
            if "comparison_limits[" in path and value:
                limits.append(str(value))
        status = row.get("status")
        if status in ("failed", "probe_timeout", "probe_cancelled_after_timeout"):
            failures.append(f"status={status}")
        if any(
            word in label.lower() for word in ("prüffehler", "auffällig", "nicht wiederhergestellt")
        ):
            failures.append("als auffällig protokolliert")
        if row.get("error") or row.get("errors") or row.get("traceback"):
            failures.append("Fehlermeldung protokolliert")
        if row.get("stopped_at") is not None:
            failures.append("Operationsauswertung angehalten")
        if "ausgelassen" in label or status in ("limited", "skipped", "partial", "unsupported"):
            limits.append(row.get("reason") or row.get("note") or str(status))
        if row.get("coverage_limit"):
            limits.append(row["coverage_limit"])
        if label in GESTURE_LABELS and status not in ("skipped", "unsupported"):
            expected = ["held_checks"]
            if label == GESTURE_LABELS[0]:
                expected.extend(("checks", "undo_restored_original_geometry"))
            missing = [key for key in expected if row.get(key) is None or row.get(key) == {}]
            if missing:
                limits.append("Gesteneigenschaft nicht protokolliert: " + ", ".join(missing))
        if row.get("coverage_complete") is False or row.get("unverified_bodies"):
            limits.append(
                "Klickabdeckung fehlt für Körper: " + ", ".join(row.get("unverified_bodies", []))
            )
        if label == "Oberflächenklicks" and not row.get("independent_comparisons"):
            limits.append("Kein unabhängiger Oberflächenvergleich durchgeführt")
        if label == "Hover-Ereignisse und Ausnahmen" and row.get("measured", 0) < row.get(
            "requested", 0
        ):
            limits.append(
                f"Hover nur {row.get('measured', 0)}/{row.get('requested', 0)} Ereignisse gemessen"
            )
        if label == "Merkmalshandlung Ergebnis":
            checks = row.get("semantic_checks", {})
            expected = list(FEATURE_PROMISES.get(row.get("op"), ()))
            if not expected:
                limits.append("Für diese Operation fehlt eine unabhängige Zieleigenschaftsprüfung")
            if row.get("variant") == "alle-gleichartigen":
                expected.append("all_sibling_diameters_match")
            expected.append("other_bodies_unchanged")
            missing = [key for key in expected if checks.get(key) is None]
            if missing:
                limits.append("Eigenschaft nicht unabhängig bestätigt: " + ", ".join(missing))
            if not checks:
                limits.append("Keine semantischen Eigenschaftsprüfungen protokolliert")
            if row.get("transaction_delta") is not None and row["transaction_delta"] != 1:
                failures.append("Eine Merkmalsbearbeitung erzeugt nicht genau eine Transaktion")
        if label == "Analysekarte":
            requested = row.get("kind")
            if "selected" in row and row["selected"] != requested:
                failures.append("ausgewählte Karte weicht vom Auftrag ab")
            if requested is not None and "computed" in row and not row["computed"]:
                limits.append("Angeforderte Karte nicht berechnet; sichtbare Rückmeldung prüfen")
            if row.get("computed") and row.get("actual_kind") != requested:
                failures.append("berechnete Kartenart weicht vom Auftrag ab")
        if (
            label == "Thema am sichtbaren Fenster"
            and row.get("expected_feature") is not None
            and row.get("selected_feature") != row["expected_feature"]
        ):
            failures.append("Merkmalsauswahl nach Themenwechsel nicht erhalten")
        context = {
            key: row[key]
            for key in (
                "object",
                "op",
                "operation",
                "kind",
                "variant",
                "reason",
                "note",
                "error",
                "errors",
                "traceback",
                "status",
                "passed",
                "stage",
                "scope",
                "coverage_limit",
            )
            if key in row
        }
        if failures:
            found.append(
                {
                    "category": "Nachprüfung",
                    "label": label,
                    "check_index": index,
                    "failed_fields": sorted(set(failures)),
                    "context": context,
                }
            )
        if limits:
            found.append(
                {
                    "category": "Grenze oder ausgelassener Weg",
                    "label": label,
                    "check_index": index,
                    "limits": sorted(set(limits)),
                    "context": context,
                }
            )
    return found


def completed_final_case(case):
    """Ein isolierter Gestenlauf ersetzt auch mit Exit 0 keinen Finaldurchgang."""
    return bool(
        case.get("final_selected")
        and not case.get("gesture_only")
        and case.get("complete")
        and case.get("exit") == 0
        and case.get("result_belongs_to_run") is True
        and case.get("closed") is True
        and case.get("source_unchanged") is True
        and case.get("source_matches_frozen_manifest") is True
    )


def fingerprint(values):
    """Hash des protokollierten Dateiverzeichnisses, ohne Produktdateien neu zu lesen."""
    if not values:
        return None
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode("utf-8")).hexdigest()


def freeze_evidence(data, frozen, selected_frozen):
    """Protokollierte Python-Quellen mit ihrem und dem gewählten Freeze vergleichen."""
    actual = data.get("source_files_sha256", {})

    def expected(manifest):
        if manifest.get("copy_verified") is not True:
            return {}
        return {
            name: value
            for name, value in manifest.get("final_app_files_sha256", {}).items()
            if name.endswith(".py")
        }

    own_expected = expected(frozen)
    selected_expected = expected(selected_frozen)
    return {
        "frozen_manifest_available": bool(own_expected),
        "frozen_manifest_fingerprint": fingerprint(own_expected),
        "source_matches_frozen_manifest": (
            actual == own_expected if actual and own_expected else None
        ),
        "selected_manifest_fingerprint": fingerprint(selected_expected),
        "source_matches_selected_manifest": (
            actual == selected_expected if actual and selected_expected else None
        ),
    }


def evidence(data, process, entry):
    """Prozess, Originaldatei und Quellstand dürfen einander nicht ersetzen."""
    result_id, process_id = data.get("run_id"), process.get("run_id")
    linked = result_id == process_id if result_id and process_id else None
    if process.get("result_belongs_to_run") is False:
        linked = False
    sources = data.get("source_files_sha256", {})
    unchanged = process.get("source_unchanged", {})
    source_same = None
    if any(value is False for value in unchanged.values()):
        source_same = False
    elif (
        sources
        and set(sources) == set(unchanged)
        and all(value is True for value in unchanged.values())
    ):
        source_same = True
    original = [
        row for row in data.get("checks", []) if row.get("label") == "Originaldatei unverändert"
    ]
    original_same = original[-1].get("same") if original else None
    actual_sha = data.get("entry", {}).get("sha256")
    original_matches = (
        actual_sha == entry.get("sha256") if actual_sha and entry.get("sha256") else None
    )
    details = {
        "run_id": result_id,
        "process_run_id": process_id,
        "result_belongs_to_run": linked,
        "original_sha256": entry.get("sha256"),
        "recorded_original_sha256": actual_sha,
        "original_matches_manifest": original_matches,
        "original_unchanged": original_same,
        "source_unchanged": source_same,
        "source_files_count": len(sources),
        "source_fingerprint": fingerprint(sources),
        "source_changed_files": sorted(name for name, same in unchanged.items() if same is False),
        "source_unchecked_files": sorted(set(sources) - set(unchanged)),
        "probe_fingerprint": fingerprint(data.get("probe_files_sha256", {})),
        "shutdown_error": data.get("shutdown_error"),
        "closed": data.get("closed"),
        "errors": data.get("errors", []),
        "process_timeout": process.get("process_timeout", False),
        "launch_error": process.get("launch_error"),
        "process_available": bool(process),
        "result_available": bool(data),
    }
    return details


def evidence_issues(data, process, info):
    """Fehlende Nachweise neutral benennen; tatsächliche Widersprüche herausstellen."""
    found = []
    for key, label in (
        ("result_belongs_to_run", "Ergebnis gehört zum protokollierten Prozess"),
        ("original_matches_manifest", "Original-SHA stimmt mit dem Manifest überein"),
        ("original_unchanged", "Originaldatei am Ende unverändert"),
        ("source_unchanged", "Quellstand während des Durchgangs unverändert"),
        ("closed", "Anwendungsfenster nach dem Herunterfahren geschlossen"),
    ):
        value = info[key]
        if value is not True:
            found.append(
                {
                    "category": "Nachprüfung"
                    if value is False
                    else "Grenze oder ausgelassener Weg",
                    "label": label,
                    "reason": "widerlegt" if value is False else "nicht nachgewiesen",
                }
            )
    for key in ("fatal", "shutdown_error", "errors", "_report_read_error"):
        if data.get(key):
            found.append({"category": "Nachprüfung", "label": key, "reason": data[key]})
    for key in ("launch_error", "process_timeout", "_report_read_error"):
        if process.get(key):
            found.append({"category": "Nachprüfung", "label": key, "reason": process[key]})
    if process.get("exit") != 0:
        found.append(
            {
                "category": "Nachprüfung"
                if process.get("exit") is not None
                else "Grenze oder ausgelassener Weg",
                "label": "Tatsächlicher Prozessausgang",
                "reason": process.get("exit", "noch nicht protokolliert"),
            }
        )
    if not data.get("complete"):
        found.append(
            {
                "category": "Grenze oder ausgelassener Weg",
                "label": "Ablauf nicht abgeschlossen",
                "reason": (
                    "Kein vollständiger Abschlussvermerk; "
                    "Zwischenstand oder abgebrochener Durchgang"
                ),
            }
        )
    return found


def coverage(data):
    """Den beobachteten Umfang zählen, ohne aus einem Auftragsflag Erfolg abzuleiten."""
    checks = data.get("checks", [])
    clicks = next((row for row in reversed(checks) if row.get("label") == "Oberflächenklicks"), {})

    def kinds(label, key):
        return sorted({str(row.get(key)) for row in checks if row.get("label") == label})

    def gesture(label):
        row = next((row for row in reversed(checks) if row.get("label") == label), {})
        return {
            "observed": bool(row),
            **{
                key: row[key]
                for key in (
                    "status",
                    "passed",
                    "scope",
                    "stage",
                    "reason",
                    "coverage_limit",
                    "held_checks",
                    "checks",
                    "undo_restored_original_geometry",
                    "screenshot_requires_visual_review",
                )
                if key in row
            },
        }

    return {
        "full_requested": bool(data.get("full")),
        "gesture_only": bool(data.get("gesture_only")),
        "body_drag": gesture(GESTURE_LABELS[0]),
        "held_body_preview": gesture(GESTURE_LABELS[1]),
        "checks_logged": len(checks),
        "click_coverage_complete": clicks.get("coverage_complete"),
        "independent_comparisons": clicks.get("independent_comparisons", 0),
        "verified_bodies": clicks.get("verified_bodies", []),
        "unverified_bodies": clicks.get("unverified_bodies", []),
        "display_modes": kinds("Darstellung", "mode"),
        "projections": kinds("Projektion", "mode"),
        "analysis_kinds": kinds("Analysekarte", "kind"),
        "layers_observed": any(row.get("label") == "Schichtansicht" for row in checks),
        "feature_edits_observed": any(
            row.get("label") == "Merkmalshandlung Ergebnis" for row in checks
        ),
        "geometry_export_checked": any(
            row.get("label") == "3MF-Geometrie unabhängig wieder eingelesen" for row in checks
        ),
    }


def self_check():
    """Kleine Gegenbeispiele ohne Qt, GPU, Produktimport oder große Datendatei."""
    row = {
        "label": "Oberflächenklicks",
        "passed": True,
        "independent_comparisons": 1,
        "coverage_complete": False,
        "unverified_bodies": ["zweiter-körper"],
        "hits": [{"surface_matches": False, "skipped": "covered"}],
    }
    found = observations({"checks": [row]})
    assert any("hits[0].surface_matches" in issue.get("failed_fields", []) for issue in found)
    assert any("zweiter-körper" in str(issue.get("limits")) for issue in found)
    found = observations(
        {
            "checks": [
                {
                    "label": "Merkmalshandlung Ergebnis",
                    "op": "duplicate_feature",
                    "semantic_checks": {"original_kept": False, "copy_has_own_id": True},
                }
            ]
        }
    )
    assert any("semantic_checks.original_kept" in issue.get("failed_fields", []) for issue in found)
    found = observations(
        {
            "checks": [
                {
                    "label": "Merkmalshandlung Ergebnis",
                    "op": "resize_hole",
                    "semantic_checks": {"other_bodies_unchanged": True},
                }
            ]
        }
    )
    assert found and all(issue["category"] == "Grenze oder ausgelassener Weg" for issue in found)
    assert "diameter_matches" in str(found)
    found = observations(
        {
            "checks": [
                {
                    "label": "Merkmalshandlung Ergebnis",
                    "op": "resize_hole",
                    "variant": "alle-gleichartigen",
                    "semantic_checks": {
                        "diameter_matches": True,
                        "other_bodies_unchanged": True,
                    },
                },
                {
                    "label": "Merkmalshandlung Ergebnis",
                    "op": "rotate_feature",
                    "semantic_checks": {"other_bodies_unchanged": True},
                },
            ]
        }
    )
    assert "all_sibling_diameters_match" in str(found)
    assert any("Zieleigenschaftsprüfung" in str(issue.get("limits")) for issue in found)
    assert all(issue["category"] == "Grenze oder ausgelassener Weg" for issue in found)
    found = observations(
        {
            "checks": [
                {
                    "label": "Bearbeitung ausgelassen",
                    "status": "unsupported",
                    "reason": "Körper bietet dieses Merkmal nicht",
                }
            ]
        }
    )
    assert len(found) == 1 and found[0]["category"] == "Grenze oder ausgelassener Weg"
    assert not observations(
        {"checks": [{"label": "Analysekarte", "kind": None, "selected": None, "computed": False}]}
    )
    for status in ("skipped", "partial"):
        gesture = {"label": GESTURE_LABELS[0], "status": status, "passed": None}
        found = observations({"checks": [gesture]})
        assert found and all(
            issue["category"] == "Grenze oder ausgelassener Weg" for issue in found
        )
        assert coverage({"checks": [gesture]})["body_drag"]["passed"] is None
    failed_gesture = {
        "label": GESTURE_LABELS[1],
        "status": "observed",
        "passed": False,
        "held_checks": {"displayed_anchor_to_text": False, "camera_unchanged": True},
    }
    found = observations({"checks": [failed_gesture]})
    assert any(
        "held_checks.displayed_anchor_to_text" in issue.get("failed_fields", []) for issue in found
    )
    complete_case = {
        "final_selected": True,
        "complete": True,
        "exit": 0,
        "result_belongs_to_run": True,
        "closed": True,
        "source_unchanged": True,
        "source_matches_frozen_manifest": True,
    }
    assert completed_final_case(complete_case)
    assert not completed_final_case({**complete_case, "gesture_only": True})
    entry = {"sha256": "original"}
    data = {
        "complete": True,
        "run_id": "neu",
        "entry": entry,
        "source_files_sha256": {"app/example.py": "source"},
        "checks": [{"label": "Originaldatei unverändert", "same": True}],
    }
    process = {"run_id": "alt", "exit": 0, "source_unchanged": {"app/example.py": True}}
    info = evidence(data, process, entry)
    assert info["result_belongs_to_run"] is False and info["source_unchanged"] is True
    process["run_id"] = "neu"
    process["source_unchanged"] = {}
    assert evidence(data, process, entry)["source_unchanged"] is None
    process["source_unchanged"] = {"app/example.py": False}
    assert evidence(data, process, entry)["source_unchanged"] is False
    assert (
        evidence(data, process, {"sha256": "anderes-original"})["original_matches_manifest"]
        is False
    )
    data.update(errors=["UI-Fehler"], shutdown_error="nativer Abbruch", screenshots=[])
    found = evidence_issues(data, process, evidence(data, process, entry))
    assert any(issue["label"] == "errors" for issue in found)
    assert any(issue["label"] == "shutdown_error" for issue in found)
    assert coverage({"full": True, "checks": []})["layers_observed"] is False
    frozen = {
        "copy_verified": True,
        "final_app_files_sha256": {"app/example.py": "source", "app/CLAUDE.md": "doc"},
    }
    selected = {
        "copy_verified": True,
        "final_app_files_sha256": {"app/example.py": "different-source"},
    }
    info = freeze_evidence(data, frozen, selected)
    assert info["source_matches_frozen_manifest"] is True
    assert info["source_matches_selected_manifest"] is False
    assert freeze_evidence(data, {}, selected)["source_matches_frozen_manifest"] is None
    data["closed"] = False
    found = evidence_issues(data, process, evidence(data, process, entry))
    assert any("geschlossen" in issue["label"] for issue in found)
    print(
        "Berichtsgegenproben grün: Semantik, Klickgrenzen, Auslassungen, "
        "Prozesszuordnung, Hashes und Abbruch"
    )


if __name__ == "__main__":
    self_check()
