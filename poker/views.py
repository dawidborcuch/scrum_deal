from django.shortcuts import render, redirect
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.core.cache import cache
from django.urls import reverse

# Create your views here.

class HomeView(TemplateView):
    template_name = 'poker/home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pobierz listę aktywnych stołów
        active_tables = self.get_active_tables()
        context['active_tables'] = active_tables
        
        # Przywróć wartości z sesji, jeśli istnieją (po błędzie duplikacji nicku lub hasła)
        request = self.request
        if 'last_table_name' in request.session:
            context['last_table_name'] = request.session['last_table_name']
            context['last_nickname'] = request.session.get('last_nickname', '')
            context['last_role'] = request.session.get('last_role', 'participant')
            context['last_is_croupier'] = request.session.get('last_is_croupier', False)
            context['last_table_password'] = request.session.get('last_table_password', '')
            # Wyczyść sesję po użyciu
            request.session.pop('last_table_name', None)
            request.session.pop('last_nickname', None)
            request.session.pop('last_role', None)
            request.session.pop('last_is_croupier', None)
            request.session.pop('last_table_password', None)
        
        # Sprawdź czy jest parametr table_name w URL (dla automatycznego otwierania modala)
        table_name = request.GET.get('table_name')
        if table_name:
            context['auto_join_table'] = table_name
        
        return context
    
    def get_active_tables(self):
        """Pobiera listę stołów z aktywnymi graczami"""
        import time
        
        active_tables = []
        current_time = time.time()
        
        # Pobierz aktywną listę stołów z cache
        redis_active_tables = cache.get('active_tables', {})
        
        for table_name, table_info in redis_active_tables.items():
            # Sprawdź czy stół nie jest zbyt stary (więcej niż 5 minut)
            if current_time - table_info['last_updated'] > 300:
                continue
                
            players = table_info['players']
            if players:  # Stół ma graczy
                # Oblicz statystyki stołu
                total_players = len(players)
                participants = [p for p in players if p.get('role') == 'participant']
                observers = [p for p in players if p.get('role') == 'observer']
                croupier = next((p for p in players if p.get('is_croupier')), None)
                
                active_tables.append({
                    'name': table_name,
                    'total_players': total_players,
                    'participants': len(participants),
                    'observers': len(observers),
                    'croupier': croupier['nickname'] if croupier else None,
                    'has_voting': any(p.get('has_voted') for p in participants),
                    'has_password': bool(table_info.get('password'))
                })
        
        # Sortuj po liczbie graczy (malejąco)
        active_tables.sort(key=lambda x: x['total_players'], reverse=True)
        return active_tables

class TableView(TemplateView):
    template_name = 'poker/table.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['table_name'] = kwargs.get('table_name')
        return context

def join_table(request):
    if request.method == 'POST':
        table_name = request.POST.get('table_name')
        nickname = request.POST.get('nickname')
        role = request.POST.get('role', 'participant')
        is_croupier = request.POST.get('is_croupier') == 'on'
        is_joining_existing = request.POST.get('is_joining_existing') == 'on'  # Nowe pole
        table_password = request.POST.get('table_password', '')  # Hasło do stołu
        enable_password = request.POST.get('enable_password') == 'on'  # Czy włączono hasło przy tworzeniu
        
        if not table_name or not nickname:
            return redirect('poker:home')
        
        # Sprawdź czy stół już istnieje i ma aktywnych graczy (tylko przy tworzeniu nowego stołu)
        import time
        current_time = time.time()
        
        # Pobierz aktywną listę stołów z cache
        redis_active_tables = cache.get('active_tables', {})
        
        if not is_joining_existing and table_name in redis_active_tables:
            table_info = redis_active_tables[table_name]
            # Sprawdź czy stół nie jest zbyt stary (więcej niż 5 minut)
            if current_time - table_info['last_updated'] <= 300 and table_info['players']:
                # Stół istnieje i ma aktywnych graczy - dodaj komunikat i przekieruj z powrotem
                from django.contrib import messages
                messages.error(request, f'Stół "{table_name}" już istnieje i ma aktywnych graczy. Wybierz inną nazwę stołu lub dołącz do istniejącego.')
                # Zapisz dane w sesji, aby je przywrócić na stronie głównej
                request.session['last_table_name'] = table_name
                request.session['last_nickname'] = nickname
                request.session['last_role'] = role
                request.session['last_is_croupier'] = is_croupier
                return redirect('poker:home')
        
        # Sprawdź czy nick jest już zajęty - użyj cache dla spójności z consumers.py
        existing_players = []
        
        # Sprawdź w cache (priorytet)
        if table_name in redis_active_tables:
            existing_players = redis_active_tables[table_name].get('players', [])
        
        # Jeśli nie ma w cache, sprawdź w table cache
        if not existing_players:
            table_data = cache.get(f'table_{table_name}')
            if table_data and 'players' in table_data:
                existing_players = table_data['players']
        
        # Sprawdź czy nick jest zajęty
        if any(p.get('nickname') == nickname for p in existing_players):
            # Nick jest zajęty - dodaj komunikat i przekieruj z powrotem do strony głównej
            from django.contrib import messages
            messages.error(request, f'Nick "{nickname}" jest już zajęty przy stole "{table_name}". Wybierz inny nick.')
            # Zapisz nazwę stołu w sesji, aby ją przywrócić na stronie głównej
            request.session['last_table_name'] = table_name
            request.session['last_nickname'] = nickname
            request.session['last_role'] = role
            request.session['last_is_croupier'] = is_croupier
            return redirect('poker:home')
        
        # Sprawdź hasło przy dołączaniu do istniejącego stołu
        table_password_to_check = None
        
        # Sprawdź hasło w cache (priorytet)
        if table_name in redis_active_tables:
            table_password_to_check = redis_active_tables[table_name].get('password')
        
        # Jeśli nie ma w cache, sprawdź w table cache
        if table_password_to_check is None:
            table_data = cache.get(f'table_{table_name}')
            if table_data:
                table_password_to_check = table_data.get('password')
        
        if is_joining_existing and table_password_to_check:
            if not table_password or table_password != table_password_to_check:
                from django.contrib import messages
                messages.error(request, f'Nieprawidłowe hasło do stołu "{table_name}".')
                # Zapisz dane w sesji
                request.session['last_table_name'] = table_name
                request.session['last_nickname'] = nickname
                request.session['last_role'] = role
                request.session['last_is_croupier'] = is_croupier
                request.session['last_table_password'] = table_password
                return redirect('poker:home')
        
        # Nick jest dostępny - zapisz w sesji i przekieruj do stołu
        request.session['nickname'] = nickname
        request.session['role'] = role
        request.session['is_croupier'] = is_croupier
        
        # Pobierz aktualne dane stołu
        table_data = cache.get(f'table_{table_name}')
        
        # Jeśli tworzysz nowy stół BEZ hasła, usuń hasło z cache
        if not is_joining_existing and not enable_password:
            if table_data and 'password' in table_data:
                del table_data['password']
                cache.set(f'table_{table_name}', table_data, 3600)
            if table_name in redis_active_tables and 'password' in redis_active_tables[table_name]:
                del redis_active_tables[table_name]['password']
                cache.set('active_tables', redis_active_tables, 3600)
        
        # Jeśli tworzysz nowy stół i włączono hasło, zapisz je w cache
        if not is_joining_existing and enable_password and table_password:
            # Zapisz hasło w cache dla nowego stołu
            if not table_data:
                table_data = {'players': [], 'password': table_password}
            else:
                table_data['password'] = table_password
            cache.set(f'table_{table_name}', table_data, 3600)  # Cache na 1 godzinę
            
            # Dodaj stół do cache z hasłem (jeśli jeszcze nie istnieje)
            if table_name not in redis_active_tables:
                redis_active_tables[table_name] = {
                    'players': [],
                    'last_updated': time.time(),
                    'password': table_password
                }
                cache.set('active_tables', redis_active_tables, 3600)
        
        return redirect(reverse('poker:table', args=[table_name]))
    return redirect('poker:home')

def table_view(request, table_name):
    nickname = request.session.get('nickname', '')
    role = request.session.get('role', 'participant')
    is_croupier = request.session.get('is_croupier', False)
    if not nickname:
        return redirect('poker:home')
    return render(request, 'poker/table.html', {
        'table_name': table_name,
        'nickname': nickname,
        'role': role,
        'is_croupier': is_croupier,
        'card_values': [0, 1, 2, 3, 5, 8, 13, 20, 40, 100]
    })

def check_croupier(request, table_name):
    table_data = cache.get(f'table_{table_name}')
    croupier_exists = False
    if table_data:
        croupier_exists = any(p.get('is_croupier', False) for p in table_data.get('players', []))
    return JsonResponse({'croupier_exists': croupier_exists})

def check_table_password(request, table_name):
    """API endpoint do sprawdzania czy stół ma hasło"""
    # Sprawdź najpierw w cache
    table_data = cache.get(f'table_{table_name}')
    has_password = False
    if table_data:
        password = table_data.get('password')
        has_password = bool(password) and password != ""
    
    # Jeśli nie ma w cache, sprawdź w active_tables
    if not has_password:
        redis_active_tables = cache.get('active_tables', {})
        if table_name in redis_active_tables:
            password = redis_active_tables[table_name].get('password')
            has_password = bool(password) and password != ""
    
    return JsonResponse({'has_password': has_password})

def get_active_tables_api(request):
    """API endpoint do pobierania aktywnych stołów"""
    import time
    
    active_tables = []
    current_time = time.time()
    
    # Pobierz aktywną listę stołów z cache
    redis_active_tables = cache.get('active_tables', {})
    
    for table_name, table_info in redis_active_tables.items():
        # Sprawdź czy stół nie jest zbyt stary (więcej niż 5 minut)
        if current_time - table_info['last_updated'] > 300:
            continue
            
        players = table_info['players']
        if players:  # Stół ma graczy
            # Oblicz statystyki stołu
            total_players = len(players)
            participants = [p for p in players if p.get('role') == 'participant']
            observers = [p for p in players if p.get('role') == 'observer']
            croupier = next((p for p in players if p.get('is_croupier')), None)
            
            active_tables.append({
                'name': table_name,
                'total_players': total_players,
                'participants': len(participants),
                'observers': len(observers),
                'croupier': croupier['nickname'] if croupier else None,
                'has_voting': any(p.get('has_voted') for p in participants),
                'players': [p['nickname'] for p in players]  # Lista nicków graczy
            })
    
    # Sortuj po liczbie graczy (malejąco)
    active_tables.sort(key=lambda x: x['total_players'], reverse=True)
    
    return JsonResponse({
        'active_tables': active_tables,
        'total_tables': len(active_tables),
        'global_tables_count': len(redis_active_tables),
        'debug_info': {
            'global_tables': list(redis_active_tables.keys()),
            'current_time': current_time
        }
    })

def ping_activity(request, table_name):
    """Endpoint do pingowania aktywności użytkownika"""
    if request.method == 'POST':
        nickname = request.POST.get('nickname')
        if not nickname:
            return JsonResponse({'success': False, 'error': 'Brak nicku'})
        
        # Zaktualizuj czas aktywności w cache
        import time
        
        redis_active_tables = cache.get('active_tables', {})
        if table_name in redis_active_tables:
            # Znajdź gracza i zaktualizuj jego czas aktywności
            for player in redis_active_tables[table_name]['players']:
                if player.get('nickname') == nickname:
                    player['last_activity'] = time.time()
                    break
            
            # Zaktualizuj czas ostatniej aktywności stołu
            redis_active_tables[table_name]['last_updated'] = time.time()
            cache.set('active_tables', redis_active_tables, 3600)
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False, 'error': 'Nieprawidłowa metoda'})
