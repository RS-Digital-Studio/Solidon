"""Wie viele Byte Unterlagen app/ui/main_window.py nachzieht — je Baum."""

import sys
from pathlib import Path

tree = Path(sys.argv[1])
sys.path.insert(0, str(tree / "tools"))
sys.path.insert(0, str(tree))
import docs_scan  # noqa: E402

docs_scan.ROOT = tree
rules = {
    rule: set().union(*(docs_scan.matched(pattern) for pattern in docs_scan.scopes(rule)))
    for rule in docs_scan.rule_files()
}
source = tree / "app" / "ui" / "main_window.py"
loaded, kb = docs_scan.load_for(source, rules)
total = sum(path.stat().st_size for path in loaded)
print("KB", kb, "Byte", total, "Grenze", 160 * 1024, "frei", 160 * 1024 - total)
for path in loaded:
    print(f"  {path.stat().st_size:7d} {path.relative_to(tree)}")
