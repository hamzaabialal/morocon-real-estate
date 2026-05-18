from django.apps import AppConfig


class PropertiesConfig(AppConfig):
    """Configuration for the properties app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.properties"

    def ready(self):
        from apps.properties import signals  # noqa: F401
