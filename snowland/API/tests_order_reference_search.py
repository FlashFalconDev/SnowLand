from django.test import TestCase

from API import tests_order_assignment_scope as assignment_fixtures
from booking.models import ReservationGroup


class OrderReferenceSearchTests(TestCase):
    setUp = assignment_fixtures.OrderAssignmentScopeTests.setUp

    def test_headquarters_can_search_stored_order_reference_without_other_tenants(self):
        reference = 'IMPORTED-SNOW-REFERENCE'
        self.group.order_number = reference
        self.group.save(update_fields=['order_number'])
        ReservationGroup.objects.create(client=self.other_tenant, order_number=reference, name='Other tenant')
        response = self.api.get('/api/admin/snowland/orders/', {'search': reference})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([row['id'] for row in response.data['data']['list']], [self.group.pk])

    def test_reference_search_does_not_expand_selected_campus(self):
        reference = 'IMPORTED-SNOW-REFERENCE'
        self.group.order_number = reference
        self.group.save(update_fields=['order_number'])
        response = self.api.get('/api/admin/snowland/orders/', {'search': reference},
                                HTTP_X_CAMPUS_ID=str(self.other_campus.pk))
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['data']['list'], [])
