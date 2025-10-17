from django.db import models

# Create your models here.
class ChatUser(models.Model):
	id = models.AutoField(primary_key=True)
	name = models.CharField(max_length=150)
	number = models.CharField(max_length=50, unique=True)
	password = models.CharField(max_length=128)  # store hashed or plain depending on implementation

	def __str__(self):
		return f"{self.name} <{self.number}>"


class ChatMessage(models.Model):
	sender = models.ForeignKey(ChatUser, related_name='sent_chat_messages', on_delete=models.CASCADE)
	receiver = models.ForeignKey(ChatUser, related_name='received_chat_messages', on_delete=models.CASCADE)
	content = models.TextField()
	timestamp = models.DateTimeField(auto_now_add=True)
	is_delivered = models.BooleanField(default=False)
	is_seen = models.BooleanField(default=False)
 
	STATUS_CHOICES = [
			('sent', 'Sent'),
			('delivered', 'Delivered'),
			('read', 'Read'),
		]
	status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='sent')

	def __str__(self):
		return f"{self.sender.number} -> {self.receiver.number}: {self.content[:20]}"
