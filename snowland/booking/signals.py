from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import CourseMedia, ReservationGroup


@receiver(post_delete, sender=CourseMedia)
def delete_private_course_file(sender, instance, **kwargs):
    if instance.file.name:
        storage, name = instance.file.storage, instance.file.name
        transaction.on_commit(lambda: storage.delete(name), using=kwargs.get('using'))


@receiver(post_delete, sender=ReservationGroup)
def delete_private_group_qr(sender, instance, **kwargs):
    if instance.line_group_qr.name:
        storage, name = instance.line_group_qr.storage, instance.line_group_qr.name
        transaction.on_commit(lambda: storage.delete(name), using=kwargs.get('using'), robust=True)
