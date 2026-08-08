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
#     pyinstaller packaging/solidon3d.spec

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).resolve().parent

# V4c (Konzept §2 I H4/H5): das Prüfmodul reist kompiliert, das Manifest
# signiert. Beides baut tools/build_licence_module.py — ohne den Schritt gibt
# es keinen Bau, sonst entstünde ein Paket, in dem die Lizenzgrenze als
# dekompilierbarer Bytecode läge.
LICENCE_BUILD = ROOT / "packaging" / "build"
if not (LICENCE_BUILD / "licence.manifest").is_file() or not list(
    (LICENCE_BUILD / "activation").glob("*")
):
    raise SystemExit(
        "Das kompilierte Prüfmodul fehlt — erst: python tools/build_licence_module.py"
    )

datas = [
    # Neben app/, wo integrity.manifest_path() es sucht.
    (str(LICENCE_BUILD / "licence.manifest"), "."),
    (str(ROOT / "app" / "core" / "knowledge" / "data"), "app/core/knowledge/data"),
    (str(ROOT / "app" / "core" / "knowledge" / "parts" / "LICENSE"), "app/core/knowledge/parts"),
    (str(ROOT / "app" / "core" / "backends" / "data"), "app/core/backends/data"),
    (str(ROOT / "app" / "i18n" / "locales"), "app/i18n/locales"),
    (str(ROOT / "app" / "examples"), "app/examples"),
    # Das Fenster rastert sein Symbol zur Laufzeit aus der SVG-Quelle.
    (str(ROOT / "app" / "images" / "icon"), "app/images/icon"),
    (str(ROOT / "LICENSE"), "."),
    (str(ROOT / "THIRD-PARTY-NOTICES.md"), "."),
]
# trimesh und pyvista lesen beim Import eigene Datendateien.
datas += collect_data_files("trimesh")
datas += collect_data_files("pyvista")

binaries = [
    # Die kompilierten Erweiterungen des Prüfmoduls, an der Stelle des
    # Python-Pakets. Der Import findet sie über den Paketpfad im
    # Dateisystem; im PYZ liegt von app.core.activation nichts (H5).
    (str(entry), "app/core/activation")
    for entry in sorted((LICENCE_BUILD / "activation").glob("*"))
]

hiddenimports = [
    # Die Operationen registrieren sich beim Import selbst (§10); PyInstaller
    # sieht keinen Import, der nur über eine Zeichenkette im Bootstrap
    # passiert. Eingesammelt wird der **ganze** eigene Kern: die
    # handgepflegte Teilmenge, die hier stand, ist mit dem Bootstrap
    # auseinandergedriftet — die Skizzen-Ops fehlten, und der Bau endete
    # beim Start mit einem ModuleNotFoundError statt eines Fensters.
    # Ausgenommen ist das Prüfmodul: das reist kompiliert (oben) und darf
    # nicht zusätzlich als Bytecode ins Archiv.
    *[
        name
        for name in collect_submodules("app.core")
        if name != "app.core.activation" and not name.startswith("app.core.activation.")
    ],
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
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    # app.core.activation: siehe oben — kompiliert statt Bytecode (H5).
    excludes=["tkinter", "pytest", "mypy", "ruff", "app.core.activation"],
    # Die vier Grenzdateien aus §2 C reisen als Quelltext, nicht im Archiv:
    # integrity.intact() hasht genau die Datei, aus der Python sie lädt —
    # ein von Hand verändertes writer.py im Paket fällt damit auf (H4).
    module_collection_mode={
        "app.core.scene.history": "py",
        "app.core.export.writer": "py",
        "app.core.export.handover": "py",
        "app.core.agent.session": "py",
    },
    noarchive=False,
)
pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="Solidon",
    console=False,
    # Erzeugt von tools/make_icon.py aus app/images/icon/solidon3d.svg.
    icon=str(ROOT / "packaging" / "solidon3d.ico"),
    # Signiert wird nach dem Bauen, in der CI (§37.2). Hier stünde sonst das
    # Zertifikat auf jeder Entwicklermaschine.
)

collected = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    name="Solidon",
)
