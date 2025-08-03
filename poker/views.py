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
        
        # Przywróć wartości z sesji, jeśli istnieją (po błędzie duplikacji nicku)
        request = self.request
        if 'last_table_name' in request.session:
            context['last_table_name'] = request.session['last_table_name']
            context['last_nickname'] = request.session.get('last_nickname', '')
            context['last_role'] = request.session.get('last_role', 'participant')
            context['last_is_croupier'] = request.session.get('last_is_croupier', False)
            # Wyczyść sesję po użyciu
            del request.session['last_table_name']
            del request.session['last_nickname']
            del request.session['last_role']
            del request.session['last_is_croupier']
        
        return context
    
    def get_active_tables(self):
        """Pobiera listę stołów z aktywnymi graczami"""
        from .consumers import ACTIVE_TABLES
        import time
        
        active_tables = []
        current_time = time.time()
        
        # Użyj globalnej listy aktywnych stołów
        for table_name, table_info in ACTIVE_TABLES.items():
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
                    'has_voting': any(p.get('has_voted') for p in participants)
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
        if not table_name or not nickname:
            return redirect('poker:home')
        
        # Sprawdź czy stół już istnieje i ma aktywnych graczy (tylko przy tworzeniu nowego stołu)
        from .consumers import ACTIVE_TABLES
        import time
        current_time = time.time()
        
        if not is_joining_existing and table_name in ACTIVE_TABLES:
            table_info = ACTIVE_TABLES[table_name]
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
        
        # Sprawdź czy nick jest już zajęty w cache
        table_data = cache.get(f'table_{table_name}')
        if table_data and 'players' in table_data:
            existing_players = table_data['players']
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
        
        # Nick jest dostępny - zapisz w sesji i przekieruj do stołu
        request.session['nickname'] = nickname
        request.session['role'] = role
        request.session['is_croupier'] = is_croupier
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

def get_active_tables_api(request):
    """API endpoint do pobierania aktywnych stołów"""
    from .consumers import ACTIVE_TABLES
    import time
    
    active_tables = []
    current_time = time.time()
    
    # Użyj globalnej listy aktywnych stołów
    for table_name, table_info in ACTIVE_TABLES.items():
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
        'global_tables_count': len(ACTIVE_TABLES),
        'debug_info': {
            'global_tables': list(ACTIVE_TABLES.keys()),
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
        from .consumers import ACTIVE_TABLES
        import time
        
        if table_name in ACTIVE_TABLES:
            # Znajdź gracza i zaktualizuj jego czas aktywności
            for player in ACTIVE_TABLES[table_name]['players']:
                if player.get('nickname') == nickname:
                    player['last_activity'] = time.time()
                    break
            
            # Zaktualizuj czas ostatniej aktywności stołu
            ACTIVE_TABLES[table_name]['last_updated'] = time.time()
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False, 'error': 'Nieprawidłowa metoda'})
