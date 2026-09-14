from django.urls import path

from . import views

urlpatterns = [
    path('', views.region_list, name='region_list'),
    path('new/', views.region_create, name='region_create'),
    path('pastor-role/', views.region_pastor_role, name='region_pastor_role'),
    path('<int:pk>/edit/', views.region_edit, name='region_edit'),
    path('<int:pk>/merge/', views.region_merge, name='region_merge'),
]
