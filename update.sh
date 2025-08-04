#!/bin/bash

# Skrypt aktualizacji aplikacji ScrumDeal na produkcji
# Użycie: sudo /opt/scrumdeal/update.sh

set -e  # Zatrzymaj skrypt przy błędzie

echo "🔄 Rozpoczynam aktualizację aplikacji ScrumDeal..."

# Przejdź do katalogu aplikacji
cd /opt/scrumdeal

# Backup bazy danych
echo "💾 Tworzę backup bazy danych..."
cp db.sqlite3 db.sqlite3.backup.$(date +%Y%m%d_%H%M%S)

# Zatrzymaj aplikację
echo "⏹️ Zatrzymuję aplikację..."
sudo systemctl stop scrumdeal

# Pobierz najnowsze zmiany
echo "📥 Pobieram najnowsze zmiany z repo..."
git pull origin main

# Aktywuj środowisko wirtualne
echo "🐍 Aktywuję środowisko wirtualne..."
source venv/bin/activate

# Zaktualizuj zależności
echo "📦 Aktualizuję zależności..."
pip install -r requirements.txt

# Wykonaj migracje
echo "🗄️ Wykonuję migracje bazy danych..."
python manage.py migrate

# Zbierz pliki statyczne
echo "📁 Zbieram pliki statyczne..."
python manage.py collectstatic --no-input

# Uruchom aplikację
echo "▶️ Uruchamiam aplikację..."
sudo systemctl start scrumdeal

# Sprawdź status
echo "🔍 Sprawdzam status aplikacji..."
sudo systemctl status scrumdeal --no-pager

echo "✅ Aktualizacja zakończona pomyślnie!"
echo "🌐 Aplikacja dostępna pod: https://scrumdeal.pl" 