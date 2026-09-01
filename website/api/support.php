<?php
/**
 * Nimmt Rückmeldungen aus Solidon an und reicht sie als E-Mail weiter.
 *
 * Warum es diese Datei gibt: Ein Programm, das selbst zu einem Postausgang
 * spricht, trägt dessen Zugangsdaten in sich — und was in einer
 * ausgelieferten .exe steht, ist kein Geheimnis mehr. Hier liegt die einzige
 * Stelle, die das Postfach kennt, und sie liegt auf dem Server.
 *
 * Gegenstück: app/core/support.py. Feldnamen und Antwortformat stehen dort
 * fest; wer hier etwas umbenennt, benennt es dort mit um.
 *
 * Erwartet ein POST als multipart/form-data:
 *   kind, subject, contact, message, app_version, environment, file0..fileN
 * Antwortet immer JSON:
 *   {"ok":true,"reference":"S-20260820-1a2b3c"}  oder  {"ok":false,"error":"…"}
 *
 * Einrichtung: Datei nach httpdocs/api/support.php legen. Sonst nichts —
 * kein Composer, keine Bibliothek, keine Datenbank. Die Sperrliste gegen
 * Massensendungen legt sich selbst an.
 *
 * Braucht PHP 8.1 oder neuer und die Erweiterung mbstring; beides bringt
 * jedes Plesk mit. Und `post_max_size` muss über MAX_BYTES liegen, sonst
 * kommt eine große Sendung mit leeren $_POST an, nicht mit einem Fehler.
 */

declare(strict_types=1);

if (PHP_VERSION_ID < 80100) {
    http_response_code(503);
    exit;
}

// --- Einstellungen ---------------------------------------------------------

/** Wohin die Post geht. Fest verdrahtet: ein Empfänger aus einem Formularfeld
 *  wäre ein offenes Weiterleitungstor für jeden, der die Adresse kennt. */
const RECIPIENT = 'support@solidon3d.de';

/** Absender. Muss eine Adresse dieser Domain sein, sonst wirft der eigene
 *  Server sie wegen SPF weg. Die Adresse des Nutzers steht im Reply-To. */
const SENDER = 'noreply@solidon3d.de';

/** Wie groß eine Sendung höchstens sein darf. Etwas über der Grenze, die der
 *  Client selbst zieht (12 MB) — damit eine Sendung, die dort durchging, hier
 *  nicht an einem Byte scheitert. */
const MAX_BYTES = 14 * 1024 * 1024;

/** Wie viele Sendungen eine Adresse in einer Stunde schicken darf. Kein
 *  Schutz gegen einen entschlossenen Angreifer — einer gegen ein Skript, das
 *  die Adresse gefunden hat. */
const MAX_PER_HOUR = 12;
const MAX_GLOBAL_PER_HOUR = 3000;
/** Im Zustand bleiben bei jedem Zugriff höchstens die letzten 60 Minuten. */
const SUPPORT_RATE_RETENTION_SECONDS = 3600;

/** Wie viele Anhänge angenommen werden. Der Client schickt drei. */
const MAX_FILES = 6;

/** Dateiname des flüchtigen, aber gegen lokale Manipulation geschützten Zählers. */
const RATE_FILE = 'support-rate.json';

// --- Antwort ---------------------------------------------------------------

header('Content-Type: application/json; charset=utf-8');
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');
header('X-Frame-Options: DENY');
header('Permissions-Policy: camera=(), microphone=(), geolocation=()');
header("Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; base-uri 'none'");
header('Cache-Control: no-store');

/**
 * Antwortet und beendet. Ein Fehler nennt seinen Grund — der Client zeigt ihn
 * dem Nutzer, und „abgelehnt" allein hilft niemandem weiter.
 */
function answer(bool $ok, string $error = '', string $reference = '', int $status = 200): void
{
    http_response_code($status);
    $payload = $ok ? ['ok' => true, 'reference' => $reference] : ['ok' => false, 'error' => $error];
    echo json_encode($payload, JSON_UNESCAPED_UNICODE);
    exit;
}

/** Ein Kopfzeilenwert ohne Steuerzeichen. Der Umbruch ist der Weg, einer Mail
 *  fremde Empfänger unterzuschieben — der Client stutzt ihn schon, und eine
 *  Prüfung an einer Stelle ist keine. */
function header_safe(string $value, int $limit = 200): string
{
    $plain = preg_replace('/[\x00-\x1f\x7f]/u', ' ', $value) ?? '';
    return trim(mb_substr($plain, 0, $limit));
}

/** Ein Dateiname ohne Pfad, ohne Anführungszeichen, mit harmloser Endung. */
function file_safe(string $name): string
{
    $plain = preg_replace('/[^A-Za-z0-9._-]/', '_', basename($name)) ?? '';
    $plain = ltrim($plain, '.');
    return $plain === '' ? 'anhang.bin' : mb_substr($plain, 0, 120);
}

/** Akzeptiert ausschließlich Browserwerte, keine verschachtelten PHP-Felder. */
function support_post_text(string $name): string
{
    $value = $_POST[$name] ?? '';
    if (!is_string($value)) {
        answer(false, 'Ein Formularfeld hat den falschen Aufbau.', '', 400);
    }
    return $value;
}

/** Bindet Browser-Schreibzugriffe an die eigene Herkunft; die App sendet keinen Origin. */
function support_require_origin(): void
{
    $origin = trim((string) ($_SERVER['HTTP_ORIGIN'] ?? ''));
    if ($origin !== ''
        && !in_array(strtolower($origin), ['https://solidon3d.de', 'https://www.solidon3d.de'], true)) {
        answer(false, 'Die Herkunft der Sendung wurde abgelehnt.', '', 403);
    }
}

/** Prüft deklarierte und nach dem Parsen sichtbare Bytes gegen dieselbe Grenze. */
function support_request_bytes(): int
{
    $declared = (string) ($_SERVER['CONTENT_LENGTH'] ?? '');
    if ($declared !== '' && (!ctype_digit($declared) || (int) $declared > MAX_BYTES)) {
        answer(false, 'Die Sendung ist zu groß.', '', 413);
    }
    $total = 0;
    foreach ($_POST as $value) {
        if (!is_string($value)) {
            answer(false, 'Ein Formularfeld hat den falschen Aufbau.', '', 400);
        }
        $total += strlen($value);
    }
    foreach ($_FILES as $entry) {
        if (!is_array($entry) || is_array($entry['size'] ?? null)) {
            answer(false, 'Ein Anhang hat den falschen Aufbau.', '', 400);
        }
        $size = (int) ($entry['size'] ?? 0);
        if ($size < 0 || $size > MAX_BYTES) {
            answer(false, 'Ein Anhang ist zu groß.', '', 413);
        }
        $total += $size;
    }
    if ($total > MAX_BYTES) {
        answer(false, 'Die Sendung ist zu groß.', '', 413);
    }
    return $declared === '' ? $total : (int) $declared;
}

/** Legt den Missbrauchszähler außerhalb des Dokumentenstamms statt im gemeinsamen Temp-Ordner ab. */
function support_rate_path(): string
{
    $configured = getenv('SOLIDON_SUPPORT_RATE_FILE');
    $path = $configured === false || $configured === ''
        ? dirname(__DIR__, 2) . '/appdata/' . RATE_FILE
        : $configured;
    if (substr($path, 0, 1) !== DIRECTORY_SEPARATOR
        && preg_match('#^[A-Za-z]:[\\\\/]#', $path) !== 1) {
        answer(false, 'Der Schutz gegen Massensendungen ist nicht sicher eingerichtet.', '', 503);
    }
    $candidate = rtrim(str_replace('\\', '/', strtolower($path)), '/');
    $root = realpath((string) ($_SERVER['DOCUMENT_ROOT'] ?? dirname(__DIR__)))
        ?: realpath(dirname(__DIR__));
    if (preg_match('#(^|/)\.\.(/|$)#', $candidate) === 1) {
        answer(false, 'Der Schutz gegen Massensendungen ist nicht sicher eingerichtet.', '', 503);
    }
    $probe = $path;
    while (true) {
        if (is_link($probe)) {
            answer(false, 'Der Schutz gegen Massensendungen ist nicht sicher eingerichtet.', '', 503);
        }
        if (file_exists($probe)) {
            break;
        }
        $parent = dirname($probe);
        if ($parent === $probe) {
            answer(false, 'Der Schutz gegen Massensendungen ist nicht sicher eingerichtet.', '', 503);
        }
        $probe = $parent;
    }
    $resolved = realpath($probe);
    if ($resolved === false) {
        answer(false, 'Der Schutz gegen Massensendungen ist nicht sicher eingerichtet.', '', 503);
    }
    $candidate = rtrim(str_replace('\\', '/', strtolower($resolved)), '/');
    if ($root !== false) {
        $root = rtrim(str_replace('\\', '/', strtolower($root)), '/');
        if ($candidate === $root || strpos($candidate, $root . '/') === 0) {
            answer(false, 'Der Schutz gegen Massensendungen ist nicht sicher eingerichtet.', '', 503);
        }
    }
    $parent = dirname($path);
    if (!is_dir($parent) && !@mkdir($parent, 0700, true) && !is_dir($parent)) {
        answer(false, 'Der Schutz gegen Massensendungen ist gerade nicht verfügbar.', '', 503);
    }
    if (DIRECTORY_SEPARATOR === '/' && ((int) fileperms($parent) & 0077) !== 0) {
        answer(false, 'Der Schutz gegen Massensendungen ist nicht sicher eingerichtet.', '', 503);
    }
    return $path;
}

/** Liefert ein privates, automatisch erzeugtes Geheimnis für IP-Kennzeichen. */
function support_rate_secret(string $ratePath): string
{
    $path = $ratePath . '.key';
    if (is_link($path)) {
        answer(false, 'Der Schutz gegen Massensendungen ist nicht sicher eingerichtet.', '', 503);
    }
    if (!file_exists($path)) {
        $created = @fopen($path, 'x+b');
        if (is_resource($created)) {
            $secretText = bin2hex(random_bytes(32));
            $private = DIRECTORY_SEPARATOR !== '/' || @chmod($path, 0600);
            $written = $private ? fwrite($created, $secretText) : false;
            $flushed = $written === strlen($secretText) && fflush($created);
            fclose($created);
            if (!$flushed) {
                @unlink($path);
                answer(false, 'Der Schutz gegen Massensendungen ist gerade nicht verfügbar.', '', 503);
            }
        }
    }
    clearstatcache(true, $path);
    $metadata = @lstat($path);
    if (!is_array($metadata) || is_link($path) || !is_file($path) || !is_readable($path)
        || (int) ($metadata['nlink'] ?? 0) !== 1
        || (DIRECTORY_SEPARATOR === '/' && ((int) $metadata['mode'] & 0077) !== 0)) {
        answer(false, 'Der Schutz gegen Massensendungen ist nicht sicher eingerichtet.', '', 503);
    }
    $stream = @fopen($path, 'rb');
    $opened = is_resource($stream) ? fstat($stream) : false;
    if (!is_resource($stream) || !is_array($opened)
        || (int) ($opened['dev'] ?? -1) !== (int) ($metadata['dev'] ?? -2)
        || (int) ($opened['ino'] ?? -1) !== (int) ($metadata['ino'] ?? -2)
        || (int) ($opened['nlink'] ?? 0) !== 1) {
        if (is_resource($stream)) {
            fclose($stream);
        }
        answer(false, 'Der Schutz gegen Massensendungen ist nicht sicher eingerichtet.', '', 503);
    }
    $secretText = stream_get_contents($stream, 65);
    fclose($stream);
    if (!is_string($secretText) || preg_match('/^[0-9a-f]{64}$/D', $secretText) !== 1) {
        answer(false, 'Der Schutz gegen Massensendungen ist nicht sicher eingerichtet.', '', 503);
    }
    $secret = hex2bin($secretText);
    if ($secret === false) {
        answer(false, 'Der Schutz gegen Massensendungen ist nicht sicher eingerichtet.', '', 503);
    }
    return $secret;
}

/** Zwei ohne das private Geheimnis nicht verknüpfbare Stundenkennzeichen. */
function support_rate_client_keys(string $secret, int $now): array
{
    $root = hash_hmac('sha256', 'solidon|support-rate', $secret, true);
    $address = (string) ($_SERVER['REMOTE_ADDR'] ?? '-');
    $bucket = intdiv($now, SUPPORT_RATE_RETENTION_SECONDS);
    $keys = [];
    foreach ([$bucket, $bucket - 1] as $number) {
        $windowSecret = hash_hmac('sha256', (string) $number, $root, true);
        $keys[] = 'ip:' . hash_hmac('sha256', $address, $windowSecret);
    }
    return array_values(array_unique($keys));
}

/** Öffnet den Zähler ohne Linkverfolgung und sperrt genau diese Datei. */
function support_open_rate_state(string $path)
{
    if (is_link($path)) {
        answer(false, 'Der Schutz gegen Massensendungen ist nicht sicher eingerichtet.', '', 503);
    }
    $previousMask = umask(0077);
    try {
        $stream = @fopen($path, 'x+b');
    } finally {
        umask($previousMask);
    }
    $created = is_resource($stream);
    if (!$created) {
        if (is_link($path)) {
            answer(false, 'Der Schutz gegen Massensendungen ist nicht sicher eingerichtet.', '', 503);
        }
        $stream = @fopen($path, 'r+b');
    }
    if (!is_resource($stream) || !flock($stream, LOCK_EX)) {
        if (is_resource($stream)) {
            fclose($stream);
        }
        answer(false, 'Der Schutz gegen Massensendungen ist gerade nicht verfügbar.', '', 503);
    }
    if ($created && DIRECTORY_SEPARATOR === '/' && !@chmod($path, 0600)) {
        flock($stream, LOCK_UN);
        fclose($stream);
        answer(false, 'Der Schutz gegen Massensendungen ist nicht sicher eingerichtet.', '', 503);
    }
    clearstatcache(true, $path);
    $opened = fstat($stream);
    $named = @lstat($path);
    if (!is_array($opened) || !is_array($named) || is_link($path) || !is_file($path)
        || (int) ($opened['dev'] ?? -1) !== (int) ($named['dev'] ?? -2)
        || (int) ($opened['ino'] ?? -1) !== (int) ($named['ino'] ?? -2)
        || (int) ($opened['nlink'] ?? 0) !== 1 || (int) ($named['nlink'] ?? 0) !== 1
        || (DIRECTORY_SEPARATOR === '/' && ((int) $opened['mode'] & 0077) !== 0)) {
        flock($stream, LOCK_UN);
        fclose($stream);
        answer(false, 'Der Schutz gegen Massensendungen ist nicht sicher eingerichtet.', '', 503);
    }
    return $stream;
}

/** Schreibt jeden angeforderten Byte auf den bereits geöffneten Stream. */
function support_write_all($stream, string $data): bool
{
    $offset = 0;
    while ($offset < strlen($data)) {
        $written = fwrite($stream, substr($data, $offset));
        if ($written === false || $written === 0) {
            return false;
        }
        $offset += $written;
    }
    return true;
}

/** Erzwingt die Persistenz; Solidon verlangt dafür PHP 8.1 oder neuer. */
function support_flush_and_sync($stream): bool
{
    return fflush($stream) && fsync($stream);
}

/** Stellt nach einem fehlgeschlagenen Ersatz den zuvor gelesenen Inhalt wieder her. */
function support_restore_stream($stream, string $original): bool
{
    $positioned = fseek($stream, 0, SEEK_SET) === 0;
    $truncated = $positioned && ftruncate($stream, 0);
    $written = $truncated && support_write_all($stream, $original);
    $synced = support_flush_and_sync($stream);
    return $positioned && $truncated && $written && $synced;
}

/** Ersetzt einen Stream transaktional und gibt bei jedem Persistenzfehler false zurück. */
function support_replace_stream($stream, string $data): bool
{
    if (fseek($stream, 0, SEEK_SET) !== 0) {
        return false;
    }
    $original = stream_get_contents($stream);
    if (!is_string($original) || fseek($stream, 0, SEEK_SET) !== 0
        || !ftruncate($stream, 0)) {
        return false;
    }
    if (support_write_all($stream, $data) && support_flush_and_sync($stream)) {
        return true;
    }
    if (!support_restore_stream($stream, $original)) {
        error_log('Solidon: Wiederherstellung des Support-Zählers fehlgeschlagen.');
    }
    return false;
}

/** Schreibt den vollständigen Zustand auf denselben geprüften Handle. */
function support_write_rate_state(string $path, $stream, string $data): bool
{
    clearstatcache(true, $path);
    $opened = fstat($stream);
    $named = @lstat($path);
    if (!is_array($opened) || !is_array($named) || is_link($path)
        || (int) ($opened['dev'] ?? -1) !== (int) ($named['dev'] ?? -2)
        || (int) ($opened['ino'] ?? -1) !== (int) ($named['ino'] ?? -2)
        || (int) ($opened['nlink'] ?? 0) !== 1 || (int) ($named['nlink'] ?? 0) !== 1
        || !support_replace_stream($stream, $data)) {
        return false;
    }
    clearstatcache(true, $path);
    $named = @lstat($path);
    return is_array($named) && !is_link($path)
        && (int) ($opened['dev'] ?? -1) === (int) ($named['dev'] ?? -2)
        && (int) ($opened['ino'] ?? -1) === (int) ($named['ino'] ?? -2)
        && (int) ($named['nlink'] ?? 0) === 1;
}

/** Atomarer Stundenzähler; bei Speicherfehlern wird nicht ohne Grenze versendet. */
function support_consume_rate(): void
{
    $path = support_rate_path();
    $secret = support_rate_secret($path);
    $stream = support_open_rate_state($path);
    try {
        $raw = stream_get_contents($stream);
        $seen = $raw === '' ? [] : json_decode($raw === false ? '' : $raw, true);
        if ($raw === false || !is_array($seen)) {
            answer(false, 'Der Schutz gegen Massensendungen ist gerade nicht verfügbar.', '', 503);
        }
        $now = time();
        $clientKeys = support_rate_client_keys($secret, $now);
        $key = $clientKeys[0];
        foreach ($seen as $name => $stamps) {
            $kept = array_values(array_filter(
                (array) $stamps,
                static fn($stamp): bool => is_int($stamp)
                    && $stamp > $now - SUPPORT_RATE_RETENTION_SECONDS && $stamp <= $now
            ));
            if ($kept === [] || ($name !== 'global'
                && preg_match('/^ip:[0-9a-f]{64}$/D', (string) $name) !== 1)) {
                unset($seen[$name]);
            } else {
                $seen[$name] = $kept;
            }
        }
        $kept = [];
        foreach ($clientKeys as $clientKey) {
            $kept = array_merge($kept, (array) ($seen[$clientKey] ?? []));
            unset($seen[$clientKey]);
        }
        $globalKey = 'global';
        if (count($kept) >= MAX_PER_HOUR
            || count($seen[$globalKey] ?? []) >= MAX_GLOBAL_PER_HOUR) {
            answer(false, 'Zu viele Sendungen in kurzer Zeit. Bitte später noch einmal.', '', 429);
        }
        $kept[] = $now;
        $seen[$key] = $kept;
        $seen[$globalKey][] = $now;
        $encoded = json_encode($seen, JSON_UNESCAPED_SLASHES);
        if (!is_string($encoded) || !support_write_rate_state($path, $stream, $encoded)) {
            answer(false, 'Der Schutz gegen Massensendungen ist gerade nicht verfügbar.', '', 503);
        }
    } finally {
        flock($stream, LOCK_UN);
        fclose($stream);
    }
}

// --- Eingang prüfen --------------------------------------------------------

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    header('Allow: POST');
    answer(false, 'Nur POST.', '', 405);
}
support_require_origin();
$contentType = strtolower((string) ($_SERVER['CONTENT_TYPE'] ?? ''));
if (strpos($contentType, 'multipart/form-data;') !== 0) {
    answer(false, 'Die Sendung muss als multipart/form-data gesendet werden.', '', 415);
}
$length = support_request_bytes();

// Reißt eine Sendung `post_max_size`, kommt sie mit leerem $_POST an und ohne
// jeden Fehler — die Meldung „war leer" wäre dann die falsche Auskunft an den
// Einzigen, der nichts dafür kann.
if ($_POST === [] && $length > 0) {
    answer(false, 'Der Server hat die Sendung nicht angenommen — sie war ihm zu groß.', '', 413);
}

$message = support_post_text('message');
if (trim($message) === '') {
    answer(false, 'Die Rückmeldung war leer.', '', 400);
}
if (mb_strlen($message) > 60000) {
    answer(false, 'Die Rückmeldung ist zu lang.', '', 400);
}

$kindValue = support_post_text('kind');
$kind = preg_match('/^[a-z]{1,16}$/', $kindValue) === 1
    ? $kindValue
    : 'idea';
$subject = header_safe(support_post_text('subject')) ?: 'Solidon3D — Rückmeldung';
$contact = header_safe(support_post_text('contact'), 120);
$version = header_safe(support_post_text('app_version'), 32);

// Eine Rückadresse, die keine ist, wird verworfen statt abgelehnt: Sie ist
// freiwillig, und eine Sendung an ihr scheitern zu lassen wäre die härteste
// Antwort auf den kleinsten Fehler.
$reply_to = filter_var($contact, FILTER_VALIDATE_EMAIL) !== false ? $contact : '';

// --- Massensendungen bremsen -----------------------------------------------

support_consume_rate();

// --- Die Mail bauen --------------------------------------------------------

$reference = 'S-' . gmdate('Ymd') . '-' . bin2hex(random_bytes(3));

$body = "Vorgang: {$reference}\n"
    . 'Art: ' . $kind . "\n"
    . 'Version: ' . ($version !== '' ? $version : '-') . "\n"
    . 'Rückadresse: ' . ($reply_to !== '' ? $reply_to : 'keine') . "\n"
    . 'Eingang: ' . gmdate('c') . "\n"
    . str_repeat('-', 60) . "\n\n"
    . $message . "\n";

$boundary = 'solidon' . bin2hex(random_bytes(16));

$headers = [
    'From: Solidon3D <' . SENDER . '>',
    'MIME-Version: 1.0',
    'Content-Type: multipart/mixed; boundary="' . $boundary . '"',
    'X-Solidon-Reference: ' . $reference,
];
if ($reply_to !== '') {
    $headers[] = 'Reply-To: ' . $reply_to;
}

$parts = "--{$boundary}\r\n"
    . "Content-Type: text/plain; charset=UTF-8\r\n"
    . "Content-Transfer-Encoding: 8bit\r\n\r\n"
    . $body . "\r\n";

$files = 0;
$actualFileBytes = 0;
$actualFieldBytes = array_sum(array_map('strlen', $_POST));
if (count($_FILES) > MAX_FILES) {
    answer(false, 'Die Sendung enthält zu viele Anhänge.', '', 400);
}
foreach ($_FILES as $entry) {
    if (!is_array($entry) || ($entry['error'] ?? UPLOAD_ERR_NO_FILE) !== UPLOAD_ERR_OK) {
        continue;
    }
    $files++;
    // Erst fragen, ob die Datei wirklich aus diesem Upload stammt: `tmp_name`
    // ist ein Pfad, und ein Pfad, den man ungeprüft liest, ist die Stelle, an
    // der aus einem Formular ein Dateibetrachter wird. Über $_FILES kommt
    // nichts anderes herein — aber diese Prüfung kostet eine Zeile und die
    // Annahme, sie sei entbehrlich, hält nur so lange wie die Annahme.
    $temporary = (string) ($entry['tmp_name'] ?? '');
    if ($temporary === '' || !is_uploaded_file($temporary)) {
        continue;
    }
    $data = file_get_contents($temporary);
    if ($data === false) {
        continue;
    }
    $actualFileBytes += strlen($data);
    if ($actualFileBytes > MAX_BYTES || $actualFieldBytes + $actualFileBytes > MAX_BYTES) {
        answer(false, 'Die Sendung ist zu groß.', '', 413);
    }
    $name = file_safe((string) ($entry['name'] ?? 'anhang.bin'));
    $parts .= "--{$boundary}\r\n"
        . "Content-Type: application/octet-stream; name=\"{$name}\"\r\n"
        . "Content-Transfer-Encoding: base64\r\n"
        . "Content-Disposition: attachment; filename=\"{$name}\"\r\n\r\n"
        . chunk_split(base64_encode($data)) . "\r\n";
}
$parts .= "--{$boundary}--\r\n";

/**
 * Ein Betreff als MIME-Wörter nach RFC 2047.
 *
 * Umlaute sind in einer Kopfzeile nur kodiert zulässig — „Fehler beim Prufen"
 * wäre die Alternative. Ein einzelnes Wort darf dabei 75 Zeichen nicht
 * überschreiten; hier stand die ganze Zeile als eines, und bei 200 erlaubten
 * Zeichen wurden daraus über 270. Die meisten Zusteller nehmen das hin, manche
 * stutzen die Kopfzeile — und dann fehlt dem Posteingang der Betreff.
 *
 * Geschnitten wird an Zeichengrenzen, nicht an Bytegrenzen: ein halbes „ü"
 * wäre nach der Kodierung kein „ü" mehr.
 */
function encode_subject(string $value): string
{
    // 75 minus '=?UTF-8?B?' und '?=' lässt 63 Zeichen Base64, also 45 Bytes
    // Nutzlast — abgerundet auf ein Vielfaches von 3, damit keine Füllzeichen
    // mitten in der Folge stehen.
    $chunks = [];
    $current = '';
    $length = mb_strlen($value);
    for ($index = 0; $index < $length; $index++) {
        $character = mb_substr($value, $index, 1);
        if (strlen($current . $character) > 45) {
            $chunks[] = $current;
            $current = '';
        }
        $current .= $character;
    }
    if ($current !== '') {
        $chunks[] = $current;
    }
    if ($chunks === []) {
        return '';
    }

    // Getrennt durch Zeilenumbruch und Leerzeichen: So verlangt es die Norm für
    // mehrere Wörter in einer Kopfzeile, und so setzt der Leser sie wieder
    // zusammen, ohne ein Leerzeichen dazwischen zu sehen.
    // Als Fluchtfolge, nicht als echter Umbruch in der Quelle. Das ist kein
    // Schönheitsgrund: Dieses Repository normalisiert Zeilenenden beim
    // Einchecken auf LF, ein literales CRLF im String käme also als bloßes
    // LF auf dem Server an — und eine Kopfzeilenfaltung ohne CR ist keine.
    return implode("\r\n ", array_map(
        static fn(string $part): string => '=?UTF-8?B?' . base64_encode($part) . '?=',
        $chunks
    ));
}

$encoded_subject = encode_subject($subject);

$sent = @mail(RECIPIENT, $encoded_subject, $parts, implode("\r\n", $headers));
if (!$sent) {
    answer(false, 'Die Post ließ sich nicht zustellen.', '', 502);
}

answer(true, '', $reference);
