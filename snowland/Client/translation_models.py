from django.db import models


class SiteTranslation(models.Model):
    client = models.ForeignKey('Client.Client', on_delete=models.CASCADE, related_name='site_translations')
    scope = models.CharField(max_length=40)
    entries = models.JSONField(default=dict)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=('client', 'scope'), name='unique_site_translation_scope'),
        ]
