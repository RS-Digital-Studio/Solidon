"""Ergänzt ausschließlich die Texte dieser Durchsicht in den aktuellen Katalogen."""

import json
from pathlib import Path

TEXTS = {
    "Stelle auswählen": {
        "en": "Choose a location",
        "es": "Seleccionar una posición",
        "fr": "Choisir un emplacement",
        "it": "Scegli una posizione",
        "pt": "Escolher uma posição",
    },
    "Pfeiltasten bewegen das Fadenkreuz, Umschalt bewegt es fein. Eingabe wählt die Stelle, Escape beendet die Auswahl.": {
        "en": "Arrow keys move the crosshair; hold Shift for fine movement. Enter chooses the location, Escape ends selection.",
        "es": "Las flechas mueven la cruz; con Mayús, el movimiento es más preciso. Intro elige la posición y Escape termina la selección.",
        "fr": "Les flèches déplacent le réticule ; Maj permet un déplacement précis. Entrée choisit l’emplacement, Échap termine la sélection.",
        "it": "Le frecce spostano il mirino; Maiusc consente movimenti precisi. Invio sceglie la posizione, Esc termina la selezione.",
        "pt": "As setas movem a mira; Shift permite movimentos precisos. Enter escolhe a posição e Escape termina a seleção.",
    },
    "Wählen Sie eine Oberfläche: klicken oder mit Pfeiltasten zielen und Enter drücken. Escape beendet die Auswahl.": {
        "en": "Choose a surface: click it, or aim with the arrow keys and press Enter. Escape ends selection.",
        "es": "Elige una superficie: haz clic o apunta con las flechas y pulsa Intro. Escape termina la selección.",
        "fr": "Choisissez une surface : cliquez dessus ou visez avec les flèches et appuyez sur Entrée. Échap termine la sélection.",
        "it": "Scegli una superficie: fai clic oppure punta con le frecce e premi Invio. Esc termina la selezione.",
        "pt": "Escolha uma superfície: clique ou aponte com as setas e prima Enter. Escape termina a seleção.",
    },
    "Wählen Sie eine Oberfläche eines markierten Modells.": {
        "en": "Choose a surface on one of the selected models.",
        "es": "Elige una superficie de uno de los modelos seleccionados.",
        "fr": "Choisissez une surface sur l’un des modèles sélectionnés.",
        "it": "Scegli una superficie di uno dei modelli selezionati.",
        "pt": "Escolha uma superfície de um dos modelos selecionados.",
    },
    "Einige offene Ränder ließen sich nicht sicher schließen. Prüfen Sie die markierten Stellen.": {
        "en": "Some open boundaries could not be closed reliably. Inspect the highlighted areas.",
        "es": "Algunos bordes abiertos no se han podido cerrar de forma fiable. Revisar las zonas marcadas.",
        "fr": "Certains bords ouverts n’ont pas pu être fermés de manière fiable. Examiner les zones signalées.",
        "it": "Non è stato possibile chiudere in modo affidabile alcuni bordi aperti. Controlla le aree evidenziate.",
        "pt": "Não foi possível fechar com segurança alguns contornos abertos. Verificar as áreas assinaladas.",
    },
    "Die Durchdringungsreparatur braucht einen geschlossenen Körper mit korrekt ausgerichteten Außenseiten. Prüfen Sie die markierten Stellen und die Einstellungen zum Schließen und Ausrichten.": {
        "en": "Repairing intersections requires a closed body with correctly oriented outer surfaces. Inspect the highlighted areas and the settings for closing openings and aligning surfaces.",
        "es": "La reparación de intersecciones requiere un cuerpo cerrado con las caras exteriores correctamente orientadas. Revisar las zonas marcadas y los ajustes para cerrar aberturas y orientar las caras.",
        "fr": "La réparation des intersections nécessite un corps fermé avec des faces extérieures correctement orientées. Examiner les zones signalées et les réglages de fermeture et d’orientation.",
        "it": "La riparazione delle intersezioni richiede un corpo chiuso con le superfici esterne orientate correttamente. Controlla le aree evidenziate e le impostazioni di chiusura e orientamento.",
        "pt": "A reparação de interseções requer um corpo fechado com as faces exteriores corretamente orientadas. Verificar as áreas assinaladas e as definições de fecho e orientação.",
    },
    "Die Suche nach Durchdringungen ist unvollständig. Markierte Fehler sind bestätigt; weitere sind möglich.": {
        "en": "The search for intersections is incomplete. Highlighted defects are confirmed; others may remain.",
        "es": "La búsqueda de intersecciones está incompleta. Los defectos marcados están confirmados; puede haber otros.",
        "fr": "La recherche d’intersections est incomplète. Les défauts signalés sont confirmés ; d’autres peuvent subsister.",
        "it": "La ricerca delle intersezioni è incompleta. I difetti evidenziati sono confermati; potrebbero essercene altri.",
        "pt": "A procura de interseções está incompleta. Os defeitos assinalados estão confirmados; podem existir outros.",
    },
    "Durchdringungen nicht vollständig geprüft": {
        "en": "Intersections not fully checked",
        "es": "Intersecciones no comprobadas por completo",
        "fr": "Intersections non entièrement vérifiées",
        "it": "Intersezioni non verificate completamente",
        "pt": "Interseções não verificadas na totalidade",
    },
    "Andere Stelle wählen": {
        "en": "Choose another location",
        "es": "Elegir otra ubicación",
        "fr": "Choisir un autre emplacement",
        "it": "Scegli un altro punto",
        "pt": "Escolher outro local",
    },
    "Flächen durchdringen sich. Aktivieren Sie unter „Weitere Einstellungen“ die Option „Selbstdurchdringungen auflösen“.": {
        "en": "Surfaces intersect each other. Under “More settings”, enable “Resolve self-intersections”.",
        "es": "Las superficies se atraviesan entre sí. En «Más ajustes», activar «Resolver autointersecciones».",
        "fr": "Des surfaces se traversent. Dans « Autres réglages », activer « Résoudre les auto-intersections ».",
        "it": "Le superfici si intersecano. In «Altre impostazioni», attiva «Risolvi le autointersezioni».",
        "pt": "As superfícies intersectam-se. Em «Mais definições», ativar «Resolver as autointerseções».",
    },
    "Die sich durchdringenden Flächen konnten nicht sicher getrennt werden. Das Modell bleibt an diesen Stellen unverändert; prüfen Sie die markierten Stellen.": {
        "en": "The intersecting surfaces could not be separated reliably. The model remains unchanged at these locations; inspect the highlighted areas.",
        "es": "Las superficies que se atraviesan no se han podido separar de forma fiable. El modelo permanece sin cambios en esas zonas; revisar las zonas marcadas.",
        "fr": "Les surfaces qui se traversent n’ont pas pu être séparées de manière fiable. Le modèle reste inchangé à ces endroits ; examiner les zones signalées.",
        "it": "Non è stato possibile separare in modo affidabile le superfici che si intersecano. Il modello resta invariato in questi punti; controlla le aree evidenziate.",
        "pt": "Não foi possível separar com segurança as superfícies que se intersectam. O modelo permanece inalterado nesses locais; verificar as áreas assinaladas.",
    },
    "Die Prüfung auf sich durchdringende Flächen ist noch unvollständig. Prüfen Sie die markierten Stellen; weitere Fehler können vorhanden sein.": {
        "en": "The check for intersecting surfaces is still incomplete. Inspect the highlighted areas; other defects may remain.",
        "es": "La comprobación de superficies que se atraviesan aún está incompleta. Revisar las zonas marcadas; puede haber otros defectos.",
        "fr": "La vérification des surfaces qui se traversent est encore incomplète. Examiner les zones signalées ; d’autres défauts peuvent subsister.",
        "it": "La verifica delle superfici che si intersecano è ancora incompleta. Controlla le aree evidenziate; potrebbero esserci altri difetti.",
        "pt": "A verificação de superfícies que se intersectam ainda está incompleta. Verificar as áreas assinaladas; podem existir outros defeitos.",
    },
    "Vereinigt sich überlappende Teile. Nicht sicher reparierbare Stellen bleiben unverändert und werden im Prüfbericht genannt.": {
        "en": "Unites overlapping parts. Areas that cannot be repaired reliably remain unchanged and are listed in the check report.",
        "es": "Une piezas que se solapan. Las zonas que no se pueden reparar de forma fiable permanecen sin cambios y se indican en el informe de comprobación.",
        "fr": "Réunit les pièces qui se chevauchent. Les zones qui ne peuvent pas être réparées de manière fiable restent inchangées et sont signalées dans le rapport de contrôle.",
        "it": "Unisce le parti sovrapposte. Le aree che non possono essere riparate in modo affidabile restano invariate e sono indicate nel rapporto di verifica.",
        "pt": "Une peças sobrepostas. As áreas que não podem ser reparadas com segurança permanecem inalteradas e são indicadas no relatório de verificação.",
    },
    "Schließt offene Ränder. Bei großen Öffnungen weist der Prüfbericht auf die neu entstandenen Flächen hin.": {
        "en": "Closes open boundaries. For large openings, the check report points out the newly created surfaces.",
        "es": "Cierra bordes abiertos. Si las aberturas son grandes, el informe de comprobación indica las superficies recién creadas.",
        "fr": "Ferme les bords ouverts. Pour les grandes ouvertures, le rapport de contrôle signale les surfaces nouvellement créées.",
        "it": "Chiude i bordi aperti. Per le aperture grandi, il rapporto di verifica segnala le superfici appena create.",
        "pt": "Fecha contornos abertos. Nas aberturas grandes, o relatório de verificação assinala as superfícies criadas.",
    },
}

REMOVED = (
    "Klicken Sie auf die Stelle, deren Merkmale Sie erkennen möchten. Escape beendet die Auswahl.",
    "Die Reparatur schließt kleine Löcher, kann fehlende Wände aber nicht ersetzen.",
    "Schließt kleine Löcher. Fehlende Wände kann das nicht ersetzen.",
    "Rechnet Flächen neu, die sich gegenseitig durchdringen. Hilft bei erzeugten Netzen und kostet Genauigkeit — deshalb aus, bis es gebraucht wird.",
    "Selbstdurchdringungen wurden nicht geprüft, weil der Körper offen ist. Die Defektkarte zeigt die Stellen, die zuerst geschlossen werden müssen.",
)

from app.i18n.extract import message_ids

current = message_ids()

for language in ("en", "es", "fr", "it", "pt"):
    path = Path("app/i18n/locales") / f"{language}.json"
    before = path.read_bytes()
    catalog = json.loads(before)
    for source, translations in TEXTS.items():
        catalog[source] = translations[language]
    for source in REMOVED:
        if source not in current:
            catalog.pop(source, None)
    if path.read_bytes() != before:
        raise RuntimeError(f"Katalog wurde parallel geändert: {path}")
    path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
