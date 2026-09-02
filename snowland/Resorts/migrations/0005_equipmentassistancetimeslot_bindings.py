# Generated manually to bind equipment assistance slots to booking context.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Resorts", "0004_equipmentassistancetimeslot"),
    ]

    operations = [
        migrations.AddField(
            model_name="equipmentassistancetimeslot",
            name="equipment_option",
            field=models.CharField(
                choices=[
                    ("purchaseAssistanceTime", "加購協助時間"),
                    ("assistDuringCourse", "課程時間內協助"),
                    ("rentWithoutyourself", "自行租借不須協助"),
                    ("ownWithoutAssistance", "自備裝備不須協助"),
                ],
                default="purchaseAssistanceTime",
                max_length=40,
                verbose_name="Equipment option",
            ),
        ),
        migrations.AddField(
            model_name="equipmentassistancetimeslot",
            name="lesson_duration",
            field=models.CharField(
                choices=[("any", "不限"), ("full_day", "全天"), ("half_day", "半天")],
                default="any",
                max_length=20,
                verbose_name="Lesson duration",
            ),
        ),
        migrations.AddField(
            model_name="equipmentassistancetimeslot",
            name="session_period",
            field=models.CharField(
                choices=[
                    ("any", "不限"),
                    ("all_day", "全天課"),
                    ("morning", "上午課"),
                    ("afternoon", "下午課"),
                ],
                default="any",
                max_length=20,
                verbose_name="Session period",
            ),
        ),
        migrations.AddField(
            model_name="equipmentassistancetimeslot",
            name="day_type",
            field=models.CharField(
                choices=[("same_day", "當天"), ("previous_day", "前一日")],
                default="same_day",
                max_length=20,
                verbose_name="Day type",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="equipmentassistancetimeslot",
            unique_together={("resort", "equipment_option", "lesson_duration", "session_period", "day_type", "label")},
        ),
        migrations.AlterModelOptions(
            name="equipmentassistancetimeslot",
            options={
                "ordering": [
                    "resort",
                    "equipment_option",
                    "lesson_duration",
                    "session_period",
                    "display_order",
                    "start_time",
                    "id",
                ],
                "verbose_name": "Equipment assistance time slot",
                "verbose_name_plural": "Equipment assistance time slots",
            },
        ),
    ]
