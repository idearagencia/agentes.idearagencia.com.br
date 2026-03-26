<?php
header('Content-Type: application/json');
$zbx_url = 'https://zabbix.idearagencia.com.br/zabbix/api_jsonrpc.php';
$api_token = '44130c8aad294b84a41c31926a5fb85545f8a816265b4d35d2ec901ff5217315';

$payload = json_encode([
    'jsonrpc' => '2.0',
    'method' => 'host.get',
    'params' => [
        'output' => ['hostid', 'name']
    ],
    'auth' => $api_token,
    'id' => 1
]);

$ch = curl_init($zbx_url);
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_POST => true,
    CURLOPT_POSTFIELDS => $payload,
    CURLOPT_HTTPHEADER => [
        'Content-Type: application/json',
        'Authorization: Bearer ' . $api_token
    ],
    CURLOPT_SSL_VERIFYHOST => 0,
    CURLOPT_SSL_VERIFYPEER => 0
]);

$response = curl_exec($ch);
curl_close($ch);

$data = json_decode($response, true);
echo json_encode($data['result'] ?? ['error' => 'no result', 'raw' => $response], JSON_PRETTY_PRINT);
