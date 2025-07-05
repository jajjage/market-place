from django.urls import path
from . import views

urlpatterns = [
    path('chat/', views.chat_room, name='chat_room'),
    path('chat/login/', views.simple_login, name='simple_login'),
]
