from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('Coach', '0015_cash_manual_assignment')]

    operations = [
        migrations.AddField(
            model_name='coach',
            name='customer_selectable',
            field=models.BooleanField(
                default=True, verbose_name='顯示在客人指定教練名單',
                help_text='關閉不影響自動排課與後台人工指派。',
            ),
        ),
    ]
