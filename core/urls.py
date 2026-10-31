from django.urls import path
from . import views


urlpatterns = [
     path('', views.index, name="index"),
     path('api/route/', views.get_route_api, name='get_route_api'),
     path('api/locate/', views.locate_api, name='locate_api'),
]
