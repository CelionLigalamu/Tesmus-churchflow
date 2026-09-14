from django.urls import path
from . import views

urlpatterns = [
    path('', views.service_list, name='service_list'),
    path('new/', views.service_create, name='service_create'),
    path('<int:pk>/', views.service_detail, name='service_detail'),
    path('<int:pk>/text-region-pastors/', views.service_send_region_summaries, name='service_send_region_summaries'),
]
