# PyInstaller specification (Bauplan §37.2, §38).
#
# One folder, not one file: a single executable unpacks itself on every start,
# and with VTK and Qt in it that is seconds the user waits for nothing.
#
# What is deliberately **not** bundled (§36, §38): OpenSCAD and the slicers are
# GPL and are only ever called; Ollama and ComfyUI are configured. The
# application checks for all four at start and says which are missing.
#
#     pyinstaller packaging/formwerk.spec

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).resolve().parent

datas = [
    (str(ROOT / "app" / "core" / "knowledge" / "data"), "app/core/knowledge/data"),
    (str(ROOT / "app" / "core" / "knowledge" / "parts" / "LICENSE"), "app/core/knowledge/parts"),
    (str(ROOT / "app" / "core" / "backends" / "data"), "app/core/backends/data"),
    (str(ROOT / "app" / "i18n" / "locales"), "app/i18n/locales"),
    (str(ROOT / "app" / "examples"), "app/examples"),
    (str(ROOT / "LICENSE"), "."),
    (str(ROOT / "THIRD-PARTY-NOTICES.md"), "."),
]
# trimesh and pyvista read data files of their own at import time.
datas += collect_data_files("trimesh")
datas += collect_data_files("pyvista")

hiddenimports = [
    # The operations register themselves on import (§10); PyInstaller cannot see
    # an import that only happens through a string in the bootstrap.
    *collect_submodules("app.core.geom"),
    *collect_submodules("app.core.knowledge.parts"),
    *collect_submodules("app.core.scene"),
    *collect_submodules("app.core.ingest"),
    "vtkmodules.all",
    "vtkmodules.util.data_model",
    "vtkmodules.util.execution_model",
]

analysis = Analysis(
    [str(ROOT / "app" / "ui" / "app.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    excludes=["tkinter", "pytest", "mypy", "ruff"],
    noarchive=False,
)
pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="Formwerk",
    console=False,
    icon=None,
    # Signing happens after the build, in the CI (§37.2). Doing it here would
    # need the certificate on every developer machine.
)

collected = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    name="Formwerk",
)
