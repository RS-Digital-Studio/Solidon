"""Verdichtet die tatsächlichen UI-Durchgänge ohne aus Vollständigkeit Erfolg abzuleiten."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from report_checks import (
    completed_final_case,
    coverage,
    evidence,
    evidence_issues,
    freeze_evidence,
    observations,
)

ROOT = Path(__file__).resolve().parent
manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf8"))


def esc(value):
    return html.escape(str(value))


def read(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf8"))
    except (OSError, ValueError) as error:
        return {"_report_read_error": f"{path.name}: {error}"}


def metric(data, name):
    row = next((r for r in data.get("checks", []) if r["label"] == name), {})
    return row.get("median_ms")


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--final-source", type=Path, help="Gewählter Freeze, absolut oder im Auditordner"
)
args = parser.parse_args()
if args.final_source:
    selected_source = args.final_source
    if not selected_source.is_absolute():
        selected_source = ROOT / selected_source
else:
    candidates = [
        path
        for path in ROOT.glob("final-source-v*")
        if path.name.removeprefix("final-source-v").isdigit()
        and (path / "audit-source-manifest.json").is_file()
    ]
    selected_source = max(
        candidates,
        key=lambda path: int(path.name.removeprefix("final-source-v")),
        default=ROOT / "final-source",
    )
selected_source = selected_source.resolve()
selected_manifest = read(selected_source / "audit-source-manifest.json")
manifest_cache = {str(selected_source): selected_manifest}
histories = {
    path.name.removesuffix("-processes.json"): read(path)
    for path in sorted(ROOT.glob("*-processes.json"))
}
rows = []
for item in manifest:
    line = {
        "index": item["index"],
        "name": item["name"],
        "original_sha256": item["sha256"],
        "original_path": item["path"],
        "selected_final_source": str(selected_source),
    }
    for phase in ("baseline", "verified"):
        for backend in ("gfx", "vtk"):
            folder = ROOT / phase / backend / f"file-{item['index']:02d}"
            latest = ROOT / "final" / backend / f"file-{item['index']:02d}"
            if phase == "verified" and any(
                (latest / name).exists() for name in ("result.json", "process.json", "run.log")
            ):
                folder = latest
            data = read(folder / "result.json")
            process = read(folder / "process.json")
            integrity = evidence(data, process, item)
            semantic = observations(data)
            issues = semantic + evidence_issues(data, process, integrity)
            actual_phase = folder.relative_to(ROOT).parts[0]
            observed = coverage(data)
            gesture_only = bool(data.get("gesture_only") or process.get("gesture_only"))
            observed["gesture_only"] = gesture_only
            if gesture_only:
                issues.append(
                    {
                        "category": "Grenze oder ausgelassener Weg",
                        "label": "Isolierter Gestenlauf",
                        "reason": (
                            "Prüft Körperzug und Vorschau; ersetzt keinen "
                            "vollständigen Finaldurchgang"
                        ),
                    }
                )
            if (data.get("full") or gesture_only) and not observed["body_drag"]["observed"]:
                issues.append(
                    {
                        "category": "Grenze oder ausgelassener Weg",
                        "label": "Gestenabdeckung",
                        "reason": "Kein freier Körperzug mit Merkmalen protokolliert",
                    }
                )
            if (
                observed["body_drag"]["observed"]
                and observed["body_drag"].get("status") not in ("skipped", "unsupported")
                and not observed["held_body_preview"]["observed"]
            ):
                issues.append(
                    {
                        "category": "Grenze oder ausgelassener Weg",
                        "label": "Gestenabdeckung",
                        "reason": "Kein eigener Nachweis während der gehaltenen Körpervorschau",
                    }
                )
            source = data.get("source_directory")
            if source and source not in manifest_cache:
                manifest_cache[source] = read(Path(source) / "audit-source-manifest.json")
            frozen = freeze_evidence(data, manifest_cache.get(source, {}), selected_manifest)
            final_selected = (
                actual_phase == "final" and frozen["source_matches_selected_manifest"] is True
            )
            if actual_phase == "final" and data and not final_selected:
                issues.append(
                    {
                        "category": "Grenze oder ausgelassener Weg",
                        "label": "Finaler Quellstand",
                        "reason": (
                            f"Python-Quellen stimmen nicht nachweislich mit dem gewählten Freeze "
                            f"{selected_source.name} überein: "
                            f"{frozen['source_matches_selected_manifest']}"
                        ),
                    }
                )
            if source and frozen["source_matches_frozen_manifest"] is not True:
                matches = frozen["source_matches_frozen_manifest"]
                issues.append(
                    {
                        "category": "Nachprüfung"
                        if matches is False
                        else "Grenze oder ausgelassener Weg",
                        "label": "Quellen entsprechen dem eigenen eingefrorenen Manifest",
                        "reason": "widerlegt" if matches is False else "nicht nachgewiesen",
                    }
                )
            missing_images = [
                name for name in data.get("screenshots", []) if not (folder / name).is_file()
            ]
            if missing_images:
                issues.append(
                    {
                        "category": "Grenze oder ausgelassener Weg",
                        "label": "Bildnachweise fehlen",
                        "reason": missing_images,
                    }
                )
            if data:
                for field, expected in (
                    ("display_modes", {"solid", "solid_edges", "wireframe", "transparent"}),
                    ("projections", {"perspective", "orthographic"}),
                ):
                    missing = sorted(expected - set(observed[field]))
                    if missing:
                        issues.append(
                            {
                                "category": "Grenze oder ausgelassener Weg",
                                "label": "Darstellungsabdeckung",
                                "reason": f"{field} nicht protokolliert: {', '.join(missing)}",
                            }
                        )
                if not observed["independent_comparisons"]:
                    issues.append(
                        {
                            "category": "Grenze oder ausgelassener Weg",
                            "label": "Klickabdeckung",
                            "reason": "Kein unabhängiger Oberflächenvergleich nachgewiesen",
                        }
                    )
            attempts = []
            for history_phase, records in histories.items():
                if not isinstance(records, list):
                    continue
                for record in records:
                    if record.get("index") == item["index"] and record.get("renderer") == backend:
                        attempts.append(
                            {
                                "history_phase": history_phase,
                                "changed_source_files": [
                                    name
                                    for name, value in record.get("source_unchanged", {}).items()
                                    if value is False
                                ],
                                **{
                                    key: record[key]
                                    for key in (
                                        "run_id",
                                        "exit",
                                        "complete",
                                        "gesture_only",
                                        "fatal",
                                        "launch_error",
                                        "process_timeout",
                                        "result_belongs_to_run",
                                        "elapsed_seconds",
                                        "source_directory",
                                    )
                                    if key in record
                                },
                            }
                        )
            scene = (
                next(
                    (
                        r.get("scene")
                        for r in data.get("checks", [])
                        if r["label"] == "Import und Erkennung"
                    ),
                    {},
                )
                or {}
            )
            line[phase + "_" + backend] = {
                "folder": str(folder.relative_to(ROOT)).replace("\\", "/"),
                "complete": data.get("complete", False),
                "exit": process.get("exit"),
                "actual_phase": actual_phase,
                "final_available": actual_phase == "final",
                "final_selected": final_selected,
                "fatal": data.get("fatal"),
                "frame_ms": metric(data, "Navigation fertiger Bilder"),
                "full": data.get("full", False),
                "gesture_only": gesture_only,
                "versions": data.get("versions", {}),
                "source": data.get("source_directory"),
                **integrity,
                **frozen,
                "coverage": observed,
                "process_history": attempts,
                "semantic_failure_count": sum(
                    issue["category"] == "Nachprüfung" for issue in semantic
                ),
                "gpu_completion_method": data.get("gpu_completion_method"),
                "timings": [r for r in data.get("checks", []) if "median_ms" in r],
                "pick_ms": metric(data, "Oberflächentreffer Renderer"),
                "hover_ms": metric(data, "Hover Merkmalssuche"),
                "triangles": sum(o["triangles"] for o in scene.get("objects", [])),
                "objects": len(scene.get("objects", [])),
                "features": sum(len(o["features"]) for o in scene.get("objects", [])),
                "issues": issues,
                "screenshots": data.get("screenshots", []),
            }
    first, second = line["verified_gfx"], line["verified_vtk"]
    line["pair_source_consistent"] = (
        first["source_fingerprint"] == second["source_fingerprint"]
        if first["source_fingerprint"] and second["source_fingerprint"]
        else None
    )
    line["pair_probe_consistent"] = (
        first["probe_fingerprint"] == second["probe_fingerprint"]
        if first["probe_fingerprint"] and second["probe_fingerprint"]
        else None
    )
    rows.append(line)
(ROOT / "summary.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf8")


def fmt(value):
    return "nicht gemessen" if value is None else f"{value:.2f}".replace(".", ",")


final_cases = [row["verified_" + backend] for row in rows for backend in ("gfx", "vtk")]
final_started = sum(case["final_available"] and not case["gesture_only"] for case in final_cases)
isolated_gestures = sum(case["final_available"] and case["gesture_only"] for case in final_cases)
final_completed = sum(completed_final_case(case) for case in final_cases)
final_sources = sorted(
    {case["source"] for case in final_cases if case["final_available"] and case["source"]}
)
final_content_mix = (
    len(
        {
            case["source_fingerprint"]
            for case in final_cases
            if case["final_available"] and case["source_fingerprint"]
        }
    )
    > 1
)
parts = [
    '<!doctype html><html lang="de"><meta charset="utf-8">'
    "<title>Solidon: GFX und VTK im Modelltest</title><style>",
    "body{margin:0;background:#10151d;color:#edf2f8;font:15px/1.5 Segoe UI,sans-serif}"
    "main{max-width:1440px;margin:auto;padding:40px}h1{font-size:36px}h2{margin-top:40px}"
    "a{color:#82bfff}p{max-width:1000px;color:#b9c5d3}"
    "table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}"
    "td,th{padding:12px;border-bottom:1px solid #334152;text-align:left}"
    "th{background:#1c2632;position:sticky;top:0}"
    ".pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}"
    ".card{padding:16px;background:#192330;border:1px solid #354559;border-radius:10px}"
    "img{width:100%;height:auto}.muted{color:#95a6ba}details{margin:16px 0}"
    "summary{cursor:pointer;font-weight:600}.bad{color:#ffb4ab}</style><main>",
    "<h1>GFX und VTK an 23 echten Modellen</h1>",
    "<p>Vergleich am sichtbaren Windows-Fenster mit nativer Qt-Ereignissteuerung. Import, "
    "Merkmalsauswahl, Darstellungsmodi, Zeigerereignisse, Schichtansicht und Bearbeitung "
    "werden einzeln protokolliert. Historischer Ausgangsstand: 782f98bb. Die finale Serie "
    f"verlangt 46 Durchgänge mit dem Quellinhalt von {esc(selected_source.name)}. "
    "Solange sie fehlen, bleiben Vorprüfungen "
    "ausdrücklich als solche gekennzeichnet. Original-SHA, Quellstandkonstanz und "
    "Übereinstimmung der Rendererpaare stehen beim Modell.</p>",
    "<p>Zeiten: Median synchronisierter Kamerabilder bzw. Oberflächentreffer in Millisekunden. "
    "Der GFX-Abschlussmarker nutzt einen geordneten 4-Byte-Readback, VTK WaitForCompletion. "
    "Darin sind Treiber-, Präsentations- und Messkosten enthalten; die physische "
    "Bildschirmausgabe wird nicht gemessen. Das sind keine isolierten GPU-Zeiten. "
    "Unterschiedliche Synchronisation zur Bildwiederholung kann den Backendvergleich "
    "begrenzen. Fensterbau nach den Initialimporten, Dateiimport mit Erkennung, Verteilungen "
    "und Darstellungsmodi stehen in den Rohdaten; ein vollständiger Kaltstart wird hier nicht "
    "nachgewiesen. Historische Vorher-Messungen sind Stichproben.</p>",
    "<p>Ein regulär beendeter Ablauf ist allein kein Nachweis aller Funktionen. "
    "„Erweiterter Auftrag“ bedeutet nur, dass Schichten und repräsentative Bearbeitungen "
    "angefordert wurden; es bedeutet keine vollständige Abdeckung aller Operationen und "
    "Eigenschaften. Grenzen oder ausgelassene Wege sind keine automatisch bestätigten "
    "Produktfehler. Isolierte Gestenläufe zählen nicht als beendete Finaldurchgänge; "
    "skipped und partial bleiben unbestätigt. Die Prüfung erfasst die eigene "
    "Qt-Fensterhierarchie, keine Verdeckung "
    "durch fremde Desktopfenster.</p>",
    f"<p><strong>Finale Serie: {final_started}/{len(final_cases)} begonnen; "
    f"{final_completed}/{len(final_cases)} mit dem Quellinhalt von {esc(selected_source.name)}, "
    "unveränderten Python-Quellen, zugeordnetem Exit 0 und nachweislich geschlossenem "
    "Fenster beendet.</strong> "
    f"Isolierte Gestenläufe anstelle eines Finaldurchgangs: {isolated_gestures}. "
    "Semantische Nachprüfungen und Prüfgrenzen werden davon getrennt ausgewiesen.</p>",
    f"<p>Gewählter Freeze: {esc(selected_source)}<br>"
    f"Kopie beim Einfrieren geprüft: {esc(selected_manifest.get('copy_verified'))}<br>"
    f"Quellordner der Finaldurchgänge: {esc(final_sources)}<br>"
    f"Unterschiedliche Python-Quellinhalte in der Finalserie: {final_content_mix}</p>",
    "<table><thead><tr><th>Modell</th><th>GFX vorher<br>Bild / Pick</th>"
    "<th>GFX letzter Stand<br>Bild / Pick</th><th>VTK vorher<br>Bild / Pick</th>"
    "<th>VTK letzter Stand<br>Bild / Pick</th></tr></thead><tbody>",
]
for row in rows:
    parts.append(
        f'<tr><td><a href="#model-{row["index"]}">{row["index"]:02d} · {esc(row["name"])}</a></td>'
    )
    for key in ("baseline_gfx", "verified_gfx", "baseline_vtk", "verified_vtk"):
        v = row[key]
        note = (
            "Vorprüfung"
            if key.startswith("verified") and not v["final_available"]
            else v["actual_phase"]
        )
        problems = sum(issue["category"] == "Nachprüfung" for issue in v["issues"])
        parts.append(
            f"<td>{fmt(v['frame_ms'])} / {fmt(v['pick_ms'])}<br><small>{esc(note)} "
            f"· Exit {esc(v['exit'])} · {problems} Nachprüfungen "
            f"· {len(v['issues']) - problems} Grenzen</small></td>"
        )
    parts.append("</tr>")
parts.append("</tbody></table>")
for phase, records in histories.items():
    if isinstance(records, dict) and records.get("_report_read_error"):
        parts.append(
            f'<p class="bad">Prozesshistorie {esc(phase)} nicht lesbar: '
            f"{esc(records['_report_read_error'])}</p>"
        )
for row in rows:
    parts.append(
        f'<h2 id="model-{row["index"]}">{row["index"]:02d} · {esc(row["name"])}</h2>'
        f"<p>Original: {esc(row['original_path'])}<br>SHA-256: "
        f"<code>{esc(row['original_sha256'])}</code><br>Rendererpaar: gleicher Quellinhalt "
        f"{esc(row['pair_source_consistent'])} · gleicher Prüfcode "
        f'{esc(row["pair_probe_consistent"])}</p><div class="pair">'
    )
    for backend in ("gfx", "vtk"):
        v = row["verified_" + backend]
        parts.append(
            f'<div class="card"><h3>{backend.upper()} · {esc(v["actual_phase"])}</h3>'
            f"<p>{v['objects']} Körper · {v['triangles']:,} Dreiecke "
            f"· {v['features']} erkannte Merkmale</p>"
        )
        parts.append(
            f'<p><a href="{v["folder"]}/result.json">Prüfschritte und Befunde</a> · '
            f'<a href="{v["folder"]}/process.json">Prozessausgang</a> · '
            f'<a href="{v["folder"]}/run.log">Laufprotokoll</a></p>'
        )
        parts.append(
            f"<p>Ablauf beendet: {v['complete']} · Exit: {v['exit']} "
            f"· Ergebnis dem Prozess zugeordnet: {v['result_belongs_to_run']}<br>"
            f"Anwendungsfenster geschlossen: {v['closed']}<br>"
            f"Erweiterter Auftrag: {v['full']} "
            f"· Nur Gesten: {v['gesture_only']} "
            f"· Semantische Nachprüfungen: {v['semantic_failure_count']}<br>"
            f"Original-SHA bestätigt: {v['original_matches_manifest']} "
            f"· Original am Ende unverändert: {v['original_unchanged']}<br>"
            f"Quellstand unverändert: {v['source_unchanged']}<br>"
            f"Entspricht eigenem Freeze: {v['source_matches_frozen_manifest']} "
            f"· entspricht gewähltem Freeze: {v['source_matches_selected_manifest']}</p>"
        )
        parts.append(
            "<details><summary>Klickabdeckung und tatsächlich protokollierter Umfang</summary>"
            f"<pre>{esc(json.dumps(v['coverage'], ensure_ascii=False, indent=2))}</pre></details>"
        )
        parts.append(f'<p class="muted">Quellstand: {esc(v["source"])}<br>{esc(v["versions"])}</p>')
        hash_context = {
            key: v[key]
            for key in (
                "source_fingerprint",
                "source_files_count",
                "source_changed_files",
                "source_unchecked_files",
                "probe_fingerprint",
                "frozen_manifest_fingerprint",
                "selected_manifest_fingerprint",
                "gpu_completion_method",
            )
        }
        parts.append(
            "<details><summary>Hashnachweise und Messkontext</summary>"
            f"<pre>{esc(json.dumps(hash_context, ensure_ascii=False, indent=2))}</pre>"
            "<p>Einzelverteilungen und CPU-Kontext stehen zusätzlich in summary.json und den "
            "Rohdaten. Picks im festen Bild enthalten wiederverwendete Pickpuffer; Hover umfasst "
            "die gesondert protokollierte Entprellwartezeit. 40 Navigationsbilder bzw. 12 Bilder "
            "je Darstellungsmodus ersetzen keine eigenständige Lastreihe. Die Quellkonstanz "
            "je Durchgang erfasst die protokollierten Python-Dateien; weitere Dateien im "
            "Freeze-Manifest werden dabei nicht erneut geprüft.</p></details>"
        )
        if v["issues"]:
            parts.append("<details open><summary>Nachprüfungen und Grenzen</summary><ul>")
            for issue in v["issues"]:
                detail = (
                    issue.get("reason")
                    or issue.get("failed_fields")
                    or issue.get("limits")
                    or issue.get("context")
                )
                parts.append(
                    f"<li>{esc(issue['category'])}: {esc(issue['label'])}: {esc(detail)}<br>"
                    f"<small>{esc(issue.get('context', {}))}</small></li>"
                )
            parts.append("</ul></details>")
        if v["process_history"]:
            parts.append(
                "<details><summary>Prozesshistorie einschließlich früherer Fehlläufe "
                f"({len(v['process_history'])})</summary>"
                f"<pre>{esc(json.dumps(v['process_history'], ensure_ascii=False, indent=2))}"
                "</pre></details>"
            )
        if v["screenshots"]:
            parts.append(
                f'<a href="{v["folder"]}/01-import.png"><img loading="lazy" '
                f'src="{v["folder"]}/01-import.png" alt="Modell nach dem Import"></a>'
            )
            parts.append("<details><summary>Darstellungen und Bediennachweise</summary>")
            for image in v["screenshots"]:
                if image != "01-import.png":
                    parts.append(
                        f'<p>{esc(image)}</p><a href="{v["folder"]}/{esc(image)}">'
                        f'<img loading="lazy" src="{v["folder"]}/{esc(image)}" '
                        f'alt="{esc(image)}"></a>'
                    )
            parts.append("</details>")
        else:
            parts.append(
                '<p class="muted">Kein Screenshot dieses Durchgangs vorhanden. '
                "Ein früheres Bild ersetzt diesen Nachweis nicht.</p>"
            )
        parts.append("</div>")
    parts.append("</div>")
parts.append("</main></html>")
(ROOT / "report.html").write_text("".join(parts), encoding="utf8")
print("Bericht aktualisiert")
