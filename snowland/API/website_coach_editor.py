"""CMS edits the existing coach's website fields, never operational/pay fields."""
from collections.abc import Mapping
import json
from django.db import transaction
from django.middleware.csrf import get_token
from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import SAFE_METHODS
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from Coach.models import Coach
from Client.coach_profiles import read_coach_profile,save_coach_profile
from .admin_views import IsTenantManager


class WebsiteCoachEditorSerializer(serializers.ModelSerializer):
    can_manage=serializers.SerializerMethodField()
    website_profile=serializers.JSONField(required=False)
    class Meta:
        model=Coach
        fields=['id','name','can_manage','img','website_enabled','website_slug','website_sort_order','website_card_bio','website_profile']
        read_only_fields=['id','name','can_manage']

    def get_can_manage(self, obj):
        request=self.context['request']
        if getattr(request,'can_view_all_campuses',False):
            return True
        assigned=set(obj.campuses.values_list('pk',flat=True))
        return bool(assigned) and assigned.issubset(set(request.campus_ids))

    def to_internal_value(self, data):
        if not isinstance(data,Mapping):
            return super().to_internal_value(data)
        editable=set(self.Meta.fields)-set(self.Meta.read_only_fields)
        if set(data)-editable:
            raise serializers.ValidationError({'non_field_errors':['此處僅能修改官網顯示欄位；姓名、排課及薪資請至教練管理']})
        return super().to_internal_value(data)

    def validate(self, attrs):
        if not self.get_can_manage(self.instance):
            raise serializers.ValidationError('此教練涉及其他校區，請由總部修改官網資料')
        slug=(attrs.get('website_slug',self.instance.website_slug) or '').strip().lower()
        enabled=attrs.get('website_enabled',self.instance.website_enabled)
        if enabled and not slug:
            raise serializers.ValidationError({'website_slug':'顯示於官網時需要填寫官網代號'})
        if slug and Coach.objects.filter(client=self.instance.client,website_slug__iexact=slug).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError({'website_slug':'官網代號已被其他教練使用'})
        attrs['website_slug']=slug
        if 'website_profile' in attrs:
            profile=attrs['website_profile']
            if not isinstance(profile,dict) or len(json.dumps(profile,ensure_ascii=False).encode('utf-8'))>250000:
                raise serializers.ValidationError({'website_profile':'介紹內容格式錯誤或過大，請縮減後重試'})
        return attrs

    def to_representation(self, instance):
        data=super().to_representation(instance)
        data['website_profile']=read_coach_profile(instance)
        return data

    @transaction.atomic
    def update(self, instance, validated_data):
        instance=Coach.objects.select_for_update().get(pk=instance.pk,client_id=instance.client_id)
        profile=validated_data.pop('website_profile',None)
        updated=super().update(instance,validated_data)
        if profile is not None:
            save_coach_profile(updated,profile,overwrite=True)
        return updated


class WebsiteCoachEditorViewSet(ModelViewSet):
    permission_classes=[IsTenantManager]
    permission_key='cms'
    serializer_class=WebsiteCoachEditorSerializer
    http_method_names=['get','patch','head','options']

    def initial(self, request, *args, **kwargs):
        super().initial(request,*args,**kwargs)
        if request.method in SAFE_METHODS:
            get_token(request._request)
        else:
            SessionAuthentication().enforce_csrf(request)

    def get_queryset(self):
        qs=Coach.objects.filter(client=self.request.tenant)
        if not self.request.can_view_all_campuses or self.request.selected_campus_id is not None:
            qs=qs.filter(campuses__id__in=self.request.campus_ids).distinct()
        return qs.order_by('website_sort_order','id')

    def list(self, request, *args, **kwargs):
        items=self.get_serializer(self.get_queryset(),many=True).data
        return Response({'code':200,'data':{'list':items,'total':len(items)}})

    def partial_update(self, request, *args, **kwargs):
        serializer=self.get_serializer(self.get_object(),data=request.data,partial=True)
        serializer.is_valid(raise_exception=True);serializer.save()
        return Response({'code':200,'msg':'官網教練資料已更新','data':serializer.data})
