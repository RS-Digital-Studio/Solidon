<?php
/** Gibt den Platz des signierenden, aktuell aktivierten Rechners frei. */

declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');
header('X-Content-Type-Options: nosniff');
header('Cache-Control: no-store');

require_once __DIR__ . '/activation_common.php';

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    activation_answer_error(new ActivationFailure('Nur POST.', 405, 'method_not_allowed'));
}
if (!function_exists('sodium_crypto_sign_verify_detached')
    || !extension_loaded('pdo_sqlite')) {
    activation_answer_error(new ActivationFailure(
        'Der Aktivierungsdienst ist auf diesem Server noch nicht vollständig eingerichtet.',
        503,
        'service_unavailable'
    ));
}
$length = (int) ($_SERVER['CONTENT_LENGTH'] ?? 0);
if ($length <= 0 || $length > 32768) {
    activation_answer_error(new ActivationFailure('Die Geräteabmeldung ist leer oder zu groß.'));
}
$raw = file_get_contents('php://input');
if ($raw === false) {
    activation_answer_error(new ActivationFailure('Die Geräteabmeldung ließ sich nicht lesen.'));
}
try {
    activation_deactivate(activation_deactivation_request($raw));
    echo json_encode(['ok' => true], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
} catch (ActivationFailure $problem) {
    activation_answer_error($problem);
}
