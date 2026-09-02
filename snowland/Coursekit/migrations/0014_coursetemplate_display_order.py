from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Coursekit", "0013_discountcode_amount_apply_mode"),
    ]

    operations = [
        migrations.AddField(
            model_name="coursetemplate",
            name="display_order",
            field=models.IntegerField(default=0, help_text="數字越小，前台排序越前面", verbose_name="顯示順序"),
        ),
        migrations.AlterModelOptions(
            name="coursetemplate",
            options={
                "ordering": [
                    "course_type__category__display_order",
                    "course_type__display_order",
                    "display_order",
                    "duration_hours",
                    "id",
                ],
                "verbose_name": "3. 課程模板",
                "verbose_name_plural": "3. 課程模板",
            },
        ),
    ]
