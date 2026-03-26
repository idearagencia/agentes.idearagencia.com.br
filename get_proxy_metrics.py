#!/usr/bin/env python3
"""
get_proxy_metrics.py - Coleta métricas do servidor Proxy (Squid)
Deve ser executado no servidor 172.16.1.9 (proxy)
Retorna JSON com CPU, Memória, Disco e Status do Squid
"""

import json
import subprocess
import os
from datetime import datetime

# Forçar timezone Brasil
os.environ['TZ'] = 'America/Sao_Paulo'

def get_cpu_metrics():
    """Retorna uso de CPU via /proc/loadavg"""
    try:
        with open('/proc/loadavg', 'r') as f:
            load = f.read().split()
            load_1min = float(load[0])
            cpu_count = int(subprocess.getoutput('nproc --all') or '1')
            cpu_percent = min(100, round((load_1min / cpu_count) * 100, 1))
            return {
                'usage_percent': cpu_percent,
                'cores': cpu_count,
                'load_1min': load_1min,
                'load_5min': float(load[1]),
                'load_15min': float(load[2])
            }
    except Exception as e:
        return {'error': str(e), 'usage_percent': 0, 'cores': 1}

def get_memory_metrics():
    """Retorna uso de memória via free"""
    try:
        out = subprocess.getoutput('free -m')
        lines = out.split('\n')
        mem_line = [l for l in lines if l.startswith('Mem:')][0]
        parts = mem_line.split()
        total = int(parts[1])
        used = int(parts[2])
        free = int(parts[3])
        percent = round((used / total) * 100, 1) if total > 0 else 0
        return {
            'total_gb': round(total / 1024, 2) if total > 1024 else total,
            'used_gb': round(used / 1024, 2) if used > 1024 else used,
            'free_gb': round(free / 1024, 2) if free > 1024 else free,
            'percent': percent
        }
    except Exception as e:
        return {'error': str(e), 'total_gb': 0, 'used_gb': 0, 'free_gb': 0, 'percent': 0}

def get_disk_metrics():
    """Retorna uso de disco via df (partição raiz /)"""
    try:
        out = subprocess.getoutput('df -h /')
        lines = out.split('\n')
        if len(lines) >= 2:
            parts = lines[1].split()
            total = parts[1]
            used = parts[2]
            avail = parts[3]
            use_percent = parts[4].replace('%', '')
            def to_gb(size_str):
                if size_str.endswith('G'):
                    return float(size_str[:-1])
                elif size_str.endswith('M'):
                    return float(size_str[:-1]) / 1024
                elif size_str.endswith('K'):
                    return float(size_str[:-1]) / (1024**2)
                else:
                    return float(size_str)
            return {
                'total_gb': to_gb(total),
                'used_gb': to_gb(used),
                'free_gb': to_gb(avail),
                'percent': float(use_percent)
            }
        return {'total_gb': 0, 'used_gb': 0, 'free_gb': 0, 'percent': 0}
    except Exception as e:
        return {'error': str(e), 'total_gb': 0, 'used_gb': 0, 'free_gb': 0, 'percent': 0}

def get_squid_status():
    """Verifica status do serviço Squid"""
    try:
        # Verificar se processo squid está rodando
        ps_out = subprocess.getoutput('ps aux | grep [s]quid')
        running = 'squid' in ps_out
        
        # Verificar porta 3128
        ss_out = subprocess.getoutput('ss -tlnp 2>/dev/null | grep :3128')
        port_open = bool(ss_out.strip())
        
        # Contar conexões estabelecidas na porta 3128
        conn_out = subprocess.getoutput('ss -tn state established | grep :3128 | wc -l')
        active_connections = int(conn_out.strip()) if conn_out.strip().isdigit() else 0
        
        return {
            'service_running': running,
            'port_open': port_open,
            'active_connections': active_connections,
            'process_count': ps_out.count('\n') if ps_out else 0
        }
    except Exception as e:
        return {
            'service_running': False,
            'port_open': False,
            'active_connections': 0,
            'process_count': 0,
            'error': str(e)
        }

def main():
    try:
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'host': 'proxy-01',
            'cpu': get_cpu_metrics(),
            'memory': get_memory_metrics(),
            'disk': get_disk_metrics(),
            'squid': get_squid_status()
        }
        print(json.dumps(metrics, indent=2, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({
            'error': str(e),
            'status': 'failed'
        }))

if __name__ == '__main__':
    main()
