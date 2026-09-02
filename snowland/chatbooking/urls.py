from django.urls import path

from .views import (
    ChatSessionCollectionAPI,
    ChatSessionConfirmAPI,
    ChatSessionDetailAPI,
    ChatSessionHandoffAPI,
    ChatSessionMessagesAPI,
    ChatSessionOptionsAPI,
    ChatSessionPaymentAPI,
    ChatSessionQuoteAPI,
    ChatSessionStateAPI,
)
from .line_webhook import LineWebhookAPI


app_name = "chatbooking"

urlpatterns = [
    path("line/webhook/", LineWebhookAPI.as_view(), name="line-webhook"),
    path("sessions/", ChatSessionCollectionAPI.as_view(), name="sessions"),
    path("sessions/<uuid:session_id>/", ChatSessionDetailAPI.as_view(), name="session-detail"),
    path("sessions/<uuid:session_id>/state/", ChatSessionStateAPI.as_view(), name="session-state"),
    path("sessions/<uuid:session_id>/options/", ChatSessionOptionsAPI.as_view(), name="session-options"),
    path("sessions/<uuid:session_id>/messages/", ChatSessionMessagesAPI.as_view(), name="session-messages"),
    path("sessions/<uuid:session_id>/quote/", ChatSessionQuoteAPI.as_view(), name="session-quote"),
    path("sessions/<uuid:session_id>/confirm/", ChatSessionConfirmAPI.as_view(), name="session-confirm"),
    path("sessions/<uuid:session_id>/payment/", ChatSessionPaymentAPI.as_view(), name="session-payment"),
    path("sessions/<uuid:session_id>/handoff/", ChatSessionHandoffAPI.as_view(), name="session-handoff"),
]
