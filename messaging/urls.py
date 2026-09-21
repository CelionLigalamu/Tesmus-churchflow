from django.urls import path
from . import views

urlpatterns = [
    path('', views.message_list, name='message_list'),
    path('new/', views.message_create, name='message_create'),
    path('templates/', views.template_list, name='sms_template_list'),
    path('templates/<int:pk>/edit/', views.template_edit, name='sms_template_edit'),
    path('resend/', views.message_resend_many, name='message_resend_many'),
    path('status/', views.message_status, name='message_status'),
    path('<int:pk>/', views.message_detail, name='message_detail'),
    path('<int:pk>/resend/', views.message_resend, name='message_resend'),
]
