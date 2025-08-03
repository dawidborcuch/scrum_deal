from django.urls import path
from . import views

app_name = 'poker'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('join_table/', views.join_table, name='join_table'),
    path('table/<str:table_name>/', views.table_view, name='table'),
    path('check_croupier/<str:table_name>/', views.check_croupier, name='check_croupier'),
    path('check_table_password/<str:table_name>/', views.check_table_password, name='check_table_password'),
    path('api/active_tables/', views.get_active_tables_api, name='active_tables_api'),
    path('ping_activity/<str:table_name>/', views.ping_activity, name='ping_activity'),
] 