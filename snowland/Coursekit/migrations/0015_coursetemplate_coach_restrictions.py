from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Coach", "0008_coach_certifications"),
        ("Coursekit", "0014_coursetemplate_display_order"),
    ]

    operations = [
        migrations.AddField(
            model_name="coursetemplate",
            name="minimum_coach_price_level",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "不限制"),
                    ("Lv1", "Lv1 以上"),
                    ("Lv2", "Lv2 以上"),
                    ("Lv3", "Lv3 以上"),
                    ("director", "校長 / 總監"),
                ],
                default="",
                help_text="例如進階課程可設定 Lv2 以上。",
                max_length=20,
                verbose_name="最低教練等級",
            ),
        ),
        migrations.AddField(
            model_name="coursetemplate",
            name="allowed_coaches",
            field=models.ManyToManyField(
                blank=True,
                help_text="留空代表只看最低等級；選擇教練後，只有名單內教練可上。",
                related_name="allowed_course_templates",
                to="Coach.coach",
                verbose_name="指定可上課教練",
            ),
        ),
    ]
