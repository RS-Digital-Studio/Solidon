"""Symbole für die Oberfläche (Bauplan §19.3, AGENTS.md Regel 18).

**Symbole ergänzen Text, sie ersetzen ihn nicht.** Ein unbeschriftetes Zeichen
wird geraten, und bei einer Anwendung, die jemand alle paar Wochen öffnet, ist
Wiedererkennen mehr wert als Kompaktheit. „Schnitt", „Explosion" und „Passung"
sind keine Begriffe mit einem Bild, auf das sich die Welt geeinigt hat. Was ein
Symbol hier leistet, ist Unterscheidbarkeit auf einen Blick — sieben Knöpfe mit
Text sehen alle gleich aus, sieben Knöpfe mit Text und Zeichen nicht.

Von Hand geschriebene Pfade und nicht aus :mod:`app.core.drawing` gerechnet:
das Modul zeichnet Maßlinien und Schemata, deren Form aus Zahlen folgt. Ein
Symbol ist eine gestaltete Form, und die entsteht nicht aus einer Formel.

Zwei Dinge halten sie brauchbar:

* **``currentColor`` statt fester Farben.** Qt löst das nicht selbst auf, also
  wird es beim Laden gegen die Textfarbe ersetzt — ein Satz Symbole für beide
  Themen, keiner, der im dunklen unsichtbar wird.
* **Größe an der Schrift, nicht an Pixeln.** Wer die Schrift größer stellt,
  bekommt größere Symbole; sonst schrumpfen sie neben dem Text zu Punkten.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from PySide6.QtCore import QByteArray, QRect, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QIcon,
    QIconEngine,
    QImage,
    QPainter,
    QPalette,
    QPen,
    QPixmap,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QWidget

#: Wie viel größer als die Zeilenhöhe ein Symbol gezeichnet wird, bevor es
#: verkleinert wird — sonst franst es auf HiDPI aus.
OVERSAMPLING: Final = 2

_HEAD: Final = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="1.6" '
    'stroke-linecap="round" stroke-linejoin="round">'
)

#: Die Symbole der Werkzeugzeile. Bewusst in einem Strichstil gehalten: ein
#: gefülltes und ein gestricheltes Zeichen nebeneinander sehen aus wie zwei
#: verschiedene Programme.
PATHS: Final[dict[str, str]] = {
    # Ein Körper, den eine Ebene durchtrennt.
    "section": (
        '<path d="M4 8.5 12 4l8 4.5v7L12 20l-8-4.5z" />'
        '<path d="M2.5 13.5h19" stroke-dasharray="3 2.5" />'
    ),
    # Maßlinie mit Endstrichen — das Zeichen jeder technischen Zeichnung.
    "measure": (
        '<path d="M4 12h16" /><path d="M7 9l-3 3 3 3" /><path d="M17 9l3 3-3 3" />'
        '<path d="M4 6v3" /><path d="M20 6v3" />'
    ),
    # Vier Richtungen: das eine Zeichen fürs Bewegen, auf das sich alle geeinigt haben.
    "move": (
        '<path d="M12 3v18" /><path d="M3 12h18" />'
        '<path d="M9 6l3-3 3 3" /><path d="M9 18l3 3 3-3" />'
        '<path d="M6 9l-3 3 3 3" /><path d="M18 9l3 3-3 3" />'
    ),
    # Eine Karte über einer Fläche: ungleich gefüllte Felder.
    "analysis": (
        '<rect x="3.5" y="3.5" width="17" height="17" rx="2" />'
        '<path d="M3.5 12h17" /><path d="M12 3.5v17" />'
        '<path d="M3.5 8h8.5" stroke-width="3" opacity="0.45" />'
        '<path d="M12 16h8.5" stroke-width="3" opacity="0.8" />'
    ),
    # Gestapelte Schichten.
    "layers": (
        '<path d="M12 3.5 21 8l-9 4.5L3 8z" />'
        '<path d="M3 12.5 12 17l9-4.5" opacity="0.75" />'
        '<path d="M3 16.5 12 21l9-4.5" opacity="0.5" />'
    ),
    # Auseinandergezogen: zwei Hälften, die voneinander wegwandern. Die erste
    # Version verband sie mit gestrichelten Linien — die verschwanden bei
    # Symbolgröße, und übrig blieben zwei Quadrate ohne Aussage.
    "explode": (
        '<rect x="3" y="3" width="8" height="8" rx="1" />'
        '<rect x="13" y="13" width="8" height="8" rx="1" />'
        '<path d="M13.5 10.5 10.5 13.5" />'
        '<path d="M13.5 10.5h-3v3" />'
    ),
    # Trennen: ein Körper, durch den eine gezeichnete Linie schräg hindurchgeht,
    # und die beiden Hälften stehen schon auseinander. Schräg mit Absicht — das
    # ist der Unterschied zum Schnittwerkzeug daneben, dessen Linie waagerecht
    # liegt; zwei Zeichen mit derselben Geste wären eines zu viel.
    "split": (
        '<path d="M4.5 10.5 10.5 4.5h5.5l-6 6z" />'
        '<path d="M8 19.5l6-6h5.5l-6 6z" />'
        '<path d="M3 18 21 6" stroke-dasharray="3 2.5" />'
    ),
    # Die Schweregrade des Prüfberichts. Hier ist Ikonografie ausnahmsweise
    # etabliert: Dreieck warnt, Kreis erklärt, Achteck hält an — die Form trägt
    # allein, auch wo die Farbe wegfällt (Regel 18).
    "severity-info": (
        '<circle cx="12" cy="12" r="8.5" /><path d="M12 11.2v5" /><path d="M12 8.2v.6" />'
    ),
    "severity-warning": (
        '<path d="M12 4 21 19.5H3z" /><path d="M12 10v4.5" /><path d="M12 17.2v.6" />'
    ),
    "severity-error": (
        '<path d="M8.6 3.5h6.8L20.5 8.6v6.8L15.4 20.5H8.6L3.5 15.4V8.6z" />'
        '<path d="M9.4 9.4l5.2 5.2" /><path d="M14.6 9.4l-5.2 5.2" />'
    ),
    # Ein leeres Blatt mit umgeknickter Ecke.
    "new": ('<path d="M6 3h7l5 5v13H6z" /><path d="M13 3v5h5" />'),
    # Ein Ordner, halb geöffnet.
    "open": ('<path d="M3 6.5h6l2 2.5h10v9.5H3z" /><path d="M3 9h18" />'),
    # Eine Diskette — das Zeichen fürs Speichern, auf das sich die Welt
    # tatsächlich geeinigt hat.
    "save": ('<path d="M4 4h12l4 4v12H4z" /><path d="M8 4v6h7V4" /><path d="M7 20v-6h10v6" />'),
    # Formen: die ursprüngliche Fläche gestrichelt, darüber die verzogene, und
    # der Pinsel, der sie hochgezogen hat. Ohne die gestrichelte Linie wäre es
    # ein Hügel mit einem Stift daneben — die Aussage ist die *Änderung*.
    "sculpt": (
        '<path d="M3 16.5h18" stroke-dasharray="3 2.5" opacity="0.55" />'
        '<path d="M3 16.5c4 0 3.5-5 9-5s5 5 9 5" />'
        '<path d="M12 3.5v3.4" /><path d="M10 6.9h4l-2 3.2z" />'
    ),
    # Skelett: ein Gelenk mit zwei Knochen und dem Bogen, um den es beugt. Eine
    # bloße Kette aus Punkten und Strichen sähe aus wie das Skizzensymbol
    # daneben; der gestrichelte Winkel ist der Unterschied.
    "armature": (
        '<path d="M7 4.5v6.2" /><circle cx="7" cy="12.6" r="1.9" />'
        '<path d="M8.4 14.2 13.5 19.3" />'
        '<path d="M11 7a8 8 0 0 1 2.2 5.6" stroke-dasharray="2.5 2" opacity="0.7" />'
    ),
    # Ein Körper mit einem Pfeil hinein.
    "import": (
        '<path d="M13 4.5 20 8.5v7l-7 4-7-4v-7z" stroke-dasharray="3 2" />'
        '<path d="M2.5 12h7" /><path d="M6.5 9l3 3-3 3" />'
    ),
    # Ein durchgestrichenes Auge für einen Körper, der da ist und nicht
    # gezeichnet wird. Das Wort „ausgeblendet" steht daneben (Regel 18) — das
    # Zeichen unterscheidet die Zeile auf einen Blick, es trägt sie nicht.
    "hidden": (
        '<path d="M3 12s3.6-6 9-6c1.4 0 2.7.4 3.8 1" />'
        '<path d="M19.4 9.1c.9.9 1.6 1.9 1.6 2.9 0 0-3.6 6-9 6-1.5 0-2.8-.5-4-1.1" />'
        '<path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" />'
        '<path d="M4 20 20 4" />'
    ),
    # Ein Haken: ein erledigter Schritt der Tour. Der Text der Zeile bleibt
    # stehen (Regel 18) — das Zeichen sagt nur den Zustand.
    "done": ('<path d="M4.5 12.5l4.5 4.5L19.5 7" />'),
    # Ein Pfeil auf den aktuellen Schritt der Tour.
    "step": ('<path d="M4 12h12.5" /><path d="M11.5 6.5 17 12l-5.5 5.5" />'),
    # --- Zeichenwerkzeuge ------------------------------------------------------
    #
    # Hier tragen die Symbole **allein**, ohne Beschriftung. Der Grund ist nicht
    # Platzmangel, sondern dass die Regel oben ihre Voraussetzung verliert:
    # „Schnitt" und „Explosion" haben kein Bild, auf das sich die Welt geeinigt
    # hat, Linie, Kreis und Bogen schon. Jedes CAD zeigt sie seit dreißig Jahren
    # gleich, und wer je eines bedient hat, liest sie ohne Wort. Das Kürzel steht
    # im Tooltip, wo es sich beim Verweilen von selbst zeigt.
    #
    # Die Werkzeugleiste über dem Fenster steht ebenfalls ohne Beschriftung,
    # aber **nicht** aus demselben Grund — das trägt nur für drei ihrer sieben
    # Knöpfe. Blatt, Ordner und Diskette sind so alt und so einheitlich wie
    # Linie und Kreis; für „Modell einfügen", „Zeichnen", „Formen" und
    # „Skelett" gibt es kein geeinigtes Bild, und geraten wird dort genauso.
    # Was sie trägt, ist zweierlei: Sie sind wenige und stehen immer an
    # derselben Stelle, und ihr Tooltip nennt Namen, Kürzel und Zweck in einem
    # Satz (``main_window._button_tip``) — der Umweg über den Zeiger kostet
    # einmal, und danach sitzt die Position.
    #
    # Die Werkzeugzeile unter dem Viewport bleibt beschriftet: dort steht
    # „Schnitt", ihre acht Umschalter wechseln mit dem Zustand, und ein
    # Werkzeug, das man sucht, ist kein Werkzeug mehr.
    #
    # Ein Punkt: kein Kreis, sondern ein Kreuz mit Mitte — ein gefüllter Kreis
    # sähe neben dem Kreiswerkzeug aus wie dessen kleiner Bruder.
    "sketch_select": ('<path d="M5 3.5l6.5 15.5 2.2-6.3 6.3-2.2z" />'),
    "sketch_point": (
        '<path d="M12 6.5v11" /><path d="M6.5 12h11" /><circle cx="12" cy="12" r="2.2" />'
    ),
    "sketch_line": (
        '<path d="M5.5 18.5 18.5 5.5" /><circle cx="5.5" cy="18.5" r="1.8" />'
        '<circle cx="18.5" cy="5.5" r="1.8" />'
    ),
    "sketch_circle": ('<circle cx="12" cy="12" r="7.5" /><circle cx="12" cy="12" r="1.4" />'),
    "sketch_rectangle": (
        '<rect x="4" y="6" width="16" height="12" rx="1" />'
        '<circle cx="4" cy="6" r="1.2" fill="currentColor" stroke="none" />'
        '<circle cx="20" cy="18" r="1.2" fill="currentColor" stroke="none" />'
    ),
    "sketch_arc": (
        '<path d="M4.5 17.5a9 9 0 0 1 15 0" /><circle cx="4.5" cy="17.5" r="1.8" />'
        '<circle cx="19.5" cy="17.5" r="1.8" />'
    ),
    # Die S-Kurve mit ihren Stützpunkten — das Bild jeder Spline-Bedienung.
    "sketch_spline": (
        '<path d="M4 17c3.5 0 4-10 8-10s4.5 10 8 10" />'
        '<circle cx="4" cy="17" r="1.6" /><circle cx="12" cy="12" r="1.6" />'
        '<circle cx="20" cy="17" r="1.6" />'
    ),
    # Trimmen: die Schere schneidet das gestrichelte Reststück weg.
    "sketch_trim": (
        '<path d="M4 12h9" /><path d="M13 12h7" stroke-dasharray="2.5 2" />'
        '<path d="M15.5 5.5 20 10" /><path d="M15.5 18.5 20 14" />'
    ),
    # Verlängern: die durchgezogene Linie wächst in die gestrichelte hinein.
    "sketch_extend": (
        '<path d="M4 12h8" /><path d="M12 12h5" stroke-dasharray="2.5 2" />'
        '<path d="M16 8.5 20 12l-4 3.5" /><path d="M20.5 6v12" />'
    ),
    # Versatz: dieselbe Kontur ein zweites Mal daneben.
    "sketch_offset": (
        '<path d="M4 16.5 9 7h6l5 9.5" /><path d="M7 19.5 11 12h2l4 7.5" stroke-dasharray="3 2" />'
    ),
    # Spiegeln: zwei Formen, dazwischen die Achse.
    "sketch_mirror": (
        '<path d="M12 3.5v17" stroke-dasharray="3 2.5" />'
        '<path d="M9.5 6.5 4 12l5.5 5.5z" /><path d="M14.5 6.5 20 12l-5.5 5.5z" />'
    ),
    # Hilfslinie: durchweg gestrichelt, denn genau das ist ihr Wesen.
    "sketch_construction": ('<path d="M4 18.5 20 5.5" stroke-dasharray="3 2.5" />'),
    # Projizieren: aus dem Körper fällt seine Kante auf die Zeichenebene.
    "sketch_project": (
        '<path d="M5 4.5h9v9H5z" /><path d="M10 19.5h9" />'
        '<path d="M5 13.5 10 19.5" stroke-dasharray="2.5 2" />'
        '<path d="M14 13.5 19 19.5" stroke-dasharray="2.5 2" />'
    ),
    # Rückgängig: der Pfeil, der zurück in seinen Bogen zeigt.
    "sketch_undo": ('<path d="M4 9.5h10a5 5 0 0 1 0 10h-6" /><path d="M8 5 4 9.5 8 14" />'),
    # Einpassen: vier Ecken, die sich um das Gezeichnete zusammenziehen. Die
    # Pfeile zeigen nach innen — ein Rahmen allein sähe aus wie ein Auswahl-
    # rechteck, und genau das tut dieser Knopf nicht.
    "sketch_fit": (
        '<path d="M4 8.5V4.5h4" /><path d="M20 8.5V4.5h-4" />'
        '<path d="M4 15.5v4h4" /><path d="M20 15.5v4h-4" />'
        '<path d="M9 12h6" /><path d="M12 9v6" />'
    ),
    # Aus einem flachen Umriss wächst ein Körper nach oben. Die Beschriftung
    # „Hochziehen“ bleibt daneben — das Zeichen macht die Richtung auf einen
    # Blick unterscheidbar, es ersetzt das Wort nicht.
    "sketch_pull": (
        '<path d="M4 15.5 12 19.5l8-4-8-4z" />'
        '<path d="M4 15.5V10l8-4 8 4v5.5" opacity="0.55" />'
        '<path d="M12 12V3.5" /><path d="M8.8 6.7 12 3.5l3.2 3.2" />'
    ),
    # Derselbe Umriss als Aussparung: gestrichelter Taschenboden und ein
    # Pfeil ins Material. Form plus Text tragen die Aussage auch ohne Farbe.
    "sketch_cut": (
        '<path d="M3.5 8h17v11h-17z" />'
        '<path d="M7 13.5h10v3H7z" stroke-dasharray="2.5 2" opacity="0.65" />'
        '<path d="M12 3.5v9" /><path d="M8.8 9.3 12 12.5l3.2-3.2" />'
    ),
    # --- je Kategorie eines (Konzept P15 §7 Etappe 8, D5) ----------------------
    #
    # **Nicht je Operation.** Dreiundsiebzig Symbole zu unterscheiden ist
    # schwerer als dreiundsiebzig Wörter zu lesen, und drei ähnliche Bohrer
    # nebeneinander sagen weniger als einer über allen Bohr-Operationen. Was
    # ein Symbol hier leistet, ist dasselbe wie in der Werkzeugzeile: die
    # Gruppe auf einen Blick, die Beschriftung daneben für alles Weitere
    # (Regel 18).
    #
    # Eine Operation darf trotzdem ihr eigenes führen; `icon` im Register
    # schlägt das der Kategorie.
    # Szene: mehrere Körper nebeneinander.
    "category.scene": (
        '<rect x="3" y="9" width="8" height="8" rx="1" />'
        '<rect x="13" y="5" width="8" height="8" rx="1" opacity="0.6" />'
    ),
    # Reparatur: eine Naht, die geschlossen wird.
    "category.repair": (
        '<path d="M4 12h16" stroke-dasharray="3 2" />'
        '<path d="M9 7l3 5-3 5" /><path d="M15 7l-3 5 3 5" />'
    ),
    # Transformation: ein Körper mit Bewegungspfeil.
    "category.transform": (
        '<rect x="3.5" y="9.5" width="8" height="8" rx="1" />'
        '<path d="M14 13.5h6" /><path d="M17.5 10 21 13.5 17.5 17" />'
    ),
    # Boolesch: zwei Kreise mit gemeinsamer Fläche.
    "category.boolean": (
        '<circle cx="9.5" cy="12" r="6" /><circle cx="14.5" cy="12" r="6" opacity="0.6" />'
    ),
    # Grundformen: Würfel und Zylinder nebeneinander — die zwei, mit denen
    # fast jede Konstruktion anfängt.
    "category.primitive": (
        '<path d="M3.5 8.5 8 6l4.5 2.5v5L8 16l-4.5-2.5z" />'
        '<path d="M3.5 8.5 8 11l4.5-2.5" /><path d="M8 11v5" opacity="0.6" />'
        '<ellipse cx="17" cy="8" rx="3.5" ry="1.6" />'
        '<path d="M13.5 8v8" /><path d="M20.5 8v8" />'
        '<path d="M13.5 16a3.5 1.6 0 0 0 7 0" />'
    ),
    # Skizze: ein Umriss mit Punkten darauf.
    "category.sketch": (
        '<path d="M5 17l4-9 5 5 5-7" />'
        '<circle cx="5" cy="17" r="1.6" /><circle cx="9" cy="8" r="1.6" />'
        '<circle cx="14" cy="13" r="1.6" /><circle cx="19" cy="6" r="1.6" />'
    ),
    # Formgebung: eine gebrochene Kante — die Fase.
    "category.shaping": ('<path d="M4 20V9l5-5h11v16z" /><path d="M4 9h5V4" opacity="0.6" />'),
    # Bohrungen: ein Loch in einer Platte, im Schnitt.
    "category.holes": (
        '<rect x="3.5" y="7" width="17" height="10" rx="1" />'
        '<ellipse cx="12" cy="12" rx="3.2" ry="4.2" />'
    ),
    # Bausteine: ein Teil, das in ein anderes greift.
    "category.parts": ('<path d="M4 8h6V5h4v3h6v8h-6v3h-4v-3H4z" />'),
    # Druckvorbereitung: ein Teil auf der Platte.
    "category.prepare": (
        '<path d="M8 14V7l4-3 4 3v7" />'
        '<path d="M3 17.5h18" stroke-width="2.2" />'
        '<path d="M6 20.5h12" opacity="0.5" />'
    ),
    # Farbe: ein Pinsel über einer Fläche.
    "category.colour": (
        '<path d="M4 20c0-3 2-4 4-4 2 0 3 1 3 3s-2 3-4 3c-1.5 0-3-.6-3-2z" />'
        '<path d="M9.5 16.5 19 5.5a1.8 1.8 0 0 1 2.6 2.5L11 18" />'
    ),
    # Beschriftung: ein A auf einer Grundlinie.
    "category.label": (
        '<path d="M6.5 15.5 11 5l4.5 10.5" /><path d="M8 12.5h6" />'
        '<path d="M3.5 19.5h17" opacity="0.6" />'
    ),
    # Oberfläche: eine Fläche mit Muster darauf.
    "category.surface": (
        '<rect x="3.5" y="3.5" width="17" height="17" rx="2" />'
        '<path d="M3.5 9h17" opacity="0.7" /><path d="M3.5 15h17" opacity="0.7" />'
        '<path d="M9 3.5v17" opacity="0.45" /><path d="M15 3.5v17" opacity="0.45" />'
    ),
    # Import: eine Datei mit einem Pfeil hinein. Es gibt schon ein „import"
    # für die Werkzeugleiste; das hier ist das der Kategorie, und beide
    # nebeneinander wären eine Verwechslung — deshalb dasselbe Zeichen.
    "category.import": (
        '<path d="M14 3.5H6.5A1.5 1.5 0 0 0 5 5v14a1.5 1.5 0 0 0 1.5 1.5h11'
        'A1.5 1.5 0 0 0 19 19V8.5z" />'
        '<path d="M14 3.5V8.5h5" opacity="0.6" />'
        '<path d="M12 10.5v6" /><path d="M9.5 14 12 16.5 14.5 14" />'
    ),
    # Netz: die Dreiecke selbst.
    "category.mesh": (
        '<path d="M12 3.5 21 9v6l-9 5.5L3 15V9z" />'
        '<path d="M12 3.5v17" opacity="0.55" />'
        '<path d="M3 9l18 6" opacity="0.55" /><path d="M21 9 3 15" opacity="0.55" />'
    ),
    # --- Die sieben Kameravorgaben (Konzept P15, D4) -------------------------
    #
    # Eine Familie, kein Satz Einzelfälle: Sechs davon zeigen dasselbe Quadrat
    # — die Bildebene — und unterscheiden sich nur darin, woher der Blick
    # kommt. Die siebte ist der Würfel selbst.
    #
    # **Für „vorne" und „hinten" die Konvention der Physik.** Beide blicken
    # senkrecht auf die Ebene, und ein Pfeil in der Bildebene könnte das nicht
    # zeigen; ein Vektor senkrecht dazu wird seit je als **Punkt** (kommt
    # heraus) und als **Kreuz** (geht hinein) gezeichnet. Wer das nicht kennt,
    # liest den Text daneben — die Leiste trägt beides.
    "view_iso": (
        '<path d="M12 3.5 20.5 8.5v7L12 20.5 3.5 15.5v-7z" />'
        '<path d="M12 12 20.5 8.5" opacity="0.55" />'
        '<path d="M12 12 3.5 8.5" opacity="0.55" />'
        '<path d="M12 12v8.5" opacity="0.55" />'
    ),
    "view_front": (
        '<path d="M5 5h14v14H5z" />'
        '<circle cx="12" cy="12" r="2.2" fill="currentColor" stroke="none" />'
    ),
    "view_back": ('<path d="M5 5h14v14H5z" /><path d="M9 9l6 6" /><path d="M15 9l-6 6" />'),
    "view_left": (
        '<path d="M9 5h10v14H9z" /><path d="M2.5 12h4.5" /><path d="M5 9.5 7.5 12 5 14.5" />'
    ),
    "view_right": (
        '<path d="M5 5h10v14H5z" /><path d="M21.5 12H17" /><path d="M19 9.5 16.5 12 19 14.5" />'
    ),
    "view_top": (
        '<path d="M5 9h14v10H5z" /><path d="M12 2.5v4.5" /><path d="M9.5 5 12 7.5 14.5 5" />'
    ),
    "view_bottom": (
        '<path d="M5 5h14v10H5z" /><path d="M12 21.5V17" /><path d="M9.5 19 12 16.5 14.5 19" />'
    ),
}


def svg_source(name: str, colour: str) -> str:
    """Das SVG eines Symbols, in einer Farbe statt ``currentColor``."""
    body = PATHS.get(name)
    if body is None:
        return ""
    return f"{_HEAD}{body}</svg>".replace("currentColor", colour)


def icon_name_for(spec: object) -> str:
    """Welches Symbol eine Operation trägt.

    Ihr eigenes, wenn sie eines deklariert hat; sonst das ihrer Kategorie.
    Damit hat **jede** Operation eines, ohne dass jemand dreiundsiebzig
    Zeichnungen pflegt — und die Kategorie ist ohnehin die Auskunft, die ein
    Symbol in einem Menü geben kann.
    """
    own = str(getattr(spec, "icon", "") or "")
    if own:
        return own
    return f"category.{getattr(spec, 'category', '')}"


class ThemedIcon(QIconEngine):
    """Ein Symbol, das seine Farbe beim **Zeichnen** holt, nicht beim Erzeugen.

    Vorher wurde beim Aufbau einmal gerastert — in der Textfarbe, die gerade
    galt. Nach einem Themenwechsel stand dieselbe Grafik weiter da: im hellen
    Thema hell auf hell, und die halbe Werkzeugzeile bestand aus Text mit
    Lücken davor. Ein Symbol, das seine Farbe jedes Mal neu nimmt, kann gar
    nicht veralten, und der Wechsel braucht keine Liste aller Stellen, die
    eines tragen.

    Nebenher wird es scharf: gezeichnet wird in die angeforderte Größe, nicht
    ein festes Pixmap auf sie hochgerechnet.
    """

    def __init__(self, name: str) -> None:
        super().__init__()
        self._name = name

    def _tone(self, mode: QIcon.Mode) -> QColor:
        palette = QApplication.palette()
        if mode == QIcon.Mode.Disabled:
            return palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText)
        if mode == QIcon.Mode.Selected:
            # Auf der Auswahlfläche gilt die Schriftfarbe der Auswahl, nicht die
            # des Fensters. Qt fragt diesen Modus für die markierte Zeile einer
            # Liste oder eines Baums — dort liegt Bernstein, und ein helles
            # Symbol darauf bringt 1,58 Kontrast. Die Beschriftung daneben ist
            # längst dunkel; das Symbol widersprach ihr.
            return palette.highlightedText().color()
        return palette.windowText().color()

    def paint(self, painter: QPainter, rect: QRect, mode: QIcon.Mode, state: QIcon.State) -> None:
        source = svg_source(self._name, self._tone(mode).name())
        if not source:
            return
        renderer = QSvgRenderer(QByteArray(source.encode("utf-8")))
        if renderer.isValid():
            renderer.render(painter, QRectF(rect))

    def pixmap(self, size: QSize, mode: QIcon.Mode, state: QIcon.State) -> QPixmap:
        source = svg_source(self._name, self._tone(mode).name())
        if not source:
            return QPixmap()
        return _pixmap(source, max(size.width(), size.height()), self._tone(mode))

    def clone(self) -> QIconEngine:
        return ThemedIcon(self._name)


def icon(name: str, widget: QWidget, *, scale: float = 1.35, colour: QColor | None = None) -> QIcon:
    """Ein Symbol in der Textfarbe und in der Größe der Schrift des Widgets.

    ``scale`` ist der Faktor auf die Zeilenhöhe: etwas größer als die Schrift,
    sonst verschwindet ein Strichsymbol neben dem Wort daneben.

    Ohne ``colour`` folgt es dem Thema und färbt sich bei jedem Zeichnen neu.
    Mit ``colour`` bleibt es dabei: eine Rollenfarbe — der Schweregrad eines
    Befunds etwa — bedeutet etwas und darf sich mit dem Thema nicht ändern.
    """
    if colour is None:
        # ``scale`` bleibt für den Fall mit fester Farbe: ein Vektorsymbol
        # zeichnet in jede angeforderte Größe, es braucht keine eigene.
        return QIcon(ThemedIcon(name)) if name in PATHS else QIcon()

    source = svg_source(name, colour.name())
    if not source:
        return QIcon()
    size = max(int(widget.fontMetrics().height() * scale), 12)
    return QIcon(_pixmap(source, size, colour))


def _pixmap(source: str, size: int, colour: QColor) -> QPixmap:
    renderer = QSvgRenderer(QByteArray(source.encode("utf-8")))
    if not renderer.isValid():
        return QPixmap()
    image = QImage(QSize(size, size) * OVERSAMPLING, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    image.setDevicePixelRatio(float(OVERSAMPLING))
    return QPixmap.fromImage(image)


def known() -> tuple[str, ...]:
    """Welche Symbole es gibt — der Test liest das."""
    return tuple(PATHS)


#: Die Größen, in denen das Fenster-Symbol vorgehalten wird — dieselbe Reihe
#: fragt Windows für Taskleiste, Alt-Tab und Titelzeile ab.
APPLICATION_ICON_SIZES: Final = (16, 24, 32, 48, 64, 128, 256)


#: Wo die Quelle des Anwendungssymbols liegt. Eine Datei, drei Abnehmer:
#: dieses Modul für das Fenster, ``tools/make_icon.py`` für ICO und Favicon,
#: und der Ladebildschirm, der sie schichtweise zeichnet.
ICON_SOURCE: Final = Path(__file__).resolve().parent.parent / "images" / "icon" / "solidon3d.svg"

#: Die vereinfachte Version für kleine Größen. Warum es sie gibt, steht in der
#: Datei selbst — kurz: was bei 128 Pixeln Struktur ist, ist bei 16 Schleier.
ICON_SOURCE_SMALL: Final = ICON_SOURCE.with_name("solidon3d-small.svg")

#: Bis zu welcher Kantenlänge die vereinfachte Version genommen wird.
#: 32 ist die Grenze, ab der die Schichtlinien wieder als Linien ankommen —
#: nachgesehen, nicht geschätzt.
SMALL_ICON_LIMIT: Final = 32


def _renderer_for(source: Path) -> QSvgRenderer | None:
    """Ein geprüfter Renderer für eine SVG-Datei, oder ``None``.

    Fasst zusammen, was sonst dreimal danebenstünde: lesen, was fehlen kann,
    und prüfen, was ungültig sein kann.
    """
    try:
        data = source.read_bytes()
    except OSError:
        return None
    renderer = QSvgRenderer(QByteArray(data))
    return renderer if renderer.isValid() else None


def application_icon_source() -> str:
    """Die SVG-Quelle des Anwendungssymbols als Text.

    Für alles, was das Symbol nicht als fertiges :class:`QIcon` braucht,
    sondern selbst zeichnet — der Ladebildschirm beschneidet es beim Rendern.
    Fehlt die Datei, kommt eine leere Zeichenkette; der Aufrufer bekommt einen
    ungültigen Renderer und zeichnet nichts, statt zu scheitern.
    """
    try:
        return ICON_SOURCE.read_text(encoding="utf-8")
    except OSError:
        return ""


#: Die Farbe der Aufbaukante — der Druckkopf, der über dem Gedruckten steht.
#: Heller als die Fortschrittsfarbe darunter, damit die Linie auf dem fertigen
#: Körper steht, statt in ihm zu verschwinden.
BUILD_EDGE: Final = "#f0b070"


def paint_printed_mark(
    painter: QPainter, renderer: QSvgRenderer, area: QRectF, done: float, ghost: float = 0.0
) -> None:
    """Zeichnet das Anwendungssymbol so weit, wie es „gedruckt" ist.

    Der Beschnitt wandert von unten nach oben: unterhalb der Kante steht der
    fertige Körper, oberhalb noch nichts. An der Kante läuft eine helle Linie
    mit — der Druckkopf. Sie verschwindet, sobald nichts mehr zu drucken ist;
    ein Druckkopf über einem fertigen Teil wäre eine Lüge.

    ``ghost`` ist die Deckkraft, mit der das *ganze* Zeichen darunter liegt —
    was noch nicht gedruckt ist, als Andeutung. Auf einer großen Fläche ist
    das der Unterschied zwischen einem Fleck und einem Körper, der entsteht:
    bei 40 Prozent ist von der Marke sonst nur ein Streifen zu sehen, aus dem
    niemand liest, was da wächst. Vorgabe ist null — der Ladebildschirm zeigt
    das Zeichen auf einer kleinen Karte und braucht es nicht.

    Zwei Stellen zeigen das: der Ladebildschirm beim Start (``splash.py``) und
    die Ladeanzeige über der Ansicht (``loading.py``). Beide meinen dasselbe,
    also zeichnet es dieselbe Funktion.

    Ein ungültiger Renderer — die SVG-Datei fehlt — zeichnet nichts. Der
    Aufrufer behält seine übrigen Anzeigen; ein Ladebildschirm ohne Symbol ist
    besser als keiner.
    """
    if not renderer.isValid():
        return

    if ghost > 0.0:
        painter.save()
        painter.setOpacity(ghost)
        renderer.render(painter, area)
        painter.restore()

    built = area.height() * max(0.0, min(1.0, done))
    painter.save()
    painter.setClipRect(QRectF(area.left(), area.bottom() - built, area.width(), built))
    renderer.render(painter, area)
    painter.restore()

    if 0.0 < done < 1.0:
        edge = area.bottom() - built
        painter.save()
        painter.setPen(QPen(QColor(BUILD_EDGE), 2.0))
        painter.drawLine(int(area.left() - 6), int(edge), int(area.right() + 6), int(edge))
        painter.restore()


def application_icon() -> QIcon:
    """Das Anwendungssymbol, zur Laufzeit aus seinen SVG-Quellen gerastert.

    **Zwei Quellen, nicht eine.** Bis 32 Pixel kommt die vereinfachte Version
    zum Zug (``solidon3d-small.svg``), darüber die ausgearbeitete. Der Grund
    steht im kleinen SVG: Bei sechzehn Pixeln — Titelleiste, Taskleiste,
    Alt-Tab, und dieselbe Größe in jedem Dialog — sind die Schichtlinien der
    großen Version 0,3 Pixel breit und ergeben einen grauen Schleier, aus dem
    kein Körper mehr zu lesen ist.

    Das gilt für **alle** Fenster: Gesetzt wird das Symbol einmal auf der
    ``QApplication`` (``app/ui/app.py``), und jedes Fenster erbt es — kein
    Dialog vergibt ein eigenes.

    Fehlt eine Datei, springt die andere ein; fehlen beide, gibt es ein leeres
    Symbol und die Plattform zeigt ihr Standardbild. Ein Start scheitert daran
    nicht.
    """
    large = _renderer_for(ICON_SOURCE)
    small = _renderer_for(ICON_SOURCE_SMALL) or large
    if large is None:
        large = small
    if large is None or small is None:
        return QIcon()

    result = QIcon()
    for size in APPLICATION_ICON_SIZES:
        renderer = small if size <= SMALL_ICON_LIMIT else large
        image = QImage(QSize(size, size), QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        result.addPixmap(QPixmap.fromImage(image))
    return result
