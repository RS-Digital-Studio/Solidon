"""Die kompilierte Auslieferung des Prüfmoduls (Konzept §2 I H4/H5, V4c).

Der echte Beweis ist der gebaute Ordner — der entsteht in der CI und wird in
V6 auf einem fremden Rechner geprüft. Was sich hier festhalten lässt, ist
alles, woran der Bau sonst stillschweigend vorbeidriften könnte: dass
Bauwerkzeug und Prüfung dasselbe Manifest sprechen, dass die Spec die vier
Grenzdateien als Quelltext einsammelt und das Prüfmodul aus dem Archiv hält,
und dass der CI-Lauf das Werkzeug vor dem Paketieren ruft.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core import activation
from app.core.activation import integrity, store
from tools.build_licence_module import PLACEHOLDER, stage_sources, write_manifest
from tools.make_licence_keys import public_key

ROOT = Path(__file__).parent.parent

#: Der erste Testvektor aus RFC 8032 — nur zum Signieren in dieser Datei.
TEST_SEED = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")


def test_the_build_tool_and_the_check_agree_on_the_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bau und Prüfung teilen sich Nutzlast und Ablageform — ein Manifest aus
    dem Werkzeug muss die Prüfung öffnen, sonst sperrte jeder Bau sich
    selbst."""
    target = tmp_path / "licence.manifest"
    write_manifest(target, TEST_SEED)

    monkeypatch.setattr(store, "user_config_dir", lambda: tmp_path)
    monkeypatch.setattr(integrity, "MANIFEST_PUBLIC_KEY", public_key(TEST_SEED))
    monkeypatch.setattr(integrity, "manifest_path", lambda: target)
    activation.forget_cache()
    try:
        assert integrity.intact()
        assert activation.state().in_trial
    finally:
        activation.forget_cache()


def test_a_reworded_manifest_from_the_tool_is_still_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Wer am abgelegten Manifest dreht, verliert die Signatur — auch wenn es
    aus dem eigenen Werkzeug kam."""
    target = tmp_path / "licence.manifest"
    write_manifest(target, TEST_SEED)
    data = json.loads(target.read_text(encoding="utf-8"))
    first = next(iter(data["files"]))
    data["files"][first] = "0" * 64
    target.write_text(json.dumps(data), encoding="utf-8")

    monkeypatch.setattr(integrity, "MANIFEST_PUBLIC_KEY", public_key(TEST_SEED))
    monkeypatch.setattr(integrity, "manifest_path", lambda: target)
    assert not integrity.intact()


def test_everything_the_manifest_covers_is_checked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """„Was es darüber hinaus deckt, wird mitgeprüft" — jetzt stimmt der Satz.

    Ein sauber signiertes Manifest, das eine fünfte Datei mit falscher
    Prüfsumme deckt, lief vorher durch: Geprüft wurden nur die vier
    Grenzdateien, und die Zusage im Kommentar war leer.
    """
    from tools.build_licence_module import sign

    files = dict(integrity.boundary_hashes())
    files["core/updates.py"] = "0" * 64
    manifest = {
        "files": files,
        "signature": sign(TEST_SEED, integrity.manifest_payload(files)).hex(),
    }
    target = tmp_path / "licence.manifest"
    target.write_text(json.dumps(manifest), encoding="utf-8")

    monkeypatch.setattr(integrity, "MANIFEST_PUBLIC_KEY", public_key(TEST_SEED))
    monkeypatch.setattr(integrity, "manifest_path", lambda: target)
    assert not integrity.intact(), "die fünfte Datei weicht ab — das muss sperren"


def test_staging_sets_the_build_key_and_refuses_without_the_placeholder(
    tmp_path: Path,
) -> None:
    """Der Bau-Schlüssel tritt an die Stelle des Platzhalters — fehlt die
    Stelle, bricht der Bau ab, statt ein ungeprüftes Manifest auszuliefern."""
    manifest_public = public_key(TEST_SEED)
    staging = tmp_path / "activation"
    stage_sources(staging, manifest_public)

    text = (staging / "integrity.py").read_text(encoding="utf-8")
    assert PLACEHOLDER not in text
    assert manifest_public.hex() in text
    assert sorted(entry.name for entry in staging.glob("*.py")) == sorted(
        entry.name for entry in (ROOT / "app" / "core" / "activation").glob("*.py")
    ), "jedes Modul des Prüfpakets reist mit — ein vergessenes bliebe Bytecode"

    # Verliert die Quelle die Platzhalter-Zeile, bricht der Bau ab — ein
    # Manifest, das niemand prüft, wäre schlimmer als keins. Nachgestellt an
    # einer Quelle, in der die Zeile schon ersetzt ist: der Staging-Ordner
    # von eben ist genau das.
    with pytest.raises(SystemExit):
        stage_sources(tmp_path / "second", manifest_public, source_dir=staging)


def test_the_spec_ships_the_boundary_files_as_source() -> None:
    """Die Spec und ``integrity.BOUNDARY_FILES`` nennen dieselben vier
    Dateien: nur was als Quelltext reist, hasht die Prüfung so, wie Python es
    lädt."""
    spec = (ROOT / "packaging" / "solidon3d.spec").read_text(encoding="utf-8")
    for name in integrity.BOUNDARY_FILES:
        module = "app." + name.removesuffix(".py").replace("/", ".")
        assert f'"{module}": "py"' in spec, f"{module} fehlt im module_collection_mode der Spec"


def test_the_spec_keeps_the_activation_bytecode_out() -> None:
    """H5: vom Prüfmodul liegt nichts im Archiv — es kommt kompiliert aus
    ``packaging/build`` und der Bau bricht ohne diesen Schritt ab."""
    spec = (ROOT / "packaging" / "solidon3d.spec").read_text(encoding="utf-8")
    assert '"app.core.activation"' in spec, "das Prüfmodul steht nicht in den excludes"
    assert "licence.manifest" in spec
    assert "build_licence_module.py" in spec, "die Spec nennt den Schritt, der vorher laufen muss"


def test_the_workflow_builds_the_licence_module_before_packaging() -> None:
    """Der CI-Lauf ruft das Bauwerkzeug, bevor PyInstaller packt — sonst
    scheitert der Bau erst am Abbruch in der Spec."""
    workflow = (ROOT / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
    tool = workflow.index("tools/build_licence_module.py")
    packaging = workflow.index("pyinstaller packaging/solidon3d.spec")
    assert tool < packaging


@pytest.mark.slow
def test_every_activation_module_translates_to_c(tmp_path: Path) -> None:
    """Cython muss jedes Modul des Prüfpakets schlucken — das ist der Teil
    des Baus, der ohne C-Compiler prüfbar ist, und der, an dem eine neue
    Sprachkonstruktion zuerst scheitern würde."""
    pytest.importorskip("Cython")
    from Cython.Build.Dependencies import cythonize
    from setuptools import Extension

    staging = tmp_path / "activation"
    stage_sources(staging, public_key(TEST_SEED))
    extensions = []
    for source in sorted(staging.glob("*.py")):
        stem = source.stem
        name = "app.core.activation" if stem == "__init__" else f"app.core.activation.{stem}"
        extensions.append(Extension(name, [str(source)]))

    cythonize(extensions, language_level=3, build_dir=str(tmp_path / "c"), quiet=True)

    translated = sorted(entry.name for entry in (tmp_path / "c").rglob("*.c"))
    expected = sorted(entry.name.replace(".py", ".c") for entry in staging.glob("*.py"))
    assert translated == expected
