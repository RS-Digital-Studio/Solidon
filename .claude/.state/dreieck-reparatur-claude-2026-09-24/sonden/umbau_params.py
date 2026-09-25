from pathlib import Path

path = Path("app/core/geom/ops.py")
text = path.read_text(encoding="utf-8")
start = text.index("@op_params\nclass RepairParams(BaseParams):")
end = text.index('@register_op(\n    name="repair",')
new = '''@op_params
class RepairParams(BaseParams):
    """Was *Reparieren* tut.

    **Vorn steht, was nach dem Einlesen noch etwas ändert** (Durchsicht
    24.09.2026). Verschweißen, leere Dreiecke und Außenseiten erledigt schon
    der Import; vorn stand allein das Lochfüllen, das er ebenfalls fährt, und
    die zwei Schalter, die danach noch wirken, lagen hinter der Klappe.
    """

    fill_holes: bool = param(
        title=_("Offene Stellen schließen"),
        default=True,
        doc=_("Schließt Löcher. Große Öffnungen nennt der Prüfbericht."),
    )
    #: **Vorgabe an** (Entscheidung Robert, 24.09.2026). Die Suche läuft beim
    #: Reparieren ohnehin; aufgelöst wird nur, was die Nachprüfung als
    #: schnittfrei belegt, sonst bleibt das Teil unverändert. Ältere Schritte
    #: ohne diesen Wert behalten über die Migration 34 → 35 „aus".
    self_intersections: bool = param(
        title=_("Überschneidungen auflösen"),
        default=True,
        doc=_(
            "Verschmilzt Teile, die ineinanderstecken. Was nicht sicher geht, bleibt unverändert."
        ),
    )
    small_components: bool = param(
        title=_("Kleinstteile entfernen"),
        default=False,
        doc=_("Entfernt lose Splitter, die viel kleiner sind als das Hauptteil."),
    )
    weld: bool = param(
        title=_("Punkte verschweißen"),
        default=True,
        placement="advanced",
        doc=_(
            "Führt Punkte zusammen, die praktisch aufeinanderliegen. Der häufigste "
            "Grund dafür, dass ein Netz aus mehreren Teilen zu bestehen scheint."
        ),
    )
    degenerate: bool = param(
        title=_("Leere Dreiecke entfernen"),
        default=True,
        placement="advanced",
        doc=_("Dreiecke ohne Fläche. Sie stören jede spätere Rechnung und tragen nichts."),
    )
    normals: bool = param(
        title=_("Außenseiten angleichen"),
        default=True,
        placement="advanced",
        doc=_("Richtet aus, wo außen ist. Ohne das erscheinen Flächen dunkel oder verschwinden."),
    )


'''
text = text[:start] + new + text[end:]
text = text.replace('''    name="repair",
    cache_version="2",''', '''    name="repair",
    cache_version="3",''', 1)
text = text.replace(
    '''    doc=_("Schließt Löcher, entfernt entartete Dreiecke und richtet die Flächen aus."),
)
def repair_object''',
    '''    doc=_(
        "Schließt Löcher, entfernt fehlerhafte Dreiecke, gleicht die Außenseiten an und "
        "löst Überschneidungen auf."
    ),
)
def repair_object''',
    1,
)
path.write_text(text, encoding="utf-8", newline="\n")
print("ok")
