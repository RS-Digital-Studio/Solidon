"""Gezielte aktuelle Prüfungen in getrennten Prozessen mit alten Gegenbeispielen."""

from pathlib import Path
import hashlib
import json
import subprocess
import sys
import time

root = Path(__file__).resolve().parent
repository = root.parents[2]
output = root / "v9-targeted"
output.mkdir(exist_ok=False)
names = ("app/ui/viewport.py", "tests/test_viewport_decisions.py", "tests/test_feature_label_layout.py")


def hashes():
    return {name: hashlib.sha256((repository / name).read_bytes()).hexdigest() for name in names}


before = hashes()
commands = [
    ("v8-red", [sys.executable, str(root / "check_v8_regressions.py")], 1),
    ("viewport-green", [sys.executable, "-m", "pytest", "-q",
                        "tests/test_viewport_decisions.py", "tests/test_feature_label_layout.py"], 0),
    ("stl-oracle", [sys.executable, str(root / "check_stl_verifier.py")], 0),
    ("counter-core", [sys.executable, str(root / "core_crash_probes_v7_corrected.py"),
                      "--case", "counter", "--out", str(root / "core-crash-v7-02")], 0),
]
records = []
for name, command, expected in commands:
    start = time.time()
    with (output / f"{name}.log").open("w", encoding="utf-8") as log:
        result = subprocess.run(command, cwd=repository, stdout=log, stderr=subprocess.STDOUT,
                                timeout=180, creationflags=subprocess.CREATE_NO_WINDOW)
    row = {"name": name, "command": command, "exit": result.returncode,
           "expected_exit": expected, "seconds": time.time() - start}
    records.append(row)
    print(json.dumps(row, ensure_ascii=False), flush=True)
    (output / "processes.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    if result.returncode != expected:
        break
after = hashes()
(output / "source.json").write_text(json.dumps({"before": before, "after": after,
    "unchanged": before == after}, indent=2), encoding="utf-8")
raise SystemExit(int(len(records) != len(commands) or before != after or
    any(row["exit"] != row["expected_exit"] for row in records)))
