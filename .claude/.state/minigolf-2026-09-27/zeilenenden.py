"""Einmalig: CRLF aus eigenen Ersetzungen zurück auf LF, Steuerzeichen im Pfad heilen.

Aufruf: python zeilenenden.py <arbeitsbaum>
"""

import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
LF_FILES = [
    "app/core/geom/orient.py",
    "app/core/geom/prepare_ops.py",
    "app/core/slice/orientation.py",
    "tests/test_advise.py",
    "tests/test_orient.py",
]
for name in LF_FILES:
    path = ROOT / name
    data = path.read_bytes()
    fixed = data.replace(b"\r\n", b"\n")
    path.write_bytes(fixed)
    print(f"{name}: CRLF {data.count(b'\r\n')} -> {fixed.count(b'\r\n')}")

rule = ROOT / ".claude" / "rules" / "schichtanalyse.md"
text = rule.read_text(encoding="utf-8")
broken = "F:\x03D Dateien\\Mini+Golf+All+Set-P1S_stls"
healed = "F:\\3D Dateien\\Mini+Golf+All+Set-P1S_stls"
assert text.count(broken) == 1, text.count(broken)
text = text.replace(broken, healed)
assert not any(ord(c) < 32 and c not in "\n\t" for c in text), "noch ein Steuerzeichen"
rule.write_bytes(text.encode("utf-8"))
print("Regel geheilt")
