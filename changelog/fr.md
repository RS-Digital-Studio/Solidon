# Nouveautés

Ce fichier est ce qu'affiche la fenêtre de mise à jour, et rien d'autre. Ce
n'est **pas** une liste des modifications : sur 97 commits entre 0.1.1 et
0.1.2, il reste huit lignes, et les choisir est le travail. Un point a sa
place ici si quelqu'un le remarque en utilisant le programme.

Donc : pas de messages de commit, pas de noms de modules, pas de numéros de
paragraphe. « La barre disparaissait alors que l'application calculait encore
pendant quatre secondes » est un bon commit et une mauvaise entrée ; « La
progression reste affichée jusqu'à la fin réelle du calcul » dit la même chose
à celui qui est devant l'écran.

Un fichier par langue dans ce dossier, comme pour les catalogues, et tous
portent les mêmes points dans le même ordre (`tests/test_changelog.py`).
`tools/make_download.py` en tire la section de la version courante et l'écrit
dans `website/version.json`.

## 0.1.3

- Le noyau exact sait désormais percer : « Percer un trou exact » travaille directement sur le corps exact, sans détour par un maillage.
- Les congés et chanfreins sont reconnus plus sûrement. Un congé était parfois signalé comme un téton — avec un diamètre qui n’existait pas.
- Les exemples fournis n’accueillent plus avec des avertissements qui n’en sont pas.
- L’écran d’accueil tient sur les petits écrans, sans défilement.
- Une caractéristique cliquée se colore elle-même. Auparavant, tout le corps prenait la couleur de sélection et l’on ne voyait pas ce qui était visé.
- L’arborescence des objets indique la cote de chaque caractéristique reconnue.
- Les maillages exportés ne contiennent plus de triangles vides.
- Enregistrer deux fois donne deux fois le même fichier.
- Les cinq traductions ont été relues. Les termes techniques portent maintenant le nom que leur donnent les slicers.
- La barre d’outils est rangée : le champ le plus large était celui dont on se sert le moins.
- Une seconde erreur du programme ne place plus une seconde fenêtre sur la première.

## 0.1.2

- Les nombres décimaux saisis sont lus correctement partout. « 12,5 » reste douze et demi ; auparavant, cela pouvait devenir 125, sans question ni avertissement.
- Chacun des cinquante-six champs des réglages d'impression indique désormais ce qu'il fait quand on le modifie.
- Le temps d'impression et la quantité de matière sont estimés plus finement, surtout pour les pièces évidées.
- Le transfert vers le trancheur atteint le plateau. Avec CuraEngine, les pièces se retrouvaient à côté.
- Lors d'une découpe avec goupilles, les trous correspondants se placent dans la bonne moitié.
- Millimètres et pouces valent maintenant partout où figure un nombre — y compris dans les barres d'outils et lors de la peinture.
- La progression reste affichée jusqu'à la fin réelle du calcul, et la fenêtre demeure utilisable pendant ce temps.
- Tous les raccourcis clavier figurent désormais dans un aperçu unique : dans le menu Aide, sous « Raccourcis clavier », ou en appuyant sur la touche point d’interrogation.
