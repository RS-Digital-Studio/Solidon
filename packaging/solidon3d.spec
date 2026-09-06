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

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

ROOT = Path(SPECPATH).resolve().parent

# Der Name kommt aus app/branding.py und nirgends sonst (§37.1). Er stand hier
# als „Solidon" fest und überlebte damit die Umbenennung auf „Solidon3D“:
# PyInstaller baute nach dist/Solidon, tools/make_installer.py suchte unter
# dist/Solidon3D — und fand nichts. Die Setup-Datei ließ sich nicht bauen, und
# im Installer zeigten Startmenüeintrag und Deinstallationssymbol auf eine
# Solidon3D.exe, die es nicht gab.
sys.path.insert(0, str(ROOT))
from app.branding import APP_ID, APP_NAME, APP_VERSION, COPYRIGHT, PROJECT_SUFFIX  # noqa: E402
from app.branding import PART_FILE_MIME_TYPE, PART_FILE_SUFFIX  # noqa: E402
from tools import asset_rights, build_slice_core, make_linux_packages, make_sbom  # noqa: E402

# Bilder, Symbole und Schriften sind Teil des Kundenpakets und brauchen vor
# PyInstaller dieselbe Freigabe auf allen drei Zielsystemen. Website-only-
# Sperren gehören nicht hierher; eine Anwendungssperre beendet den Bau mit dem
# konkreten Nachweis, statt das Medium still wegzulassen.
try:
    asset_rights.require_application_assets_cleared(sys.platform)
except RuntimeError as problem:
    raise SystemExit(str(problem)) from problem

# Windows will ein ICO, macOS ein ICNS. Beide entstehen aus derselben SVG-
# Quelle in tools/make_icon.py und liegen daneben — hier wird nur gewählt.
ICON = ROOT / "packaging" / ("solidon3d.icns" if sys.platform == "darwin" else "solidon3d.ico")

# V4c (Konzept §2 I H4/H5): das Prüfmodul reist kompiliert, das Manifest
# signiert. Beides baut tools/build_licence_module.py — ohne den Schritt gibt
# es keinen Bau, sonst entstünde ein Paket, in dem die Lizenzgrenze als
# dekompilierbarer Bytecode läge.
LICENCE_BUILD = ROOT / "packaging" / "build"
if not (LICENCE_BUILD / "licence.manifest").is_file() or not list(
    (LICENCE_BUILD / "activation").glob("*")
):
    raise SystemExit("Das kompilierte Prüfmodul fehlt — erst: python tools/build_licence_module.py")

# Die schnelle Schichtanalyse aus §31 ist kein optionaler Paketinhalt. Im
# Quellbaum darf sie fehlen und fällt dann ehrlich auf GEOS zurück; ein
# Kundenpaket wird dagegen nur gebaut, wenn der plattformeigene Rechenkern aus
# dem unmittelbar vorherigen CI-Schritt wirklich da ist.
SLICE_CORE = build_slice_core.current_extensions()
if not SLICE_CORE:
    raise SystemExit("Der schnelle Schichtkern fehlt — erst: python tools/build_slice_core.py")

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
    # Die Bildschirmfotos des Handbuchs, je Sprache ein Ordner. Ohne sie öffnet
    # F1 ein Handbuch, in dem an jeder Abbildung eine Lücke steht:
    # `figures.IMAGE_ROOT` zeigt hierher, und `ManualView._image` gibt für eine
    # fehlende Datei stillschweigend nichts zurück.
    (str(ROOT / "app" / "images" / "manual"), "app/images/manual"),
    # Der Verlauf für *Hilfe → Neuerungen*, je Sprache eine Datei. Neben das
    # ``app``-Paket, wo ``core.changes.folder()`` zuerst nachsieht: Bis 0.1.3
    # kannte die Anwendung ihn nur aus der Versionsdatei vom Server — also erst
    # beim nächsten Update und nie für die eigene Fassung.
    (str(ROOT / "changelog"), "app/changelog"),
    (str(ROOT / "LICENSE"), "."),
    # Der KI-Hinweis öffnet diese Fassung lokal im Fenster, ohne Webabruf.
    (str(ROOT / "DATENSCHUTZ.md"), "."),
]
# trimesh liest beim Import eigene Datendateien.
datas += collect_data_files("trimesh")
# OpenSSLs Vorgabepfad zeigt im macOS-Paket auf den Bauserver. Die Anwendung
# setzt dort ``SSL_CERT_FILE`` auf certifis CA-Satz; ohne dessen Datendatei
# wäre der richtige Pfad im Quellcode trotzdem eine Lücke im Paket.
datas += collect_data_files("certifi")

# **Die Paketbeschreibungen von manifold3d und trimesh.** Ein Fehlerbericht
# nennt die Fassung jeder tragenden Bibliothek, und ``report.environment`` fragt
# zuerst das Modul (``__version__``) und erst dann die Metadaten. Ohne die
# ``.dist-info`` stand im Bericht eines Kunden vom 27.08.2026 schlicht ein
# Strich — die reisen in einem PyInstaller-Bau nicht von selbst mit.
#
# **Zwei der sechs kommen ohne diese Zeilen nicht durch**, und der zweite ist
# der unauffälligere: ``manifold3d`` hat gar kein ``__version__``, und
# ``trimesh.__version__`` ist selbst ein Metadatenaufruf — ``version.py`` ruft
# ``importlib.metadata.version("trimesh")`` und gibt ohne sie ``None`` zurück.
#
# Hier stand bis zum 27.08.2026, ``trimesh`` und ``numpy`` bekämen ihre
# Metadaten nebenbei, weil ``collect_data_files`` sie mitnehme. **Gemessen ist
# das falsch:** ``collect_data_files("trimesh")`` liefert 24 Einträge und
# ``collect_data_files("numpy")`` 495, davon **null** mit ``dist-info`` — die
# Funktion sammelt ausschließlich Dateien *innerhalb* des Paketverzeichnisses.
# ``numpy`` steht trotzdem im Bericht, aber aus einem anderen Grund: Es trägt
# sein ``__version__`` wirklich selbst.
#
# Ein Fehlerbericht, der „nicht installiert" sagt, wo eine Bibliothek läuft, ist
# schlimmer als einer ohne die Zeile: Er schickt die Diagnose an eine Stelle, an
# der nichts ist. Ein paar Kilobyte gegen eine falsche Fährte.
datas += copy_metadata("manifold3d")
datas += copy_metadata("trimesh")

# **Qts eigene Sprachkataloge.** Die Standardknöpfe beschriftet Qt aus
# ``qtbase_<sprache>.qm``, nicht aus unserem Katalog; ``install_qt_translations``
# lädt sie über ``QLibraryInfo.TranslationsPath``. In der Entwicklungsumgebung
# liegen sie neben PySide6 und alle sechs laden — im Paket hängt es daran, ob
# PyInstallers Hook sie von selbst einsammelt. Tut er es nicht, steht auf jedem
# zweiten Dialog „Cancel" statt „Abbrechen", und zwar nur im gebauten Programm.
# Ausdrücklich mitgenommen sind es ein paar hundert Kilobyte und eine Frage
# weniger.
#
# Nur die Sprachen, die es gibt, und die Liste wird nicht gepflegt: sie kommt
# aus dem Verzeichnis der Kataloge, wie überall sonst (§4.1). **Deutsch steht
# dazu**, denn es ist die Quellsprache und hat dort keine Datei — ausgerechnet
# die Vorgabe hätte englische Knöpfe getragen.
import PySide6  # noqa: E402

_QT_TRANSLATIONS = Path(PySide6.__file__).parent / "translations"
_LANGUAGES = {"de"} | {path.stem for path in (ROOT / "app" / "i18n" / "locales").glob("*.json")}
for _code in sorted(_LANGUAGES):
    # Mit Varianten gesucht: Portugiesisch liegt bei Qt nur als ``pt_BR`` vor,
    # und ``QTranslator.load`` findet es von dort aus selbst. Wer stur
    # ``qtbase_pt.qm`` mitnimmt, nimmt nichts mit.
    _found = sorted(_QT_TRANSLATIONS.glob(f"qtbase_{_code}*.qm"))
    if _found:
        datas.extend((str(entry), "PySide6/translations") for entry in _found)
    else:
        print(f"Hinweis: Qt hat keinen Katalog für {_code} — Standardknöpfe bleiben englisch.")

binaries = [
    # Die kompilierten Erweiterungen des Prüfmoduls, an der Stelle des
    # Python-Pakets. Der Import findet sie über den Paketpfad im
    # Dateisystem; im PYZ liegt von app.core.activation nichts (H5).
    (str(entry), "app/core/activation")
    for entry in sorted((LICENCE_BUILD / "activation").glob("*"))
]
binaries += [(str(entry), "app/core/slice") for entry in SLICE_CORE]

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
    # die Anwendung ohne sie startet (§30, §22.3). Normale Funktionsimporte
    # findet PyInstallers Modulgraph; ausdrücklich stehen sie hier trotzdem
    # als Paketvertrag für optionale Kerne und dynamisch geladene Backends —
    # ein paketierter Build kann nichts nachinstallieren, und einer, dem
    # stillschweigend die Verrundungen fehlen, ist schlimmer als ein großer.
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
    # Die 3D-Maus liest über hidapi, importiert erst beim Öffnen des Geräts
    # (app/ui/spacemouse.py) — ein Bau ohne das Modul soll auffallen.
    "hid",
    # trimesh fragt xxhash in einem try/except am Modulkopf ab und fällt ohne
    # es still auf blake2b zurück — der Kunde merkt nur, dass jede Auswertung
    # großer Baugruppen langsamer ist. Der Modulgraph findet auch try-Importe;
    # ausdrücklich steht es hier aus demselben Grund wie die OCP-Zeilen: als
    # Paketvertrag, damit ein Bau ohne xxhash auffällt statt schleichend
    # langsam zu sein.
    "xxhash",
    # **Ohne diese Zeile konnte der Kunde seinen Schlüssel nicht ablegen.**
    # ``keyring`` wird in ``backends/keys.py`` innerhalb einer Funktion
    # importiert, PyInstaller sieht das nicht, und im gebauten Paket gab
    # ``keys.store()`` deshalb immer False zurück: Der Chat-Dialog nahm einen
    # Schlüssel an und behielt ihn nicht. Übrig blieb eine Umgebungsvariable,
    # gedacht für einen Bauserver. Die Liste der zusätzlichen Programme bot
    # daneben an, den Schlüsselbund zu installieren — mit einem Knopf, der in
    # einem Paket nicht drückbar ist.
    "keyring",
    # Die Hintertüren des Schlüsselbunds sucht er selbst über Einsprungpunkte;
    # die des Systems steht damit noch nicht im Archiv.
    "keyring.backends.Windows",
    "keyring.backends.macOS",
    "keyring.backends.SecretService",
]

analysis = Analysis(
    [str(ROOT / "app" / "ui" / "app.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    # app.core.activation: siehe oben — kompiliert statt Bytecode (H5).
    # Cython/setuptools bauen oben die beiden Prüfmodule. PyInstallers Cython-
    # Hook zieht sonst den vollständigen Compiler samt Buildwerkzeug in die
    # Anwendung, obwohl der fertige Maschinencode beides nicht importiert.
    excludes=[
        "tkinter",
        "pytest",
        "mypy",
        "ruff",
        "Cython",
        "cython",
        "pyximport",
        "setuptools",
        "app.core.activation",
        # Terminalmodule, die eine Fensteranwendung nie ruft — und ``readline``
        # zöge ``libreadline`` mit, GPL-3 (Regel 15), samt ncurses. Auf Linux
        # und macOS lagen beide im Kundenpaket, gemessen an der 0.2.1/0.2.2.
        "readline",
        "curses",
        "_curses",
        "_curses_panel",
    ],
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

# **Die gemeinsame Build-Grenze für jede Plattform.** Erst Analysis weiß,
# welche der installierten Laufzeitdistributionen im Kundenpaket liegen. Die
# Liste der Besitzer entsteht deshalb aus ihren tatsächlichen
# PYMODULE-/BINARY-/DATA-Einträgen. Die Stückliste selbst folgt erst nach dem
# fertigen Artefakt: Nur dort stehen auch CPython, Bootloader und jede wirklich
# mitgereiste native Datei fest. Ein ``pip freeze`` oder die gesamte
# deklarierte Umgebung wäre nur eine Prognose.
_included_distributions = make_sbom.distributions_for_analysis(
    [*analysis.pure, *analysis.binaries, *analysis.datas]
)

# Qt für Windows bindet an die ICU des Betriebssystems. PyInstaller sucht eine
# unversionierte ``icuuc.dll`` jedoch zusätzlich im ``PATH`` des Baurechners.
# Auf der Codex-Maschine fand es dort Popplers ICU 78, legte sie ins Paket und
# erzeugte einen Kundenbau, dessen erster Import von ``QtCore`` mit „Prozedur
# nicht gefunden“ endete. Die direkt gestartete PySide6-Installation lädt
# dagegen nachweislich ``C:\Windows\System32\icuuc.dll``. Darum darf der
# Windows-Bau weder diese fremde DLL noch ihre Datendatei übernehmen.
if sys.platform == "win32":
    analysis.binaries = [
        binary
        for binary in analysis.binaries
        if not (
            (name := Path(binary[0]).name.lower()) == "icuuc.dll"
            or (name.startswith("icudt") and name.endswith(".dll"))
        )
    ]

# Linux: Das GTK-3-Erscheinungsbild von Qt und die Bibliotheken, die jedes
# Linux mit einem Fenster selbst hat, bleiben draußen — welche und warum, steht
# an der Liste in ``make_linux_packages``. Was bleibt, inventarisiert
# ``make_sbom`` je Familie; eine fremde Datei ohne Besitzer lässt die
# Releaseakte nicht durch.
if sys.platform.startswith("linux"):
    analysis.binaries = make_linux_packages.trim_linux_binaries(analysis.binaries)

pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    console=False,
    # Erzeugt von tools/make_icon.py aus app/images/icon/solidon3d.svg.
    icon=str(ICON),
    # Signiert wird nach dem Bauen, in der CI (§37.2). Hier stünde sonst das
    # Zertifikat auf jeder Entwicklermaschine.
)

collected = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    name=APP_NAME,
)

# Auf macOS ist ein Ordner keine Anwendung. Was der Finder startet, was im Dock
# steht und was Gatekeeper überhaupt prüfen kann, ist ein .app-Bundle; COLLECT
# allein füllt nur den Ordner, den BUNDLE dann umschließt. Ohne diesen Schritt
# entstünde auf dem Mac zwar ein lauffähiges Programm, aber keines, das sich
# per Doppelklick starten oder in den Programme-Ordner ziehen ließe.
if sys.platform == "darwin":
    bundle = BUNDLE(  # noqa: F821  (von PyInstaller bereitgestellt)
        collected,
        name=f"{APP_NAME}.app",
        icon=str(ICON),
        bundle_identifier=APP_ID,
        version=APP_VERSION,
        info_plist={
            "CFBundleShortVersionString": APP_VERSION,
            "NSHumanReadableCopyright": COPYRIGHT,
            # Fehlt das, rendert Qt auf einem Retina-Bildschirm in halber
            # Auflösung und das Fenster sieht unscharf aus — eine Ursache,
            # die niemand in einer Plist sucht.
            "NSHighResolutionCapable": True,
            # Die älteste Version, auf der die mitgelieferten Qt-Räder laufen.
            "LSMinimumSystemVersion": "13.0",
            # Die eigene Projektdatei, damit ein Doppelklick im Finder hier
            # ankommt. Zwei Einträge, und beide werden gebraucht: die
            # Deklaration sagt dem System, dass es den Typ überhaupt gibt und
            # woran es ihn erkennt (an der Endung), der Dokumenttyp sagt, dass
            # diese Anwendung ihn öffnet. Ohne die Deklaration kennt macOS die
            # Endung nicht und ordnet sie niemandem zu.
            #
            # `LSHandlerRank: Owner` heißt: Wir sind der Eigentümer dieses
            # Typs, nicht ein Programm, das ihn auch lesen kann.
            #
            # Abgeholt wird das Ereignis in app/ui/app.py (`FileOpenListener`)
            # — auf dem Mac kommt der Pfad nicht über argv, und ohne den
            # Filter wäre dieser Eintrag ein Versprechen ohne Wirkung.
            "CFBundleDocumentTypes": [
                {
                    "CFBundleTypeName": f"{APP_NAME} project",
                    "CFBundleTypeRole": "Editor",
                    "LSHandlerRank": "Owner",
                    "LSItemContentTypes": [f"{APP_ID}.project"],
                },
                {
                    "CFBundleTypeName": f"{APP_NAME} part",
                    "CFBundleTypeRole": "Editor",
                    "LSHandlerRank": "Owner",
                    "LSItemContentTypes": [f"{APP_ID}.part"],
                },
            ],
            "UTExportedTypeDeclarations": [
                {
                    "UTTypeIdentifier": f"{APP_ID}.project",
                    "UTTypeDescription": f"{APP_NAME} project",
                    # Eine Projektdatei ist ein ZIP-Archiv mit JSON darin
                    # (§16.1) — das gehört hier gesagt, sonst hält der Finder
                    # sie für ein Archiv und bietet „Öffnen mit Archivierungs-
                    # programm" an.
                    "UTTypeConformsTo": ["public.data", "public.zip-archive"],
                    "UTTypeTagSpecification": {
                        "public.filename-extension": [PROJECT_SUFFIX.lstrip(".")]
                    },
                },
                {
                    "UTTypeIdentifier": f"{APP_ID}.part",
                    "UTTypeDescription": f"{APP_NAME} part",
                    "UTTypeConformsTo": ["public.data", "public.json"],
                    "UTTypeTagSpecification": {
                        "public.filename-extension": [PART_FILE_SUFFIX.lstrip(".")],
                        "public.mime-type": PART_FILE_MIME_TYPE,
                    },
                },
            ],
        },
    )

# **Jetzt** existiert das Kundenartefakt. Auf Windows/Linux ist es der
# COLLECT-Ordner, auf macOS die .app nach BUNDLE. Die Datei wird direkt dort
# geschrieben und inventarisiert dadurch nicht nur importierte Distributionen,
# sondern jede tatsächlich mitgereiste PE-/ELF-/Mach-O-Datei. Signiert wird in
# der CI erst danach; deshalb reist genau diese eine Stückliste mit.
_artifact = Path(DISTPATH) / (f"{APP_NAME}.app" if sys.platform == "darwin" else APP_NAME)
_sbom_folder = (
    _artifact / "Contents" / "Resources" if sys.platform == "darwin" else _artifact / "_internal"
)
_sbom = make_sbom.write_bom(
    _sbom_folder / "Solidon3D.cdx.json",
    included_distributions=_included_distributions,
    customer_artifact=_artifact,
)
print(
    f"Laufzeit-Stückliste: {len(_sbom['components'])} Komponenten aus dem fertigen Kundenartefakt"
)

# Der Quellbaum war vor Analysis freigegeben; dieser zweite Beleg bindet die
# Freigabe an die tatsächlich kopierten Medienbytes und an genau diese Spec.
# Die nachfolgenden Installerwerkzeuge lehnen einen alten oder nachträglich
# veränderten dist-Ordner ab.
_rights_receipt = asset_rights.write_customer_artifact_receipt(_artifact, sys.platform)
print(f"Rechtebeleg im Kundenartefakt: {_rights_receipt.relative_to(_artifact)}")
