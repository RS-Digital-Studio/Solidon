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
        $findings[] = sprintf(
            'Die Datei ist %d Byte groß, erlaubt sind %d.',
            $size,
            $rules['max_upload_bytes']
        );
        // Weiter geht es trotzdem: Wer zwei Gründe hat, soll beide erfahren.
    }

    $data = json_decode($payload, true);
    if ($data === null && strtolower(trim($payload)) !== 'null') {
        $findings[] = 'Die Datei ist kein gültiges JSON.';
        return $findings;
    }
    if (!is_array($data) || array_is_list_compat($data)) {
        $findings[] = 'Ein Rezept ist ein Objekt, keine Liste und keine Zahl.';
        return $findings;
    }

    $unknown = array_values(array_diff(array_keys($data), $rules['recipe_keys']));
    sort($unknown);
    if ($unknown) {
        $findings[] = 'Unbekannte Schlüssel: ' . implode(', ', $unknown) . '.';
    }

    $version = $data['format_version'] ?? null;
    if (!in_array($version, $rules['recipe_format_versions'], true)) {
        $findings[] = sprintf(
            'Die Formatversion %s kennt der Server nicht — bekannt sind [%s].',
            $version === null ? 'None' : var_export($version, true),
            implode(', ', $rules['recipe_format_versions'])
        );
    }

    $findings = array_merge(
        $findings,
        shared_text_findings($data, $rules),
        shared_operation_findings($data, $rules),
        shared_payload_findings($data)
    );
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
            $findings[] = sprintf('„%s“ ist kein Text.', $key);
            continue;
        }
        // `mb_strlen` und nicht `strlen`: Ein Titel mit Umlauten wäre sonst
        // länger, als er ist, und die Grenze eine andere als in der App.
        $length = mb_strlen($text, 'UTF-8');
        if ($length > $limit) {
            $findings[] = sprintf('„%s“ ist %d Zeichen lang, erlaubt sind %d.', $key, $length, $limit);
        }
        if (preg_match(FORBIDDEN_TEXT, $text)) {
            $findings[] = sprintf('„%s“ enthält einen Link oder Auszeichnung.', $key);
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
            $findings[] = '„license“ ist kein Text.';
        } elseif ($allowed && !in_array($licence, $allowed, true)) {
            $findings[] = sprintf('„%s“ ist keine der erlaubten Lizenzen.', $licence);
        }
    }

    $author = $data['author'] ?? null;
    if ($author !== null && $author !== '') {
        if (!is_string($author)) {
            $findings[] = '„author“ ist kein Text.';
        } else {
            $limit = $rules['max_title_chars'];
            $length = mb_strlen($author, 'UTF-8');
            if ($length > $limit) {
                $findings[] = sprintf('„author“ ist %d Zeichen lang, erlaubt sind %d.', $length, $limit);
            }
            if (preg_match(FORBIDDEN_MARKUP, $author)) {
                $findings[] = '„author“ enthält eine Auszeichnung.';
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
        return ['„document“ ist kein Objekt.'];
    }
    $steps = $document['ops'] ?? [];
    if (!is_array($steps) || !array_is_list_compat($steps)) {
        return ['„ops“ ist keine Liste.'];
    }

    $findings = [];
    $permitted = array_flip($rules['operations']);
    foreach ($steps as $index => $step) {
        $where = sprintf('Schritt %d', $index + 1);
        if (!is_array($step) || array_is_list_compat($step)) {
            $findings[] = $where . ' ist kein Objekt.';
            continue;
        }
        $name = $step['op'] ?? null;
        if (!is_string($name) || !isset($permitted[$name])) {
            $findings[] = sprintf(
                '%s nennt die unbekannte Operation %s.',
                $where,
                $name === null ? 'None' : var_export($name, true)
            );
        }
        $params = $step['params'] ?? [];
        if (!is_array($params) || array_is_list_compat($params) && $params !== []) {
            $findings[] = $where . ' hat Parameter, die kein Objekt sind.';
            continue;
        }
        foreach ($params as $key => $value) {
            if (!shared_value_is_allowed($value)) {
                $findings[] = sprintf('%s, Parameter „%s“ hat einen Wert, der nicht erlaubt ist.', $where, $key);
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
        return ['„payloads“ ist kein Objekt.'];
    }
    $findings = [];
    foreach ($payloads as $key => $value) {
        if (!is_string($value)) {
            $findings[] = sprintf('Der Anhang „%s“ ist keine Zeichenkette.', $key);
            continue;
        }
        // `strict` wie in Python: Ohne das schluckt PHP jedes Zeichen, das
        // nicht ins Alphabet gehört, und meldet Erfolg für Müll.
        if (base64_decode($value, true) === false) {
            $findings[] = sprintf('Der Anhang „%s“ ist kein base64.', $key);
        }
    }
    return $findings;
}
