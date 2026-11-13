from datetime import datetime, time, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from Client.models import Client
from Coach.models import Coach
from Coach.payroll_settlement import number
from Coach.vehicle_models import Vehicle, VehicleCharge, VehicleExpense, VehiclePolicy, VehicleTrip
from Coach.vehicle_payroll import JAPAN_TIME, charge_balance, create_trip_charges, payroll_cutoff
from Control.tenant_memberships import staff_profile
from Resorts.models import Campus, Resorts
from booking.media_files import private_file_response, validate_course_upload
from booking.models import Booking
from .admin_permissions import user_has_admin_permission
from .admin_views import _resolve_campus_scope, _resolve_tenant, SCHEDULED_RESERVATION_STATUSES
from .payroll_security import PayrollCsrfMixin


REVIEW_ROLES = {'hq_admin', 'campus_principal', 'campus_manager'}
FINANCE_ROLES = {'hq_admin', 'assistant'}


class TripRequest(serializers.Serializer):
    campus = serializers.IntegerField(min_value=1)
    driver = serializers.IntegerField(min_value=1, required=False)
    participants = serializers.ListField(child=serializers.IntegerField(min_value=1), default=list, max_length=20)
    resort = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    purpose = serializers.ChoiceField(choices=VehicleTrip.PURPOSES)
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    note = serializers.CharField(max_length=500, allow_blank=True, default='')

    def validate(self, attrs):
        if attrs['ends_at'] <= attrs['starts_at']:
            raise serializers.ValidationError('歸還時間必須晚於出發時間')
        return attrs


class VehicleForm(serializers.Serializer):
    campus = serializers.IntegerField(min_value=1)
    name = serializers.CharField(max_length=80)
    plate = serializers.CharField(max_length=32)
    active = serializers.BooleanField(default=True)
    shared_campuses = serializers.ListField(child=serializers.IntegerField(min_value=1), default=list, max_length=100)


class PolicyForm(serializers.Serializer):
    yen_per_km = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    yen_per_twd = serializers.DecimalField(max_digits=12, decimal_places=8, min_value=0)
    payroll_day = serializers.IntegerField(min_value=1, max_value=31)
    exempt_resorts = serializers.ListField(child=serializers.IntegerField(min_value=1), default=list, max_length=250)


class VehicleDesk(PayrollCsrfMixin, APIView):
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.tenant = _resolve_tenant(request, self)
        self.personal = kwargs.get('personal', False)
        if not self.tenant or (not self.personal and not _resolve_campus_scope(request, self.tenant)):
            raise PermissionDenied('沒有此租戶或校區的用車權限')
        profile = staff_profile(request.user, self.tenant)
        self.coach = Coach.objects.filter(client=self.tenant, user=request.user).first() if profile and profile.is_coach else None
        role = profile.role if profile and profile.is_manager else ''
        self.review = request.user.is_superuser or (
            role in REVIEW_ROLES and user_has_admin_permission(request.user, 'vehicle_review', self.tenant))
        self.finance = request.user.is_superuser or (
            role in FINANCE_ROLES and user_has_admin_permission(request.user, 'vehicle_finance', self.tenant))
        if (self.personal and not self.coach) or (not self.personal and not (self.review or self.finance)):
            raise PermissionDenied('沒有用車功能權限')

    def campuses(self):
        campuses = Campus.objects.filter(client=self.tenant, is_active=True)
        if self.personal:
            return campuses.filter(coaches=self.coach)
        return campuses.filter(pk__in=self.request.campus_ids)

    def vehicles(self):
        campuses = self.campuses()
        return Vehicle.objects.filter(campus__client=self.tenant).filter(
            Q(campus__in=campuses) | Q(shared_campuses__in=campuses)).distinct()

    def trips(self):
        trips = VehicleTrip.objects.filter(campus__client=self.tenant)
        if self.personal:
            return trips.filter(Q(driver=self.coach) | Q(participants=self.coach)).distinct()
        return trips.filter(campus__in=self.campuses())

    def eligible(self):
        return Coach.objects.filter(client=self.tenant, campuses__in=self.campuses(), user__is_active=True,
                                    pay_rules__is_active=True, pay_rules__hourly_rate__gt=0).distinct()

    def policy(self):
        return VehiclePolicy.objects.filter(client=self.tenant).first()

    def exempt_resorts(self, policy):
        resorts = Resorts.objects.filter(client=self.tenant)
        return policy.exempt_resorts.all() if policy else resorts.filter(
            Q(name__icontains='tomamu') | Q(display_name__icontains='星野'))

    def trip_payload(self, trip):
        def photo_url(file, key):
            if not file:
                return None
            return reverse('coach-vehicle-file' if self.personal else 'admin-vehicle-file', kwargs={
                'client_code': self.tenant.internal_code, 'trip_id': trip.pk, 'file_key': key,
            })
        owner = not self.personal or trip.driver_id == self.coach.pk
        charges = trip.charges.all() if not self.personal else (charge for charge in trip.charges.all() if charge.coach_id == self.coach.pk)
        return {
            'id': trip.pk, 'campus': trip.campus_id, 'campus_name': trip.campus.name,
            'driver': trip.driver.name, 'vehicle': trip.vehicle_id,
            'vehicle_name': trip.vehicle.name if trip.vehicle_id else '',
            'purpose': trip.purpose, 'status': trip.status, 'starts_at': trip.starts_at, 'ends_at': trip.ends_at,
            'resort': trip.resort.display_name if trip.resort_id else '', 'note': trip.note,
            'decision_note': trip.decision_note, 'owner': owner,
            'participants': [coach.name for coach in trip.participants.all()],
            'departure_km': trip.departure_km, 'return_km': trip.return_km,
            'departure_photo': photo_url(trip.departure_photo, 'departure'),
            'return_photo': photo_url(trip.return_photo, 'return'),
            'amount_yen': trip.amount_yen, 'amount_twd': trip.amount_twd,
            'expenses': [{'id': item.pk, 'kind': item.kind, 'amount_yen': item.amount_yen, 'note': item.note,
                          'reimbursable': trip.purpose != 'private' or item.kind == 'fuel',
                          'receipt': photo_url(item.receipt, str(item.pk))} for item in trip.expenses.all()] if owner else [],
            'charges': [{'id': charge.pk, 'coach': charge.coach.name, 'amount_twd': charge.amount_twd,
                         'balance': charge_balance(charge, include_drafts=False), 'first_month': charge.first_month,
                         'last_month': charge.last_month, 'manual_due': self.manual_due(charge)}
                        for charge in charges],
        }

    @staticmethod
    def manual_due(charge):
        return timezone.localdate(timezone=JAPAN_TIME) > payroll_cutoff(charge.last_month, charge.trip.payroll_day or 1)

    def get(self, request, client_code, personal=False):
        campuses = self.campuses()
        policy = self.policy()
        resorts = Resorts.objects.filter(client=self.tenant).prefetch_related('campuses')
        campus_ids = {campus.pk for campus in campuses}
        exempt = list(self.exempt_resorts(policy).values_list('pk', flat=True))
        trips = self.trips().select_related('campus', 'driver', 'vehicle', 'resort').prefetch_related('participants', 'expenses', 'charges__coach')
        start = serializers.DateField().run_validation(request.query_params['from']) if request.query_params.get('from') else None
        end = serializers.DateField().run_validation(request.query_params['to']) if request.query_params.get('to') else None
        if start and end and end < start:
            raise ValidationError('結束日不能早於開始日')
        if start:
            trips = trips.filter(ends_at__gt=datetime.combine(start, time.min, JAPAN_TIME))
        if end:
            trips = trips.filter(starts_at__lt=datetime.combine(end + timedelta(days=1), time.min, JAPAN_TIME))
        demands = []
        if self.review and not self.personal:
            today = timezone.localdate(timezone=JAPAN_TIME)
            bookings = Booking.objects.filter(
                reservation__group__campus__in=campuses, reservation__group__client=self.tenant,
                reservation__resort__client=self.tenant, reservation__status__in=SCHEDULED_RESERVATION_STATUSES,
                is_scheduled=True, date__range=(start or today, end or today + timedelta(days=30)),
            ).exclude(reservation__resort_id__in=exempt)
            demands = list(bookings.values('date', 'reservation__group__campus_id',
                                           'reservation__group__campus__name', 'reservation__resort_id',
                                           'reservation__resort__display_name').order_by('date').distinct()[:150])
        return Response({'data': {
            'review': self.review and not self.personal, 'finance': self.finance and not self.personal,
            'campuses': list(campuses.values('id', 'name')),
            'settings_campuses': list(Campus.objects.filter(client=self.tenant, is_active=True).values('id', 'name')) if not self.personal and self.finance and request.can_view_all_campuses else list(campuses.values('id', 'name')),
            'resorts': [{'id': resort.pk, 'name': resort.display_name, 'exempt': resort.pk in exempt,
                        'campuses': [campus.pk for campus in resort.campuses.all()]}
                       for resort in resorts if (not self.personal and self.finance) or any(campus.pk in campus_ids for campus in resort.campuses.all())],
            'coaches': [{'id': coach.pk, 'name': coach.name, 'campuses': [campus.pk for campus in coach.campuses.all() if campus.client_id == self.tenant.pk]}
                        for coach in self.eligible().prefetch_related('campuses').order_by('name', 'id')],
            'coach_id': self.coach.pk if self.personal else None,
            'eligible': not self.personal or self.eligible().filter(pk=self.coach.pk).exists(),
            'vehicles': [{'id': vehicle.pk, 'campus': vehicle.campus_id, 'name': vehicle.name, 'plate': vehicle.plate,
                          'active': vehicle.active, 'shared_campuses': [c.pk for c in vehicle.shared_campuses.all()]}
                         for vehicle in self.vehicles().prefetch_related('shared_campuses')] if not self.personal else [],
            'policy': {'yen_per_km': policy.yen_per_km, 'yen_per_twd': policy.yen_per_twd,
                       'payroll_day': policy.payroll_day, 'exempt_resorts': exempt} if policy and self.finance and not self.personal else None,
            'trips': [self.trip_payload(trip) for trip in trips.order_by('-starts_at', '-pk')],
            'demands': demands,
        }})

    @transaction.atomic
    def post(self, request, client_code, personal=False):
        Client.objects.select_for_update().get(pk=self.tenant.pk)
        if not hasattr(request.data, 'get'):
            raise ValidationError('用車資料格式錯誤')
        action = serializers.CharField(max_length=20).run_validation(request.data.get('action'))
        if action == 'request':
            return self.request_trip(request.data)
        if not self.personal and action in ('policy', 'vehicle'):
            if not self.finance:
                raise PermissionDenied('沒有車輛與費率設定權限')
            return self.save_settings(action, request.data)
        trip_id = serializers.IntegerField(min_value=1).run_validation(request.data.get('trip'))
        # Avoid SELECT FOR UPDATE on a DISTINCT result or on nullable joined tables.
        trip = get_object_or_404(self.trips(), pk=trip_id)
        trip = VehicleTrip.objects.select_for_update().get(pk=trip.pk)
        if self.personal:
            if trip.driver_id != self.coach.pk:
                raise PermissionDenied('僅駕駛可登記及修正用車資料')
            return self.record_trip(action, trip)
        return self.review_trip(action, trip)

    def request_trip(self, data):
        form = TripRequest(data=data)
        form.is_valid(raise_exception=True)
        values = form.validated_data
        campus = get_object_or_404(self.campuses(), pk=values.pop('campus'))
        driver_id = values.pop('driver', None)
        if not self.personal and (not self.review or values['purpose'] != 'lesson'):
            raise PermissionDenied('主管可建立課程用車，借車由教練提出')
        driver = get_object_or_404(self.eligible().filter(campuses=campus), pk=self.coach.pk if self.personal else driver_id)
        riders = set(values.pop('participants')) - {driver.pk}
        if self.eligible().filter(campuses=campus, pk__in=riders).count() != len(riders):
            raise ValidationError('同行者須為同校區的領薪教練')
        resort_id = values.pop('resort', None)
        if values['purpose'] == 'lesson':
            resort = get_object_or_404(campus.resorts.filter(client=self.tenant), pk=resort_id)
            if self.exempt_resorts(self.policy()).filter(pk=resort.pk).exists():
                raise ValidationError('此雪場不需要安排課程用車')
            values['resort'] = resort
        if values['purpose'] == 'shopping':
            if not riders:
                raise ValidationError('生活採買至少需要兩位領薪教練')
            self.check_shopping_week(values['starts_at'])
        trip = VehicleTrip.objects.create(campus=campus, driver=driver, **values)
        trip.participants.set(riders)
        return Response({'data': self.trip_payload(trip)}, status=201)

    def check_shopping_week(self, starts_at, trip_id=None):
        day = timezone.localdate(starts_at, JAPAN_TIME)
        monday = day - timedelta(days=day.weekday())
        start = datetime.combine(monday, time.min, JAPAN_TIME)
        if VehicleTrip.objects.filter(campus__client=self.tenant, purpose='shopping',
                                      starts_at__gte=start, starts_at__lt=start + timedelta(days=7)).exclude(
            Q(status='rejected') | Q(pk=trip_id)
        ).exists():
            raise ValidationError('這一週全校共用的生活採買用車已有人申請')

    def save_settings(self, action, data):
        if action == 'policy':
            if not self.request.can_view_all_campuses:
                raise PermissionDenied('全校費率須由有全校權限的行政設定')
            form = PolicyForm(data=data)
            form.is_valid(raise_exception=True)
            values = form.validated_data
            ids = set(values.pop('exempt_resorts'))
            resorts = Resorts.objects.filter(client=self.tenant, pk__in=ids)
            if resorts.count() != len(ids) or values['yen_per_km'] <= 0 or values['yen_per_twd'] < Decimal('0.01'):
                raise ValidationError('請填寫大於零的費率、至少 0.01 的匯率，並選擇本校雪場')
            policy, _ = VehiclePolicy.objects.update_or_create(client=self.tenant, defaults=values)
            policy.exempt_resorts.set(resorts)
        else:
            form = VehicleForm(data=data)
            form.is_valid(raise_exception=True)
            values = form.validated_data
            campus = get_object_or_404(self.campuses(), pk=values.pop('campus'))
            ids = set(values.pop('shared_campuses')) - {campus.pk}
            scope = Campus.objects.filter(client=self.tenant, is_active=True) if self.request.can_view_all_campuses else self.campuses()
            shared = scope.filter(pk__in=ids)
            if shared.count() != len(ids):
                raise ValidationError('共用校區必須屬於同一租戶及授權範圍')
            vehicle_id = serializers.IntegerField(min_value=1).run_validation(data['vehicle']) if data.get('vehicle') else None
            vehicle = get_object_or_404(Vehicle, pk=vehicle_id, campus=campus) if vehicle_id else Vehicle(campus=campus)
            if Vehicle.objects.filter(campus__client=self.tenant, plate__iexact=values['plate']).exclude(pk=vehicle.pk).exists():
                raise ValidationError('這個租戶已使用相同車牌，跨校用車請設定共用校區')
            for field, value in values.items():
                setattr(vehicle, field, value)
            try:
                with transaction.atomic():
                    vehicle.save()
            except IntegrityError as exc:
                raise ValidationError('這個校區已使用相同車牌') from exc
            vehicle.shared_campuses.set(shared)
        return Response({'data': True})

    def review_trip(self, action, trip):
        request = self.request
        if action in {'approve', 'reject', 'review'}:
            if not self.review:
                raise PermissionDenied('沒有排車或審核用車紀錄權限')
            if action == 'review' and trip.status == 'returned':
                trip.status, trip.reviewed_by = 'reviewed', request.user
            elif action == 'reject' and trip.status in {'pending', 'approved'}:
                trip.status, trip.approved_by = 'rejected', request.user
                trip.decision_note = serializers.CharField(max_length=500).run_validation(request.data.get('note'))
            elif action == 'approve' and trip.status == 'pending':
                self.assign_vehicle(trip, request.data.get('vehicle'))
                trip.status, trip.approved_by = 'approved', request.user
            else:
                raise ValidationError('此用車狀態無法進行此操作')
        elif action in {'settle', 'collect'}:
            if not self.finance:
                raise PermissionDenied('沒有車輛費用核准權限')
            if action == 'collect':
                return self.collect_charge(trip)
            if trip.status != 'reviewed':
                raise ValidationError('用車紀錄須先審核')
            if trip.purpose == 'private':
                policy = self.policy()
                if not policy or min(policy.yen_per_km, policy.yen_per_twd, policy.payroll_day) <= 0:
                    raise ValidationError('請先設定日圓費率、匯率與給薪日')
                ids = [trip.driver_id, *trip.participants.order_by('pk').values_list('pk', flat=True)]
                create_trip_charges(trip, policy, ids, timezone.now())
            trip.status, trip.settled_by = 'settled', request.user
        else:
            raise ValidationError('未知的用車操作')
        trip.save()
        return Response({'data': self.trip_payload(trip)})

    def assign_vehicle(self, trip, raw_id):
        vehicle_id = serializers.IntegerField(min_value=1).run_validation(raw_id)
        vehicle = get_object_or_404(self.vehicles(), pk=vehicle_id, active=True)
        if vehicle.campus_id != trip.campus_id and not vehicle.shared_campuses.filter(pk=trip.campus_id).exists():
            raise ValidationError('此車輛未開放給申請校區')
        if vehicle.trips.filter(
            status__in=['approved', 'driving'], starts_at__lt=trip.ends_at, ends_at__gt=trip.starts_at,
        ).exists():
            raise ValidationError('這輛車在所選時段已有安排，請先處理原用車紀錄或選擇其他車輛')
        if trip.purpose != 'lesson' and VehicleTrip.objects.filter(
            Q(campus_id=vehicle.campus_id) | Q(campus__shared_vehicles=vehicle),
            campus__client=self.tenant, status='pending', purpose='lesson',
            starts_at__lt=trip.ends_at, ends_at__gt=trip.starts_at,
        ).exists():
            raise ValidationError('同時段有課程用車待安排，請先處理課程用車')
        if trip.purpose != 'lesson' and self.unassigned_lesson_demand(trip, vehicle):
            raise ValidationError('同時段有課程尚未排車，請先安排課程用車')
        if trip.purpose == 'shopping':
            self.check_shopping_week(trip.starts_at, trip.pk)
        trip.vehicle = vehicle

    def unassigned_lesson_demand(self, trip, vehicle):
        first, last = (timezone.localtime(value, JAPAN_TIME) for value in (trip.starts_at, trip.ends_at))
        campus_ids = Campus.objects.filter(Q(pk=vehicle.campus_id) | Q(shared_vehicles=vehicle), client=self.tenant)
        exempt = self.exempt_resorts(self.policy())
        needs = Booking.objects.filter(
            reservation__group__client=self.tenant, reservation__group__campus__in=campus_ids,
            reservation__resort__client=self.tenant, reservation__status__in=SCHEDULED_RESERVATION_STATUSES,
            is_scheduled=True, date__range=(first.date(), last.date()),
        ).exclude(reservation__resort__in=exempt).values_list(
            'date', 'start_time', 'end_time', 'reservation__group__campus_id', 'reservation__resort_id',
        ).distinct()
        for day, start_time, end_time, campus_id, resort_id in needs:
            start, end = (datetime.combine(day, value, JAPAN_TIME) for value in (start_time, end_time))
            if start < last and end > first and not VehicleTrip.objects.filter(
                campus_id=campus_id, resort_id=resort_id, purpose='lesson',
                status__in=['approved', 'driving', 'returned', 'reviewed', 'settled'],
                starts_at__lte=start, ends_at__gte=end,
            ).exists():
                return True
        return False

    def collect_charge(self, trip):
        charge_id = serializers.IntegerField(min_value=1).run_validation(self.request.data.get('charge'))
        charge = get_object_or_404(trip.charges.select_for_update(), pk=charge_id)
        amount = serializers.IntegerField(min_value=1).run_validation(self.request.data.get('amount'))
        expected_balance = serializers.IntegerField(min_value=1).run_validation(self.request.data.get('expected_balance'))
        balance = charge_balance(charge)
        if balance != expected_balance:
            raise ValidationError('收款餘額已變更，請重新載入後核對')
        if not self.manual_due(charge) or amount > balance:
            raise ValidationError('收款金額不得超過待人工收取的餘額')
        charge.collected_twd += amount
        charge.save(update_fields=['collected_twd'])
        return Response({'data': self.trip_payload(trip)})

    def record_trip(self, action, trip):
        request = self.request
        if action not in {'depart', 'return'}:
            raise ValidationError('未知的用車操作')
        departure = action == 'depart'
        if (departure and trip.status != 'approved') or (not departure and trip.status not in {'driving', 'returned', 'reviewed'}):
            raise ValidationError('此用車狀態無法登記或修正')
        if departure and not trip.starts_at <= timezone.now() < trip.ends_at:
            raise ValidationError('請在已核准的用車時段內登記出車')
        try:
            km = number(request.data.get('km'), '里程', 999999999, 1)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        if departure and VehicleTrip.objects.filter(vehicle=trip.vehicle, status='driving').exclude(pk=trip.pk).exists():
            raise ValidationError('這輛車尚未歸還，無法出車')
        if not departure and km < trip.departure_km:
            raise ValidationError('歸還里程不得低於出發里程')
        field = 'departure_photo' if departure else 'return_photo'
        photo = request.FILES.get('photo')
        photo_field = getattr(trip, field)
        if not photo and not photo_field:
            raise ValidationError('請上傳里程照片')
        uploads = [(photo_field, photo, self.photo_extension(photo))] if photo else []
        expenses = []
        old = [photo_field.name] if photo and photo_field else []
        if not departure:
            expenses, receipts, replaced = self.prepare_expenses(trip)
            uploads.extend(receipts)
            old.extend(replaced)
        saved = []
        try:
            for target, upload, extension in uploads:
                target.save(f'{trip.pk}/{uuid4().hex}{extension}', upload, save=False)
                saved.append((target.storage, target.name))
            if departure:
                trip.departure_km, trip.departed_at, trip.status = km, timezone.now(), 'driving'
            else:
                trip.return_km, trip.status, trip.reviewed_by = km, 'returned', None
                trip.returned_at = trip.returned_at or timezone.now()
                if expenses is not None:
                    trip.expenses.exclude(pk__in=[item.pk for item in expenses if item.pk]).delete()
                    for item in expenses:
                        item.save()
            trip.save()
        except Exception:
            for storage, name in saved:
                storage.delete(name)
            raise
        for name in old:
            transaction.on_commit(lambda value=name: photo_field.storage.delete(value), robust=True)
        return Response({'data': self.trip_payload(trip)})

    @staticmethod
    def photo_extension(upload):
        try:
            kind, extension = validate_course_upload(upload)
            if kind != 'photo':
                raise ValueError('請上傳照片')
            return extension
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

    def prepare_expenses(self, trip):
        request = self.request
        if 'expenses' not in request.data:
            return None, [], []
        rows = serializers.JSONField(binary=True).run_validation(request.data['expenses'])
        if not isinstance(rows, list) or len(rows) > 20:
            raise ValidationError('每筆用車最多可登記 20 筆支出')
        existing = {item.pk: item for item in trip.expenses.all()}
        expenses, receipts, replaced = [], [], []
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                raise ValidationError('支出資料格式錯誤')
            expense_id = row.get('id')
            if expense_id is not None and (type(expense_id) is not int or expense_id not in existing):
                raise ValidationError('找不到這筆用車支出')
            item = existing.pop(expense_id) if expense_id else VehicleExpense(trip=trip)
            item.kind = serializers.ChoiceField(choices=VehicleExpense.KINDS).run_validation(row.get('kind'))
            item.amount_yen = serializers.IntegerField(min_value=1, max_value=10000000).run_validation(row.get('amount_yen'))
            item.note = serializers.CharField(allow_blank=True, max_length=200).run_validation(row.get('note', ''))
            receipt = request.FILES.get(f'receipt_{index}')
            if not receipt and not item.receipt and (trip.purpose != 'private' or item.kind == 'fuel'):
                raise ValidationError('公用支出與代墊加油費須附收據')
            if receipt:
                if item.receipt:
                    replaced.append(item.receipt.name)
                receipts.append((item.receipt, receipt, self.photo_extension(receipt)))
            expenses.append(item)
        replaced.extend(item.receipt.name for item in existing.values() if item.receipt)
        return expenses, receipts, replaced


class VehicleFile(VehicleDesk):
    http_method_names = ['get', 'head', 'options']

    def get(self, request, client_code, trip_id, file_key, personal=False):
        trip = get_object_or_404(self.trips(), pk=trip_id)
        if file_key == 'departure':
            file = trip.departure_photo
        elif file_key == 'return':
            file = trip.return_photo
        elif file_key.isascii() and file_key.isdecimal() and len(file_key) <= 19:
            if self.personal and trip.driver_id != self.coach.pk:
                raise PermissionDenied('僅駕駛與管理人員可讀取收據')
            file = get_object_or_404(trip.expenses, pk=file_key).receipt
        else:
            raise ValidationError('附件識別碼無效')
        if not file:
            raise ValidationError('沒有這份附件')
        return private_file_response(SimpleNamespace(file=file))
