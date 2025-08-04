#!/bin/bash

# Monitoring zasobów VPS
echo "📊 Monitoring zasobów VPS..."

echo "=== PAMIĘĆ ==="
free -h

echo -e "\n=== PROCESY ==="
ps aux --sort=-%mem | head -10

echo -e "\n=== DYSK ==="
df -h

echo -e "\n=== USŁUGI ==="
echo "Django: $(systemctl is-active scrumdeal)"
echo "Nginx: $(systemctl is-active nginx)"
echo "Redis: $(systemctl is-active redis-server)"

echo -e "\n=== PORTY ==="
netstat -tlnp | grep -E ':(80|443|6379)'

echo -e "\n=== LOGI DJANGO (ostatnie 10 linii) ==="
if [ -f /opt/scrumdeal/logs/django.log ]; then
    tail -10 /opt/scrumdeal/logs/django.log
else
    echo "Brak pliku logów Django"
fi 