from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies=[('booking','0025_booking_course_template')]
    operations=[
        migrations.AddField(model_name='memberdetail',name='is_active',field=models.BooleanField(default=True,db_index=True,verbose_name='目前參課學員')),
        migrations.AddField(model_name='memberdetail',name='archived_at',field=models.DateTimeField(null=True,blank=True,verbose_name='退出課程留底時間')),
        migrations.AlterModelOptions(name='memberdetail',options={'verbose_name':'學員程度表單','verbose_name_plural':'2-3.學員程度表單',
            'default_manager_name':'objects','base_manager_name':'all_objects'}),
        migrations.AlterModelManagers(name='memberdetail',managers=[('objects',models.Manager()),('all_objects',models.Manager())]),
    ]
