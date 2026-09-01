<?php
/**
 * Zählt, was auf solidon3d.de abgerufen wird — Seiten und Downloads.
 *
 * Warum es diese Datei gibt: Ohne eine Zahl weiß niemand, ob eine
 * Pressemitteilung etwas gebracht hat oder ob die Demo überhaupt geladen
 * wird. Die üblichen Antworten darauf heißen Google Analytics oder Matomo;
 * beide setzen Cookies, beide erkennen denselben Besucher über Wochen
 * wieder, und die Website verspricht ausdrücklich das Gegenteil. Hier steht
 * die kleinste Sache, die die Frage beantwortet: ein Zähler ohne Cookie,
 * ohne fremden Server und ohne gespeicherte IP-Adresse.
 *
 * Zwei Eingänge, ein Zweck:
 *
 *   POST /api/count.php   mit Feld `p` (Pfad)   → Seitenaufruf, Antwort 204
 *   GET  /api/count.php?f=<Datei>               → Download, Antwort 302 auf /dl/
 *
 * Der Download läuft deshalb über eine Weiterleitung und nicht über
 * ``readfile``: Die Setup-Datei wiegt 170 MB, und wer sie durch PHP schiebt,
 * verliert die Wiederaufnahme abgebrochener Downloads und handelt sich ein
 * Zeitlimit ein. Nach der Weiterleitung liefert der Webserver die Datei
 * selbst aus, wie vorher auch.
 *
 * **Was gespeichert wird und was nicht.** Gespeichert werden Zeitpunkt, der
 * abgerufene Pfad, der Host der verweisenden Seite und ein Tageskennzeichen.
 * Nicht gespeichert werden IP-Adresse und User-Agent. Das Tageskennzeichen
 * ist ein gekürzter HMAC aus IP und User-Agent unter einem privaten
 * Zufallswert, der am ersten Aufruf jedes UTC-Tags neu entsteht — damit lassen sich
 * Aufrufe innerhalb eines Tages zu Besuchen zusammenfassen, und am nächsten
 * Tag ist die Verbindung zur Person ohne den ersetzten Tageswert nicht
 * wiederherstellbar. Dieselbe Bauart benutzt Plausible; sie gilt als einwilligungsfrei
 * nach § 25 Abs. 2 TDDDG, weil auf dem Gerät des Besuchers nichts abgelegt
 * und nichts ausgelesen wird.
 *
 * Gegenstück: website/api/stats.php zeigt, was hier zusammenkommt.
 *
 * Einrichtung: Datei nach httpdocs/api/count.php legen. Sonst nichts — kein
 * Composer, keine Datenbank. Der Ablageordner legt sich selbst an.
 *
 * Braucht PHP 8.1 oder neuer.
 */

declare(strict_types=1);

if (PHP_VERSION_ID < 80100) {
    http_response_code(503);
    exit;
}

// --- Einstellungen ---------------------------------------------------------

/** Wo die Downloads liegen, vom Dokumentenstamm aus gesehen. */
const DOWNLOAD_URL = '/dl/';

/** Und wo im Dateisystem — zum Nachsehen, ob es die Datei überhaupt gibt.
 *  Ohne diese Prüfung wäre die Weiterleitung ein offenes Tor: Wer `f`
 *  frei wählen darf, schickt Besucher über unsere Domain irgendwohin. */
const DOWNLOAD_DIR = __DIR__ . '/../dl';

/** Wie lang das Tageskennzeichen ist. Acht Hex-Zeichen reichen, um
 *  Aufrufe eines Tages zu gruppieren, und sind kurz genug, dass die Datei
 *  lesbar bleibt. */
const MARK_LENGTH = 8;

/** Wie viele Zeichen eines Pfads aufgezeichnet werden. Alles darüber ist
 *  entweder ein Angriffsversuch oder ein Kennzeichen, das jemand angehängt
 *  hat — beides gehört nicht in die Auswertung. */
const MAX_PATH = 120;
const COUNT_MAX_BODY = 2048;
const COUNT_MAX_PER_MINUTE = 60;
const COUNT_MAX_GLOBAL_PER_MINUTE = 1000;
/** Im Zustand bleiben bei jedem Zugriff höchstens die letzten 60 Sekunden. */
const COUNT_RATE_RETENTION_SECONDS = 60;
const COUNT_MAX_MONTH_BYTES = 16 * 1024 * 1024;
const COUNT_MAX_TOTAL_BYTES = 64 * 1024 * 1024;

// --- Ablage ----------------------------------------------------------------

/**
 * Der Ordner, in dem die Zähldaten liegen.
 *
 * Erste Wahl ist ein Ordner **neben** dem Dokumentenstamm: Was dort liegt,
 * ist über keine Adresse abrufbar, egal wie der Webserver eingestellt ist.
 * Verbietet ``open_basedir`` den Weg dorthin, wird nicht gezählt. Ein
 * öffentlicher Rückfallordner wäre für pseudonyme Nutzungsdaten nicht sicher.
 */
function store_dir(): string
{
    $configured = getenv('SOLIDON_STATS_DIR');
    $outside = $configured === false || $configured === ''
        ? dirname(__DIR__, 2) . '/solidon-stats'
        : $configured;
    if (substr($outside, 0, 1) !== DIRECTORY_SEPARATOR
        && preg_match('#^[A-Za-z]:[\\\\/]#', $outside) !== 1) {
        return '';
    }
    $root = realpath((string) ($_SERVER['DOCUMENT_ROOT'] ?? dirname(__DIR__)))
        ?: realpath(dirname(__DIR__));
    $candidate = rtrim(str_replace('\\', '/', strtolower($outside)), '/');
    if (preg_match('#(^|/)\.\.(/|$)#', $candidate) === 1) {
        return '';
    }
    $probe = $outside;
    while (true) {
        if (is_link($probe)) {
            return '';
        }
        if (file_exists($probe)) {
            break;
        }
        $parent = dirname($probe);
        if ($parent === $probe) {
            return '';
        }
        $probe = $parent;
    }
    $resolved = realpath($probe);
    if ($resolved === false) {
        return '';
    }
    $candidate = rtrim(str_replace('\\', '/', strtolower($resolved)), '/');
    if ($root !== false) {
        $root = rtrim(str_replace('\\', '/', strtolower($root)), '/');
        if ($candidate === $root || strpos($candidate, $root . '/') === 0) {
            return '';
        }
    }
    if (!@is_dir($outside) && !@mkdir($outside, 0700, true) && !@is_dir($outside)) {
        return '';
    }
    if (is_link($outside)) {
        return '';
    }
    $resolvedOutside = realpath($outside);
    if ($resolvedOutside === false) {
        return '';
    }
    $resolvedOutside = rtrim(str_replace('\\', '/', strtolower($resolvedOutside)), '/');
    if ($root !== false
        && ($resolvedOutside === $root || strpos($resolvedOutside, $root . '/') === 0)) {
        return '';
    }
    if (DIRECTORY_SEPARATOR === '/' && ((int) fileperms($outside) & 0077) !== 0) {
        return '';
    }
    return $outside;
}

/** Prüft, dass ein Handle weiterhin genau die benannte Privatdatei hält. */
function count_stream_is_named_private(string $path, $stream): bool
{
    clearstatcache(true, $path);
    $opened = fstat($stream);
    $named = @lstat($path);
    return is_array($opened) && is_array($named) && !is_link($path) && is_file($path)
        && (int) ($opened['dev'] ?? -1) === (int) ($named['dev'] ?? -2)
        && (int) ($opened['ino'] ?? -1) === (int) ($named['ino'] ?? -2)
        && (int) ($opened['nlink'] ?? 0) === 1 && (int) ($named['nlink'] ?? 0) === 1
        && (DIRECTORY_SEPARATOR !== '/' || ((int) $opened['mode'] & 0077) === 0);
}

/** Öffnet eine private Datei ohne Links oder Mehrfachverweise. */
function count_open_private_state(string $path, bool $create = true, int $lockMode = LOCK_EX)
{
    if (is_link($path)) {
        return null;
    }
    $stream = null;
    $created = false;
    if ($create) {
        $previousMask = umask(0077);
        try {
            $stream = @fopen($path, 'x+b');
        } finally {
            umask($previousMask);
        }
        $created = is_resource($stream);
    }
    if (!is_resource($stream)) {
        if (is_link($path)) {
            return null;
        }
        if (!$create && !is_file($path)) {
            return null;
        }
        $stream = @fopen($path, $create ? 'r+b' : 'rb');
    }
    if (!is_resource($stream) || !flock($stream, $lockMode)) {
        if (is_resource($stream)) {
            fclose($stream);
        }
        return null;
    }
    if ($created && DIRECTORY_SEPARATOR === '/' && !@chmod($path, 0600)) {
        flock($stream, LOCK_UN);
        fclose($stream);
        return null;
    }
    if (!count_stream_is_named_private($path, $stream)) {
        flock($stream, LOCK_UN);
        fclose($stream);
        return null;
    }
    return $stream;
}

/** Schreibt jeden angeforderten Byte auf den bereits geöffneten Stream. */
function count_write_all($stream, string $data): bool
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
function count_flush_and_sync($stream): bool
{
    return fflush($stream) && fsync($stream);
}

/** Stellt nach einem fehlgeschlagenen Ersatz den zuvor gelesenen Inhalt wieder her. */
function count_restore_stream($stream, string $original): bool
{
    $positioned = fseek($stream, 0, SEEK_SET) === 0;
    $truncated = $positioned && ftruncate($stream, 0);
    $written = $truncated && count_write_all($stream, $original);
    $synced = count_flush_and_sync($stream);
    return $positioned && $truncated && $written && $synced;
}

/** Ersetzt einen Stream transaktional und gibt bei jedem Persistenzfehler false zurück. */
function count_replace_stream($stream, string $data): bool
{
    if (fseek($stream, 0, SEEK_SET) !== 0) {
        return false;
    }
    $original = stream_get_contents($stream);
    if (!is_string($original) || fseek($stream, 0, SEEK_SET) !== 0
        || !ftruncate($stream, 0)) {
        return false;
    }
    if (count_write_all($stream, $data) && count_flush_and_sync($stream)) {
        return true;
    }
    if (!count_restore_stream($stream, $original)) {
        error_log('Solidon: Wiederherstellung des Website-Zählers fehlgeschlagen.');
    }
    return false;
}

/** Schreibt alle Bytes auf denselben weiterhin benannten Handle. */
function count_write_private_state(string $path, $stream, string $data): bool
{
    if (!count_stream_is_named_private($path, $stream)
        || !count_replace_stream($stream, $data)) {
        return false;
    }
    return count_stream_is_named_private($path, $stream);
}

/**
 * Der Zufallswert des Tages, aus dem das Besucherkennzeichen entsteht.
 *
 * Er liegt in einer Datei, weil mehrere Aufrufe denselben brauchen, und er
 * wird überschrieben, sobald das Datum wechselt. Der Wert von gestern ist
 * damit weg — und mit ihm jede Möglichkeit, das Kennzeichen von gestern
 * einer IP-Adresse zuzuordnen.
 */
function day_salt(string $dir, string $day): string
{
    $file = $dir . '/salt.json';
    $stream = count_open_private_state($file);
    if (!is_resource($stream)) {
        throw new RuntimeException('Tageswert nicht verfügbar.');
    }
    try {
        $raw = stream_get_contents($stream);
        if ($raw === false) {
            throw new RuntimeException('Tageswert nicht verfügbar.');
        }
        $current = $raw === '' ? [] : json_decode($raw, true);
        if ($raw !== '' && (!is_array($current) || array_keys($current) !== ['day', 'salt']
            || !is_string($current['day']) || !is_string($current['salt'])
            || preg_match('/^\d{4}-\d{2}-\d{2}$/D', $current['day']) !== 1
            || preg_match('/^[0-9a-f]{32}$/D', $current['salt']) !== 1)) {
            throw new RuntimeException('Tageswert ist ungültig.');
        }
        if (is_array($current) && ($current['day'] ?? '') === $day
            && preg_match('/^[0-9a-f]{32}$/D', (string) ($current['salt'] ?? '')) === 1) {
            return (string) $current['salt'];
        }
        $salt = bin2hex(random_bytes(16));
        $encoded = json_encode(['day' => $day, 'salt' => $salt], JSON_UNESCAPED_SLASHES);
        if (!is_string($encoded) || !count_write_private_state($file, $stream, $encoded)) {
            throw new RuntimeException('Tageswert ließ sich nicht speichern.');
        }
        return $salt;
    } finally {
        flock($stream, LOCK_UN);
        fclose($stream);
    }
}

/** Eigenes dauerhaftes Geheimnis für das gleitende Minutenlimit. */
function count_rate_secret(string $dir): ?string
{
    $path = $dir . '/rate.key';
    $stream = count_open_private_state($path);
    if (!is_resource($stream)) {
        return null;
    }
    try {
        $raw = stream_get_contents($stream);
        if (!is_string($raw)) {
            return null;
        }
        if ($raw !== '') {
            return preg_match('/^[0-9a-f]{64}$/D', $raw) === 1 ? $raw : null;
        }
        $secret = bin2hex(random_bytes(32));
        return count_write_private_state($path, $stream, $secret) ? $secret : null;
    } finally {
        flock($stream, LOCK_UN);
        fclose($stream);
    }
}

/**
 * Das Kennzeichen dieses Besuchers für heute.
 *
 * IP und User-Agent gehen hinein, gespeichert wird nur das Ergebnis. Fehlt
 * eines von beidem, ist das Kennzeichen entsprechend gröber — das ist
 * hinnehmbar, denn es dient dem Zählen, nicht dem Wiedererkennen.
 */
function visitor_mark(string $salt): string
{
    $address = (string) ($_SERVER['REMOTE_ADDR'] ?? '');
    $agent = (string) ($_SERVER['HTTP_USER_AGENT'] ?? '');
    $secret = hex2bin($salt);
    if ($secret === false) {
        throw new RuntimeException('Tageswert ist ungültig.');
    }
    $visitorSecret = hash_hmac('sha256', 'solidon|visitor', $secret, true);
    return substr(hash_hmac('sha256', $address . '|' . $agent, $visitorSecret), 0, MARK_LENGTH);
}

/**
 * Hat der Besucher gesagt, dass er nicht gezählt werden will?
 *
 * `site.js` fragt dasselbe im Browser und kehrt still um — aber **nur für
 * Seitenaufrufe**. Ein Download ist ein blanker Verweis auf diese Datei und
 * läuft an jedem JavaScript vorbei; gezählt wurde er deshalb immer, auch mit
 * eingeschaltetem Signal. Die Datenschutzerklärung sagt im selben Absatz
 * beides zu: dass ein Download über dieselbe Stelle läuft, und dass nicht
 * gezählt wird, wer das Signal sendet. Eine der beiden Zusagen war unwahr.
 *
 * Die Frage steht hier und nicht an den beiden Aufrufstellen, damit ein
 * dritter Zählweg sie nicht vergessen kann.
 */
function opted_out(): bool
{
    return ($_SERVER['HTTP_DNT'] ?? '') === '1'
        || ($_SERVER['HTTP_SEC_GPC'] ?? '') === '1';
}

/** Zwei ohne das private Rate-Geheimnis nicht verknüpfbare Minutenkennzeichen. */
function count_rate_client_keys(string $rateSecret, int $now): array
{
    $secret = hex2bin($rateSecret);
    if ($secret === false) {
        return [];
    }
    $root = hash_hmac('sha256', 'solidon|count-rate', $secret, true);
    $address = (string) ($_SERVER['REMOTE_ADDR'] ?? '-');
    $bucket = intdiv($now, COUNT_RATE_RETENTION_SECONDS);
    $keys = [];
    foreach ([$bucket, $bucket - 1] as $number) {
        $windowSecret = hash_hmac('sha256', (string) $number, $root, true);
        $keys[] = 'ip:' . hash_hmac('sha256', $address, $windowSecret);
    }
    return array_values(array_unique($keys));
}

function count_consume_rate(string $dir, string $rateSecret, int $now): bool
{
    $path = $dir . '/rate.json';
    $stream = count_open_private_state($path);
    if (!is_resource($stream)) {
        return false;
    }
    try {
        $raw = stream_get_contents($stream);
        $state = $raw === '' ? [] : json_decode($raw === false ? '' : $raw, true);
        if ($raw === false || !is_array($state)) {
            return false;
        }
        $clientKeys = count_rate_client_keys($rateSecret, $now);
        if ($clientKeys === []) {
            return false;
        }
        $key = $clientKeys[0];
        $globalKey = 'global';
        $kept = [];
        foreach ($clientKeys as $clientKey) {
            $kept = array_merge($kept, array_values(array_filter(
                (array) ($state[$clientKey] ?? []),
                static fn($stamp): bool => is_int($stamp)
                    && $stamp > $now - COUNT_RATE_RETENTION_SECONDS && $stamp <= $now
            )));
            unset($state[$clientKey]);
        }
        $global = array_values(array_filter(
            (array) ($state[$globalKey] ?? []),
            static fn($stamp): bool => is_int($stamp)
                && $stamp > $now - COUNT_RATE_RETENTION_SECONDS && $stamp <= $now
        ));
        if (count($kept) >= COUNT_MAX_PER_MINUTE
            || count($global) >= COUNT_MAX_GLOBAL_PER_MINUTE) {
            return false;
        }
        $kept[] = $now;
        $global[] = $now;
        foreach ($state as $name => $stamps) {
            $recent = array_values(array_filter(
                (array) $stamps,
                static fn($stamp): bool => is_int($stamp)
                    && $stamp > $now - COUNT_RATE_RETENTION_SECONDS && $stamp <= $now
            ));
            if ($recent === [] || ($name !== $globalKey
                && preg_match('/^ip:[0-9a-f]{64}$/D', (string) $name) !== 1)) {
                unset($state[$name]);
            } else {
                $state[$name] = $recent;
            }
        }
        $state[$key] = $kept;
        $state[$globalKey] = $global;
        $encoded = json_encode($state, JSON_UNESCAPED_SLASHES);
        return is_string($encoded) && count_write_private_state($path, $stream, $encoded);
    } finally {
        flock($stream, LOCK_UN);
        fclose($stream);
    }
}

/** Rollt einen fehlgeschlagenen Anhang bis zur vorherigen Dateigröße zurück. */
function count_rollback_append($stream, int $start): bool
{
    $truncated = ftruncate($stream, $start);
    $positioned = fseek($stream, 0, SEEK_END) === 0;
    $synced = count_flush_and_sync($stream);
    return $truncated && $positioned && $synced;
}

/** Hängt alle Bytes an denselben geprüften Handle an und rollt Teilwrites zurück. */
function count_append_stream(string $path, $stream, string $data): bool
{
    if (!count_stream_is_named_private($path, $stream) || fseek($stream, 0, SEEK_END) !== 0) {
        return false;
    }
    $start = ftell($stream);
    if (!is_int($start)) {
        return false;
    }
    $offset = 0;
    $length = strlen($data);
    while ($offset < $length) {
        $written = fwrite($stream, substr($data, $offset));
        if ($written === false || $written === 0) {
            if (!count_rollback_append($stream, $start)) {
                error_log('Solidon: Wiederherstellung der Website-Monatsdatei fehlgeschlagen.');
            }
            return false;
        }
        $offset += $written;
    }
    if (!count_flush_and_sync($stream) || !count_stream_is_named_private($path, $stream)) {
        if (!count_rollback_append($stream, $start)) {
            error_log('Solidon: Wiederherstellung der Website-Monatsdatei fehlgeschlagen.');
        }
        return false;
    }
    $after = fstat($stream);
    if (!is_array($after) || (int) ($after['size'] ?? -1) !== $start + $length) {
        if (!count_rollback_append($stream, $start)) {
            error_log('Solidon: Wiederherstellung der Website-Monatsdatei fehlgeschlagen.');
        }
        return false;
    }
    return true;
}

/** Schreibt nur innerhalb atomar geprüfter Monats- und Gesamtquoten. */
function count_append(string $dir, string $path, string $line): bool
{
    $resolvedDir = realpath($dir);
    $resolvedParent = realpath(dirname($path));
    if ($resolvedDir === false || $resolvedParent === false
        || strtolower($resolvedDir) !== strtolower($resolvedParent)
        || preg_match('/^\d{4}-\d{2}\.jsonl$/D', basename($path)) !== 1) {
        return false;
    }
    $lockPath = $dir . '/quota.lock';
    $lock = count_open_private_state($lockPath);
    if (!is_resource($lock)) {
        return false;
    }
    $month = null;
    try {
        $month = count_open_private_state($path);
        if (!is_resource($month)) {
            return false;
        }
        $addition = strlen($line) + 1;
        $monthStat = fstat($month);
        $monthBytes = is_array($monthStat) ? (int) ($monthStat['size'] ?? -1) : -1;
        if ($monthBytes < 0 || $monthBytes + $addition > COUNT_MAX_MONTH_BYTES) {
            return false;
        }
        $total = 0;
        foreach (glob($dir . '/*.jsonl') ?: [] as $candidate) {
            if (strtolower($candidate) === strtolower($path)) {
                $bytes = $monthBytes;
            } else {
                $candidateStream = count_open_private_state($candidate, false, LOCK_SH);
                if (!is_resource($candidateStream)) {
                    return false;
                }
                try {
                    $candidateStat = fstat($candidateStream);
                    $bytes = is_array($candidateStat) ? (int) ($candidateStat['size'] ?? -1) : -1;
                } finally {
                    flock($candidateStream, LOCK_UN);
                    fclose($candidateStream);
                }
            }
            if ($bytes < 0) {
                return false;
            }
            $total += $bytes;
            if ($total + $addition > COUNT_MAX_TOTAL_BYTES) {
                return false;
            }
        }
        return count_append_stream($path, $month, $line . "\n");
    } finally {
        if (is_resource($month)) {
            flock($month, LOCK_UN);
            fclose($month);
        }
        flock($lock, LOCK_UN);
        fclose($lock);
    }
}

function record(string $kind, string $value): bool
{
    if (opted_out()) {
        return true;  // Der Download läuft trotzdem — nur die Zeile entsteht nicht.
    }

    $dir = store_dir();
    if (!@is_dir($dir)) {
        return true;  // Kein Ablageort — dann eben keine Zahl. Ein Zähler hält nie den Betrieb an.
    }

    try {
        $now = new DateTimeImmutable('now', new DateTimeZone('UTC'));
        $rateSecret = count_rate_secret($dir);
        if ($rateSecret === null
            || !count_consume_rate($dir, $rateSecret, $now->getTimestamp())) {
            return false;
        }
    } catch (Throwable $problem) {
        return false;
    }

    try {
        $day = $now->format('Y-m-d');
        $salt = day_salt($dir, $day);
        $line = json_encode(
            [
                't' => $now->format('c'),
                'k' => $kind,
                'v' => $value,
                'r' => referrer_host(),
                'u' => visitor_mark($salt),
            ],
            JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE
        );
    } catch (Throwable $problem) {
        return true;  // Ein Statistikfehler hält Seiten und Downloads nicht an.
    }
    if ($line !== false) {
        $path = $dir . '/' . $now->format('Y-m') . '.jsonl';
        return count_append($dir, $path, $line);
    }
    return true;
}

/**
 * Woher der Besucher kam — nur der Host, nicht die volle Adresse.
 *
 * Die volle Adresse einer verweisenden Seite kann einen Suchbegriff oder
 * eine Kennung enthalten; der Host beantwortet die Frage, die hier gestellt
 * wird („kam das über 3druck.com?"), und sonst nichts. Verweise von der
 * eigenen Domain fallen weg: Sie sind Navigation, keine Herkunft.
 */
function referrer_host(): string
{
    // **Der mitgeschickte Verweis gewinnt über den Header, und ohne ihn gibt
    // es überhaupt keinen.** Der Seitenaufruf kommt als Beacon aus `site.js`,
    // und dessen `Referer` ist die Seite, von der aus gerufen wird — also
    // immer solidon3d.de selbst. Die Prüfung unten erkennt sie als eigen und
    // verwirft sie, völlig zu Recht: Ein Sprung von Seite zu Seite ist kein
    // Verweis von außen. Nur stand damit in „Woher" nie etwas, und es sah aus
    // wie „niemand schickt seine Herkunft mit". Woher der Besucher wirklich
    // kam, weiß allein `document.referrer` im Browser; `site.js` reicht ihn
    // als `r` herein.
    //
    // Der Header bleibt der Weg für Downloads: Die laufen über `?f=` direkt
    // gegen diese Datei, ohne Skript, und dort ist er das Einzige, was es gibt.
    $posted = $_POST['r'] ?? null;
    $referrer = is_string($posted) ? $posted : (string) ($_SERVER['HTTP_REFERER'] ?? '');
    if ($referrer === '') {
        return '';
    }
    $host = strtolower((string) parse_url($referrer, PHP_URL_HOST));

    // Der eigene Name ohne Port. ``HTTP_HOST`` trägt ihn mit, sobald der
    // Server nicht auf 80 oder 443 hört — beim Ausprobieren auf dem eigenen
    // Rechner ist das die Regel, und ohne diese Zeile zählte dort jeder
    // Sprung von Seite zu Seite als Verweis von außen.
    $bare = static fn (string $name): string => preg_replace('/^www\./', '', $name) ?? $name;
    if ($host === '' || $bare($host) === 'solidon3d.de') {
        return '';
    }
    return substr($host, 0, 80);
}

// --- Eingänge --------------------------------------------------------------

/**
 * Einen Pfad auf das kürzen, was gezählt werden soll.
 *
 * Alles außer dem Pfad selbst fliegt weg: Abfrageteil, Sprungmarke,
 * Steuerzeichen. Was bleibt, ist die Seite — und die ist die Frage.
 */
function clean_path(string $raw): string
{
    $path = (string) parse_url(trim($raw), PHP_URL_PATH);
    if ($path === '' || $path[0] !== '/') {
        $path = '/' . ltrim($path, '/');
    }
    $path = preg_replace('/[^\x20-\x7e]/', '', $path) ?? '/';
    return substr($path, 0, MAX_PATH);
}

function count_request_bytes(): int
{
    $declared = (string) ($_SERVER['CONTENT_LENGTH'] ?? '');
    if ($declared !== '' && (!ctype_digit($declared) || (int) $declared > COUNT_MAX_BODY)) {
        return -1;
    }
    $raw = file_get_contents('php://input', false, null, 0, COUNT_MAX_BODY + 1);
    if ($raw === false || strlen($raw) > COUNT_MAX_BODY) {
        return -1;
    }
    return strlen($raw);
}

function count_security_headers(): void
{
    header('X-Content-Type-Options: nosniff');
    header('Referrer-Policy: no-referrer');
    header('X-Frame-Options: DENY');
    header('Permissions-Policy: camera=(), microphone=(), geolocation=()');
    header("Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; base-uri 'none'");
    header('Cache-Control: no-store');
}

function count_require_origin(): void
{
    $origin = trim((string) ($_SERVER['HTTP_ORIGIN'] ?? ''));
    if (!in_array(strtolower($origin), ['https://solidon3d.de', 'https://www.solidon3d.de'], true)) {
        http_response_code(403);
        exit;
    }
}

count_security_headers();
$method = (string) ($_SERVER['REQUEST_METHOD'] ?? '');
if (!in_array($method, ['GET', 'POST'], true)) {
    header('Allow: GET, POST');
    http_response_code(405);
    exit;
}
if ($method === 'POST') {
    count_require_origin();
    $contentType = strtolower(trim(explode(';', (string) ($_SERVER['CONTENT_TYPE'] ?? ''), 2)[0]));
    if ($contentType !== 'application/x-www-form-urlencoded') {
        http_response_code(415);
        exit;
    }
    if (count_request_bytes() < 0) {
        http_response_code(413);
        exit;
    }
}

$fileValue = $_GET['f'] ?? '';
$file = is_string($fileValue) ? $fileValue : '';
if ($file !== '') {
    if ($method !== 'GET') {
        header('Allow: GET');
        http_response_code(405);
        exit;
    }
    // Download: nur ein Dateiname, kein Pfad, und die Datei muss es geben.
    $name = basename($file);
    if ($name === '' || $name !== $file || !is_file(DOWNLOAD_DIR . '/' . $name)) {
        http_response_code(404);
        header('Content-Type: text/plain; charset=utf-8');
        echo "Diese Datei gibt es hier nicht.\n";
        exit;
    }
    record('d', $name);
    header('Location: ' . DOWNLOAD_URL . rawurlencode($name), true, 302);
    exit;
}

$pageValue = $_POST['p'] ?? '';
$page = is_string($pageValue) ? $pageValue : '';
if ($page !== '') {
    if ($method !== 'POST') {
        header('Allow: POST');
        http_response_code(405);
        exit;
    }
    if (!record('p', clean_path($page))) {
        http_response_code(429);
        exit;
    }
    http_response_code(204);
    exit;
}

// Ohne beides: Die Datei sagt, wofür sie da ist. Kein Fehler — wer sie von
// Hand aufruft, hat nichts falsch gemacht.
http_response_code(400);
header('Content-Type: text/plain; charset=utf-8');
echo "Zählpunkt von solidon3d.de. Erwartet ?f=<Datei> oder das Feld p.\n";
