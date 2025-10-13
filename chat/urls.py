from django.urls import path, include
from . import views

urlpatterns = [
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('chat/', views.chat_list_view, name='chat_list'),
    path('chat/<str:username>/', views.chat_view, name='chat'),
    path('lobby/', views.lobby_view, name='lobby'),
]
