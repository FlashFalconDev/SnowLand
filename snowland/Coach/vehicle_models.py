from django.conf import settings
from django.db import models

from booking.media_files import PrivateCourseMediaStorage


class VehiclePolicy(models.Model):
    client = models.OneToOneField('Client.Client', on_delete=models.CASCADE)
    yen_per_km = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    yen_per_twd = models.DecimalField(max_digits=12, decimal_places=8, default=0)
    payroll_day = models.PositiveSmallIntegerField(default=0)
    exempt_resorts = models.ManyToManyField('Resorts.Resorts', blank=True)


class Vehicle(models.Model):
    campus = models.ForeignKey('Resorts.Campus', on_delete=models.PROTECT, related_name='vehicles')
    shared_campuses = models.ManyToManyField('Resorts.Campus', blank=True, related_name='shared_vehicles')
    name = models.CharField(max_length=80)
    plate = models.CharField(max_length=32)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name', 'id']
        constraints = [models.UniqueConstraint(fields=['campus', 'plate'], name='unique_vehicle_plate_per_campus')]


class VehicleTrip(models.Model):
    PURPOSES = [('lesson', '課程用車'), ('business', '其他公用'), ('shopping', '生活採買'), ('private', '私用')]
    STATUSES = [('pending', '待核准'), ('approved', '已排車'), ('driving', '用車中'),
                ('returned', '待審核'), ('reviewed', '紀錄已審核'), ('settled', '費用已核准'), ('rejected', '未核准')]
    campus = models.ForeignKey('Resorts.Campus', on_delete=models.PROTECT)
    driver = models.ForeignKey('Coach.Coach', on_delete=models.PROTECT, related_name='vehicle_trips')
    participants = models.ManyToManyField('Coach.Coach', blank=True, related_name='shared_vehicle_trips')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, null=True, blank=True, related_name='trips')
    resort = models.ForeignKey('Resorts.Resorts', on_delete=models.PROTECT, null=True, blank=True)
    purpose = models.CharField(max_length=12, choices=PURPOSES)
    status = models.CharField(max_length=12, choices=STATUSES, default='pending')
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    note = models.CharField(max_length=500, blank=True)
    decision_note = models.CharField(max_length=500, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name='+')
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name='+')
    settled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name='+')
    departure_km = models.DecimalField(max_digits=10, decimal_places=1, null=True)
    return_km = models.DecimalField(max_digits=10, decimal_places=1, null=True)
    departure_photo = models.FileField(storage=PrivateCourseMediaStorage(), upload_to='vehicle-trips', max_length=240, blank=True)
    return_photo = models.FileField(storage=PrivateCourseMediaStorage(), upload_to='vehicle-trips', max_length=240, blank=True)
    departed_at = models.DateTimeField(null=True)
    returned_at = models.DateTimeField(null=True)
    yen_per_km = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    yen_per_twd = models.DecimalField(max_digits=12, decimal_places=8, null=True)
    payroll_day = models.PositiveSmallIntegerField(null=True)
    amount_yen = models.PositiveBigIntegerField(default=0)
    amount_twd = models.PositiveBigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['vehicle', 'status', 'starts_at'], name='vehicle_trip_schedule_idx'),
            models.Index(fields=['campus', 'purpose', 'starts_at'], name='vehicle_trip_purpose_idx'),
        ]


class VehicleExpense(models.Model):
    KINDS = [('fuel', '加油'), ('toll', '過路費'), ('other', '車輛雜支')]
    trip = models.ForeignKey(VehicleTrip, on_delete=models.CASCADE, related_name='expenses')
    kind = models.CharField(max_length=8, choices=KINDS)
    amount_yen = models.PositiveIntegerField()
    note = models.CharField(max_length=200, blank=True)
    receipt = models.FileField(storage=PrivateCourseMediaStorage(), upload_to='vehicle-receipts', max_length=240, blank=True)


class VehicleCharge(models.Model):
    trip = models.ForeignKey(VehicleTrip, on_delete=models.PROTECT, related_name='charges')
    coach = models.ForeignKey('Coach.Coach', on_delete=models.PROTECT, related_name='vehicle_charges')
    amount_twd = models.PositiveBigIntegerField()
    first_month = models.DateField()
    last_month = models.DateField()
    collected_twd = models.PositiveBigIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['trip', 'coach'], name='unique_vehicle_charge_per_coach')]


class VehicleDeduction(models.Model):
    charge = models.ForeignKey(VehicleCharge, on_delete=models.PROTECT, related_name='deductions')
    statement = models.ForeignKey('Coach.PayrollStatement', on_delete=models.CASCADE, related_name='vehicle_deductions')
    amount_twd = models.PositiveBigIntegerField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['charge', 'statement'], name='unique_vehicle_payroll_deduction')]
