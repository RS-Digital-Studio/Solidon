# Release-Lizenzakte

`third_party_licenses.toml` ist der freigegebene Katalog. Die eigentliche
Release-Akte entsteht erst aus dem fertigen Kundenartefakt:

```text
python tools/make_licence_notices.py --sbom <artefakt>/Solidon3D.cdx.json \
  --output <artefakt>/THIRD-PARTY-NOTICES.md \
  --manifest <akte>/third-party-licenses.json

python tools/make_licence_notices.py --release-check \
  --artifact-root <artefakt> \
  --sbom <artefakt>/Solidon3D.cdx.json \
  --release-evidence <akte>/release-evidence.json
```

Der zweite Lauf ist ein Release-Tor. Er verlangt:

- jede native Datei genau einmal in der Endartefakt-SBOM und mit bekanntem
  Besitzer;
- jede SBOM-Bibliothek mit identischer Version in der Lizenzbeilage;
- exakt eine aus dieser SBOM erzeugte `THIRD-PARTY-NOTICES.md`;
- gehashte äußere Pakete (`windows-installer`, `appimage` und `flatpak` oder
  `macos-installer`);
- für Qt, OCCT und GEOS je ein von RS Digital verwahrtes Quellarchiv sowie
  gehashtes Austausch-/Relink-Material, Kontakt und Bereitstellung bis
  mindestens drei Jahre nach Freigabe.

Die Evidenzdatei hat Schema 1. Alle Dateipfade sind relativ zu ihrer Ablage:

```json
{
  "schema": 1,
  "product_version": "0.3.0",
  "target": "win-amd64",
  "release_date": "2026-08-31",
  "packages": [
    {
      "kind": "windows-installer",
      "path": "packages/Solidon3D-Setup.exe",
      "path_sha256": "<sha256>"
    }
  ],
  "source_provisions": [
    {
      "component_id": "qt",
      "version": "6.11.2",
      "issuer": "RS Digital",
      "contact": "<überwachte Adresse>",
      "method": "archive",
      "source_archive": "sources/qt-6.11.2.tar.xz",
      "source_archive_sha256": "<sha256>",
      "relink_material": "sources/qt-6.11.2-relink.zip",
      "relink_material_sha256": "<sha256>",
      "available_until": "<ISO-Datum>"
    }
  ]
}
```

Ein URL-Hinweis ersetzt kein verwahrtes Archiv. `method = "written-offer"`
ändert nur die Auslieferungsform; auch dann muss das angebotene Archiv beim
Release vorhanden und gehasht sein.

## Noch zwingend im Paketbau zu liefern

Der AppImage-Type-2-Runtime wird dem AppImage vorangestellt und gehört deshalb
zum ausgelieferten Binärbestand. Seine eigene Lizenzakte nennt statisch
eingebettete Fremdteile, darunter libfuse. Der derzeitige SBOM-Erzeuger sieht
diesen äußeren Runtime-Block noch nicht. Linux bleibt deshalb absichtlich rot,
bis die Endartefakt-SBOM den Runtime `20251108` samt exakten Versionen seiner
statisch eingebundenen Bestandteile ausweist und das vollständige zugehörige
Quellarchiv belegt ist.

Ebenso akzeptiert das Tor für libffi nur eine exakte Version, nicht bloß eine
ABI-Nummer, und für GCC-/MSVC-Runtimes nicht nur die Compilerangabe. Diese
Versionen müssen aus den fertigen Binärdateien oder einer gehashten
Build-Provenienz in die SBOM übernommen werden.

Primärgrundlagen: [LGPL 3.0 §4](https://www.gnu.org/licenses/lgpl-3.0.html),
[LGPL 2.1 §§4–6](https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html),
[OCCT-Lizenz und Ausnahme](https://occt3d.com/dev/doc/overview/html/occt_public_license.html),
[PyInstaller-Lizenz 6.22.2](https://github.com/pyinstaller/pyinstaller/blob/v6.22.2/COPYING.txt)
und [AppImage-Type-2-Runtime `dd6cebe`](https://github.com/AppImage/type2-runtime/tree/dd6cebe).
