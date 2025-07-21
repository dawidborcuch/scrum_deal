from django.shortcuts import render, redirect
from django.views.generic import TemplateView

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
    if not nickname:
        return redirect('poker:home')
    
    return render(request, 'poker/table.html', {
        'table_name': table_name,
        'nickname': nickname,
        'card_values': [0, 1, 2, 3, 5, 8, 13, 20, 40, 100]
    })
