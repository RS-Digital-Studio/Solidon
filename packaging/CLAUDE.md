# `packaging/` — was das Paket zusammenhält

Die Vorlagen und Beschreibungen, aus denen die Installationsdateien entstehen.
Gebaut wird nicht von hier, sondern über `tools/` und den Skill `/erzeugen`.

## Die Karte

| Datei | Für |
|---|---|
| `solidon3d.spec` | PyInstaller — **die Quelle für alle Plattformen** |
| `solidon3d.iss` | Inno Setup, der Windows-Installer |
| `de.rsdigital.solidon3d.yml` | Flatpak |
| `de.rsdigital.solidon3d.xml` | AppStream-Zuordnung |
| `de.rsdigital.solidon3d.metainfo.xml` | Was der Software-Katalog unter Linux zeigt |
| `solidon3d.desktop` | Startmenü-Eintrag unter Linux |
| `macos-distribution.xml`, `macos-conclusion.txt` | Das macOS-Paket |
| `install.sh` | Linux von Hand |
| `solidon3d.ico`, `solidon3d.icns` | Symbole je Plattform — **erzeugt** von `tools/make_icon.py` |
| `eula.txt` | Die Fassung, die der Installer zeigt — **erzeugt** von `tools/make_legal.py` aus `EULA.md` |

## Die Symbolquelle liegt woanders

`app/images/icon/solidon3d.svg` (und `-small.svg`) ist die Quelle.
`tools/make_icon.py` rastert daraus die `.ico` und die `.icns` **hierher** und
legt zusätzlich `website/icon.svg` als Kopie ab. Was die exe zeigt und was das
Fenster zeigt, ist damit dasselbe.

Zwei Dateien hier sind also Ergebnisse, keine Quellen — sie werden nicht von
Hand bearbeitet.

## Was hier hineinmuss, wenn sich etwas ändert

- **Eine neue Abhängigkeit** kann in der `.spec` fehlen und erst im gebauten
  Paket auffallen — dort, wo kein `pip` mehr hilft.
- **Ein neues Datenverzeichnis** (Kataloge, Profile, Bausteindaten) reist nur
  mit, wenn die `.spec` es kennt.
- **Die Version** kommt aus `app/branding.py` über `tools/bump_version.py` —
  hier wird sie nicht getippt.

`tests/test_packaging.py` prüft, was sich prüfen lässt, ohne zu bauen.

## Der eigene Arbeitsbaum

Paketiert wird in einem **eigenen** Arbeitsbaum, nicht im Entwicklungsbaum —
sonst wandert hinein, was gerade offen ist. Die Reihenfolge und die Falle mit
den fehlenden Schriften stehen im Skill `/erzeugen`.
