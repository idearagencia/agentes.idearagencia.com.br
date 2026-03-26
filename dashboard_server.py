#!/usr/bin/env python3
"""
Dashboard server for MikroTik and Squid alerts
Serves static dashboards + API endpoints
"""

import os
import re
import json
import subprocess
import pytz
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.parse

# FORCE TIMEZONE: America/Sao_Paulo (GMT-3)
BRAZIL_TZ = pytz.timezone('America/Sao_Paulo')

LOG_DIR = '/root/.openclaw/workspace/logs'
UNIFI_DATA_DIR = '/root/.openclaw/workspace/unifi_data'
REPORTS_DIR = '/var/www/agentes.idearagencia.com.br/reports'

class DashboardHandler(SimpleHTTPRequestHandler):
    def set_no_cache_headers(self):
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/':
            self.path = '/dashboard.html'
            return super().do_GET()
        elif parsed.path == '/alerts':
            self.handle_alerts()
            return
        elif parsed.path == '/alert':
            self.handle_alert(parsed.query)
            return
        elif parsed.path == '/squid-dashboard.html':
            self.path = '/squid-dashboard.html'
            return super().do_GET()
        elif parsed.path == '/squid-alerts':
            self.handle_squid_alerts()
            return
        elif parsed.path == '/squid-stats':
            self.handle_squid_stats()
            return
        elif parsed.path == '/squid-realtime':
            self.handle_squid_realtime()
            return
            self.handle_mikrotik_analytics()
            return
        elif parsed.path == '/proxy-metrics':
            self.handle_proxy_metrics()
            return
        return super().do_GET()

    def handle_alerts(self):
        try:
            files = [f for f in os.listdir(LOG_DIR) if f.startswith('mikrotik_alert_') and f.endswith('.md')]
            files.sort(reverse=True)
            self.send_response(200)
            self.set_no_cache_headers()
            self.set_no_cache_headers()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(files).encode())
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
            self.set_no_cache_headers()
            self.set_no_cache_headers()
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(alerts[:50]).encode())
        except Exception as e:
            self.send_error(500, str(e))


    def handle_squid_stats(self):
        ALERT_DIR = LOG_DIR
        # PRIORITIZAR dados reais se disponível (WebHacks)
        REALTIME_FILE = '/var/www/agentes.idearagencia.com.br/squid-realtime.json'
        if os.path.exists(REALTIME_FILE):
            try:
                with open(REALTIME_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.send_response(200)
                self.set_no_cache_headers()
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
                return
            except Exception:
                pass  # se erro, Cair para fallback (alertas)
        try:
            files = [f for f in os.listdir(ALERT_DIR) if f.startswith('squid_alert_') and f.endswith('.md')]
            files.sort(reverse=True)
            stats = {
                'total_requests': 0,
                'status_4xx': 0,
                'status_5xx': 0,
                'unique_users': 0,
                'top_domains': {},
                'top_users_bytes': [],
                'auth_407_by_ip': {}
            }
            if files:
                latest = os.path.join(ALERT_DIR, files[0])
                # Usar mtime do arquivo (UTC) para timestamp preciso
                file_mtime = os.path.getmtime(latest)
                # Criar datetime aware em UTC
                file_dt_utc = datetime.fromtimestamp(file_mtime, tz=timezone.utc)
                # Formatar como ISO com 'Z' (UTC)
                stats['last_analyzed'] = file_dt_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
                
                with open(latest, 'r', encoding='utf-8') as f:
                    content = f.read()

                def get_number(pattern):
                    m = re.search(pattern, content)
                    if m:
                        num = m.group(1).replace(',', '').replace('.', '')
                        try:
                            return int(num)
                        except:
                            return 0
                    return 0

                # Formato novo: "Requisições (1h): 0" ou "Requisições (última análise): X"
                stats['total_requests'] = get_number(r'Requisições\s*\(24h\):\s*([\d,.]+)')
                stats['status_4xx'] = get_number(r'Erros 4xx\s*\(24h\):\s*([\d,.]+)')
                stats['status_5xx'] = get_number(r'Erros 5xx\s*\(24h\):\s*([\d,.]+)')
                stats['unique_users'] = get_number(r'Usuários únicos\s*\(24h\):\s*([\d,.]+)')
                stats['unique_domains'] = get_number(r'Domínios únicos\s*\(24h\):\s*([\d,.]+)')

                # Top domínios (24h) - pode aparecer com ou sem (24h)
                m = re.search(r'Top domínios(?:\s*\(24h\))?:\s*(\{.*?\})', content)
                if m:
                    try:
                        stats['top_domains'] = json.loads(m.group(1))
                    except:
                        pass

                # Top usuários por tráfego (24h)
                m = re.search(r'Top usuários por tráfego:\s*(.+)', content)
                if m:
                    users_str = m.group(1)
                    entries = re.findall(r'([^,(]+?)\s*\(([\d.]+)\s*MB?\)', users_str)
                    stats['top_users_bytes'] = [(u.strip(), float(b)*1e6) for u,b in entries]

                stats['auth_407_by_ip'] = {}
                for line in re.findall(r'Alto volume de 407: IP ([\d.]+) com ([\d,.]+) falhas', content):
                    ip, count = line
                    stats['auth_407_by_ip'][ip] = int(count.replace(',','').replace('.',''))

                # Domínios suspeitos
                stats['suspicious'] = []
                for line in re.findall(r'Domínio suspeito:\s*([^\n]+?)\s*\(([^)]+)\)', content):
                    domain, reason = line
                    stats['suspicious'].append({'domain': domain.strip(), 'reason': reason.strip()})

            self.send_response(200)
            self.set_no_cache_headers()
            self.set_no_cache_headers()
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(stats).encode())
        except Exception as e:
            self.send_error(500, str(e))


    def handle_squid_realtime(self):
        """Retorna dados reais coletados do log do Squid (WebHacks)"""
        REALTIME_FILE = '/var/www/agentes.idearagencia.com.br/squid-realtime.json'
        try:
            if not os.path.exists(REALTIME_FILE):
                # Retornar dados vazios ou gerar alerta
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'Dados não disponíveis. Execute o coletor.'}).encode())
                return
            
            with open(REALTIME_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.send_response(200)
            self.set_no_cache_headers()
            self.set_no_cache_headers()
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        except Exception as e:
            self.send_error(500, str(e))


    def handle_proxy_metrics(self):
        """Retorna métricas do servidor proxy 172.16.1.9 coletadas via SSH"""
        PROXY_FILE = '/var/www/agentes.idearagencia.com.br/proxy-realtime.json'
        try:
            if not os.path.exists(PROXY_FILE):
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'Métricas do proxy não disponíveis. Execute o coletor.'}).encode())
                return
            
            with open(PROXY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Garantir campos mínimos
            data.setdefault('host', '172.16.1.9')
            data.setdefault('status', 'online')
            
            self.send_response(200)
            self.set_no_cache_headers()
            self.set_no_cache_headers()
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        except Exception as e:
            self.send_error(500, str(e))


    def handle_mikrotik_analytics(self):
        """Retorna dados do analytics do MikroTik (coletado via script)"""
        ANALYTICS_FILE = '/var/www/agentes.idearagencia.com.br/mikrotik-analytics.json'
        try:
            if not os.path.exists(ANALYTICS_FILE):
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'Dados do MikroTik não disponíveis. Execute o coletor.'}).encode())
                return
            
            with open(ANALYTICS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Garantir campos mínimos
            data.setdefault('status', 'online')
            
            self.send_response(200)
            self.set_no_cache_headers()
            self.set_no_cache_headers()
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        except Exception as e:
            self.send_error(500, str(e))


    def handle_unifi_stats(self):
        try:
            # Ler último snapshot do UniFi
            files = [f for f in os.listdir(UNIFI_DATA_DIR) if f.startswith('unifi_snapshot_') and f.endswith('.json')]
            files.sort(reverse=True)
            if not files:
                self.send_error(404, 'No UniFi data available')
                return
            latest = os.path.join(UNIFI_DATA_DIR, files[0])
            with open(latest, 'r') as f:
                data = json.load(f)

            # Stats simples baseados no que temos
            devices = data.get('devices', [])
            aps = [d for d in devices if d.get('type') in ['uap', 'uap']]
            switches = [d for d in devices if d.get('type') == 'usw']
            clients = data.get('clients', [])
            rogues = data.get('rogue_aps', [])
            alerts = data.get('alerts', [])

            stats = {
                'timestamp': data.get('timestamp'),
                'total_aps': len(aps),
                'aps_online': len(aps),  # simplificado: todos online pois foram coletados
                'aps_offline': 0,
                'total_switches': len(switches),
                'total_ssids': len([s for s in data.get('ssids', []) if s.get('enabled', True)]),
                'active_clients_24h': len(clients),  # simplificado
                'rogue_aps_total': len(rogues),
                'rogue_aps_2g': 0,
                'rogue_aps_5g': 0,
                'alerts_active': len(alerts),
                'alerts_list': alerts[:5]
            }

            self.send_response(200)
            self.set_no_cache_headers()
            self.set_no_cache_headers()
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(stats).encode())
        except Exception as e:
            self.send_error(500, str(e))


    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/':
            self.path = '/dashboard.html'
            return super().do_GET()
        elif parsed.path == '/alerts':
            self.handle_alerts()
            return
        elif parsed.path == '/alert':
            self.handle_alert(parsed.query)
            return
        elif parsed.path == '/squid-dashboard.html':
            self.path = '/squid-dashboard.html'
            return super().do_GET()
        elif parsed.path == '/squid-alerts':
            self.handle_squid_alerts()
            return
        elif parsed.path == '/squid-stats':
            self.handle_squid_stats()
            return
        elif parsed.path == '/proxy-metrics':
            self.handle_proxy_metrics()
            return
        elif parsed.path == '/unifi-dashboard.html':
            self.path = '/unifi-dashboard.html'
            return super().do_GET()
        elif parsed.path == '/unifi-stats':
            self.handle_unifi_stats()
            return
        elif parsed.path == '/api/mikrotik-analytics':
            self.handle_mikrotik_analytics()
            return
        elif parsed.path == '/mikrotik-stats':
            self.handle_mikrotik_stats()
            return
        elif parsed.path == '/api/mikrotik-analytics':
            self.handle_mikrotik_analytics()
            return
        elif parsed.path == '/mikrotik-logs':
            self.handle_mikrotik_logs()
            return
        elif parsed.path == '/reports-list':
            self.handle_reports_list()
            return
        return super().do_GET()

    def handle_mikrotik_stats(self):
        """Retorna estatísticas do MikroTik a partir do alerta com mais logs"""
        try:
            import glob
            # Procurar arquivos de alerta
            pattern = os.path.join(LOG_DIR, 'mikrotik_alert_*.md')
            files = glob.glob(pattern)
            if not files:
                self.send_error(404, 'Nenhum alerta MikroTik disponível')
                return
            
            # Avaliar todos os arquivos e pegar o com maior total de logs
            best_file = None
            best_total = 0
            best_content = ''
            best_mtime = 0
            
            for filepath in files:
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    total_match = re.search(r'Total de logs analisados:\s*([\d,.]+)', content)
                    total_logs = 0
                    if total_match:
                        try:
                            total_logs = int(total_match.group(1).replace(',', '').replace('.', ''))
                        except:
                            total_logs = 0
                    
                    file_mtime = os.path.getmtime(filepath)
                    
                    # Escolher arquivo com mais logs; se empatar, o mais recente
                    if total_logs > best_total or (total_logs == best_total and file_mtime > best_mtime):
                        best_file = filepath
                        best_total = total_logs
                        best_content = content
                        best_mtime = file_mtime
                except Exception as e:
                    print(f"[!] Erro lendo {filepath}: {e}")
                    continue
            
            if best_file is None or best_total == 0:
                # Fallback: usar o arquivo mais recente, mesmo sem dados
                files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                best_file = files[0]
                best_mtime = os.path.getmtime(best_file)
                with open(best_file, 'r', encoding='utf-8') as f:
                    best_content = f.read()
                best_total = 0
            
            last_analyzed = datetime.fromtimestamp(best_mtime, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            content = best_content
            
            # Extrair tópicos (JSON) — pode estar em linha única após "Por tópico:"
            topics = {}
            pos = content.find('Por tópico:')
            if pos != -1:
                # Procurar chave { após esta posição
                start = content.find('{', pos)
                if start != -1:
                    # Encontrar o } correspondente
                    depth = 0
                    end = None
                    for i in range(start, len(content)):
                        if content[i] == '{':
                            depth += 1
                        elif content[i] == '}':
                            depth -= 1
                            if depth == 0:
                                end = i + 1
                                break
                    if end:
                        topics_str = content[start:end]
                        try:
                            topics = json.loads(topics_str)
                        except json.JSONDecodeError as e:
                            print(f"[!] JSON decode error em {best_file}: {e}")
                            topics = {}
            
            # Extrair alertas detectados
            alerts = []
            alerts_section = re.search(r'Alertas detectados:(.*?)(?=\n\*{2,}|\Z)', content, re.DOTALL)
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
            
            self.send_response(200)
            self.set_no_cache_headers()
            self.set_no_cache_headers()
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(stats).encode())
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_error(500, f'Erro MikroTik: {str(e)}')

    def handle_reports_list(self):
        """Lista todos os relatórios PDF disponíveis com metadados"""
        try:
            reports = []
            if os.path.exists(REPORTS_DIR):
                for filename in sorted(os.listdir(REPORTS_DIR)):
                    if filename.lower().endswith('.pdf'):
                        filepath = os.path.join(REPORTS_DIR, filename)
                        try:
                            stat = os.stat(filepath)
                            # Extrair nome do agente do filename: Agent-Titulo.pdf
                            name_parts = filename[:-4].split('-', 1)  # remove .pdf e split no primeiro '-'
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
            
            self.send_response(200)
            self.set_no_cache_headers()
            self.set_no_cache_headers()
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(reports).encode())
        except Exception as e:
            self.send_error(500, str(e))


    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/proxy-metrics-upload':
            self.handle_proxy_metrics_upload()
        else:
            self.send_error(404, 'Not Found')

    def handle_proxy_metrics_upload(self):
        """Recebe métricas do proxy via POST e salva em arquivo"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            # Garantir campos mínimos
            data.setdefault('host', '172.16.1.9')
            data.setdefault('status', 'online')
            
            output_path = '/var/www/agentes.idearagencia.com.br/proxy-realtime.json'
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            self.send_response(200)
            self.set_no_cache_headers()
            self.set_no_cache_headers()
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'ok', 'message': 'Metrics received'}).encode())
        except Exception as e:
            self.send_error(500, str(e))
        """Retorna dados do analytics do MikroTik (coletado via script)"""
        ANALYTICS_FILE = '/var/www/agentes.idearagencia.com.br/mikrotik-analytics.json'
        try:
            if not os.path.exists(ANALYTICS_FILE):
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'Dados do MikroTik não disponíveis. Execute o coletor.'}).encode())
                return
            
            with open(ANALYTICS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Garantir campos mínimos
            data.setdefault('status', 'online')
            
            self.send_response(200)
            self.set_no_cache_headers()
            self.set_no_cache_headers()
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        except Exception as e:
            self.send_error(500, str(e))

def run_server(host='0.0.0.0', port=8080):
    server = HTTPServer((host, port), DashboardHandler)
    print(f"[+] Dashboard server running at http://{host}:{port}")
    server.serve_forever()

if __name__ == '__main__':
    run_server()
