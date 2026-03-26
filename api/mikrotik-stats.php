<?php
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: https://agentes.idearagencia.com.br');

$cmd = 'sudo -u dashboard /usr/local/lib/dashboard/mikrotik-stats.sh 2>&1';
exec($cmd, $output, $ret);

if ($ret !== 0) {
    http_response_code(500);
    echo json_encode(['error' => 'Script failed', 'output' => $output]);
    exit;
}

echo implode("\n", $output);
