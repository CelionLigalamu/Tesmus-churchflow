from django.urls import path
from . import views

urlpatterns = [
    path('', views.member_list, name='member_list'),
    path('new/', views.member_create, name='member_create'),
    path('<int:pk>/edit/', views.member_edit, name='member_edit'),
    path('ministry-roles/', views.ministry_role_list, name='ministry_role_list'),
    path('ministry-roles/new/', views.ministry_role_create, name='ministry_role_create'),
    path('ministry-roles/<int:pk>/edit/', views.ministry_role_edit, name='ministry_role_edit'),
    path('ministry-roles/<int:pk>/delete/', views.ministry_role_delete, name='ministry_role_delete'),
    path('<int:pk>/', views.member_detail, name='member_detail'),
]
