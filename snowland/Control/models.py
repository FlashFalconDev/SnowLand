from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

# Create your models here.
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_manager = models.BooleanField(default=False)
    is_coach = models.BooleanField(default=False)
    admin_permissions = models.JSONField(default=None, blank=True, null=True)

    def __str__(self):
        return self.user.username
    class Meta:
        verbose_name = '使用者權限'
        verbose_name_plural = '使用者權限'

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
