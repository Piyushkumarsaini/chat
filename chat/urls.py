from django.contrib import admin
from . import views

urlpatterns = [
    path('signup/', views.signup_view, name='signup'),
]
