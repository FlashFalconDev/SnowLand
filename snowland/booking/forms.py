from django import forms
from .models import MemberDetail

class MemberDetailForm(forms.ModelForm):
    class Meta:
        model = MemberDetail
        fields = '__all__'  # 或者指定具体字段，如 ['age_range', 'snowboard_skills', 'ski_skills'] 