from django.urls import path
from . import views

app_name = 'poker'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('table/<str:table_name>/', views.table_view, name='table'),
] 