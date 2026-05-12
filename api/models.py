import uuid
from django.db import models


class Transaction(models.Model):
    """
    Represents a TrustFlow transaction between a buyer and a seller.

    Lifecycle:
        SECURED  → payment not yet initiated
        PENDING  → Konnect payment initiated, awaiting buyer completion
        RELEASED → payment confirmed completed by Konnect webhook + API check
        FAILED   → payment failed or was rejected
    """

    STATUS_SECURED = "SECURED"
    STATUS_PENDING = "PENDING"
    STATUS_RELEASED = "RELEASED"
    STATUS_FAILED = "FAILED"

    STATUS_CHOICES = [
        (STATUS_SECURED, "Secured"),
        (STATUS_PENDING, "Pending"),
        (STATUS_RELEASED, "Released"),
        (STATUS_FAILED, "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    amount = models.DecimalField(max_digits=10, decimal_places=3)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SECURED)

    # Set once Konnect payment is initiated 
    konnect_payment_ref = models.CharField(max_length=150, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"TX {self.id} | {self.amount} TND | {self.status}"


class AgentAudit(models.Model):
    """
    the audit log entry written by the agent for every decision 
    """

    transaction = models.ForeignKey(
        Transaction, on_delete=models.CASCADE, related_name="audits"
    )
    reasoning = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        return f"Audit @ {self.timestamp} for TX {self.transaction_id}"
