<?php
/** Einmalige Online- und Offline-Ausstellung eines Geräte-Zertifikats. */

declare(strict_types=1);

require_once __DIR__ . '/activation_common.php';

header('Content-Type: application/json; charset=utf-8');
activation_security_headers();
try {
    activation_require_method('POST');
    activation_require_trusted_origin();
    $raw = activation_read_json_body();
    activation_consume_client_rate('issue', 30, 900);
    if (!function_exists('sodium_crypto_sign_verify_detached')
        || !extension_loaded('pdo_sqlite')) {
        throw new ActivationFailure(
            'Der Aktivierungsdienst ist auf diesem Server noch nicht vollständig eingerichtet.',
            503,
            'service_unavailable'
        );
    }
    echo activation_issue(activation_request($raw));
} catch (ActivationFailure $problem) {
    activation_answer_error($problem);
} catch (Throwable $problem) {
    error_log('Solidon activation internal error: ' . get_class($problem));
    activation_answer_error(new ActivationFailure(
        'Der Aktivierungsdienst ist vorübergehend nicht verfügbar. Bitte später erneut versuchen.',
        503,
        'service_unavailable'
    ));
}
