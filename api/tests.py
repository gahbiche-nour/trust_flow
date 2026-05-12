
import uuid
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from api.models import AgentAudit, Transaction



def get_jwt_client(user):
    """Return an APIClient pre-loaded with a valid JWT for *user*."""
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client



class AgentVerifyTests(TestCase):
    def setUp(self):
        # Create a test user and authenticated client
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.client = get_jwt_client(self.user)

        # create a SECURED transaction 
        self.tx = Transaction.objects.create(
            amount=50.000,
            status=Transaction.STATUS_SECURED,
        )

        self.url = reverse("agent-verify")

    
    @patch("api.views.KonnectAgentClient.initiate_payment")
    def test_successful_handshake(self, mock_init):
        """Buyer and seller are at the same coordinates → payment initiated."""
        mock_init.return_value = {
            "payUrl": "https://pay.sandbox.konnect.network/sandbox_tx_abc",
            "paymentRef": "sandbox_tx_abc",
        }

        payload = {
            "amount":1,
            "lat_b": 36.8001,
            "lon_b": 10.1801,
            "lat_s": 36.8001,
            "lon_s": 10.1801,
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["decision"], "SUCCESS")
        self.assertIn("pay_url", response.data)
        self.assertIn("payment_ref", response.data)

        tx = Transaction.objects.filter(status=Transaction.STATUS_PENDING).latest("created_at")
        self.assertEqual(tx.status, Transaction.STATUS_PENDING)
        self.assertEqual(tx.konnect_payment_ref, "sandbox_tx_abc")
        audit = AgentAudit.objects.filter(transaction=tx).last()
        self.assertIn("sandbox_tx_abc", audit.reasoning) 
        self.assertIsNotNone(audit)
        self.assertIn("sandbox_tx_abc", audit.reasoning)
        print("✅ test_successful_handshake passed")

    # ------------------------------------------------------------------
    # Proximity block
    # ------------------------------------------------------------------

    def test_blocked_by_proximity(self):
        """Buyer in Tunis, seller in Sfax → BLOCKED. Verification creates a new TX."""
        payload = {
            "amount": "1", # Explicitly include amount as the view expects it for TX creation
            "lat_b": 36.8065,
            "lon_b": 10.1815,
            "lat_s": 34.7406,  # Sfax
            "lon_s": 10.7603,
        }

        # Count transactions before the call
        initial_tx_count = Transaction.objects.count()

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["decision"], "BLOCKED")

        # Verify a NEW transaction was created for this failed attempt
        self.assertEqual(Transaction.objects.count(), initial_tx_count + 1)
        
        # Query the most recent audit entry in the system
        audit = AgentAudit.objects.select_related('transaction').last()
        
        self.assertIsNotNone(audit)
        self.assertIn("Proximity failed", audit.reasoning)
        
        # Verify the audit is linked to a transaction ( NOT the one from setUp
        self.assertNotEqual(audit.transaction.id, self.tx.id)
        self.assertEqual(audit.transaction.status, Transaction.STATUS_SECURED)
        
        print("✅ test_blocked_by_proximity passed (Corrected Audit Assertion)")
    
    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    
    def test_unauthenticated_request_returns_401(self):
        """No JWT → 401 Unauthorized."""
        anon_client = APIClient()
        payload = {
            "amount": "1", 
            "lat_b": 36.8001,
            "lon_b": 10.1801,
            "lat_s": 36.8001,
            "lon_s": 10.1801,
        }
        response = anon_client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, 401)
        print("✅ test_unauthenticated_request_returns_401 passed")

   
    @patch("api.views.KonnectAgentClient.initiate_payment")
    def test_konnect_failure_returns_500(self, mock_init):
        """If Konnect API fails, return 500 and leave TX as SECURED."""
        mock_init.return_value = None  # Simulates network/API failure

        payload = {
            "amount": "1", 
            "lat_b": 36.8001,
            "lon_b": 10.1801,
            "lat_s": 36.8001,
            "lon_s": 10.1801,
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, 500)

        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, Transaction.STATUS_SECURED)
        print("✅ test_konnect_failure_returns_500 passed")



# ---------------------------------------------------------------------------
# Konnect Webhook endpoint tests
# ---------------------------------------------------------------------------

class KonnectWebhookTests(TestCase):
    def setUp(self):
        self.client = APIClient()  # No auth needed for webhooks
        self.url = reverse("konnect-webhook")

        self.tx = Transaction.objects.create(
            amount=1,
            status=Transaction.STATUS_PENDING,
            konnect_payment_ref="sandbox_tx_12345",
        )

    @patch("api.views.KonnectAgentClient.get_payment_details")
    def test_completed_webhook_releases_transaction(self, mock_details):
        """Completed webhook + API confirmation → TX RELEASED."""
        # Mock the cross-check API to return 'completed'
        mock_details.return_value = {
            "payment": {"ref": "sandbox_tx_12345", "status": "completed"}
        }

        # Use GET with query parameters to match Konnect's behavior
        response = self.client.get(self.url, {"payment_ref": "sandbox_tx_12345"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "verified")

        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, Transaction.STATUS_RELEASED)

        audit = AgentAudit.objects.filter(transaction=self.tx).last()
        self.assertIsNotNone(audit)
        self.assertIn("RELEASED", audit.reasoning)
        print("✅ test_completed_webhook_releases_transaction passed")

    @patch("api.views.KonnectAgentClient.get_payment_details")
    def test_pending_webhook_is_ignored(self, mock_details):
        """Non-completed status from API → ignored, TX stays PENDING."""
        # Even if the webhook hits, we trust the API cross-check
        mock_details.return_value = {
            "payment": {"ref": "sandbox_tx_12345", "status": "pending"}
        }

        response = self.client.get(self.url, {"payment_ref": "sandbox_tx_12345"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ignored")

        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, Transaction.STATUS_PENDING)
        print("✅ test_pending_webhook_is_ignored passed")

    