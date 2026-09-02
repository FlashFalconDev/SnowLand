from django.db import migrations, models


def mark_existing_photo_categories(apps, schema_editor):
    CourseCategory = apps.get_model("Coursekit", "CourseCategory")
    photo_keywords = ["攝影", "旅拍", "Photography", "Photo", "photography", "photo"]
    for keyword in photo_keywords:
        CourseCategory.objects.filter(name__icontains=keyword).update(service_type="photo")


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("Coursekit", "0009_coursepricingtier"),
    ]

    operations = [
        migrations.AddField(
            model_name="coursecategory",
            name="service_type",
            field=models.CharField(
                choices=[("ski", "滑雪課程"), ("photo", "攝影服務")],
                db_index=True,
                default="ski",
                help_text="控制此分類出現在哪一種前台預約流程",
                max_length=20,
                verbose_name="服務類型",
            ),
        ),
        migrations.RunPython(mark_existing_photo_categories, noop_reverse),
    ]
