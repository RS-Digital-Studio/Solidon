<?php
/**
 * Gemeinsamer, nicht direkt aufgerufener Kern der Geräteaktivierung.
 *
 * Der Kaufcode wird gegen den langfristigen Lizenzschlüssel geprüft. Das
 * Geräte-Zertifikat unterschreibt ein bewusst getrenntes Serverpaar. Sein
 * privater Teil und die SQLite-Datei liegen außerhalb von httpdocs im
 * benachbarten Verzeichnis appdata. SOLIDON_ACTIVATION_SEED_FILE und
 * SOLIDON_ACTIVATION_DB können diese sicheren Standardpfade überschreiben.
 *
 * Braucht PHP 8.1+, sodium und PDO_SQLITE. Es gibt kein Composer-Paket und
 * keine weitere Abhängigkeit.
 */

declare(strict_types=1);

if (PHP_VERSION_ID < 80100) {
    http_response_code(503);
    exit;
}

const ACTIVATION_DOCUMENT_FORMAT = 1;
const ACTIVATION_REQUEST_KIND = 'activation-request';
const ACTIVATION_CERTIFICATE_KIND = 'activation-certificate';
const DEACTIVATION_REQUEST_KIND = 'deactivation-request';
const LICENCE_PUBLIC_KEY_HEX = 'c1a6c906ff05f935ae99e71ea3bea79919021077fbd763a9f31475b56e6d714d';
const ACTIVATION_PUBLIC_KEY_HEX = '52e0682ff6d864d4c07809c2ec48728f435fd4b2e1f18dbd5a60561f524887c6';
const ACTIVATION_MAX_BODY = 32768;
/** Im IP-Missbrauchszähler bleiben bei jedem Zugriff höchstens 15 Minuten. */
const ACTIVATION_RATE_RETENTION_SECONDS = 900;

final class ActivationFailure extends RuntimeException
{
    public string $reason;
    public int $status;
    public string $errorCode;

    public function __construct(
        string $reason,
        int $status = 400,
        string $errorCode = 'invalid_request'
    ) {
        $this->reason = $reason;
        $this->status = $status;
        $this->errorCode = $errorCode;
        parent::__construct($reason);
    }
}

/** Einheitliche Schutzköpfe für alle Antworten des Aktivierungsdienstes. */
function activation_security_headers(): void
{
    header('X-Content-Type-Options: nosniff');
    header('Referrer-Policy: no-referrer');
    header('X-Frame-Options: DENY');
    header('Permissions-Policy: camera=(), microphone=(), geolocation=()');
    header("Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; base-uri 'none'");
    header('Cache-Control: no-store');
}

/** Bindet einen Endpunkt an genau eine HTTP-Methode. */
function activation_require_method(string $method): void
{
    if (($_SERVER['REQUEST_METHOD'] ?? '') !== $method) {
        header('Allow: ' . $method);
        throw new ActivationFailure('Diese HTTP-Methode ist nicht erlaubt.', 405, 'method_not_allowed');
    }
}

/** Browser dürfen nur von der eigenen öffentlichen Herkunft schreiben. */
function activation_require_trusted_origin(): void
{
    $origin = trim((string) ($_SERVER['HTTP_ORIGIN'] ?? ''));
    if ($origin === '') {
        return;  // Native Anwendung und Offline-Dateiweg senden keinen Origin-Kopf.
    }
    if (!in_array(strtolower($origin), ['https://solidon3d.de', 'https://www.solidon3d.de'], true)) {
        throw new ActivationFailure('Die Herkunft der Anforderung wurde abgelehnt.', 403, 'origin_forbidden');
    }
}

/** Prüft Medientyp und deklarierte Größe, bevor teure Arbeit beginnt. */
function activation_require_json_headers(int $maximum = ACTIVATION_MAX_BODY): void
{
    $type = strtolower(trim(explode(';', (string) ($_SERVER['CONTENT_TYPE'] ?? ''), 2)[0]));
    if ($type !== 'application/json') {
        throw new ActivationFailure(
            'Die Anforderung muss als application/json gesendet werden.',
            415,
            'unsupported_media_type'
        );
    }
    $declared = (string) ($_SERVER['CONTENT_LENGTH'] ?? '');
    if ($declared !== '' && (!ctype_digit($declared) || (int) $declared > $maximum)) {
        throw new ActivationFailure('Die Anforderung ist zu groß.', 413, 'invalid_request');
    }
}

/** Liest einen JSON-Körper bytegenau und unabhängig vom Content-Length-Kopf. */
function activation_read_json_body(int $maximum = ACTIVATION_MAX_BODY): string
{
    activation_require_json_headers($maximum);
    $raw = file_get_contents('php://input', false, null, 0, $maximum + 1);
    if ($raw === false || $raw === '') {
        throw new ActivationFailure('Die Anforderung ist leer.', 400, 'invalid_request');
    }
    if (strlen($raw) > $maximum) {
        throw new ActivationFailure('Die Anforderung ist zu groß.', 413, 'invalid_request');
    }
    return $raw;
}

/** Verhindert die versehentliche Veröffentlichung privater Zustandsdateien. */
function activation_path_is_public(string $path): bool
{
    $root = realpath((string) ($_SERVER['DOCUMENT_ROOT'] ?? dirname(__DIR__)))
        ?: realpath(dirname(__DIR__));
    if ($root === false) {
        return false;
    }
    $root = rtrim(str_replace('\\', '/', strtolower($root)), '/');
    $candidate = rtrim(str_replace('\\', '/', strtolower($path)), '/');
    if (preg_match('#(^|/)\.\.(/|$)#', $candidate) === 1) {
        return true;
    }
    $probe = $path;
    while (true) {
        if (is_link($probe)) {
            return true;
        }
        if (file_exists($probe)) {
            break;
        }
        $parent = dirname($probe);
        if ($parent === $probe) {
            return true;
        }
        $probe = $parent;
    }
    $resolved = realpath($probe);
    if ($resolved === false) {
        return true;
    }
    $candidate = rtrim(str_replace('\\', '/', strtolower($resolved)), '/');
    return $candidate === $root || strpos($candidate, $root . '/') === 0;
}

/** Prüft Existenz, Lage und auf POSIX die Rechte einer Geheimnisdatei. */
function activation_require_private_file(string $path): void
{
    if (!is_file($path) || !is_readable($path) || activation_path_is_public($path)) {
        throw new ActivationFailure(
            'Der Aktivierungsdienst ist noch nicht vollständig eingerichtet.',
            503,
            'service_unavailable'
        );
    }
    if (DIRECTORY_SEPARATOR === '/' && ((int) fileperms($path) & 0077) !== 0) {
        throw new ActivationFailure(
            'Der Aktivierungsdienst ist noch nicht vollständig eingerichtet.',
            503,
            'service_unavailable'
        );
    }
}

/** Private Zustandsordner schützen auch SQLite-WAL- und Sperrdateien. */
function activation_require_private_directory(string $path): void
{
    if (!is_dir($path) && !@mkdir($path, 0700, true) && !is_dir($path)) {
        throw new ActivationFailure(
            'Der Aktivierungsdienst ist vorübergehend nicht verfügbar.',
            503,
            'service_unavailable'
        );
    }
    if (DIRECTORY_SEPARATOR === '/' && ((int) fileperms($path) & 0077) !== 0) {
        throw new ActivationFailure(
            'Der Aktivierungsdienst ist noch nicht vollständig eingerichtet.',
            503,
            'service_unavailable'
        );
    }
    if (activation_path_is_public($path)) {
        throw new ActivationFailure(
            'Der Aktivierungsdienst ist noch nicht vollständig eingerichtet.',
            503,
            'service_unavailable'
        );
    }
}

/** Zwei nicht verknüpfbare Kennzeichen für das laufende und vorige Zeitfenster. */
function activation_rate_client_keys(string $scope, int $window, int $now): array
{
    if ($window <= 0 || $window > ACTIVATION_RATE_RETENTION_SECONDS) {
        throw new ActivationFailure(
            'Der Aktivierungsdienst ist vorübergehend nicht verfügbar.',
            503,
            'service_unavailable'
        );
    }
    $root = hash_hmac('sha256', 'solidon|activation-rate', activation_seed(), true);
    $address = (string) ($_SERVER['REMOTE_ADDR'] ?? '-');
    $bucket = intdiv($now, $window);
    $keys = [];
    foreach ([$bucket, $bucket - 1] as $number) {
        $secret = hash_hmac('sha256', $scope . '|' . $number, $root, true);
        $keys[] = $scope . ':ip:' . hash_hmac('sha256', $address, $secret);
    }
    return array_values(array_unique($keys));
}

/** Öffnet den IP-Zähler ohne Linkverfolgung und sperrt genau diese Datei. */
function activation_open_rate_state(string $path)
{
    if (is_link($path)) {
        throw new ActivationFailure(
            'Der Aktivierungsdienst ist noch nicht vollständig eingerichtet.',
            503,
            'service_unavailable'
        );
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
            throw new ActivationFailure(
                'Der Aktivierungsdienst ist noch nicht vollständig eingerichtet.',
                503,
                'service_unavailable'
            );
        }
        $stream = @fopen($path, 'r+b');
    }
    if (!is_resource($stream) || !flock($stream, LOCK_EX)) {
        if (is_resource($stream)) {
            fclose($stream);
        }
        throw new ActivationFailure(
            'Der Aktivierungsdienst ist vorübergehend nicht verfügbar.',
            503,
            'service_unavailable'
        );
    }
    if ($created && DIRECTORY_SEPARATOR === '/' && !@chmod($path, 0600)) {
        flock($stream, LOCK_UN);
        fclose($stream);
        throw new ActivationFailure(
            'Der Aktivierungsdienst ist noch nicht vollständig eingerichtet.',
            503,
            'service_unavailable'
        );
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
        throw new ActivationFailure(
            'Der Aktivierungsdienst ist noch nicht vollständig eingerichtet.',
            503,
            'service_unavailable'
        );
    }
    return $stream;
}

/** Schreibt jeden angeforderten Byte auf den bereits geöffneten Stream. */
function activation_write_all($stream, string $data): bool
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
function activation_flush_and_sync($stream): bool
{
    return fflush($stream) && fsync($stream);
}

/** Stellt nach einem fehlgeschlagenen Ersatz den zuvor gelesenen Inhalt wieder her. */
function activation_restore_stream($stream, string $original): bool
{
    $positioned = fseek($stream, 0, SEEK_SET) === 0;
    $truncated = $positioned && ftruncate($stream, 0);
    $written = $truncated && activation_write_all($stream, $original);
    $synced = activation_flush_and_sync($stream);
    return $positioned && $truncated && $written && $synced;
}

/** Ersetzt einen Stream transaktional und gibt bei jedem Persistenzfehler false zurück. */
function activation_replace_stream($stream, string $data): bool
{
    if (fseek($stream, 0, SEEK_SET) !== 0) {
        return false;
    }
    $original = stream_get_contents($stream);
    if (!is_string($original) || fseek($stream, 0, SEEK_SET) !== 0
        || !ftruncate($stream, 0)) {
        return false;
    }
    if (activation_write_all($stream, $data) && activation_flush_and_sync($stream)) {
        return true;
    }
    if (!activation_restore_stream($stream, $original)) {
        error_log('Solidon: Wiederherstellung des Aktivierungszählers fehlgeschlagen.');
    }
    return false;
}

/** Schreibt den vollständigen Zähler auf denselben geprüften Handle. */
function activation_write_rate_state(string $path, $stream, string $data): bool
{
    clearstatcache(true, $path);
    $opened = fstat($stream);
    $named = @lstat($path);
    if (!is_array($opened) || !is_array($named) || is_link($path)
        || (int) ($opened['dev'] ?? -1) !== (int) ($named['dev'] ?? -2)
        || (int) ($opened['ino'] ?? -1) !== (int) ($named['ino'] ?? -2)
        || (int) ($opened['nlink'] ?? 0) !== 1 || (int) ($named['nlink'] ?? 0) !== 1
        || !activation_replace_stream($stream, $data)) {
        return false;
    }
    clearstatcache(true, $path);
    $named = @lstat($path);
    return is_array($named) && !is_link($path)
        && (int) ($opened['dev'] ?? -1) === (int) ($named['dev'] ?? -2)
        && (int) ($opened['ino'] ?? -1) === (int) ($named['ino'] ?? -2)
        && (int) ($named['nlink'] ?? 0) === 1;
}

/** Kurzes IP-Limit vor Signatur- und Datenbankarbeit; gespeichert wird nur ein HMAC. */
function activation_consume_client_rate(string $scope, int $limit, int $window): void
{
    $configured = getenv('SOLIDON_ACTIVATION_RATE_FILE');
    $path = $configured === false || $configured === ''
        ? dirname(activation_data_path('SOLIDON_ACTIVATION_DB', 'activation.sqlite'))
            . DIRECTORY_SEPARATOR . 'activation-rate.json'
        : activation_data_path('SOLIDON_ACTIVATION_RATE_FILE', 'activation-rate.json');
    $parent = dirname($path);
    activation_require_private_directory($parent);
    $stream = activation_open_rate_state($path);
    try {
        $raw = stream_get_contents($stream);
        $state = $raw === '' ? [] : json_decode($raw === false ? '' : $raw, true);
        if ($raw === false || !is_array($state)) {
            throw new ActivationFailure(
                'Der Aktivierungsdienst ist vorübergehend nicht verfügbar.',
                503,
                'service_unavailable'
            );
        }
        $now = time();
        $clientKeys = activation_rate_client_keys($scope, $window, $now);
        $key = $clientKeys[0];
        $globalKey = $scope . ':global';
        $kept = [];
        foreach ($clientKeys as $clientKey) {
            $kept = array_merge($kept, array_values(array_filter(
                (array) ($state[$clientKey] ?? []),
                static fn($stamp): bool => is_int($stamp)
                    && $stamp > $now - $window && $stamp <= $now
            )));
            unset($state[$clientKey]);
        }
        $global = array_values(array_filter(
            (array) ($state[$globalKey] ?? []),
            static fn($stamp): bool => is_int($stamp)
                && $stamp > $now - $window && $stamp <= $now
        ));
        if (count($kept) >= $limit || count($global) >= $limit * 100) {
            throw new ActivationFailure('Zu viele Anforderungen in kurzer Zeit.', 429, 'rate_limit');
        }
        $kept[] = $now;
        $global[] = $now;
        $state[$key] = $kept;
        $state[$globalKey] = $global;
        foreach ($state as $name => $stamps) {
            $recent = array_values(array_filter(
                (array) $stamps,
                static fn($stamp): bool => is_int($stamp)
                    && $stamp > $now - ACTIVATION_RATE_RETENTION_SECONDS && $stamp <= $now
            ));
            if ($recent === []
                || preg_match('/^[a-z]{1,16}:(?:global|ip:[0-9a-f]{64})$/D', (string) $name) !== 1) {
                unset($state[$name]);
            } else {
                $state[$name] = $recent;
            }
        }
        $encoded = json_encode($state, JSON_UNESCAPED_SLASHES);
        if (!is_string($encoded) || !activation_write_rate_state($path, $stream, $encoded)) {
            throw new ActivationFailure(
                'Der Aktivierungsdienst ist vorübergehend nicht verfügbar.',
                503,
                'service_unavailable'
            );
        }
    } finally {
        flock($stream, LOCK_UN);
        fclose($stream);
    }
}

// Eine Hilfsdatei ist kein öffentlicher Endpunkt.
if (realpath((string) ($_SERVER['SCRIPT_FILENAME'] ?? '')) === realpath(__FILE__)) {
    activation_security_headers();
    http_response_code(404);
    exit;
}

/** Eine JSON-Fehlermeldung mit stabiler Kennung für die Anwendung. */
function activation_answer_error(ActivationFailure $problem): void
{
    http_response_code($problem->status);
    echo json_encode(
        ['ok' => false, 'code' => $problem->errorCode, 'error' => $problem->reason],
        JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES
    );
    exit;
}

/** URL-sicheres Base64 ohne Füllzeichen. */
function activation_encode(string $data): string
{
    return rtrim(strtr(base64_encode($data), '+/', '-_'), '=');
}

/** Liest das Transportformat streng; fremde Zeichen werden nicht verschluckt. */
function activation_decode($text): string
{
    if (!is_string($text) || preg_match('/^[A-Za-z0-9_-]*$/D', $text) !== 1) {
        throw new ActivationFailure('Ein Datenfeld der Aktivierungsanforderung ist ungültig.');
    }
    $padding = (4 - strlen($text) % 4) % 4;
    $decoded = base64_decode(strtr($text, '-_', '+/') . str_repeat('=', $padding), true);
    if ($decoded === false) {
        throw new ActivationFailure('Ein Datenfeld der Aktivierungsanforderung ist unvollständig.');
    }
    return $decoded;
}

/** Base32 nach RFC 4648, passend zum Kaufcode der Anwendung. */
function activation_base32_decode(string $text): string
{
    $alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
    $buffer = 0;
    $bits = 0;
    $result = '';
    foreach (str_split($text) as $character) {
        $value = strpos($alphabet, $character);
        if ($value === false) {
            throw new ActivationFailure('Der Lizenzschlüssel enthält ein fremdes Zeichen.');
        }
        $buffer = ($buffer << 5) | $value;
        $bits += 5;
        while ($bits >= 8) {
            $bits -= 8;
            $result .= chr(($buffer >> $bits) & 0xff);
            $buffer &= $bits === 0 ? 0 : (1 << $bits) - 1;
        }
    }
    if ($bits > 0 && $buffer !== 0) {
        throw new ActivationFailure('Der Lizenzschlüssel ist unvollständig.');
    }
    return $result;
}

/** Prüft den Kaufcode und liefert dessen signierte Nutzlast + Kennung. */
function activation_licence(string $text): array
{
    $upper = strtoupper(trim($text));
    $prefix = 'SOLIDON3D-1-';
    if (substr($upper, 0, strlen($prefix)) !== $prefix) {
        throw new ActivationFailure('Der Lizenzschlüssel beginnt nicht mit SOLIDON3D-1-.');
    }
    $body = '';
    foreach (str_split(substr($upper, strlen($prefix))) as $character) {
        if ($character === '-' || ctype_space($character)) {
            continue;
        }
        $body .= ['0' => 'O', '1' => 'I', '8' => 'B'][$character] ?? $character;
    }
    $raw = activation_base32_decode($body);
    if (strlen($raw) <= SODIUM_CRYPTO_SIGN_BYTES) {
        throw new ActivationFailure('Der Lizenzschlüssel ist zu kurz.');
    }
    $payload = substr($raw, 0, -SODIUM_CRYPTO_SIGN_BYTES);
    $signature = substr($raw, -SODIUM_CRYPTO_SIGN_BYTES);
    // Der Prüfschlüssel aus der Umgebung gilt nur im eingebauten Testserver
    // (`php -S`); im Hosting ersetzt keine liegengebliebene Variable den
    // festen Schlüssel — sonst nähme der Dienst fremd signierte Lizenzen an.
    $publicHex = (PHP_SAPI === 'cli-server' ? getenv('SOLIDON_ACTIVATION_TEST_LICENCE_PUBLIC_KEY') : false)
        ?: LICENCE_PUBLIC_KEY_HEX;
    $public = hex2bin($publicHex);
    if ($public === false || strlen($public) !== SODIUM_CRYPTO_SIGN_PUBLICKEYBYTES
        || !sodium_crypto_sign_verify_detached($signature, $payload, $public)) {
        throw new ActivationFailure('Die Signatur des Lizenzschlüssels passt nicht.');
    }
    if (strlen($payload) < 6 || ord($payload[0]) !== 1) {
        throw new ActivationFailure('Der Lizenzschlüssel hat das falsche Format.');
    }
    $orderEnd = 5 + ord($payload[4]);
    if (strlen($payload) < $orderEnd + 1) {
        throw new ActivationFailure('Der Lizenzschlüssel ist unvollständig.');
    }
    $holderEnd = $orderEnd + 1 + ord($payload[$orderEnd]);
    if (strlen($payload) !== $holderEnd) {
        throw new ActivationFailure('Der Lizenzschlüssel ist unvollständig.');
    }
    $majorSetting = getenv('SOLIDON_ACTIVATION_MAJOR');
    $expectedMajor = (int) ($majorSetting === false || $majorSetting === '' ? '1' : $majorSetting);
    if (ord($payload[1]) !== $expectedMajor) {
        throw new ActivationFailure(
            'Der Lizenzschlüssel gilt für eine andere Hauptversion.',
            409,
            'wrong_major'
        );
    }
    return ['payload' => $payload, 'digest' => hash('sha256', $payload)];
}

/** Liest und prüft das äußere Dokument. */
function activation_document(string $raw, string $kind): array
{
    try {
        $document = json_decode($raw, true, 16, JSON_THROW_ON_ERROR);
    } catch (JsonException $problem) {
        throw new ActivationFailure('Die Aktivierungsanforderung ist kein vollständiges JSON.') ;
    }
    if (!is_array($document)
        || !activation_has_exact_keys(
            $document,
            ['format', 'kind', 'licence', 'payload', 'signature']
        )
        || ($document['format'] ?? null) !== ACTIVATION_DOCUMENT_FORMAT
        || ($document['kind'] ?? null) !== $kind) {
        throw new ActivationFailure('Die Aktivierungsanforderung hat das falsche Format.');
    }
    return [
        'document' => $document,
        'payload' => activation_decode($document['payload'] ?? null),
        'signature' => activation_decode($document['signature'] ?? null),
    ];
}

/** Verhindert unbemerkte Zusatzfelder und PHP-Arrayformen in signierten Verträgen. */
function activation_has_exact_keys(array $value, array $expected): bool
{
    $actual = array_keys($value);
    sort($actual);
    sort($expected);
    return $actual === $expected;
}

/** Prüft Kaufcode, Gerätenachweis und alle Bindungen dazwischen. */
function activation_request(string $raw): array
{
    $parts = activation_document($raw, ACTIVATION_REQUEST_KIND);
    $document = $parts['document'];
    if (!is_string($document['licence'] ?? null)) {
        throw new ActivationFailure('Der Lizenzschlüssel fehlt in der Anforderung.');
    }
    $licence = activation_licence($document['licence']);
    try {
        $values = json_decode($parts['payload'], true, 16, JSON_THROW_ON_ERROR);
    } catch (JsonException $problem) {
        throw new ActivationFailure('Die signierten Gerätedaten sind unvollständig.');
    }
    if (!is_array($values)
        || !activation_has_exact_keys(
            $values,
            ['device_name', 'device_public', 'format', 'kind', 'licence_digest', 'request_id']
        )
        || ($values['format'] ?? null) !== ACTIVATION_DOCUMENT_FORMAT
        || ($values['kind'] ?? null) !== ACTIVATION_REQUEST_KIND) {
        throw new ActivationFailure('Die signierten Gerätedaten haben das falsche Format.');
    }
    $public = activation_decode($values['device_public'] ?? null);
    $digest = (string) ($values['licence_digest'] ?? '');
    $name = trim((string) ($values['device_name'] ?? ''));
    $requestId = (string) ($values['request_id'] ?? '');
    if (strlen($public) !== SODIUM_CRYPTO_SIGN_PUBLICKEYBYTES
        || strlen($parts['signature']) !== SODIUM_CRYPTO_SIGN_BYTES
        || !sodium_crypto_sign_verify_detached($parts['signature'], $parts['payload'], $public)) {
        throw new ActivationFailure('Die Geräte-Signatur passt nicht.');
    }
    if (!hash_equals($licence['digest'], $digest)) {
        throw new ActivationFailure('Lizenzschlüssel und Gerätedaten gehören nicht zusammen.');
    }
    $expectedId = substr(hash('sha256', $public . $digest), 0, 32);
    if (!hash_equals($expectedId, $requestId)) {
        throw new ActivationFailure('Die Aktivierungsanforderung trägt die falsche Kennung.');
    }
    $nameLength = activation_text_length($name);
    if ($name === '' || $nameLength > 80) {
        throw new ActivationFailure('Der Gerätename muss zwischen 1 und 80 Zeichen lang sein.');
    }
    return [
        'digest' => $digest,
        'device_public' => $public,
        'device_name' => $name,
        'request_id' => $requestId,
    ];
}

/** Zählt sichtbare UTF-8-Zeichen auch auf Hostings ohne mbstring. */
function activation_text_length(string $text): int
{
    if (function_exists('mb_strlen')) {
        return mb_strlen($text, 'UTF-8');
    }
    if (preg_match('//u', $text) !== 1) {
        throw new ActivationFailure('Der Gerätename ist kein gültiger Text.');
    }
    $count = preg_match_all('/./us', $text, $matches);
    if ($count === false) {
        throw new ActivationFailure('Der Gerätename ließ sich nicht lesen.');
    }
    return $count;
}

/** Prüft die vom aktuell aktivierten Gerät signierte Abmeldung. */
function activation_deactivation_request(string $raw): array
{
    $parts = activation_document($raw, DEACTIVATION_REQUEST_KIND);
    $document = $parts['document'];
    if (!is_string($document['licence'] ?? null)) {
        throw new ActivationFailure('Der Lizenzschlüssel fehlt in der Abmeldung.');
    }
    $licence = activation_licence($document['licence']);
    try {
        $values = json_decode($parts['payload'], true, 16, JSON_THROW_ON_ERROR);
    } catch (JsonException $problem) {
        throw new ActivationFailure('Die signierten Abmeldedaten sind unvollständig.');
    }
    if (!is_array($values)
        || !activation_has_exact_keys(
            $values,
            ['activation_id', 'device_public', 'format', 'kind', 'licence_digest']
        )
        || ($values['format'] ?? null) !== ACTIVATION_DOCUMENT_FORMAT
        || ($values['kind'] ?? null) !== DEACTIVATION_REQUEST_KIND) {
        throw new ActivationFailure('Die signierten Abmeldedaten haben das falsche Format.');
    }
    $public = activation_decode($values['device_public'] ?? null);
    $digest = (string) ($values['licence_digest'] ?? '');
    $activationId = (string) ($values['activation_id'] ?? '');
    if (strlen($public) !== SODIUM_CRYPTO_SIGN_PUBLICKEYBYTES
        || strlen($parts['signature']) !== SODIUM_CRYPTO_SIGN_BYTES
        || !sodium_crypto_sign_verify_detached($parts['signature'], $parts['payload'], $public)
        || !hash_equals($licence['digest'], $digest)
        || preg_match('/^[0-9a-f]{32}$/D', $activationId) !== 1) {
        throw new ActivationFailure('Die Geräteabmeldung ist nicht gültig.');
    }
    return [
        'digest' => $digest,
        'device_public' => $public,
        'activation_id' => $activationId,
    ];
}

/** Sicherer Standardpfad neben, niemals unter dem öffentlichen httpdocs. */
function activation_data_path(string $setting, string $filename): string
{
    $configured = getenv($setting);
    $path = $configured === false || $configured === ''
        ? dirname(__DIR__, 2) . DIRECTORY_SEPARATOR . 'appdata' . DIRECTORY_SEPARATOR . $filename
        : $configured;
    if (substr($path, 0, 1) !== DIRECTORY_SEPARATOR
        && preg_match('#^[A-Za-z]:[\\\\/]#', $path) !== 1) {
        throw new ActivationFailure(
            'Der Aktivierungsdienst ist noch nicht vollständig eingerichtet.',
            503,
            'service_unavailable'
        );
    }
    if (activation_path_is_public($path)) {
        throw new ActivationFailure(
            'Der Aktivierungsdienst ist noch nicht vollständig eingerichtet.',
            503,
            'service_unavailable'
        );
    }
    return $path;
}

/** Legt die feste Datenbankstruktur idempotent an. */
function activation_create_schema(PDO $database): void
{
    $database->exec(
        'CREATE TABLE IF NOT EXISTS licences ('
        . 'digest TEXT PRIMARY KEY, status TEXT NOT NULL DEFAULT \'active\', created_at TEXT NOT NULL)'
    );
    $database->exec(
        'CREATE TABLE IF NOT EXISTS activations ('
        . 'id TEXT PRIMARY KEY, licence_digest TEXT NOT NULL, device_public TEXT NOT NULL, '
        . 'device_name TEXT NOT NULL, activated_on TEXT NOT NULL, deactivated_at TEXT NULL, '
        . 'FOREIGN KEY(licence_digest) REFERENCES licences(digest))'
    );
    $database->exec(
        'CREATE UNIQUE INDEX IF NOT EXISTS one_active_device '
        . 'ON activations(licence_digest) WHERE deactivated_at IS NULL'
    );
    $database->exec(
        'CREATE TABLE IF NOT EXISTS activation_attempts ('
        . 'licence_digest TEXT NOT NULL, day TEXT NOT NULL, attempts INTEGER NOT NULL, '
        . 'PRIMARY KEY(licence_digest, day))'
    );
    $database->exec(
        'CREATE TABLE IF NOT EXISTS operator_events ('
        . 'id INTEGER PRIMARY KEY AUTOINCREMENT, occurred_at TEXT NOT NULL, '
        . 'licence_digest TEXT NOT NULL, action TEXT NOT NULL, reason TEXT NOT NULL, '
        . 'changed INTEGER NOT NULL)'
    );
}

/** Öffnet die Datenbank; die Bereitschaftsprobe schreibt dabei garantiert nichts. */
function activation_database(bool $initialise = true): PDO
{
    $path = activation_data_path('SOLIDON_ACTIVATION_DB', 'activation.sqlite');
    if (!$initialise && !is_file($path)) {
        throw new ActivationFailure(
            'Der Aktivierungsdienst ist noch nicht vollständig eingerichtet.',
            503,
            'service_unavailable'
        );
    }
    $parent = dirname($path);
    activation_require_private_directory($parent);
    if (!$initialise) {
        activation_require_private_file($path);
    }
    try {
        $database = new PDO('sqlite:' . $path, null, null, [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        ]);
        $database->exec('PRAGMA busy_timeout = 5000');
        if ($initialise) {
            if (DIRECTORY_SEPARATOR === '/') {
                @chmod($path, 0600);
            }
            $database->exec('PRAGMA journal_mode = WAL');
            activation_create_schema($database);
        } else {
            $database->exec('PRAGMA query_only = ON');
        }
    } catch (PDOException $problem) {
        throw new ActivationFailure(
            'Der Aktivierungsdienst kann seinen sicheren Speicher gerade nicht öffnen.',
            503,
            'service_unavailable'
        );
    }
    return $database;
}

/** Beendet eine mit SQL begonnene SQLite-Transaktion auch über SQL. */
function activation_commit(PDO $database): void
{
    $database->exec('COMMIT');
}

/** Räumt eine begonnene SQLite-Transaktion auf und bewahrt den ersten Fehler. */
function activation_rollback(PDO $database): void
{
    try {
        $database->exec('ROLLBACK');
    } catch (Throwable $problem) {
        // Der ursprüngliche Fehler erklärt die Handlung; ein fehlender
        // Transaktionszustand beim Aufräumen darf ihn nicht verdecken.
    }
}

/** Liest den privaten Serverteil und stellt sicher, dass er zum Produkt passt. */
function activation_seed(): string
{
    $path = activation_data_path('SOLIDON_ACTIVATION_SEED_FILE', 'activation.seed');
    activation_require_private_file($path);
    $text = file_get_contents($path);
    if ($text === false) {
        throw new ActivationFailure(
            'Der Aktivierungsdienst ist noch nicht vollständig eingerichtet.',
            503,
            'service_unavailable'
        );
    }
    $seed = hex2bin(trim($text));
    if ($seed === false || strlen($seed) !== SODIUM_CRYPTO_SIGN_SEEDBYTES) {
        throw new ActivationFailure(
            'Der Aktivierungsdienst hat keinen gültigen Signaturschlüssel.',
            503,
            'service_unavailable'
        );
    }
    $pair = sodium_crypto_sign_seed_keypair($seed);
    $public = sodium_crypto_sign_publickey($pair);
    $expectedPublic = (PHP_SAPI === 'cli-server' ? getenv('SOLIDON_ACTIVATION_TEST_PUBLIC_KEY') : false)
        ?: ACTIVATION_PUBLIC_KEY_HEX;
    if (!hash_equals($expectedPublic, bin2hex($public))) {
        throw new ActivationFailure(
            'Der Signaturschlüssel des Aktivierungsdienstes passt nicht zur Anwendung.',
            503,
            'service_unavailable'
        );
    }
    return $seed;
}

/** Begrenzt gültig signierte Aktivierungsversuche auf fünf je UTC-Tag. */
function activation_consume_rate(PDO $database, string $digest): void
{
    $day = gmdate('Y-m-d');
    try {
        $database->exec('BEGIN IMMEDIATE');
        // Der Zähler schützt nur den laufenden UTC-Tag. Ältere Zeilen würden
        // weder die Entscheidung verändern noch dem Kunden helfen; der
        // nächste gültige Aktivierungsversuch räumt sie deshalb gemeinsam ab.
        $purge = $database->prepare('DELETE FROM activation_attempts WHERE day < ?');
        $purge->execute([$day]);
        $insert = $database->prepare(
            'INSERT OR IGNORE INTO activation_attempts(licence_digest, day, attempts) VALUES(?, ?, 0)'
        );
        $insert->execute([$digest, $day]);
        $select = $database->prepare(
            'SELECT attempts FROM activation_attempts WHERE licence_digest = ? AND day = ?'
        );
        $select->execute([$digest, $day]);
        if ((int) $select->fetchColumn() >= 5) {
            throw new ActivationFailure(
                'Für diesen Lizenzschlüssel gab es heute zu viele Aktivierungsversuche.',
                429,
                'rate_limit'
            );
        }
        $update = $database->prepare(
            'UPDATE activation_attempts SET attempts = attempts + 1 '
            . 'WHERE licence_digest = ? AND day = ?'
        );
        $update->execute([$digest, $day]);
        activation_commit($database);
    } catch (ActivationFailure $problem) {
        activation_rollback($database);
        throw $problem;
    } catch (Throwable $problem) {
        activation_rollback($database);
        throw new ActivationFailure(
            'Die Aktivierung konnte gerade nicht geprüft werden. Versuchen Sie es später erneut.',
            503,
            'service_unavailable'
        );
    }
}

/** Vergibt idempotent den einzigen aktiven Geräteplatz und signiert ihn. */
function activation_issue(array $request): string
{
    $database = activation_database();
    activation_consume_rate($database, $request['digest']);
    $deviceHex = bin2hex($request['device_public']);
    $today = gmdate('Y-m-d');
    try {
        $database->exec('BEGIN IMMEDIATE');
        $insertLicence = $database->prepare(
            'INSERT OR IGNORE INTO licences(digest, status, created_at) VALUES(?, \'active\', ?)'
        );
        $insertLicence->execute([$request['digest'], gmdate('c')]);
        $licence = $database->prepare('SELECT status FROM licences WHERE digest = ?');
        $licence->execute([$request['digest']]);
        if (($licence->fetch()['status'] ?? '') !== 'active') {
            throw new ActivationFailure('Dieser Lizenzschlüssel ist gesperrt.', 403, 'licence_blocked');
        }
        $current = $database->prepare(
            'SELECT id, device_public, device_name, activated_on FROM activations '
            . 'WHERE licence_digest = ? AND deactivated_at IS NULL'
        );
        $current->execute([$request['digest']]);
        $active = $current->fetch();
        if ($active !== false && !hash_equals((string) $active['device_public'], $deviceHex)) {
            throw new ActivationFailure(
                'Der Lizenzschlüssel ist bereits auf einem anderen Rechner aktiviert. '
                . 'Deaktivieren Sie ihn dort oder wenden Sie sich bei einem Geräteverlust an den Support.',
                409,
                'device_limit'
            );
        }
        if ($active === false) {
            $active = [
                'id' => bin2hex(random_bytes(16)),
                'device_public' => $deviceHex,
                'device_name' => $request['device_name'],
                'activated_on' => $today,
            ];
            $insert = $database->prepare(
                'INSERT INTO activations(id, licence_digest, device_public, device_name, activated_on) '
                . 'VALUES(?, ?, ?, ?, ?)'
            );
            $insert->execute([
                $active['id'],
                $request['digest'],
                $deviceHex,
                $request['device_name'],
                $today,
            ]);
        }
        activation_commit($database);
    } catch (ActivationFailure $problem) {
        activation_rollback($database);
        throw $problem;
    } catch (Throwable $problem) {
        activation_rollback($database);
        throw new ActivationFailure(
            'Die Aktivierung konnte gerade nicht gespeichert werden. Versuchen Sie es erneut.',
            503,
            'service_unavailable'
        );
    }

    // Alphabetische Reihenfolge wie json.dumps(sort_keys=True) in Python.
    $payload = json_encode([
        'activation_id' => $active['id'],
        'device_name' => $active['device_name'],
        'device_public' => activation_encode($request['device_public']),
        'format' => ACTIVATION_DOCUMENT_FORMAT,
        'issued_on' => $active['activated_on'],
        'kind' => ACTIVATION_CERTIFICATE_KIND,
        'licence_digest' => $request['digest'],
    ], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    if ($payload === false) {
        throw new ActivationFailure('Das Geräte-Zertifikat ließ sich nicht erstellen.', 500, 'server_error');
    }
    $seed = activation_seed();
    $pair = sodium_crypto_sign_seed_keypair($seed);
    $secret = sodium_crypto_sign_secretkey($pair);
    $signature = sodium_crypto_sign_detached($payload, $secret);
    return json_encode([
        'format' => ACTIVATION_DOCUMENT_FORMAT,
        'kind' => ACTIVATION_CERTIFICATE_KIND,
        'payload' => activation_encode($payload),
        'signature' => activation_encode($signature),
    ], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) ?: '';
}

/** Gibt genau den vom Gerät selbst genannten Platz frei; Wiederholen ist harmlos. */
function activation_deactivate(array $request): void
{
    $database = activation_database();
    try {
        $database->exec('BEGIN IMMEDIATE');
        $entry = $database->prepare(
            'SELECT deactivated_at FROM activations '
            . 'WHERE id = ? AND licence_digest = ? AND device_public = ?'
        );
        $entry->execute([
            $request['activation_id'],
            $request['digest'],
            bin2hex($request['device_public']),
        ]);
        $found = $entry->fetch();
        if ($found === false) {
            throw new ActivationFailure(
                'Dieser Geräteplatz gehört nicht zu dieser Lizenz.',
                404,
                'activation_not_found'
            );
        }
        if ($found['deactivated_at'] === null) {
            $update = $database->prepare('UPDATE activations SET deactivated_at = ? WHERE id = ?');
            $update->execute([gmdate('c'), $request['activation_id']]);
        }
        activation_commit($database);
    } catch (ActivationFailure $problem) {
        activation_rollback($database);
        throw $problem;
    } catch (Throwable $problem) {
        activation_rollback($database);
        throw new ActivationFailure(
            'Der Geräteplatz konnte gerade nicht freigegeben werden. Versuchen Sie es erneut.',
            503,
            'service_unavailable'
        );
    }
}
