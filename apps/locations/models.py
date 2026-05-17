"""Location hierarchy models for Moroccan real estate listings."""
import uuid

from django.db import models
from django.utils.text import slugify


def build_unique_slug(model_class, value: str, instance_pk=None) -> str:
    """Build a unique slug for models that require globally unique slugs."""
    base_slug = slugify(value) or "location"
    slug = base_slug
    counter = 2

    queryset = model_class.objects.filter(slug=slug)
    if instance_pk:
        queryset = queryset.exclude(pk=instance_pk)

    while queryset.exists():
        slug = f"{base_slug}-{counter}"
        queryset = model_class.objects.filter(slug=slug)
        if instance_pk:
            queryset = queryset.exclude(pk=instance_pk)
        counter += 1

    return slug


class Country(models.Model):
    """Country record for grouping cities, fixed to Morocco at launch."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=2, default="MA", unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Country"
        verbose_name_plural = "Countries"

    def __str__(self) -> str:
        return self.name


class City(models.Model):
    """City-level location such as Casablanca, Rabat, or Marrakech."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name="cities")
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "City"
        verbose_name_plural = "Cities"

    def save(self, *args, **kwargs) -> None:
        """Auto-generate a globally unique slug from the city name."""
        if not self.slug:
            self.slug = build_unique_slug(City, self.name, self.pk)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class District(models.Model):
    """District-level location within a city."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, blank=True)
    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name="districts")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("name", "city")
        verbose_name = "District"
        verbose_name_plural = "Districts"

    def save(self, *args, **kwargs) -> None:
        """Auto-generate the district slug from the district name."""
        if not self.slug:
            self.slug = slugify(self.name) or "district"
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class Neighborhood(models.Model):
    """Neighborhood-level location within a district."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, blank=True)
    district = models.ForeignKey(
        District, on_delete=models.PROTECT, related_name="neighborhoods"
    )
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("name", "district")
        verbose_name = "Neighborhood"
        verbose_name_plural = "Neighborhoods"

    def save(self, *args, **kwargs) -> None:
        """Auto-generate the neighborhood slug from the neighborhood name."""
        if not self.slug:
            self.slug = slugify(self.name) or "neighborhood"
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name
