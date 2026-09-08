from django.urls import path
from . import views

urlpatterns = [
    path('', views.visitor_list, name='visitor_list'),
    path('new/', views.visitor_create, name='visitor_create'),
    path('<int:pk>/', views.visitor_detail, name='visitor_detail'),
]
