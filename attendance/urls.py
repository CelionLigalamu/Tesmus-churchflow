from django.urls import path
from . import views

urlpatterns = [
    path('checkin/<uuid:token>/', views.qr_checkin, name='qr_checkin'),
]