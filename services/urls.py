from django.urls import path
from . import views

urlpatterns = [
    path('', views.service_list, name='service_list'),
    path('new/', views.service_create, name='service_create'),
    path('<int:pk>/', views.service_detail, name='service_detail'),
    path('<int:pk>/text-region-pastors/', views.service_send_region_summaries, name='service_send_region_summaries'),
    path('<int:pk>/checkin-poster/', views.service_checkin_poster, name='service_checkin_poster'),
    path('<int:pk>/new-checkin-link/', views.service_new_checkin_link, name='service_new_checkin_link'),
    path('<int:pk>/close-now/', views.service_close_now, name='service_close_now'),
]
