#!/bin/bash
set -e

# Load environment variables
if [ -f /app/.env ]; then
    export $(grep -v '^#' /app/.env | xargs 2>/dev/null)
fi

# ============================
# nginx: BasicAuth setup
# ============================
if [ -n "$APP_AUTH_KEY" ] && [ -n "$LOGIN_CODE" ]; then
    echo "[nginx] Setting up BasicAuth..."
    # Run htpasswd as root, nginx will drop privileges
    htpasswd -bc /tmp/.htpasswd admin "$APP_AUTH_KEY"
    sed -i 's/# auth_basic/auth_basic/' /etc/nginx/nginx.conf
    sed -i 's/# auth_basic_user_file/auth_basic_user_file/' /etc/nginx/nginx.conf
elif [ -z "$APP_AUTH_KEY" ]; then
    echo "[nginx] APP_AUTH_KEY not set - running without authentication"
    sed -i 's/# auth_basic/auth_basic/' /etc/nginx/nginx.conf
    sed -i 's/# auth_basic_user_file/auth_basic_user_file/' /etc/nginx/nginx.conf
fi

# ============================
# nginx: copy config and start
# ============================
cp /app/nginx.conf /etc/nginx/nginx.conf
nginx -t
nginx

# ============================
# Discord Listener (background)
# ============================
echo "[discord] Starting Discord self-bot listener..."
cd /app
python -m ingestion.discord_listener &
DISCORD_PID=$!

# ============================
# Daily Rollup Scheduler (background)
# ============================
echo "[scheduler] Starting daily rollup scheduler..."
python -m scheduler.daily_rollup --daemon &
SCHEDULER_PID=$!

# ============================
# ngrok tunnel (background)
# ============================
if [ -n "$NGROK_AUTH_TOKEN" ]; then
    echo "[ngrok] Starting tunnel to :8000 ..."
    ngrok config add-authtoken "$NGROK_AUTH_TOKEN" 2>/dev/null || true
    ngrok http --domain="$NGROK_DOMAIN" 8000 --log /app/logs/ngrok.log &
    NGROK_PID=$!
else
    echo "[ngrok] NGROK_AUTH_TOKEN not set — skipping tunnel"
fi

# ============================
# Streamlit Frontend (foreground)
# ============================
echo "[streamlit] Starting frontend on 127.0.0.1:8501..."
exec streamlit run frontend/app.py \
    --server.port 8501 \
    --server.address 127.0.0.1 \
    --server.headless true \
    --browser.gatherUsageStats false \
    --server.runOnSave false
