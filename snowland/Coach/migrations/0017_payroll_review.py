from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('Coach', '0016_coach_customer_selectable'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AlterField(model_name='payrollstatement', name='status', field=models.CharField(choices=[('draft', '草稿'), ('review', '待教練確認'), ('confirmed', '已確認'), ('paid', '已發放')], default='draft', max_length=20)),
        migrations.AddField(model_name='payrollstatement', name='published_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='payrollstatement', name='confirmation_deadline', field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name='payrollstatement', name='review_token', field=models.UUIDField(blank=True, editable=False, null=True)),
        migrations.AddField(model_name='payrollstatement', name='confirmed_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='payrollstatement', name='confirmation_method', field=models.CharField(blank=True, default='', max_length=20)),
        migrations.AddField(model_name='payrollstatement', name='confirmed_by', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='confirmed_coach_payrolls', to=settings.AUTH_USER_MODEL)),
    ]
