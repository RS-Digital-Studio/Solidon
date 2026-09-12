<?php
/**
 * In welcher Zeitzone Tage gezählt und angezeigt werden.
 *
 * Gespeichert wird UTC. count.php zieht hier die Tagesgrenze, stats.php zeigt in
 * derselben Zone an — eine Stelle, damit beide dieselbe bleiben. Bis zum
 * 06.09.2026 stand der Name in beiden Dateien, mit einem Kommentar, der auf die
 * jeweils andere verwies.
 */
declare(strict_types=1);

// Diese Datei liefert nur eine Konstante an ihre PHP-Aufrufer, keinen Endpunkt.
if (realpath((string) ($_SERVER['SCRIPT_FILENAME'] ?? '')) === __FILE__) {
    header('Cache-Control: no-store');
    header('X-Content-Type-Options: nosniff');
    header("Content-Security-Policy: default-src 'none'; frame-ancestors 'none'");
    http_response_code(404);
    exit;
}

const DAY_ZONE = 'Europe/Berlin';
