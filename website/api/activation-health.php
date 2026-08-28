<?php
/** Lesender Bereitschaftstest des Aktivierungsdienstes. */

declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');
header('X-Content-Type-Options: nosniff');
header('Cache-Control: no-store');

require_once __DIR__ . '/activation_common.php';

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'GET') {
    activation_answer_error(new ActivationFailure('Nur GET.', 405, 'method_not_allowed'));
}
if (!function_exists('sodium_crypto_sign_verify_detached')
    || !extension_loaded('pdo_sqlite')) {
    activation_answer_error(new ActivationFailure(
        'Der Aktivierungsdienst ist auf diesem Server noch nicht vollständig eingerichtet.',
        503,
        'service_unavailable'
    ));
}
try {
    activation_seed();
    $database = activation_database(false);
    $required = ['licences', 'activations', 'activation_attempts'];
    $tables = $database->query(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    )->fetchAll(PDO::FETCH_COLUMN);
    if (count(array_diff($required, $tables)) !== 0) {
        throw new ActivationFailure(
            'Der Aktivierungsdienst ist noch nicht vollständig eingerichtet.',
            503,
            'service_unavailable'
        );
    }
    echo json_encode(
        ['ok' => true, 'protocol' => ACTIVATION_DOCUMENT_FORMAT],
        JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES
    );
} catch (ActivationFailure $problem) {
    activation_answer_error($problem);
} catch (Throwable $problem) {
    activation_answer_error(new ActivationFailure(
        'Der Aktivierungsdienst ist vorübergehend nicht verfügbar.',
        503,
        'service_unavailable'
    ));
}
