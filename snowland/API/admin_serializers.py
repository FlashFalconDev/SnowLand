"""
後台管理用 Serializer
跟前端使用的 serializer 不同，這些回傳完整資訊（含 nested 關聯）
給管理員看的，不過濾欄位
"""
from rest_framework import serializers
from django.contrib.auth.models import User
from django.db import transaction
from Client.models import SiteContent
from Coach.models import Coach, CoachResort, CoachCourseLevel, CoachLeaveRequest, normalize_ability_levels
from Resorts.models import Resorts, ResortFee, EquipmentPricingTier, EquipmentAssistanceTimeSlot, EquipmentRentalItem
from Coursekit.models import CourseCategory, CourseType, CourseTemplate, CourseSession, CoursePricing, CoursePricingTier, SeasonSetting, DiscountCode
from booking.models import ReservationGroup, Reservation, Booking, MemberDetail, Payment


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


class CoachAdminSerializer(serializers.ModelSerializer):
    resorts = serializers.SerializerMethodField()
    course_levels = serializers.SerializerMethodField()
    user_id = serializers.IntegerField(required=False, allow_null=True)
    user_email = serializers.CharField(source='user.email', read_only=True, default=None)
    user_name = serializers.SerializerMethodField()
    user_username = serializers.CharField(source='user.username', read_only=True, default='')
    img = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    languages = serializers.ListField(child=serializers.CharField(), required=False)
    certifications = serializers.ListField(
        child=serializers.DictField(), required=False, allow_empty=True
    )
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
            'languages', 'availability_status', 'assignment_score', 'img',
            'website_enabled', 'website_slug', 'website_sort_order', 'website_card_bio',
            'certifications',
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
        return attrs

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
        resorts_input = validated_data.pop('resorts_input', [])
        course_levels_input = validated_data.pop('course_levels_input', [])
        request = self.context.get('request')
        client = getattr(request, 'tenant', None) if request else None
        self._sync_coach_permission(validated_data.get('user_id'))
        coach = Coach.objects.create(client=client, **validated_data)
        self._sync_resorts(coach, resorts_input)
        self._sync_course_levels(coach, course_levels_input)
        return coach

    def update(self, instance, validated_data):
        resorts_input = validated_data.pop('resorts_input', None)
        course_levels_input = validated_data.pop('course_levels_input', None)
        if 'user_id' in validated_data:
            self._sync_coach_permission(validated_data.get('user_id'))
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
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
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'reviewed_at', 'reviewed_by']

    def get_affected_count(self, obj):
        return obj.affected_reservations.count()


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
    fees = serializers.SerializerMethodField()
    equipment_tiers = serializers.SerializerMethodField()
    equipment_rental_items = serializers.SerializerMethodField()
    equipment_time_slots = serializers.SerializerMethodField()
    fees_input = serializers.ListField(
        child=serializers.DictField(), write_only=True, required=False, allow_empty=True
    )
    equipment_tiers_input = serializers.ListField(
        child=serializers.DictField(), write_only=True, required=False, allow_empty=True
    )
    equipment_rental_items_input = serializers.ListField(
        child=serializers.DictField(), write_only=True, required=False, allow_empty=True
    )
    equipment_time_slots_input = serializers.ListField(
        child=serializers.DictField(), write_only=True, required=False, allow_empty=True
    )

    class Meta:
        model = Resorts
        fields = [
            'id', 'name', 'display_name', 'auto_scheduling_enabled',
            'fees', 'equipment_tiers', 'equipment_rental_items', 'equipment_time_slots',
            'fees_input', 'equipment_tiers_input', 'equipment_rental_items_input', 'equipment_time_slots_input',
        ]
        read_only_fields = ['id']

    def get_fees(self, obj):
        return ResortFeeNestedSerializer(
            ResortFee.objects.filter(resort=obj),
            many=True
        ).data

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
                    'daily_price': int(item.get('daily_price') or 0),
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
        for item in tiers:
            if item.get('is_active', True) is False:
                continue
            min_people = int(item.get('min_people') or 0)
            max_people = int(item.get('max_people') or 0)
            price = int(item.get('price') or 0)
            if min_people < 1 or max_people < min_people:
                raise serializers.ValidationError('Invalid equipment people range')
            if price < 0:
                raise serializers.ValidationError('Equipment tier price cannot be negative')
            for start, end in active_ranges:
                if min_people <= end and max_people >= start:
                    raise serializers.ValidationError('Equipment people ranges cannot overlap')
            active_ranges.append((min_people, max_people))

    def _validate_equipment_rental_items(self, items):
        active_codes = set()
        for item in items:
            code = (item.get('code') or '').strip()
            name = (item.get('name') or '').strip()
            daily_price = int(item.get('daily_price') or 0)
            additional_day_price = int(item.get('additional_day_price') or 0)
            has_content = code or name or daily_price or additional_day_price or item.get('description')
            if not has_content:
                continue
            if not code or not name:
                raise serializers.ValidationError('Equipment rental item code and name are required')
            if daily_price < 0 or additional_day_price < 0:
                raise serializers.ValidationError('Equipment rental item prices cannot be negative')
            if item.get('is_active', True):
                normalized_code = code.lower()
                if normalized_code in active_codes:
                    raise serializers.ValidationError('Equipment rental item codes cannot duplicate')
                active_codes.add(normalized_code)

    def _validate_time_slots(self, slots):
        active_keys = set()
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
                if any(item.get(k) for k in ('start_time', 'end_time', 'description')):
                    raise serializers.ValidationError('Equipment time slot label is required')
                continue
            if equipment_option not in valid_equipment_options:
                raise serializers.ValidationError('Invalid equipment option for time slot')
            if lesson_duration not in valid_lesson_durations:
                raise serializers.ValidationError('Invalid lesson duration for equipment time slot')
            if session_period not in valid_session_periods:
                raise serializers.ValidationError('Invalid session period for equipment time slot')
            if day_type not in valid_day_types:
                raise serializers.ValidationError('Invalid day type for equipment time slot')
            self._normalize_course_template_ids(item.get('course_template_ids') or item.get('course_templates') or [])
            if item.get('is_active', True):
                key = (equipment_option, lesson_duration, session_period, day_type, label.lower())
                if key in active_keys:
                    raise serializers.ValidationError('Equipment time slot labels cannot duplicate in the same binding')
                active_keys.add(key)

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


class CourseTemplateAdminSerializer(serializers.ModelSerializer):
    sessions = CourseSessionAdminSerializer(many=True, read_only=True)  # related_name='sessions'
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
            'id', 'course_type', 'course_type_name', 'name',
            'display_order', 'duration_hours', 'max_capacity', 'is_active',
            'resorts', 'resort_names',
            'booking_open_date', 'booking_close_date',
            'course_start_date', 'course_end_date',
            'minimum_coach_price_level', 'minimum_coach_price_level_label',
            'allowed_coaches', 'allowed_coach_names',
            'sessions',
        ]
        read_only_fields = ['id']

    def get_resort_names(self, obj):
        return [r.display_name for r in obj.resorts.all()]

    def get_allowed_coach_names(self, obj):
        return [coach.name for coach in obj.allowed_coaches.all()]

    def get_minimum_coach_price_level_label(self, obj):
        return obj.get_minimum_coach_price_level_display()


class CourseTypeAdminSerializer(serializers.ModelSerializer):
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


class CourseCategoryAdminSerializer(serializers.ModelSerializer):
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
        fields = ['id', 'reservation', 'course_type', 'course_name', 'date', 'start_time', 'end_time', 'is_scheduled']


class OrderAdminSerializer(serializers.ModelSerializer):
    """訂單 = ReservationGroup 為主，附帶旗下的 Reservation 與 Booking"""
    user_name = serializers.SerializerMethodField()
    user_email = serializers.SerializerMethodField()
    reservations = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    payment_method = serializers.SerializerMethodField()
    bank_account = serializers.SerializerMethodField()
    total_fee = serializers.SerializerMethodField()
    sn = serializers.SerializerMethodField()

    class Meta:
        model = ReservationGroup
        fields = [
            'id', 'sn', 'name', 'user', 'user_name', 'user_email',
            'reservations', 'total_fee', 'payment_status', 'payment_method',
            'bank_account', 'created_at',
        ]
        read_only_fields = fields

    def get_sn(self, obj):
        # 格式:YYYYMMDD-{id:04d},例如 20260512-0229
        # 一眼能看出哪天的單;id 全域唯一,搜尋時取後 4 碼當 id 查即可
        if obj.created_at:
            return f'{obj.created_at.strftime("%Y%m%d")}-{obj.id:04d}'
        return f'00000000-{obj.id:04d}'

    def get_user_name(self, obj):
        return obj.user.username if obj.user else (obj.name or '訪客')

    def get_user_email(self, obj):
        if obj.user:
            return obj.user.email
        payment = obj.payments.last()
        contact = (payment.DataJSON or {}).get('contact', {}) if payment else {}
        return contact.get('email', '')

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
    user_name = serializers.SerializerMethodField()
    resort = serializers.CharField(source='reservation.resort.display_name', read_only=True, default='')
    number_of_people = serializers.IntegerField(source='reservation.number_of_people', read_only=True)
    status = serializers.SerializerMethodField()
    event_type = serializers.SerializerMethodField()
    service_type = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            'id', 'reservation_id', 'group_id', 'date', 'start_time', 'end_time',
            'course_name', 'coach_name', 'user_name', 'resort',
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

    def get_user_name(self, obj):
        try:
            user = obj.reservation.group.user
            return user.username if user else (obj.reservation.group.name or '')
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
