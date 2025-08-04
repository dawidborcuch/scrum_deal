# ScrumDeal

## Instrukcja uruchomienia aplikacji

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

## Najczęstsze problemy

- **Błąd importu Django:** Upewnij się, że środowisko wirtualne jest aktywne (`.venv`).
- **Błąd z bazą danych:** Sprawdź, czy plik `scrumdeal/settings.py` zawiera poprawną sekcję `DATABASES`.
- **Błąd z importem `ScrumDeal`:** Upewnij się, że katalog z kodem to `scrumdeal` (małe litery), a nie `ScrumDeal`.
- **Błąd z migracjami:** Usuń stare migracje z `poker/migrations/` (oprócz `__init__.py`), usuń plik `db.sqlite3` i wykonaj migracje od nowa.
- **Błąd z odpaleniem środowiska wirtualnego:** Usuń stare środowisko wirtualne i utwórz je od nowa:
   deactivate
   Remove-Item -Recurse -Force .venv
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
---

## Wymagania
- Python 3.10+
- Django 5+
- channels
- daphne
- channels-redis (opcjonalnie, do produkcji)
- redis (opcjonalnie, do produkcji)

---

