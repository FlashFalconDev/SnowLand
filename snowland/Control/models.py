from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

# Create your models here.
class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('hq_admin', '總部管理員'),
        ('marketing', '行銷人員'),
        ('web_editor', '網頁人員'),
        ('insurance', '保險人員'),
        ('assistant', '行政小幫手'),
        ('campus_principal', '校區校長'),
        ('campus_manager', '校區主管'),
        ('coach', '教練'),
        ('photographer', '攝影人員'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_manager = models.BooleanField(default=False)
    is_coach = models.BooleanField(default=False)
    admin_permissions = models.JSONField(default=None, blank=True, null=True)
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, blank=True, default='')
    campuses = models.ManyToManyField('Resorts.Campus', blank=True, related_name='staff_profiles')

    def __str__(self):
        return self.user.username
    class Meta:
        verbose_name = '使用者權限'
        verbose_name_plural = '使用者權限'

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
