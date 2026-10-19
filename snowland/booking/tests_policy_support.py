from Client.models import Client
from booking.checkout_policies import checkout_policy_payload


def checkout_policy_acknowledgement(client_code='snowland'):
    documents = checkout_policy_payload(Client.objects.get(internal_code=client_code))['documents']
    return {'accepted_policy': True, 'policy_acceptance': {
        'terms': True, 'privacy': True,
        'terms_version': documents['terms']['version'],
        'privacy_version': documents['privacy']['version'],
    }}
