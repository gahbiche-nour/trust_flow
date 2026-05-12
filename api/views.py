import math
import logging

from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from drf_spectacular.utils import OpenApiParameter, extend_schema, OpenApiExample, OpenApiResponse
from drf_spectacular.types import OpenApiTypes

from api.konnect_client import KonnectAgentClient
from api.models import AgentAudit, Transaction
from api.serializers import (
    AgentVerifySerializer,
    AgentVerifySuccessSerializer,
    AgentVerifyBlockedSerializer,
    WebhookResponseSerializer,
)

logger = logging.getLogger(__name__)


class AgentVerifyView(APIView):
    """
    POST /api/agent/verify/

    The agentic handshake. 
    
    Requires a valid JWT Bearer token.

    Flow:
      . Validate input (amount, buyer/seller GPS coords).
      . Confirm physical proximity (Euclidean delta ≤ 0.001 , ~100 m).
      . If close enough → initiate Konnect payment .
      . Persist paymentRef on the Transaction and write an AgentAudit entry.
      . Return the Konnect hosted-payment URL to the caller.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Trigger Agentic Handshake",
        description=(
            "Verifies that buyer and seller are physically close (≤ ~100 m) "
            "then initiates a Konnect payment. Requires JWT authentication."
        ),
        request=AgentVerifySerializer,
        responses={
            200: OpenApiResponse(
                response=AgentVerifySuccessSerializer,
                description="Proximity passed — Konnect payment initiated.",
            ),
            400: OpenApiResponse(description="Invalid request payload."),
            403: OpenApiResponse(
                response=AgentVerifyBlockedSerializer,
                description="Proximity check failed — transaction blocked.",
            ),
            404: OpenApiResponse(description="Transaction not found."),
            500: OpenApiResponse(description="Konnect API call failed."),
        },
        examples=[
            OpenApiExample(
                "Successful Handshake",
                summary="Buyer and seller are at the same spot",
                value={
                    "amount": "5",
                    "lat_b": 36.8001,
                    "lon_b": 10.1801,
                    "lat_s": 36.8001,
                    "lon_s": 10.1801,
                },
                request_only=True,
            ),
            OpenApiExample(
                "Distance Too Far",
                summary="Blocked — parties are in different cities",
                value={
                    "amount": "5",
                    "lat_b": 36.8001,
                    "lon_b": 10.1801,
                    "lat_s": 35.0000,
                    "lon_s": 9.0000,
                },
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        current_user = request.user

        # --- Validate input ---
        serializer = AgentVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        data = serializer.validated_data
        
        # --- Proximity check ---
        lat_b, lon_b = data["lat_b"], data["lon_b"]
        lat_s, lon_s = data["lat_s"], data["lon_s"]

        delta = math.sqrt((lat_s - lat_b) ** 2 + (lon_s - lon_b) ** 2)
        PROXIMITY_THRESHOLD = 0.001  # ~100–110 m in decimal degrees
        
        if delta > PROXIMITY_THRESHOLD:
            tx = Transaction.objects.create(
                amount=data["amount"],
                status=Transaction.STATUS_SECURED,
            )
            # Always write an audit entry 
           
            AgentAudit.objects.create(
                transaction=tx,
                reasoning=(
                    f"User {current_user.id} attempted handshake. "
                    f"Proximity failed (delta={delta:.5f} > {PROXIMITY_THRESHOLD}). "
                    "Transaction blocked."
                ),
            )
            return Response(
                {"decision": "BLOCKED", "reason": "Proximity failed."},
                status=403,
            )


        # --- Create Transaction (SECURED)  after proximity passes ---
        tx = Transaction.objects.create(
            amount=data["amount"],
            status=Transaction.STATUS_SECURED,
        )
        # --- Initiate Konnect payment ---
        payment_data = KonnectAgentClient.initiate_payment(
            receiver_wallet_id=settings.KONNECT_WALLET_ID,
            amount_tnd=data["amount"],
           
        )

        if not payment_data:
            AgentAudit.objects.create(
                transaction=tx,
                reasoning=(
                    f"User {current_user.id} passed proximity (delta={delta:.5f}) "
                    "but Konnect payment initiation failed."
                ),
            )
            return Response(
                {"decision": "BLOCKED", "reason": "Konnect API initiation failed."},
                status=500,
            )

        # --- Log ---
        tx.status = Transaction.STATUS_PENDING
        tx.konnect_payment_ref = payment_data.get("paymentRef")
        tx.save(update_fields=["status", "konnect_payment_ref", "updated_at"])

        AgentAudit.objects.create(
            transaction=tx,
            reasoning=(
                f"User {current_user.id} confirmed handshake (delta={delta:.5f}). "
                f"Konnect payment {tx.konnect_payment_ref} initiated successfully."
            ),
        )

        # --- return payment URL ---
        return Response(
            {
                "decision": "SUCCESS",
                "pay_url": payment_data.get("payUrl"),
                "payment_ref": tx.konnect_payment_ref,
            },
            status=200,
        )


class KonnectWebhookView(APIView):
    """
    GET /api/webhooks/konnect/
 
    Receives Konnect payment status notifications via a GET request.
    (called by Konnect servers)
 
 
    Flow:
      . Extract payment_ref from query params (METHOD handle_webhook).
      . Cross-verify via the Konnect API (METHOD get_payment_details).
      . On confirmed completion → mark Transaction as RELEASED, write AgentAudit.
    """
 
    permission_classes = [AllowAny]
 
    @extend_schema(
        summary="Konnect Payment Webhook",
        description=(
            "Called by Konnect servers when a payment is completed. "
            "This is a GET request — Konnect sends ?payment_ref=<id> as a query parameter. "
            "No authentication required. Always returns HTTP 200 to prevent Konnect retries."
        ),
        parameters=[
            OpenApiParameter(
                name="payment_ref",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=True,
                description="Unique payment reference sent by Konnect.",
            )
        ],
        responses={
            200: OpenApiResponse(
                response=WebhookResponseSerializer,
                description="'verified' if released, 'ignored' otherwise.",
            ),
            400: OpenApiResponse(description="Missing payment_ref query parameter."),
            404: OpenApiResponse(description="Transaction matching paymentRef not found."),
        },
    )
    def get(self, request):
        # extract payment_ref 
        ref = KonnectAgentClient.handle_webhook(request.GET)
 
        if not ref:
            logger.warning("Konnect webhook called with no payment_ref query param.")
            return Response({"error": "Missing payment_ref parameter."}, status=400)
 
        try:
            tx = Transaction.objects.get(konnect_payment_ref=ref)
        except Transaction.DoesNotExist:
            logger.warning(f"Konnect webhook: no transaction found for ref={ref}")
            return Response({"error": "Transaction not found."}, status=404)
 
        # verify with the Konnect API (to not trust the webhook signal alone
        details = KonnectAgentClient.get_payment_details(ref)
        payment_status = (
            details.get("payment", {}).get("status") if details else None
        )
 
        if payment_status == "completed":
            tx.status = Transaction.STATUS_RELEASED
            tx.save(update_fields=["status", "updated_at"])
 
            AgentAudit.objects.create(
                transaction=tx,
                reasoning=(
                    f"Konnect webhook received (GET ?payment_ref={ref}) + "
                    f"API cross-check confirmed 'completed'. Transaction RELEASED."
                ),
            )
            logger.info(f"Transaction {tx.id} RELEASED. ref={ref}")
            return Response({"status": "verified"}, status=200)
 
        # if API did not confirm completion : log and ignore
        logger.warning(
            f"Konnect webhook/API mismatch for ref={ref}. "
            f"API returned: {payment_status}"
        )
        AgentAudit.objects.create(
            transaction=tx,
            reasoning=(
                f"Konnect webhook received for ref={ref} "
                f"but API returned status='{payment_status}'. No state change."
            ),
        )
        return Response({"status": "ignored"}, status=200)
 