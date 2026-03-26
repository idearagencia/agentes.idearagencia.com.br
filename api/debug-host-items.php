<?php
header('Content-Type: application/json');
$zbx_url = 'https://zabbix.idearagencia.com.br/zabbix/api_jsonrpc.php';
$api_token = '44130c8aad294b84a41c31926a5fb85545f8a816265b4d35d2ec901ff5217315';
$hostname = 'srv857035';

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
        CURLOPT_TIMEOUT=>10
    ]);
    $r = curl_exec($ch);
    curl_close($ch);
    $d = json_decode($r, true);
    return $d['result'] ?? $d;
}

// 1. Buscar host ID
$hosts = zbx_req('host.get', ['output'=>['hostid','name'], 'filter'=>['host'=>$hostname]]);
if (!$hosts) { echo json_encode(['error'=>'Host not found']); exit; }
$hostid = $hosts[0]['hostid'];

// 2. Buscar itens do host
$items = zbx_req('item.get', [
    'output'=>['itemid','key_','name','lastvalue','units'],
    'hostids'=>$hostid,
    'sortfield'=>'name',
    'limit'=>200
]);

echo json_encode(['hostid'=>$hostid, 'items'=>$items], JSON_PRETTY_PRINT);
