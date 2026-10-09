"""Startet die CI-Auswahl für einen Zweig: python ci_start.py <zweig>."""
import subprocess
import sys

zweig = sys.argv[1]
ausgabe = subprocess.run(
    [sys.executable, "F:/3D Druck/tools/ci_selection.py", "--diff", f"origin/main...{zweig}"],
    capture_output=True, text=True, encoding="utf-8", check=True,
).stdout
listen = {}
for zeile in ausgabe.splitlines():
    for art in ("fenster", "slicer"):
        if zeile.startswith(art + ": "):
            listen[art] = zeile[len(art) + 2:]
for art, workflow in (("fenster", "fenster-auswahl.yml"), ("slicer", "slicer-auswahl.yml")):
    if not listen.get(art):
        print(art, "leer")
        continue
    lauf = subprocess.run(
        ["gh", "workflow", "run", workflow, "--ref", zweig, "-f", f"tests={listen[art]}"],
        capture_output=True, text=True, encoding="utf-8",
    )
    print(art, lauf.returncode, lauf.stdout.strip(), lauf.stderr.strip())
