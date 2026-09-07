from django.urls import path
from . import views

urlpatterns = [
    path('', views.message_list, name='message_list'),
    path('<int:pk>/', views.message_detail, name='message_detail'),
]
