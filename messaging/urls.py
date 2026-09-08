from django.urls import path
from . import views

urlpatterns = [
    path('', views.message_list, name='message_list'),
    path('new/', views.message_create, name='message_create'),
    path('<int:pk>/', views.message_detail, name='message_detail'),
]
