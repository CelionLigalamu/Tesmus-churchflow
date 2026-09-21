from django.urls import path
from . import views

urlpatterns = [
    path('', views.followup_list, name='pastoral_followup_list'),
    path('alert-setting/', views.absence_alert_setting, name='pastoral_absence_setting'),
    path('<int:pk>/', views.followup_detail, name='pastoral_followup_detail'),
    path('<int:pk>/update/', views.followup_update, name='pastoral_followup_update'),
]
