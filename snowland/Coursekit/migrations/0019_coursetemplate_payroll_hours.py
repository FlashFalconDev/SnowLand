from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('Coursekit', '0018_shared_class_settings')]

    operations = [
        migrations.AddField(model_name='coursetemplate', name='payroll_hours',
            field=models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, default=None,
                validators=[MinValueValidator(0), MaxValueValidator(24)], verbose_name='每堂計薪時數',
                help_text='留空依上課時段計算；填0不計課程時薪，不影響排課或客人價格')),
    ]
