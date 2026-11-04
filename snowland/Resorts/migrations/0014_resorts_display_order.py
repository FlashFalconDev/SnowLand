from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('Resorts', '0013_alter_resorts_name_and_more')]

    operations = [
        migrations.AddField(
            model_name='resorts',
            name='display_order',
            field=models.PositiveIntegerField(default=0, verbose_name='訂課顯示順序'),
        ),
    ]
