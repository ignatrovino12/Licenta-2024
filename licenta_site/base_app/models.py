from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    csrf_token = models.CharField(max_length=100)  

    def __str__(self):
        return self.user.username

