# ScrumDeal

Aplikacja do planowania pokerowego dla zespołów Agile z komunikacją w czasie rzeczywistym.

## 🌐 **Aplikacja wdrożona**

**ScrumDeal** jest dostępny online pod adresem: [https://scrumdeal.pl](https://scrumdeal.pl)

### Funkcje:
- ✅ Tworzenie i dołączanie do stołów
- ✅ Głosowanie w czasie rzeczywistym
- ✅ WebSocket komunikacja
- ✅ Zarządzanie krupierem
- ✅ Hasła do stołów
- ✅ Tryb ciemny/jasny
- ✅ Responsywny design

---

## 🚀 **Wdrożenie na produkcję**

### Wymagania serwera:
- Ubuntu 22.04 LTS
- 2 vCPU, 2GB RAM, 40GB SSD
- Domeny: `scrumdeal.pl`, `www.scrumdeal.pl`

### Automatyczne wdrożenie:
```bash
# Sklonuj repo na serwerze
git clone https://github.com/twoj-username/scrum_deal.git /opt/scrumdeal

# Uruchom skrypt wdrożenia
sudo chmod +x /opt/scrumdeal/deploy.sh
sudo /opt/scrumdeal/deploy.sh
```

### Konfiguracja SSL/HTTPS:
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d scrumdeal.pl -d www.scrumdeal.pl
```

---

## 🔄 **Aktualizacja aplikacji na produkcji**

### Szybka aktualizacja:
```bash
cd /opt/scrumdeal
sudo systemctl stop scrumdeal
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --no-input
sudo systemctl start scrumdeal
sudo systemctl status scrumdeal
```

### Skrypt aktualizacji:
```bash
# Utwórz skrypt update.sh na VPS
sudo nano /opt/scrumdeal/update.sh
chmod +x /opt/scrumdeal/update.sh

# Użycie:
sudo /opt/scrumdeal/update.sh
```

### Backup przed aktualizacją:
```bash
cp /opt/scrumdeal/db.sqlite3 /opt/scrumdeal/db.sqlite3.backup.$(date +%Y%m%d_%H%M%S)
```

---

## 💻 **Instrukcja uruchomienia aplikacji lokalnie**

### 1. Klonowanie repozytorium

### 2. Utworzenie i aktywacja środowiska wirtualnego (Windows)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate
```

### 3. Instalacja zależności

```powershell
pip install -r requirements.txt
```

### 4. Migracje bazy danych

```powershell
python manage.py makemigrations
python manage.py migrate
```

### 5. Utworzenie konta administratora (opcjonalnie)

```powershell
python manage.py createsuperuser
```

### 6. Uruchomienie serwera (Daphne/Channels)

```powershell
daphne -p 8000 scrumdeal.asgi:application
```

Aplikacja będzie dostępna pod adresem: [http://127.0.0.1:8000](http://127.0.0.1:8000)

---

## 🛠️ **Najczęstsze problemy**

- **Błąd importu Django:** Upewnij się, że środowisko wirtualne jest aktywne (`.venv`).
- **Błąd z bazą danych:** Sprawdź, czy plik `scrumdeal/settings.py` zawiera poprawną sekcję `DATABASES`.
- **Błąd z importem `ScrumDeal`:** Upewnij się, że katalog z kodem to `scrumdeal` (małe litery), a nie `ScrumDeal`.
- **Błąd z migracjami:** Usuń stare migracje z `poker/migrations/` (oprócz `__init__.py`), usuń plik `db.sqlite3` i wykonaj migracje od nowa.
- **Błąd z odpaleniem środowiska wirtualnego:** Usuń stare środowisko wirtualne i utwórz je od nowa:
  
   deactivate
  
   Remove-Item -Recurse -Force .venv
  
   python -m venv .venv
  
   .\.venv\Scripts\activate
  
   pip install -r requirements.txt

---

## 📋 **Wymagania**
- Python 3.10+
- Django 5+
- channels
- daphne
- channels-redis (opcjonalnie, do produkcji)
- redis (opcjonalnie, do produkcji)
- gunicorn (produkcja)
- nginx (produkcja)

---

## 🔧 **Pliki konfiguracyjne**

- `deploy.sh` - Skrypt automatycznego wdrożenia na VPS
- `build.sh` - Skrypt budowania dla platform cloud
- `env.example` - Przykład zmiennych środowiskowych
- `monitoring.sh` - Skrypt monitorowania zasobów VPS
- `requirements.txt` - Zależności Python
- `.gitignore` - Ignorowane pliki Git

---

## 📞 **Wsparcie**

W przypadku problemów z wdrożeniem lub aktualizacją, sprawdź:
1. Logi aplikacji: `sudo journalctl -u scrumdeal -f`
2. Logi Nginx: `sudo tail -f /var/log/nginx/error.log`
3. Status usług: `sudo systemctl status scrumdeal nginx redis`


