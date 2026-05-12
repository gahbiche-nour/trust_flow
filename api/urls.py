
from django.contrib import admin
from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from api.views import AgentVerifyView, KonnectWebhookView


urlpatterns = [
    path("agent/verify/", AgentVerifyView.as_view(), name="agent-verify"),
    path("webhooks/konnect/", KonnectWebhookView.as_view(), name="konnect-webhook")
    ]