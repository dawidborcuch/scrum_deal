from django.shortcuts import render, redirect
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.core.cache import cache

# Create your views here.

class HomeView(TemplateView):
    template_name = 'poker/home.html'

class TableView(TemplateView):
    template_name = 'poker/table.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['table_name'] = kwargs.get('table_name')
        return context

def table_view(request, table_name):
    nickname = request.GET.get('nickname', '')
    role = request.GET.get('role', 'participant')
    is_croupier = request.GET.get('is_croupier', '0') == '1'
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
