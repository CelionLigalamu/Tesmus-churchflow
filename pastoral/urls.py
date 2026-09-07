from django.urls import path
from . import views

urlpatterns = [
    path('', views.followup_list, name='pastoral_followup_list'),
    path('<int:pk>/', views.followup_detail, name='pastoral_followup_detail'),
]
