<?php
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *'); // ajuste depois se necessário

// Executa o script como usuário dashboard
$cmd = 'sudo -u dashboard /usr/local/lib/dashboard/server-stats.sh 2>&1';
exec($cmd, $output, $return_var);

if ($return_var !== 0) {
    http_response_code(500);
    echo json_encode(['error' => 'Failed to collect stats', 'details' => implode("\n", $output)]);
    exit;
}

echo implode("\n", $output);
