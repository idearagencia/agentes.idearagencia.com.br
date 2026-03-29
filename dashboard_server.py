#!/usr/bin/env python3
"""
Dashboard server with authentication - final
Serve estáticos de /var/www/agentes.idearagencia.com.br
Injeção de header de usuário logado em páginas HTML APENAS
"""

import os
import re
import json
import subprocess
import pytz
import threading
import sys
import io  # <-- adicionado
from pathlib import Path
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.parse
import mimetypes

from auth import get_auth_manager, generate_session_cookie, parse_session_cookie, SESSION_COOKIE_NAME

BRAZIL_TZ = pytz.timezone('America/Sao_Paulo')

# Diretório base para arquivos estáticos (HTML, CSS, JS)
WEB_ROOT = Path('/var/www/agentes.idearagencia.com.br')

# Diretórios de dados (logs, eventos)
LOG_DIR = '/root/.openclaw/workspace/logs'
UNIFI_DATA_DIR = '/root/.openclaw/workspace/unifi_data'
REPORTS_DIR = '/var/www/agentes.idearagencia.com.br/reports'
INFRA_EVENTS_DIR = Path('/var/www/agentes.idearagencia.com.br/infra_events')
INFRA_EVENTS_DIR.mkdir(parents=True, exist_ok=True)

infra_events = []
infra_events_lock = threading.Lock()
auth_manager = get_auth_manager()


class DashboardHandler(SimpleHTTPRequestHandler):
    """Handler com autenticação, servindo arquivos de WEB_ROOT e injetando header do usuário"""

    def translate_path(self, path):
        path = path.split('?', 1)[0]
        path = path.split('#', 1)[0]
        path = urllib.parse.unquote(path)
        if path == '/' or path == '':
            path = '/index.html'
        elif not path.startswith('/api/') and not path.startswith('/infra-') and not path.startswith('/reports'):
            if not path.startswith('/'):
                path = '/' + path
        full_path = WEB_ROOT / path.lstrip('/')
        return str(full_path)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        public = ['/login.html', '/api/login', '/api/logout', '/favicon.ico']
        if parsed.path in public:
            return self.handle_public(parsed)

        session_token = self.get_session_token()
        user = auth_manager.validate_session(session_token) if session_token else None

        if not user:
            # Redireciona para login com return-to
            self.send_response(302)
            self.send_header('Location', f'/login.html?redirect_to={urllib.parse.quote(parsed.path)}')
            self.end_headers()
            return

        self.current_user = user

        if parsed.path == '/':
            self.path = '/index.html'
            return super().do_GET()
        elif parsed.path in ['/alerts', '/alert', '/squid-dashboard.html', '/squid-alerts',
                            '/squid-stats', '/proxy-metrics', '/infrastructure-events',
                            '/unifi-dashboard.html', '/unifi-stats', '/mikrotik-stats',
                            '/mikrotik-logs', '/reports']:
            return self.dispatch_protected(parsed)
        else:
            self.path = parsed.path
            return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b'{}'

        try:
            data = json.loads(post_data.decode('utf-8'))
        except:
            data = {}

        if parsed.path == '/api/login':
            self.api_login(data)
        elif parsed.path == '/api/logout':
            self.api_logout()
        elif parsed.path == '/infra-event':
            self.handle_infra_event(data)
        else:
            self.send_error(404)

    def handle_public(self, parsed):
        if parsed.path == '/login.html':
            self.path = '/login.html'
            return super().do_GET()
        elif parsed.path == '/api/login':
            self.send_error(405)
        elif parsed.path == '/api/logout':
            self.api_logout()
        else:
            self.send_error(404)

    def get_session_token(self):
        cookie = self.headers.get('Cookie', '')
        for c in cookie.split(';'):
            c = c.strip()
            if c.startswith(f'{SESSION_COOKIE_NAME}='):
                return c.split('=', 1)[1]
        return None

    def api_login(self, credentials):
        username = credentials.get('username', '').strip()
        password = credentials.get('password', '')
        if not username or not password:
            self.send_error(400, json.dumps({'success': False, 'message': 'Credenciais obrigatórias'}))
            return

        if auth_manager.verify_password(username, password):
            token, expires = auth_manager.create_session(username, self.client_address[0])
            cookie = generate_session_cookie(token)
            user_info = auth_manager.get_user_info(username)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Set-Cookie', cookie)
            self.end_headers()
            self.wfile.write(json.dumps({
                'success': True,
                'user': user_info,
                'expires_at': expires.isoformat()
            }).encode())
        else:
            self.send_error(401, json.dumps({'success': False, 'message': 'Senha inválida'}))

    def api_logout(self):
        token = self.get_session_token()
        if token:
            auth_manager.invalidate_session(token)

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Set-Cookie', f'{SESSION_COOKIE_NAME}=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT')
        self.end_headers()
        self.wfile.write(json.dumps({'success': True}).encode())

    def dispatch_protected(self, parsed):
        path = parsed.path
        if path == '/alerts':
            return self.handle_alerts()
        if path == '/alert':
            return self.handle_alert(parsed.query)
        if path == '/squid-alerts':
            return self.handle_squid_alerts()
        if path == '/squid-stats':
            return self.handle_squid_stats()
        if path == '/squid-dashboard.html':
            self.path = '/squid-dashboard.html'
            return super().do_GET()
        if path == '/proxy-metrics':
            return self.handle_proxy_metrics()
        if path == '/infrastructure-events':
            return self.handle_infrastructure_events()
        if path == '/unifi-dashboard.html':
            self.path = '/unifi-dashboard.html'
            return super().do_GET()
        if path == '/unifi-stats':
            return self.handle_unifi_stats()
        if path == '/mikrotik-stats':
            return self.handle_mikrotik_stats()
        if path == '/mikrotik-logs':
            return self.handle_mikrotik_logs()
        if path == '/reports':
            return self.handle_reports_list()
        self.send_error(404)

    # ============ HANDLERS ============

    def handle_alerts(self):
        files = [f for f in os.listdir(LOG_DIR) if f.startswith('mikrotik_alert_') and f.endswith('.md')]
        files.sort(reverse=True)
        self.send_json(files)

    def handle_alert(self, query):
        params = urllib.parse.parse_qs(query)
        file = params.get('file', [None])[0]
        if not file:
            self.send_error(400, 'File required')
            return
        filepath = os.path.join(LOG_DIR, file)
        if not os.path.exists(filepath):
            self.send_error(404, 'Not found')
            return
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(content.encode())
        except Exception as e:
            self.send_error(500, str(e))

    def handle_squid_alerts(self):
        try:
            files = [f for f in os.listdir(LOG_DIR) if f.startswith('squid_alert_') and f.endswith('.md')]
            files.sort(reverse=True)
            alerts = []
            for f in files[:30]:
                path = os.path.join(LOG_DIR, f)
                try:
                    with open(path, 'r', encoding='utf-8') as fh:
                        content = fh.read()
                    m = re.search(r'\*\*Alertas detectados:\*\*(.*?)(\*\*Recomendações:|\*)', content, re.S)
                    if m:
                        block = m.group(1).strip()
                        alert_lines = [line.strip().lstrip('-* ') for line in block.split('\n') if line.strip().startswith(('-', '*'))]
                        alerts.extend(alert_lines[:10])
                except:
                    pass
            self.send_json(alerts[:50])
        except Exception as e:
            self.send_error(500, str(e))

    def handle_squid_stats(self):
        """Retorna estatísticas do Squid a partir do JSON gerado pelo generate_squid_stats.py"""
        try:
            json_path = '/var/www/agentes.idearagencia.com.br/logs/squid/squid-stats.json'
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.send_json(data)
            else:
                # Fallback: tentar ler arquivos .md antigos (compatibilidade)
                files = [f for f in os.listdir(LOG_DIR) if f.startswith('squid_alert_') and f.endswith('.md')]
                files.sort(reverse=True)
                stats = {'total_requests':0, 'status_4xx':0, 'status_5xx':0, 'unique_users':0,
                        'top_domains':{}, 'top_users_bytes':[], 'auth_407_by_ip':{}}

                if files:
                    files_with_mtime = [(f, os.path.getmtime(os.path.join(LOG_DIR, f))) for f in files]
                    files_with_mtime.sort(key=lambda x: x[1], reverse=True)
                    latest = os.path.join(LOG_DIR, files_with_mtime[0][0])
                    stats['last_analyzed'] = datetime.fromtimestamp(files_with_mtime[0][1], tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

                    with open(latest, 'r', encoding='utf-8') as f:
                        content = f.read()

                    def get_num(pat):
                        m = re.search(pat, content)
                        if m:
                            try: return int(m.group(1).replace(',','').replace('.',''))
                            except: return 0
                        return 0

                    stats['total_requests'] = get_num(r'Requisições\s*\(24h\):\s*([\d,.]+)')
                    stats['status_4xx'] = get_num(r'Erros 4xx\s*\(24h\):\s*([\d,.]+)')
                    stats['status_5xx'] = get_num(r'Erros 5xx\s*\(24h\):\s*([\d,.]+)')
                    stats['unique_users'] = get_num(r'Usuários únicos\s*\(24h\):\s*([\d,.]+)')
                    stats['unique_domains'] = get_num(r'Domínios únicos\s*\(24h\):\s*([\d,.]+)')

                    m = re.search(r'Top domínios(?:\s*\(24h\))?:\s*(\{.*?\})', content)
                    if m:
                        try: stats['top_domains'] = json.loads(m.group(1))
                        except: pass

                    m = re.search(r'Top usuários por tráfego:\s*(.+)', content)
                    if m:
                        entries = re.findall(r'([^,(]+?)\s*\(([\d.]+)\s*MB?\)', m.group(1))
                        stats['top_users_bytes'] = [(u.strip(), float(b)*1e6) for u,b in entries]

                    stats['auth_407_by_ip'] = {}
                    for ip, cnt in re.findall(r'Alto volume de 407: IP ([\d.]+) com ([\d,.]+) falhas', content):
                        stats['auth_407_by_ip'][ip] = int(cnt.replace(',','').replace('.',''))

                    stats['suspicious'] = []
                    for domain, reason in re.findall(r'Domínio suspeito:\s*([^\n]+?)\s*\(([^)]+)\)', content):
                        stats['suspicious'].append({'domain': domain.strip(), 'reason': reason.strip()})

                self.send_json(stats)
        except Exception as e:
            self.send_error(500, str(e))

    def handle_proxy_metrics(self):
        PROXY_IP = '172.16.1.9'
        PROXY_USER = 'openclaw'
        SSH_KEY = '/var/lib/openclaw/.ssh/id_ed25519'
        metrics = {}
        try:
            ssh_cmd = f"ssh -i {SSH_KEY} -o ConnectTimeout=5 -o StrictHostKeyChecking=no {PROXY_USER}@{PROXY_IP} 'python3 /tmp/get_proxy_metrics.py'"
            result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True, timeout=20)
            if result.returncode == 0:
                try:
                    metrics = json.loads(result.stdout.strip())
                    metrics['status'] = 'online'
                    metrics['timestamp'] = datetime.now(BRAZIL_TZ).isoformat()
                    self.send_json(metrics)
                    return
                except Exception as e:
                    metrics = {'error': f'JSON parse error: {e}', 'status': 'degraded'}
            else:
                metrics = {'error': f'SSH falhou: {result.stderr.strip()}', 'status': 'degraded'}
        except Exception as e:
            metrics = {'error': str(e), 'status': 'degraded'}

        # Se SSH falhou, testar ping para ver se host está reachable
        try:
            ping_cmd = f"ping -c 2 -W 2 {PROXY_IP}"
            ping_result = subprocess.run(ping_cmd, shell=True, capture_output=True, text=True, timeout=10)
            if ping_result.returncode == 0:
                metrics['status'] = 'online'  # Host vivo, assumimos serviços online
                metrics['ping_ok'] = True
            else:
                metrics['status'] = 'offline'
                metrics['ping_ok'] = False
        except Exception as e:
            metrics['status'] = 'offline'
            metrics['ping_error'] = str(e)

        metrics['timestamp'] = datetime.now(BRAZIL_TZ).isoformat()
        self.send_json(metrics)

    def handle_infrastructure_events(self):
        with infra_events_lock:
            recent = list(reversed(infra_events[-100:]))
        self.send_json(recent)

    def handle_infra_event(self, event):
        required = ['source', 'type', 'timestamp', 'data']
        if not all(k in event for k in required):
            self.send_error(400, json.dumps({'success': False, 'message': 'Evento inválido'}))
            return

        event_file = INFRA_EVENTS_DIR / f"{event['source']}_{datetime.now(BRAZIL_TZ).strftime('%Y%m%d_%H%M%S')}_{event['type']}.json"
        try:
            with open(event_file, 'w') as f:
                json.dump(event, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[!] Erro salvando evento: {e}")

        with infra_events_lock:
            infra_events.append(event)
            if len(infra_events) > 1000:
                infra_events.pop(0)

        self.send_json({'status': 'ok', 'received': True})

    def handle_unifi_stats(self):
        try:
            files = [f for f in os.listdir(UNIFI_DATA_DIR) if f.startswith('unifi_snapshot_') and f.endswith('.json')]
            files.sort(reverse=True)
            if not files:
                self.send_error(404, 'No data')
                return
            with open(os.path.join(UNIFI_DATA_DIR, files[0]), 'r') as f:
                data = json.load(f)

            devices = data.get('devices', [])
            aps = [d for d in devices if d.get('type') in ['uap', 'uap']]
            stats = {
                'timestamp': data.get('timestamp'),
                'total_aps': len(aps),
                'aps_online': len(aps),
                'aps_offline': 0,
                'total_switches': len([d for d in devices if d.get('type') == 'usw']),
                'total_ssids': len([s for s in data.get('ssids', []) if s.get('enabled', True)]),
                'active_clients_24h': len(data.get('clients', [])),
                'rogue_aps_total': len(data.get('rogue_aps', [])),
                'rogue_aps_2g': 0,
                'rogue_aps_5g': 0,
                'alerts_active': len(data.get('alerts', [])),
                'alerts_list': data.get('alerts', [])[:5]
            }
            self.send_json(stats)
        except Exception as e:
            self.send_error(500, str(e))

    def handle_mikrotik_stats(self):
        try:
            import glob
            pattern = os.path.join(LOG_DIR, 'mikrotik_alert_*.md')
            files = glob.glob(pattern)
            if not files:
                self.send_error(404, 'Nenhum alerta MikroTik disponível')
                return

            best_file = None
            best_total = 0
            best_content = ''
            best_mtime = 0

            for filepath in files:
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    total_match = re.search(r'Total de logs analisados:\s*([\d,.]+)', content)
                    total_logs = int(total_match.group(1).replace(',', '').replace('.', '')) if total_match else 0
                    file_mtime = os.path.getmtime(filepath)
                    if total_logs > best_total or (total_logs == best_total and file_mtime > best_mtime):
                        best_file = filepath
                        best_total = total_logs
                        best_content = content
                        best_mtime = file_mtime
                except:
                    continue

            if best_file is None:
                files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                best_file = files[0]
                with open(best_file, 'r') as f:
                    best_content = f.read()
                best_mtime = os.path.getmtime(best_file)

            last_analyzed = datetime.fromtimestamp(best_mtime, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

            topics = {}
            pos = best_content.find('Por tópico:')
            if pos != -1:
                start = best_content.find('{', pos)
                if start != -1:
                    depth = 0
                    for i in range(start, len(best_content)):
                        if best_content[i] == '{': depth += 1
                        elif best_content[i] == '}':
                            depth -= 1
                            if depth == 0:
                                try:
                                    topics = json.loads(best_content[start:i+1])
                                except:
                                    pass
                                break

            alerts = []
            alerts_section = re.search(r'Alertas detectados:(.*?)(?=\n\*{2,}|\Z)', best_content, re.DOTALL)
            if alerts_section:
                for line in alerts_section.group(1).strip().split('\n'):
                    line = line.strip()
                    if line.startswith('- '):
                        alerts.append(line[2:].strip())

            stats = {
                'timestamp': last_analyzed,
                'total_logs_24h': best_total,
                'topics': topics,
                'alerts_count': len(alerts),
                'top_alerts': alerts[:20],
                'sources_count': len(topics)
            }
            self.send_json(stats)
        except Exception as e:
            self.send_error(500, f'Erro MikroTik: {str(e)}')

    def handle_mikrotik_logs(self):
        try:
            files = [f for f in os.listdir(LOG_DIR) if f.startswith('mikrotik_alert_') and f.endswith('.md')]
            files.sort(reverse=True)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(files).encode())
        except Exception as e:
            self.send_error(500, str(e))

    def handle_reports_list(self):
        try:
            reports = []
            if os.path.exists(REPORTS_DIR):
                for filename in sorted(os.listdir(REPORTS_DIR)):
                    if filename.lower().endswith('.pdf'):
                        filepath = os.path.join(REPORTS_DIR, filename)
                        try:
                            stat = os.stat(filepath)
                            name_parts = filename[:-4].split('-', 1)
                            if len(name_parts) >= 2:
                                agent = name_parts[0]
                                title = name_parts[1].replace('-', ' ').title()
                            else:
                                agent = 'Desconhecido'
                                title = filename[:-4]
                            reports.append({
                                'filename': filename,
                                'agent': agent,
                                'title': title,
                                'size': stat.st_size,
                                'modified': datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                            })
                        except OSError:
                            continue
            self.send_json(reports)
        except Exception as e:
            self.send_error(500, str(e))

    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    # ============ INJEÇÃO DE HEADER LOGADO ============

    def send_head(self):
        """Sobrescreve para injetar header de usuário em páginas HTML APENAS"""
        path = self.translate_path(self.path)

        # Se for diretório, procurar por index.html
        if os.path.isdir(path):
            for index in ["index.html", "index.htm"]:
                index_path = os.path.join(path, index)
                if os.path.exists(index_path) and os.path.isfile(index_path):
                    path = index_path
                    break
            else:
                return super().send_head()

        if not os.path.exists(path) or not os.path.isfile(path):
            return super().send_head()

        # Se não houver current_user, servir normalmente
        if not hasattr(self, 'current_user'):
            return super().send_head()

        # Se não for HTML, servir normalmente (CSS, JS, imagens, etc.)
        if not path.endswith('.html'):
            return super().send_head()

        # Ler o arquivo HTML
        try:
            with open(path, 'rb') as f:
                content = f.read()
        except OSError:
            self.send_error(404, "File not found")
            return None

        # Determinar encoding
        try:
            html = content.decode('utf-8')
        except UnicodeDecodeError:
            html = content.decode('latin-1')

        # Injetar header de usuário
        user = self.current_user
        user_header = f'''<div id="user-header" style="padding: 6px 16px; font-family: Inter, sans-serif; height: 40px; margin-bottom: 8px; max-width: 1600px; margin: 0 auto; width: 100%; display: flex; justify-content: space-between; align-items: center;">
  <div style="color: #A5A5A5; font-weight: 500; font-size: 14px;">
    👋 Olá, <span style="color: #f4f4f4;">{user['full_name']}</span> <small style="color: #666;">({user['role']})</small>
  </div>
  <button onclick="fetch('/api/logout', {{method: 'POST'}}).then(() => window.location.href='/login.html')" 
          style="background: #EC1D3A; color: white; border: none; padding: 4px 12px; border-radius: 6px; cursor: pointer; font-weight: 500; font-size: 13px; height: 28px;">
    Sair
  </button>
</div>
'''

        body_pos = html.find('<body')
        # Encontrar <body e injetar logo após a abertura
        if body_pos != -1:
            tag_end = html.find('>', body_pos)
            if tag_end != -1:
                insert_pos = tag_end + 1
                html = html[:insert_pos] + user_header + html[insert_pos:]

        # Injetar footer antes do </body>
        footer = '''<footer style="max-width: 1600px; margin: 0 auto; padding: 24px 16px; text-align: center; color: #666; font-size: 13px; border-top: 1px solid #333; margin-top: 40px;">
  Sistema de Gestão de Agentes Inteligentes — <strong style="color: #00d4ff;">AgentOS</strong><br>
  Desenvolvido por <span style="color: #A5A5A5;">DiegoHacks</span> @ 2026
</footer>
'''
        body_close = html.rfind('</body>')
        if body_close != -1:
            html = html[:body_close] + footer + html[body_close:]

        # Retornar conteúdo modificado
        enc = sys.getfilesystemencoding()
        content = html.encode('utf-8')
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=%s" % enc)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        return io.BytesIO(content)


def run_server(host='0.0.0.0', port=8080):
    server = HTTPServer((host, port), DashboardHandler)
    print(f"[+] Dashboard server running at http://{host}:{port}")
    print(f"[+] Login: http://{host}:{port}/login.html")
    server.serve_forever()


if __name__ == '__main__':
    run_server()
