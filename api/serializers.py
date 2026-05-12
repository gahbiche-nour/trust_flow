from rest_framework import serializers
from api.models import Transaction, AgentAudit


# ---------------------------------------------------------------------------
# Request serializers
# ---------------------------------------------------------------------------

class AgentVerifySerializer(serializers.Serializer):
  
    amount = serializers.FloatField(help_text="Le montant de la transaction en TND")
   
    lat_b = serializers.FloatField(
        required=True,
        help_text="Buyer latitude (decimal degrees)",
    )
    lon_b = serializers.FloatField(
        required=True,
        help_text="Buyer longitude (decimal degrees)",
    )
    lat_s = serializers.FloatField(
        required=True,
        help_text="Seller latitude (decimal degrees)",
    )
    lon_s = serializers.FloatField(
        required=True,
        help_text="Seller longitude (decimal degrees)",
    )

   


# ---------------------------------------------------------------------------
# Response / read serializers (used by Swagger response schemas)
# ---------------------------------------------------------------------------

class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = [
            "id",
            "amount",
            "status",
            "konnect_payment_ref",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class AgentAuditSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentAudit
        fields = ["id", "transaction", "reasoning", "timestamp"]
        read_only_fields = fields


# ---------------------------------------------------------------------------
#  response serializers (for Swagger schema generation)
# ---------------------------------------------------------------------------

class AgentVerifySuccessSerializer(serializers.Serializer):
    decision = serializers.CharField(help_text="Always 'SUCCESS'")
    pay_url = serializers.URLField(help_text="Konnect hosted payment page URL")
    payment_ref = serializers.CharField(help_text="Konnect payment reference")


class AgentVerifyBlockedSerializer(serializers.Serializer):
    decision = serializers.CharField(help_text="Always 'BLOCKED'")
    reason = serializers.CharField(help_text="Human-readable block reason")


class WebhookResponseSerializer(serializers.Serializer):
    status = serializers.CharField(help_text="'verified' or 'ignored'")
