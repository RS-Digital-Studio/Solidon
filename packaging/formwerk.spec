# PyInstaller-Spezifikation (Bauplan §37.2, §38).
#
# Ein Ordner, keine Ein-Datei-Anwendung: eine einzelne ausführbare Datei packt
# sich bei jedem Start selbst aus, und mit VTK und Qt darin sind das Sekunden,
# in denen der Nutzer auf nichts wartet.
#
# Was absichtlich **nicht** mitreist (§36, §38): OpenSCAD und die Slicer sind
# GPL und werden nur aufgerufen; Ollama und ComfyUI werden angegeben. Die
# Anwendung prüft alle vier beim Start und sagt, was fehlt.
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
# trimesh und pyvista lesen beim Import eigene Datendateien.
datas += collect_data_files("trimesh")
datas += collect_data_files("pyvista")

hiddenimports = [
    # Die Operationen registrieren sich beim Import selbst (§10); PyInstaller
    # sieht keinen Import, der nur über eine Zeichenkette im Bootstrap
    # passiert. Eingesammelt wird der **ganze** eigene Kern: die
    # handgepflegte Teilmenge, die hier stand, ist mit dem Bootstrap
    # auseinandergedriftet — die Skizzen-Ops fehlten, und der Bau endete
    # beim Start mit einem ModuleNotFoundError statt eines Fensters.
    *collect_submodules("app.core"),
    "vtkmodules.all",
    "vtkmodules.util.data_model",
    "vtkmodules.util.execution_model",
    # Die optionalen Kerne werden innerhalb von Funktionen importiert, damit
    # die Anwendung ohne sie startet (§30, §22.3). PyInstaller sieht nur
    # Importe auf Modulebene, also stehen sie hier — ein paketierter Build
    # kann nichts nachinstallieren, und einer, dem stillschweigend die
    # Verrundungen fehlen, ist schlimmer als ein großer.
    "OCP.BRepPrimAPI",
    "OCP.BRepFilletAPI",
    "OCP.BRepAlgoAPI",
    "OCP.BRepBuilderAPI",
    "OCP.BRepAdaptor",
    "OCP.BRepGProp",
    "OCP.BRepMesh",
    "OCP.STEPControl",
    "OCP.Interface",
    "OCP.IFSelect",
    "OCP.GeomAbs",
    "OCP.Message",
    "vhacdx",
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
    # Signiert wird nach dem Bauen, in der CI (§37.2). Hier stünde sonst das
    # Zertifikat auf jeder Entwicklermaschine.
)

collected = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    name="Formwerk",
)
