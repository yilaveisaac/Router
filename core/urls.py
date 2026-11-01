from django.urls import path
from . import views
from django.views.generic import TemplateView


urlpatterns = [
     path('', views.index, name="index"),
     path('privacy/', TemplateView.as_view(template_name='privacy.html'), name='privacy'),
     path('guides/', views.guides_index, name='guides'),
     path('guides/<slug:slug>/', views.guide_detail, name='guide_detail'),
     path('api/route/', views.get_route_api, name='get_route_api'),
     path('api/locate/', views.locate_api, name='locate_api'),
]
