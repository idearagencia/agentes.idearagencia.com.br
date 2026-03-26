<?php
header('Content-Type: application/json');
$zbx_url = 'https://zabbix.idearagencia.com.br/zabbix/api_jsonrpc.php';
$api_token = '44130c8aad294b84a41c31926a5fb85545f8a816265b4d35d2ec901ff5217315';

function zbx_req($m, $p) {
    global $api_token, $zbx_url;
    $payload = json_encode(['jsonrpc'=>'2.0','method'=>$m,'params'=>$p,'auth'=>$api_token,'id'=>1]);
    $ch = curl_init($zbx_url);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER=>true,
        CURLOPT_POST=>true,
        CURLOPT_POSTFIELDS=>$payload,
        CURLOPT_HTTPHEADER=>['Content-Type: application/json','Authorization: Bearer '.$api_token],
        CURLOPT_SSL_VERIFYHOST=>0,
        CURLOPT_SSL_VERIFYPEER=>0,
        CURLOPT_TIMEOUT=>15
    ]);
    $r = curl_exec($ch);
    if (curl_errno($ch)) { $err = curl_error($ch); curl_close($ch); return ['error'=>$err]; }
    $http = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    if ($http !== 200) return ['error'=>"HTTP $http"];
    $d = json_decode($r, true);
    return $d['result'] ?? $d;
}

// 1. Todos os hosts
$hosts = zbx_req('host.get', ['output'=>['hostid','name'], 'sortfield'=>'name']);
if (isset($hosts['error'])) { echo json_encode($hosts); exit; }

// 2. Para cada host, buscar alguns itens (limitado para não sobrecarregar)
$result = [];
foreach ($hosts as $h) {
    $items = zbx_req('item.get', [
        'output'=>['itemid','key_','name','lastvalue','units'],
        'hostids'=>$h['hostid'],
        'filter'=>['key_'=>['system.cpu.util','vm.memory.size','vfs.fs.size']],
        'limit'=>20
    ]);
    $result[] = [
        'host' => $h['name'],
        'hostid' => $h['hostid'],
        'items' => $items
    ];
}

echo json_encode($result, JSON_PRETTY_PRINT);
