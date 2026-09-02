from django.contrib import admin

from .models import (
    ChatBookingDraft,
    ChatBookingEvent,
    ChatBookingHandoff,
    ChatBookingMessage,
    ChatBookingSession,
    ChatBookingToolInvocation,
)


@admin.register(ChatBookingSession)
class ChatBookingSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "channel", "status", "state_version", "updated_at")
    list_filter = ("client", "channel", "status", "ai_enabled")
    search_fields = ("id", "external_user_id")
    readonly_fields = ("access_token_hash", "created_at", "updated_at")


@admin.register(ChatBookingMessage)
class ChatBookingMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "direction", "sender_type", "created_at")
    list_filter = ("direction", "sender_type")
    search_fields = ("content", "external_message_key")


@admin.register(ChatBookingDraft)
class ChatBookingDraftAdmin(admin.ModelAdmin):
    list_display = ("session", "status", "quote_expires_at", "updated_at")
    list_filter = ("status",)


@admin.register(ChatBookingEvent)
class ChatBookingEventAdmin(admin.ModelAdmin):
    list_display = (
        "external_event_id",
        "client",
        "channel",
        "status",
        "acknowledged_at",
        "response_sent_at",
        "created_at",
        "updated_at",
        "acknowledged_at",
        "response_sent_at",
        "processed_at",
    )
    list_filter = ("client", "channel", "status")
    search_fields = ("external_event_id",)
    readonly_fields = (
        "payload_hash",
        "created_at",
        "updated_at",
        "processed_at",
    )


@admin.register(ChatBookingToolInvocation)
class ChatBookingToolInvocationAdmin(admin.ModelAdmin):
    list_display = ("tool_key", "session", "idempotency_key", "status", "updated_at")
    list_filter = ("tool_key", "status")


@admin.register(ChatBookingHandoff)
class ChatBookingHandoffAdmin(admin.ModelAdmin):
    list_display = ("session", "status", "assigned_to", "requested_at", "updated_at")
    list_filter = ("status",)
