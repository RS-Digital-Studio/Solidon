"""Die acht neuen Zuordnungstexte in alle vorhandenen Sprachkataloge eintragen."""

import json
from pathlib import Path

rows = {
    "Mehrere bisherige Merkmale wurden demselben aktuellen Merkmal zugeordnet. Bitte die Zuordnung erneut wählen.": (
        "Several previous features were assigned to the same current feature. Please choose the mapping again.",
        "Se han asignado varias características anteriores a una misma característica actual. Vuelva a elegir la correspondencia.",
        "Plusieurs caractéristiques précédentes ont été associées à la même caractéristique actuelle. Veuillez choisir à nouveau la correspondance.",
        "Più caratteristiche precedenti sono state associate alla stessa caratteristica attuale. Scegli nuovamente la corrispondenza.",
        "Várias características anteriores foram associadas à mesma característica atual. Escolher novamente a correspondência.",
    ),
    "Die Merkmalszuordnung ist widersprüchlich. Bitte die Zuordnung erneut prüfen.": (
        "The feature mapping is inconsistent. Please check the mapping again.",
        "La correspondencia de características es incoherente. Vuelva a comprobarla.",
        "La correspondance des caractéristiques est incohérente. Veuillez la vérifier à nouveau.",
        "La corrispondenza delle caratteristiche è incoerente. Verificala nuovamente.",
        "A correspondência das características é incoerente. Verificar novamente a correspondência.",
    ),
    "Ordne alle bisherigen Bezüge dieser Gruppe zu oder führe sie nicht weiter.": (
        "Assign every previous reference in this group or choose not to carry it forward.",
        "Asignar todas las referencias anteriores de este grupo o elegir no conservarlas.",
        "Associer chaque référence précédente de ce groupe ou choisir de ne pas la conserver.",
        "Associa ogni riferimento precedente di questo gruppo oppure scegliere di non mantenerlo.",
        "Associar cada referência anterior deste grupo ou escolher não a manter.",
    ),
    "Die Zuordnung ist nicht mehr gültig. Wähle die Bezüge erneut aus.": (
        "The mapping is no longer valid. Select the references again.",
        "La correspondencia ya no es válida. Seleccionar de nuevo las referencias.",
        "La correspondance n’est plus valide. Sélectionner à nouveau les références.",
        "La corrispondenza non è più valida. Seleziona nuovamente i riferimenti.",
        "A correspondência deixou de ser válida. Selecionar novamente as referências.",
    ),
    "Nicht weiterführen": (
        "Do not carry forward", "No conservar", "Ne pas conserver", "Non mantenere", "Não manter",
    ),
    "Diese bisherigen Bezüge teilen sich mögliche Nachfolger: {names}. Jedes aktuelle Merkmal kann nur einen bisherigen Bezug übernehmen.": (
        "These previous references share possible successors: {names}. Each current feature can take over only one previous reference.",
        "Estas referencias anteriores comparten posibles sucesores: {names}. Cada característica actual solo puede asumir una referencia anterior.",
        "Ces références précédentes partagent des successeurs possibles : {names}. Chaque caractéristique actuelle ne peut reprendre qu’une seule référence précédente.",
        "Questi riferimenti precedenti condividono possibili successori: {names}. Ogni caratteristica attuale può assumere un solo riferimento precedente.",
        "Estas referências anteriores partilham possíveis sucessores: {names}. Cada característica atual só pode assumir uma referência anterior.",
    ),
    "Die bisherigen Flächenbezüge sind am exakten Körper nicht eindeutig. Wähle die betroffenen Flächen im Folgeschritt erneut aus.": (
        "The previous surface references are ambiguous on the exact body. Select the affected surfaces again in the following step.",
        "Las referencias de superficies anteriores son ambiguas en el cuerpo exacto. Seleccionar de nuevo las superficies afectadas en el paso siguiente.",
        "Les références de surfaces précédentes sont ambiguës sur le corps exact. Sélectionner à nouveau les surfaces concernées dans l’étape suivante.",
        "I riferimenti precedenti alle superfici sono ambigui sul corpo esatto. Seleziona nuovamente le superfici interessate nel passaggio successivo.",
        "As referências anteriores às superfícies são ambíguas no corpo exato. Selecionar novamente as superfícies afetadas no passo seguinte.",
    ),
    "Die Kandidaten werden in der Ansicht vorbereitet. Danach kannst du auswählen.": (
        "The candidates are being prepared in the view. You can select them once they are ready.",
        "Los candidatos se están preparando en la vista. Podrá seleccionarlos cuando estén listos.",
        "Les candidats sont en cours de préparation dans la vue. Vous pourrez les sélectionner dès qu’ils seront prêts.",
        "I candidati vengono preparati nella vista. Potrai selezionarli quando saranno pronti.",
        "Os candidatos estão a ser preparados na vista. Poderá selecioná-los quando estiverem prontos.",
    ),
}

root = Path(__file__).resolve().parents[3]
for index, language in enumerate(("en", "es", "fr", "it", "pt")):
    path = root / "app/i18n/locales" / f"{language}.json"
    catalog = json.loads(path.read_text(encoding="utf-8"))
    for source, translations in rows.items():
        assert source in catalog and catalog[source] in ("", translations[index]), source
        catalog[source] = translations[index]
    path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"{language}: {len(rows)} Texte ergänzt")
