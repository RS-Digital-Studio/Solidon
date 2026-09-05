/* Der Dateiweg der Geräteaktivierung. Keine Bibliothek, kein fremder Dienst. */
(() => {
  "use strict";

  const translations = {
    de: {
      document_title: "Solidon3D offline aktivieren", language: "Sprache", skip: "Zum Inhalt springen",
      brand_home: "Solidon3D Startseite", language_navigation: "Sprachauswahl", steps_label: "Drei Schritte",
      kicker: "Einmal verbinden, danach offline", title: "Solidon3D offline aktivieren",
      lead: "Der Solidon-Rechner bleibt ohne Internet. Nur diese Aktivierungsanfrage wird einmal übermittelt und geprüft.",
      step_1_title: "Anfrage speichern", step_1_text: "In Solidon unter Hilfe → Solidon freischalten → Offline aktivieren.",
      step_2_title: "Hier auswählen", step_2_text: "Die Datei endet auf .solidon-request. Mehr müssen Sie nicht eingeben.",
      step_3_title: "Antwort zurückbringen", step_3_text: "Antwort herunterladen und auf dem Solidon-Rechner einlesen.",
      form_title: "Aktivierungsanfrage auswählen", form_text: "Die Datei enthält Ihren Lizenzschlüssel, den gewählten Rechnernamen und einen zufälligen öffentlichen Geräteschlüssel.",
      file_label: "Datei auswählen", no_file: "Keine Datei ausgewählt", selected_file: "Ausgewählt",
      file_help: ".solidon-request · höchstens wenige Kilobyte", or: "oder",
      paste_toggle: "Die Datei lässt sich nicht auswählen?", paste_help: "Öffnen Sie die Anfrage als Text und fügen Sie den vollständigen Inhalt hier ein.",
      paste_label: "Dateiinhalt einfügen", submit: "Anfrage prüfen und diesen Rechner aktivieren",
      result_kicker: "✓ Prüfung abgeschlossen", result_title: "Antwort ist fertig", checking_title: "Anfrage wird geprüft",
      error_title: "Aktivierung noch nicht möglich", download: "Antwortdatei herunterladen",
      no_account_title: "Kein Konto. Keine Hardwaredaten.",
      privacy: "Gespeichert werden die Aktivierungsdaten und ein kurzer Tageszähler je Schlüssel. Zusätzlich schützt für höchstens 15 Minuten ein HMAC-Pseudonym der IP-Adresse vor Missbrauch; die IP-Adresse selbst, Projekte, Modelle und Hardwaremerkmale werden nicht in diesen Anwendungsdaten gespeichert.",
      privacy_link: "Datenschutzerklärung lesen", help_title: "Etwas klappt nicht?",
      help_text: "Die Anfrage bleibt unverändert erhalten. Versuchen Sie es erneut oder schreiben Sie mit Ihrer Bestellnummer an den Support.",
      home: "Startseite", legal: "Impressum", privacy_short: "Datenschutz",
      checking: "Die Anfrage wird sicher geprüft …", ready: "Die Aktivierung wurde erteilt. Laden Sie die Antwortdatei herunter und lesen Sie sie auf dem Solidon-Rechner ein.",
      checking_kicker: "Prüfung läuft", error_kicker: "Nicht abgeschlossen", error_large: "Die Anfrage ist ungewöhnlich groß. Bitte erzeugen Sie sie in Solidon noch einmal.",
      error_file: "Die Datei ließ sich nicht lesen. Wählen Sie die Aktivierungsanfrage bitte noch einmal aus.",
      error_network: "Der Aktivierungsdienst ist gerade nicht erreichbar. Versuchen Sie es erneut oder nutzen Sie den Support.",
      error_unreadable: "Der Aktivierungsdienst hat keine lesbare Antwort gesendet. Versuchen Sie es erneut oder wenden Sie sich an den Support.",
      error_rejected: "Die Anfrage wurde abgelehnt. Prüfen Sie den Lizenzschlüssel oder wenden Sie sich mit Ihrer Bestellnummer an den Support.",
      error_kind: "Die Antwort enthält kein Geräte-Zertifikat. Versuchen Sie es erneut oder wenden Sie sich an den Support.",
      error_empty: "Wählen Sie zuerst Ihre .solidon-request-Datei aus.",
      error_device_limit: "Dieser Lizenzschlüssel ist bereits auf einem anderen Rechner aktiv. Deaktivieren Sie ihn dort oder wenden Sie sich mit Ihrer Bestellnummer an den Support.",
      error_rate_limit: "Für diesen Lizenzschlüssel gab es heute zu viele Versuche. Probieren Sie es morgen erneut oder wenden Sie sich an den Support.",
      error_wrong_major: "Der Lizenzschlüssel gehört zu einer anderen Hauptversion von Solidon3D.",
      error_licence_blocked: "Dieser Lizenzschlüssel wurde gesperrt. Wenden Sie sich mit Ihrer Bestellnummer an den Support.",
      error_service_unavailable: "Der Aktivierungsdienst ist vorübergehend nicht verfügbar. Versuchen Sie es später erneut oder wenden Sie sich an den Support.",
      error_invalid_request: "Die Anfrage ist nicht vollständig. Erzeugen Sie sie in Solidon3D noch einmal und wählen Sie die neue Datei aus."
    },
    en: {
      document_title: "Activate Solidon3D offline", language: "Language", skip: "Skip to content",
      brand_home: "Solidon3D home page", language_navigation: "Language selection", steps_label: "Three steps",
      kicker: "Connect once, then stay offline", title: "Activate Solidon3D offline",
      lead: "The Solidon computer stays offline. Only this activation request is transmitted and checked once.",
      step_1_title: "Save the request", step_1_text: "In Solidon, open Help → Unlock Solidon → Activate offline.",
      step_2_title: "Select it here", step_2_text: "The file ends in .solidon-request. You do not need to enter anything else.",
      step_3_title: "Take the response back", step_3_text: "Download the response and import it on the Solidon computer.",
      form_title: "Select activation request", form_text: "The file contains your licence key, the computer name you chose and a random public device key.",
      file_label: "Choose file", no_file: "No file selected", selected_file: "Selected",
      file_help: ".solidon-request · only a few kilobytes", or: "or",
      paste_toggle: "Unable to select the file?", paste_help: "Open the request as text and paste its complete contents here.",
      paste_label: "Paste file contents", submit: "Check request and activate this computer",
      result_kicker: "✓ Check completed", result_title: "Your response is ready", checking_title: "Checking your request",
      error_title: "Activation is not yet possible", download: "Download response file",
      no_account_title: "No account. No hardware data.",
      privacy: "Activation data and a short daily counter per licence key are stored. In addition, an HMAC pseudonym of the IP address protects against abuse for no more than 15 minutes; the IP address itself, projects, models and hardware characteristics are not stored in this application data.",
      privacy_link: "Read the privacy notice", help_title: "Something not working?",
      help_text: "Your request remains unchanged. Try again or contact support with your order number.",
      home: "Home", legal: "Legal notice", privacy_short: "Privacy",
      checking: "The request is being checked securely …", ready: "Activation has been granted. Download the response file and import it on the Solidon computer.",
      checking_kicker: "Check in progress", error_kicker: "Not completed", error_large: "The request is unusually large. Please create it again in Solidon.",
      error_file: "The file could not be read. Please select the activation request again.",
      error_network: "The activation service is currently unavailable. Try again or contact support.",
      error_unreadable: "The activation service sent no readable response. Try again or contact support.",
      error_rejected: "The request was rejected. Check the licence key or contact support with your order number.",
      error_kind: "The response contains no device certificate. Try again or contact support.",
      error_empty: "First select your .solidon-request file.",
      error_device_limit: "This licence key is already active on another computer. Deactivate it there or contact support with your order number.",
      error_rate_limit: "There have been too many attempts for this licence key today. Try again tomorrow or contact support.",
      error_wrong_major: "The licence key belongs to a different major version of Solidon3D.",
      error_licence_blocked: "This licence key has been blocked. Contact support with your order number.",
      error_service_unavailable: "The activation service is temporarily unavailable. Try again later or contact support.",
      error_invalid_request: "The request is incomplete. Create it again in Solidon3D and select the new file."
    },
    es: {
      document_title: "Activar Solidon3D sin conexión", language: "Idioma", skip: "Saltar al contenido",
      brand_home: "Página de inicio de Solidon3D", language_navigation: "Selección de idioma", steps_label: "Tres pasos",
      kicker: "Conéctese una vez y después siga sin conexión", title: "Activar Solidon3D sin conexión",
      lead: "El ordenador con Solidon permanece sin internet. Solo esta solicitud de activación se transmite y comprueba una vez.",
      step_1_title: "Guardar la solicitud", step_1_text: "En Solidon, abra Ayuda → Desbloquear Solidon → Activar sin conexión.",
      step_2_title: "Seleccionarla aquí", step_2_text: "El archivo termina en .solidon-request. No necesita introducir nada más.",
      step_3_title: "Llevar la respuesta", step_3_text: "Descargue la respuesta e impórtela en el ordenador con Solidon.",
      form_title: "Seleccionar solicitud de activación", form_text: "El archivo contiene su clave de licencia, el nombre elegido para el ordenador y una clave pública aleatoria del dispositivo.",
      file_label: "Elegir archivo", no_file: "Ningún archivo seleccionado", selected_file: "Seleccionado",
      file_help: ".solidon-request · solo unos pocos kilobytes", or: "o",
      paste_toggle: "¿No puede seleccionar el archivo?", paste_help: "Abra la solicitud como texto y pegue aquí todo su contenido.",
      paste_label: "Pegar el contenido del archivo", submit: "Comprobar la solicitud y activar este ordenador",
      result_kicker: "✓ Comprobación terminada", result_title: "La respuesta está lista", checking_title: "Comprobando la solicitud",
      error_title: "La activación aún no es posible", download: "Descargar archivo de respuesta",
      no_account_title: "Sin cuenta. Sin datos de hardware.",
      privacy: "Se guardan los datos de activación y un breve contador diario por clave. Además, un seudónimo HMAC de la dirección IP protege contra abusos durante un máximo de 15 minutos; la dirección IP, los proyectos, los modelos y las características del hardware no se guardan en estos datos de la aplicación.",
      privacy_link: "Leer la política de privacidad", help_title: "¿Algo no funciona?",
      help_text: "La solicitud permanece sin cambios. Inténtelo de nuevo o escriba al soporte con su número de pedido.",
      home: "Inicio", legal: "Aviso legal", privacy_short: "Privacidad",
      checking: "La solicitud se está comprobando de forma segura …", ready: "La activación se ha concedido. Descargue la respuesta e impórtela en el ordenador con Solidon.",
      checking_kicker: "Comprobación en curso", error_kicker: "No completado", error_large: "La solicitud es inusualmente grande. Vuelva a crearla en Solidon.",
      error_file: "No se pudo leer el archivo. Vuelva a seleccionar la solicitud de activación.",
      error_network: "El servicio de activación no está disponible en este momento. Inténtelo de nuevo o contacte con soporte.",
      error_unreadable: "El servicio de activación no envió una respuesta legible. Inténtelo de nuevo o contacte con soporte.",
      error_rejected: "La solicitud fue rechazada. Compruebe la clave de licencia o contacte con soporte indicando su número de pedido.",
      error_kind: "La respuesta no contiene un certificado del dispositivo. Inténtelo de nuevo o contacte con soporte.",
      error_empty: "Seleccione primero su archivo .solidon-request.",
      error_device_limit: "Esta clave de licencia ya está activa en otro ordenador. Desactívela allí o contacte con soporte indicando su número de pedido.",
      error_rate_limit: "Hoy ha habido demasiados intentos con esta clave de licencia. Inténtelo mañana o contacte con soporte.",
      error_wrong_major: "La clave de licencia pertenece a otra versión principal de Solidon3D.",
      error_licence_blocked: "Esta clave de licencia está bloqueada. Contacte con soporte indicando su número de pedido.",
      error_service_unavailable: "El servicio de activación no está disponible temporalmente. Inténtelo más tarde o contacte con soporte.",
      error_invalid_request: "La solicitud está incompleta. Créela de nuevo en Solidon3D y seleccione el archivo nuevo."
    },
    fr: {
      document_title: "Activer Solidon3D hors ligne", language: "Langue", skip: "Aller au contenu",
      brand_home: "Accueil de Solidon3D", language_navigation: "Choix de la langue", steps_label: "Trois étapes",
      kicker: "Une connexion, puis restez hors ligne", title: "Activer Solidon3D hors ligne",
      lead: "L’ordinateur Solidon reste sans internet. Seule cette demande d’activation est transmise et vérifiée une fois.",
      step_1_title: "Enregistrer la demande", step_1_text: "Dans Solidon, ouvrez Aide → Déverrouiller Solidon → Activer hors ligne.",
      step_2_title: "La sélectionner ici", step_2_text: "Le fichier se termine par .solidon-request. Vous n’avez rien d’autre à saisir.",
      step_3_title: "Rapporter la réponse", step_3_text: "Téléchargez la réponse et importez-la sur l’ordinateur Solidon.",
      form_title: "Sélectionner la demande d’activation", form_text: "Le fichier contient votre clé de licence, le nom choisi pour l’ordinateur et une clé publique d’appareil aléatoire.",
      file_label: "Choisir le fichier", no_file: "Aucun fichier sélectionné", selected_file: "Sélectionné",
      file_help: ".solidon-request · quelques kilo-octets seulement", or: "ou",
      paste_toggle: "Impossible de sélectionner le fichier ?", paste_help: "Ouvrez la demande comme texte et collez ici tout son contenu.",
      paste_label: "Coller le contenu du fichier", submit: "Vérifier la demande et activer cet ordinateur",
      result_kicker: "✓ Vérification terminée", result_title: "La réponse est prête", checking_title: "Vérification de la demande",
      error_title: "L’activation n’est pas encore possible", download: "Télécharger le fichier de réponse",
      no_account_title: "Aucun compte. Aucune donnée matérielle.",
      privacy: "Les données d’activation et un compteur journalier court par clé sont conservés. En plus, un pseudonyme HMAC de l’adresse IP protège contre les abus pendant 15 minutes au maximum ; l’adresse IP elle-même, les projets, modèles et caractéristiques matérielles ne sont pas conservés dans ces données d’application.",
      privacy_link: "Lire la déclaration de confidentialité", help_title: "Quelque chose ne fonctionne pas ?",
      help_text: "Votre demande reste inchangée. Réessayez ou contactez l’assistance avec votre numéro de commande.",
      home: "Accueil", legal: "Mentions légales", privacy_short: "Confidentialité",
      checking: "La demande est vérifiée de manière sécurisée …", ready: "L’activation a été accordée. Téléchargez la réponse et importez-la sur l’ordinateur Solidon.",
      checking_kicker: "Vérification en cours", error_kicker: "Non terminé", error_large: "La demande est anormalement volumineuse. Recréez-la dans Solidon.",
      error_file: "Le fichier n’a pas pu être lu. Sélectionnez à nouveau la demande d’activation.",
      error_network: "Le service d’activation est momentanément indisponible. Réessayez ou contactez l’assistance.",
      error_unreadable: "Le service d’activation n’a envoyé aucune réponse lisible. Réessayez ou contactez l’assistance.",
      error_rejected: "La demande a été refusée. Vérifiez la clé de licence ou contactez l’assistance avec votre numéro de commande.",
      error_kind: "La réponse ne contient aucun certificat d’appareil. Réessayez ou contactez l’assistance.",
      error_empty: "Sélectionnez d’abord votre fichier .solidon-request.",
      error_device_limit: "Cette clé de licence est déjà active sur un autre ordinateur. Désactivez-la sur celui-ci ou contactez l’assistance avec votre numéro de commande.",
      error_rate_limit: "Il y a eu trop de tentatives aujourd’hui pour cette clé de licence. Réessayez demain ou contactez l’assistance.",
      error_wrong_major: "La clé de licence appartient à une autre version majeure de Solidon3D.",
      error_licence_blocked: "Cette clé de licence a été bloquée. Contactez l’assistance avec votre numéro de commande.",
      error_service_unavailable: "Le service d’activation est temporairement indisponible. Réessayez plus tard ou contactez l’assistance.",
      error_invalid_request: "La demande est incomplète. Créez-la de nouveau dans Solidon3D et sélectionnez le nouveau fichier."
    },
    it: {
      document_title: "Attivare Solidon3D offline", language: "Lingua", skip: "Vai al contenuto",
      brand_home: "Pagina iniziale di Solidon3D", language_navigation: "Selezione della lingua", steps_label: "Tre passaggi",
      kicker: "Connettiti una volta, poi resta offline", title: "Attivare Solidon3D offline",
      lead: "Il computer con Solidon resta senza internet. Solo questa richiesta di attivazione viene trasmessa e verificata una volta.",
      step_1_title: "Salvare la richiesta", step_1_text: "In Solidon apri Aiuto → Sblocca Solidon → Attiva offline.",
      step_2_title: "Selezionarla qui", step_2_text: "Il file termina con .solidon-request. Non devi inserire altro.",
      step_3_title: "Riportare la risposta", step_3_text: "Scarica la risposta e importala sul computer con Solidon.",
      form_title: "Selezionare la richiesta di attivazione", form_text: "Il file contiene la chiave di licenza, il nome scelto per il computer e una chiave pubblica casuale del dispositivo.",
      file_label: "Scegliere il file", no_file: "Nessun file selezionato", selected_file: "Selezionato",
      file_help: ".solidon-request · solo pochi kilobyte", or: "oppure",
      paste_toggle: "Non riesci a selezionare il file?", paste_help: "Apri la richiesta come testo e incolla qui l’intero contenuto.",
      paste_label: "Incollare il contenuto del file", submit: "Verificare la richiesta e attivare questo computer",
      result_kicker: "✓ Verifica completata", result_title: "La risposta è pronta", checking_title: "Verifica della richiesta",
      error_title: "L’attivazione non è ancora possibile", download: "Scaricare il file di risposta",
      no_account_title: "Nessun account. Nessun dato hardware.",
      privacy: "Vengono conservati i dati di attivazione e un breve contatore giornaliero per chiave. Inoltre, uno pseudonimo HMAC dell’indirizzo IP protegge dagli abusi per non più di 15 minuti; l’indirizzo IP stesso, i progetti, i modelli e le caratteristiche hardware non vengono conservati in questi dati dell’applicazione.",
      privacy_link: "Leggere l’informativa sulla privacy", help_title: "Qualcosa non funziona?",
      help_text: "La richiesta resta invariata. Riprova o scrivi all’assistenza indicando il numero d’ordine.",
      home: "Home", legal: "Note legali", privacy_short: "Privacy",
      checking: "La richiesta viene verificata in modo sicuro …", ready: "L’attivazione è stata concessa. Scarica il file di risposta e importalo sul computer con Solidon.",
      checking_kicker: "Verifica in corso", error_kicker: "Non completato", error_large: "La richiesta è insolitamente grande. Creala di nuovo in Solidon.",
      error_file: "Non è stato possibile leggere il file. Seleziona di nuovo la richiesta di attivazione.",
      error_network: "Il servizio di attivazione non è al momento disponibile. Riprova o contatta l’assistenza.",
      error_unreadable: "Il servizio di attivazione non ha inviato una risposta leggibile. Riprova o contatta l’assistenza.",
      error_rejected: "La richiesta è stata rifiutata. Controlla la chiave di licenza o contatta l’assistenza con il numero d’ordine.",
      error_kind: "La risposta non contiene un certificato del dispositivo. Riprova o contatta l’assistenza.",
      error_empty: "Seleziona prima il file .solidon-request.",
      error_device_limit: "Questa chiave di licenza è già attiva su un altro computer. Disattivala lì o contatta l’assistenza con il numero d’ordine.",
      error_rate_limit: "Oggi ci sono stati troppi tentativi per questa chiave di licenza. Riprova domani o contatta l’assistenza.",
      error_wrong_major: "La chiave di licenza appartiene a un’altra versione principale di Solidon3D.",
      error_licence_blocked: "Questa chiave di licenza è stata bloccata. Contatta l’assistenza con il numero d’ordine.",
      error_service_unavailable: "Il servizio di attivazione è temporaneamente non disponibile. Riprova più tardi o contatta l’assistenza.",
      error_invalid_request: "La richiesta è incompleta. Creala di nuovo in Solidon3D e seleziona il nuovo file."
    },
    pt: {
      document_title: "Ativar o Solidon3D offline", language: "Idioma", skip: "Saltar para o conteúdo",
      brand_home: "Página inicial do Solidon3D", language_navigation: "Seleção de idioma", steps_label: "Três passos",
      kicker: "Ligue uma vez e depois fique offline", title: "Ativar o Solidon3D offline",
      lead: "O computador com o Solidon permanece sem internet. Apenas este pedido de ativação é transmitido e verificado uma vez.",
      step_1_title: "Guardar o pedido", step_1_text: "No Solidon, abra Ajuda → Desbloquear o Solidon → Ativar offline.",
      step_2_title: "Selecioná-lo aqui", step_2_text: "O ficheiro termina em .solidon-request. Não precisa de introduzir mais nada.",
      step_3_title: "Levar a resposta", step_3_text: "Transfira a resposta e importe-a no computador com o Solidon.",
      form_title: "Selecionar o pedido de ativação", form_text: "O ficheiro contém a chave de licença, o nome escolhido para o computador e uma chave pública aleatória do dispositivo.",
      file_label: "Escolher ficheiro", no_file: "Nenhum ficheiro selecionado", selected_file: "Selecionado",
      file_help: ".solidon-request · apenas alguns kilobytes", or: "ou",
      paste_toggle: "Não consegue selecionar o ficheiro?", paste_help: "Abra o pedido como texto e cole aqui todo o conteúdo.",
      paste_label: "Colar o conteúdo do ficheiro", submit: "Verificar o pedido e ativar este computador",
      result_kicker: "✓ Verificação concluída", result_title: "A resposta está pronta", checking_title: "A verificar o pedido",
      error_title: "A ativação ainda não é possível", download: "Transferir ficheiro de resposta",
      no_account_title: "Sem conta. Sem dados de hardware.",
      privacy: "São guardados os dados de ativação e um contador diário curto por chave. Além disso, um pseudónimo HMAC do endereço IP protege contra abusos por no máximo 15 minutos; o próprio endereço IP, projetos, modelos e características do hardware não são guardados nestes dados da aplicação.",
      privacy_link: "Ler a declaração de privacidade", help_title: "Algo não está a funcionar?",
      help_text: "O pedido permanece inalterado. Tente novamente ou contacte o suporte com o número da encomenda.",
      home: "Início", legal: "Aviso legal", privacy_short: "Privacidade",
      checking: "O pedido está a ser verificado em segurança …", ready: "A ativação foi concedida. Transfira a resposta e importe-a no computador com o Solidon.",
      checking_kicker: "Verificação em curso", error_kicker: "Não concluído", error_large: "O pedido é invulgarmente grande. Volte a criá-lo no Solidon.",
      error_file: "Não foi possível ler o ficheiro. Selecione novamente o pedido de ativação.",
      error_network: "O serviço de ativação não está disponível neste momento. Tente novamente ou contacte o suporte.",
      error_unreadable: "O serviço de ativação não enviou uma resposta legível. Tente novamente ou contacte o suporte.",
      error_rejected: "O pedido foi recusado. Verifique a chave de licença ou contacte o suporte com o número da encomenda.",
      error_kind: "A resposta não contém um certificado do dispositivo. Tente novamente ou contacte o suporte.",
      error_empty: "Selecione primeiro o ficheiro .solidon-request.",
      error_device_limit: "Esta chave de licença já está ativa noutro computador. Desative-a nesse computador ou contacte o suporte com o número da encomenda.",
      error_rate_limit: "Hoje houve demasiadas tentativas com esta chave de licença. Tente amanhã ou contacte o suporte.",
      error_wrong_major: "A chave de licença pertence a outra versão principal do Solidon3D.",
      error_licence_blocked: "Esta chave de licença foi bloqueada. Contacte o suporte com o número da encomenda.",
      error_service_unavailable: "O serviço de ativação está temporariamente indisponível. Tente novamente mais tarde ou contacte o suporte.",
      error_invalid_request: "O pedido está incompleto. Crie-o novamente no Solidon3D e selecione o novo ficheiro."
    }
  };

  const form = document.querySelector("#activation-form");
  const file = document.querySelector("#request-file");
  const fileName = document.querySelector("#request-file-name");
  const text = document.querySelector("#request-text");
  const result = document.querySelector("#activation-result");
  const resultKicker = document.querySelector("#activation-result-kicker");
  const resultTitle = result && result.querySelector("h2");
  const message = document.querySelector("#activation-message");
  const download = document.querySelector("#activation-download");
  const language = document.querySelector("#activation-language");
  const skip = document.querySelector(".skip");
  const submit = form && form.querySelector('button[type="submit"]');
  const MAX_REQUEST_BYTES = 32768;
  let answer = "";
  let activeLanguage = "de";
  let resultMessageKey = "";
  let selectedFilename = "";

  if (!(form && file && fileName && text && result && resultKicker && resultTitle && message && download && language && skip && submit)) return;

  const phrase = (key) => translations[activeLanguage][key] || translations.de[key] || key;
  const chooseLanguage = (wanted) => Object.hasOwn(translations, wanted) ? wanted : "de";
  const updateFileName = () => {
    fileName.textContent = selectedFilename
      ? `${phrase("selected_file")}: ${selectedFilename}`
      : phrase("no_file");
  };

  const applyLanguage = (wanted, updateAddress = false) => {
    activeLanguage = chooseLanguage(wanted);
    document.documentElement.lang = activeLanguage;
    document.title = phrase("document_title");
    language.value = activeLanguage;
    language.setAttribute("aria-label", phrase("language"));
    skip.textContent = phrase("skip");
    for (const node of document.querySelectorAll("[data-i18n]")) {
      node.textContent = phrase(node.dataset.i18n);
    }
    for (const node of document.querySelectorAll("[data-i18n-aria]")) {
      node.setAttribute("aria-label", phrase(node.dataset.i18nAria));
    }
    updateFileName();
    if (!result.hidden && resultMessageKey) renderResult();
    if (updateAddress) {
      const address = new URL(window.location.href);
      address.searchParams.set("lang", activeLanguage);
      history.replaceState(null, "", address);
    }
  };

  const requested = new URLSearchParams(window.location.search).get("lang");
  const browserLanguage = (navigator.language || "de").split("-")[0];
  applyLanguage(chooseLanguage(requested || browserLanguage));
  language.addEventListener("change", () => applyLanguage(language.value, true));

  function renderResult() {
    const kind = result.dataset.state;
    const titleKey = kind === "success" ? "result_title" : kind === "loading" ? "checking_title" : "error_title";
    const kickerKey = kind === "success" ? "result_kicker" : kind === "loading" ? "checking_kicker" : "error_kicker";
    resultKicker.textContent = phrase(kickerKey);
    resultTitle.textContent = phrase(titleKey);
    message.textContent = phrase(resultMessageKey);
  }

  const showResult = (kind, messageKey) => {
    result.hidden = false;
    result.dataset.state = kind;
    result.setAttribute("role", kind === "error" ? "alert" : "status");
    resultMessageKey = messageKey;
    renderResult();
    result.focus({preventScroll: true});
    result.scrollIntoView({behavior: "smooth", block: "nearest"});
  };

  const resetResult = () => {
    answer = "";
    resultMessageKey = "";
    result.hidden = true;
    delete result.dataset.state;
    result.removeAttribute("role");
    message.textContent = "";
    download.hidden = true;
  };

  const serverErrorKey = (response, parsed) => {
    const code = parsed && typeof parsed.code === "string" ? parsed.code : "";
    const specific = `error_${code}`;
    if (code && Object.hasOwn(translations.de, specific)) return specific;
    return response.status >= 500 ? "error_network" : "error_rejected";
  };

  const updateSubmit = () => {
    submit.disabled = !text.value.trim();
  };

  file.addEventListener("change", async () => {
    resetResult();
    text.value = "";
    updateSubmit();
    const chosen = file.files && file.files[0];
    selectedFilename = chosen ? chosen.name : "";
    updateFileName();
    if (!chosen) return;
    if (chosen.size > MAX_REQUEST_BYTES) {
      file.setCustomValidity(phrase("error_large"));
      file.reportValidity();
      return;
    }
    file.setCustomValidity("");
    try {
      text.value = await chosen.text();
      updateSubmit();
      submit.focus();
    } catch (_problem) {
      text.value = "";
      updateSubmit();
      file.setCustomValidity(phrase("error_file"));
      file.reportValidity();
    }
  });
  text.addEventListener("input", () => {
    resetResult();
    file.value = "";
    // Die abgelehnte Datei ist weg — ihre Fehlermeldung muss es auch sein,
    // sonst hält die Formularprüfung den Knopf an, der längst wieder geht.
    file.setCustomValidity("");
    selectedFilename = "";
    updateFileName();
    updateSubmit();
  });
  updateSubmit();

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    resetResult();
    submit.disabled = true;
    file.disabled = true;
    text.readOnly = true;
    form.setAttribute("aria-busy", "true");
    const request = text.value.trim();
    if (!request) {
      showResult("error", "error_empty");
      updateSubmit();
      file.disabled = false;
      text.readOnly = false;
      form.removeAttribute("aria-busy");
      return;
    }
    if (new TextEncoder().encode(request).byteLength > MAX_REQUEST_BYTES) {
      showResult("error", "error_large");
      updateSubmit();
      file.disabled = false;
      text.readOnly = false;
      form.removeAttribute("aria-busy");
      return;
    }
    showResult("loading", "checking");
    try {
      const response = await fetch("/api/activation.php", {
        method: "POST",
        headers: {"Content-Type": "application/json; charset=utf-8"},
        body: request,
        cache: "no-store",
        credentials: "same-origin"
      });
      const body = await response.text();
      let parsed;
      try {
        parsed = JSON.parse(body);
      } catch (_problem) {
        throw new Error("error_unreadable");
      }
      if (!response.ok || parsed.ok === false) {
        throw new Error(serverErrorKey(response, parsed));
      }
      if (parsed.kind !== "activation-certificate") throw new Error("error_kind");
      answer = body;
      showResult("success", "ready");
      download.hidden = false;
    } catch (problem) {
      const detailKey = problem instanceof TypeError
        ? "error_network"
        : problem instanceof Error && Object.hasOwn(translations.de, problem.message)
          ? problem.message : "error_rejected";
      showResult("error", detailKey);
    } finally {
      updateSubmit();
      file.disabled = false;
      text.readOnly = false;
      form.removeAttribute("aria-busy");
    }
  });

  download.addEventListener("click", () => {
    if (!answer) return;
    const link = document.createElement("a");
    const address = URL.createObjectURL(new Blob([answer], {type: "application/json"}));
    link.href = address;
    link.download = "solidon-aktivierung.solidon-activation";
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(address), 0);
  });
})();
