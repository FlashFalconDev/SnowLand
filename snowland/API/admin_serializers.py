"""
後台管理用 Serializer
跟前端使用的 serializer 不同，這些回傳完整資訊（含 nested 關聯）
給管理員看的，不過濾欄位
"""
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from django.contrib.auth.models import User
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from copy import deepcopy
from uuid import uuid4
from Client.models import SiteContent
from Coach.models import (
    Coach, CoachResort, CoachCourseLevel, CoachLeaveRequest, normalize_ability_levels,
    CoachPayRule, PayrollStatement, PayrollLine, StaffIncentiveRule,
)
from Resorts.models import (
    Resorts, ResortFee, EquipmentPricingTier, EquipmentAssistanceTimeSlot, EquipmentRentalItem,
    Campus, PaymentAccount, OperatingPolicy,
)
from Coursekit.models import CourseCategory, CourseType, CourseTemplate, CourseSession, CoursePricing, CoursePricingTier, SeasonSetting, DiscountCode
from booking.models import (
    ReservationGroup, Reservation, Booking, MemberDetail, Payment,
    CancellationRequest, CourseEvaluation, CourseMedia, NotificationTemplate,
    NotificationDelivery, OrderRevision, StaffBookingLink,
)
from booking.staff_link_snapshot import public_staff_cart_snapshot
from booking.marketing_source import display_marketing_source
from .admin_permissions import user_has_admin_permission


class TenantRelationValidationMixin:
    def _tenant(self):
        request = self.context.get('request')
        return getattr(request, 'tenant', None) if request else None

    def _validate_tenant_relations(self, attrs, relation_names):
        tenant = self._tenant()
        for relation_name in relation_names:
            for obj in attrs.get(relation_name, []):
                if getattr(obj, 'client_id', None) != getattr(tenant, 'id', None):
                    raise serializers.ValidationError({relation_name: '不能選擇其他公司的資料'})
        return attrs


class CampusAdminSerializer(TenantRelationValidationMixin, serializers.ModelSerializer):
    code = serializers.SlugField(max_length=50, required=False, allow_blank=True)
    resort_ids = serializers.PrimaryKeyRelatedField(
        source='resorts', many=True, queryset=Resorts.objects.all(), required=False
    )
    resort_names = serializers.SerializerMethodField()
    staff_count = serializers.SerializerMethodField()
    coach_count = serializers.SerializerMethodField()

    class Meta:
        model = Campus
        fields = [
            'id', 'name', 'code', 'description', 'is_active', 'display_order',
            'resort_ids', 'resort_names', 'staff_count', 'coach_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'resort_names', 'staff_count', 'coach_count', 'created_at', 'updated_at']

    def validate(self, attrs):
        self._validate_tenant_relations(attrs, ['resorts'])
        code = attrs.get('code')
        if self.instance is None and not code:
            code = f'campus-{uuid4().hex}'
            attrs['code'] = code
        elif self.instance is not None and code == '':
            raise serializers.ValidationError({'code': '內部代碼不能留空'})
        if code:
            existing = Campus.objects.filter(client=self._tenant(), code__iexact=code)
            if self.instance is not None:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError({'code': '這個內部代碼已被其他校區使用，請換一個'})
        return attrs

    def get_resort_names(self, obj):
        return [resort.display_name for resort in obj.resorts.all()]

    def get_staff_count(self, obj):
        return obj.staff_profiles.count()

    def get_coach_count(self, obj):
        return obj.coaches.count()

    def create(self, validated_data):
        resorts = validated_data.pop('resorts', [])
        campus = Campus.objects.create(client=self._tenant(), **validated_data)
        campus.resorts.set(resorts)
        return campus


class PaymentAccountAdminSerializer(TenantRelationValidationMixin, serializers.ModelSerializer):
    campus_ids = serializers.PrimaryKeyRelatedField(
        source='campuses', many=True, queryset=Campus.objects.all(), required=False
    )
    resort_ids = serializers.PrimaryKeyRelatedField(
        source='resorts', many=True, queryset=Resorts.objects.all(), required=False
    )

    class Meta:
        model = PaymentAccount
        fields = [
            'id', 'name', 'bank_name', 'bank_branch', 'account_number', 'account_holder',
            'overseas_details', 'campus_ids', 'resort_ids', 'is_default', 'is_active',
            'display_order', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        attrs = self._validate_tenant_relations(attrs, ['campuses', 'resorts'])
        is_active = attrs.get('is_active', self.instance.is_active if self.instance else True)
        if is_active:
            required_bank_fields = ('bank_name', 'bank_branch', 'account_number', 'account_holder')
            missing_fields = [field for field in required_bank_fields if not str(
                attrs.get(field, getattr(self.instance, field, '') if self.instance else '')
            ).strip()]
            if missing_fields:
                raise serializers.ValidationError({field: '啟用收款帳戶前請填寫此欄位' for field in missing_fields})
        campuses = list(attrs.get('campuses', self.instance.campuses.all() if self.instance else []))
        resorts = list(attrs.get('resorts', self.instance.resorts.all() if self.instance else []))
        if campuses and resorts:
            selected_campus_ids = [campus.id for campus in campuses]
            selected_resort_ids = set(Resorts.objects.filter(
                client=self._tenant(), campuses__id__in=selected_campus_ids,
            ).values_list('id', flat=True))
            if any(resort.id not in selected_resort_ids for resort in resorts):
                raise serializers.ValidationError({'resort_ids': '只能選擇指定校區可使用的雪場'})
        request = self.context.get('request')
        if request and not getattr(request, 'can_view_all_campuses', False):
            allowed_ids = set(getattr(request, 'campus_ids', []))
            if self.instance:
                if not set(self.instance.campuses.values_list('id', flat=True)).issubset(allowed_ids):
                    raise serializers.ValidationError({'campus_ids': '此帳戶也適用其他校區，請由總部管理員修改'})
            if not campuses or any(campus.id not in allowed_ids for campus in campuses):
                raise serializers.ValidationError({'campus_ids': '只能設定自己管理的校區'})
            allowed_resort_ids = set(Resorts.objects.filter(
                client=self._tenant(), campuses__id__in=allowed_ids,
            ).values_list('id', flat=True))
            if any(resort.id not in allowed_resort_ids for resort in resorts):
                raise serializers.ValidationError({'resort_ids': '只能設定自己校區可用的雪場'})
        return attrs

    def create(self, validated_data):
        campuses = validated_data.pop('campuses', [])
        resorts = validated_data.pop('resorts', [])
        account = PaymentAccount.objects.create(client=self._tenant(), **validated_data)
        account.campuses.set(campuses)
        account.resorts.set(resorts)
        return account


class OperatingPolicyAdminSerializer(TenantRelationValidationMixin, serializers.ModelSerializer):
    campus_name = serializers.CharField(source='campus.name', read_only=True, default='全公司預設')

    class Meta:
        model = OperatingPolicy
        fields = [
            'id', 'campus', 'campus_name', 'unpaid_hold_days', 'provisional_extra_groups',
            'cancellation_fee_percent', 'cancellation_rules', 'leave_advance_days',
            'leave_daily_coach_limit', 'leave_max_consecutive_days', 'course_reminder_days',
            'settings', 'updated_at',
        ]
        read_only_fields = ['id', 'campus_name', 'updated_at']

    def validate_campus(self, value):
        if value and value.client_id != getattr(self._tenant(), 'id', None):
            raise serializers.ValidationError('不能選擇其他公司的校區')
        return value

    def validate_cancellation_rules(self, value):
        if not isinstance(value, list) or not value:
            raise serializers.ValidationError('至少需要一條退費規則')
        seen_days = set()
        for rule in value:
            if not isinstance(rule, dict) or 'days_before' not in rule or 'refund_percent' not in rule:
                raise serializers.ValidationError('每條規則需要 days_before 與 refund_percent')
            days, percent = rule['days_before'], rule['refund_percent']
            if type(days) is not int or days < 0 or days in seen_days:
                raise serializers.ValidationError('天數須為不重複的非負整數')
            if type(percent) is not int or not 0 <= percent <= 100:
                raise serializers.ValidationError('退費比例須為 0 到 100 的整數')
            seen_days.add(days)
        return sorted(value, key=lambda item: int(item['days_before']), reverse=True)

    def validate_cancellation_fee_percent(self, value):
        if not 0 <= value <= 100:
            raise serializers.ValidationError('手續費百分比須介於 0 到 100')
        return value

    def validate(self, attrs):
        campus = attrs.get('campus', getattr(self.instance, 'campus', None))
        request = self.context.get('request')
        if request and not getattr(request, 'can_view_all_campuses', False):
            allowed_ids = set(getattr(request, 'campus_ids', []))
            if self.instance and self.instance.campus_id not in allowed_ids:
                raise serializers.ValidationError({'campus': '全公司預設只能由總部管理員修改'})
            if not campus or campus.id not in allowed_ids:
                raise serializers.ValidationError({'campus': '只能設定自己管理的校區'})
        duplicate = OperatingPolicy.objects.filter(client=self._tenant(), campus=campus)
        if self.instance:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise serializers.ValidationError({'campus': '這個範圍已有營運規則'})
        return attrs

    def create(self, validated_data):
        if validated_data.get('campus'):
            company_policy = OperatingPolicy.objects.filter(client=self._tenant(), campus__isnull=True).first()
            if company_policy:
                for field in (
                    'unpaid_hold_days', 'provisional_extra_groups', 'cancellation_fee_percent',
                    'cancellation_rules', 'leave_advance_days', 'leave_daily_coach_limit',
                    'leave_max_consecutive_days', 'course_reminder_days', 'settings',
                ):
                    validated_data.setdefault(field, deepcopy(getattr(company_policy, field)))
        return OperatingPolicy.objects.create(client=self._tenant(), **validated_data)


# ==================== Site Content ====================

class SiteContentAdminSerializer(serializers.ModelSerializer):
    computed_status = serializers.CharField(read_only=True)

    class Meta:
        model = SiteContent
        fields = [
            'id', 'content_type', 'location_key',
            'title', 'subtitle', 'summary', 'body',
            'image_url', 'link_url', 'source', 'external_id',
            'tags', 'metadata', 'status', 'computed_status',
            'start_at', 'end_at', 'display_order', 'is_pinned',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'computed_status', 'created_at', 'updated_at']

    def validate_tags(self, value):
        if value in (None, ''):
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(',') if item.strip()]
        if not isinstance(value, list):
            raise serializers.ValidationError('標籤必須是清單')
        return [str(item).strip() for item in value if str(item).strip()]

    def validate_metadata(self, value):
        if value in (None, ''):
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError('其他設定必須是物件')
        return value

    def validate(self, attrs):
        content_type=attrs.get('content_type',getattr(self.instance,'content_type',None))
        location = attrs.get('location_key', getattr(self.instance, 'location_key', None))
        metadata = attrs.get('metadata', getattr(self.instance, 'metadata', {}))
        external_id = attrs.get('external_id', getattr(self.instance, 'external_id', ''))
        if location in ('homepage.hero','homepage.intro','homepage.coaches','homepage.contact'):
            from Client.homepage_presentation import validate_homepage_presentation
            try:
                attrs['metadata'] = validate_homepage_presentation(attrs,self.instance,getattr(self.context.get('request'),'tenant',None))
            except ValueError as exc:
                raise serializers.ValidationError({'metadata':str(exc)})
        if location == 'course.areas':
            from Client.course_areas import validate_course_area
            try:
                attrs['metadata'] = validate_course_area(attrs, self.instance, getattr(self.context.get('request'), 'tenant', None))
            except ValueError as exc:
                raise serializers.ValidationError({'metadata': str(exc)})
        if location == 'homepage.courses':
            from Client.article_pages import safe_article_url
            if content_type != 'page':
                raise serializers.ValidationError({'content_type': '熱門課程請使用頁面類型'})
            for field in ('link_url', 'image_url'):
                value = attrs.get(field, getattr(self.instance, field, ''))
                if not safe_article_url(value):
                    raise serializers.ValidationError({field: '請使用完整http/https網址或站內路徑'})
            if attrs.get('status', getattr(self.instance, 'status', 'draft')) == 'active':
                for field in ('title', 'link_url'):
                    if not attrs.get(field, getattr(self.instance, field, '')).strip():
                        raise serializers.ValidationError({field: '公開熱門課程前請填寫名稱與課程連結'})
        if location in ('about.snowland', 'about.join-us'):
            from Client.about_pages import validate_about_metadata
            try:
                attrs['metadata'] = validate_about_metadata(metadata, attrs.get('status', getattr(self.instance, 'status', 'draft')) == 'active', 'about' if location == 'about.snowland' else 'join-us')
            except ValueError as exc:
                raise serializers.ValidationError({'metadata': str(exc)})
        if location in ('offers.earlybird','offers.referral','offers.promo'):
            from Client.article_pages import validate_offer_metadata
            try:
                attrs['metadata'] = validate_offer_metadata(metadata,
                    attrs.get('status',getattr(self.instance,'status','draft'))=='active',
                    attrs.get('image_url',getattr(self.instance,'image_url','')))
            except ValueError as exc:
                raise serializers.ValidationError({'metadata':str(exc)})
        if location == 'guides.articles':
            from Client.article_pages import validate_guide_article
            try:
                attrs['metadata'] = validate_guide_article(attrs, self.instance)
            except ValueError as exc:
                raise serializers.ValidationError({'metadata': str(exc)})
        if location == 'guides.packing' or (location == 'guides.article-pages' and (external_id == 'packing-checklist' or isinstance(metadata, dict) and 'article' in metadata)):
            from Client.article_pages import validate_article_metadata
            try:
                attrs['metadata'] = validate_article_metadata(metadata, attrs.get('status', getattr(self.instance, 'status', 'draft')) == 'active')
            except ValueError as exc:
                raise serializers.ValidationError({'metadata': str(exc)})
        if content_type == 'page' and location in ('photography.winter', 'photography.summer'):
            from Client.photography_pages import validate_photography_metadata
            try:
                attrs['metadata'] = validate_photography_metadata(
                    attrs.get('metadata', getattr(self.instance, 'metadata', {})), location.rsplit('.', 1)[1],
                    attrs.get('status', getattr(self.instance, 'status', 'draft')) == 'active',
                )
            except ValueError as exc:
                raise serializers.ValidationError({'metadata': str(exc)})
        if content_type == 'media' and location == 'photography.gallery':
            from Client.photography_gallery import validate_gallery
            try:
                attrs['metadata'] = validate_gallery(
                    attrs.get('metadata', getattr(self.instance, 'metadata', {})),
                    attrs.get('image_url', getattr(self.instance, 'image_url', '')),
                    attrs.get('status', getattr(self.instance, 'status', 'draft')) == 'active',
                )
            except ValueError as exc:
                raise serializers.ValidationError({'metadata': str(exc)})
        if content_type=='review' and 'metadata' in attrs:
            from Client.coach_reviews import validate_review_metadata
            try:
                validate_review_metadata(attrs['metadata'],getattr(self.context.get('request'),'tenant',None))
            except ValueError as exc:
                raise serializers.ValidationError({'metadata':str(exc)})
        start_at = attrs.get('start_at', getattr(self.instance, 'start_at', None))
        end_at = attrs.get('end_at', getattr(self.instance, 'end_at', None))
        if start_at and end_at and end_at < start_at:
            raise serializers.ValidationError({'end_at': '結束時間不能早於開始時間'})
        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        client = getattr(request, 'tenant', None) if request else None
        return SiteContent.objects.create(client=client, **validated_data)


# ==================== Coach ====================

class CoachResortNestedSerializer(serializers.ModelSerializer):
    resort_id = serializers.IntegerField(source='resort.id', read_only=True)
    resort_name = serializers.CharField(source='resort.display_name', read_only=True)

    class Meta:
        model = CoachResort
        fields = ['resort_id', 'resort_name', 'resort_priority', 'assignment_score']


class CoachCourseLevelNestedSerializer(serializers.ModelSerializer):
    course_type_id = serializers.IntegerField(source='course_type.id', read_only=True)
    course_type_name = serializers.CharField(source='course_type.name', read_only=True)
    ability_levels = serializers.SerializerMethodField()

    class Meta:
        model = CoachCourseLevel
        fields = ['course_type_id', 'course_type_name', 'ability_levels', 'price_level', 'course_order']

    def get_ability_levels(self, obj):
        return normalize_ability_levels(obj.ability_levels)


class CoachCertificationsField(serializers.ListField):
    """Keep older string-only certification rows readable by the admin API."""

    child = serializers.DictField()

    def to_representation(self, data):
        normalized = []
        for item in data if isinstance(data, list) else []:
            if isinstance(item, dict):
                normalized.append(item)
                continue
            if not isinstance(item, str) or not item.strip():
                continue
            value = item.strip()
            certificate, separator, level_number = value.rpartition(' Level ')
            upper_value = value.upper()
            category = 'snowboard' if any(name in upper_value for name in ('CASI', 'JSBA', 'SBINZ')) else 'ski' if any(name in upper_value for name in ('CSIA', 'NZSIA', 'SIA')) else 'other'
            normalized.append({
                'category': category,
                'certificate': certificate if separator else value,
                'level': f'Level {level_number}' if separator else '',
                'note': '',
                'show_on_website': True,
            })
        return super().to_representation(normalized)


class CoachAdminSerializer(serializers.ModelSerializer):
    resorts = serializers.SerializerMethodField()
    course_levels = serializers.SerializerMethodField()
    campus_ids = serializers.SerializerMethodField()
    campus_assignments = serializers.SerializerMethodField()
    can_manage = serializers.SerializerMethodField()
    campus_ids_input = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False, allow_empty=False
    )
    user_id = serializers.IntegerField(required=False, allow_null=True)
    user_email = serializers.CharField(source='user.email', read_only=True, default=None)
    user_name = serializers.SerializerMethodField()
    user_username = serializers.CharField(source='user.username', read_only=True, default='')
    img = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    languages = serializers.ListField(child=serializers.CharField(), required=False)
    certifications = CoachCertificationsField(required=False, allow_empty=True)
    resorts_input = serializers.ListField(
        child=serializers.DictField(), write_only=True, required=False, allow_empty=True
    )
    course_levels_input = serializers.ListField(
        child=serializers.DictField(), write_only=True, required=False, allow_empty=True
    )

    class Meta:
        model = Coach
        fields = [
            'id', 'name', 'user_id', 'user_email', 'user_name', 'user_username',
            'languages', 'availability_status', 'auto_assignment_enabled', 'customer_selectable', 'schedule_visibility', 'assignment_score', 'img',
            'website_enabled', 'website_slug', 'website_sort_order', 'website_card_bio',
            'certifications',
            'campus_ids', 'campus_assignments', 'can_manage', 'campus_ids_input',
            'resorts', 'course_levels',
            'resorts_input', 'course_levels_input',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def validate(self, attrs):
        website_enabled = attrs.get('website_enabled', getattr(self.instance, 'website_enabled', False))
        website_slug = (attrs.get('website_slug', getattr(self.instance, 'website_slug', '')) or '').strip()
        if website_enabled and not website_slug:
            raise serializers.ValidationError({'website_slug': '顯示於官網時需要填寫官網代號'})

        request = self.context.get('request')
        client = getattr(request, 'tenant', None) if request else getattr(self.instance, 'client', None)
        if website_slug:
            queryset = Coach.objects.filter(website_slug=website_slug)
            if client:
                queryset = queryset.filter(client=client)
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError({'website_slug': '官網代號已被其他教練使用'})

        attrs['website_slug'] = website_slug
        if 'user_id' in attrs:
            user_id = attrs.get('user_id')
            if user_id:
                if not User.objects.filter(pk=user_id).exists():
                    raise serializers.ValidationError({'user_id': '找不到此會員帳號'})
                queryset = Coach.objects.filter(user_id=user_id)
                if self.instance:
                    queryset = queryset.exclude(pk=self.instance.pk)
                existing_coach = queryset.first()
                if existing_coach:
                    raise serializers.ValidationError({
                        'user_id': f'該會員已經綁定教練「{existing_coach.name}」，不能重複綁定'
                    })
        if 'certifications' in attrs:
            attrs['certifications'] = self._clean_certifications(attrs.get('certifications'))

        campus_ids = attrs.get('campus_ids_input')
        if campus_ids is not None:
            campuses = Campus.objects.filter(client=client, id__in=campus_ids) if client else Campus.objects.none()
            retained_inactive_ids = set()
            if self.instance and request and getattr(request, 'can_view_all_campuses', False):
                retained_inactive_ids = set(self.instance.campuses.filter(is_active=False).values_list('id', flat=True))
            if campuses.count() != len(set(campus_ids)) or any(
                not campus.is_active and campus.id not in retained_inactive_ids for campus in campuses
            ):
                raise serializers.ValidationError({'campus_ids_input': '請選擇有效的校區'})
            if request and not getattr(request, 'can_view_all_campuses', False):
                if not set(campus_ids).issubset(set(getattr(request, 'campus_ids', []))):
                    raise serializers.ValidationError({'campus_ids_input': '只能設定自己管理的校區'})

        if 'resorts_input' in attrs:
            resort_ids = {item.get('resort_id') for item in attrs['resorts_input'] if item.get('resort_id')}
            resorts = Resorts.objects.filter(client=client, id__in=resort_ids)
            if resorts.count() != len(resort_ids):
                raise serializers.ValidationError({'resorts_input': '只能選擇此公司的雪場'})
            if request and not getattr(request, 'can_view_all_campuses', False):
                allowed = set(getattr(request, 'campus_ids', []))
                if resorts.exclude(campuses__id__in=allowed).exists():
                    raise serializers.ValidationError({'resorts_input': '只能選擇自己校區可用的雪場'})

        if 'course_levels_input' in attrs:
            type_ids = {item.get('course_type_id') for item in attrs['course_levels_input'] if item.get('course_type_id')}
            if CourseType.objects.filter(category__client=client, id__in=type_ids).count() != len(type_ids):
                raise serializers.ValidationError({'course_levels_input': '只能選擇此公司的課程類型'})
        return attrs

    def get_campus_ids(self, obj):
        return list(obj.campuses.values_list('id', flat=True))

    def get_campus_assignments(self, obj):
        return [
            {'id': campus.id, 'name': campus.name, 'is_active': campus.is_active}
            for campus in obj.campuses.all().order_by('display_order', 'id')
        ]

    def get_can_manage(self, obj):
        request = self.context.get('request')
        if not request:
            return False
        if getattr(request, 'can_view_all_campuses', False):
            return True
        assigned = set(obj.campuses.values_list('id', flat=True))
        return bool(assigned) and assigned.issubset(set(getattr(request, 'campus_ids', [])))

    def get_user_name(self, obj):
        if not obj.user:
            return ''
        return obj.user.get_full_name() or obj.user.username

    def _clean_certifications(self, certifications):
        if not isinstance(certifications, list):
            return []

        cleaned = []
        allowed_categories = {'ski', 'snowboard', 'photo', 'other'}
        level_aliases = {
            'Lv1': 'Level 1',
            'Lv2': 'Level 2',
            'Lv3': 'Level 3',
            'Lv4': 'Level 4',
            'LV1': 'Level 1',
            'LV2': 'Level 2',
            'LV3': 'Level 3',
            'LV4': 'Level 4',
        }
        for item in certifications:
            if not isinstance(item, dict):
                continue

            category = (item.get('category') or 'other').strip()
            if category not in allowed_categories:
                category = 'other'

            certificate = (item.get('certificate') or '').strip()
            level = (item.get('level') or '').strip()
            level = level_aliases.get(level, level)
            note = (item.get('note') or '').strip()
            if not certificate and not level and not note:
                continue

            cleaned.append({
                'category': category,
                'certificate': certificate,
                'level': level,
                'note': note,
                'show_on_website': bool(item.get('show_on_website', True)) and category != 'photo',
            })

        return cleaned

    def get_resorts(self, obj):
        return CoachResortNestedSerializer(
            CoachResort.objects.filter(coach=obj).select_related('resort'),
            many=True
        ).data

    def get_course_levels(self, obj):
        return CoachCourseLevelNestedSerializer(
            CoachCourseLevel.objects.filter(coach=obj).select_related('course_type'),
            many=True
        ).data

    def create(self, validated_data):
        campus_ids = validated_data.pop('campus_ids_input', None)
        resorts_input = validated_data.pop('resorts_input', [])
        course_levels_input = validated_data.pop('course_levels_input', [])
        request = self.context.get('request')
        client = getattr(request, 'tenant', None) if request else None

        if campus_ids is None:
            accessible = list(getattr(request, 'campus_ids', [])) if request else []
            if len(accessible) != 1:
                raise serializers.ValidationError({'campus_ids_input': '請先選擇教練所屬校區'})
            campus_ids = accessible
        self._sync_coach_permission(validated_data.get('user_id'))
        coach = Coach.objects.create(client=client, **validated_data)
        coach.campuses.set(Campus.objects.filter(client=client, id__in=campus_ids))
        self._sync_resorts(coach, resorts_input)
        self._sync_course_levels(coach, course_levels_input)
        return coach

    def update(self, instance, validated_data):
        campus_ids = validated_data.pop('campus_ids_input', None)
        resorts_input = validated_data.pop('resorts_input', None)
        course_levels_input = validated_data.pop('course_levels_input', None)
        if 'user_id' in validated_data:
            self._sync_coach_permission(validated_data.get('user_id'))
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if campus_ids is not None:
            instance.campuses.set(Campus.objects.filter(client=instance.client, id__in=campus_ids))
        if resorts_input is not None:
            self._sync_resorts(instance, resorts_input)
        if course_levels_input is not None:
            self._sync_course_levels(instance, course_levels_input)
        return instance

    def _sync_coach_permission(self, user_id):
        if not user_id:
            return
        try:
            from Control.models import UserProfile
            profile, _ = UserProfile.objects.get_or_create(user_id=user_id)
            if not profile.is_coach:
                profile.is_coach = True
                profile.save(update_fields=['is_coach'])
        except Exception as exc:
            raise serializers.ValidationError({'user_id': f'會員已選擇，但開啟教練權限失敗：{exc}'})

    def _sync_resorts(self, coach, resorts_input):
        CoachResort.objects.filter(coach=coach).delete()
        for item in resorts_input:
            resort_id = item.get('resort_id')
            if not resort_id:
                continue
            try:
                resort = Resorts.objects.get(id=resort_id)
            except Resorts.DoesNotExist:
                continue
            assignment_score = item.get('assignment_score')
            if assignment_score is None:
                assignment_score = coach.assignment_score
            CoachResort.objects.create(
                coach=coach,
                resort=resort,
                resort_priority=item.get('resort_priority', 0),
                assignment_score=assignment_score,
            )

    def _sync_course_levels(self, coach, course_levels_input):
        CoachCourseLevel.objects.filter(coach=coach).delete()
        for item in course_levels_input:
            course_type_id = item.get('course_type_id')
            if not course_type_id:
                continue
            try:
                course_type = CourseType.objects.get(id=course_type_id)
            except CourseType.DoesNotExist:
                continue
            CoachCourseLevel.objects.create(
                coach=coach,
                course_type=course_type,
                ability_levels=normalize_ability_levels(item.get('ability_levels', [])),
                price_level=item.get('price_level', 'Lv1'),
                course_order=item.get('course_order', 0),
            )


# ==================== CoachLeaveRequest ====================

class CoachLeaveRequestAdminSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M', read_only=True)
    reviewed_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M', read_only=True)
    can_review = serializers.SerializerMethodField()
    review_block_reason = serializers.SerializerMethodField()
    coach_name = serializers.CharField(source='coach.name', read_only=True)
    coach_img = serializers.CharField(source='coach.img', read_only=True, default='')
    leave_days = serializers.ReadOnlyField()
    affected_count = serializers.SerializerMethodField()
    reviewed_by_name = serializers.CharField(source='reviewed_by.username', read_only=True, default=None)

    class Meta:
        model = CoachLeaveRequest
        fields = [
            'id', 'coach', 'coach_name', 'coach_img',
            'start_date', 'end_date', 'leave_days', 'reason',
            'status', 'affected_count', 'processing_result',
            'reviewed_by', 'reviewed_by_name', 'reviewed_at',
            'created_at', 'updated_at',
            'can_review', 'review_block_reason',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'reviewed_at', 'reviewed_by']

    def get_affected_count(self, obj):
        request = self.context.get('request')
        qs = obj.affected_reservations.all()
        if not request:
            return 0
        qs = qs.filter(group__client=getattr(request, 'tenant', None))
        if not (getattr(request, 'can_view_all_campuses', False) and request.selected_campus_id is None):
            qs = qs.filter(group__campus_id__in=getattr(request, 'campus_ids', []))
        return qs.count()

    def get_review_block_reason(self, obj):
        request = self.context.get('request')
        if not request or not user_has_admin_permission(request.user, 'coaches'):
            return '沒有請假審核權限'
        profile = getattr(request.user, 'userprofile', None)
        if not request.user.is_superuser and profile and profile.role == 'assistant':
            return '行政小幫手僅能查看請假紀錄'
        if obj.status != 'pending':
            return '此申請已處理，不能重複審核'
        if getattr(request, 'can_view_all_campuses', False) and request.selected_campus_id is None:
            return ''
        assigned = {campus.pk for campus in obj.coach.campuses.all()}
        if not assigned or not assigned.issubset(set(getattr(request, 'campus_ids', []))):
            return '此請假涉及其他校區，請由總部在全部校區範圍審核'
        return ''

    def get_can_review(self, obj):
        return not self.get_review_block_reason(obj)


# ==================== Resorts ====================

class ResortFeeNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResortFee
        fields = ['fee_type', 'price', 'is_active', 'description']


class EquipmentPricingTierNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipmentPricingTier
        fields = ['id', 'min_people', 'max_people', 'price', 'is_active', 'display_order', 'description']
        read_only_fields = ['id']


class EquipmentRentalItemNestedSerializer(serializers.ModelSerializer):
    daily_price = serializers.IntegerField(min_value=0)

    class Meta:
        model = EquipmentRentalItem
        fields = ['id', 'code', 'name', 'daily_price', 'additional_day_price', 'is_active', 'display_order', 'description']
        read_only_fields = ['id']


class EquipmentAssistanceTimeSlotNestedSerializer(serializers.ModelSerializer):
    course_template_ids = serializers.SerializerMethodField()
    course_template_names = serializers.SerializerMethodField()

    class Meta:
        model = EquipmentAssistanceTimeSlot
        fields = [
            'id', 'equipment_option', 'lesson_duration', 'session_period', 'day_type',
            'course_template_ids', 'course_template_names',
            'label', 'start_time', 'end_time', 'is_active', 'display_order', 'description',
        ]
        read_only_fields = ['id']

    def get_course_template_ids(self, obj):
        return list(obj.course_templates.values_list('id', flat=True))

    def get_course_template_names(self, obj):
        return [template.name for template in obj.course_templates.all()]


class ResortAdminSerializer(serializers.ModelSerializer):
    trail_names = serializers.ListField(
        child=serializers.CharField(max_length=120, error_messages={'blank': '雪道名稱不能空白', 'max_length': '每條雪道名稱最多120字'}),
        max_length=100, required=False,
        error_messages={'not_a_list': '雪道資料必須是清單', 'null': '雪道清單不能是空值，未設定請使用空清單', 'max_length': '雪道清單最多100條'},
    )
    can_manage = serializers.SerializerMethodField()
    campus_assignments = serializers.SerializerMethodField()
    fees = serializers.SerializerMethodField()
    equipment_tiers = serializers.SerializerMethodField()
    equipment_rental_items = serializers.SerializerMethodField()
    equipment_time_slots = serializers.SerializerMethodField()
    fees_input = ResortFeeNestedSerializer(many=True, write_only=True, required=False)
    equipment_tiers_input = EquipmentPricingTierNestedSerializer(many=True, write_only=True, required=False)
    equipment_rental_items_input = EquipmentRentalItemNestedSerializer(many=True, write_only=True, required=False)
    equipment_time_slots_input = serializers.ListField(
        child=serializers.DictField(), write_only=True, required=False, allow_empty=True
    )

    class Meta:
        model = Resorts
        fields = [
            'id', 'name', 'display_name', 'auto_scheduling_enabled', 'trail_names', 'can_manage', 'campus_assignments',
            'fees', 'equipment_tiers', 'equipment_rental_items', 'equipment_time_slots',
            'fees_input', 'equipment_tiers_input', 'equipment_rental_items_input', 'equipment_time_slots_input',
        ]
        read_only_fields = ['id']

    def validate_trail_names(self, value):
        return list(dict.fromkeys(value))

    def get_fees(self, obj):
        return ResortFeeNestedSerializer(
            ResortFee.objects.filter(resort=obj),
            many=True
        ).data

    def get_can_manage(self, obj):
        request = self.context.get('request')
        return bool(request and (
            user_has_admin_permission(request.user, 'resorts') and (
                getattr(request, 'can_view_all_campuses', False) or sum(
                    campus.is_active for campus in obj.campuses.all()
                ) == 1
            )
        ))

    def get_campus_assignments(self, obj):
        request = self.context.get('request')
        allowed_ids = None if request and getattr(request, 'can_view_all_campuses', False) else set(
            getattr(request, 'campus_ids', []) if request else []
        )
        campuses = sorted(obj.campuses.all(), key=lambda campus: (campus.display_order, campus.id))
        return [
            {'id': campus.id, 'name': campus.name, 'is_active': campus.is_active}
            for campus in campuses if allowed_ids is None or campus.id in allowed_ids
        ]

    def get_equipment_tiers(self, obj):
        return EquipmentPricingTierNestedSerializer(
            obj.equipment_pricing_tiers.all(),
            many=True
        ).data

    def get_equipment_rental_items(self, obj):
        return EquipmentRentalItemNestedSerializer(
            obj.equipment_rental_items.all(),
            many=True
        ).data

    def get_equipment_time_slots(self, obj):
        return EquipmentAssistanceTimeSlotNestedSerializer(
            obj.equipment_assistance_time_slots.all(),
            many=True
        ).data

    def validate_fees_input(self, fees):
        seen_types = set()
        for fee in fees:
            if 'fee_type' not in fee or 'price' not in fee:
                raise serializers.ValidationError('每項雪場費用都需填寫類型與金額')
            if fee['fee_type'] in seen_types:
                raise serializers.ValidationError('同一種雪場費用不能重複設定')
            seen_types.add(fee['fee_type'])
        return fees

    def validate_equipment_tiers_input(self, tiers):
        self._validate_tiers(tiers)
        return tiers

    def validate_equipment_rental_items_input(self, items):
        self._validate_equipment_rental_items(items)
        return items

    def validate_equipment_time_slots_input(self, slots):
        self._validate_time_slots(slots)
        return slots

    def create(self, validated_data):
        fees_input = validated_data.pop('fees_input', [])
        equipment_tiers_input = validated_data.pop('equipment_tiers_input', [])
        equipment_rental_items_input = validated_data.pop('equipment_rental_items_input', [])
        equipment_time_slots_input = validated_data.pop('equipment_time_slots_input', [])
        request = self.context.get('request')
        client = getattr(request, 'tenant', None) if request else None
        with transaction.atomic():
            resort = Resorts.objects.create(client=client, **validated_data)
            self._sync_fees(resort, fees_input)
            self._sync_equipment_tiers(resort, equipment_tiers_input)
            self._sync_equipment_rental_items(resort, equipment_rental_items_input)
            self._validate_time_slot_templates(resort, equipment_time_slots_input)
            self._sync_equipment_time_slots(resort, equipment_time_slots_input)
        return resort

    def update(self, instance, validated_data):
        fees_input = validated_data.pop('fees_input', None)
        equipment_tiers_input = validated_data.pop('equipment_tiers_input', None)
        equipment_rental_items_input = validated_data.pop('equipment_rental_items_input', None)
        equipment_time_slots_input = validated_data.pop('equipment_time_slots_input', None)
        with transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            if fees_input is not None:
                self._sync_fees(instance, fees_input)
            if equipment_tiers_input is not None:
                self._sync_equipment_tiers(instance, equipment_tiers_input)
            if equipment_rental_items_input is not None:
                self._sync_equipment_rental_items(instance, equipment_rental_items_input)
            if equipment_time_slots_input is not None:
                self._validate_time_slot_templates(instance, equipment_time_slots_input)
                self._sync_equipment_time_slots(instance, equipment_time_slots_input)
        return instance

    def _sync_fees(self, resort, fees_input):
        synced_types = set()
        for item in fees_input:
            fee_type = item.get('fee_type')
            price = item.get('price')
            if not fee_type or price is None:
                continue
            ResortFee.objects.update_or_create(
                resort=resort,
                fee_type=fee_type,
                defaults={
                    'price': price,
                    'is_active': item.get('is_active', True),
                    'description': item.get('description', ''),
                },
            )
            synced_types.add(fee_type)
        ResortFee.objects.filter(resort=resort).exclude(fee_type__in=synced_types).delete()

    def _sync_equipment_tiers(self, resort, equipment_tiers_input):
        self._validate_tiers(equipment_tiers_input)
        synced_ids = []
        for index, item in enumerate(equipment_tiers_input):
            min_people = item.get('min_people')
            max_people = item.get('max_people')
            price = item.get('price')
            if min_people is None or max_people is None or price is None:
                continue
            tier, _ = EquipmentPricingTier.objects.update_or_create(
                resort=resort,
                min_people=min_people,
                max_people=max_people,
                defaults={
                    'price': price,
                    'is_active': item.get('is_active', True),
                    'display_order': item.get('display_order', index),
                    'description': item.get('description', ''),
                },
            )
            synced_ids.append(tier.id)
        EquipmentPricingTier.objects.filter(resort=resort).exclude(id__in=synced_ids).delete()

    def _sync_equipment_rental_items(self, resort, items_input):
        self._validate_equipment_rental_items(items_input)
        synced_ids = []
        for index, item in enumerate(items_input):
            code = (item.get('code') or '').strip()
            name = (item.get('name') or '').strip()
            if not code or not name:
                continue
            rental_item, _ = EquipmentRentalItem.objects.update_or_create(
                resort=resort,
                code=code,
                defaults={
                    'name': name,
                    'daily_price': int(item['daily_price']),
                    'additional_day_price': int(item.get('additional_day_price') or 0),
                    'is_active': item.get('is_active', True),
                    'display_order': item.get('display_order', index),
                    'description': item.get('description', ''),
                },
            )
            synced_ids.append(rental_item.id)
        EquipmentRentalItem.objects.filter(resort=resort).exclude(id__in=synced_ids).delete()

    def _sync_equipment_time_slots(self, resort, equipment_time_slots_input):
        self._validate_time_slots(equipment_time_slots_input)
        synced_ids = []
        for index, item in enumerate(equipment_time_slots_input):
            label = (item.get('label') or '').strip()
            if not label:
                continue
            lookup = {
                'resort': resort,
                'equipment_option': item.get('equipment_option') or 'purchaseAssistanceTime',
                'lesson_duration': item.get('lesson_duration') or 'any',
                'session_period': item.get('session_period') or 'any',
                'day_type': item.get('day_type') or 'same_day',
                'label': label,
            }
            slot, _ = EquipmentAssistanceTimeSlot.objects.update_or_create(
                **lookup,
                defaults={
                    'start_time': item.get('start_time') or None,
                    'end_time': item.get('end_time') or None,
                    'is_active': item.get('is_active', True),
                    'display_order': item.get('display_order', index),
                    'description': item.get('description', ''),
                },
            )
            synced_ids.append(slot.id)
            course_template_ids = self._normalize_course_template_ids(
                item.get('course_template_ids') or item.get('course_templates') or []
            )
            slot.course_templates.set(
                CourseTemplate.objects.filter(id__in=course_template_ids, resorts=resort).distinct()
            )
        self._remove_stale_equipment_time_slots(resort, synced_ids)

    def _remove_stale_equipment_time_slots(self, resort, synced_ids):
        stale_slots = EquipmentAssistanceTimeSlot.objects.filter(resort=resort).exclude(id__in=synced_ids)
        for slot in stale_slots:
            if slot.reservations.exists():
                if slot.is_active:
                    slot.is_active = False
                    slot.save(update_fields=['is_active'])
                continue
            slot.delete()

    def _validate_tiers(self, tiers):
        active_ranges = []
        seen_ranges = set()
        for item in tiers:
            if not all(field in item for field in ('min_people', 'max_people', 'price')):
                raise serializers.ValidationError('Equipment tier people range and price are required')
            min_people = item['min_people']
            max_people = item['max_people']
            price = item['price']
            if min_people < 1 or max_people < min_people:
                raise serializers.ValidationError('Invalid equipment people range')
            if price < 0:
                raise serializers.ValidationError('Equipment tier price cannot be negative')
            key = (min_people, max_people)
            if key in seen_ranges:
                raise serializers.ValidationError('Equipment people ranges cannot duplicate')
            seen_ranges.add(key)
            if item.get('is_active', True) is False:
                continue
            for start, end in active_ranges:
                if min_people <= end and max_people >= start:
                    raise serializers.ValidationError('Equipment people ranges cannot overlap')
            active_ranges.append((min_people, max_people))

    def _validate_equipment_rental_items(self, items):
        seen_codes = set()
        for item in items:
            code = (item.get('code') or '').strip()
            name = (item.get('name') or '').strip()
            if 'daily_price' not in item:
                raise serializers.ValidationError('Equipment rental item daily price is required')
            daily_price = item['daily_price']
            additional_day_price = item.get('additional_day_price') or 0
            if not code or not name:
                raise serializers.ValidationError('Equipment rental item code and name are required')
            if daily_price < 0 or additional_day_price < 0:
                raise serializers.ValidationError('Equipment rental item prices cannot be negative')
            normalized_code = code.lower()
            if normalized_code in seen_codes:
                raise serializers.ValidationError('Equipment rental item codes cannot duplicate')
            seen_codes.add(normalized_code)

    def _validate_time_slots(self, slots):
        seen_keys = set()
        valid_equipment_options = {value for value, _ in EquipmentAssistanceTimeSlot.EQUIPMENT_OPTION_CHOICES}
        valid_lesson_durations = {value for value, _ in EquipmentAssistanceTimeSlot.LESSON_DURATION_CHOICES}
        valid_session_periods = {value for value, _ in EquipmentAssistanceTimeSlot.SESSION_PERIOD_CHOICES}
        valid_day_types = {value for value, _ in EquipmentAssistanceTimeSlot.DAY_TYPE_CHOICES}
        for item in slots:
            label = (item.get('label') or '').strip()
            equipment_option = item.get('equipment_option') or 'purchaseAssistanceTime'
            lesson_duration = item.get('lesson_duration') or 'any'
            session_period = item.get('session_period') or 'any'
            day_type = item.get('day_type') or 'same_day'
            if not label:
                raise serializers.ValidationError('Equipment time slot label is required')
            if equipment_option not in valid_equipment_options:
                raise serializers.ValidationError('Invalid equipment option for time slot')
            if lesson_duration not in valid_lesson_durations:
                raise serializers.ValidationError('Invalid lesson duration for equipment time slot')
            if session_period not in valid_session_periods:
                raise serializers.ValidationError('Invalid session period for equipment time slot')
            if day_type not in valid_day_types:
                raise serializers.ValidationError('Invalid day type for equipment time slot')
            for field in ('start_time', 'end_time'):
                if item.get(field):
                    serializers.TimeField().run_validation(item[field])
            self._normalize_course_template_ids(item.get('course_template_ids') or item.get('course_templates') or [])
            key = (equipment_option, lesson_duration, session_period, day_type, label.lower())
            if key in seen_keys:
                raise serializers.ValidationError('Equipment time slot labels cannot duplicate in the same binding')
            seen_keys.add(key)

    def _normalize_course_template_ids(self, values):
        if values in (None, ''):
            return []
        if not isinstance(values, (list, tuple)):
            raise serializers.ValidationError('course_template_ids must be a list')
        ids = []
        for value in values:
            try:
                template_id = int(value)
            except (TypeError, ValueError):
                raise serializers.ValidationError('course_template_ids must contain numbers')
            if template_id > 0 and template_id not in ids:
                ids.append(template_id)
        return ids

    def _validate_time_slot_templates(self, resort, slots):
        requested_ids = set()
        for item in slots:
            requested_ids.update(self._normalize_course_template_ids(
                item.get('course_template_ids') or item.get('course_templates') or []
            ))
        if not requested_ids:
            return

        valid_ids = set(
            CourseTemplate.objects.filter(id__in=requested_ids, resorts=resort).values_list('id', flat=True)
        )
        invalid_ids = sorted(requested_ids - valid_ids)
        if invalid_ids:
            raise serializers.ValidationError(
                f'Course templates must belong to this resort: {invalid_ids}'
            )


# ==================== CourseKit ====================

class CourseSessionAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseSession
        fields = ['id', 'template', 'start_time', 'end_time', 'is_active']

    def validate(self, attrs):
        start_time = attrs.get('start_time', getattr(self.instance, 'start_time', None))
        end_time = attrs.get('end_time', getattr(self.instance, 'end_time', None))
        if start_time is not None and end_time is not None and end_time <= start_time:
            raise serializers.ValidationError({'end_time': '結束時間必須晚於開始時間'})
        return attrs


class CourseTemplateAdminSerializer(serializers.ModelSerializer):
    payroll_hours = serializers.DecimalField(max_digits=4, decimal_places=2, min_value=0, max_value=24, allow_null=True, required=False)
    can_manage_payroll_hours = serializers.SerializerMethodField()
    sessions = CourseSessionAdminSerializer(many=True, read_only=True)  # related_name='sessions'
    can_manage = serializers.SerializerMethodField()
    resort_names = serializers.SerializerMethodField()
    resorts = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Resorts.objects.all(), required=False
    )
    allowed_coaches = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Coach.objects.all(), required=False
    )
    allowed_coach_names = serializers.SerializerMethodField()
    minimum_coach_price_level_label = serializers.SerializerMethodField()
    course_type_name = serializers.CharField(source='course_type.name', read_only=True)

    class Meta:
        model = CourseTemplate
        fields = [
            'id', 'can_manage', 'course_type', 'course_type_name', 'name',
            'display_order', 'duration_hours', 'payroll_hours', 'can_manage_payroll_hours', 'max_capacity', 'is_active',
            'billing_mode', 'minimum_group_size', 'shared_class_enabled',
            'shared_class_minimum_students', 'minimum_student_level',
            'resorts', 'resort_names',
            'booking_open_date', 'booking_close_date',
            'course_start_date', 'course_end_date',
            'minimum_coach_price_level', 'minimum_coach_price_level_label',
            'allowed_coaches', 'allowed_coach_names',
            'sessions',
        ]
        read_only_fields = ['id']

    def _limited_scope_ids(self):
        request = self.context.get('request')
        if not request or (getattr(request, 'can_view_all_campuses', False)
                           and not getattr(request, 'selected_campus_id', None)):
            return None
        return set(getattr(request, 'campus_ids', []))

    def _visible_resorts(self, obj):
        allowed = self._limited_scope_ids()
        resorts = obj.resorts.all()
        if allowed is None:
            return list(resorts)
        return [resort for resort in resorts if allowed.intersection(
            campus.id for campus in resort.campuses.all()
        )]

    def _visible_coaches(self, obj):
        allowed = self._limited_scope_ids()
        coaches = obj.allowed_coaches.all()
        if allowed is None:
            return list(coaches)
        return [coach for coach in coaches if allowed.intersection(
            campus.id for campus in coach.campuses.all()
        )]

    def get_can_manage(self, obj):
        allowed = self._limited_scope_ids()
        if allowed is None:
            return True
        resorts = list(obj.resorts.all())
        if not resorts:
            return False
        for resort in resorts:
            campus_ids = [campus.id for campus in resort.campuses.all() if campus.is_active]
            if len(campus_ids) != 1 or campus_ids[0] not in allowed:
                return False
        return True

    def get_can_manage_payroll_hours(self, obj):
        request = self.context.get('request')
        return self.get_can_manage(obj) and user_has_admin_permission(getattr(request, 'user', None), 'payroll')

    def get_resort_names(self, obj):
        return [resort.display_name for resort in self._visible_resorts(obj)]

    def get_allowed_coach_names(self, obj):
        return [coach.name for coach in self._visible_coaches(obj)]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if self._limited_scope_ids() is not None:
            data['resorts'] = [resort.id for resort in self._visible_resorts(instance)]
            data['allowed_coaches'] = [coach.id for coach in self._visible_coaches(instance)]
        return data

    def get_minimum_coach_price_level_label(self, obj):
        return obj.get_minimum_coach_price_level_display()

    def validate(self, attrs):
        request = self.context.get('request')
        tenant = getattr(request, 'tenant', None)
        if 'payroll_hours' in attrs and attrs['payroll_hours'] != getattr(self.instance, 'payroll_hours', None):
            if not user_has_admin_permission(getattr(request, 'user', None), 'payroll'):
                raise PermissionDenied('需要薪資管理權限才能修改計薪時數')
        course_type = attrs.get('course_type', getattr(self.instance, 'course_type', None))
        if not course_type or course_type.category.client_id != getattr(tenant, 'id', None):
            raise serializers.ValidationError({'course_type': '不能選擇其他公司的課程'})
        for resort in attrs.get('resorts', []):
            if resort.client_id != tenant.id:
                raise serializers.ValidationError({'resorts': '不能選擇其他公司的雪場'})
        if request and (not getattr(request, 'can_view_all_campuses', False)
                        or getattr(request, 'selected_campus_id', None)):
            resorts = attrs.get('resorts', self.instance.resorts.all() if self.instance else [])
            allowed_ids = set(getattr(request, 'campus_ids', []))
            if not resorts:
                raise serializers.ValidationError({
                    'resorts': '只能設定自己校區的非共用雪場；共用雪場請由總部設定'
                })
            for resort in resorts:
                campus_ids = list(resort.campuses.filter(is_active=True).values_list('id', flat=True))
                if len(campus_ids) != 1 or campus_ids[0] not in allowed_ids:
                    raise serializers.ValidationError({
                        'resorts': '只能設定自己校區的非共用雪場；共用雪場請由總部設定'
                    })
        for coach in attrs.get('allowed_coaches', []):
            if coach.client_id != tenant.id:
                raise serializers.ValidationError({'allowed_coaches': '不能選擇其他公司的教練'})
        if request and (not getattr(request, 'can_view_all_campuses', False)
                        or getattr(request, 'selected_campus_id', None)):
            allowed_ids = set(getattr(request, 'campus_ids', []))
            coaches = attrs.get('allowed_coaches', self.instance.allowed_coaches.all() if self.instance else [])
            for coach in coaches:
                coach_campus_ids = set(coach.campuses.filter(is_active=True).values_list('id', flat=True))
                if not coach_campus_ids or not coach_campus_ids.issubset(allowed_ids):
                    raise serializers.ValidationError({'allowed_coaches': '只能選擇自己校區的教練'})
        minimum = attrs.get('minimum_group_size', getattr(self.instance, 'minimum_group_size', 1))
        capacity = attrs.get('max_capacity', getattr(self.instance, 'max_capacity', 1))
        if minimum > capacity:
            raise serializers.ValidationError({'minimum_group_size': '單筆預約最低人數不能大於最大人數'})
        shared_enabled = attrs.get('shared_class_enabled', getattr(self.instance, 'shared_class_enabled', False))
        if shared_enabled and not settings.SHARED_CLASS_FEATURE_ENABLED:
            raise serializers.ValidationError({'shared_class_enabled': '團體湊班尚未開放，請使用一般課程設定'})
        billing_mode = attrs.get('billing_mode', getattr(self.instance, 'billing_mode', 'private'))
        shared_minimum = attrs.get('shared_class_minimum_students', getattr(self.instance, 'shared_class_minimum_students', 3))
        if shared_enabled and billing_mode != 'per_person':
            raise serializers.ValidationError({'shared_class_enabled': '跨訂單湊班必須使用每人計價'})
        if shared_enabled and (shared_minimum < 2 or shared_minimum > capacity):
            raise serializers.ValidationError({'shared_class_minimum_students': '成班人數須介於 2 人與最大人數之間'})
        if shared_enabled:
            attrs['minimum_group_size'] = 1
        return attrs


class CourseTypeAdminSerializer(TenantRelationValidationMixin, serializers.ModelSerializer):
    templates = CourseTemplateAdminSerializer(many=True, read_only=True)  # related_name='templates'
    available_resorts = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Resorts.objects.all(), required=False
    )
    available_resort_names = serializers.SerializerMethodField()

    class Meta:
        model = CourseType
        fields = [
            'id', 'category', 'name', 'display_order',
            'available_resorts', 'available_resort_names', 'templates',
        ]
        read_only_fields = ['id']

    def get_available_resort_names(self, obj):
        return [r.display_name for r in obj.available_resorts.all()]

    def validate(self, attrs):
        category = attrs.get('category', getattr(self.instance, 'category', None))
        if not category or category.client_id != getattr(self._tenant(), 'id', None):
            raise serializers.ValidationError({'category': '不能選擇其他公司的課程大類'})
        return self._validate_tenant_relations(attrs, ['available_resorts'])


class CourseCategoryAdminSerializer(TenantRelationValidationMixin, serializers.ModelSerializer):
    types = CourseTypeAdminSerializer(many=True, read_only=True)  # related_name='types'
    available_resorts = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Resorts.objects.all(), required=False
    )
    available_resort_names = serializers.SerializerMethodField()

    class Meta:
        model = CourseCategory
        fields = [
            'id', 'name', 'service_type', 'display_order',
            'available_resorts', 'available_resort_names', 'types',
        ]
        read_only_fields = ['id']

    def get_available_resort_names(self, obj):
        return [r.display_name for r in obj.available_resorts.all()]

    def validate(self, attrs):
        return self._validate_tenant_relations(attrs, ['available_resorts'])

    def create(self, validated_data):
        request = self.context.get('request')
        client = getattr(request, 'tenant', None) if request else None
        available_resorts = validated_data.pop('available_resorts', [])
        instance = CourseCategory.objects.create(client=client, **validated_data)
        if available_resorts:
            instance.available_resorts.set(available_resorts)
        return instance


# ==================== CoursePricing / SeasonSetting ====================

class CoursePricingTierAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = CoursePricingTier
        fields = ['id', 'min_people', 'max_people', 'price', 'is_active', 'display_order']
        read_only_fields = ['id']


class CoursePricingAdminSerializer(serializers.ModelSerializer):
    """課程定價:一筆規則綁多個 template + 一個 resort"""
    templates = serializers.PrimaryKeyRelatedField(
        many=True, queryset=CourseTemplate.objects.all()
    )
    template_names = serializers.SerializerMethodField()
    resort_name = serializers.CharField(source='resort.display_name', read_only=True)
    people_tiers = CoursePricingTierAdminSerializer(many=True, required=False)

    class Meta:
        model = CoursePricing
        fields = [
            'id',
            'templates', 'template_names',
            'resort', 'resort_name',
            'base_price_off_peak', 'peak_season_surcharge',
            'additional_person_fee', 'max_capacity',
            'people_tiers',
            'is_active',
        ]
        read_only_fields = ['id']

    def get_template_names(self, obj):
        return [t.name for t in obj.templates.all()]

    def validate_people_tiers(self, tiers):
        active_ranges = []
        for tier in tiers:
            if tier.get('is_active', True) is False:
                continue
            min_people = int(tier.get('min_people') or 0)
            max_people = int(tier.get('max_people') or 0)
            price = int(tier.get('price') or 0)
            if min_people < 1 or max_people < min_people:
                raise serializers.ValidationError('Invalid people range')
            if price < 0:
                raise serializers.ValidationError('Tier price cannot be negative')
            for start, end in active_ranges:
                if min_people <= end and max_people >= start:
                    raise serializers.ValidationError('People ranges cannot overlap')
            active_ranges.append((min_people, max_people))
        return tiers

    def validate(self, attrs):
        tiers = attrs.get('people_tiers')
        max_capacity = attrs.get('max_capacity') or getattr(self.instance, 'max_capacity', None)
        templates = attrs.get('templates')
        if templates is None and self.instance:
            templates = self.instance.templates.all()
        if not templates:
            raise serializers.ValidationError({'templates': '請至少選擇一個適用課程'})
        request = self.context.get('request')
        tenant = getattr(request, 'tenant', None) if request else None
        resort = attrs.get('resort', self.instance.resort if self.instance else None)
        if tenant and resort and resort.client_id != tenant.id:
            raise serializers.ValidationError({'resort': '只能選擇此公司的雪場'})
        if tenant and any(template.course_type.category.client_id != tenant.id for template in (templates or [])):
            raise serializers.ValidationError({'templates': '只能選擇此公司的課程模板'})
        billing_modes = {template.billing_mode for template in templates}
        if len(billing_modes) > 1:
            raise serializers.ValidationError({
                'templates': '包班計價與每人計價不能共用同一組價格，請分開設定。'
            })
        if resort and templates is not None:
            # Legacy prices may already reference a template that is no longer offered
            # at this resort. Keep them editable, but do not create new orphan prices.
            legacy_template_ids = set()
            if self.instance and self.instance.resort_id == resort.id:
                legacy_template_ids = set(self.instance.templates.values_list('id', flat=True))
            unavailable = [
                template.id for template in templates
                if template.id not in legacy_template_ids
                and not template.resorts.filter(id=resort.id).exists()
            ]
            if unavailable:
                raise serializers.ValidationError({
                    'templates': '選取的課程尚未開放此雪場，請先到課程架構設定適用雪場。'
                })
        if request and not getattr(request, 'can_view_all_campuses', False) and resort:
            campus_ids = list(resort.campuses.filter(is_active=True).values_list('id', flat=True))
            if len(campus_ids) != 1 or campus_ids[0] not in getattr(request, 'campus_ids', []):
                raise serializers.ValidationError({'resort': '只能設定自己校區的非共用雪場；共用雪場請由總部設定'})
        if tiers and max_capacity:
            for tier in tiers:
                if tier.get('is_active', True) and int(tier.get('max_people') or 0) > int(max_capacity):
                    raise serializers.ValidationError('People tier cannot exceed max_capacity')
        return attrs

    def create(self, validated_data):
        tiers_data = validated_data.pop('people_tiers', [])
        pricing = super().create(validated_data)
        self._sync_people_tiers(pricing, tiers_data)
        return pricing

    def update(self, instance, validated_data):
        tiers_data = validated_data.pop('people_tiers', None)
        pricing = super().update(instance, validated_data)
        if tiers_data is not None:
            self._sync_people_tiers(pricing, tiers_data)
        return pricing

    def _sync_people_tiers(self, pricing, tiers_data):
        pricing.people_tiers.all().delete()
        for index, tier in enumerate(tiers_data):
            CoursePricingTier.objects.create(
                pricing=pricing,
                min_people=tier['min_people'],
                max_people=tier['max_people'],
                price=tier['price'],
                is_active=tier.get('is_active', True),
                display_order=tier.get('display_order', index),
            )


class DiscountCodeAdminSerializer(serializers.ModelSerializer):
    discount_type_label = serializers.CharField(source='get_discount_type_display', read_only=True)
    amount_apply_mode_label = serializers.CharField(source='get_amount_apply_mode_display', read_only=True)
    apply_scope_label = serializers.CharField(source='get_apply_scope_display', read_only=True)

    class Meta:
        model = DiscountCode
        fields = [
            'id',
            'code', 'name', 'description',
            'discount_type', 'discount_type_label',
            'amount_apply_mode', 'amount_apply_mode_label',
            'discount_value', 'max_discount_amount', 'min_order_amount',
            'apply_scope', 'apply_scope_label',
            'require_multiple_items', 'can_combine',
            'is_auto_apply', 'new_customer_only',
            'usage_limit', 'used_count',
            'start_at', 'end_at',
            'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'used_count', 'created_at', 'updated_at']

    def validate_code(self, value):
        value = (value or '').strip().upper()
        if not value:
            raise serializers.ValidationError('折扣碼不可空白')
        return value

    def validate(self, attrs):
        discount_type = attrs.get('discount_type') or getattr(self.instance, 'discount_type', None)
        discount_value = attrs.get('discount_value', getattr(self.instance, 'discount_value', 0))
        max_discount_amount = attrs.get('max_discount_amount', getattr(self.instance, 'max_discount_amount', None))
        usage_limit = attrs.get('usage_limit', getattr(self.instance, 'usage_limit', None))
        used_count = getattr(self.instance, 'used_count', 0)
        start_at = attrs.get('start_at', getattr(self.instance, 'start_at', None))
        end_at = attrs.get('end_at', getattr(self.instance, 'end_at', None))

        if discount_value <= 0:
            raise serializers.ValidationError('折扣數值必須大於 0')
        if discount_type == DiscountCode.DISCOUNT_TYPE_PERCENT and discount_value > 100:
            raise serializers.ValidationError('百分比折扣不可超過 100')
        if max_discount_amount is not None and max_discount_amount <= 0:
            raise serializers.ValidationError('最高折抵金額必須大於 0')
        if usage_limit is not None and usage_limit < used_count:
            raise serializers.ValidationError('使用上限不可小於已使用次數')
        if start_at and end_at and start_at > end_at:
            raise serializers.ValidationError('結束時間不能早於開始時間')
        return attrs

    def create(self, validated_data):
        client = self.context['request'].tenant
        return DiscountCode.objects.create(client=client, **validated_data)


class SeasonSettingAdminSerializer(serializers.ModelSerializer):
    """旺/淡季區間"""
    class Meta:
        model = SeasonSetting
        fields = ['id', 'name', 'season_type', 'start_date', 'end_date']
        read_only_fields = ['id']

    def validate(self, attrs):
        start = attrs.get('start_date') or getattr(self.instance, 'start_date', None)
        end = attrs.get('end_date') or getattr(self.instance, 'end_date', None)
        if start and end and start > end:
            raise serializers.ValidationError('開始日期不能晚於結束日期')
        return attrs


# ==================== Reservation / Order ====================

class BookingAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = ['id', 'reservation', 'course_template', 'course_type', 'course_name', 'date', 'start_time', 'end_time', 'is_scheduled']
        read_only_fields = ['course_template']


class CampusManagerOrderSerializer(serializers.ModelSerializer):
    """校區主管與校長僅取得排課必需的訂單資訊。"""
    sn = serializers.SerializerMethodField()
    campus_name = serializers.CharField(source='campus.name', read_only=True, default='')
    student_alias = serializers.SerializerMethodField()
    number_of_people = serializers.SerializerMethodField()
    course_dates = serializers.SerializerMethodField()
    sessions = serializers.SerializerMethodField()

    class Meta:
        model = ReservationGroup
        fields = ['id', 'sn', 'campus_name', 'student_alias', 'number_of_people', 'course_dates', 'sessions']
        read_only_fields = fields

    def _visible_bookings(self, obj):
        request = self.context.get('request')
        profile = getattr(getattr(request, 'user', None), 'userprofile', None)
        manager_window = bool(profile and profile.role == 'campus_manager')
        today = timezone.localdate() if manager_window else None
        limit = today + timedelta(days=10) if today else None
        return [
            (reservation, booking)
            for reservation in obj.reservations.all()
            for booking in reservation.bookings.all()
            if not manager_window or today <= booking.date <= limit
        ]

    def get_sn(self, obj):
        return f'{obj.created_at:%Y%m%d}-{obj.id:04d}' if obj.created_at else f'00000000-{obj.id:04d}'

    def get_student_alias(self, obj):
        if obj.user:
            return obj.user.first_name or '學員'
        return obj.name or '學員'

    def get_number_of_people(self, obj):
        visible_reservation_ids = {reservation.id for reservation, _ in self._visible_bookings(obj)}
        return sum(
            reservation.number_of_people or 0
            for reservation in obj.reservations.all()
            if reservation.id in visible_reservation_ids
        )

    def get_course_dates(self, obj):
        return sorted({booking.date.isoformat() for _, booking in self._visible_bookings(obj)})

    def get_sessions(self, obj):
        sessions = []
        for reservation, booking in self._visible_bookings(obj):
            members = list(reservation.members.all())
            sessions.append({
                'date': booking.date,
                'start_time': booking.start_time,
                'end_time': booking.end_time,
                'course_type': reservation.course_type.name if reservation.course_type else booking.course_type,
                'number_of_people': reservation.number_of_people,
                'ability_level': reservation.max_ability_level or '',
                'age_ranges': [member.get_age_range_display() for member in members],
            })
        return sessions


class OrderAdminSerializer(serializers.ModelSerializer):
    """訂單 = ReservationGroup 為主，附帶旗下的 Reservation 與 Booking"""
    user_name = serializers.SerializerMethodField()
    user_email = serializers.SerializerMethodField()
    booking_contact = serializers.SerializerMethodField()
    marketing_source = serializers.SerializerMethodField()
    reservations = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    payment_method = serializers.SerializerMethodField()
    bank_account = serializers.SerializerMethodField()
    total_fee = serializers.SerializerMethodField()
    sn = serializers.SerializerMethodField()
    campus_name = serializers.CharField(source='campus.name', read_only=True, default='')
    revisions = serializers.SerializerMethodField()
    cancellation = serializers.SerializerMethodField()
    amendment_balance = serializers.SerializerMethodField()
    line_group_qr_url = serializers.SerializerMethodField()

    def get_line_group_qr_url(self, obj):
        from booking.class_group_qr import group_qr_url
        return group_qr_url(obj)

    class Meta:
        model = ReservationGroup
        fields = [
            'id', 'sn', 'order_number', 'name', 'user', 'user_name', 'user_email', 'booking_contact',
            'campus', 'campus_name', 'marketing_source', 'marketing_source_detail', 'line_group_url', 'line_group_qr_url',
            'reservations', 'total_fee', 'payment_status', 'payment_method',
            'bank_account', 'revisions', 'cancellation', 'amendment_balance', 'created_at',
        ]
        read_only_fields = fields

    def get_sn(self, obj):
        # 格式:YYYYMMDD-{id:04d},例如 20260512-0229
        # 一眼能看出哪天的單;id 全域唯一,搜尋時取後 4 碼當 id 查即可
        if obj.created_at:
            return f'{obj.created_at.strftime("%Y%m%d")}-{obj.id:04d}'
        return f'00000000-{obj.id:04d}'

    def get_marketing_source(self, obj):
        return display_marketing_source(obj.marketing_source)

    def get_revisions(self, obj):
        is_detail = getattr(self.context.get('view'), 'action', '') == 'retrieve'
        revisions = obj.revisions.all()
        if not is_detail:
            revisions = revisions[:20]
        return [
            {
                'id': revision.id,
                'version': revision.version,
                'change_type': revision.change_type,
                'difference_amount': revision.difference_amount,
                'reason': revision.reason,
                'created_at': revision.created_at,
                **({'snapshot': revision.snapshot} if is_detail else {}),
            }
            for revision in revisions
        ]

    def get_cancellation(self, obj):
        cancellation = obj.cancellation_requests.order_by('-created_at').first()
        return CancellationRequestAdminSerializer(cancellation).data if cancellation else None

    def get_amendment_balance(self, obj):
        pending=list(obj.amendments.filter(status__in=['topup_due','topup_reported','refund_account_due','refund_due']))
        if not pending:return None
        return {'amount':sum(row.balance_amount for row in pending),'statuses':sorted({row.status for row in pending})}

    def get_user_name(self, obj):
        return (obj.user.get_full_name() or obj.user.username) if obj.user else (obj.name or '訪客')

    def get_user_email(self, obj):
        if obj.user:
            return obj.user.email
        payment = obj.payments.last()
        contact = (payment.DataJSON or {}).get('contact', {}) if payment else {}
        return contact.get('email', '')

    def get_booking_contact(self, obj):
        contact = obj.booking_contact if isinstance(obj.booking_contact, dict) else {}
        if not contact:
            payment = obj.payments.last()
            payload = payment.DataJSON if payment and isinstance(payment.DataJSON, dict) else {}
            legacy = payload.get('contact', {})
            contact = legacy if isinstance(legacy, dict) else {}
        values = {
            key: contact.get(key) if isinstance(contact.get(key), str) else ''
            for key in ('name', 'email', 'phone', 'messenger_type', 'messenger_id')
        }
        values['name'] = values['name'] or obj.name or self.get_user_name(obj)
        values['email'] = values['email'] or self.get_user_email(obj)
        return values

    def get_reservations(self, obj):
        items = []
        include_available_coaches = self.context.get('include_available_coaches', False)
        for r in obj.reservations.all():
            item = {
                'id': r.id,
                'resort': r.resort.display_name if r.resort else '',
                'course_type': r.course_type.name if r.course_type else '',
                'course_template_id': r.course_template_id,
                'course_template': r.course_template.name if r.course_template else '',
                'ability_level': r.max_ability_level or '',
                'preferred_coach_id': r.preferred_coach_id,
                'preferred_coach': r.preferred_coach.name if r.preferred_coach else None,
                'is_preferred_coach': bool(r.is_preferred_coach),
                'shared_course_class_id': r.shared_course_class_id,
                'shared_class_status': r.shared_course_class.status if r.shared_course_class_id else None,
                'language': r.language,
                'equipment': r.equipment,
                'equipment_assistance_time_label': r.get_equipment_assistance_time_display(),
                'number_of_people': r.number_of_people,
                'status': r.status,
                'course_fee': r.course_fee,
                'coach_fee': r.coach_fee,
                'language_fee': r.language_fee,
                'equipment_rental_fee': r.equipment_rental_fee,
                'discount_amount': r.discount_amount,
                'discount_code': r.discount_code,
                'discount_name': r.discount_name,
                'original_total_fee': r.total_fee,
                'total_fee': r.payment_amount,
                'payment_amount': r.payment_amount,
                'bookings': [
                    {
                        'id': b.id,
                        'course_template_id': b.course_template_id,
                        'date': b.date,
                        'start_time': b.start_time,
                        'end_time': b.end_time,
                        'course_name': b.course_name,
                    } for b in r.bookings.all()
                ],
            }
            if include_available_coaches:
                item['available_coaches'] = self.get_available_coaches(r)
            items.append(item)
        return items

    def get_available_coaches(self, reservation):
        if not reservation.resort or not reservation.course_type:
            return []
        try:
            from collections import defaultdict
            from booking.scheduler import get_feasible_coaches, can_assign_all_bookings

            rejected_ids = list(reservation.rejected_coaches.values_list('id', flat=True))
            feasible_coaches = get_feasible_coaches(
                reservation.language,
                reservation.resort,
                reservation.course_type,
                reservation.max_ability_level,
                rejected_coach_ids=rejected_ids,
                course_template=reservation.course_template,
            )

            coach_busy_map = defaultdict(list)
            busy_bookings = self.context.get('_coach_busy_bookings')
            if busy_bookings is None:
                busy_bookings = list(Booking.objects.filter(
                    reservation__preferred_coach__isnull=False,
                    reservation__status__in=[
                        'auto_assigned',
                        'manually_assigned',
                        'pending_coach_confirmation',
                        'completed',
                    ],
                    is_scheduled=True,
                ).select_related('reservation'))
                self.context['_coach_busy_bookings'] = busy_bookings

            for booking in busy_bookings:
                if booking.reservation_id == reservation.id:
                    continue
                coach_id = booking.reservation.preferred_coach_id
                if coach_id:
                    coach_busy_map[coach_id].append((booking.date, booking.start_time, booking.end_time))

            bookings = list(reservation.bookings.all())
            return [
                {
                    'id': coach.id,
                    'name': coach.name,
                    'availability_status': coach.availability_status,
                    'requires_confirmation': coach.availability_status == 'passive',
                }
                for coach in feasible_coaches
                if can_assign_all_bookings(bookings, coach.id, coach_busy_map)
            ]
        except Exception:
            return []

    def get_payment_status(self, obj):
        p = obj.payments.last()
        return p.status if p else 'unpaid'

    def get_payment_method(self, obj):
        p = obj.payments.last()
        return p.payment_method if p else 'TT'

    def get_bank_account(self, obj):
        p = obj.payments.last()
        return p.bank_account if p else ''

    def get_total_fee(self, obj):
        return sum((r.payment_amount or 0) for r in obj.reservations.all())


class OrderRevisionAdminSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, default='')

    class Meta:
        model = OrderRevision
        fields = ['id', 'version', 'change_type', 'snapshot', 'difference_amount', 'reason', 'created_by_name', 'created_at']


class CancellationRequestSummarySerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='group.order_number', read_only=True)

    class Meta:
        model = CancellationRequest
        fields = ['id', 'group', 'order_number', 'status']
        read_only_fields = fields


class CancellationRequestAdminSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='group.order_number', read_only=True)
    refund_amount = serializers.SerializerMethodField()
    requires_cash_review = serializers.SerializerMethodField()

    def get_requires_cash_review(self,obj):
        from booking.operations import outstanding_amendments
        return obj.requires_cash_review or outstanding_amendments(obj.group).exists()

    def get_refund_amount(self,obj):
        return None if self.get_requires_cash_review(obj) and obj.actual_received_amount is None else obj.refund_amount

    class Meta:
        model = CancellationRequest
        fields = [
            'id', 'group', 'order_number', 'status', 'reason', 'reason_note', 'original_amount',
            'days_before', 'refund_percent', 'handling_fee_percent', 'refund_amount',
            'calculation_mode', 'selected_rule_days_before',
            'requires_cash_review','actual_received_amount','cash_review_note','cash_review_snapshot',
            'refund_bank_name', 'refund_account_number', 'refund_account_holder',
            'reviewed_by', 'reviewed_at', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'order_number', 'original_amount', 'days_before', 'refund_percent',
            'handling_fee_percent', 'refund_amount', 'reviewed_by', 'reviewed_at', 'created_at', 'updated_at',
            'calculation_mode', 'selected_rule_days_before',
            'requires_cash_review','actual_received_amount','cash_review_note','cash_review_snapshot',
        ]


class NotificationTemplateAdminSerializer(TenantRelationValidationMixin, serializers.ModelSerializer):
    repeat_interval_days = serializers.IntegerField(min_value=0, max_value=365, required=False)
    course_template_ids = serializers.PrimaryKeyRelatedField(
        source='course_templates', many=True, queryset=CourseTemplate.objects.all(), required=False
    )
    delivery_count = serializers.IntegerField(source='deliveries.count', read_only=True)

    class Meta:
        model = NotificationTemplate
        fields = ['id', 'campus', 'name', 'event', 'channel', 'subject', 'body', 'days_before', 'repeat_interval_days', 'course_template_ids', 'is_active', 'delivery_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'delivery_count', 'created_at', 'updated_at']

    def validate_campus(self, value):
        if value and value.client_id != getattr(self._tenant(), 'id', None):
            raise serializers.ValidationError('不能選擇其他公司的校區')
        return value

    def validate_course_template_ids(self, values):
        tenant = self._tenant()
        for template in values:
            if template.course_type.category.client_id != getattr(tenant, 'id', None):
                raise serializers.ValidationError('不能選擇其他公司的課程')
        return values

    def validate(self, attrs):
        event = attrs.get('event', self.instance.event if self.instance else None)
        if event == 'manual':
            raise serializers.ValidationError({'event': '請使用手動站內通知，不可建立自動發送範本'})
        repeat = attrs.get('repeat_interval_days', self.instance.repeat_interval_days if self.instance else 0)
        if repeat and event != 'missing_documents':
            raise serializers.ValidationError({'repeat_interval_days': '只有資料未完成通知可設定重複提醒'})
        if event in {'order_created', 'shared_class_ready', 'payment_confirmed'}:
            attrs['days_before'] = 0
        if event == 'shared_class_ready' and attrs.get('is_active', self.instance.is_active if self.instance else True):
            body = attrs.get('body', self.instance.body if self.instance else '')
            channel = attrs.get('channel', self.instance.channel if self.instance else '')
            if '{payment_url}' not in body:
                raise serializers.ValidationError({'body': '成班付款通知須包含 {payment_url}，客人才有付款連結'})
            if channel not in {'email', 'line'}:
                raise serializers.ValidationError({'channel': '成班付款請選 Email 或 LINE；站內通知尚未提供可用的付款提醒'})
        return attrs

    def create(self, validated_data):
        templates = validated_data.pop('course_templates', [])
        instance = NotificationTemplate.objects.create(client=self._tenant(), **validated_data)
        instance.course_templates.set(templates)
        return instance


class NotificationDeliveryAdminSerializer(serializers.ModelSerializer):
    channel = serializers.SerializerMethodField()
    email_synced = serializers.SerializerMethodField()
    template_name = serializers.CharField(source='template.name', read_only=True)
    order_number = serializers.CharField(source='group.order_number', read_only=True, default='')
    manual = serializers.SerializerMethodField()
    local_test = serializers.SerializerMethodField()

    class Meta:
        model = NotificationDelivery
        fields = ['id', 'template_name', 'order_number', 'recipient', 'channel', 'email_synced', 'manual', 'local_test', 'scheduled_at', 'sent_at', 'status', 'error_message', 'created_at']

    def get_local_test(self, instance):
        return bool(isinstance(instance.payload, dict) and instance.payload.get('local_test'))

    def get_manual(self, instance):
        return instance.template.event == 'manual'

    def get_channel(self, instance):
        payload = instance.payload if isinstance(instance.payload, dict) else {}
        return 'in_app' if payload.get('in_app_mirror_of') else instance.template.channel

    def get_email_synced(self, instance):
        return bool(isinstance(instance.payload, dict) and instance.payload.get('in_app_mirror_of'))


class CourseMediaAdminSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        from booking.media_files import course_media_url
        data = super().to_representation(instance)
        data['url'] = course_media_url(instance)
        return data

    url = serializers.URLField(max_length=800, error_messages={
        'invalid': '請輸入有效的 http:// 或 https:// 照片／影片網址',
    })

    def validate_url(self, value):
        if not value.lower().startswith(('http://', 'https://')):
            raise serializers.ValidationError('照片／影片網址須以 http:// 或 https:// 開頭')
        return value

    class Meta:
        model = CourseMedia
        fields = ['id', 'media_type', 'url', 'caption', 'is_public', 'created_at']
        read_only_fields = ['id', 'created_at']


class InsuranceProcessingInputSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=MemberDetail.INSURANCE_PROCESSING_CHOICES)
    premium_amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, allow_null=True)
    currency = serializers.CharField(max_length=3, allow_blank=True)
    expected_updated_at = serializers.DateTimeField(allow_null=True)
    confirm_insured = serializers.BooleanField(default=False)

    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise serializers.ValidationError({'non_field_errors': ['只能更新投保作業欄位，不能修改學員、監護人或簽署資料']})
        return super().to_internal_value(data)

    def validate_currency(self, value):
        value = value.upper()
        if value and (len(value) != 3 or not value.isascii() or not value.isalpha()):
            raise serializers.ValidationError('幣別請填3碼英文字母，例如 TWD 或 JPY')
        return value

    def validate(self, attrs):
        if attrs['premium_amount'] is not None and not attrs['currency']:
            raise serializers.ValidationError({'currency': '填寫金額時請同時填寫幣別'})
        return attrs


class InsuranceRecordAdminSerializer(serializers.ModelSerializer):
    can_remind = serializers.SerializerMethodField()
    can_mark_complete = serializers.SerializerMethodField()
    member_name = serializers.SerializerMethodField()
    order_number = serializers.CharField(source='reservation.group.order_number', read_only=True)
    sn = serializers.SerializerMethodField()
    campus_name = serializers.CharField(source='reservation.group.campus.name', read_only=True, default='')
    course_dates = serializers.SerializerMethodField()

    class Meta:
        model = MemberDetail
        fields = ['id', 'member_name', 'order_number', 'sn', 'campus_name', 'age_range', 'guardian', 'insurance_completed_at', 'waiver_completed_at', 'course_dates', 'can_mark_complete', 'can_remind',
                  'insurance_processing_status', 'insurance_premium_amount', 'insurance_premium_currency', 'insurance_processing_updated_at']
        read_only_fields = [name for name in fields if name != 'age_range']

    def update(self, instance, validated_data):
        # Preserve the existing age-range correction, but never rebind a guardian
        # or re-save stale processing/form/signature fields through this route.
        if 'age_range' in validated_data:
            instance.age_range = validated_data['age_range']
            instance.save(update_fields=['age_range'])
        return instance

    def get_sn(self, obj):
        group = obj.reservation.group
        return f'{group.created_at:%Y%m%d}-{group.id:04d}' if group.created_at else f'00000000-{group.id:04d}'

    def get_member_name(self, obj):
        return obj.display_name

    def get_can_mark_complete(self, obj):
        request = self.context.get('request')
        if not request or not user_has_admin_permission(request.user, 'insurance_records'):
            return False
        profile = getattr(request.user, 'userprofile', None)
        return request.user.is_superuser or not (profile and profile.role == 'assistant')

    def get_course_dates(self, obj):
        if obj.reservation.status in {'cancelled','deleted'}:
            return []
        return list(obj.reservation.bookings.order_by('date').values_list('date', flat=True).distinct())

    def get_can_remind(self, obj):
        request = self.context.get('request')
        return bool(request and user_has_admin_permission(request.user,'insurance_records')
            and obj.reservation.status not in {'cancelled','deleted'})


class InsuranceRecordDetailAdminSerializer(InsuranceRecordAdminSerializer):
    member_email = serializers.SerializerMethodField()

    def get_member_email(self, obj):
        if obj.user_id and obj.user.email:
            return obj.user.email
        data = obj.insurance_data if isinstance(obj.insurance_data, dict) else {}
        return data.get('email', '') if isinstance(data.get('email', ''), str) else ''

    class Meta(InsuranceRecordAdminSerializer.Meta):
        fields = InsuranceRecordAdminSerializer.Meta.fields + [
            'member_email', 'insurance_data', 'waiver_signature', 'waiver_document_version',
            'waiver_document_snapshot', 'media_consent',
        ]
        read_only_fields = fields


class EvaluationTrailNamesField(serializers.ListField):
    def to_internal_value(self, data):
        if isinstance(data, str):
            from booking.trails import trail_names_as_list
            data = trail_names_as_list(data)
        return super().to_internal_value(data)

    def to_representation(self, value):
        from booking.trails import trail_names_as_list
        return super().to_representation(trail_names_as_list(value))


class CourseEvaluationAdminSerializer(serializers.ModelSerializer):
    can_edit_assessment = serializers.SerializerMethodField()
    trail_names = EvaluationTrailNamesField(
        child=serializers.CharField(max_length=120, error_messages={'blank': '雪道名稱不能空白', 'max_length': '每條雪道名稱最多120字'}),
        max_length=100, required=False,
        error_messages={'not_a_list': '雪道資料必須是清單', 'null': '雪道清單不能是空值，未設定請使用空清單', 'max_length': '雪道清單最多100條'},
    )
    available_trails = serializers.SerializerMethodField()
    media = CourseMediaAdminSerializer(many=True, read_only=True)
    new_media = serializers.JSONField(write_only=True, required=False)
    member_name = serializers.SerializerMethodField()
    coach_name = serializers.CharField(source='coach.name', read_only=True, default='')
    course_date = serializers.DateField(source='booking.date', read_only=True)
    order_number = serializers.SerializerMethodField()
    course_name = serializers.SerializerMethodField()
    campus_name = serializers.SerializerMethodField()
    resort_name = serializers.SerializerMethodField()

    class Meta:
        model = CourseEvaluation
        fields = ['id', 'booking', 'member', 'member_name', 'coach', 'coach_name', 'course_date', 'order_number', 'course_name', 'campus_name', 'resort_name', 'self_assessment', 'coach_assessment', 'learning_progress', 'trail_names', 'available_trails', 'coach_notes', 'completed_at', 'media', 'new_media', 'created_at', 'updated_at', 'can_edit_assessment']
        read_only_fields = ['id', 'member_name', 'coach_name', 'course_date', 'order_number', 'course_name', 'campus_name', 'resort_name', 'media', 'created_at', 'updated_at']

    def validate_new_media(self, value):
        serializer = CourseMediaAdminSerializer(data=value)
        serializer.is_valid(raise_exception=True)
        if not self.get_can_edit_assessment(self.instance) and serializer.validated_data.get('is_public'):
            raise PermissionDenied('行政加入的課程附件僅供授權學員查看，不能直接公開')
        return serializer.validated_data

    def get_can_edit_assessment(self, obj):
        request = self.context.get('request')
        if not request:
            return False
        if getattr(self.context.get('view'), 'coach_scoped', False):
            return True
        profile = getattr(request.user, 'userprofile', None)
        return user_has_admin_permission(request.user, 'evaluations') and (
            request.user.is_superuser or not (profile and profile.role == 'assistant')
        )

    def validate_trail_names(self, value):
        return list(dict.fromkeys(value))

    def get_available_trails(self, obj):
        reservation = obj.booking.reservation
        resort = reservation.resort
        if not resort or resort.client_id != reservation.group.client_id:
            return []
        return resort.trail_names if isinstance(resort.trail_names, list) else []

    @transaction.atomic
    def create(self, validated_data):
        media = validated_data.pop('new_media', None)
        instance = super().create(validated_data)
        if media is not None:
            CourseMedia.objects.create(evaluation=instance, uploaded_by=self.context['request'].user, **media)
        return instance

    @transaction.atomic
    def update(self, instance, validated_data):
        media = validated_data.pop('new_media', None)
        instance = super().update(instance, validated_data)
        if media is not None:
            CourseMedia.objects.create(evaluation=instance, uploaded_by=self.context['request'].user, **media)
        return instance

    def get_member_name(self, obj):
        return obj.member.display_name

    def get_order_number(self, obj):
        return obj.booking.reservation.group.order_number or f'訂單 #{obj.booking.reservation.group_id}'

    def get_course_name(self, obj):
        return obj.booking.course_name or obj.booking.course_type or ''

    def get_campus_name(self, obj):
        campus = obj.booking.reservation.group.campus
        return campus.name if campus else ''

    def get_resort_name(self, obj):
        resort = obj.booking.reservation.resort
        return resort.display_name if resort else ''

    def validate(self, attrs):
        request = self.context.get('request')
        tenant = getattr(request, 'tenant', None)
        booking = attrs.get('booking', getattr(self.instance, 'booking', None))
        member = attrs.get('member', getattr(self.instance, 'member', None))
        coach = attrs.get('coach', getattr(self.instance, 'coach', None))
        if not booking or booking.reservation.group.client_id != getattr(tenant, 'id', None):
            raise serializers.ValidationError({'booking': '不能選擇其他公司的課程'})
        if getattr(self.context.get('view'), 'coach_scoped', False):
            if not booking.reservation.preferred_coach or booking.reservation.preferred_coach.user_id != request.user.id:
                raise serializers.ValidationError({'booking': '只能填寫自己授課的評量'})
        elif (not getattr(request, 'can_view_all_campuses', False) or
                getattr(request, 'selected_campus_id', None) is not None):
            if booking.reservation.group.campus_id not in getattr(request, 'campus_ids', []):
                raise serializers.ValidationError({'booking': '只能填寫目前管理校區的課程評量'})
        if not member or member.reservation_id != booking.reservation_id:
            raise serializers.ValidationError({'member': '學員不屬於這堂課'})
        if coach and coach.client_id != getattr(tenant, 'id', None):
            raise serializers.ValidationError({'coach': '不能選擇其他公司的教練'})
        completed_at = attrs.get('completed_at', getattr(self.instance, 'completed_at', None))
        if completed_at:
            notes = attrs.get('coach_notes', getattr(self.instance, 'coach_notes', ''))
            progress = attrs.get('learning_progress', getattr(self.instance, 'learning_progress', {}))
            trails = attrs.get('trail_names', getattr(self.instance, 'trail_names', []))
            has_progress = any(str(value).strip() for value in progress.values()) if isinstance(progress, dict) else bool(progress)
            has_trails = any(str(value).strip() for value in trails) if isinstance(trails, list) else bool(trails and str(trails).strip())
            if not (notes.strip() or has_progress or has_trails):
                raise serializers.ValidationError({'completed_at': '請先填寫教練評語、學習進度或完成雪道，再標示完成'})
        return attrs


class CoachCourseEvaluationSerializer(CourseEvaluationAdminSerializer):
    class Meta(CourseEvaluationAdminSerializer.Meta):
        read_only_fields = CourseEvaluationAdminSerializer.Meta.read_only_fields + ['booking', 'member', 'coach', 'self_assessment']

    def validate(self, attrs):
        protected = {'booking', 'member', 'coach', 'self_assessment'} & set(self.initial_data)
        if protected:
            raise serializers.ValidationError({field: '教練不能修改此欄位' for field in protected})
        if attrs.get('new_media', {}).get('is_public'):
            raise serializers.ValidationError({'new_media': '教練課程媒體僅供會員查看，不能直接公開'})
        return super().validate(attrs)


class CoachPayRuleAdminSerializer(serializers.ModelSerializer):
    referral_percent = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100, required=False)
    assistance_hour_factor = serializers.DecimalField(max_digits=4, decimal_places=2, min_value=0, required=False)
    coach_name = serializers.CharField(source='coach.name', read_only=True)
    course_type_name = serializers.CharField(source='course_type.name', read_only=True, default='')
    course_type = serializers.PrimaryKeyRelatedField(
        queryset=CourseType.objects.all(), required=False, allow_null=True,
    )

    class Meta:
        model = CoachPayRule
        fields = ['id', 'coach', 'coach_name', 'course_type', 'course_type_name', 'discipline', 'certification_level', 'hourly_rate', 'specified_fee', 'referral_percent', 'assistance_hour_factor', 'supervisor_allowance', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'coach_name', 'course_type_name', 'created_at', 'updated_at']
        validators = []

    def validate(self, attrs):
        tenant = getattr(self.context.get('request'), 'tenant', None)
        coach = attrs.get('coach', getattr(self.instance, 'coach', None))
        course_type = attrs.get('course_type', getattr(self.instance, 'course_type', None))
        if not coach or coach.client_id != getattr(tenant, 'id', None):
            raise serializers.ValidationError({'coach': '不能選擇其他公司的教練'})
        if course_type and course_type.category.client_id != getattr(tenant, 'id', None):
            raise serializers.ValidationError({'course_type': '不能選擇其他公司的課程'})
        discipline = attrs.get('discipline', getattr(self.instance, 'discipline', None))
        certification_level = attrs.get('certification_level', getattr(self.instance, 'certification_level', ''))
        if coach and discipline and CoachPayRule.objects.filter(
            coach=coach, course_type=course_type, discipline=discipline,
            certification_level=certification_level,
        ).exclude(pk=getattr(self.instance, 'pk', None)).exists():
            raise serializers.ValidationError({'non_field_errors': '這位教練的相同薪資規則已存在，請編輯原規則'})
        active = attrs.get('is_active', getattr(self.instance, 'is_active', True))
        if active and CoachPayRule.objects.filter(coach=coach, course_type=course_type,
            discipline=discipline, is_active=True).exclude(pk=getattr(self.instance, 'pk', None)).exists():
            raise serializers.ValidationError({'non_field_errors': '同一教練、工作類型與適用課程只能有一筆啟用規則。請先停用原規則，或將新版存成停用，再切換啟用。'})
        return attrs


class StaffIncentiveRuleAdminSerializer(serializers.ModelSerializer):
    completed_order_percent = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100)
    user_name = serializers.SerializerMethodField()
    campus_name = serializers.CharField(source='campus.name', read_only=True)

    def get_user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username

    class Meta:
        model = StaffIncentiveRule
        fields = ['id', 'user', 'user_name', 'campus', 'campus_name', 'completed_order_percent', 'is_active']
        read_only_fields = ['id', 'user_name', 'campus_name']
        validators = []

    def validate(self, attrs):
        request = self.context['request']
        campus = attrs.get('campus', getattr(self.instance, 'campus', None))
        user = attrs.get('user', getattr(self.instance, 'user', None))
        disabling_existing = bool(self.instance and campus and user and
            campus.pk == self.instance.campus_id and user.pk == self.instance.user_id and
            attrs.get('is_active', self.instance.is_active) is False)
        if not campus or campus.client_id != request.tenant.pk or (not campus.is_active and not disabling_existing):
            raise serializers.ValidationError({'campus': '請選擇本公司的使用中校區'})
        if (not request.can_view_all_campuses or request.selected_campus_id is not None) and campus.pk not in request.campus_ids:
            raise PermissionDenied('只能設定目前可管理校區的員工獎金')
        if not user or (not user.is_active and not disabling_existing):
            raise serializers.ValidationError({'user': '請選擇使用中的員工帳號'})
        from Control.models import UserProfile
        profile = UserProfile.objects.filter(user=user, manager_client=request.tenant, is_manager=True).first()
        headquarters_roles = {'hq_admin', 'marketing', 'web_editor', 'insurance', 'assistant'}
        if not disabling_existing and (not profile or not (profile.role in headquarters_roles or profile.campuses.filter(pk=campus.pk).exists())):
            raise serializers.ValidationError({'user': '請選擇本公司且可管理此校區的員工'})
        if StaffIncentiveRule.objects.filter(user=user, campus=campus).exclude(pk=getattr(self.instance, 'pk', None)).exists():
            raise serializers.ValidationError({'non_field_errors': '此員工在這個校區已有獎金比例，請編輯原設定'})
        return attrs


class PayrollLineAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollLine
        fields = ['id', 'booking', 'line_type', 'description', 'quantity', 'unit_amount', 'total_amount', 'metadata']


class PayrollStatementAdminSerializer(serializers.ModelSerializer):
    coach_name = serializers.CharField(source='coach.name', read_only=True)
    campus_name = serializers.CharField(source='campus.name', read_only=True)
    lines = PayrollLineAdminSerializer(many=True, read_only=True)
    confirmation_timezone = serializers.SerializerMethodField()
    document_digest = serializers.SerializerMethodField()
    signature_file_url = serializers.SerializerMethodField()

    def get_document_digest(self, obj):
        from Coach.payroll_documents import document_digest
        return document_digest(obj.document_snapshot)

    def get_signature_file_url(self, obj):
        if not obj.signature_file or not obj.signed_at:
            return ''
        from django.urls import reverse
        coach_view = getattr(self.context.get('view'), 'coach_scoped', False)
        return reverse('coach-payroll-signature-file' if coach_view else 'admin-payroll-statements-signature-file',
            kwargs={'client_code': obj.coach.client.internal_code, 'pk': obj.pk})

    def get_confirmation_timezone(self, obj):
        return settings.TIME_ZONE

    class Meta:
        model = PayrollStatement
        fields = ['id', 'coach', 'coach_name', 'campus', 'campus_name', 'period_start', 'period_end', 'course_pay', 'specified_fees', 'referral_commission', 'assistance_pay', 'supervisor_allowance', 'adjustment', 'total_amount', 'status', 'notes', 'lines', 'published_at', 'confirmation_deadline', 'review_token', 'confirmed_at', 'confirmation_method', 'confirmation_timezone', 'document_snapshot', 'document_digest', 'signature_file_url', 'signer_name', 'signed_at', 'created_at', 'updated_at']
        read_only_fields = fields

    def validate(self, attrs):
        tenant = getattr(self.context.get('request'), 'tenant', None)
        coach = attrs.get('coach', getattr(self.instance, 'coach', None))
        campus = attrs.get('campus', getattr(self.instance, 'campus', None))
        if coach and coach.client_id != getattr(tenant, 'id', None):
            raise serializers.ValidationError({'coach': '不能選擇其他公司的教練'})
        if campus and campus.client_id != getattr(tenant, 'id', None):
            raise serializers.ValidationError({'campus': '不能選擇其他公司的校區'})
        return attrs


class StaffBookingLinkAdminSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    url = serializers.SerializerMethodField()
    is_available = serializers.BooleanField(read_only=True)

    class Meta:
        model = StaffBookingLink
        fields = ['id', 'token', 'campus', 'title', 'cart_snapshot', 'expires_at', 'used_by', 'used_at', 'is_active', 'is_available', 'created_by_name', 'url', 'created_at']
        read_only_fields = ['id', 'token', 'used_by', 'used_at', 'created_by_name', 'url', 'created_at']

    def get_url(self, obj):
        request = self.context.get('request')
        base = request.build_absolute_uri('/')[:-1] if request else ''
        return f'{base}/{obj.client.internal_code}/booking?staff_link={obj.token}'

    def validate_campus(self, value):
        request = self.context.get('request')
        tenant = getattr(request, 'tenant', None)
        if value.client_id != getattr(tenant, 'id', None):
            raise serializers.ValidationError('不能選擇其他公司的校區')
        if request and (
            not getattr(request, 'can_view_all_campuses', False)
            or getattr(request, 'selected_campus_id', None)
        ) and value.id not in getattr(request, 'campus_ids', []):
            raise PermissionDenied('不能為其他校區建立或修改訂課連結')
        return value

    def validate(self, attrs):
        snapshot = attrs.get('cart_snapshot', self.instance.cart_snapshot if self.instance else [])
        if not snapshot:
            if self.instance is None:
                raise serializers.ValidationError({'cart_snapshot': '請先為客人選好至少一堂課'})
            return attrs
        campus = attrs.get('campus', self.instance.campus if self.instance else None)
        tenant = getattr(self.context.get('request'), 'tenant', None)
        if not isinstance(snapshot, list) or not campus:
            raise serializers.ValidationError({'cart_snapshot': '請先選校區及課程'})
        if not campus.is_active:
            raise serializers.ValidationError({'campus': '校區已停用，不能建立訂課連結'})
        if public_staff_cart_snapshot(snapshot) != snapshot:
            raise serializers.ValidationError({'cart_snapshot': '選課內容含有未支援欄位，請重新選課'})
        for item in snapshot:
            if not isinstance(item, dict) or type(item.get('peopleCount')) is not int or item['peopleCount'] < 1:
                raise serializers.ValidationError({'cart_snapshot': '請確認每組課程與人數'})
            if item.get('campusId') not in (None, campus.id):
                raise serializers.ValidationError({'cart_snapshot': '選課校區與連結校區不一致'})
            resort = Resorts.objects.filter(
                client=tenant, name=item.get('resort'), campuses=campus,
            ).first()
            if not resort or not campus.is_active:
                raise serializers.ValidationError({'cart_snapshot': '所選雪場不屬於這個校區'})
            courses = item.get('courses')
            if not isinstance(courses, list) or not courses:
                raise serializers.ValidationError({'cart_snapshot': '請至少選一堂課'})
            for course in courses:
                if not isinstance(course, dict) or type(course.get('courseTemplateId')) is not int:
                    raise serializers.ValidationError({'cart_snapshot': '課程模板資料不正確'})
                if not CourseTemplate.objects.filter(
                    id=course['courseTemplateId'], is_active=True,
                    course_type__category__client=tenant, resorts=resort,
                ).exists():
                    raise serializers.ValidationError({'cart_snapshot': '所選課程不適用此校區雪場'})
        return attrs


# ==================== Customer (聚合 User + 預約紀錄) ====================

class CustomerAdminSerializer(serializers.Serializer):
    """從 User + 其 ReservationGroup 聚合出 Customer 資料"""
    id = serializers.IntegerField()
    name = serializers.CharField()
    email = serializers.CharField()
    phone = serializers.CharField()
    total_reservations = serializers.IntegerField()
    total_spent = serializers.IntegerField()
    last_visit = serializers.CharField()
    age_range = serializers.CharField()
    snowboard_skills = serializers.ListField(child=serializers.CharField())
    ski_skills = serializers.ListField(child=serializers.CharField())
    notes = serializers.CharField(required=False, allow_blank=True)


# ==================== Booking (排課) ====================

class BookingScheduleAdminSerializer(serializers.ModelSerializer):
    reservation_id = serializers.IntegerField(read_only=True)
    coach_name = serializers.CharField(source='reservation.preferred_coach.name', read_only=True, default='')
    group_id = serializers.SerializerMethodField()
    order_number = serializers.CharField(source='reservation.group.order_number', read_only=True, default='')
    sn = serializers.SerializerMethodField()
    user_name = serializers.SerializerMethodField()
    resort = serializers.CharField(source='reservation.resort.display_name', read_only=True, default='')
    campus_name = serializers.CharField(source='reservation.group.campus.name', read_only=True, default='')
    campus_is_active = serializers.BooleanField(source='reservation.group.campus.is_active', read_only=True, default=True)
    number_of_people = serializers.IntegerField(source='reservation.number_of_people', read_only=True)
    status = serializers.SerializerMethodField()
    event_type = serializers.SerializerMethodField()
    service_type = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            'id', 'reservation_id', 'group_id', 'order_number', 'sn', 'date', 'start_time', 'end_time',
            'course_name', 'coach_name', 'user_name', 'resort', 'campus_name', 'campus_is_active',
            'number_of_people', 'is_scheduled', 'status', 'event_type',
            'service_type',
        ]
        read_only_fields = fields

    def _is_photo_booking(self, obj):
        reservation = getattr(obj, 'reservation', None)
        course_type = getattr(reservation, 'course_type', None)
        template = getattr(reservation, 'course_template', None)
        category = getattr(course_type, 'category', None)
        service_type = getattr(category, 'service_type', '')
        text = ' '.join([
            str(getattr(category, 'name', '') or ''),
            str(getattr(course_type, 'name', '') or ''),
            str(getattr(template, 'name', '') or ''),
            str(getattr(obj, 'course_type', '') or ''),
            str(getattr(obj, 'course_name', '') or ''),
        ]).lower()
        return service_type == 'photo' or any(keyword in text for keyword in ['攝影', '旅拍', 'photography', 'photo'])

    def get_group_id(self, obj):
        return obj.reservation.group_id if obj.reservation else None

    def get_sn(self, obj):
        group = obj.reservation.group if obj.reservation else None
        if not group:
            return ''
        return f'{group.created_at:%Y%m%d}-{group.id:04d}' if group.created_at else f'00000000-{group.id:04d}'

    def get_user_name(self, obj):
        try:
            user = obj.reservation.group.user
            return (user.get_full_name() or user.username) if user else (obj.reservation.group.name or '')
        except Exception:
            return ''

    def get_status(self, obj):
        if obj.is_scheduled:
            return 'scheduled'
        return obj.reservation.status if obj.reservation else 'pending'

    def get_event_type(self, obj):
        return 'photo' if self._is_photo_booking(obj) else 'course'

    def get_service_type(self, obj):
        return 'photo' if self._is_photo_booking(obj) else 'ski'
