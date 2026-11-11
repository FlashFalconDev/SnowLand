from django.db import models


class RecruitmentForm(models.Model):
    client = models.OneToOneField('Client.Client', on_delete=models.CASCADE, related_name='recruitment_form')
    enabled = models.BooleanField(default=False)
    fields = models.JSONField(default=list)


class RecruitmentApplication(models.Model):
    client = models.ForeignKey('Client.Client', on_delete=models.PROTECT, related_name='recruitment_applications')
    submission_id = models.UUIDField()
    submitted_at = models.DateTimeField(auto_now_add=True)
    fields = models.JSONField()
    answers = models.JSONField()
    attachments = models.JSONField(default=dict)
    fingerprint = models.CharField(max_length=64)

    class Meta:
        ordering = ['-id']
        constraints = [
            models.UniqueConstraint(fields=['client', 'submission_id'], name='unique_recruitment_submission'),
        ]
