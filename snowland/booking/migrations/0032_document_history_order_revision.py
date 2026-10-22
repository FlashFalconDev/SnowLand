from django.db import migrations, models
import django.db.models.deletion


def preserve_revision_links(apps, schema_editor):
    History=apps.get_model('booking','MemberCourseDocumentRevision')
    alias=schema_editor.connection.alias
    for row in History.objects.using(alias).select_related('amendment').iterator():
        History.objects.using(alias).filter(pk=row.pk).update(revision_id=row.amendment.revision_id)


class Migration(migrations.Migration):
    dependencies=[('booking','0031_member_course_document_revision')]
    operations=[
        migrations.AddField(model_name='membercoursedocumentrevision',name='revision',
            field=models.ForeignKey(null=True,on_delete=django.db.models.deletion.CASCADE,
                related_name='member_document_revisions',to='booking.orderrevision')),
        # A whole-class revision has no financial amendment; do not fabricate one
        # or silently discard evidence when attempting to reverse this migration.
        migrations.RunPython(preserve_revision_links),
        migrations.AlterField(model_name='membercoursedocumentrevision',name='revision',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                related_name='member_document_revisions',to='booking.orderrevision')),
        migrations.RemoveField(model_name='membercoursedocumentrevision',name='amendment'),
    ]
