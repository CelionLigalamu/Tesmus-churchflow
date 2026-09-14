from django.urls import path
from django.contrib.auth import views as auth_views
from django.views.generic import RedirectView
from . import views
from accounts.views import ChurchLoginView, set_theme_preference

urlpatterns = [
    path('public-preview/', RedirectView.as_view(pattern_name='public_home', permanent=True)),
    path('', views.public_home, name='public_home'),
    path('dashboard/', views.home, name='home'),
    path('activity/', views.activity_list, name='activity_list'),
    path('settings/', views.settings_page, name='settings_page'),
    path('preferences/theme/', set_theme_preference, name='set_theme_preference'),
    path('login/', auth_views.LoginView.as_view(template_name='dashboard/login.html'), name='login'),
    path('<slug:church_slug>/login/', ChurchLoginView.as_view(), name='church_login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
]
