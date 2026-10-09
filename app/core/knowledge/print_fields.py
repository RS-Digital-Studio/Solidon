"""Die Felder des Druckdialogs als Tabelle — ohne Qt (RM-289, N4).

Feldname, Einheit, Grenzen, Wahlen und der erklärende Satz jeder Einstellung
stehen hier, damit Druckdialog, Prüfbericht und Kommandozeile dieselbe
Beschriftung lesen. Bis 0.5.1 lag die Tabelle im Dialog: Die Kommandozeile
lädt kein Qt und nannte bei Einstellungen je Teil weder Einstellung noch Wert.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, Literal

from app.core.knowledge import print_settings
from app.core.units import DEGREE_UNIT
from app.i18n import TranslatableText, _, decimal_separator, tr

FieldKind = Literal["float", "int", "bool", "enum", "colour"]


@dataclass(frozen=True, slots=True)
class Field:
    """Eine Zeile im Dialog. ``group`` ist der Reiter, ``front`` hebt sie nach
    vorn."""

    path: str
    title: str | TranslatableText
    """Die Beschriftung — im ganzen Dialog nur einmal vergeben (RM-514)."""
    group: str
    kind: FieldKind = "float"
    unit: str = ""
    minimum: float = 0.0
    maximum: float = 1000.0
    step: float = 0.1
    decimals: int = 2
    choices: tuple[str, ...] = ()
    front: bool = False
    """Vorn im Dialog stehen nur Fülldichte und Stützen (RM-514); was aus
    Drucker, Filament und Qualität kommt, steht hinter „Weitere Einstellungen"."""
    factor: float = 1.0
    """Anzeige geteilt durch Modellwert. Der Kern rechnet Anteile in 0…1, die
    Werkstatt spricht in Prozent — ein Feld mit ``[%]`` und einer 0,15 darin
    ist schlicht falsch beschriftet (§19.3)."""
    choice_notes: tuple[tuple[str, str | TranslatableText], ...] = ()
    """Sätze zu einzelnen Auswahlwerten, die nur für dieses Feld gelten.

    „Automatisch" erklärte ``labels.choice_note`` für alle Felder gleich —
    als Parameter, der „aus dem Zusammenhang bestimmt wird". Bei Stützen und
    Haftung heißt es etwas anderes (Review Stufe A+B, H8)."""
    note: str | TranslatableText = ""
    """Was der Wert tut, und woran man ihn ändert — als Tooltip am Feld.

    **Der größte Dialog der Anwendung war der einzige ohne ein erklärendes
    Wort.** Jeder der 136 Menüeinträge trägt einen Satz, jeder Parameter einer
    Operation seinen ``doc``-Satz; hier standen sechsundfünfzig Felder, und wer
    „Außenwand auf Sollmaß" oder „Wände nicht überfahren" las, blieb allein
    damit. Bei „Schichthöhe" hätte man es übersehen können — bei den
    dreiundzwanzig Feldern, deren Name eine Technik nennt statt einer Sache,
    nicht.

    Alle sechsundfünfzig tragen einen: Ein Dialog, in dem die Hälfte der Felder
    einen Tooltip hat, lehrt niemanden, dass es Tooltips gibt (Konsistenz vor
    Vollständigkeit). ``tests/test_print_settings_ui.py`` hält das fest."""


# **Eine Tabelle für Auswahlwerte, nicht zwei.** Hier stand eine eigene neben
# ``labels._CHOICE_NAMES``, mit demselben Funktionsnamen davor — die eine
# verdeckte die andere, und beide beschrifteten dieselben Schlüssel. Sie waren
# schon auseinandergelaufen: „cubic" hieß dort „Würfelgitter" und hier „Würfel",
# „none" dort „Ohne" und hier „Keine". Und zwei Werte hatte keine von beiden:
# Im deutschen Fenster stand „Wandbahnen: classic" und „arachne".
#
# Die Gebietsregel nennt den Ort eindeutig — „Der Name steht in
# ``_CHOICE_NAMES`` (``app/ui/labels.py``)" —, und ``tests/test_translations.py``
# prüft jetzt beide Feldquellen gegen diese eine Tabelle.
#
# **Und jeder Text hier steht mit ``_()``, nicht mit ``tr()``.** Die Tabelle
# ist ein Modulrumpf: ``tr()`` übersetzt sofort, also beim Import, in der
# Sprache, die dann gerade gilt — und das ist beim Start noch keine.
# ``main_window.py`` zieht dieses Modul auf Modulebene nach, ``app.py``
# installiert die Sprache danach; ein Sprachwechsel zur Laufzeit
# (``rebuild_for_language``) baut die Fenster neu und die Module nicht. Alle
# sechsundfünfzig Titel und alle sechsundfünfzig Sätze blieben damit in der
# Startsprache stehen — der größte Dialog der Anwendung, deutsch in einem
# englischen Fenster. ``_()`` gibt einen ``TranslatableText``, der seine
# Sprache erst beim ``str()`` sucht; aufgelöst wird in ``_label`` und
# ``_editor``. Dieselbe Umstellung wie in ``settings_dialog``.


FIELDS: tuple[Field, ...] = (
    # --- Schichten ---
    Field(
        "layers.layer_height",
        _("Schichthöhe"),
        "layers",
        unit="mm",
        minimum=0.02,
        maximum=1.2,
        step=0.02,
        decimals=3,
        note=_(
            "Wie dick jede Schicht ist. Weniger heißt feiner und länger: 0,2 mm ist der Alltag, "
            "0,12 mm für Sichtteile, 0,28 mm für Klötze."
        ),
    ),
    Field(
        "layers.first_layer_height",
        _("Schichthöhe erste Schicht"),
        "layers",
        unit="mm",
        minimum=0.02,
        maximum=1.2,
        step=0.02,
        decimals=3,
        note=_(
            "Die erste Schicht darf dicker sein — sie füllt Unebenheiten der Platte aus und hält "
            "damit besser."
        ),
    ),
    Field(
        "layers.line_width",
        _("Bahnbreite"),
        "layers",
        unit="mm",
        minimum=0.1,
        maximum=2.0,
        step=0.02,
        decimals=3,
        note=_(
            "Wie breit eine Bahn gelegt wird. Etwas mehr als der Düsendurchmesser ist normal: "
            "mehr trägt besser, weniger zeichnet feiner."
        ),
    ),
    Field(
        "layers.first_layer_line_width",
        _("Bahnbreite erste Schicht"),
        "layers",
        unit="mm",
        minimum=0.1,
        maximum=2.0,
        step=0.02,
        decimals=3,
        note=_("Breiter als die übrigen Bahnen — mehr Material auf dem Bett heißt mehr Haftung."),
    ),
    # --- Wände ---
    Field(
        "shell.wall_count",
        _("Wände"),
        "shell",
        kind="int",
        minimum=1,
        maximum=20,
        note=_(
            "Wie viele Bahnen die Außenhaut dick ist. Zwei halten die Form, drei oder vier tragen "
            "Last."
        ),
    ),
    Field(
        "shell.top_layers",
        _("Deckschichten"),
        "shell",
        kind="int",
        minimum=0,
        maximum=50,
        note=_(
            "Volle Schichten oben schließen die Füllung ab. Wie viele nötig sind, "
            "hängt von Schichthöhe und Füllmuster ab."
        ),
    ),
    Field(
        "shell.bottom_layers",
        _("Bodenschichten"),
        "shell",
        kind="int",
        minimum=0,
        maximum=50,
        note=_("Volle Schichten auf dem Bett. Sie bestimmen, wie glatt die Unterseite wird."),
    ),
    Field(
        "shell.outer_wall_first",
        _("Außenwand zuerst"),
        "shell",
        kind="bool",
        note=_(
            "Legt die Außenbahn vor der Innenbahn. Das trifft Maße genauer und stützt Überhänge "
            "schlechter."
        ),
    ),
    Field(
        "shell.seam_position",
        _("Naht"),
        "shell",
        kind="enum",
        choices=("aligned", "nearest", "random", "rear"),
        note=_(
            "Wo die Naht jeder Schicht sitzt — die Stelle, an der eine Bahn beginnt und endet. "
            "Ausgerichtet ergibt eine sichtbare Linie, zufällig verteilt sie sich."
        ),
    ),
    Field(
        "shell.scarf_seam",
        _("Schrägnaht"),
        "shell",
        kind="bool",
        note=_(
            "Setzt Anfang und Ende der Außenwand schräg übereinander. Das kann die "
            "Naht an runden Teilen weniger sichtbar machen und kostet etwas "
            "Druckzeit."
        ),
    ),
    Field(
        "shell.wall_generator",
        _("Wandbahnen"),
        "shell",
        kind="enum",
        choices=("classic", "arachne"),
        note=_(
            "Wie die Bahnen einer Wand verteilt werden. Arachne trifft schmale Stege, die auf "
            "keine ganze Bahnbreite passen; klassisch rechnet mit gleicher Breite und füllt den "
            "Rest."
        ),
    ),
    Field(
        "shell.precise_outer_wall",
        _("Außenwand auf Sollmaß"),
        "shell",
        kind="bool",
        note=_(
            "Rechnet die Außenwand auf ihr Sollmaß statt auf die Bahnmitte. Für Passungen "
            "richtig, sonst unnötig."
        ),
    ),
    Field(
        "shell.ironing",
        _("Oberfläche bügeln"),
        "shell",
        kind="bool",
        note=_(
            "Fährt die Oberseite ein zweites Mal ab und glättet sie mit wenig Material. Kostet "
            "Zeit und lohnt bei Sichtflächen."
        ),
    ),
    Field(
        "shell.ironing_topmost",
        _("Oberste Fläche bügeln"),
        "shell",
        kind="bool",
        note=_(
            "Bügelt nur die oberste Fläche, etwa den Deckel einer Box. Kostet weniger Zeit, "
            "als jede Oberseite zu bügeln."
        ),
    ),
    # --- Füllung ---
    Field(
        "infill.density",
        _("Fülldichte"),
        "infill",
        unit="%",
        minimum=0.0,
        maximum=100.0,
        step=5.0,
        decimals=0,
        factor=100.0,
        front=True,
        note=_(
            "Wie viel Material im Inneren steht. 15 % ist Alltag, 40 % für Belastung, 0 % ergibt "
            "einen hohlen Körper."
        ),
    ),
    Field(
        "infill.pattern",
        _("Füllmuster"),
        "infill",
        kind="enum",
        choices=("grid", "gyroid", "honeycomb", "cubic", "lines", "triangles"),
        note=_(
            "Wie die Füllung gelegt wird. Gyroid trägt in alle Richtungen gleich, Gitter ist "
            "schneller, Wabe liegt dazwischen."
        ),
    ),
    Field(
        "infill.angle",
        _("Füllwinkel"),
        "infill",
        unit=DEGREE_UNIT,
        minimum=0.0,
        maximum=180.0,
        step=5.0,
        decimals=1,
        note=_(
            "Um wie viel die Füllung gedreht liegt. Bahnen längs der Belastung tragen mehr "
            "als querlaufende — bei einem Teil, das in eine bekannte Richtung belastet wird, "
            "lohnt das Drehen."
        ),
    ),
    # --- Temperaturen ---
    Field(
        "temperature.nozzle",
        _("Düsentemperatur"),
        "temperature",
        kind="int",
        unit="°C",
        minimum=0,
        maximum=400,
        note=_(
            "Wie heiß die Düse ist. Zu kalt heißt schwache Schichtbindung, zu heiß bringt Fäden "
            "und weiche Überhänge."
        ),
    ),
    Field(
        "temperature.nozzle_first_layer",
        _("Düse, erste Schicht"),
        "temperature",
        kind="int",
        unit="°C",
        minimum=0,
        maximum=400,
        note=_("Meist etwas heißer als der Rest: Die erste Schicht soll auf dem Bett kleben."),
    ),
    Field(
        "temperature.bed",
        _("Betttemperatur"),
        "temperature",
        kind="int",
        unit="°C",
        minimum=0,
        maximum=150,
        note=_(
            "Wie warm das Bett ist. Die passende Temperatur hilft der Haftung und "
            "kann das Hochziehen der Ecken verringern."
        ),
    ),
    Field(
        "temperature.bed_first_layer",
        _("Bett, erste Schicht"),
        "temperature",
        kind="int",
        unit="°C",
        minimum=0,
        maximum=150,
        note=_("Für die erste Schicht darf das Bett wärmer sein als danach."),
    ),
    Field(
        "temperature.chamber",
        _("Kammer"),
        "temperature",
        kind="int",
        unit="°C",
        minimum=0,
        maximum=90,
        note=_(
            "Temperatur im beheizten Bauraum, sofern der Drucker sie regeln kann. "
            "Die Vorgabe kommt vom Materialprofil; ein geschlossenes Gehäuse "
            "allein heizt nicht aktiv."
        ),
    ),
    # --- Kühlung ---
    # Zwei Enden einer Kurve über der Schichtzeit, dazu ihre Schwelle — so
    # regeln alle drei Slicer-Familien den Lüfter. Ein Feld für beide Enden
    # hielt ihn fest: PLA lief in jeder Schicht voll (Befund Robert, 23.09.2026).
    Field(
        "cooling.fan_speed",
        _("Lüfter höchstens"),
        "cooling",
        unit="%",
        minimum=0.0,
        maximum=100.0,
        step=5.0,
        decimals=0,
        factor=100.0,
        note=_(
            "So stark kühlt der Lüfter kurze Schichten. Viel Kühlung gibt scharfe Kanten und "
            "schwächere Schichten; bei ABS deshalb wenig."
        ),
    ),
    Field(
        "cooling.minimum_fan_speed",
        _("Lüfter mindestens"),
        "cooling",
        unit="%",
        minimum=0.0,
        maximum=100.0,
        step=5.0,
        decimals=0,
        factor=100.0,
        note=_(
            "So stark läuft der Lüfter bei langen Schichten, nie mehr als der Höchstwert. "
            "Gleich hoch hält ihn fest, null schaltet ihn dort aus."
        ),
    ),
    Field(
        "cooling.fan_below_layer_time",
        _("Mehr Lüfter unter"),
        "cooling",
        unit="s",
        minimum=0.0,
        maximum=300.0,
        step=5.0,
        decimals=0,
        note=_(
            "Kürzere Schichten kühlt der Lüfter stärker als mit dem Mindestwert, bis zum "
            "Höchstwert bei der Mindestzeit je Schicht."
        ),
    ),
    Field(
        "cooling.bridge_fan_speed",
        _("Lüfter bei Brücken"),
        "cooling",
        unit="%",
        minimum=0.0,
        maximum=100.0,
        step=5.0,
        decimals=0,
        factor=100.0,
        note=_(
            "Über einer Brücke darf mehr gekühlt werden: Die Bahn hängt frei und soll schnell "
            "fest sein."
        ),
    ),
    Field(
        "cooling.disable_first_layers",
        _("Lüfter aus für Schichten"),
        "cooling",
        kind="int",
        minimum=0,
        maximum=20,
        note=_(
            "So viele Schichten bleiben ungekühlt. Der Lüfter würde die erste Schicht vom "
            "Bett lösen."
        ),
    ),
    Field(
        "cooling.minimum_layer_time",
        _("Mindestzeit je Schicht"),
        "cooling",
        unit="s",
        minimum=0.0,
        maximum=120.0,
        step=1.0,
        decimals=0,
        note=_(
            "Wie lange eine Schicht mindestens dauert. Bei kleinen Querschnitten bremst der "
            "Drucker, damit die vorige Schicht fest wird."
        ),
    ),
    Field(
        "cooling.minimum_speed",
        _("Mindesttempo beim Bremsen"),
        "cooling",
        unit="mm/s",
        minimum=1.0,
        maximum=100.0,
        step=1.0,
        decimals=0,
        note=_(
            "Langsamer wird der Drucker für die Mindestzeit nicht. Ist der Wert zu hoch, "
            "sind kleine Spitzen zu schnell fertig und werden weich."
        ),
    ),
    Field(
        "cooling.support_interface_cooling",
        _("Volle Kühlung an der Stütze"),
        "cooling",
        kind="bool",
        note=_(
            "Kühlt mit vollem Lüfter, wo Stütze und Teil sich berühren. Die Stütze löst sich "
            "leichter, vor allem bei PETG."
        ),
    ),
    # --- Geschwindigkeit ---
    Field(
        "speed.outer_wall",
        _("Außenwand"),
        "speed",
        unit="mm/s",
        minimum=1.0,
        maximum=1000.0,
        step=5.0,
        decimals=1,
        note=_("Tempo der sichtbaren Außenbahn. Langsamer heißt glatter und maßgenauer."),
    ),
    Field(
        "speed.inner_wall",
        _("Innenwand"),
        "speed",
        unit="mm/s",
        minimum=1.0,
        maximum=1000.0,
        step=5.0,
        decimals=1,
        note=_("Tempo der inneren Bahnen. Sie sieht niemand — hier darf es schneller sein."),
    ),
    Field(
        "speed.infill",
        _("Füllung"),
        "speed",
        unit="mm/s",
        minimum=1.0,
        maximum=1000.0,
        step=5.0,
        decimals=1,
        note=_("Tempo der Füllung. Nach oben begrenzt sie ohnehin der höchste Volumenstrom."),
    ),
    Field(
        "speed.top_surface",
        _("Oberfläche", context="Druckgeschwindigkeit"),
        "speed",
        unit="mm/s",
        minimum=1.0,
        maximum=1000.0,
        step=5.0,
        decimals=1,
        note=_("Tempo der Deckschichten. Langsam macht die Oberseite gleichmäßig."),
    ),
    Field(
        "speed.first_layer",
        _("Erste Schicht"),
        "speed",
        unit="mm/s",
        minimum=1.0,
        maximum=1000.0,
        step=5.0,
        decimals=1,
        note=_("Tempo der ersten Schicht. Langsam heißt haften."),
    ),
    Field(
        "speed.travel",
        _("Leerfahrt"),
        "speed",
        unit="mm/s",
        minimum=1.0,
        maximum=1000.0,
        step=10.0,
        decimals=0,
        note=_("Tempo ohne Material. Schnell spart Zeit und schüttelt den Drucker mehr."),
    ),
    Field(
        "speed.bridge",
        _("Brücken"),
        "speed",
        unit="mm/s",
        minimum=1.0,
        maximum=200.0,
        step=5.0,
        decimals=1,
        note=_("Tempo über einer Brücke. Zu langsam hängt durch, zu schnell reißt."),
    ),
    Field(
        "speed.acceleration",
        _("Beschleunigung"),
        "speed",
        unit="mm/s²",
        minimum=100.0,
        maximum=30000.0,
        step=500.0,
        decimals=0,
        note=_("Wie hart der Drucker beschleunigt. Weniger heißt sauberere Ecken und mehr Zeit."),
    ),
    Field(
        "speed.outer_wall_acceleration",
        _("Beschleunigung Außenwand"),
        "speed",
        unit="mm/s²",
        minimum=100.0,
        maximum=30000.0,
        step=500.0,
        decimals=0,
        note=_(
            "Beschleunigung nur für die Außenbahn. Hier lohnt es, weniger zu nehmen als überall "
            "sonst."
        ),
    ),
    # --- Stützen ---
    Field(
        "support.style",
        _("Stützen"),
        "support",
        kind="enum",
        choices=("none", "auto", "grid", "tree"),
        front=True,
        choice_notes=(("auto", _("Stützen an. Welche Art, bestimmt das Profil Ihres Slicers.")),),
        note=_(
            "Ob und wie gestützt wird. Automatisch nimmt die Art aus dem Profil Ihres Slicers. "
            "Baum braucht weniger Material und lässt sich leichter abnehmen, Gitter trägt "
            "schwere Überhänge sicherer."
        ),
    ),
    Field(
        "support.placement",
        _("Stützen ansetzen"),
        "support",
        kind="enum",
        choices=("everywhere", "build_plate"),
        note=_(
            "Wo Stützen ansetzen dürfen. Nur vom Bett lässt das Modell selbst unberührt; "
            "überall stützt auch mitten darauf und hinterlässt Spuren."
        ),
    ),
    Field(
        "support.threshold_angle",
        _("Ab Winkel"),
        "support",
        unit=DEGREE_UNIT,
        minimum=0.0,
        maximum=90.0,
        step=5.0,
        decimals=1,
        note=_(
            "Ab welcher Neigung gestützt wird, gemessen zur Senkrechten. Was steiler steht, trägt "
            "sich selbst — wie steil, sagt der Überhangfächer."
        ),
    ),
    Field(
        "support.z_gap",
        _("Abstand oben und unten"),
        "support",
        unit="mm",
        minimum=0.0,
        maximum=2.0,
        step=0.05,
        decimals=2,
        note=_(
            "Luft zwischen Stütze und Teil, oben wie unten. Mehr heißt leichter abnehmen und "
            "rauere Fläche."
        ),
    ),
    Field(
        "support.xy_gap",
        _("Abstand zur Seite"),
        "support",
        unit="mm",
        minimum=0.0,
        maximum=5.0,
        step=0.1,
        decimals=2,
        note=_("Luft zwischen Stütze und Teil zur Seite. Zu wenig verschweißt beides miteinander."),
    ),
    Field(
        "support.density",
        _("Stützdichte"),
        "support",
        unit="%",
        # Kleinster positiver ganzzahliger Prozentwert (RM-475).
        minimum=print_settings.LEAST_SUPPORT_DENSITY * 100.0,
        maximum=100.0,
        step=5.0,
        decimals=0,
        factor=100.0,
        note=_(
            "Wie dicht die Stütze steht, von 1 bis 100 %. Dichter trägt mehr und ist schwerer "
            "abzunehmen. Für einen Druck ohne Stützen wählen Sie bei „Stützen“ die Option „Keine“."
        ),
    ),
    Field(
        "support.interface_layers",
        _("Trennschichten"),
        "support",
        kind="int",
        minimum=0,
        maximum=10,
        note=_(
            "Dichte Schichten zwischen Stütze und Teil. Sie machen die gestützte Fläche glatter."
        ),
    ),
    Field(
        "support.bottom_interface_layers",
        _("Trennschichten unten"),
        "support",
        kind="int",
        minimum=0,
        maximum=10,
        note=_(
            "Dichte Schichten, wo die Stütze auf dem Teil steht. Ohne sie zeichnet ihr Fuß die "
            "Fläche darunter."
        ),
    ),
    Field(
        "support.interface_spacing",
        _("Lücke in der Trennschicht"),
        "support",
        unit="mm",
        minimum=0.0,
        maximum=2.0,
        step=0.05,
        decimals=2,
        note=_(
            "Abstand der Linien in der Trennschicht. Eng gibt glatte flache Unterseiten, weit "
            "löst sich an kleinen und runden Flächen leichter."
        ),
    ),
    Field(
        "support.block_channels",
        _("Kanäle frei halten"),
        "support",
        kind="bool",
        note=_(
            "Sperrt Stützen in schmalen Kanälen und Rohren. Dort kämen sie nicht mehr heraus, "
            "und die Decken tragen sich selbst."
        ),
    ),
    Field(
        "support.spare_ledges",
        _("Ränder ohne Stütze"),
        "support",
        kind="bool",
        note=_(
            "Sperrt Stützen unter Rändern, die nur wenige Millimeter überstehen. Sie tragen "
            "sich selbst, und jede Stütze dort hinterließe eine Narbe."
        ),
    ),
    # --- Haftung ---
    Field(
        "adhesion.kind",
        _("Druckbetthaftung"),
        "adhesion",
        kind="enum",
        choices=("none", "auto", "skirt", "brim", "raft"),
        choice_notes=(
            (
                "auto",
                _(
                    "Ihr Slicer entscheidet je Teil. Bei PrusaSlicer und Cura gilt Solidons "
                    "Vorgabe für das Material."
                ),
            ),
        ),
        note=_(
            "Was zusätzlich aufs Bett kommt, damit das Teil hält. Automatisch entscheidet der "
            "Slicer nach Teil und Material. Brim legt einen Rand an, Raft eine Unterlage; "
            "Skirt berührt das Teil nicht und hält nur die Düse im Fluss."
        ),
    ),
    Field(
        "adhesion.skirt_loops",
        _("Skirt-Runden"),
        "adhesion",
        kind="int",
        minimum=0,
        maximum=20,
        note=_("Wie viele Runden neben dem Teil gelegt werden, ohne es zu berühren."),
    ),
    Field(
        "adhesion.skirt_distance",
        _("Skirt-Abstand"),
        "adhesion",
        unit="mm",
        minimum=0.0,
        maximum=50.0,
        step=0.5,
        decimals=1,
        note=_("Wie weit diese Runden vom Teil entfernt liegen."),
    ),
    Field(
        "adhesion.brim_width",
        _("Brim-Breite"),
        "adhesion",
        unit="mm",
        minimum=0.0,
        maximum=50.0,
        step=0.5,
        decimals=1,
        note=_(
            "Wie breit der angelegte Rand ist. Mehr hält besser und muss hinterher abgeschnitten "
            "werden."
        ),
    ),
    Field(
        "adhesion.brim_gap",
        _("Brim-Abstand"),
        "adhesion",
        unit="mm",
        minimum=0.0,
        maximum=5.0,
        step=0.05,
        decimals=2,
        note=_(
            "Abstand zwischen Rand und Teil. Null verbindet beide für besseren Halt; "
            "etwas Abstand erleichtert das Ablösen."
        ),
    ),
    Field(
        "adhesion.raft_layers",
        _("Raft-Schichten"),
        "adhesion",
        kind="int",
        minimum=0,
        maximum=20,
        note=_("Wie viele Schichten die Unterlage hat, auf der das Teil steht."),
    ),
    Field(
        "adhesion.raft_gap",
        _("Abstand zum Raft"),
        "adhesion",
        unit="mm",
        minimum=0.0,
        maximum=2.0,
        step=0.05,
        decimals=2,
        note=_(
            "Luft zwischen der Unterlage und der ersten Schicht des Teils. "
            "Ohne eigene Zahl bleibt die Vorgabe des Slicers."
        ),
    ),
    # --- Rückzug ---
    Field(
        "retraction.length",
        _("Rückzug"),
        "retraction",
        unit="mm",
        minimum=0.0,
        maximum=10.0,
        step=0.1,
        decimals=2,
        note=_(
            "Wie weit das Filament zurückgezogen wird, bevor die Düse leer fährt. Das Mittel "
            "gegen Fäden."
        ),
    ),
    Field(
        "retraction.speed",
        _("Rückzugstempo"),
        "retraction",
        unit="mm/s",
        minimum=1.0,
        maximum=200.0,
        step=5.0,
        decimals=0,
        note=_(
            "Wie schnell zurückgezogen wird. Zu schnell mahlt das Antriebsrad ins Filament, zu "
            "langsam zieht Fäden."
        ),
    ),
    Field(
        "retraction.z_hop",
        _("Z-Sprung"),
        "retraction",
        unit="mm",
        minimum=0.0,
        maximum=5.0,
        step=0.05,
        decimals=2,
        note=_(
            "Wie weit die Düse anhebt, bevor sie leer fährt. Sie stößt dann nicht an schon "
            "Gedrucktes."
        ),
    ),
    Field(
        "retraction.wipe",
        _("Abstreifen"),
        "retraction",
        kind="bool",
        note=_("Wischt die Düse am Teil ab, bevor sie wegfährt. Weniger Nasen, etwas mehr Zeit."),
    ),
    Field(
        "retraction.avoid_crossing_walls",
        _("Wände nicht überfahren"),
        "retraction",
        kind="bool",
        note=_(
            "Führt Leerfahrten um Wände herum statt darüber. Weniger Narben auf der Oberfläche, "
            "längere Wege."
        ),
    ),
    # --- Filament ---
    # **Nicht vorn**, und der Grund ist die Spule: Sobald ein Teil einen
    # Materialslot mit eigener Farbe trägt, überschreibt ``handover`` diesen
    # Wert damit — die Farbe gehört dorthin, wo sie gewählt wird. Zwei Orte für
    # dieselbe Auskunft heißen raten, welcher gilt (Robert, 30.08.2026). Im
    # Modell bleibt sie: Ein Teil ganz ohne Spule hat sonst keine Farbe für den
    # Slicer, und ein Rückfall gehört nach hinten, nicht auf die Vorderseite.
    Field(
        "filament.colour",
        _("Farbe ohne eigene Spule"),
        "filament",
        kind="colour",
        note=_(
            "Gilt nur, solange das Teil keine eingefärbte Spule hat — dann steht hier, womit "
            "der Slicer rechnet. Sobald Sie im Filamentwähler eine Farbe setzen oder über "
            "„Filament auf eine Fläche“ arbeiten, gilt die Spule."
        ),
    ),
    Field(
        "filament.diameter",
        _("Filamentdurchmesser"),
        "filament",
        unit="mm",
        minimum=1.0,
        maximum=4.0,
        step=0.05,
        decimals=2,
        note=_("Der Durchmesser des Filaments, wie die Rolle ihn angibt — 1,75 mm oder 2,85 mm."),
    ),
    Field(
        "filament.density",
        _("Dichte"),
        "filament",
        unit="g/cm³",
        minimum=0.5,
        maximum=3.0,
        step=0.01,
        decimals=2,
        note=_("Dichte des Materials. Daraus rechnet die Schätzung das Gewicht."),
    ),
    Field(
        "filament.flow_ratio",
        _("Flussfaktor"),
        "filament",
        minimum=0.5,
        maximum=1.5,
        step=0.01,
        decimals=3,
        note=_(
            "Feinkorrektur der Materialmenge. Über 1 legt mehr, darunter weniger — geändert wird "
            "das nach einem gemessenen Prüfwürfel."
        ),
    ),
    Field(
        "filament.max_flow",
        _("Höchster Volumenstrom"),
        "filament",
        unit="mm³/s",
        minimum=0.5,
        maximum=60.0,
        step=0.5,
        decimals=1,
        note=_(
            "Wie viel Material die Düse je Sekunde schafft. Diese Grenze bremst jedes Tempo, das "
            "mehr verlangt."
        ),
    ),
    Field(
        "filament.cost_per_kg",
        _("Preis je Kilogramm"),
        "filament",
        minimum=0.0,
        maximum=1000.0,
        step=1.0,
        decimals=2,
        note=_("Was ein Kilogramm kostet. Nur für die Kostenschätzung."),
    ),
)


#: Die Felder nach Punktpfad — für Beschriftung und Wertanzeige außerhalb des
#: Dialogs (:func:`setting_title`, :func:`shown_value`).
_FIELD_OF: Final[dict[str, Field]] = {field.path: field for field in FIELDS}


def field_of(path: str) -> Field | None:
    """Das Feld zu einem Punktpfad — ``None``, wo der Dialog keines zeigt."""
    return _FIELD_OF.get(path)


def setting_title(path: str) -> str:
    """Wie der Dialog eine Einstellung nennt — Prüfbericht und Kommandozeile
    nennen sie genauso.

    Ein Pfad, den kein Feld trägt, bleibt stehen: mehr als nichts, und ein
    Test sieht ihn.
    """
    field = _FIELD_OF.get(path)
    return str(field.title) if field is not None else path


def _decimal(text: str) -> str:
    """Das Dezimalzeichen der Anzeigesprache in einer fertig formatierten Zahl."""
    return text.replace(".", decimal_separator())


def _choice(value: str) -> str:
    from app.core.registry.surfaces import choice_label

    return choice_label(value)


def shown_value(
    path: str,
    value: object,
    *,
    localise: Callable[[str], str] = _decimal,
    choice: Callable[[str], str] = _choice,
) -> str:
    """Ein Wert so, wie er im Feld daneben steht — sonst schlägt der Vorschlag
    etwas vor, das der Nutzer nicht wiedererkennt, und der Prüfbericht nennt
    nach dem Export einen anderen Wert als der Dialog davor.

    ``localise`` setzt das Dezimalzeichen, ``choice`` beschriftet Wahlen; die
    Oberfläche reicht ihre eigenen herein (Anzeigeeinheit, ``QLocale``), die
    Kommandozeile nimmt die des Kerns.
    """
    field = _FIELD_OF.get(path)
    if path == "adhesion.raft_gap" and value is None:
        return str(tr("Vorgabe des Slicers"))
    if isinstance(value, str):
        return choice(value)
    # Vor der Zahl, denn ``True`` ist auch ein ``int``: Ein Haken stand
    # hier als „0 → 1".
    if isinstance(value, bool):
        return str(tr("an") if value else tr("aus"))
    if field is not None and isinstance(value, int | float):
        # Mit den Nachkommastellen und dem Komma des Felds daneben — ``:g``
        # schrieb „0.16 mm" neben „0,160 mm" und „59.5238 mm/s".
        decimals = 0 if field.kind == "int" else field.decimals
        number = localise(f"{float(value) * field.factor:.{decimals}f}")
        return f"{number} {field.unit}".strip()
    return str(value)
