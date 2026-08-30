"""Die Sätze, die der Börsenserver an den Kunden schickt.

**Der Server spricht sechs Sprachen, kann aber keine Kataloge lesen.** Die
Übersetzungen liegen in ``app/i18n/locales/`` und damit in der Anwendung; PHP
kommt nicht daran. Wer die Sätze deshalb im PHP-Quelltext lässt, hat eine
Oberfläche, die in sechs Sprachen spricht, und einen Server, der auf eine
davon antwortet — ein spanischer Kunde lädt auf ``es/shared.html`` hoch und
bekommt eine deutsche Fehlermeldung und eine deutsche Mail.

Deshalb steht hier die **eine** Quelle. Jeder Satz ist ein ``_(…)``, also
sieht ``app/i18n/extract.py`` ihn wie jeden Oberflächentext, und
``tests/test_translations.py`` prüft alle sechs Sprachen mit. Daraus erzeugt
``tools/make_shared_texts.py`` die Datei ``website/api/shared-texts.json``,
die PHP nach dem ``lang``-Parameter der Seite ausliest.

**Warum das Modul in ``app/`` liegt und nicht in ``tools/``**, obwohl der
Kunde diese Sätze in der Anwendung nie sieht: Unter ``app/`` findet der
Einsammler es über ``rglob("*.py")`` von selbst. In ``tools/`` fände er es nur
über einen Eintrag in ``EXTRA_SOURCES`` — und wer den vergisst, bekommt keinen
Fehler, sondern Sätze, die in keinem Katalog auftauchen und darum nie übersetzt
werden. Ein paar Kilobyte im Paket sind der billigere Preis als eine Lücke,
die niemand meldet (gemessen und entschieden mit 72 am 30.08.2026).

**Die Platzhalter füllt die PHP-Seite.** Sie heißen, wie sie hier stehen; ein
``{limit}``, das niemand füllt, steht beim Kunden so da. Benannt und nicht
``%d``, weil die Wortstellung je Sprache wechselt: Im Deutschen steht die
Grenze hinten, im Französischen kann sie vorn stehen.
"""

from __future__ import annotations

from app.i18n import TranslatableText, _

#: Was der Server antwortet — Schlüssel, wie PHP sie anfragt.
#:
#: Ein Satz steht hier **einmal**, auch wo PHP ihn an vier Stellen wirft:
#: „Diesen Baustein kennt die Börse nicht" ist eine Aussage und keine vier.
MESSAGES: dict[str, TranslatableText] = {
    # Hochladen
    "upload_no_file": _("Es kam keine Datei an. Wählen Sie ein Rezept aus und senden Sie erneut."),
    "upload_incomplete": _(
        "Die Datei kam nicht vollständig an. Prüfen Sie ihre Größe und senden Sie erneut."
    ),
    "upload_too_large": _("Die Datei ist {size} Byte groß, erlaubt sind {limit}."),
    "upload_unreadable": _("Die hochgeladene Datei ließ sich nicht lesen."),
    "upload_needs_address": _(
        "Für eine Einreichung braucht die Börse eine Mailadresse — sie wird nicht "
        "angezeigt und dient nur der Bestätigung. Tragen Sie eine gültige Adresse ein."
    ),
    "upload_not_a_recipe": _("Die Datei ist kein Rezept, das die Börse annehmen kann."),
    "upload_too_many_today": _(
        "Von dieser Adresse sind heute schon genug Einreichungen gekommen. "
        "Versuchen Sie es morgen wieder."
    ),
    "upload_store_failed": _("Die Datei ließ sich auf dem Server nicht ablegen."),
    "upload_accepted": _(
        "Angenommen. In Ihrem Postfach liegt ein Link — erst nach dem Klick "
        "darauf ist der Baustein öffentlich sichtbar."
    ),
    "upload_mail_failed": _(
        "Der Baustein liegt auf dem Server, aber die Bestätigungsmail ging nicht "
        "hinaus. Melden Sie sich beim Support, dann schalten wir ihn von Hand frei."
    ),
    # Bestätigen einer Einreichung
    "confirm_incomplete": _("Dieser Bestätigungslink ist unvollständig."),
    "confirm_unknown": _(
        "Diesen Bestätigungslink kennt die Börse nicht — vielleicht wurde er schon "
        "benutzt. Sehen Sie in der Börse nach, ob Ihr Baustein bereits dasteht."
    ),
    "confirm_expired": _(
        "Dieser Bestätigungslink ist abgelaufen. Laden Sie den Baustein erneut hoch."
    ),
    "confirm_done": _("Bestätigt. Der Baustein steht jetzt in der Börse."),
    # Zurückziehen
    "withdraw_incomplete": _(
        "Dieser Rückziehlink ist unvollständig. Nehmen Sie den vollständigen Link aus "
        "der Mail, die Sie beim Einreichen bekommen haben."
    ),
    "withdraw_part_done": _(
        "Zurückgezogen. Der Baustein ist gelöscht, und die Verknüpfung zu Ihrer Adresse mit ihm."
    ),
    "withdraw_comment_done": _("Zurückgezogen. Der Kommentar ist gelöscht."),
    "withdraw_unknown": _(
        "Zu diesem Schlüssel gibt es nichts mehr — vielleicht haben Sie den Beitrag "
        "bereits zurückgezogen. Sehen Sie in der Börse nach, ob er noch dasteht."
    ),
    # Ein einzelner Baustein
    "part_unknown": _("Diesen Baustein kennt die Börse nicht."),
    "part_file_missing": _("Die Datei zu diesem Baustein fehlt auf dem Server."),
    # Like
    "like_bad_browser_key": _(
        "Diese Browser-Kennung kann die Börse nicht verwenden. Laden Sie die Seite "
        "neu — sie legt dann eine neue an."
    ),
    # Kommentieren
    "comment_empty": _("Der Kommentar ist leer."),
    "comment_too_long": _("Der Kommentar ist länger als {limit} Zeichen."),
    "comment_has_markup": _("Der Kommentar enthält einen Link oder eine Auszeichnung."),
    "comment_name_too_long": _("Der Name ist länger als {limit} Zeichen."),
    "comment_name_has_markup": _("Der Name enthält eine Auszeichnung."),
    "comment_mail_failed": _(
        "Die Bestätigungsmail ging nicht hinaus. Melden Sie sich beim Support, dann "
        "schalten wir den Kommentar von Hand frei."
    ),
    "comment_confirm_unknown": _(
        "Diesen Bestätigungslink kennt die Börse nicht — vielleicht wurde der "
        "Kommentar schon zurückgezogen."
    ),
    "comment_confirm_expired": _(
        "Dieser Bestätigungslink ist abgelaufen. Schreiben Sie den Kommentar erneut."
    ),
    # Der Server selbst
    "unknown_action": _(
        "Diese Anfrage kennt die Börse nicht. Möglich sind upload, confirm, list, "
        "download, withdraw, like, comment, comments und confirm_comment."
    ),
    "server_error": _("Die Börse hat einen Fehler auf dem Server."),
    "not_configured": _("Die Tauschbörse ist auf diesem Server noch nicht eingerichtet."),
    "store_no_folder": _("Die Tauschbörse kann ihren Ablageordner nicht anlegen."),
    "store_no_database": _("Die Tauschbörse erreicht ihre Datenbank nicht."),
    "store_no_files_folder": _("Die Tauschbörse kann ihren Dateiordner nicht anlegen."),
}

#: Betreff und Text der beiden Bestätigungsmails.
#:
#: **Der Text steht als Ganzes und nicht in Stücken.** In PHP ist er aus acht
#: Fragmenten zusammengesetzt; übersetzt man die einzeln, entstehen sechs
#: Briefe, deren Sätze in keiner Sprache aufeinander zulaufen. Der Fluss eines
#: Briefes ist Teil seiner Verständlichkeit.
MAILS: dict[str, TranslatableText] = {
    "mail_upload_subject": _("Ihre Einreichung bestätigen"),
    "mail_upload_body": _(
        "Hallo,\n"
        "\n"
        "Sie haben „{title}“ in der Solidon-Tauschbörse eingereicht.\n"
        "\n"
        "Mit diesem Link wird er öffentlich sichtbar:\n"
        "\n"
        "{link}\n"
        "\n"
        "Der Link gilt {hours} Stunden. Wenn Sie nichts eingereicht haben, "
        "ignorieren Sie diese Nachricht — ohne Klick wird nichts veröffentlicht.\n"
        "\n"
        "Heben Sie diese Nachricht auf: Mit dem folgenden Link ziehen Sie Ihren "
        "Baustein jederzeit selbst zurück. Er wird dann gelöscht, und die "
        "Verknüpfung zu Ihrer Adresse geht mit.\n"
        "\n"
        "{withdraw}\n"
    ),
    "mail_comment_subject": _("Ihr Kommentar in der Solidon-Tauschbörse"),
    "mail_comment_body": _(
        "Hallo,\n"
        "\n"
        "Sie haben einen Kommentar in der Solidon-Tauschbörse geschrieben.\n"
        "\n"
        "Mit diesem Link wird er öffentlich sichtbar:\n"
        "\n"
        "{link}\n"
        "\n"
        "Der Link gilt {hours} Stunden. Wenn Sie nichts geschrieben haben, "
        "ignorieren Sie diese Nachricht — ohne Klick wird nichts veröffentlicht.\n"
        "\n"
        "Heben Sie diese Nachricht auf: Mit dem folgenden Link ziehen Sie Ihren "
        "Kommentar jederzeit selbst zurück. Er wird dann gelöscht, und die "
        "Verknüpfung zu Ihrer Adresse geht mit.\n"
        "\n"
        "{withdraw}\n"
    ),
}


#: Was die Formatprüfung an einer Datei beanstandet (Konzept §3.1, §3.2).
#:
#: **Diese Sätze sind ein Sonderfall unter den Servertexten.** Bei allen
#: anderen ist es gleichgültig, ob Anwendung und Server denselben Wortlaut
#: wählen — hier ist es die Zusage: Dieselbe Datei muss auf beiden Seiten
#: dasselbe Urteil bekommen, sonst sucht der Kunde den Fehler bei sich. Die
#: Anwendung nimmt seine Datei an, der Server wirft sie weg, und niemand kann
#: ihm erklären, warum.
#:
#: **Feldnamen bleiben englisch, auch mitten im deutschen Satz.** „``title`` ist
#: kein Text" liest sich hölzern, und die Alternative wäre schlimmer: Der Kunde
#: sucht das Feld **in seiner Datei**, und dort heißt es `title`. Dieselbe
#: Entscheidung wie bei `skirt`, `brim` und `raft` in den Druckeinstellungen —
#: `.claude/rules/oberflaeche.md` nennt einen Wert, der anders heißt als sein
#: Feld, „eine Fährte ins Nichts". Wer das später „aufräumt", nimmt dem Kunden
#: die einzige Angabe, mit der er die Stelle findet.
CHECKS: dict[str, TranslatableText] = {
    "check_not_json": _("Die Datei ist kein gültiges JSON."),
    "check_not_object": _("Ein Rezept ist ein Objekt, keine Liste und keine Zahl."),
    "check_unknown_keys": _("Unbekannte Schlüssel: {keys}."),
    "check_bad_version": _(
        "Die Formatversion {version} kennt der Server nicht — bekannt sind {known}."
    ),
    "check_field_not_text": _("„{field}“ ist kein Text."),
    "check_field_too_long": _("„{field}“ ist {length} Zeichen lang, erlaubt sind {limit}."),
    "check_field_has_link": _("„{field}“ enthält einen Link oder Auszeichnung."),
    "check_licence_not_text": _("„license“ ist kein Text."),
    "check_licence_unknown": _("„{licence}“ ist keine der erlaubten Lizenzen."),
    "check_author_not_text": _("„author“ ist kein Text."),
    "check_author_too_long": _("„author“ ist {length} Zeichen lang, erlaubt sind {limit}."),
    "check_author_has_markup": _("„author“ enthält eine Auszeichnung."),
    "check_document_not_object": _("„document“ ist kein Objekt."),
    "check_ops_not_list": _("„ops“ ist keine Liste."),
    "check_step_not_object": _("Schritt {n} ist kein Objekt."),
    "check_step_unknown_op": _("Schritt {n} nennt die unbekannte Operation {name}."),
    "check_params_not_object": _("Schritt {n} hat Parameter, die kein Objekt sind."),
    "check_value_not_allowed": _(
        "Schritt {n}, Parameter „{key}“ hat einen Wert, der nicht erlaubt ist."
    ),
    "check_payloads_not_object": _("„payloads“ ist kein Objekt."),
    "check_payload_not_text": _("Der Anhang „{name}“ ist keine Zeichenkette."),
    "check_payload_not_base64": _("Der Anhang „{name}“ ist kein base64."),
    "check_name_not_snake_case": _(
        "„{name}“ ist kein gültiger Bausteinname — erlaubt sind Kleinbuchstaben, "
        "Ziffern und Unterstriche, beginnend mit einem Buchstaben."
    ),
    "check_missing_field": _("Das Pflichtfeld „{field}“ fehlt."),
    "check_unknown_group": _("Die Gruppe „{group}“ gibt es nicht — bekannt sind {known}."),
    "check_no_features": _(
        "Der Baustein benennt kein einziges Merkmal. Ohne benanntes Merkmal "
        "lässt er sich nicht einsetzen."
    ),
}


def all_texts() -> dict[str, TranslatableText]:
    """Alles, was der Erzeuger in die JSON-Datei schreibt.

    Meldungen, Mails und Prüfbefunde zusammen — für ``make_shared_texts.py``
    ist es eine Tabelle, getrennt sind sie nur hier, wo jemand sie liest.
    """
    return {**MESSAGES, **MAILS, **CHECKS}
