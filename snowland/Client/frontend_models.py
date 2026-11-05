"""Durable, platform-only website publishing jobs shared by all web instances."""
from django.conf import settings
from django.db import models


class FrontendDeployment(models.Model):
    ACTIVE = ('queued', 'backing_up', 'publishing', 'invalidating', 'cleaning')
    client = models.ForeignKey('Client.Client', on_delete=models.PROTECT, related_name='frontend_deployments')
    release = models.ForeignKey('Client.FrontendRelease', on_delete=models.PROTECT, related_name='deployments')
    backup = models.ForeignKey('Client.FrontendRelease', on_delete=models.PROTECT, null=True, blank=True, related_name='backup_jobs')
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    operation = models.CharField(max_length=12, default='publish')
    status = models.CharField(max_length=20, default='queued', db_index=True)
    message = models.CharField(max_length=500, blank=True, default='')
    target = models.JSONField(default=dict)
    backup_headers = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-id']
