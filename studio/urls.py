from django.urls import path

from . import views

app_name = 'studio'
urlpatterns = [
    path('', views.studio, name='home'),
    path('audio/<uuid:public_id>/download/', views.download, name='download'),
    path('audio/<uuid:public_id>/delete/', views.delete, name='delete'),
    path('health/', views.health, name='health'),
]
