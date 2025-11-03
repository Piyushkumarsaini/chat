from django.db import models
from django.utils import timezone
import pyotp
import time

class ChatUser(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=150)
    country_code = models.CharField(max_length=10, blank=True, null=True)
    number = models.CharField(max_length=20, unique=True)  # stores full number like +919876543210
    image = models.ImageField(upload_to='profile_images/', null=True, blank=True)
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=200, blank=True, default='Hey there! I am using In Chat.')

    # temporary OTP field
    otp_secret = models.CharField(max_length=6, blank=True, null=True)
    otp_timestamp = models.FloatField(blank=True, null=True)

    # Generate OTP using pyotp
    def generate_otp(self):
        self.otp_secret = pyotp.random_base32()
        self.otp_timestamp = time.time()
        otp = pyotp.TOTP(self.otp_secret, interval=300).now()  # Valid for 5 mins
        self.save()
        return otp
    
    # Verify OTP entered by user
    def verify_otp(self, otp_input):
        if not self.otp_secret:
            return False
        totp = pyotp.TOTP(self.otp_secret, interval=300)
        return totp.verify(otp_input)
    
    
    def update_last_seen(self):
        self.last_seen = timezone.now()
        self.is_online = False
        self.save()

    def __str__(self):
        return f"{self.name} ({self.number})"

class ChatMessage(models.Model):
    sender = models.ForeignKey(ChatUser, related_name='sent_chat_messages', on_delete=models.CASCADE)
    receiver = models.ForeignKey(ChatUser, related_name='received_chat_messages', on_delete=models.CASCADE)
    content = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    seen_at = models.DateTimeField(null=True, blank=True)

    attachment = models.FileField(upload_to='chat_uploads/', blank=True, null=True)
    attachment_type = models.CharField(max_length=20, blank=True, null=True)

    STATUS_CHOICES = [
            ('sent', 'Sent'), # Single tick
            ('delivered', 'Delivered'), # Double tick
            ('read', 'Read'), # Blue tick
        ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='sent')

    def __str__(self):
        display_text = self.content[:20] if self.content else (
            self.attachment.name if self.attachment else "[Empty]"
        )
        return f"{self.sender} -> {self.receiver}: {self.content[:20]} ({self.status})  {display_text}"
    
class TempUser(models.Model):
    country_code = models.CharField(max_length=10)
    number = models.CharField(max_length=15, unique=True)
    otp = models.CharField(max_length=6, blank=True, null=True)
    otp_secret = models.CharField(max_length=64, blank=True, null=True)  # 👈 add this
    otp_created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.country_code}{self.number}"
