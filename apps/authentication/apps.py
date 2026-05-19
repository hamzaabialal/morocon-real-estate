from django.apps import AppConfig


class AuthenticationConfig(AppConfig):
    """Stub config; the actual auth flows live in apps.agencies for now."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.authentication"
