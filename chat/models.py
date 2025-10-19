from django.db import models

# Create your models here.
class ChatUser(models.Model):
	id = models.AutoField(primary_key=True)
	name = models.CharField(max_length=150)
	number = models.CharField(max_length=50, unique=True)
	password = models.CharField(max_length=128)  # store hashed or plain depending on implementation
	is_online = models.BooleanField(default=False)
	last_seen = models.DateTimeField(null=True, blank=True)
	def __str__(self):
		return f"{self.name} <{self.number}>"

class Presence(models.Model):
    user = models.ForeignKey(ChatUser, on_delete=models.CASCADE)
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(null=True, blank=True)
    device_name = models.CharField(max_length=150, null=True, blank=True)


class ChatMessage(models.Model):
	sender = models.ForeignKey(ChatUser, related_name='sent_chat_messages', on_delete=models.CASCADE)
	receiver = models.ForeignKey(ChatUser, related_name='received_chat_messages', on_delete=models.CASCADE)
	content = models.TextField()
	timestamp = models.DateTimeField(auto_now_add=True)
	delivered_at = models.DateTimeField(null=True, blank=True)
	seen_at = models.DateTimeField(null=True, blank=True)
 
	STATUS_CHOICES = [
			('sent', 'Sent'), # Single tick
			('delivered', 'Delivered'), # Double tick
			('read', 'Read'), # Blue tick
		]
	status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='sent')

	def __str__(self):
		return f"{self.sender} -> {self.receiver}: {self.content[:20]} ({self.status})"
