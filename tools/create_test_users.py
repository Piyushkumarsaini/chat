import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chat_app.settings')
import django
django.setup()
from chat.models import ChatUser

u1, created1 = ChatUser.objects.get_or_create(number='1', defaults={'name':'User1','password':'pwd'})
if created1:
    print('Created', u1.id)
else:
    print('Exists', u1.id)

u2, created2 = ChatUser.objects.get_or_create(number='2', defaults={'name':'User2','password':'pwd'})
if created2:
    print('Created', u2.id)
else:
    print('Exists', u2.id)
