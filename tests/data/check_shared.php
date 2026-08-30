<?php
/**
 * Treiber für die Gegenprobe: eine Datei durch die PHP-Prüfung schicken.
 *
 * Wird von tests/test_shared_php.py gerufen. Er lädt die **echte**
 * website/api/shared_common.php und nicht einen Nachbau — ein Nachbau prüfte
 * den Nachbau. Die Befunde kommen als JSON heraus, damit Python sie Zeile für
 * Zeile mit denen des Kerns vergleichen kann.
 *
 *     php check_shared.php <datei>
 */

declare(strict_types=1);

require __DIR__ . '/../../website/api/shared_common.php';

if ($argc < 2) {
    fwrite(STDERR, "Aufruf: check_shared.php <datei>\n");
    exit(2);
}

$payload = file_get_contents($argv[1]);
if ($payload === false) {
    fwrite(STDERR, "Die Datei {$argv[1]} ließ sich nicht lesen.\n");
    exit(2);
}

try {
    $findings = shared_inspect($payload, shared_rules());
} catch (RuntimeException $error) {
    fwrite(STDERR, $error->getMessage() . "\n");
    exit(3);
}

echo json_encode($findings, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
