from django.urls import path

from . import views

urlpatterns = [
    path('', views.notification_list, name='notification_list'),
    path('<int:pk>/open/', views.notification_open, name='notification_open'),
    path('mark-all-read/', views.notification_mark_all_read, name='notification_mark_all_read'),
]
