"""Übersetzbare Befunde der lokalen Rezeptdatei-Prüfung."""

from __future__ import annotations

from app.i18n import TranslatableText, _

#: Was die lokale Formatprüfung an einer Rezeptdatei beanstandet.
#: Feldnamen bleiben englisch, weil der Kunde genau diese Schlüssel in der
#: Datei wiederfindet.
CHECKS: dict[str, TranslatableText] = {
    "file_too_large": _(
        "Die Bausteindatei ist größer als erlaubt — höchstens {limit} Byte sind möglich."
    ),
    "check_not_json": _("Die Datei ist kein gültiges JSON."),
    "check_not_object": _("Ein Rezept ist ein Objekt, keine Liste und keine Zahl."),
    "check_unknown_keys": _("Unbekannte Schlüssel: {keys}."),
    "check_bad_version": _(
        "Die Formatversion {version} kennt diese Installation nicht — bekannt sind {known}."
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
