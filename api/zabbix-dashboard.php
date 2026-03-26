<?php
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');

$zbx_url = 'https://zabbix.idearagencia.com.br/zabbix/api_jsonrpc.php';
$api_token = '44130c8aad294b84a41c31926a5fb85545f8a816265b4d35d2ec901ff5217315';

function zbx_request($url, $method, $params = []) {
    global $api_token;
    $payload = json_encode(['jsonrpc'=>'2.0','method'=>$method,'params'=>$params,'id'=>1]);
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER=>true,
        CURLOPT_POST=>true,
        CURLOPT_POSTFIELDS=>$payload,
        CURLOPT_HTTPHEADER=>['Content-Type: application/json','Authorization: Bearer '.$api_token],
        CURLOPT_SSL_VERIFYHOST=>0,
        CURLOPT_SSL_VERIFYPEER=>0,
        CURLOPT_TIMEOUT=>10
    ]);
    $response = curl_exec($ch);
    $httpcode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    if ($httpcode !== 200) return ['error'=>"HTTP $httpcode"];
    $data = json_decode($response, true);
    if (isset($data['error'])) return ['error'=>$data['error']['message']];
    return $data['result'] ?? [];
}

$hosts_raw = zbx_request($zbx_url, 'host.get', ['output'=>['hostid','name','status','lastaccess'],'sortfield'=>'name']);
$triggers_raw = zbx_request($zbx_url, 'trigger.get', ['output'=>['triggerid','value','clock'],'selectHosts'=>['hostid'],'filter'=>['value'=>1]]);

$hosts_with_problems = [];
$trigger_times = [];

if (!isset($triggers_raw['error']) && is_array($triggers_raw)) {
    foreach ($triggers_raw as $t) {
        if (isset($t['hosts'])) {
            foreach ($t['hosts'] as $h) {
                $hosts_with_problems[] = $h['hostid'];
                $hid = $h['hostid'];
                if (!isset($trigger_times[$hid]) || $t['clock'] > $trigger_times[$hid]) {
                    $trigger_times[$hid] = $t['clock'];
                }
            }
        }
    }
    $hosts_with_problems = array_unique($hosts_with_problems);
}

$hosts = []; $online = 0; $offline = 0;
if (!isset($hosts_raw['error']) && is_array($hosts_raw)) {
    foreach ($hosts_raw as $h) {
        $is_online = ($h['status'] == '0') && !in_array($h['hostid'], $hosts_with_problems);
        $down_since = null;
        if (!$is_online) {
            if (isset($trigger_times[$h['hostid']])) {
                $down_since = (int)$trigger_times[$h['hostid']];
            } elseif (!empty($h['lastaccess'])) {
                $down_since = (int)$h['lastaccess'];
            } else {
                // fallback para teste
                $down_since = time() - 3600;
            }
        }
        $hosts[] = [
            'name' => $h['name'],
            'status' => $is_online ? 'online' : 'offline',
            'down_since' => $down_since
        ];
        if ($is_online) $online++; else $offline++;
    }
}

$mk = @shell_exec("sudo -u dashboard /usr/local/lib/dashboard/mikrotik-stats.sh 2>&1");
$mk_data = json_decode($mk, true);
if (!$mk_data || isset($mk_data['error'])) {
    $mk_data = [
        'metrics'=>['dhcp_total'=>0,'unknown_giaddr'=>0,'winbox_denied'=>0],
        'top_macs'=>[],'last_errors'=>[]
    ];
}

echo json_encode([
    'timestamp'=>time(),
    'zabbix'=>['hosts'=>$hosts,'summary'=>['total'=>count($hosts),'online'=>$online,'offline'=>$offline]],
    'mikrotik'=>$mk_data
], JSON_PRETTY_PRINT);
