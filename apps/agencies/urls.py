"""Router registrations for agencies endpoints."""
from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.agencies.views import AgencyViewSet, LoginView, LogoutView, RegisterView


router = DefaultRouter()
router.register("agencies", AgencyViewSet, basename="agency")

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
]
