#!/usr/bin/env python3
"""Teste de Notificação Telegram - NetWatch"""

import json, os, requests
from datetime import datetime
import pytz

BRAZIL_TZ = pytz.timezone('America/Sao_Paulo')

# Carregar configuração
CONFIG_FILE = "/var/log/netwatch/telegram.conf"
if not os.path.exists(CONFIG_FILE):
    print("❌ Configuração Telegram não encontrada. Rode setup_telegram.sh")
    sys.exit(1)

config = {}
with open(CONFIG_FILE) as f:
    for line in f:
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            key, val = line.split('=', 1)
            config[key.strip()] = val.strip().strip('"')

BOT_TOKEN = config.get('BOT_TOKEN')
CHAT_ID = config.get('CHAT_ID')

if not BOT_TOKEN or not CHAT_ID:
    print("❌ Token ou Chat ID não configurados")
    sys.exit(1)

# Alerta de teste
test_alert = {
    'source': 'mikrotik',
    'severity': 8,
    'title': 'Teste de Notificação NetWatch',
    'desc': 'Este é um teste de integração com Telegram. Se você está vendo, funcionou!',
    'ip': '192.168.1.1',
    'count': 999
}

# Formatar mensagem
emoji = "🔴" if test_alert['severity'] >= 8 else "🟡" if test_alert['severity'] >= 5 else "🟢"
text = f"{emoji} *{test_alert['title']}*\n"
text += f"Fonte: `{test_alert['source']}`\n"
text += f"Severidade: {test_alert['severity']}/10\n"
text += f"Descrição: {test_alert['desc']}\n"
text += f"Hora: {datetime.now(BRAZIL_TZ).strftime('%d/%m/%Y %H:%M:%S')}\n"
text += f"IP: `{test_alert['ip']}`\n"
text += f"\n[Dashboard](http://monitor.idearagencia.com.br/netwatch/)"

# Enviar
url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
payload = {'chat_id': CHAT_ID, 'text': text, 'parse_mode': 'Markdown'}
print(f"DEBUG: POST {url}")
print(f"DEBUG: payload {payload}")
try:
    resp = requests.post(url, json=payload, timeout=10)
    print(f"DEBUG: status {resp.status_code}")
    print(f"DEBUG: body {resp.text}")
    if resp.status_code == 200:
        print("✅ Mensagem enviada com sucesso para Telegram!")
        print(f"   Chat ID: {CHAT_ID}")
    else:
        print(f"❌ Erro {resp.status_code}: {resp.text}")
except Exception as e:
    print(f"❌ Exceção: {e}")
