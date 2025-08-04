#!/bin/bash

# Skrypt deploymentu dla VPS OVH
set -e

echo "🚀 Rozpoczynam deployment ScrumDeal..."

# Aktualizacja systemu
echo "📦 Aktualizacja systemu..."
sudo apt update && sudo apt upgrade -y

# Instalacja wymaganych pakietów
echo "🔧 Instalacja pakietów systemowych..."
sudo apt install -y python3-pip python3-venv nginx redis-server git curl

# Tworzenie użytkownika dla aplikacji
echo "👤 Tworzenie użytkownika aplikacji..."
sudo useradd -m -s /bin/bash scrumdeal || true
sudo usermod -aG sudo scrumdeal

# Tworzenie katalogu aplikacji
echo "📁 Tworzenie katalogu aplikacji..."
sudo mkdir -p /opt/scrumdeal
sudo chown scrumdeal:scrumdeal /opt/scrumdeal

# Konfiguracja SQLite3
echo "🗄️ Konfiguracja SQLite3..."
# SQLite3 jest wbudowany w Python, nie wymaga dodatkowej konfiguracji

# Konfiguracja Redis
echo "🔴 Konfiguracja Redis..."
sudo systemctl enable redis-server
sudo systemctl start redis-server

# Konfiguracja Nginx
echo "🌐 Konfiguracja Nginx..."
sudo tee /etc/nginx/sites-available/scrumdeal << EOF
server {
    listen 80;
    server_name twoja-domena.com www.twoja-domena.com;

    location = /favicon.ico { access_log off; log_not_found off; }
    
    location /static/ {
        root /opt/scrumdeal;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/run/scrumdeal.sock;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/scrumdeal /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo systemctl restart nginx

# Konfiguracja systemd service
echo "⚙️ Konfiguracja systemd service..."
sudo tee /etc/systemd/system/scrumdeal.service << EOF
[Unit]
Description=ScrumDeal Django Application
After=network.target

[Service]
User=scrumdeal
Group=scrumdeal
WorkingDirectory=/opt/scrumdeal
Environment="PATH=/opt/scrumdeal/venv/bin"
Environment="SECRET_KEY=TWÓJ_SECRET_KEY_TUTAJ"
Environment="DEBUG=False"
Environment="ALLOWED_HOSTS=twoja-domena.com,www.twoja-domena.com"
# Usunięte zmienne PostgreSQL - SQLite3 nie wymaga konfiguracji
Environment="REDIS_URL=redis://localhost:6379"
ExecStart=/opt/scrumdeal/venv/bin/gunicorn --workers 2 --bind unix:/run/scrumdeal.sock scrumdeal.asgi:application -k uvicorn.workers.UvicornWorker
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Konfiguracja firewall
echo "🔥 Konfiguracja firewall..."
sudo ufw allow 'Nginx Full'
sudo ufw allow ssh
sudo ufw --force enable

echo "✅ Deployment zakończony!"
echo "📝 Następne kroki:"
echo "1. Skopiuj kod do /opt/scrumdeal"
echo "2. Zaktualizuj zmienne środowiskowe w /etc/systemd/system/scrumdeal.service"
echo "3. Uruchom: sudo systemctl start scrumdeal"
echo "4. Sprawdź: sudo systemctl status scrumdeal" 