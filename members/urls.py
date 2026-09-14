from django.urls import path
from . import views

urlpatterns = [
    path('', views.member_list, name='member_list'),
    path('new/', views.member_create, name='member_create'),
    path('join/<uuid:token>/', views.member_self_register, name='member_self_register'),
    path('import/', views.member_import, name='member_import'),
    path('import/confirm/', views.member_import_confirm, name='member_import_confirm'),
    path('<int:pk>/edit/', views.member_edit, name='member_edit'),
    path('ministry-roles/', views.ministry_role_list, name='ministry_role_list'),
    path('ministry-roles/new/', views.ministry_role_create, name='ministry_role_create'),
    path('ministry-roles/<int:pk>/edit/', views.ministry_role_edit, name='ministry_role_edit'),
    path('ministry-roles/<int:pk>/delete/', views.ministry_role_delete, name='ministry_role_delete'),
    path('<int:pk>/', views.member_detail, name='member_detail'),
    path('<int:pk>/send-reference/', views.member_send_reference, name='member_send_reference'),
]
