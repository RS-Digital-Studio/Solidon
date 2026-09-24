"""Übernimmt ausschließlich belegte Sitzungszeiten aus dem erfolgreichen Windows-Lauf."""

import hashlib
import json
import math
import re
from pathlib import Path

source = Path(__file__).with_name("windows-baseline.log")
text = re.sub(r"\x1b\[[0-9;]*m", "", source.read_text(encoding="utf-8"))
durations = {}
section = text.split("Fensterdateien: 92", 1)[1]
for session in section.split("test session starts")[1:]:
    paths = set(re.findall(r"(tests/test_[a-zA-Z0-9_]+\.py)::", session))
    summaries = re.findall(r"\d+ passed[^\n]*? in ([0-9.]+)s", session)
    assert len(paths) == len(summaries) == 1, (paths, summaries)
    name = paths.pop()
    assert name not in durations, name
    durations[name] = float(summaries[0])
assert len(durations) == 90, len(durations)
contract = text.split("for file in tests/test_print_settings_ui.py tests/test_render_factory.py; do", 1)[1]
contract = contract.split("windowed=$(python", 1)[0]
times = re.findall(r"\d+ passed[^\n]*? in ([0-9.]+)s", contract)
assert len(times) == 2, times
durations.update(zip(("tests/test_print_settings_ui.py", "tests/test_render_factory.py"), map(float, times), strict=True))
document = {
    "schema": 1,
    "source": {
        "run_id": 35982366247,
        "job_id": 107577041008,
        "url": "https://github.com/RS-Digital-Studio/Solidon/actions/runs/35982366247/job/107577041008",
        "commit": "0895c4a69eb6adcb03834ee7f005087dcc3c2c6d",
        "conclusion": "success",
        "platform": "windows-latest",
        "python": "3.14.7",
        "log_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "measurement": "Sekunden aus den 92 pytest-Schlusszeilen; ohne Prozessstart und Sammlung des Gesamtplans.",
    },
    "unknown_file_seconds": sorted(durations.values())[math.ceil(len(durations) * .9) - 1],
    "unknown_file_policy": "90. Perzentil der ursprünglichen Dateizeiten; neue und umbenannte Dateien bleiben immer in der aktuellen Sammlung.",
    "durations_seconds": dict(sorted(durations.items())),
}
Path("tests/data/ci_window_durations.json").write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"{len(durations)} Dateien, {sum(durations.values()):.2f} s, Ersatzgewicht {document['unknown_file_seconds']:.2f} s")
