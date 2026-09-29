"""Trägt die drei Sätze von RM-279 (ii) in die fünf Kataloge ein (einmalig)."""

import io
import json
import sys

TREE = sys.argv[1]
CHAMFER = (
    "Einige Kanten dieser Auswahl sind nicht gefast: Neben ihnen ist die Fläche zu "
    "schmal für diese Breite. Dort passt nur eine Breite unter {largest}. Die "
    "übrigen Kanten sind gefast. Soll die Fase auch dort sitzen, wählen Sie eine "
    "kleinere Breite."
)
LAW = (
    "Einige Kanten dieser Auswahl sind nicht verrundet: Neben ihnen ist die Fläche "
    "zu schmal für diese Radien. Dort passt nur ein größter Radius unter {largest}. "
    "Die übrigen Kanten sind verrundet. Soll die Rundung auch dort sitzen, "
    "verkleinern Sie die Radien."
)
FILLET = (
    "Einige Kanten dieser Auswahl sind nicht verrundet: Neben ihnen ist die Fläche "
    "zu schmal für diesen Radius. Dort passt nur ein Radius unter {largest}. Die "
    "übrigen Kanten sind verrundet. Soll die Rundung auch dort sitzen, wählen Sie "
    "einen kleineren Radius."
)
TEXTS = {
    "en": {
        CHAMFER: "Some edges of this selection are not chamfered: the face beside them is too narrow for this width. Only a width under {largest} fits there. The other edges are chamfered. If the chamfer should sit there too, choose a smaller width.",
        LAW: "Some edges of this selection are not rounded: the face beside them is too narrow for these radii. Only a largest radius under {largest} fits there. The other edges are rounded. If the fillet should sit there too, reduce the radii.",
        FILLET: "Some edges of this selection are not rounded: the face beside them is too narrow for this radius. Only a radius under {largest} fits there. The other edges are rounded. If the fillet should sit there too, choose a smaller radius.",
    },
    "es": {
        CHAMFER: "Algunas aristas de esta selección no están achaflanadas: la cara junto a ellas es demasiado estrecha para este ancho. Allí solo cabe un ancho inferior a {largest}. Las demás aristas están achaflanadas. Si el chaflán también debe ir allí, elija un ancho menor.",
        LAW: "Algunas aristas de esta selección no están redondeadas: la cara junto a ellas es demasiado estrecha para estos radios. Allí solo cabe un radio máximo inferior a {largest}. Las demás aristas están redondeadas. Si el redondeo también debe ir allí, reduzca los radios.",
        FILLET: "Algunas aristas de esta selección no están redondeadas: la cara junto a ellas es demasiado estrecha para este radio. Allí solo cabe un radio inferior a {largest}. Las demás aristas están redondeadas. Si el redondeo también debe ir allí, elija un radio menor.",
    },
    "fr": {
        CHAMFER: "Certaines arêtes de cette sélection ne sont pas chanfreinées : la face voisine est trop étroite pour cette largeur. Seule une largeur inférieure à {largest} y tient. Les autres arêtes sont chanfreinées. Si le chanfrein doit aussi s’y trouver, choisissez une largeur plus petite.",
        LAW: "Certaines arêtes de cette sélection ne sont pas arrondies : la face voisine est trop étroite pour ces rayons. Seul un plus grand rayon inférieur à {largest} y tient. Les autres arêtes sont arrondies. Si l’arrondi doit aussi s’y trouver, réduisez les rayons.",
        FILLET: "Certaines arêtes de cette sélection ne sont pas arrondies : la face voisine est trop étroite pour ce rayon. Seul un rayon inférieur à {largest} y tient. Les autres arêtes sont arrondies. Si l’arrondi doit aussi s’y trouver, choisissez un rayon plus petit.",
    },
    "it": {
        CHAMFER: "Alcuni spigoli di questa selezione non sono smussati: la faccia accanto è troppo stretta per questa larghezza. Lì entra solo una larghezza inferiore a {largest}. Gli altri spigoli sono smussati. Se lo smusso deve esserci anche lì, scegli una larghezza minore.",
        LAW: "Alcuni spigoli di questa selezione non sono arrotondati: la faccia accanto è troppo stretta per questi raggi. Lì entra solo un raggio massimo inferiore a {largest}. Gli altri spigoli sono arrotondati. Se il raccordo deve esserci anche lì, riduci i raggi.",
        FILLET: "Alcuni spigoli di questa selezione non sono arrotondati: la faccia accanto è troppo stretta per questo raggio. Lì entra solo un raggio inferiore a {largest}. Gli altri spigoli sono arrotondati. Se il raccordo deve esserci anche lì, scegli un raggio minore.",
    },
    "pt": {
        CHAMFER: "Algumas arestas desta seleção não estão chanfradas: a face ao lado é demasiado estreita para esta largura. Ali só cabe uma largura inferior a {largest}. As restantes arestas estão chanfradas. Se o chanfro também deve ficar ali, escolha uma largura menor.",
        LAW: "Algumas arestas desta seleção não estão arredondadas: a face ao lado é demasiado estreita para estes raios. Ali só cabe um raio máximo inferior a {largest}. As restantes arestas estão arredondadas. Se o arredondamento também deve ficar ali, reduza os raios.",
        FILLET: "Algumas arestas desta seleção não estão arredondadas: a face ao lado é demasiado estreita para este raio. Ali só cabe um raio inferior a {largest}. As restantes arestas estão arredondadas. Se o arredondamento também deve ficar ali, escolha um raio menor.",
    },
}
for language, entries in TEXTS.items():
    path = f"{TREE}/app/i18n/locales/{language}.json"
    raw = io.open(path, encoding="utf-8", newline="").read()
    for key, value in entries.items():
        old = "  " + json.dumps(key, ensure_ascii=False) + ': ""'
        assert raw.count(old) == 1, (language, key[:40])
        raw = raw.replace(
            old, "  " + json.dumps(key, ensure_ascii=False) + ": " + json.dumps(value, ensure_ascii=False)
        )
    json.loads(raw)
    io.open(path, "w", encoding="utf-8", newline="").write(raw)
    print(language, "ok")
