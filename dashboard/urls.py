from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('public-preview/', views.public_home, name='public_home'),
    path('', views.home, name='home'),
    path('activity/', views.activity_list, name='activity_list'),
    path('settings/', views.settings_page, name='settings_page'),
    path('login/', auth_views.LoginView.as_view(template_name='dashboard/login.html'), name='login'),
    path('plcm/login/', auth_views.LoginView.as_view(template_name='dashboard/plcm_login.html'), name='plcm_login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
]
