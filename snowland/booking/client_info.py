"""Public school identity: never serialize private company or payment settings."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from Client.models import Client
from Client.tenant_settings import google_client_id, module_enabled


@api_view(['GET'])
@permission_classes([AllowAny])
def client_info(request, client_code):
    client=Client.objects.filter(internal_code=client_code,is_active=True).first()
    if not client:
        return Response({'error':'找不到此學校或目前未開放'},status=404)
    return Response({'internal_code':client.internal_code,'name':client.name,'logo_url':client.logo_url or '', 'google_client_id':google_client_id(client), 'booking_enabled':module_enabled(client,'booking')})
