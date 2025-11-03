from django.urls import path, include
from . import views

urlpatterns = [
    path('api/signup/', views.signup_view, name='signup'),
    path('check-phone/', views.check_phone, name='check_phone'),
    path('send-otp/', views.send_otp, name='send_otp'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('complete-signup/', views.complete_signup, name='complete_signup'),
    
    path('login/', views.phone_login_page, name='phone_login_page'),
    path('api/send-otp/', views.phone_login, name='phone_login'),
    path('api/verify-otp/', views.login_verify_otp, name='verify_otp'),
    # 
    path('logout/', views.logout_view, name='logout'),
    path('chat/', views.chat_view, name='chat_list'),
    path('api/chat/<str:number>/messages/', views.get_chat_messages, name='get_chat_messages'),

    # path('lobby/', views.lobby_view, name='lobby'),
    path('profile/get/', views.get_profile, name='get_profile'),
    path('update_profile/', views.update_profile, name='update_profile'),
    path('chat/upload_attachment/', views.upload_attachment, name='upload_attachment'),
]