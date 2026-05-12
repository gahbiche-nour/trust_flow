import uuid
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Transaction",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("amount", models.DecimalField(decimal_places=3, max_digits=10)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("SECURED", "Secured"),
                            ("PENDING", "Pending"),
                            ("RELEASED", "Released"),
                            ("FAILED", "Failed"),
                        ],
                        default="SECURED",
                        max_length=20,
                    ),
                ),
                (
                    "konnect_payment_ref",
                    models.CharField(blank=True, max_length=150, null=True),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        default=django.utils.timezone.now,
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="AgentAudit",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "transaction",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="audits",
                        to="api.transaction",
                    ),
                ),
                ("reasoning", models.TextField()),
                ("timestamp", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["timestamp"],
            },
        ),
    ]
