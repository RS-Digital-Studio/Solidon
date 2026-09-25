"""Einmalig: die Reparaturtexte der Durchsicht vom 24.09.2026 in alle Kataloge.

Lesen, ändern, schreiben — je Sprache einmal. Verwaiste Schlüssel gehen,
neue kommen dazu; der Schlüssel der Nachbarsitzung (lokale Erkennung, B5)
mit ihren eigenen Übersetzungen.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from app.i18n.catalog import read_catalog, write_catalog  # noqa: E402

LANGS = ("en", "es", "fr", "it", "pt")
SLICER_EN = " Many slicers still print such places correctly."

T: dict[str, tuple[str, str, str, str, str]] = {
    "An einer Kante hängt eine überzählige Fläche, die sich nicht sicher entfernen ließ.": (
        "One edge carries a surplus face that could not be removed safely.",
        "En una arista queda una cara sobrante que no se ha podido eliminar con seguridad.",
        "Une arête porte une face en trop qui n’a pas pu être supprimée sans risque.",
        "Su uno spigolo resta una faccia in eccesso che non è stato possibile rimuovere in sicurezza.",
        "Numa aresta fica uma face excedente que não foi possível remover com segurança.",
    ),
    "An einer Kante zeigen die Außenseiten gegeneinander.": (
        "At one edge the outer sides face each other.",
        "En una arista los lados exteriores se oponen entre sí.",
        "Sur une arête, les faces extérieures sont tournées l’une contre l’autre.",
        "Su uno spigolo i lati esterni sono rivolti l’uno contro l’altro.",
        "Numa aresta os lados exteriores estão virados um contra o outro.",
    ),
    "An {edges} Kanten hängen überzählige Flächen, die sich nicht sicher entfernen ließen.": (
        "{edges} edges carry surplus faces that could not be removed safely.",
        "En {edges} aristas quedan caras sobrantes que no se han podido eliminar con seguridad.",
        "{edges} arêtes portent des faces en trop qui n’ont pas pu être supprimées sans risque.",
        "Su {edges} spigoli restano facce in eccesso che non è stato possibile rimuovere in sicurezza.",
        "Em {edges} arestas ficam faces excedentes que não foi possível remover com segurança.",
    ),
    "An {edges} Kanten zeigen die Außenseiten gegeneinander.": (
        "At {edges} edges the outer sides face each other.",
        "En {edges} aristas los lados exteriores se oponen entre sí.",
        "Sur {edges} arêtes, les faces extérieures sont tournées l’une contre l’autre.",
        "Su {edges} spigoli i lati esterni sono rivolti l’uno contro l’altro.",
        "Em {edges} arestas os lados exteriores estão virados um contra o outro.",
    ),
    "Außenseiten gegeneinander": (
        "outer sides facing each other",
        "lados exteriores opuestos",
        "faces extérieures opposées",
        "lati esterni contrapposti",
        "lados exteriores opostos",
    ),
    "Das Modell ist eine Fläche ohne Dicke.": (
        "The model is a surface without thickness.",
        "El modelo es una superficie sin grosor.",
        "Le modèle est une surface sans épaisseur.",
        "Il modello è una superficie senza spessore.",
        "O modelo é uma superfície sem espessura.",
    ),
    "Dicke geben": (
        "Give it thickness",
        "Dar grosor",
        "Donner une épaisseur",
        "Dai spessore",
        "Dar espessura",
    ),
    "Die Außenseiten wurden angeglichen.": (
        "The outer sides were aligned.",
        "Se han igualado los lados exteriores.",
        "Les faces extérieures ont été harmonisées.",
        "I lati esterni sono stati uniformati.",
        "Os lados exteriores foram igualados.",
    ),
    "Die Oberfläche kreuzt sich selbst. Viele Slicer drucken solche Stellen trotzdem richtig.": (
        "The surface crosses itself." + SLICER_EN,
        "La superficie se cruza consigo misma. Muchos slicers imprimen bien estas zonas de todos modos.",
        "La surface se croise elle-même. Beaucoup de slicers impriment malgré tout correctement ces endroits.",
        "La superficie si interseca con se stessa. Molti slicer stampano comunque correttamente questi punti.",
        "A superfície cruza-se consigo mesma. Muitos slicers imprimem mesmo assim corretamente esses pontos.",
    ),
    "Die Suche nach Überschneidungen wurde vorzeitig beendet; es kann weitere geben.": (
        "The search for overlaps stopped early; there may be more.",
        "La búsqueda de solapamientos terminó antes de tiempo; puede haber más.",
        "La recherche de recouvrements s’est arrêtée plus tôt ; il peut y en avoir d’autres.",
        "La ricerca delle sovrapposizioni si è fermata prima; potrebbero essercene altre.",
        "A procura de sobreposições terminou antes do tempo; pode haver mais.",
    ),
    "Die Suche nach Überschneidungen wurde vorzeitig beendet; es kann welche geben.": (
        "The search for overlaps stopped early; there may be some.",
        "La búsqueda de solapamientos terminó antes de tiempo; puede haber alguno.",
        "La recherche de recouvrements s’est arrêtée plus tôt ; il peut y en avoir.",
        "La ricerca delle sovrapposizioni si è fermata prima; potrebbero esserci.",
        "A procura de sobreposições terminou antes do tempo; pode haver algumas.",
    ),
    "Die Überschneidungen ließen sich nicht sicher auflösen. Viele Slicer drucken solche Stellen trotzdem richtig.": (
        "The overlaps could not be resolved safely." + SLICER_EN,
        "Los solapamientos no se han podido resolver con seguridad. Muchos slicers imprimen bien estas zonas de todos modos.",
        "Les recouvrements n’ont pas pu être résolus sans risque. Beaucoup de slicers impriment malgré tout correctement ces endroits.",
        "Non è stato possibile risolvere le sovrapposizioni in sicurezza. Molti slicer stampano comunque correttamente questi punti.",
        "Não foi possível resolver as sobreposições com segurança. Muitos slicers imprimem mesmo assim corretamente esses pontos.",
    ),
    "Doppelte Dreiecke wurden entfernt.": (
        "Duplicate triangles were removed.",
        "Se han eliminado los triángulos duplicados.",
        "Les triangles en double ont été supprimés.",
        "I triangoli doppi sono stati rimossi.",
        "Os triângulos duplicados foram removidos.",
    ),
    "Doppelte Punkte blieben stehen, weil das Verschweißen das Modell aufgerissen hätte.": (
        "Duplicate points were kept because welding them would have torn the model open.",
        "Los puntos duplicados se han mantenido porque soldarlos habría abierto el modelo.",
        "Les points en double ont été conservés, car les souder aurait déchiré le modèle.",
        "I punti doppi sono rimasti perché saldarli avrebbe aperto il modello.",
        "Os pontos duplicados foram mantidos porque soldá-los teria rompido o modelo.",
    ),
    "Ein Kleinstteil wurde entfernt.": (
        "One stray fragment was removed.",
        "Se ha eliminado un fragmento suelto.",
        "Un fragment parasite a été supprimé.",
        "È stato rimosso un frammento minuscolo.",
        "Foi removido um fragmento solto.",
    ),
    "Ein Loch wurde geschlossen.": (
        "One hole was closed.",
        "Se ha cerrado un agujero.",
        "Un trou a été fermé.",
        "È stato chiuso un foro.",
        "Foi fechado um buraco.",
    ),
    "Ein Teil des Modells ist eine Fläche ohne Dicke.": (
        "Part of the model is a surface without thickness.",
        "Una parte del modelo es una superficie sin grosor.",
        "Une partie du modèle est une surface sans épaisseur.",
        "Una parte del modello è una superficie senza spessore.",
        "Uma parte do modelo é uma superfície sem espessura.",
    ),
    "Ein loser Splitter wurde entfernt.": (
        "One loose sliver was removed.",
        "Se ha eliminado una astilla suelta.",
        "Un éclat isolé a été supprimé.",
        "È stata rimossa una scheggia isolata.",
        "Foi removida uma lasca solta.",
    ),
    "Eine große Öffnung wurde mit einer neuen Fläche geschlossen.": (
        "One large opening was closed with a new surface.",
        "Se ha cerrado una abertura grande con una superficie nueva.",
        "Une grande ouverture a été fermée par une nouvelle surface.",
        "Un’apertura grande è stata chiusa con una superficie nuova.",
        "Uma abertura grande foi fechada com uma superfície nova.",
    ),
    "Eine offene Stelle ließ sich nicht sicher schließen.": (
        "One open place could not be closed safely.",
        "Una zona abierta no se ha podido cerrar con seguridad.",
        "Un endroit ouvert n’a pas pu être fermé sans risque.",
        "Non è stato possibile chiudere in sicurezza un punto aperto.",
        "Não foi possível fechar com segurança um ponto aberto.",
    ),
    "Eine überzählige Fläche an einer Kante wurde entfernt.": (
        "One surplus face at an edge was removed.",
        "Se ha eliminado una cara sobrante en una arista.",
        "Une face en trop sur une arête a été supprimée.",
        "È stata rimossa una faccia in eccesso su uno spigolo.",
        "Foi removida uma face excedente numa aresta.",
    ),
    "Entfernt lose Splitter, die viel kleiner sind als das Hauptteil.": (
        "Removes loose slivers that are much smaller than the main part.",
        "Elimina las astillas sueltas mucho más pequeñas que la pieza principal.",
        "Supprime les éclats isolés bien plus petits que la pièce principale.",
        "Rimuove le schegge isolate molto più piccole della parte principale.",
        "Remove as lascas soltas muito mais pequenas do que a peça principal.",
    ),
    "Hier gibt es kein ganzes Merkmal, und für einen größeren Suchradius ist das Netz zu fein. Wählen Sie eine andere Stelle oder verringern Sie die Dreiecke.": (
        "There is no whole feature here, and the mesh is too fine for a larger search radius. Choose another location or reduce the triangles.",
        "Aquí no hay ningún detalle entero, y la malla es demasiado fina para un radio de búsqueda mayor. Elija otra ubicación o reduzca los triángulos.",
        "Il n’y a ici aucun élément entier, et le maillage est trop fin pour un rayon de recherche plus grand. Choisissez un autre emplacement ou réduisez les triangles.",
        "Qui non c’è nessun elemento intero, e la mesh è troppo fine per un raggio di ricerca maggiore. Scegli un altro punto o riduci i triangoli.",
        "Aqui não há nenhum elemento inteiro, e a malha é fina demais para um raio de pesquisa maior. Escolha outro local ou reduza os triângulos.",
    ),
    "Kleinstteile entfernen": (
        "Remove stray fragments",
        "Eliminar fragmentos sueltos",
        "Supprimer les fragments parasites",
        "Rimuovi i frammenti minuscoli",
        "Remover fragmentos soltos",
    ),
    "Leere Dreiecke blieben stehen, weil ihr Entfernen das Modell aufgerissen hätte.": (
        "Empty triangles were kept because removing them would have torn the model open.",
        "Los triángulos vacíos se han mantenido porque eliminarlos habría abierto el modelo.",
        "Les triangles vides ont été conservés, car les supprimer aurait déchiré le modèle.",
        "I triangoli vuoti sono rimasti perché rimuoverli avrebbe aperto il modello.",
        "Os triângulos vazios foram mantidos porque removê-los teria rompido o modelo.",
    ),
    "Leere Dreiecke entfernen": (
        "Remove empty triangles",
        "Eliminar triángulos vacíos",
        "Supprimer les triangles vides",
        "Rimuovi i triangoli vuoti",
        "Remover triângulos vazios",
    ),
    "Leere Dreiecke wurden entfernt.": (
        "Empty triangles were removed.",
        "Se han eliminado los triángulos vacíos.",
        "Les triangles vides ont été supprimés.",
        "I triangoli vuoti sono stati rimossi.",
        "Os triângulos vazios foram removidos.",
    ),
    "Lücken an Nähten wurden geschlossen.": (
        "Gaps at seams were closed.",
        "Se han cerrado los huecos en las costuras.",
        "Les interstices aux coutures ont été fermés.",
        "Le fessure nelle cuciture sono state chiuse.",
        "As falhas nas costuras foram fechadas.",
    ),
    "Offen lassen": (
        "Leave open",
        "Dejar abierto",
        "Laisser ouvert",
        "Lascia aperto",
        "Deixar aberto",
    ),
    "Offene Stellen ließen sich nicht sicher schließen.": (
        "Open places could not be closed safely.",
        "Algunas zonas abiertas no se han podido cerrar con seguridad.",
        "Des endroits ouverts n’ont pas pu être fermés sans risque.",
        "Non è stato possibile chiudere in sicurezza alcuni punti aperti.",
        "Não foi possível fechar com segurança alguns pontos abertos.",
    ),
    "Offene Stellen und überzählige Flächen an {edges} Kanten ließen sich nicht sicher beheben.": (
        "Open places and surplus faces at {edges} edges could not be fixed safely.",
        "Las zonas abiertas y las caras sobrantes en {edges} aristas no se han podido corregir con seguridad.",
        "Des endroits ouverts et des faces en trop sur {edges} arêtes n’ont pas pu être corrigés sans risque.",
        "Non è stato possibile correggere in sicurezza i punti aperti e le facce in eccesso su {edges} spigoli.",
        "Não foi possível corrigir com segurança os pontos abertos e as faces excedentes em {edges} arestas.",
    ),
    "Schließt Löcher gleich beim Einlesen. Große Öffnungen nennt der Prüfbericht.": (
        "Closes holes right when reading the file. The check report names large openings.",
        "Cierra los agujeros ya al leer el archivo. El informe de comprobación indica las aberturas grandes.",
        "Ferme les trous dès la lecture du fichier. Le rapport de contrôle signale les grandes ouvertures.",
        "Chiude i fori già durante la lettura del file. Il rapporto di controllo segnala le aperture grandi.",
        "Fecha os buracos logo ao ler o ficheiro. O relatório de verificação indica as aberturas grandes.",
    ),
    "Schließt Löcher, entfernt fehlerhafte Dreiecke, gleicht die Außenseiten an und löst Überschneidungen auf.": (
        "Closes holes, removes faulty triangles, aligns the outer sides and resolves overlaps.",
        "Cierra agujeros, elimina triángulos defectuosos, iguala los lados exteriores y resuelve solapamientos.",
        "Ferme les trous, supprime les triangles défectueux, harmonise les faces extérieures et résout les recouvrements.",
        "Chiude i fori, rimuove i triangoli difettosi, uniforma i lati esterni e risolve le sovrapposizioni.",
        "Fecha buracos, remove triângulos defeituosos, iguala os lados exteriores e resolve sobreposições.",
    ),
    "Schließt Löcher. Große Öffnungen nennt der Prüfbericht.": (
        "Closes holes. The check report names large openings.",
        "Cierra agujeros. El informe de comprobación indica las aberturas grandes.",
        "Ferme les trous. Le rapport de contrôle signale les grandes ouvertures.",
        "Chiude i fori. Il rapporto di controllo segnala le aperture grandi.",
        "Fecha buracos. O relatório de verificação indica as aberturas grandes.",
    ),
    "Teile des Modells überschneiden sich.": (
        "Parts of the model overlap.",
        "Partes del modelo se solapan.",
        "Des parties du modèle se recouvrent.",
        "Parti del modello si sovrappongono.",
        "Partes do modelo sobrepõem-se.",
    ),
    "Verschmilzt Teile, die ineinanderstecken. Was nicht sicher geht, bleibt unverändert.": (
        "Merges parts that sit inside each other. Whatever cannot be done safely stays unchanged.",
        "Fusiona las piezas que están metidas unas en otras. Lo que no se puede hacer con seguridad queda sin cambios.",
        "Fusionne les pièces imbriquées les unes dans les autres. Ce qui ne peut pas se faire sans risque reste inchangé.",
        "Fonde le parti infilate l’una nell’altra. Ciò che non si può fare in sicurezza resta invariato.",
        "Funde as peças encaixadas umas nas outras. O que não se pode fazer com segurança fica inalterado.",
    ),
    "{holes} Löcher wurden geschlossen.": (
        "{holes} holes were closed.",
        "Se han cerrado {holes} agujeros.",
        "{holes} trous ont été fermés.",
        "Sono stati chiusi {holes} fori.",
        "Foram fechados {holes} buracos.",
    ),
    "{holes} offene Stellen ließen sich nicht sicher schließen.": (
        "{holes} open places could not be closed safely.",
        "{holes} zonas abiertas no se han podido cerrar con seguridad.",
        "{holes} endroits ouverts n’ont pas pu être fermés sans risque.",
        "Non è stato possibile chiudere in sicurezza {holes} punti aperti.",
        "Não foi possível fechar com segurança {holes} pontos abertos.",
    ),
    "{removed} Kleinstteile wurden entfernt.": (
        "{removed} stray fragments were removed.",
        "Se han eliminado {removed} fragmentos sueltos.",
        "{removed} fragments parasites ont été supprimés.",
        "Sono stati rimossi {removed} frammenti minuscoli.",
        "Foram removidos {removed} fragmentos soltos.",
    ),
    "{removed} lose Splitter wurden entfernt.": (
        "{removed} loose slivers were removed.",
        "Se han eliminado {removed} astillas sueltas.",
        "{removed} éclats isolés ont été supprimés.",
        "Sono state rimosse {removed} schegge isolate.",
        "Foram removidas {removed} lascas soltas.",
    ),
    "{walls} große Öffnungen wurden mit neuen Flächen geschlossen.": (
        "{walls} large openings were closed with new surfaces.",
        "Se han cerrado {walls} aberturas grandes con superficies nuevas.",
        "{walls} grandes ouvertures ont été fermées par de nouvelles surfaces.",
        "Sono state chiuse {walls} aperture grandi con superfici nuove.",
        "Foram fechadas {walls} aberturas grandes com superfícies novas.",
    ),
    "Überschneidungen auflösen": (
        "Resolve overlaps",
        "Resolver solapamientos",
        "Résoudre les recouvrements",
        "Risolvi le sovrapposizioni",
        "Resolver as sobreposições",
    ),
    "Überschneidungen lassen sich erst an einem geschlossenen Modell auflösen.": (
        "Overlaps can only be resolved once the model is closed.",
        "Los solapamientos solo se pueden resolver en un modelo cerrado.",
        "Les recouvrements ne peuvent être résolus que sur un modèle fermé.",
        "Le sovrapposizioni si possono risolvere solo su un modello chiuso.",
        "As sobreposições só se podem resolver num modelo fechado.",
    ),
    "Überschneidungen lassen sich nicht auflösen, solange Außenseiten gegeneinander zeigen.": (
        "Overlaps cannot be resolved while outer sides face each other.",
        "Los solapamientos no se pueden resolver mientras haya lados exteriores opuestos entre sí.",
        "Les recouvrements ne peuvent pas être résolus tant que des faces extérieures sont tournées l’une contre l’autre.",
        "Le sovrapposizioni non si possono risolvere finché dei lati esterni sono rivolti l’uno contro l’altro.",
        "As sobreposições não se podem resolver enquanto houver lados exteriores virados um contra o outro.",
    ),
    "Überschneidungen suchen": (
        "Searching for overlaps",
        "Buscando solapamientos",
        "Recherche des recouvrements",
        "Ricerca delle sovrapposizioni",
        "A procurar sobreposições",
    ),
    "Überschneidungen wurden aufgelöst.": (
        "Overlaps were resolved.",
        "Se han resuelto los solapamientos.",
        "Les recouvrements ont été résolus.",
        "Le sovrapposizioni sono state risolte.",
        "As sobreposições foram resolvidas.",
    ),
    "Überzählige Flächen an {edges} Kanten wurden entfernt.": (
        "Surplus faces at {edges} edges were removed.",
        "Se han eliminado las caras sobrantes en {edges} aristas.",
        "Des faces en trop sur {edges} arêtes ont été supprimées.",
        "Sono state rimosse le facce in eccesso su {edges} spigoli.",
        "Foram removidas as faces excedentes em {edges} arestas.",
    ),
}

gaps = json.loads(
    Path(".claude/.state/dreieck-reparatur-claude-2026-09-24/katalog_luecken.json").read_text(
        encoding="utf-8"
    )
)
for position, language in enumerate(LANGS):
    missing = set(gaps[language]["missing"])
    orphaned = set(gaps[language]["orphaned"])
    assert missing == set(T), (language, sorted(missing ^ set(T)))
    catalog = read_catalog(language)
    for key in orphaned:
        catalog.pop(key, None)
    for key, texts in T.items():
        catalog[key] = texts[position]
    write_catalog(language, catalog)
    print(language, "geschrieben:", len(T), "neu,", len(orphaned), "entfernt")
