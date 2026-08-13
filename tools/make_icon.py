"""Rastert das Anwendungssymbol aus seiner SVG-Quelle (Bauplan §37.2).

Die Quelle ist eine gestaltete Form und liegt in ``app/images/icon/solidon3d.svg``
— sie wird von Hand gestaltet und hier nur gerastert, nie umgekehrt. Erzeugt
werden die zwei Ablagen, die nicht selbst rendern können:

* ``packaging/solidon3d.ico`` — für die exe (PyInstaller) und den Installer
  (Inno Setup). Kleine Größen als DIB, die 256er als PNG, wie Windows es
  vorsieht; geschrieben ohne neue Abhängigkeit.
* ``packaging/solidon3d.icns`` — dasselbe für das macOS-Bundle. Ein ICNS ist
  ein Container aus benannten Blöcken; die modernen Typen nehmen PNG, also
  entsteht es aus denselben Rasterungen wie die ICO und braucht ebenfalls
  keine neue Abhängigkeit.
* ``website/icon.svg`` — das Favicon der Website, eine Kopie der Quelle.

Das Fenster selbst rastert die SVG-Quelle zur Laufzeit
(``app.ui.icons.application_icon``) — dafür entsteht hier nichts.

    python tools/make_icon.py
"""

from __future__ import annotations

import shutil
import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QSize, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "app" / "images" / "icon" / "solidon3d.svg"
SOURCE_SMALL = ROOT / "app" / "images" / "icon" / "solidon3d-small.svg"
ICO_TARGET = ROOT / "packaging" / "solidon3d.ico"
ICNS_TARGET = ROOT / "packaging" / "solidon3d.icns"
WEBSITE_TARGET = ROOT / "website" / "icon.svg"

#: Die Größenreihe der ICO — was Windows in Taskleiste, Explorer und
#: Alt-Tab tatsächlich abruft.
SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)

#: Die Blöcke der ICNS: Typkennung und Kantenlänge. Die Doppelungen sind
#: keine — ``ic13`` ist 128 Punkte in doppelter Auflösung und damit dieselben
#: 256 Pixel wie ``ic08``, das für 256 Punkte einfach steht. macOS greift je
#: nach Bildschirm den einen oder den anderen Block ab, und fehlt er, skaliert
#: es sichtbar unscharf.
ICNS_BLOCKS = (
    ("icp4", 16),
    ("icp5", 32),
    ("ic11", 32),
    ("ic12", 64),
    ("ic07", 128),
    ("ic13", 256),
    ("ic08", 256),
    ("ic14", 512),
    ("ic09", 512),
    ("ic10", 1024),
)

#: Bis hierher kommt die vereinfachte Fassung zum Zug. Dieselbe Grenze wie in
#: ``app.ui.icons`` — was die exe zeigt und was das Fenster zeigt, ist dasselbe
#: Symbol, und zwei Grenzen wären zwei Symbole.
SMALL_LIMIT = 32


def render(source: bytes, size: int) -> QImage:
    """Die SVG-Quelle als quadratisches Bild in einer Größe."""
    renderer = QSvgRenderer(QByteArray(source))
    if not renderer.isValid():
        raise ValueError(f"{SOURCE} ist kein lesbares SVG")
    image = QImage(QSize(size, size), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    return image


def source_for(size: int, large: bytes, small: bytes) -> bytes:
    """Welche der beiden Quellen eine Größe bekommt.

    Bis 32 Pixel die vereinfachte: die ausgearbeitete Fassung trägt
    Schichtlinien, die dort 0,3 Pixel breit wären und als grauer Schleier
    ankommen. Der Grund steht ausführlich in ``solidon3d-small.svg``.
    """
    return small if size <= SMALL_LIMIT else large


def _as_png(image: QImage) -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def _as_dib(image: QImage) -> bytes:
    """Ein Bild als ICO-Eintrag im klassischen Format: BITMAPINFOHEADER mit
    doppelter Höhe, Zeilen von unten nach oben, dahinter die leere AND-Maske
    (die Transparenz trägt der Alphakanal).
    """
    image = image.convertToFormat(QImage.Format.Format_ARGB32)
    width, height = image.width(), image.height()
    header = struct.pack("<IiiHHIIiiII", 40, width, height * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    stride = image.bytesPerLine()
    data = bytes(image.constBits())
    # ARGB32 liegt im Speicher als B,G,R,A — genau die Reihenfolge der DIB.
    rows = b"".join(
        data[row * stride : row * stride + width * 4] for row in range(height - 1, -1, -1)
    )
    mask_stride = ((width + 31) // 32) * 4
    mask = b"\x00" * (mask_stride * height)
    return header + rows + mask


def write_ico(large: bytes, small: bytes, target: Path) -> None:
    """Schreibt die ICO: ein Verzeichnis, dann die Bilder in Größenreihe.

    Zwei Quellen, weil eine ICO alle Größen trägt und die kleinen ein anderes
    Bild brauchen als die großen — siehe :func:`source_for`.
    """
    entries: list[bytes] = []
    blobs: list[bytes] = []
    offset = 6 + 16 * len(SIZES)
    for size in SIZES:
        image = render(source_for(size, large, small), size)
        # Nur die 256er als PNG — kleinere Größen erwartet Windows als DIB.
        blob = _as_png(image) if size == 256 else _as_dib(image)
        entries.append(
            struct.pack(
                "<BBBBHHII",
                size % 256,
                size % 256,
                0,
                0,
                1,
                32,
                len(blob),
                offset,
            )
        )
        blobs.append(blob)
        offset += len(blob)
    target.write_bytes(struct.pack("<HHH", 0, 1, len(SIZES)) + b"".join(entries) + b"".join(blobs))


def write_icns(large: bytes, small: bytes, target: Path) -> None:
    """Schreibt die ICNS: Kennung, Gesamtlänge, dann die Blöcke.

    Jeder Block trägt seine Typkennung, seine Länge **einschließlich** dieser
    acht Kopfbytes und danach die Daten — hier immer ein PNG. Das ist die
    Stelle, an der ein selbstgebautes ICNS üblicherweise scheitert: Wird die
    Länge ohne den Kopf gezählt, liest macOS den nächsten Block acht Bytes zu
    früh und die Datei gilt als beschädigt.
    """
    blocks: list[bytes] = []
    for kind, size in ICNS_BLOCKS:
        png = _as_png(render(source_for(size, large, small), size))
        blocks.append(kind.encode("ascii") + struct.pack(">I", len(png) + 8) + png)
    body = b"".join(blocks)
    target.write_bytes(b"icns" + struct.pack(">I", len(body) + 8) + body)


def main() -> int:
    QGuiApplication.instance() or QGuiApplication(sys.argv)
    source = SOURCE.read_bytes()
    source_small = SOURCE_SMALL.read_bytes()

    # Selbstkontrolle vor dem Schreiben: eine 16er-Rasterung, die leer ist,
    # wäre ein leeres Symbol in der Taskleiste — das fällt hier auf, nicht dort.
    smallest = render(source_small, 16)
    if all(smallest.pixelColor(x, y).alpha() == 0 for x in range(16) for y in range(16)):
        print("Die 16er-Rasterung ist leer — die Quelle prüfen.")
        return 1

    write_ico(source, source_small, ICO_TARGET)
    write_icns(source, source_small, ICNS_TARGET)
    shutil.copyfile(SOURCE, WEBSITE_TARGET)
    print(f"Geschrieben: {ICO_TARGET} ({ICO_TARGET.stat().st_size} Bytes)")
    print(f"Geschrieben: {ICNS_TARGET} ({ICNS_TARGET.stat().st_size} Bytes)")
    print(f"Geschrieben: {WEBSITE_TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
