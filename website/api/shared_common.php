<?php
/**
 * Die Formatprüfung der Tauschbörse — dieselbe wie im Kern, nur auf dem Server.
 *
 * Warum es diese Datei gibt: Robert hat entschieden, dass Kunden ohne Sichtung
 * hochladen („automatisches hochladen durch kunden", 30.08.2026). Damit ist
 * diese Prüfung **die einzige Instanz vor der Veröffentlichung** — im Entwurf
 * war sie die zweite Verteidigungslinie, jetzt ist sie die erste. Wer die
 * Börse baut, fängt bei ihr an (Konzept §7).
 *
 * Gegenstück: app/core/knowledge/parts/shared.py. Beide lesen **dieselbe
 * Datei** — `shared-rules.json`, geschrieben von tools/make_shared_rules.py
 * aus dem Register. Es gibt keine zweite Liste, die altern könnte; das war
 * 72s Auflage, und sie kommt aus einem gemessenen Fall: Skizzenlöser und
 * Serializer führten dieselben Bedingungsarten in zwei Listen, und die eine
 * ließ durch, was die andere verwarf.
 *
 * **Die Befundtexte sind wörtlich die des Kerns.** Nicht aus Bequemlichkeit:
 * Dieselbe Datei muss auf beiden Seiten dasselbe Urteil bekommen, und ein
 * Kunde, dem die App etwas anderes sagt als der Server, sucht den Fehler bei
 * sich. Wer einen Text hier ändert, ändert ihn dort mit.
 *
 * **Was hier nicht passiert: ausführen.** Ein Rezept ist eine Liste
 * registrierter Operationen mit Werten (Regel 13). Diese Datei liest JSON,
 * vergleicht Namen gegen eine Erlaubnisliste und misst Längen — sie ruft
 * nichts auf, was in der Datei steht, und `eval` kommt darin nicht vor.
 *
 * Braucht PHP 7.4 oder neuer und mbstring.
 */

declare(strict_types=1);

/** Wo die Regelquelle liegt — neben dieser Datei, von make_shared_rules.py erzeugt. */
const RULES_FILE = __DIR__ . '/shared-rules.json';

/**
 * Links und Auszeichnung in Titel und Erklärtext.
 *
 * Spiegelt `FORBIDDEN_TEXT`. Die Börse zeigt beide Felder öffentlich, und ein
 * Titel, der eine Adresse trägt, ist eine Anzeige.
 */
const FORBIDDEN_TEXT = '~https?://|www\.|<[a-zA-Z/!]~i';

/**
 * Dasselbe ohne die Link-Hälfte — fürs Autorenfeld.
 *
 * Ein Autor darf sagen, wo man ihn findet; eine Auszeichnung einschleusen
 * darf er nicht. Zwei Muster, weil die zwei Felder zwei Fragen beantworten.
 */
const FORBIDDEN_MARKUP = '~<[a-zA-Z/!]~';

/**
 * Die Regelliste. Fehlt sie, ist das kein leerer Erlaubnisrahmen, sondern ein
 * Abbruch: Eine Erlaubnisliste, die niemand gefüllt hat, lässt sonst alles
 * durch, was keinen Namen hat.
 */
function shared_rules(): array
{
    $raw = @file_get_contents(RULES_FILE);
    if ($raw === false) {
        throw new RuntimeException('Die Regelliste shared-rules.json fehlt auf dem Server.');
    }
    $rules = json_decode($raw, true);
    if (!is_array($rules) || empty($rules['operations']) || empty($rules['recipe_keys'])) {
        throw new RuntimeException('Die Regelliste shared-rules.json ist unvollständig.');
    }
    return $rules;
}

//: Die Sätze, die der Server an den Kunden schickt — erzeugt aus dem Kern.
const TEXTS_FILE = __DIR__ . '/shared-texts.json';

//: Die Sprache, in der geantwortet wird, wenn die gewünschte fehlt.
//:
//: Nicht Deutsch: Wer auf `es/shared.html` steht und Spanisch nicht bekommt,
//: versteht Englisch eher als Deutsch. Die Quellsprache ist die des Codes,
//: nicht die des Kunden.
const TEXTS_FALLBACK = 'en';

/**
 * Die Satztabelle einer Sprache.
 *
 * **Die Liste der Sprachen steht in der Datei und nicht hier.** Eine
 * aufgezählte Whitelist in PHP wäre die Stelle, an der eine siebte Sprache
 * hängen bliebe: `available_languages()` liest das Katalogverzeichnis, der
 * Erzeuger schreibt jede gefundene Sprache, und dieser Server nimmt, was da
 * ist. Wer eine Sprache einlegt, legt eine Datei ab — mehr nicht.
 *
 * Geprüft wird die Gestalt des Parameters trotzdem, und zwar bevor er als
 * Schlüssel dient: Ein `lang` aus der Adresszeile ist Kundeneingabe.
 */
function shared_texts(?string $language = null): array
{
    static $tables = null;
    if ($tables === null) {
        $raw = @file_get_contents(TEXTS_FILE);
        if ($raw === false) {
            throw new RuntimeException('Die Satzliste shared-texts.json fehlt auf dem Server.');
        }
        $tables = json_decode($raw, true);
        if (!is_array($tables) || !isset($tables[TEXTS_FALLBACK])) {
            throw new RuntimeException('Die Satzliste shared-texts.json ist unvollständig.');
        }
    }

    $wanted = $language ?? (string) ($_GET['lang'] ?? $_POST['lang'] ?? '');
    if (preg_match('/^[a-z]{2}$/D', $wanted) !== 1 || !isset($tables[$wanted])) {
        $wanted = TEXTS_FALLBACK;
    }
    return $tables[$wanted];
}

/**
 * Ein Satz in der Sprache des Kunden, mit gefüllten Platzhaltern.
 *
 * **Ein Platzhalter, den niemand füllt, steht beim Kunden so da.** Deshalb
 * bleibt kein `{…}` übrig: Was `$values` nicht kennt, wird nicht durchgereicht,
 * sondern der Satz fällt auf die Fallback-Sprache zurück und, wenn auch die
 * ihn nicht hat, auf den Schlüssel selbst — der ist häßlich, aber er sagt
 * wenigstens, was fehlt.
 *
 * Benannte Platzhalter und nicht `%s`: Die Wortstellung wechselt je Sprache,
 * im Deutschen steht eine Grenze hinten, im Französischen kann sie vorn stehen.
 */
function shared_text(string $key, array $values = []): string
{
    $table = shared_texts();
    $sentence = $table[$key] ?? '';
    if ($sentence === '') {
        $sentence = shared_texts(TEXTS_FALLBACK)[$key] ?? $key;
    }
    foreach ($values as $name => $value) {
        $sentence = str_replace('{' . $name . '}', (string) $value, $sentence);
    }
    return $sentence;
}

/**
 * Ob ein Parameterwert eine der erlaubten Formen hat.
 *
 * `$depth` bricht nach einer Ebene ab: Eine Liste von Zahlen ist ein
 * Parameter, eine Liste von Listen von Listen ist eine Struktur, die sich
 * jemand ausgedacht hat.
 *
 * **In PHP braucht das eine Prüfung mehr als in Python.** `json_decode` mit
 * `true` macht aus Objekt *und* Array beides ein `array`; ohne die Frage nach
 * fortlaufenden Schlüsseln käme ein verschachteltes Objekt als Liste durch.
 */
function shared_value_is_allowed($value, int $depth = 0): bool
{
    if (is_bool($value) || is_int($value) || is_float($value) || is_string($value)) {
        return true;
    }
    if (is_array($value) && $depth === 0 && array_is_list_compat($value)) {
        foreach ($value as $item) {
            if (!shared_value_is_allowed($item, $depth + 1)) {
                return false;
            }
        }
        return true;
    }
    return false;
}

/** `array_is_list` gibt es erst ab PHP 8.1; der Server fährt 7.4 aufwärts. */
function array_is_list_compat(array $value): bool
{
    $index = 0;
    foreach ($value as $key => $_) {
        if ($key !== $index++) {
            return false;
        }
    }
    return true;
}

/**
 * Ein Befund als Schlüssel und Werte, nicht als fertiger Satz.
 *
 * **Der Satz entsteht am Anzeigeort, das Urteil hier.** Solange beide
 * Prüfseiten ihre Sätze selbst bauten, war der Vergleich in
 * `tests/test_shared_php.py` scharf: Eine Mutation, die `mb_strlen` durch
 * `strlen` ersetzt, ließ ihn fallen, weil die Zahl **im Satz** stand — 200
 * Zeichen gegen 400 Bytes.
 *
 * Mit einer gemeinsamen Textquelle wäre genau diese Schärfe verschwunden:
 * Zwei Seiten, die denselben Satz aus derselben JSON holen, stimmen immer
 * überein. Der Test verglich dann zwei Lesevorgänge einer Datei und wäre grün
 * geblieben, ohne je rot zu werden (gefunden von 72 beim Lesen des
 * Vorschlags, 31.08.2026). Deshalb trägt ein Befund **beides**.
 */
function shared_finding(string $code, array $values = []): array
{
    return ['code' => $code, 'values' => (object) $values];
}

/**
 * Prüft eine hochgeladene Rezeptdatei. Leeres Feld heißt: nimmt der Server an.
 *
 * Gibt **alle** Befunde zurück und nicht nur den ersten — eine Ablehnung, die
 * nach jedem Berichtigen eine neue nennt, ist eine Kette ohne Ende.
 */
function shared_inspect(string $payload, array $rules): array
{
    $findings = [];

    $size = strlen($payload);
    if ($size > $rules['max_upload_bytes']) {
        // Derselbe Schlüssel wie beim Upload-Fehler und kein eigener
        // `check_*`: Es ist wörtlich derselbe Satz, und ein Satz steht einmal.
        $findings[] = shared_finding('upload_too_large', [
            'size' => $size,
            'limit' => (int) $rules['max_upload_bytes'],
        ]);
        // Weiter geht es trotzdem: Wer zwei Gründe hat, soll beide erfahren.
    }

    $data = json_decode($payload, true);
    if ($data === null && strtolower(trim($payload)) !== 'null') {
        $findings[] = shared_finding('check_not_json');
        return $findings;
    }
    if (!is_array($data) || array_is_list_compat($data)) {
        $findings[] = shared_finding('check_not_object');
        return $findings;
    }

    $unknown = array_values(array_diff(array_keys($data), $rules['recipe_keys']));
    sort($unknown);
    if ($unknown) {
        $findings[] = shared_finding('check_unknown_keys', ['keys' => implode(', ', $unknown)]);
    }

    $version = $data['format_version'] ?? null;
    if (!in_array($version, $rules['recipe_format_versions'], true)) {
        // **Ohne Klammern**, und der rohe Wert statt einer Darstellung: Der
        // Kern liefert `", ".join(str(one) for one in …)`, und beide Seiten
        // müssen denselben Text erzeugen — sonst geht ausgerechnet dieser
        // Befund auseinander (abgestimmt mit 72).
        $findings[] = shared_finding('check_bad_version', [
            'version' => $version,
            'known' => implode(', ', $rules['recipe_format_versions']),
        ]);
    }

    $findings = array_merge(
        $findings,
        shared_text_findings($data, $rules),
        shared_adoptable_findings($data, $rules),
        shared_operation_findings($data, $rules),
        shared_payload_findings($data)
    );
    return $findings;
}

/**
 * Ob ein Rezept beim Empfänger überhaupt aufnehmbar ist (Konzept §3.1).
 *
 * **Der Anlass ist ein Ende-zu-Ende-Lauf von 3a:** `for_upload` gab dreimal
 * eine formal saubere Datei aus, die der Empfänger danach ablehnte — Name
 * nicht in `lower_snake_case`, Gruppe unbekannt, kein benanntes Merkmal. Der
 * Kunde klickt „Veröffentlichen", lädt hoch, und der Erste, der sie holt,
 * liest „ließ sich nicht aufnehmen".
 *
 * Die Prüfung steht deshalb **hier** und nicht beim Empfänger: Das ist die
 * erste und einzige Instanz vor der Veröffentlichung, und was durchkommt,
 * steht in der Galerie. Ein Server, der annimmt, was seine eigenen Nutzer
 * nicht öffnen können, ist die schlechtere Wahl.
 *
 * Muster und Gruppen sind **abgeleitet und nicht abgeschrieben**: Sie stehen
 * in `shared-rules.json`, die aus `parts/registry.py` entsteht. Ein
 * abgeschriebenes Muster liefe beim nächsten Zuwachs auseinander.
 */
function shared_adoptable_findings(array $data, array $rules): array
{
    $findings = [];

    $name = $data['name'] ?? null;
    if (is_string($name) && !preg_match('~' . $rules['name_pattern'] . '~', $name)) {
        $findings[] = shared_finding('check_name_not_snake_case', ['name' => $name]);
    }

    // Die Pflichtfelder stehen in der Regeldatei und sind aus den
    // Dataclass-Feldern ohne Vorgabewert abgeleitet — was ein Rezept ohne
    // Vorgabe braucht, braucht auch die Börse.
    foreach ($rules['required_keys'] ?? [] as $field) {
        if (!array_key_exists($field, $data)) {
            $findings[] = shared_finding('check_missing_field', ['field' => $field]);
        }
    }

    // **Nur wenn die Gruppe da ist.** Fehlt sie ganz, ist das ein fehlendes
    // Pflichtfeld und keine unbekannte Gruppe: „Die Gruppe „None" gibt es
    // nicht" wäre technisch wahr und schickte den Kunden los, einen
    // Tippfehler zu suchen, den er nie gemacht hat — er sucht, findet nichts
    // und zweifelt an seiner Datei statt an der Meldung (72, 31.08.2026).
    $known = $rules['groups'] ?? [];
    $group = $data['group'] ?? null;
    if ($known && $group !== null && !in_array($group, $known, true)) {
        $findings[] = shared_finding('check_unknown_group', [
            'group' => $group,
            'known' => implode(', ', $known),
        ]);
    }

    if (!empty($rules['needs_features']) && empty($data['features'])) {
        $findings[] = shared_finding('check_no_features');
    }

    return $findings;
}

/** Titel und Beschreibung: Länge und keine Links (Konzept §3.2). */
function shared_text_findings(array $data, array $rules): array
{
    $findings = [];
    $limits = ['title' => $rules['max_title_chars'], 'doc' => $rules['max_doc_chars']];
    foreach ($limits as $key => $limit) {
        $text = $data[$key] ?? null;
        if ($text === null) {
            continue;
        }
        if (!is_string($text)) {
            $findings[] = shared_finding('check_field_not_text', ['field' => $key]);
            continue;
        }
        // `mb_strlen` und nicht `strlen`: Ein Titel mit Umlauten wäre sonst
        // länger, als er ist, und die Grenze eine andere als in der App.
        $length = mb_strlen($text, 'UTF-8');
        if ($length > $limit) {
            $findings[] = shared_finding('check_field_too_long', [
                'field' => $key,
                'length' => $length,
                'limit' => (int) $limit,
            ]);
        }
        if (preg_match(FORBIDDEN_TEXT, $text)) {
            $findings[] = shared_finding('check_field_has_link', ['field' => $key]);
        }
    }
    return array_merge($findings, shared_credit_findings($data, $rules));
}

/**
 * Lizenz und Autor — die zwei Felder, die eine Weitergabe erst erlauben.
 *
 * **Abwesend ist kein Fehler.** Geprüft wird die Zulässigkeit eines Wertes,
 * nie seine Anwesenheit; ob die Börse eine Lizenz verlangt, entscheidet die
 * Börse und nicht das Dateiformat.
 */
function shared_credit_findings(array $data, array $rules): array
{
    $findings = [];

    $licence = $data['license'] ?? null;
    if ($licence !== null && $licence !== '') {
        $allowed = $rules['licenses'] ?? [];
        if (!is_string($licence)) {
            $findings[] = shared_finding('check_licence_not_text');
        } elseif ($allowed && !in_array($licence, $allowed, true)) {
            $findings[] = shared_finding('check_licence_unknown', ['licence' => $licence]);
        }
    }

    $author = $data['author'] ?? null;
    if ($author !== null && $author !== '') {
        if (!is_string($author)) {
            $findings[] = shared_finding('check_author_not_text');
        } else {
            $limit = $rules['max_title_chars'];
            $length = mb_strlen($author, 'UTF-8');
            if ($length > $limit) {
                $findings[] = shared_finding('check_author_too_long', [
                    'length' => $length,
                    'limit' => (int) $limit,
                ]);
            }
            if (preg_match(FORBIDDEN_MARKUP, $author)) {
                $findings[] = shared_finding('check_author_has_markup');
            }
        }
    }
    return $findings;
}

/** Jeder Schritt nennt eine Operation, die der Server kennt (Konzept §3.1). */
function shared_operation_findings(array $data, array $rules): array
{
    $document = $data['document'] ?? null;
    if ($document === null) {
        return [];
    }
    if (!is_array($document) || array_is_list_compat($document)) {
        return [shared_finding('check_document_not_object')];
    }
    $steps = $document['ops'] ?? [];
    if (!is_array($steps) || !array_is_list_compat($steps)) {
        return [shared_finding('check_ops_not_list')];
    }

    $findings = [];
    $permitted = array_flip($rules['operations']);
    foreach ($steps as $index => $step) {
        $where = sprintf('Schritt %d', $index + 1);
        if (!is_array($step) || array_is_list_compat($step)) {
            $findings[] = shared_finding('check_step_not_object', ['n' => $index + 1]);
            continue;
        }
        $name = $step['op'] ?? null;
        if (!is_string($name) || !isset($permitted[$name])) {
            $findings[] = shared_finding('check_step_unknown_op', [
                'n' => $index + 1,
                'name' => $name,
            ]);
        }
        $params = $step['params'] ?? [];
        if (!is_array($params) || array_is_list_compat($params) && $params !== []) {
            $findings[] = shared_finding('check_params_not_object', ['n' => $index + 1]);
            continue;
        }
        foreach ($params as $key => $value) {
            if (!shared_value_is_allowed($value)) {
                $findings[] = shared_finding('check_value_not_allowed', [
                    'n' => $index + 1,
                    'key' => $key,
                ]);
            }
        }
    }
    return $findings;
}

/**
 * Anhänge sind base64 und werden nicht ausgeführt — nur gemessen (§3.6).
 *
 * Robert hat entschieden, dass Geometrie mitreist („ohne etwas zu verlieren“).
 * Sie wird deshalb nicht verboten, sondern gewogen: Was hier ankommt, ist eine
 * Zeichenkette, und die einzige Frage an sie ist, ob sie eine base64-Zeichenkette
 * ist. Entpackt wird sie hier nicht.
 */
function shared_payload_findings(array $data): array
{
    $payloads = $data['payloads'] ?? null;
    if ($payloads === null) {
        return [];
    }
    if (!is_array($payloads) || (array_is_list_compat($payloads) && $payloads !== [])) {
        return [shared_finding('check_payloads_not_object')];
    }
    $findings = [];
    foreach ($payloads as $key => $value) {
        if (!is_string($value)) {
            $findings[] = shared_finding('check_payload_not_text', ['name' => $key]);
            continue;
        }
        // `strict` wie in Python: Ohne das schluckt PHP jedes Zeichen, das
        // nicht ins Alphabet gehört, und meldet Erfolg für Müll.
        if (base64_decode($value, true) === false) {
            $findings[] = shared_finding('check_payload_not_base64', ['name' => $key]);
        }
    }
    return $findings;
}
