from django.urls import path
from . import views

urlpatterns = [
    path('', views.visitor_list, name='visitor_list'),
    path('<int:pk>/', views.visitor_detail, name='visitor_detail'),
]
