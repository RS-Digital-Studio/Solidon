<?php
/** Entfernt abgelaufene private Missbrauchszähler außerhalb von HTTP. */

declare(strict_types=1);

const CLEANUP_MAX_JSON_BYTES = 4 * 1024 * 1024;
const CLEANUP_MAX_MONTH_BYTES = 16 * 1024 * 1024;
const CLEANUP_MAX_MONTH_TOTAL_BYTES = 64 * 1024 * 1024;
const CLEANUP_MAX_MONTH_FILES = 120;
const CLEANUP_MAX_MONTH_LINE_BYTES = 4096;
const CLEANUP_EXIT_CONFIGURATION = 64;
const CLEANUP_EXIT_DATA = 65;
const CLEANUP_EXIT_IO = 74;
const CLEANUP_EXIT_LOCKED = 75;

final class CleanupFailure extends RuntimeException
{
    public int $exitCode;

    public function __construct(string $message, int $exitCode)
    {
        parent::__construct($message);
        $this->exitCode = $exitCode;
    }
}

/** Bricht bei einem Webaufruf ab, bevor Pfade oder Zustände gelesen werden. */
if (PHP_SAPI !== 'cli') {
    http_response_code(404);
    exit(CLEANUP_EXIT_CONFIGURATION);
}
if (PHP_VERSION_ID < 80100) {
    fwrite(STDERR, "Privatzustand: PHP 8.1 oder neuer ist erforderlich.\n");
    exit(CLEANUP_EXIT_CONFIGURATION);
}

/** Erkennt absolute Unix-, Laufwerks- und UNC-Pfade. */
function cleanup_path_is_absolute(string $path): bool
{
    return substr($path, 0, 1) === '/'
        || (strlen($path) >= 3 && ctype_alpha($path[0]) && $path[1] === ':'
            && ($path[2] === '\\' || $path[2] === '/'))
        || substr($path, 0, 2) === '\\\\';
}

/** Vereinheitlicht einen Pfad nur für Lagevergleiche, nie zum Öffnen. */
function cleanup_normal_path(string $path): string
{
    return rtrim(str_replace('\\', '/', strtolower($path)), '/');
}

/** Prüft einen zwingenden CLI-Pfad ohne einen versteckten Standardwert. */
function cleanup_required_path(string $name, string $path): string
{
    $path = trim($path);
    $normal = str_replace('\\', '/', $path);
    if ($path === '' || !cleanup_path_is_absolute($path)
        || preg_match('#(^|/)\.\.(/|$)#', $normal) === 1) {
        throw new CleanupFailure(
            'Eine private Pfadvariable fehlt oder ist ungültig: ' . $name,
            CLEANUP_EXIT_CONFIGURATION
        );
    }
    return rtrim($path, "\\/");
}

/** Liest genau die drei benannten Plesk-Argumente. */
function cleanup_arguments(array $arguments): array
{
    $names = [
        '--stats-dir' => 'SOLIDON_STATS_DIR',
        '--activation-rate' => 'SOLIDON_ACTIVATION_RATE_FILE',
        '--support-rate' => 'SOLIDON_SUPPORT_RATE_FILE',
    ];
    $values = [];
    for ($index = 1; $index < count($arguments); $index++) {
        $argument = (string) $arguments[$index];
        $value = '';
        $name = $argument;
        if (strpos($argument, '=') !== false) {
            [$name, $value] = explode('=', $argument, 2);
        } else {
            if (!array_key_exists($name, $names) || !array_key_exists($index + 1, $arguments)) {
                throw new CleanupFailure('Die CLI-Argumente sind unvollständig.', CLEANUP_EXIT_CONFIGURATION);
            }
            $value = (string) $arguments[++$index];
        }
        if (!array_key_exists($name, $names) || array_key_exists($name, $values)) {
            throw new CleanupFailure('Die CLI-Argumente sind ungültig.', CLEANUP_EXIT_CONFIGURATION);
        }
        $values[$name] = cleanup_required_path($names[$name], $value);
    }
    if (array_keys($values) !== array_keys($names)) {
        foreach (array_keys($names) as $name) {
            if (!array_key_exists($name, $values)) {
                throw new CleanupFailure('Ein CLI-Pfad fehlt: ' . $name, CLEANUP_EXIT_CONFIGURATION);
            }
        }
    }
    return $values;
}

/** Verhindert Links und zu offene Rechte in allen vorhandenen Pfadteilen. */
function cleanup_require_private_parent(string $path, string $label): void
{
    $parent = dirname($path);
    $probe = $parent;
    while (true) {
        if (is_link($probe)) {
            throw new CleanupFailure($label . ': Ein Pfadteil ist ein Link.', CLEANUP_EXIT_DATA);
        }
        if (!file_exists($probe) || !is_dir($probe)) {
            throw new CleanupFailure($label . ': Der private Ordner fehlt.', CLEANUP_EXIT_CONFIGURATION);
        }
        $next = dirname($probe);
        if ($next === $probe) {
            break;
        }
        $probe = $next;
    }
    if (!is_dir($parent) || is_link($parent)) {
        throw new CleanupFailure($label . ': Der private Ordner fehlt.', CLEANUP_EXIT_CONFIGURATION);
    }
    $resolved = realpath($parent);
    $webRoot = realpath(dirname(__DIR__));
    if ($resolved === false || $webRoot === false) {
        throw new CleanupFailure($label . ': Die Pfadlage ist nicht prüfbar.', CLEANUP_EXIT_DATA);
    }
    $candidate = cleanup_normal_path($resolved);
    $public = cleanup_normal_path($webRoot);
    if ($candidate === $public || strpos($candidate, $public . '/') === 0) {
        throw new CleanupFailure($label . ': Der Zustand liegt im Dokumentenstamm.', CLEANUP_EXIT_DATA);
    }
    if (DIRECTORY_SEPARATOR === '/') {
        $mode = fileperms($resolved);
        if ($mode === false || ((int) $mode & 0077) !== 0) {
            throw new CleanupFailure($label . ': Der private Ordner hat zu weite Rechte.', CLEANUP_EXIT_DATA);
        }
        if (function_exists('posix_geteuid')) {
            $owner = fileowner($resolved);
            if ($owner === false || (int) $owner !== posix_geteuid()) {
                throw new CleanupFailure($label . ': Der private Ordner gehört einem anderen Konto.', CLEANUP_EXIT_DATA);
            }
        }
    }
}

/** Vergleicht einen geöffneten Handle mit dem weiterhin benannten Objekt. */
function cleanup_same_file(array $opened, array $named): bool
{
    return (int) ($opened['dev'] ?? -1) === (int) ($named['dev'] ?? -2)
        && (int) ($opened['ino'] ?? -1) === (int) ($named['ino'] ?? -2)
        && (int) ($opened['nlink'] ?? 0) === 1
        && (int) ($named['nlink'] ?? 0) === 1;
}

/** Öffnet und sperrt genau eine vorhandene reguläre Privatdatei. */
function cleanup_open_locked(array $target): ?array
{
    $path = $target['path'];
    $label = $target['label'];
    cleanup_require_private_parent($path, $label);
    if (is_link($path)) {
        throw new CleanupFailure($label . ': Die Zustandsdatei ist ein Link.', CLEANUP_EXIT_DATA);
    }
    $before = @lstat($path);
    if ($before === false) {
        if (file_exists($path) || is_link($path)) {
            throw new CleanupFailure($label . ': Die Zustandsdatei ist nicht prüfbar.', CLEANUP_EXIT_DATA);
        }
        return null;
    }
    if (!is_file($path)) {
        throw new CleanupFailure($label . ': Der Zustand ist keine reguläre Datei.', CLEANUP_EXIT_DATA);
    }
    $stream = @fopen($path, 'r+b');
    if ($stream === false) {
        throw new CleanupFailure($label . ': Die Zustandsdatei ist nicht lesbar.', CLEANUP_EXIT_IO);
    }
    if (!flock($stream, LOCK_EX | LOCK_NB)) {
        fclose($stream);
        throw new CleanupFailure($label . ': Die Zustandsdatei ist gerade gesperrt.', CLEANUP_EXIT_LOCKED);
    }
    clearstatcache(true, $path);
    $opened = fstat($stream);
    $named = @lstat($path);
    if (!is_array($opened) || !is_array($named) || is_link($path)
        || !cleanup_same_file($opened, $named)) {
        flock($stream, LOCK_UN);
        fclose($stream);
        throw new CleanupFailure($label . ': Die Dateiidentität hat sich geändert.', CLEANUP_EXIT_DATA);
    }
    if (DIRECTORY_SEPARATOR === '/') {
        if (((int) $opened['mode'] & 0077) !== 0) {
            flock($stream, LOCK_UN);
            fclose($stream);
            throw new CleanupFailure($label . ': Die Zustandsdatei hat zu weite Rechte.', CLEANUP_EXIT_DATA);
        }
        if (function_exists('posix_geteuid')
            && (int) ($opened['uid'] ?? -1) !== posix_geteuid()) {
            flock($stream, LOCK_UN);
            fclose($stream);
            throw new CleanupFailure($label . ': Die Zustandsdatei gehört einem anderen Konto.', CLEANUP_EXIT_DATA);
        }
    }
    return ['target' => $target, 'stream' => $stream, 'stat' => $opened];
}

/** Erzeugt oder öffnet die gemeinsame Count-Quotensperre mit demselben Privatvertrag. */
function cleanup_open_quota_lock(string $statsDir): array
{
    $target = [
        'label' => 'Website-Quotensperre',
        'path' => $statsDir . DIRECTORY_SEPARATOR . 'quota.lock',
        'kind' => 'lock',
    ];
    $path = $target['path'];
    cleanup_require_private_parent($path, $target['label']);
    if (is_link($path)) {
        throw new CleanupFailure('Website-Quotensperre: Die Datei ist ein Link.', CLEANUP_EXIT_DATA);
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
            throw new CleanupFailure('Website-Quotensperre: Die Datei ist ein Link.', CLEANUP_EXIT_DATA);
        }
        $stream = @fopen($path, 'r+b');
    }
    if (!is_resource($stream) || !flock($stream, LOCK_EX | LOCK_NB)) {
        if (is_resource($stream)) {
            fclose($stream);
        }
        throw new CleanupFailure(
            'Website-Quotensperre: Die Datei ist gerade gesperrt.',
            CLEANUP_EXIT_LOCKED
        );
    }
    if ($created && DIRECTORY_SEPARATOR === '/' && !@chmod($path, 0600)) {
        flock($stream, LOCK_UN);
        fclose($stream);
        throw new CleanupFailure(
            'Website-Quotensperre: Sichere Rechte ließen sich nicht setzen.',
            CLEANUP_EXIT_DATA
        );
    }
    clearstatcache(true, $path);
    $opened = fstat($stream);
    $named = @lstat($path);
    if (!is_array($opened) || !is_array($named) || is_link($path) || !is_file($path)
        || !cleanup_same_file($opened, $named) || (int) ($opened['size'] ?? -1) !== 0
        || (DIRECTORY_SEPARATOR === '/' && ((int) $opened['mode'] & 0077) !== 0)
        || (DIRECTORY_SEPARATOR === '/' && function_exists('posix_geteuid')
            && (int) ($opened['uid'] ?? -1) !== posix_geteuid())) {
        flock($stream, LOCK_UN);
        fclose($stream);
        throw new CleanupFailure(
            'Website-Quotensperre: Die Datei ist nicht sicher.',
            CLEANUP_EXIT_DATA
        );
    }
    return ['target' => $target, 'stream' => $stream, 'stat' => $opened];
}

/** Liefert den laufenden und unmittelbar vorherigen UTC-Kalendermonat. */
function cleanup_month_window(int $now): array
{
    $instant = (new DateTimeImmutable('@' . $now))->setTimezone(new DateTimeZone('UTC'));
    $current = $instant->format('Y-m');
    $previous = $instant->modify('first day of this month')->modify('-1 month')->format('Y-m');
    return [$current, $previous];
}

/** Erfasst jede JSONL-Datei; ein abweichender Name könnte sonst die Frist umgehen. */
function cleanup_month_targets(string $statsDir, int $now): array
{
    [$current] = cleanup_month_window($now);
    $paths = glob($statsDir . DIRECTORY_SEPARATOR . '*.jsonl', GLOB_NOSORT);
    if ($paths === false) {
        throw new CleanupFailure('Monatsdateien: Der Ordner ist nicht lesbar.', CLEANUP_EXIT_IO);
    }
    if (count($paths) > CLEANUP_MAX_MONTH_FILES) {
        throw new CleanupFailure('Monatsdateien: Es liegen zu viele Dateien vor.', CLEANUP_EXIT_DATA);
    }
    sort($paths, SORT_STRING);
    $targets = [];
    foreach ($paths as $path) {
        $name = basename($path);
        if (preg_match('/^(\d{4})-(\d{2})\.jsonl$/D', $name, $match) !== 1
            || !checkdate((int) $match[2], 1, (int) $match[1])) {
            throw new CleanupFailure(
                'Monatsdateien: Ein JSONL-Dateiname umgeht das Kalenderschema.',
                CLEANUP_EXIT_DATA
            );
        }
        $month = $match[1] . '-' . $match[2];
        if ($month > $current) {
            throw new CleanupFailure(
                'Monatsdateien: Eine Datei liegt in einem künftigen UTC-Monat.',
                CLEANUP_EXIT_DATA
            );
        }
        $targets[] = [
            'label' => 'Reichweitenmonat ' . $month,
            'path' => $path,
            'kind' => 'month',
            'month' => $month,
        ];
    }
    return $targets;
}

/** Prüft einen Rate-Zustand und liefert bei alten SHA-Schlüsseln seine bereinigte Form. */
function cleanup_validate_rate_json(
    string $raw,
    string $pattern,
    string $legacyPattern,
    int $now,
    string $label
): ?string
{
    try {
        $state = json_decode($raw, true, 16, JSON_THROW_ON_ERROR);
    } catch (JsonException $problem) {
        throw new CleanupFailure($label . ': Der JSON-Zustand ist beschädigt.', CLEANUP_EXIT_DATA);
    }
    if (!is_array($state)) {
        throw new CleanupFailure($label . ': Der JSON-Zustand hat den falschen Aufbau.', CLEANUP_EXIT_DATA);
    }
    $clean = [];
    $changed = false;
    foreach ($state as $key => $stamps) {
        if (!is_string($key) || !is_array($stamps)) {
            throw new CleanupFailure($label . ': Der JSON-Zustand hat den falschen Aufbau.', CLEANUP_EXIT_DATA);
        }
        foreach ($stamps as $stamp) {
            if (!is_int($stamp) || $stamp <= 0 || $stamp > $now) {
                throw new CleanupFailure($label . ': Der JSON-Zustand enthält ungültige Zeiten.', CLEANUP_EXIT_DATA);
            }
        }
        if (preg_match($pattern, $key) === 1) {
            $clean[$key] = $stamps;
        } elseif ($legacyPattern !== '' && preg_match($legacyPattern, $key) === 1) {
            $changed = true;
        } else {
            throw new CleanupFailure($label . ': Der JSON-Zustand hat den falschen Aufbau.', CLEANUP_EXIT_DATA);
        }
    }
    if (!$changed) {
        return null;
    }
    $encoded = json_encode((object) $clean, JSON_UNESCAPED_SLASHES);
    if (!is_string($encoded)) {
        throw new CleanupFailure($label . ': Der JSON-Zustand ist nicht speicherbar.', CLEANUP_EXIT_DATA);
    }
    return $encoded;
}

/** Prüft den Tageswert, bevor seine Datei anhand des Alters gelöscht wird. */
function cleanup_validate_salt_json(string $raw, string $label): void
{
    try {
        $state = json_decode($raw, true, 4, JSON_THROW_ON_ERROR);
    } catch (JsonException $problem) {
        throw new CleanupFailure($label . ': Der JSON-Zustand ist beschädigt.', CLEANUP_EXIT_DATA);
    }
    if (!is_array($state) || array_keys($state) !== ['day', 'salt']
        || !is_string($state['day']) || !is_string($state['salt'])
        || preg_match('/^\d{4}-\d{2}-\d{2}$/D', $state['day']) !== 1
        || preg_match('/^[0-9a-f]{32}$/D', $state['salt']) !== 1) {
        throw new CleanupFailure($label . ': Der JSON-Zustand hat den falschen Aufbau.', CLEANUP_EXIT_DATA);
    }
    [$year, $month, $day] = array_map('intval', explode('-', $state['day']));
    if (!checkdate($month, $day, $year)) {
        throw new CleanupFailure($label . ': Der JSON-Zustand hat ein ungültiges Datum.', CLEANUP_EXIT_DATA);
    }
}

/** Prüft eine Reichweitendatei streamend gegen Count-Schema und UTC-Monat. */
function cleanup_validate_month_jsonl($stream, int $size, string $month, string $label): string
{
    if (fseek($stream, 0, SEEK_SET) !== 0) {
        throw new CleanupFailure($label . ': Die Datei ist nicht lesbar.', CLEANUP_EXIT_IO);
    }
    $read = 0;
    $original = '';
    while (($withNewline = fgets($stream, CLEANUP_MAX_MONTH_LINE_BYTES + 2)) !== false) {
        $length = strlen($withNewline);
        $read += $length;
        if ($read > $size || $length < 2 || $length > CLEANUP_MAX_MONTH_LINE_BYTES + 1
            || substr($withNewline, -1) !== "\n") {
            throw new CleanupFailure($label . ': Eine JSONL-Zeile ist ungültig.', CLEANUP_EXIT_DATA);
        }
        $original .= $withNewline;
        $line = substr($withNewline, 0, -1);
        try {
            $row = json_decode($line, true, 8, JSON_THROW_ON_ERROR);
        } catch (JsonException $problem) {
            throw new CleanupFailure($label . ': Eine JSONL-Zeile ist beschädigt.', CLEANUP_EXIT_DATA);
        }
        if (!is_array($row) || array_keys($row) !== ['t', 'k', 'v', 'r', 'u']
            || !is_string($row['t']) || !is_string($row['k']) || !is_string($row['v'])
            || !is_string($row['r']) || !is_string($row['u'])
            || preg_match('/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00$/D', $row['t']) !== 1
            || substr($row['t'], 0, 7) !== $month || !in_array($row['k'], ['p', 'd'], true)
            || strlen($row['v']) === 0 || strlen($row['v']) > 255
            || preg_match('/[\x00-\x1f\x7f]/', $row['v']) === 1
            || strlen($row['r']) > 80 || preg_match('/[\x00-\x20\x7f]/', $row['r']) === 1
            || preg_match('/^[0-9a-f]{8}$/D', $row['u']) !== 1) {
            throw new CleanupFailure($label . ': Eine JSONL-Zeile hat das falsche Schema.', CLEANUP_EXIT_DATA);
        }
        $when = DateTimeImmutable::createFromFormat('!Y-m-d\TH:i:sP', $row['t']);
        $errors = DateTimeImmutable::getLastErrors();
        if ($when === false || ($errors !== false
            && ((int) $errors['warning_count'] !== 0 || (int) $errors['error_count'] !== 0))
            || $when->format('Y-m-d\TH:i:sP') !== $row['t']) {
            throw new CleanupFailure($label . ': Eine JSONL-Zeit ist ungültig.', CLEANUP_EXIT_DATA);
        }
        if (($row['k'] === 'p' && substr($row['v'], 0, 1) !== '/')
            || ($row['k'] === 'd' && basename($row['v']) !== $row['v'])) {
            throw new CleanupFailure($label . ': Ein JSONL-Ziel ist ungültig.', CLEANUP_EXIT_DATA);
        }
    }
    if (!feof($stream) || $read !== $size) {
        throw new CleanupFailure($label . ': Die Datei ist nicht vollständig lesbar.', CLEANUP_EXIT_IO);
    }
    return $original;
}

/** Liest einen gesperrten Zustand begrenzt und prüft sein vollständiges Schema. */
function cleanup_validate_locked(array &$locked, int $now): ?string
{
    $target = $locked['target'];
    $stream = $locked['stream'];
    $size = (int) ($locked['stat']['size'] ?? -1);
    $mtime = (int) ($locked['stat']['mtime'] ?? -1);
    if ($target['kind'] === 'lock') {
        if ($size !== 0) {
            throw new CleanupFailure($target['label'] . ': Die Sperrdatei ist nicht leer.', CLEANUP_EXIT_DATA);
        }
        return null;
    }
    $limit = $target['kind'] === 'month' ? CLEANUP_MAX_MONTH_BYTES : CLEANUP_MAX_JSON_BYTES;
    if ($size < 0 || $size > $limit || $mtime <= 0 || $mtime > $now) {
        throw new CleanupFailure($target['label'] . ': Größe oder Zeit ist ungültig.', CLEANUP_EXIT_DATA);
    }
    if ($target['kind'] === 'month') {
        $locked['original'] = cleanup_validate_month_jsonl(
            $stream,
            $size,
            $target['month'],
            $target['label']
        );
        return null;
    }
    rewind($stream);
    $raw = stream_get_contents($stream, $limit + 1);
    if (!is_string($raw) || strlen($raw) !== $size) {
        throw new CleanupFailure($target['label'] . ': Der Zustand ist nicht vollständig lesbar.', CLEANUP_EXIT_IO);
    }
    if ($target['kind'] === 'salt') {
        cleanup_validate_salt_json($raw, $target['label']);
        return null;
    }
    return cleanup_validate_rate_json(
        $raw,
        $target['pattern'],
        $target['legacy_pattern'],
        $now,
        $target['label']
    );
}

/** Schreibt jeden angeforderten Byte auf den bereits geöffneten Stream. */
function cleanup_write_all($stream, string $data): bool
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

/** Erzwingt die Persistenz; der Wartungslauf verlangt PHP 8.1 oder neuer. */
function cleanup_flush_and_sync($stream): bool
{
    return fflush($stream) && fsync($stream);
}

/** Stellt nach einem fehlgeschlagenen Ersatz den zuvor gelesenen Inhalt wieder her. */
function cleanup_restore_stream($stream, string $original): bool
{
    $positioned = fseek($stream, 0, SEEK_SET) === 0;
    $truncated = $positioned && ftruncate($stream, 0);
    $written = $truncated && cleanup_write_all($stream, $original);
    $synced = cleanup_flush_and_sync($stream);
    return $positioned && $truncated && $written && $synced;
}

/** Ersetzt einen Stream transaktional und gibt bei jedem Persistenzfehler false zurück. */
function cleanup_replace_stream($stream, string $data): bool
{
    if (fseek($stream, 0, SEEK_SET) !== 0) {
        return false;
    }
    $original = stream_get_contents($stream);
    if (!is_string($original) || fseek($stream, 0, SEEK_SET) !== 0
        || !ftruncate($stream, 0)) {
        return false;
    }
    if (cleanup_write_all($stream, $data) && cleanup_flush_and_sync($stream)) {
        return true;
    }
    if (!cleanup_restore_stream($stream, $original)) {
        error_log('Solidon: Wiederherstellung eines privaten Zählers fehlgeschlagen.');
    }
    return false;
}

/** Schreibt JSON dauerhaft auf denselben gesperrten Handle. */
function cleanup_write_locked(array $locked, string $data): void
{
    $stream = $locked['stream'];
    $path = $locked['target']['path'];
    clearstatcache(true, $path);
    $opened = fstat($stream);
    $named = @lstat($path);
    if (!is_array($opened) || !is_array($named) || is_link($path)
        || !cleanup_same_file($opened, $named)) {
        throw new CleanupFailure(
            $locked['target']['label'] . ': Die Dateiidentität hat sich geändert.',
            CLEANUP_EXIT_DATA
        );
    }
    if (!cleanup_replace_stream($stream, $data)) {
        throw new CleanupFailure(
            $locked['target']['label'] . ': Der Zustand ließ sich nicht schreiben.',
            CLEANUP_EXIT_IO
        );
    }
    clearstatcache(true, $path);
    $named = @lstat($path);
    if (!is_array($named) || is_link($path) || !cleanup_same_file($opened, $named)) {
        throw new CleanupFailure(
            $locked['target']['label'] . ': Die Dateiidentität hat sich geändert.',
            CLEANUP_EXIT_DATA
        );
    }
}

/** Entfernt eine bereits dauerhaft geleerte Datei nur bei unveränderter Identität. */
function cleanup_unlink_empty_locked(array &$locked): void
{
    $path = $locked['target']['path'];
    clearstatcache(true, $path);
    $named = @lstat($path);
    if (!is_array($named) || is_link($path) || !cleanup_same_file($locked['stat'], $named)) {
        throw new CleanupFailure(
            $locked['target']['label'] . ': Die Dateiidentität hat sich vor dem Löschen geändert.',
            CLEANUP_EXIT_DATA
        );
    }
    if (@unlink($path)) {
        return;
    }

    // Windows verweigert das Entfernen oft, solange derselbe Prozess den
    // Handle hält. Der Inhalt ist zu diesem Zeitpunkt bereits dauerhaft leer.
    flock($locked['stream'], LOCK_UN);
    fclose($locked['stream']);
    $locked['stream'] = null;
    clearstatcache(true, $path);
    $named = @lstat($path);
    if (!is_array($named) || is_link($path) || !cleanup_same_file($locked['stat'], $named)
        || !@unlink($path)) {
        throw new CleanupFailure(
            $locked['target']['label'] . ': Die geleerte Datei ließ sich nicht entfernen.',
            CLEANUP_EXIT_IO
        );
    }
}

/** Leert den Tageswert dauerhaft und entfernt erst danach seinen Namen. */
function cleanup_unlink_salt(array &$locked): void
{
    cleanup_write_locked($locked, '{}');
    cleanup_unlink_empty_locked($locked);
}

/** Leert alle alten Monate als Gruppe; bei einem Schreibfehler werden frühere wiederhergestellt. */
function cleanup_remove_old_months(array &$months): int
{
    $cleared = [];
    try {
        foreach ($months as $index => &$locked) {
            cleanup_write_locked($locked, '');
            $cleared[] = $index;
        }
        unset($locked);
    } catch (Throwable $problem) {
        $restored = true;
        foreach (array_reverse($cleared) as $index) {
            try {
                cleanup_write_locked($months[$index], $months[$index]['original']);
            } catch (Throwable $restoreProblem) {
                $restored = false;
            }
        }
        if (!$restored) {
            error_log('Solidon: Wiederherstellung der Reichweitenmonate fehlgeschlagen.');
        }
        throw $problem;
    }
    foreach ($months as &$locked) {
        cleanup_unlink_empty_locked($locked);
    }
    unset($locked);
    return count($months);
}

/** Gibt alle noch gehaltenen Sperren auch nach einem Fehler frei. */
function cleanup_close_all(array &$lockedFiles): void
{
    for ($index = count($lockedFiles) - 1; $index >= 0; $index--) {
        $locked = &$lockedFiles[$index];
        if (is_resource($locked['stream'])) {
            flock($locked['stream'], LOCK_UN);
            fclose($locked['stream']);
            $locked['stream'] = null;
        }
        unset($locked);
    }
}

/** Prüft erst alle Ziele und beginnt erst danach mit der eigentlichen Bereinigung. */
function cleanup_main(): int
{
    global $argv;
    if (!is_array($argv)) {
        throw new CleanupFailure('Die CLI-Argumente fehlen.', CLEANUP_EXIT_CONFIGURATION);
    }
    $arguments = cleanup_arguments($argv);
    $statsDir = $arguments['--stats-dir'];
    $activationRate = $arguments['--activation-rate'];
    $supportRate = $arguments['--support-rate'];
    $targets = [
        [
            'label' => 'Website-Zähler',
            'path' => $statsDir . DIRECTORY_SEPARATOR . 'rate.json',
            'ttl' => 60,
            'kind' => 'rate',
            'pattern' => '/^(?:global|ip:[0-9a-f]{64})$/D',
            'legacy_pattern' => '/^[0-9a-f]{64}$/D',
        ],
        [
            'label' => 'Aktivierungszähler',
            'path' => $activationRate,
            'ttl' => 900,
            'kind' => 'rate',
            'pattern' => '/^[a-z]{1,16}:(?:global|ip:[0-9a-f]{64})$/D',
            'legacy_pattern' => '/^[a-z]{1,16}:[0-9a-f]{64}$/D',
        ],
        [
            'label' => 'Statistik-Anmeldezähler',
            'path' => $statsDir . DIRECTORY_SEPARATOR . 'anmeldeversuche.json',
            'ttl' => 900,
            'kind' => 'rate',
            'pattern' => '/^(?:global|ip:v2:[0-9a-f]{64})$/D',
            'legacy_pattern' => '/^ip:[0-9a-f]{64}$/D',
        ],
        [
            'label' => 'Support-Zähler',
            'path' => $supportRate,
            'ttl' => 3600,
            'kind' => 'rate',
            'pattern' => '/^(?:global|ip:[0-9a-f]{64})$/D',
            'legacy_pattern' => '/^[0-9a-f]{64}$/D',
        ],
        [
            'label' => 'Besucher-Tageswert',
            'path' => $statsDir . DIRECTORY_SEPARATOR . 'salt.json',
            'ttl' => 86400,
            'kind' => 'salt',
            'pattern' => '',
            'legacy_pattern' => '',
        ],
    ];
    $lockedFiles = [];
    $missing = 0;
    $cleaned = 0;
    $now = time();
    try {
        $lockedFiles[] = cleanup_open_quota_lock($statsDir);
        $monthTargets = cleanup_month_targets($statsDir, $now);
        foreach ($monthTargets as $target) {
            $locked = cleanup_open_locked($target);
            if ($locked === null) {
                throw new CleanupFailure(
                    $target['label'] . ': Die Datei verschwand während der Prüfung.',
                    CLEANUP_EXIT_DATA
                );
            }
            $lockedFiles[] = $locked;
        }
        foreach ($targets as $target) {
            $locked = cleanup_open_locked($target);
            if ($locked === null) {
                $missing++;
                continue;
            }
            $lockedFiles[] = $locked;
        }
        $monthBytes = 0;
        foreach ($lockedFiles as $locked) {
            if ($locked['target']['kind'] === 'month') {
                $monthBytes += (int) ($locked['stat']['size'] ?? 0);
            }
        }
        if ($monthBytes > CLEANUP_MAX_MONTH_TOTAL_BYTES) {
            throw new CleanupFailure(
                'Monatsdateien: Die Gesamtgröße überschreitet die sichere Grenze.',
                CLEANUP_EXIT_DATA
            );
        }
        foreach ($lockedFiles as &$locked) {
            $locked['migration'] = cleanup_validate_locked($locked, $now);
        }
        unset($locked);
        [$currentMonth, $previousMonth] = cleanup_month_window($now);
        $oldMonths = [];
        foreach ($lockedFiles as $locked) {
            if ($locked['target']['kind'] === 'month'
                && $locked['target']['month'] !== $currentMonth
                && $locked['target']['month'] !== $previousMonth) {
                $oldMonths[] = $locked;
            }
        }
        $cleaned += cleanup_remove_old_months($oldMonths);
        foreach ($lockedFiles as &$locked) {
            if (!in_array($locked['target']['kind'], ['rate', 'salt'], true)) {
                continue;
            }
            $mtime = (int) $locked['stat']['mtime'];
            $expired = $now - $mtime >= (int) $locked['target']['ttl'];
            $migration = $locked['migration'];
            if (!$expired && $migration === null) {
                continue;
            }
            if ($expired && $locked['target']['kind'] === 'salt') {
                cleanup_unlink_salt($locked);
            } else {
                cleanup_write_locked($locked, $expired ? '{}' : $migration);
            }
            $cleaned++;
        }
    } finally {
        cleanup_close_all($lockedFiles);
    }
    $checked = count($targets) + count($monthTargets ?? []) + 1;
    fwrite(STDOUT, 'Privatzustand: ' . $checked . ' geprüft, '
        . $cleaned . ' bereinigt, ' . $missing . " nicht vorhanden.\n");
    return 0;
}

if (realpath((string) ($_SERVER['SCRIPT_FILENAME'] ?? '')) === realpath(__FILE__)) {
    try {
        exit(cleanup_main());
    } catch (CleanupFailure $problem) {
        fwrite(STDERR, 'Privatzustand: ' . $problem->getMessage() . "\n");
        exit($problem->exitCode);
    } catch (Throwable $problem) {
        fwrite(STDERR, "Privatzustand: interner Bereinigungsfehler.\n");
        exit(CLEANUP_EXIT_IO);
    }
}
