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
 * Braucht PHP 7.4 oder neuer und die Erweiterung mbstring; beides bringt
 * jedes Plesk mit. Und `post_max_size` muss über MAX_BYTES liegen, sonst
 * kommt eine große Sendung mit leeren $_POST an, nicht mit einem Fehler.
 */

declare(strict_types=1);

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

/** Wie viele Anhänge angenommen werden. Der Client schickt drei. */
const MAX_FILES = 6;

/** Wo die Sperrliste liegt. Im temporären Verzeichnis: sie darf jederzeit
 *  weg sein, sie ist keine Aufzeichnung, sondern ein Zähler. */
const RATE_FILE = 'solidon-support-rate.json';

// --- Antwort ---------------------------------------------------------------

header('Content-Type: application/json; charset=utf-8');
header('X-Content-Type-Options: nosniff');

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

// --- Eingang prüfen --------------------------------------------------------

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    answer(false, 'Nur POST.', '', 405);
}

$length = (int) ($_SERVER['CONTENT_LENGTH'] ?? 0);
if ($length > MAX_BYTES) {
    answer(false, 'Die Sendung ist zu groß.', '', 413);
}

// Reißt eine Sendung `post_max_size`, kommt sie mit leerem $_POST an und ohne
// jeden Fehler — die Meldung „war leer" wäre dann die falsche Auskunft an den
// Einzigen, der nichts dafür kann.
if ($_POST === [] && $length > 0) {
    answer(false, 'Der Server hat die Sendung nicht angenommen — sie war ihm zu groß.', '', 413);
}

$message = (string) ($_POST['message'] ?? '');
if (trim($message) === '') {
    answer(false, 'Die Rückmeldung war leer.', '', 400);
}
if (mb_strlen($message) > 60000) {
    answer(false, 'Die Rückmeldung ist zu lang.', '', 400);
}

$kind = preg_match('/^[a-z]{1,16}$/', (string) ($_POST['kind'] ?? '')) === 1
    ? (string) $_POST['kind']
    : 'idea';
$subject = header_safe((string) ($_POST['subject'] ?? '')) ?: 'Solidon3D — Rückmeldung';
$contact = header_safe((string) ($_POST['contact'] ?? ''), 120);
$version = header_safe((string) ($_POST['app_version'] ?? ''), 32);

// Eine Rückadresse, die keine ist, wird verworfen statt abgelehnt: Sie ist
// freiwillig, und eine Sendung an ihr scheitern zu lassen wäre die härteste
// Antwort auf den kleinsten Fehler.
$reply_to = filter_var($contact, FILTER_VALIDATE_EMAIL) !== false ? $contact : '';

// --- Massensendungen bremsen -----------------------------------------------

$who = hash('sha256', (string) ($_SERVER['REMOTE_ADDR'] ?? '-'));
$rate_path = sys_get_temp_dir() . DIRECTORY_SEPARATOR . RATE_FILE;
$now = time();
$seen = [];
if (is_readable($rate_path)) {
    $raw = file_get_contents($rate_path);
    $decoded = $raw === false ? null : json_decode($raw, true);
    if (is_array($decoded)) {
        $seen = $decoded;
    }
}
// Was älter als eine Stunde ist, fällt heraus — die Liste wächst damit nicht.
foreach ($seen as $key => $stamps) {
    $kept = array_values(array_filter((array) $stamps, static fn($t) => $now - (int) $t < 3600));
    if ($kept === []) {
        unset($seen[$key]);
    } else {
        $seen[$key] = $kept;
    }
}
if (count($seen[$who] ?? []) >= MAX_PER_HOUR) {
    answer(false, 'Zu viele Sendungen in kurzer Zeit. Bitte später noch einmal.', '', 429);
}
$seen[$who][] = $now;
@file_put_contents($rate_path, json_encode($seen), LOCK_EX);

// --- Die Mail bauen --------------------------------------------------------

$reference = 'S-' . gmdate('Ymd') . '-' . bin2hex(random_bytes(3));

$body = "Vorgang: {$reference}\n"
    . 'Art: ' . $kind . "\n"
    . 'Fassung: ' . ($version !== '' ? $version : '-') . "\n"
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
foreach ($_FILES as $entry) {
    if (!is_array($entry) || ($entry['error'] ?? UPLOAD_ERR_NO_FILE) !== UPLOAD_ERR_OK) {
        continue;
    }
    if (++$files > MAX_FILES) {
        break;
    }
    $data = file_get_contents((string) $entry['tmp_name']);
    if ($data === false) {
        continue;
    }
    $name = file_safe((string) ($entry['name'] ?? 'anhang.bin'));
    $parts .= "--{$boundary}\r\n"
        . "Content-Type: application/octet-stream; name=\"{$name}\"\r\n"
        . "Content-Transfer-Encoding: base64\r\n"
        . "Content-Disposition: attachment; filename=\"{$name}\"\r\n\r\n"
        . chunk_split(base64_encode($data)) . "\r\n";
}
$parts .= "--{$boundary}--\r\n";

// Der Betreff wird kodiert, nicht gestutzt: Umlaute sind in einer Kopfzeile
// nur als MIME-Wort zulässig, und „Fehler beim Prufen" wäre die Alternative.
$encoded_subject = '=?UTF-8?B?' . base64_encode($subject) . '?=';

$sent = @mail(RECIPIENT, $encoded_subject, $parts, implode("\r\n", $headers));
if (!$sent) {
    answer(false, 'Die Post ließ sich nicht zustellen.', '', 502);
}

answer(true, '', $reference);
