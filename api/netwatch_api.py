#!/usr/bin/env python3
"""NetWatch API - usando apenas stdlib (sem Flask)"""

import json, os, sys
from datetime import datetime, timedelta
import pytz
from collections import defaultdict, Counter
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

BRAZIL_TZ = pytz.timezone('America/Sao_Paulo')
DATA_DIR = "/var/log/netwatch"

class NetWatchHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/api/netwatch/stats' or parsed.path == '/mikrotik-stats':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            data = get_stats()
            self.wfile.write(json.dumps(data).encode('utf-8'))
        elif parsed.path == '/api/netwatch/alerts':
            query = parse_qs(parsed.query)
            limit = int(query.get('limit', ['50'])[0])
            alerts = load_alerts(limit)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(alerts).encode('utf-8'))
        elif parsed.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'ok'}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found')

    def log_message(self, format, *args):
        # Silenciar logs do servidor
        return

def load_alerts(limit=50):
    alert_dir = f"{DATA_DIR}/alerts"
    alerts = []
    if not os.path.exists(alert_dir):
        return []
    files = sorted([f for f in os.listdir(alert_dir) if f.endswith('.json')], reverse=True)
    for fname in files:
        try:
            with open(f"{alert_dir}/{fname}") as f:
                for line in f:
                    try:
                        alerts.append(json.loads(line))
                    except:
                        continue
            if len(alerts) >= limit:
                break
        except:
            continue
    # Ordenar por severidade
    alerts.sort(key=lambda x: x.get('severity', 0), reverse=True)
    return alerts[:limit]

def load_raw_stats(hours=24):
    stats = {'mikrotik': 0, 'squid': 0, 'unifi': 0, 'zabbix': 0}
    cutoff = datetime.now(BRAZIL_TZ) - timedelta(hours=hours)
    for source in stats:
        raw_dir = f"{DATA_DIR}/raw/{source}"
        if not os.path.exists(raw_dir):
            continue
        for fname in os.listdir(raw_dir):
            if not fname.endswith('.log'):
                continue
            try:
                file_date = datetime.strptime(fname.replace('.log', ''), '%Y-%m-%d')
                file_date = BRAZIL_TZ.localize(file_date)
                if file_date.date() < cutoff.date():
                    continue
            except:
                continue
            try:
                with open(f"{raw_dir}/{fname}") as f:
                    stats[source] += sum(1 for _ in f)
            except:
                continue
    return stats

def get_stats():
    alerts = load_alerts(100)
    raw_stats = load_raw_stats(24)
    sources = set(a['source'] for a in alerts if 'source' in a)
    topics = {s: sum(1 for a in alerts if a.get('source') == s) for s in sources}
    total_logs = sum(raw_stats.values())
    ip_counter = Counter(a.get('ip') for a in alerts if 'ip' in a)
    top_ips = ip_counter.most_common(5)
    sev_counter = Counter(a.get('severity', 0) for a in alerts)
    return {
        'generated_at': datetime.now(BRAZIL_TZ).isoformat(),
        'total_logs_24h': total_logs,
        'alerts_count': len(alerts),
        'sources_count': len(sources),
        'topics': topics,
        'raw_by_source': raw_stats,
        'top_ips': [{'ip': ip, 'count': c} for ip, c in top_ips],
        'severity_distribution': dict(sev_counter),
        'recent_alerts': alerts[:20]
    }

def run_server(port=5001):
    server = HTTPServer(('0.0.0.0', port), NetWatchHandler)
    print(f"🚀 NetWatch API rodando em http://0.0.0.0:{port}")
    print(f"📊 Endpoint: /api/netwatch/stats")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Servidor parado")
        sys.exit(0)

if __name__ == '__main__':
    run_server()
