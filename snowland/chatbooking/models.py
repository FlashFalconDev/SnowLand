import uuid

from django.conf import settings
from django.db import models


class ChatBookingSession(models.Model):
    CHANNEL_API = "api"
    CHANNEL_LINE = "line"
    CHANNEL_CHOICES = [
        (CHANNEL_API, "Internal API"),
        (CHANNEL_LINE, "LINE"),
    ]

    STATUS_ACTIVE = "active"
    STATUS_AWAITING_CONFIRMATION = "awaiting_confirmation"
    STATUS_CONFIRMED = "confirmed"
    STATUS_ESCALATED = "escalated"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_EXPIRED = "expired"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_AWAITING_CONFIRMATION, "Awaiting confirmation"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_ESCALATED, "Escalated"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_EXPIRED, "Expired"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(
        "Client.Client",
        on_delete=models.CASCADE,
        related_name="chat_booking_sessions",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chat_booking_sessions",
    )
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default=CHANNEL_API)
    external_user_id = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    current_step = models.CharField(max_length=64, blank=True, default="service_type")
    slot_values = models.JSONField(default=dict, blank=True)
    state_version = models.PositiveIntegerField(default=1)
    access_token_hash = models.CharField(max_length=64)
    ai_enabled = models.BooleanField(default=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["client", "channel", "external_user_id"]),
            models.Index(fields=["client", "status", "updated_at"]),
        ]

    def __str__(self):
        return f"{self.client.internal_code}:{self.channel}:{self.pk}"


class ChatBookingMessage(models.Model):
    DIRECTION_INBOUND = "inbound"
    DIRECTION_OUTBOUND = "outbound"
    DIRECTION_SYSTEM = "system"
    DIRECTION_CHOICES = [
        (DIRECTION_INBOUND, "Inbound"),
        (DIRECTION_OUTBOUND, "Outbound"),
        (DIRECTION_SYSTEM, "System"),
    ]
    SENDER_CUSTOMER = "customer"
    SENDER_AI = "ai"
    SENDER_AGENT = "agent"
    SENDER_SYSTEM = "system"
    SENDER_CHOICES = [
        (SENDER_CUSTOMER, "Customer"),
        (SENDER_AI, "AI"),
        (SENDER_AGENT, "Agent"),
        (SENDER_SYSTEM, "System"),
    ]

    session = models.ForeignKey(
        ChatBookingSession,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    direction = models.CharField(max_length=16, choices=DIRECTION_CHOICES)
    sender_type = models.CharField(max_length=16, choices=SENDER_CHOICES)
    content = models.TextField()
    external_message_key = models.CharField(
        max_length=320,
        null=True,
        blank=True,
        unique=True,
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["session", "created_at"])]


class ChatBookingDraft(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_QUOTED = "quoted"
    STATUS_COMMITTED = "committed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_QUOTED, "Quoted"),
        (STATUS_COMMITTED, "Committed"),
        (STATUS_FAILED, "Failed"),
    ]

    session = models.OneToOneField(
        ChatBookingSession,
        on_delete=models.CASCADE,
        related_name="draft",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    cart = models.JSONField(default=list, blank=True)
    contact = models.JSONField(default=dict, blank=True)
    discount_code = models.CharField(max_length=100, blank=True, default="")
    quote = models.JSONField(default=dict, blank=True)
    quote_hash = models.CharField(max_length=64, blank=True, default="")
    quote_expires_at = models.DateTimeField(null=True, blank=True)
    reservation_group_ids = models.JSONField(default=list, blank=True)
    payment_snapshot = models.JSONField(default=dict, blank=True)
    last_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ChatBookingEvent(models.Model):
    STATUS_RECEIVED = "received"
    STATUS_PROCESSING = "processing"
    STATUS_PROCESSED = "processed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_RECEIVED, "Received"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_PROCESSED, "Processed"),
        (STATUS_FAILED, "Failed"),
    ]

    client = models.ForeignKey(
        "Client.Client",
        on_delete=models.CASCADE,
        related_name="chat_booking_events",
    )
    session = models.ForeignKey(
        ChatBookingSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )
    channel = models.CharField(max_length=20)
    external_event_id = models.CharField(max_length=255)
    payload_hash = models.CharField(max_length=64, blank=True, default="")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_RECEIVED)
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    response_sent_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["client", "channel", "external_event_id"],
                name="chatbooking_unique_external_event",
            ),
        ]


class ChatBookingToolInvocation(models.Model):
    STATUS_PROCESSING = "processing"
    STATUS_SUCCEEDED = "succeeded"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PROCESSING, "Processing"),
        (STATUS_SUCCEEDED, "Succeeded"),
        (STATUS_FAILED, "Failed"),
    ]

    session = models.ForeignKey(
        ChatBookingSession,
        on_delete=models.CASCADE,
        related_name="tool_invocations",
    )
    tool_key = models.CharField(max_length=100)
    idempotency_key = models.CharField(max_length=128)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PROCESSING)
    input_data = models.JSONField(default=dict, blank=True)
    output_data = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session", "tool_key", "idempotency_key"],
                name="chatbooking_unique_tool_invocation",
            ),
        ]


class ChatBookingHandoff(models.Model):
    STATUS_REQUESTED = "requested"
    STATUS_ASSIGNED = "assigned"
    STATUS_RESOLVED = "resolved"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_REQUESTED, "Requested"),
        (STATUS_ASSIGNED, "Assigned"),
        (STATUS_RESOLVED, "Resolved"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    session = models.OneToOneField(
        ChatBookingSession,
        on_delete=models.CASCADE,
        related_name="handoff",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_REQUESTED)
    reason = models.TextField(blank=True, default="")
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_chat_booking_handoffs",
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
