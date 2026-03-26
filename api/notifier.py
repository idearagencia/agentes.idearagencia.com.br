#!/usr/bin/env python3
"""NetWatch Notifier"""

import json, os, requests, smtplib, ssl
from email.mime.text import MIMEText
from datetime import datetime
import pytz

BRAZIL_TZ = pytz.timezone('America/Sao_Paulo')
DATA_DIR = "/var/log/netwatch"

# Configurações padrão
EMAIL_CFG = {
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587,
    'username': '',
    'password': '',
    'from': 'NetWatch <alertas@barra-mansa.rj.gov.br>',
    'to': ['infra@barra-mansa.rj.gov.br'],
}
TELEGRAM_CFG = {
    'bot_token': '',
    'chat_id': '',
}
WEBHOOK_URL = 'http://localhost:8080/webhook/netwatch'

# Carregar configurações de arquivos
def load_telegram_config():
    cfg_file = os.path.join(DATA_DIR, 'telegram.conf')
    if os.path.exists(cfg_file):
        with open(cfg_file) as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, val = line.split('=', 1)
                    TELEGRAM_CFG[key.strip()] = val.strip().strip('"')
    return TELEGRAM_CFG

def load_email_config():
    email_file = os.path.join(DATA_DIR, 'email.conf')
    if os.path.exists(email_file):
        with open(email_file) as f:
            return json.load(f)
    return EMAIL_CFG

def load_alert_files():
    alert_dir = f"{DATA_DIR}/alerts"
    if not os.path.exists(alert_dir): return []
    alerts = []
    for fname in sorted(os.listdir(alert_dir)):
        if not fname.endswith('.json'): continue
        with open(f"{alert_dir}/{fname}") as f:
            for line in f:
                try:
                    alerts.append(json.loads(line))
                except: continue
    return alerts[-50:]  # últimos 50

def format_message(alert):
    emoji = "🔴" if alert['severity'] >= 8 else "🟡" if alert['severity'] >= 5 else "🟢"
    text = f"{emoji} *{alert['title']}*\n"
    text += f"Fonte: `{alert['source']}`\n"
    text += f"Severidade: {alert['severity']}/10\n"
    text += f"Descrição: {alert['desc']}\n"
    text += f"Hora: {datetime.now(BRAZIL_TZ).strftime('%d/%m/%Y %H:%M:%S')}\n"
    if 'ip' in alert:
        text += f"IP: `{alert['ip']}`\n"
    text += f"\n[Dashboard](http://monitor.idearagencia.com.br/netwatch/)"
    return text

def send_email(subject, body):
    cfg = load_email_config()
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = cfg.get('from', 'NetWatch')
    msg['To'] = ', '.join(cfg.get('to', []))
    context = ssl.create_default_context()
    with smtplib.SMTP(cfg['smtp_server'], cfg['smtp_port']) as server:
        server.starttls(context=context)
        server.login(cfg['username'], cfg['password'])
        server.send_message(msg)

def send_telegram(text):
    cfg = load_telegram_config()
    if not cfg['bot_token'] or not cfg['chat_id']:
        print("⚠️ Telegram não configurado")
        return
    url = f"https://api.telegram.org/bot{cfg['bot_token']}/sendMessage"
    payload = {'chat_id': cfg['chat_id'], 'text': text, 'parse_mode': 'Markdown'}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code != 200:
            print(f"❌ Telegram error: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"❌ Telegram exception: {e}")

def send_webhook(alert):
    try:
        requests.post(WEBHOOK_URL, json=alert, timeout=5)
    except Exception as e:
        print(f"⚠️ Webhook falhou: {e}")

def notify(alert):
    msg = format_message(alert)
    subject = f"[NetWatch] {alert['title']}"
    # Decidir canal por severidade
    if alert['severity'] >= 8:
        # Crítico: email + telegram
        try: send_email(subject, msg)
        except: pass
        try: send_telegram(msg)
        except: pass
    elif alert['severity'] >= 5:
        # Médio: email
        try: send_email(subject, msg)
        except: pass
    # Sempre webhook
    send_webhook(alert)

def main():
    alerts = load_alert_files()
    print(f"📨 Notificando {len(alerts)} alertas...")
    for alert in alerts:
        notify(alert)
        # Aqui poderíamos marcar como notificado
    print("✅ Notificações enviadas")

if __name__ == "__main__":
    main()