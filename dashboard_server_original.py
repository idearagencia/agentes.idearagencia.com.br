#!/usr/bin/env python3
"""
Dashboard server for Squid and MikroTik analytics
"""

import os
import re
import json
import subprocess
import pytz
import time
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.parse

BRAZIL_TZ = pytz.timezone('America/Sao_Paulo')
LOG_DIR = '/var/www/agentes.idearagencia.com.br/logs/squid'
MIKROTIK_JSON = '/var/www/agentes.idearagencia.com.br/mikrotik-analytics.json'

# Cache para métricas do proxy (evitar SSH repetitivo)
PROXY_METRICS_CACHE = {
    'data': None,
    'timestamp': None,
    'cache_duration': 300  # segundos (5 minutos)
}

class DashboardHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/':
            self.path = '/dashboard.html'
            return super().do_GET()
        elif parsed.path == '/squid-dashboard.html':
            self.path = '/squid-dashboard.html'
            return super().do_GET()
        elif parsed.path == '/mikrotik-analytics.html':
            self.path = '/mikrotik-analytics.html'
            return super().do_GET()
        elif parsed.path == '/squid-stats':
            self.handle_squid_stats()
            return
        elif parsed.path == '/squid-alerts':
            self.handle_squid_alerts()
            return
        elif parsed.path == '/mikrotik-stats':
            self.handle_mikrotik_stats()
            return
        elif parsed.path == '/proxy-metrics':
            self.handle_proxy_metrics()
            return
        return super().do_GET()

    def handle_squid_stats(self):
        JSON_PATH = os.path.join(LOG_DIR, 'squid-stats.json')
        try:
            if not os.path.exists(JSON_PATH):
                raise Exception("Arquivo squid-stats.json não encontrado")
            
            with open(JSON_PATH, 'r', encoding='utf-8') as f:
                stats = json.load(f)
            
            # Adicionar last_analyzed baseado no mtime do JSON
            file_mtime = os.path.getmtime(JSON_PATH)
            file_dt_utc = datetime.fromtimestamp(file_mtime, tz=timezone.utc)
            stats['last_analyzed'] = file_dt_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
            
            # Garantir campos padrão e mapear campos com sufixo _24h para compatibilidade
            if 'unique_users' not in stats and 'unique_users_24h' in stats:
                stats['unique_users'] = stats['unique_users_24h']
            if 'unique_domains' not in stats and 'unique_domains_24h' in stats:
                stats['unique_domains'] = stats['unique_domains_24h']
            if 'top_domains' not in stats and 'top_domains_24h' in stats:
                stats['top_domains'] = stats['top_domains_24h']
            if 'top_users_bytes' not in stats and 'top_users_bytes_24h' in stats:
                stats['top_users_bytes'] = stats['top_users_bytes_24h']
            if 'auth_407_by_ip' not in stats and 'top_407_by_ip' in stats:
                stats['auth_407_by_ip'] = stats['top_407_by_ip']
            
            defaults = {
                'total_requests': 0,
                'status_4xx': 0,
                'status_5xx': 0,
                'unique_users': 0,
                'unique_domains': 0,
                'top_domains': {},
                'top_users_bytes': [],
                'auth_407_by_ip': {},
                'suspicious': [],
                'errors_5xx': None,
                'req_per_sec_avg': None
            }
            for k, v in defaults.items():
                if k not in stats:
                    stats[k] = v
            
            # Gerar recomendações
            recommendations = []
            if stats['total_requests'] > 0:
                error_rate_4xx = (stats['status_4xx'] / stats['total_requests']) * 100
                if error_rate_4xx > 50:
                    recommendations.append({'priority': 'high', 'text': f'Taxa de erros 4xx extremamente alta ({error_rate_4xx:.1f}%). Verifique ACLs e regras de autenticação.'})
                elif error_rate_4xx > 20:
                    recommendations.append({'priority': 'medium', 'text': f'Taxa de erros 4xx elevada ({error_rate_4xx:.1f}%). Revise configurações de acesso e políticas.'})
            
            if stats['auth_407_by_ip']:
                top_407 = sorted(stats['auth_407_by_ip'].items(), key=lambda x: x[1], reverse=True)[:3]
                for ip, count in top_407:
                    if count > 100000:
                        recommendations.append({'priority': 'high', 'text': f'IP {ip} com {count:,} falhas de autenticação 407. Investigar possíveis misconfigurações ou ataque.'})
                    elif count > 10000:
                        recommendations.append({'priority': 'medium', 'text': f'IP {ip} com {count:,} falhas 407. Monitorar comportamento.'})
            
            if stats['suspicious']:
                recommendations.append({'priority': 'high', 'text': f'{len(stats["suspicious"])} domínios suspeitos detectados. Analisar tráfego para possíveis ameaças.'})
            
            if stats['top_domains']:
                top_domain, top_count = list(stats['top_domains'].items())[0]
                dominance = (top_count / stats['total_requests']) * 100 if stats['total_requests'] > 0 else 0
                if dominance > 50:
                    recommendations.append({'priority': 'info', 'text': f'Domínio {top_domain} concentra {dominance:.1f}% do tráfego. Verificar se é esperado.'})
            
            if stats['status_5xx'] > 100:
                recommendations.append({'priority': 'high', 'text': f'{stats["status_5xx"]:,} erros 5xx nas últimas 4h. Investigar servidores backend ou configuração.'})
            
            if stats.get('cache_hit_ratio_24h') is not None:
                hit_ratio = stats['cache_hit_ratio_24h'] * 100
                if hit_ratio < 30:
                    recommendations.append({'priority': 'medium', 'text': f'Cache hit ratio baixo ({hit_ratio:.1f}%). Aumentar memória cache ou ajustar objetos.'})
            
            stats['recommendations'] = recommendations

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(stats).encode())
        except Exception as e:
            self.send_error(500, str(e))

    def handle_squid_alerts(self):
        ALERT_DIR = LOG_DIR
        try:
            files = [f for f in os.listdir(ALERT_DIR) if f.startswith('squid_alert_') and f.endswith('.md')]
            files.sort(reverse=True)
            alerts = []
            for f in files[:30]:
                path = os.path.join(ALERT_DIR, f)
                try:
                    with open(path, 'r', encoding='utf-8') as fh:
                        content = fh.read()
                    m = re.search(r'\*\*Alertas detectados:\*\*(.*?)(\*\*Recomendações:|\*)', content, re.S)
                    if m:
                        alert_block = m.group(1).strip()
                        alert_lines = [line.strip().lstrip('-* ') for line in alert_block.split('\n') if line.strip().startswith('-') or line.strip().startswith('*')]
                        alerts.extend(alert_lines[:10])
                except:
                    pass
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(alerts[:50]).encode())
        except Exception as e:
            self.send_error(500, str(e))

    def handle_mikrotik_stats(self):
        MIKROTIK_JSON = '/var/www/agentes.idearagencia.com.br/logs/mikrotik/mikrotik-stats.json'
        try:
            if not os.path.exists(MIKROTIK_JSON):
                stats = {
                    "status": "offline",
                    "generated_at": None,
                    "router_uptime": "N/A",
                    "cpu_load": 0,
                    "memory_free_mb": 0,
                    "memory_total_mb": 0,
                    "interfaces_total": 0,
                    "interfaces_active": 0,
                    "interfaces_list": [],
                    "top_rx": [],
                    "top_tx": [],
                    "ip_addresses_total": 0,
                    "ip_addresses_list": [],
                    "dhcp_leases_total": 0,
                    "dhcp_leases_list": [],
                    "firewall_total_rules": 0,
                    "firewall_rules_sample": [],
                    "errors_last_hour_total": 0,
                    "errors_recent": [],
                    "alerts": []
                }
            else:
                with open(MIKROTIK_JSON, 'r', encoding='utf-8') as f:
                    stats = json.load(f)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(stats).encode())
        except Exception as e:
            self.send_error(500, str(e))

    def handle_proxy_metrics(self):
        global PROXY_METRICS_CACHE
        
        # Verificar cache primeiro
        now = time.time()
        if (PROXY_METRICS_CACHE['data'] is not None and 
            PROXY_METRICS_CACHE['timestamp'] is not None and
            now - PROXY_METRICS_CACHE['timestamp'] < PROXY_METRICS_CACHE['cache_duration']):
            # Retornar dados em cache
            metrics = PROXY_METRICS_CACHE['data'].copy()
            metrics['cached'] = True
            metrics['cache_age_seconds'] = int(now - PROXY_METRICS_CACHE['timestamp'])
        else:
            # Buscar dados frescos via SSH
            PROXY_IP = '172.16.1.9'
            PROXY_USER = 'openclaw'
            SSH_KEY = '/var/lib/openclaw/.ssh/id_ed25519'
            
            try:
                ping_cmd = f"ping -c 1 -W 2 {PROXY_IP}"
                ping_result = subprocess.run(ping_cmd, shell=True, capture_output=True, text=True, timeout=5)
                is_reachable = ping_result.returncode == 0
            except:
                is_reachable = False
            
            metrics = {}
            if is_reachable:
                try:
                    ssh_cmd = f"ssh -i {SSH_KEY} -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o BatchMode=yes -o PasswordAuthentication=no {PROXY_USER}@{PROXY_IP} 'python3 /tmp/get_proxy_metrics.py'"
                    result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True, timeout=20)
                    if result.returncode == 0:
                        try:
                            metrics = json.loads(result.stdout.strip())
                            metrics['status'] = 'online'
                        except:
                            metrics = {'error': 'JSON parse error', 'status': 'offline'}
                    else:
                        metrics = {'error': f'SSH failed: {result.stderr.strip()}', 'status': 'offline'}
                except:
                    metrics = {'status': 'offline', 'error': 'SSH exception'}
            else:
                metrics = {'status': 'offline', 'error': 'Host unreachable'}
            
            metrics['timestamp'] = datetime.now(BRAZIL_TZ).isoformat()
            metrics['cached'] = False
            
            # Salvar no cache
            PROXY_METRICS_CACHE['data'] = metrics.copy()
            PROXY_METRICS_CACHE['timestamp'] = time.time()
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(metrics).encode())

if __name__ == '__main__':
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    server = HTTPServer(('0.0.0.0', port), DashboardHandler)
    print(f"Dashboard server running on port {port}")
    server.serve_forever()
