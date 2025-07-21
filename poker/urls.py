from django.urls import path
from . import views

app_name = 'poker'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('join_table/', views.join_table, name='join_table'),
    path('table/<str:table_name>/', views.table_view, name='table'),
    path('check_croupier/<str:table_name>/', views.check_croupier, name='check_croupier'),
] 