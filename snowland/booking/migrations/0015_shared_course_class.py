from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('Coursekit', '0018_shared_class_settings'),
        ('booking', '0014_reservation_ability_level_counts'),
    ]

    operations = [
        migrations.CreateModel(
            name='SharedCourseClass',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('start_time', models.TimeField()),
                ('end_time', models.TimeField()),
                ('ability_level', models.CharField(choices=[('no_exp', '等級 0'), ('level1', '等級 1'), ('level2', '等級 2'), ('level3', '等級 3'), ('level4', '等級 4'), ('level5', '等級 5'), ('level6', '等級 6')], max_length=20)),
                ('language', models.CharField(choices=[('zh', '中文'), ('en', '英文'), ('yue', '粵語')], default='zh', max_length=10)),
                ('opening_mode', models.CharField(choices=[('school', '學校開班'), ('customer', '客人發起')], default='customer', max_length=10)),
                ('status', models.CharField(choices=[('collecting', '湊班中'), ('ready', '已成班'), ('cancelled', '已取消')], default='collecting', max_length=12)),
                ('minimum_students', models.PositiveSmallIntegerField(default=3)),
                ('max_capacity', models.PositiveSmallIntegerField(default=6)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('campus', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='shared_course_classes', to='Resorts.campus')),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='shared_course_classes', to='Client.client')),
                ('resort', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='shared_course_classes', to='Resorts.resorts')),
                ('template', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='shared_course_classes', to='Coursekit.coursetemplate')),
            ],
        ),
        migrations.AddField(
            model_name='reservation',
            name='shared_course_class',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='reservations', to='booking.sharedcourseclass', verbose_name='跨訂單團體班'),
        ),
        migrations.AddConstraint(
            model_name='sharedcourseclass',
            constraint=models.UniqueConstraint(
                fields=('client', 'campus', 'resort', 'template', 'date', 'start_time', 'end_time', 'ability_level', 'language'),
                name='unique_shared_course_class_slot',
            ),
        ),
    ]
