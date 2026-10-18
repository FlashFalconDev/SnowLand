from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('booking','0024_memberdetail_insurance_processing'),('Coursekit','0019_coursetemplate_payroll_hours')]
    operations = [migrations.AddField(
        model_name='booking',name='course_template',field=models.ForeignKey(
            to='Coursekit.coursetemplate',null=True,blank=True,on_delete=django.db.models.deletion.SET_NULL,
            related_name='booking_sessions',verbose_name='每堂課程模板'))]
