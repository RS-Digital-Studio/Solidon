# Release-Lizenzakte

`third_party_licenses.toml` ist der freigegebene Katalog.

Eine Quelle mit Archiv-URL und `#Pfad` bezeichnet genau das Mitglied dieses
Versionsarchivs. Bei einem Lizenzkopf im Quelltext beschreibt der Eintrag,
welcher Kommentarmantel entfernt wurde; Lizenzwortlaut und Zuschreibungen
bleiben unverändert. Hashes verwenden die Zeilennormalisierung des Generators.

`versions` nennt die Fassungen, für die ein Text geprüft ist. Ohne `native`
ist das die Wheel-Version. Beschreibt der Text die eingebettete native
Bibliothek (HarfBuzz in `uharfbuzz`, FreeType in `freetype-py`, wgpu-native
in `wgpu`), nennt `native` deren Laufzeitfamilie, und `versions` zählt deren
Versionen, wie sie auch die Stückliste liest. Eine neue Wheel-Fassung mit
derselben Bibliothek braucht dann keinen Eintrag. `versions` des Textes und
der gleichnamigen `[[runtime]]`-Familie bleiben gleich
(`test_native_text_pins_and_runtime_families_name_the_same_versions`). Für eine
neue Bibliotheksfassung wird der Text an ihrem Tag geladen und verglichen:
Ist er gleich, kommt nur die Version dazu, sonst ein neuer Text mit Hash.

Die eigentliche Release-Akte entsteht erst aus dem fertigen Kundenartefakt:

```text
python tools/make_licence_notices.py --sbom <artefakt>/Solidon3D.cdx.json \
  --output <artefakt>/THIRD-PARTY-NOTICES.md \
  --manifest <akte>/third-party-licenses.json

python tools/make_licence_notices.py --release-check \
  --artifact-root <artefakt> \
  --sbom <artefakt>/Solidon3D.cdx.json \
  --release-evidence <akte>/release-evidence.json \
  [--artifact-kind appimage]
```

Der zweite Lauf ist ein Release-Tor. Er verlangt:

- jede native Datei genau einmal in der Endartefakt-SBOM und mit bekanntem
  Besitzer;
- jede SBOM-Bibliothek mit identischer Version in der Lizenzbeilage;
- exakt eine aus dieser SBOM erzeugte `THIRD-PARTY-NOTICES.md`;
- gehashte äußere Pakete (`windows-installer`, `appimage` und `flatpak` oder
  `macos-installer`);
- für jede Familie mit `source_delivery` (Qt, OCCT, GEOS, keyutils und im
  AppImage dessen Laufzeitkern) ein Quellenangebot von RS Digital mit Kontakt
  und Bereitstellung bis mindestens drei Jahre nach Freigabe — entweder
  `archive` mit gehashtem Quellarchiv und Austausch-/Relink-Material oder
  `written-offer` mit Angebotstext und Austauschweg;
- mit `--artifact-kind appimage` den vorangestellten Laufzeitkern in der
  Stückliste des AppImage-Inhalts, ohne diese Sorte seine Abwesenheit.

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

Ein URL-Hinweis ersetzt kein Quellenangebot. `written-offer` ist der Weg, den
`--write-evidence` schreibt und die CI nimmt; das Tor prüft dabei Text, Kontakt,
Frist und Austauschweg, ein genanntes Archiv zusätzlich mit Hash. **Ob RS
Digital die angebotenen Quellen zur Freigabe außerdem selbst verwahren muss,
entscheidet das Tor nicht** — hier stand bis zum 22.09.2026, es müsse so sein,
während die Prüfung es seit dem 02.09.2026 nicht verlangte. Das ist eine
Rechtsfrage (`/legal-review`), keine technische.

## Der Laufzeitkern des AppImage

Der AppImage-Type-2-Runtime wird dem AppImage vorangestellt und gehört deshalb
zum ausgelieferten Binärbestand, aber nie zum App-Baum.
`tools/make_linux_packages.py --appimage` schreibt deshalb im AppDir eine
eigene Stückliste und Beilage: den App-Baum und den Laufzeitkern `20251108`
(nur mit der geprüften Datei, `make_sbom.APPIMAGE_RUNTIME_SHA256`), samt der
statisch eingebundenen Bestandteile mit Version und Beleg
(`make_sbom.APPIMAGE_RUNTIME_STATIC`: libfuse, squashfuse, zstd, zlib, musl,
mimalloc) und ihren Texten im Katalog. Die Linux-Releaseakte packt das
AppImage aus und prüft diesen Inhalt mit `--artifact-kind appimage`, Archiv
und Flatpak ohne.

Außerdem akzeptiert das Tor für libffi nur eine exakte Version, nicht bloß eine
ABI-Nummer, und für GCC-/MSVC-Runtimes nicht nur die Compilerangabe. Diese
Versionen müssen aus den fertigen Binärdateien oder einer gehashten
Build-Provenienz in die SBOM übernommen werden.

Primärgrundlagen: [LGPL 3.0 §4](https://www.gnu.org/licenses/lgpl-3.0.html),
[LGPL 2.1 §§4–6](https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html),
[OCCT-Lizenz und Ausnahme](https://occt3d.com/dev/doc/overview/html/occt_public_license.html),
[PyInstaller-Lizenz 6.22.2](https://github.com/pyinstaller/pyinstaller/blob/v6.22.2/COPYING.txt),
[PyInstaller-Lizenz 6.22.3](https://github.com/pyinstaller/pyinstaller/blob/v6.22.3/COPYING.txt)
und [AppImage-Type-2-Runtime `dd6cebe`](https://github.com/AppImage/type2-runtime/tree/dd6cebe).

## Die beiden geprüften PyInstaller-Fassungen

Der festgeschriebene Paketbau verwendet weiterhin 6.22.2; der Lauf mit den
neuesten Abhängigkeiten darf zusätzlich die geprüfte Fassung 6.22.3 verwenden.
`notice_package = "pyinstaller"` liest den vollständigen Lizenztext aus dem
tatsächlich verwendeten Wheel. Der gemeinsame Repositorylink der Laufzeitfamilie
ersetzt nicht die folgenden genauen Quellenbelege:

| Fassung | Quellstand | Veröffentlichtes Quellarchiv | SHA-256 des Archivs |
|---|---|---|---|
| 6.22.2 | [Tag v6.22.2](https://github.com/pyinstaller/pyinstaller/tree/v6.22.2) | [PyPI-Quellarchiv](https://files.pythonhosted.org/packages/cc/2b/836d9def811c02522e0921d8b8cdf0c16b0545a216e97e71041758057859/pyinstaller-6.22.2.tar.gz) | `89b65a3ad07d9dd5832253e37bc45f31872d10d7f9d5c9fd0fdd6088a83829dd` |
| 6.22.3 | [Tag v6.22.3](https://github.com/pyinstaller/pyinstaller/tree/v6.22.3) | [PyPI-Quellarchiv](https://files.pythonhosted.org/packages/63/41/f90302845945abd4ed647933ff5ee7c6ac93983187be67f897b6cb613331/pyinstaller-6.22.3.tar.gz) | `05eb2f5615503e72939a7224d68b4aff572c6b0438ee4a17d0a4b481f399362d` |

`COPYING.txt` ist je Fassung bytegleich im Quellarchiv und Git-Tag. Die
SHA-256-Werte der unveränderten Quelldateibytes sind für 6.22.2
`dcf75fdb959db1e3b41c0f8505069d2ece781b5ec6b3d0a4d30975cfc6580245`
und für 6.22.3
`0598064c7d2718e38d7914a7d08343b2fa008e3bea9ebba2aa7a6ffa5900dd64`.
Der Beilagengenerator hasht dagegen seine dokumentierte Zeilennormalisierung.

Der Lizenztext von 6.22.3 ergänzt ausschließlich den Abschnitt zu zusätzlichen Laufzeitmodulen:
`pyi_splash` und `_pyi_rth_utils` unter `PyInstaller/fake-modules` sind dort
ausdrücklich Apache-2.0 zugeordnet. Bootloader-Ausnahme, GPL-Text und die
weiteren Lizenzabschnitte bleiben unverändert; auch die Lizenzdateien von
Waf und zlib im Quellarchiv sind unverändert. Eine andere PyInstaller-Fassung
bleibt bis zur eigenen Quellen- und Lizenzprüfung gesperrt.
