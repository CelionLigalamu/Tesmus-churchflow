from django.urls import path
from . import views

urlpatterns = [
    path('', views.service_list, name='attendance_service_list'),
    path('services/<int:pk>/', views.service_detail, name='attendance_service_detail'),
    path('checkin/<uuid:token>/', views.qr_checkin, name='qr_checkin'),
    path('usher/', views.usher_home, name='usher_home'),
    path('usher/services/<int:pk>/', views.usher_service, name='usher_service'),
    path('usher/services/<int:pk>/check-in/', views.usher_check_in, name='usher_check_in'),
]
