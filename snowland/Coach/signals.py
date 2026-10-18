from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import PayrollStatement


@receiver(post_delete, sender=PayrollStatement)
def delete_payroll_signature(sender, instance, **kwargs):
    if instance.signature_file.name:
        storage, name = instance.signature_file.storage, instance.signature_file.name
        transaction.on_commit(lambda: storage.delete(name), using=kwargs.get('using'), robust=True)
