import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class KonnectAgentClient:
    BASE_URL = "https://api.sandbox.konnect.network/api/v2"

    @classmethod
    def _get_headers(cls):
        return {
            "x-api-key": settings.KONNECT_API_KEY,
            "Content-Type": "application/json",
        }

    @classmethod
    def initiate_payment(cls, receiver_wallet_id, amount_tnd
                         ):
        """
        Initiate a Konnect payment.
        Returns: {"payUrl": "...", "paymentRef": "..."} or None on failure.
        """
        endpoint = f"{cls.BASE_URL}/payments/init-payment"

        # Konnect requires amount in millimes (integer)
        amount_millimes = int(round(float(amount_tnd) * 1000))

        payload = {
            "receiverWalletId": receiver_wallet_id,
            "amount": amount_millimes,
            "token": "TND",
            "webhook": settings.KONNECT_WEBHOOK_URL,
        }

        try:
            response = requests.post(endpoint, json=payload, headers=cls._get_headers(), timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            error_text = e.response.text if hasattr(e, "response") and e.response else str(e)
            logger.error(f"Konnect Init Error: {error_text}")
            return None

    @classmethod
    def get_payment_details(cls, payment_ref):
        """
        METHOD 2 — Fetch payment details for a given paymentRef.
        Docs: api-integration/endpoints/get-payment-details
        Returns: full payment object dict or None on failure.
        """
        endpoint = f"{cls.BASE_URL}/payments/{payment_ref}"

        try:
            response = requests.get(endpoint, headers=cls._get_headers(), timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            error_text = e.response.text if hasattr(e, "response") and e.response else str(e)
            logger.error(f"Konnect Detail Error: {error_text}")
            return None


    
    @staticmethod
    def handle_webhook(query_params):
        """
        Extracts the payment reference from the query parameters.
        """
        ref = query_params.get("payment_ref")
        return ref
