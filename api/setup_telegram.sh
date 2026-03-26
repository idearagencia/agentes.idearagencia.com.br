#!/bin/bash
# Configuração de Notificações Telegram - NetWatch

echo "=== Configuração Telegram para NetWatch ==="
echo ""
echo "Primeiro, crie um bot no Telegram:"
echo "1. Abra o Telegram e busque @BotFather"
echo "2. Envie: /newbot"
echo "3. Escolha um nome: NetWatch Alerts"
echo "4. Escolha um username: (deve terminar em 'bot')"
echo "5. Copie o token que o BotFather retorna"
echo ""
echo "Segundo, obtenha o chat_id do destino:"
echo "1. Adicione o bot ao grupo/canal ou inicie conversa"
echo "2. Envie qualquer mensagem no destino"
echo "3. Execute no servidor:"
echo "   curl -s 'https://api.telegram.org/bot<SEU_TOKEN>/getUpdates' | jq '.result[0].message.chat.id'"
echo "   (ou procure por 'chat':{'id': ...})"
echo ""

read -p "Token do Bot Telegram: " BOT_TOKEN
read -p "Chat ID (ex: -100XXXXXXXX): " CHAT_ID

# Validar
if [ -z "$BOT_TOKEN" ] || [ -z "$CHAT_ID" ]; then
    echo "❌ Token e Chat_ID são obrigatórios."
    exit 1
fi

# Salvar configuração
CONFIG_FILE="/var/log/netwatch/telegram.conf"
cat > "$CONFIG_FILE" <<EOF
BOT_TOKEN="$BOT_TOKEN"
CHAT_ID="$CHAT_ID"
EOF

chmod 600 "$CONFIG_FILE"

echo ""
echo "✅ Configuração salva em $CONFIG_FILE"
echo ""
echo "Testar envio? (s/N)"
read -r TEST
if [[ "$TEST" =~ ^[Ss]$ ]]; then
    python3 /var/www/agentes.idearagencia.com.br/api/test_telegram.py
fi

echo ""
echo "Configurar agendamento cron? (s/N)"
read -r CRON
if [[ "$CRON" =~ ^[Ss]$ ]]; then
    echo "Agendando a cada 5 minutos..."
    (crontab -l 2>/dev/null | grep -v "/var/www/agentes.idearagencia.com.br/api/notifier.py"; echo "*/5 * * * * /usr/bin/python3 /var/www/agentes.idearagencia.com.br/api/notifier.py >> /var/log/netwatch/notifier.log 2>&1") | crontab -
    echo "✅ Cron configurado."
fi

echo ""
echo "Pronto! Para enviar manualmente agora:"
echo "  python3 /var/www/agentes.idearagencia.com.br/api/notifier.py"
