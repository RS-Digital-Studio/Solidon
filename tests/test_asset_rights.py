"""Rechtenachweis der ausgelieferten Medien und Beispielprojekte."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import tomllib
from pathlib import Path
from typing import Any
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "ASSET-RIGHTS.toml"
DELIVERY_ROOTS = ("app/images/", "app/examples/", "packaging/", "website/")
DELIVERED_SUFFIXES = {
    ".gif",
    ".icns",
    ".ico",
    ".jpeg",
    ".jpg",
    ".mp3",
    ".mp4",
    ".ogg",
    ".otf",
    ".png",
    ".p3d",
    ".svg",
    ".ttf",
    ".wav",
    ".webm",
    ".webp",
    ".woff2",
}
REQUIRED_FIELDS = {
    "art",
    "creator",
    "rights_holder",
    "source",
    "license",
    "generator",
    "inputs",
    "derivative_status",
    "evidence",
    "redistribution_right",
    "platforms",
    "status",
}
EXAMPLE_STEMS = (
    "aushoehlen-und-teilen",
    "dose-mit-deckel",
    "drucker-kalibrieren",
    "gehaeuse-mit-bausteinen",
    "passung-nach-materialwechsel",
    "schild-zweifarbig",
    "skizze-mit-massen",
    "weg1-halterung-anpassen",
    "weg2-halter-konstruieren",
    "weg3-generiert-aufbereiten",
    "weg4-figur-formen",
)
EXAMPLE_SOURCE_INGEST = {
    "components": 1,
    "removed_triangles": 0,
    "scale": 1.0,
    "unit": "mm",
    "welded": False,
}
EXAMPLE_SOURCE_POLICY: dict[str, dict[str, Any]] = {
    "weg1-halterung-anpassen": {
        "archive_path": "sources/plate_holes.stl",
        "corpus_path": "tests/data/meshes/plate_holes.stl",
        "size": 39884,
        "sha256": "b7f2232fa1538ea9b85dd4d1c8f5a5dc06e54be7e76801db42967cbfa621b01e",
        "type": "import",
    },
    "weg3-generiert-aufbereiten": {
        "archive_path": "sources/src_1/Figur.stl",
        "corpus_path": "tests/data/meshes/generated_figure.stl",
        "size": 168684,
        "sha256": "f5aa84dd37fd6719bf68b661876a64ecaac629968810f1bb228e33888a1fcf1b",
        "type": "generated",
        "origin": {
            "author": "scripted",
            "prompt": "eine kleine Figur",
            "retrieved": "2026-08-31",
            "seed": 7,
            "title": "Figur",
        },
    },
}
PLATFORMS = {"windows", "macos", "linux", "web"}
PATH_INPUT_ROOTS = ("app/", "packaging/", "tests/", "tools/", "website/")
STATUS = {"cleared", "distribution_blocked"}
REDISTRIBUTION = {
    "blocked",
    "confirmed_in_product",
    "confirmed_on_website",
    "confirmed_with_notice",
}
LICENSES = {
    "LicenseRef-Solidon-Examples",
    "LicenseRef-Solidon-Proprietary",
    "OFL-1.1",
}
DERIVATIVE_STATUS = {
    "derived_from_icon",
    "generated_from_mit_source",
    "generated_from_own_sources",
    "original",
    "third_party_unmodified",
}
ART_SUFFIXES = {
    "font": {".otf", ".ttf", ".woff2"},
    "icon": {".icns", ".ico", ".svg"},
    "image": {".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp"},
    "video": {".mp4", ".png", ".webm"},
    "audio": {".mp3", ".ogg", ".wav"},
    "project": {".p3d"},
}


def load_manifest() -> dict[str, Any]:
    """Das Rechteinventar aus seiner einzigen Quelle lesen."""

    with MANIFEST.open("rb") as handle:
        return tomllib.load(handle)


def tracked_delivered_assets() -> set[str]:
    """Alle vorhandenen Assets lesen, die Anwendung oder Website ausliefern."""

    delivered: set[str] = set()
    for prefix in DELIVERY_ROOTS:
        folder = ROOT / prefix
        for candidate in folder.rglob("*"):
            if not candidate.is_file():
                continue
            path = candidate.relative_to(ROOT).as_posix()
            if path.startswith("website/teile/"):
                continue
            suffix = candidate.suffix.lower()
            if suffix == ".p3d":
                if path.startswith("app/examples/"):
                    delivered.add(path)
            elif suffix in DELIVERED_SUFFIXES:
                delivered.add(path)
    return delivered


def matches(pattern: str, paths: set[str]) -> set[str]:
    """Git-Pfade gegen ein absichtlich einfaches Glob-Muster vergleichen."""

    return {path for path in paths if fnmatch.fnmatchcase(path, pattern)}


def record_paths(asset: dict[str, Any], paths: set[str]) -> set[str]:
    """Ein Pattern oder eine explizite fail-closed Pfadliste auflösen."""

    if "paths" in asset:
        return set(asset["paths"]) & paths
    return matches(asset["pattern"], paths)


def record_name(asset: dict[str, Any]) -> str:
    """Einen stabilen Namen für Befunde zu einem Rechteblock liefern."""

    if "paths" in asset:
        return ", ".join(asset["paths"])
    return asset["pattern"]


def test_manifest_has_complete_shape() -> None:
    """Jede Rechtekette trägt dieselben prüfbaren Angaben."""

    data = load_manifest()
    assert data["schema_version"] == 1
    assert data["delivery"]["scope"] == "copyright_and_redistribution"
    assert data["delivery"]["not_a_safety_approval"] is True
    assert data["delivery"]["application_platforms"] == [
        "windows",
        "macos",
        "linux",
    ]
    assert data["delivery"]["application_media_identical"] is True
    assert isinstance(data.get("asset"), list) and data["asset"]

    for index, asset in enumerate(data["asset"], start=1):
        missing = REQUIRED_FIELDS - asset.keys()
        assert not missing, f"Asset {index} ohne Pflichtfelder: {sorted(missing)}"
        selectors = {selector for selector in ("pattern", "paths") if selector in asset}
        assert len(selectors) == 1, (
            f"Asset {index} braucht genau eines von pattern oder paths: {sorted(selectors)}"
        )
        if "pattern" in asset:
            assert isinstance(asset["pattern"], str) and asset["pattern"].strip()
        else:
            assert isinstance(asset["paths"], list) and asset["paths"]
            assert len(asset["paths"]) == len(set(asset["paths"]))
            assert all(
                isinstance(path, str)
                and path.strip()
                and not any(marker in path for marker in "*?[")
                for path in asset["paths"]
            ), f"Asset {index}: paths muss ausschließlich exakte Pfade enthalten"
        for field in REQUIRED_FIELDS - {"inputs", "evidence", "platforms"}:
            assert isinstance(asset[field], str) and asset[field].strip(), (
                f"Asset {index}: {field} ist leer"
            )
        for field in ("inputs", "evidence", "platforms"):
            assert isinstance(asset[field], list) and asset[field], (
                f"Asset {index}: {field} ist keine gefüllte Liste"
            )
            assert all(isinstance(value, str) and value.strip() for value in asset[field]), (
                f"Asset {index}: {field} enthält einen leeren oder ungültigen Wert"
            )
        assert set(asset["platforms"]) <= PLATFORMS
        assert asset["status"] in STATUS
        assert asset["redistribution_right"] in REDISTRIBUTION
        assert asset["license"] in LICENSES
        assert asset["derivative_status"] in DERIVATIVE_STATUS
        if asset["status"] == "distribution_blocked":
            assert asset.get("blocker", "").strip(), (
                f"Asset {index}: Sperre ohne begründeten Blocker"
            )
            assert asset["redistribution_right"] == "blocked"
        else:
            assert "blocker" not in asset
            assert asset["redistribution_right"] != "blocked"
            assert "Unresolved" not in asset["license"]
            assert asset["rights_holder"] != "nicht abschließend geklärt"
            assert asset["generator"] == "none" or asset["generator"].endswith(".py")
            if asset["license"] == "LicenseRef-Solidon-Examples":
                assert "app/examples/LICENSE" in asset["evidence"]


def test_every_delivered_asset_has_exactly_one_rights_record() -> None:
    """Kein ausgeliefertes Asset bleibt ohne oder mit zwei Rechteketten."""

    data = load_manifest()
    assets = tracked_delivered_assets()
    assert assets, "Der Quellbaum enthält keine ausgelieferten Assets"

    owners: dict[str, list[str]] = {path: [] for path in assets}
    unused: list[str] = []
    for asset in data["asset"]:
        found = record_paths(asset, assets)
        if not found:
            unused.append(record_name(asset))
        for path in found:
            owners[path].append(record_name(asset))

    missing = sorted(path for path, patterns in owners.items() if not patterns)
    duplicate = {path: patterns for path, patterns in owners.items() if len(patterns) > 1}
    assert not missing, "Medien ohne Rechtekette:\n" + "\n".join(missing)
    assert not duplicate, "Medien mit mehreren Rechteketten:\n" + "\n".join(
        f"{path}: {patterns}" for path, patterns in sorted(duplicate.items())
    )
    assert not unused, "Leere Rechte-Pattern:\n" + "\n".join(unused)


def test_every_bundled_example_project_has_a_project_rights_record() -> None:
    """Nur elf festgelegte P3D/SVG-Paare sind ausdrücklich freigegeben."""

    expected_projects = {f"app/examples/{stem}.p3d" for stem in EXAMPLE_STEMS}
    expected_previews = {f"app/examples/{stem}.svg" for stem in EXAMPLE_STEMS}
    expected = expected_projects | expected_previews
    actual = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "app" / "examples").iterdir()
        if path.suffix.lower() in {".p3d", ".svg"}
    }
    delivered = {path for path in tracked_delivered_assets() if Path(path).suffix.lower() == ".p3d"}
    records = [
        asset
        for asset in load_manifest()["asset"]
        if asset["license"] == "LicenseRef-Solidon-Examples"
        and set(asset.get("paths", ())) & expected
    ]

    assert actual == expected, (
        "Die Nutzungsfreigabe und der Beispielbestand weichen voneinander ab:\n"
        f"unerwartet={sorted(actual - expected)}\nfehlend={sorted(expected - actual)}"
    )
    assert delivered == expected_projects
    assert len(records) == 2
    assert {asset["art"] for asset in records} == {"image", "project"}
    assert {path for asset in records for path in asset["paths"]} == expected
    for stem in EXAMPLE_STEMS:
        assert f"app/examples/{stem}.p3d" in actual
        assert f"app/examples/{stem}.svg" in actual


def test_bundled_example_sources_are_exact_rs_corpus_bytes() -> None:
    """Bekannte Namen dürfen keine fremde oder zusätzliche Geometrie einschleusen."""

    for stem in EXAMPLE_STEMS:
        policy = EXAMPLE_SOURCE_POLICY.get(stem)
        with ZipFile(ROOT / "app" / "examples" / f"{stem}.p3d") as archive:
            project = json.loads(archive.read("project.json"))
            sources = project["sources"]
            expected_members = {"project.json", "report.json"}
            members = archive.namelist()
            assert len(members) == len(set(members)), f"{stem} enthält doppelte ZIP-Einträge"

            if policy is None:
                assert sources == {}, f"{stem} enthält eine unerwartete Quelle"
                assert set(members) == expected_members
                continue

            expected_members.add(policy["archive_path"])
            assert set(members) == expected_members
            assert set(sources) == {"src_1"}
            source = sources["src_1"]
            expected_source = {
                "embedded": True,
                "ingest": EXAMPLE_SOURCE_INGEST,
                "path": policy["archive_path"],
                "sha256": policy["sha256"],
                "type": policy["type"],
            }
            if "origin" in policy:
                expected_source["origin"] = policy["origin"]
            assert source == expected_source

            embedded = archive.read(policy["archive_path"])
            corpus = (ROOT / policy["corpus_path"]).read_bytes()
            assert len(embedded) == policy["size"]
            assert hashlib.sha256(embedded).hexdigest() == policy["sha256"]
            assert embedded == corpus


def test_ui_catalog_documents_the_independent_rights_allowlist() -> None:
    """UI-Auswahl und Rechtefreigabe dürfen nicht dieselbe Positivliste sein."""

    module = (ROOT / "app" / "core" / "examples.py").read_text(encoding="utf-8")
    assert "rechtliche Positivliste" in module
    assert "ASSET-RIGHTS.toml" in module
    assert "app/examples/LICENSE" in module


def test_website_build_sources_are_excluded_from_upload_and_inventory() -> None:
    """Interne Website-Quellen reisen weder auf den Server noch ins Lieferinventar."""

    from tools import upload_website

    sources = sorted(path for path in (ROOT / "website" / "teile").rglob("*") if path.is_file())
    assert sources, "Die Website-Bauquellen fehlen"
    uploaded = [str(path.relative_to(ROOT)) for path in sources if upload_website.wanted(path)]
    delivered = sorted(
        path for path in tracked_delivered_assets() if path.startswith("website/teile/")
    )

    assert not uploaded, "Website-Bauquellen würden hochgeladen:\n" + "\n".join(uploaded)
    assert not delivered, "Website-Bauquellen stehen im Lieferinventar:\n" + "\n".join(delivered)


def test_example_projects_carry_their_limited_permission_in_every_package() -> None:
    """P3D, Vorschau und eigentumsschonende Nutzungsfreigabe reisen gemeinsam."""

    license_path = ROOT / "app" / "examples" / "LICENSE"
    assert license_path.is_file(), "app/examples/LICENSE mit Nutzungsfreigabe fehlt"
    license_text = license_path.read_text(encoding="utf-8")
    normalized_license_text = " ".join(license_text.split())
    for marker in (
        "RS Digital behält das Urheberrecht",
        "einfaches, nicht ausschließliches und zeitlich unbefristetes Nutzungsrecht",
        "entfällt nicht allein durch Ablauf der Demo",
        "gedruckte Gegenstände privat oder gewerblich nutzen und weitergeben",
        "unveränderten ursprünglichen `.p3d`-Projektdateien",
        "Eine bloße Umbenennung oder Formatumwandlung",
        "MIT-lizenzierten Referenzkorpus",
        "importierten Inhalte Dritter",
        "keine Aussage über Druckbarkeit, Festigkeit, Lebensmittelechtheit",
    ):
        assert marker in normalized_license_text, (
            f"app/examples/LICENSE ist unvollständig: {marker!r} fehlt"
        )
    assert "CC0" not in license_text
    assert "Creative Commons" not in license_text
    assert "`*.p3d`" not in license_text
    assert "`*.svg`" not in license_text
    for stem in EXAMPLE_STEMS:
        assert f"`{stem}`" in license_text

    with (ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)
    package_data = set(project["tool"]["setuptools"]["package-data"]["app"])
    expected = {"examples/*.p3d", "examples/*.svg", "examples/LICENSE"}
    assert expected <= package_data, f"Wheel-Paketdaten fehlen: {sorted(expected - package_data)}"

    spec = (ROOT / "packaging" / "solidon3d.spec").read_text(encoding="utf-8")
    assert '(str(ROOT / "app" / "examples"), "app/examples")' in spec
    for document in ("LICENSE", "EULA.md"):
        content = (ROOT / document).read_text(encoding="utf-8")
        required = 2 if document == "LICENSE" else 1
        assert content.count("app/examples/LICENSE") >= required, (
            f"{document} nennt den Vorrang der Beispiellizenz nicht vollständig"
        )
        assert "CC0" not in content, f"{document} gibt Beispiele ohne Entscheidung unter CC0 frei"


def test_rights_records_match_media_kind_and_platform() -> None:
    """Art und Plattform weichen nicht still vom getroffenen Bestand ab."""

    data = load_manifest()
    assets = tracked_delivered_assets()
    full_application_platforms = {"windows", "macos", "linux"}

    for asset in data["asset"]:
        found = record_paths(asset, assets)
        allowed_suffixes = ART_SUFFIXES[asset["art"]]
        wrong = sorted(path for path in found if Path(path).suffix.lower() not in allowed_suffixes)
        assert not wrong, f"{record_name(asset)} hat die falsche Medienart: {wrong}"

        if found and all(path.startswith(("app/images/", "app/examples/")) for path in found):
            assert set(asset["platforms"]) == full_application_platforms
        elif record_name(asset) == "packaging/solidon3d.ico":
            assert asset["platforms"] == ["windows"]
        elif record_name(asset) == "packaging/solidon3d.icns":
            assert asset["platforms"] == ["macos"]
        elif found and all(path.startswith("website/") for path in found):
            assert asset["platforms"] == ["web"]


def test_every_evidence_generator_and_file_input_exists() -> None:
    """Nachweise, Erzeuger und benannte Quelldateien sind auffindbar."""

    data = load_manifest()
    for asset in data["asset"]:
        generator = asset["generator"]
        if generator.endswith(".py"):
            assert (ROOT / generator).is_file(), f"Erzeuger fehlt: {generator}"

        for source in asset["inputs"]:
            if not source.startswith(PATH_INPUT_ROOTS):
                continue
            if any(marker in source for marker in "*?["):
                assert list(ROOT.glob(source)), f"Eingabe-Pattern ist leer: {source}"
            else:
                assert (ROOT / source).exists(), f"Eingabe fehlt: {source}"

        for evidence in asset["evidence"]:
            assert not evidence.startswith("git:"), (
                f"Nachweis {evidence} hängt von einer möglicherweise flachen Git-Historie ab"
            )
            assert (ROOT / evidence).exists(), f"Datei-Nachweis fehlt: {evidence}"


def test_published_pages_do_not_reference_distribution_blocked_media() -> None:
    """Keine veröffentlichte Seite verweist auf ein gesperrtes Medium."""

    data = load_manifest()
    assets = tracked_delivered_assets()
    website_sources = [
        path
        for path in (ROOT / "website").rglob("*")
        if path.is_file() and path.suffix.lower() in {".css", ".html", ".js"}
    ]
    references: list[str] = []
    for asset in data["asset"]:
        if asset["status"] != "distribution_blocked":
            continue
        blocked_media = record_paths(asset, assets)
        for document in website_sources:
            content = document.read_text(encoding="utf-8")
            for path in blocked_media:
                name = Path(path).name
                if name in content:
                    references.append(f"{document.relative_to(ROOT)} → {path}")

    assert not references, "Seiten verweisen auf gesperrte Medien:\n" + "\n".join(
        sorted(references)
    )


def test_asset_rights_have_no_release_blockers() -> None:
    """Ein Release enthält kein Asset mit ungeklärter Rechtekette."""

    blockers = [
        f"{record_name(asset)}: {asset['blocker']}"
        for asset in load_manifest()["asset"]
        if asset["status"] == "distribution_blocked"
    ]
    assert not blockers, "Ungeklärte Asset-Rechte sperren den Release:\n" + "\n".join(blockers)
